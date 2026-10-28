"""Control layer: authentication, catalogue, borrowing and report use cases."""
from datetime import date, datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from dsa_algorithms import FIFOQueue, merge_sort

class AuthenticationService:
    def __init__(self, db): self.db = db
    def authenticate(self, identity, password):
        row = self.db.execute("SELECT * FROM users WHERE username=? OR email=?", (identity, identity)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password): return None
        return row
    def create_user(self, username, email, full_name, password):
        self.db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)", (username,email,full_name,generate_password_hash(password)))

class CatalogService:
    def __init__(self, db): self.db = db
    def search(self, q="", category="", sort="title", page=1, limit=12, availability=""):
        clauses, args = [], []
        if q:
            clauses.append("(title LIKE ? OR authors LIKE ? OR COALESCE(isbn,'') LIKE ? OR description LIKE ? OR category LIKE ?)")
            args.extend([f"%{q}%"]*5)
        if category: clauses.append("category=?"); args.append(category)
        if availability == "available": clauses.append("available_copies>0")
        elif availability == "unavailable": clauses.append("available_copies=0")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = {"title":"title COLLATE NOCASE ASC", "availability":"available_copies DESC, title COLLATE NOCASE ASC", "available":"available_copies DESC, title COLLATE NOCASE ASC"}.get(sort, "title COLLATE NOCASE ASC")
        total = self.db.execute("SELECT COUNT(*) FROM books"+where,args).fetchone()[0]
        rows = self.db.execute(f"SELECT * FROM books{where} ORDER BY {order} LIMIT ? OFFSET ?", args+[limit,(page-1)*limit]).fetchall()
        return {"items":[dict(r) for r in rows],"total":total,"page":page,"pages":(total+limit-1)//limit}

class BorrowingService:
    LOAN_DAYS = 14
    MAX_ACTIVE = 5
    def __init__(self, db): self.db = db
    def borrow(self, user_id, book_id):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            active = self.db.execute("SELECT COUNT(*) FROM borrow_records WHERE user_id=? AND status='active'",(user_id,)).fetchone()[0]
            if active >= self.MAX_ACTIVE: raise ValueError("You have reached the limit of 5 active loans.")
            existing = self.db.execute("SELECT id FROM borrow_records WHERE user_id=? AND book_id=? AND status='active'",(user_id,book_id)).fetchone()
            if existing: raise ValueError("You already have this book on loan.")
            # Reservation requests are served in FIFO order.
            pending_rows = self.db.execute("SELECT id,user_id FROM reservations WHERE book_id=? AND status='pending' ORDER BY id",(book_id,)).fetchall()
            reservation_queue = FIFOQueue(max(1, len(pending_rows)))
            for reservation in pending_rows:
                reservation_queue.enqueue(dict(reservation))
            first_reservation = reservation_queue.peek()
            if first_reservation and first_reservation["user_id"] != user_id:
                raise ValueError("This book is reserved for the next person in the waiting queue.")
            changed = self.db.execute("UPDATE books SET available_copies=available_copies-1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND available_copies>0",(book_id,)).rowcount
            if not changed: raise ValueError("This book is unavailable or no longer exists.")
            today = date.today(); due = today + timedelta(days=self.LOAN_DAYS)
            cur = self.db.execute("INSERT INTO borrow_records(user_id,book_id,borrowed_at,due_at,status) VALUES(?,?,?,?, 'active')",(user_id,book_id,today.isoformat(),due.isoformat()))
            if first_reservation:
                self.db.execute("UPDATE reservations SET status='fulfilled', fulfilled_borrow_id=? WHERE id=? AND status='pending'",(cur.lastrowid,first_reservation["id"]))
            self.db.commit()
            return cur.lastrowid, due.isoformat()
        except Exception:
            self.db.rollback(); raise
    def return_book(self, user_id, record_id):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            record = self.db.execute("SELECT * FROM borrow_records WHERE id=? AND user_id=? AND status='active'",(record_id,user_id)).fetchone()
            if not record: raise ValueError("Active borrowing record not found; it may already have been returned.")
            today = date.today().isoformat()
            self.db.execute("UPDATE borrow_records SET status='returned',returned_at=? WHERE id=?",(today,record_id))
            self.db.execute("UPDATE books SET available_copies=MIN(total_copies,available_copies+1),updated_at=CURRENT_TIMESTAMP WHERE id=?",(record["book_id"],))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
    def mine(self,user_id):
        rows=self.db.execute("SELECT br.*,b.title,b.authors,b.cover,b.shelf FROM borrow_records br JOIN books b ON b.id=br.book_id WHERE br.user_id=? ORDER BY CASE br.status WHEN 'active' THEN 0 ELSE 1 END,br.borrowed_at DESC",(user_id,)).fetchall()
        return [dict(r) for r in rows]

class ReportService:
    def __init__(self,db): self.db=db
    def data(self,start=None,end=None,kind="history"):
        clauses,args=[],[]
        if start: clauses.append("br.borrowed_at>=?");args.append(start)
        if end: clauses.append("br.borrowed_at<=?");args.append(end)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        records=self.db.execute("SELECT br.id,br.borrowed_at,br.due_at,br.returned_at,br.status,u.full_name,u.username,b.title,b.authors FROM borrow_records br JOIN users u ON u.id=br.user_id JOIN books b ON b.id=br.book_id"+where+" ORDER BY br.borrowed_at DESC",args).fetchall()
        today=date.today().isoformat()
        summary={"total":len(records),"active":sum(r["status"]=="active" for r in records),"returned":sum(r["status"]=="returned" for r in records),"overdue":sum(r["status"]=="active" and r["due_at"]<today for r in records)}
        popular_rows = [dict(r) for r in self.db.execute("SELECT b.title,COUNT(*) AS borrow_count FROM borrow_records br JOIN books b ON b.id=br.book_id"+where+" GROUP BY b.id",args).fetchall()]
        popular_sorted, popular_sort_comparisons = merge_sort(popular_rows, key=lambda row: (-int(row["borrow_count"]), str(row["title"]).casefold()))
        popular = popular_sorted[:10]
        trend={}
        for r in records: trend[r["borrowed_at"][:7]]=trend.get(r["borrowed_at"][:7],0)+1
        return {"summary":summary,"records":[dict(r) for r in records],"popular":popular,"trend":[{"month":k,"count":v} for k,v in sorted(trend.items())],"dsa_metrics":{"popular_sort_algorithm":"Merge Sort","popular_sort_comparisons":popular_sort_comparisons}}
