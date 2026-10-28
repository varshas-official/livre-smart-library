"""Flask application factory and HTTP Boundary/API layer."""
import csv, io, os
from datetime import date
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, send_from_directory, Response
from werkzeug.exceptions import HTTPException
from database import get_db, init_app as init_database, init_db
from seed import seed_database
from services import AuthenticationService, CatalogService, BorrowingService, ReportService
from dsa_algorithms import FIFOQueue, build_book_hash_index, build_title_bst, merge_sort, resolve_book_lookup_key

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

def create_app(test_config=None):
    app=Flask(__name__,static_folder="../frontend",static_url_path="")
    production=os.getenv("APP_ENV", "development").lower() == "production"
    secret=os.getenv("SECRET_KEY")
    if production and (not secret or len(secret) < 32):
        raise RuntimeError("Production requires a SECRET_KEY with at least 32 characters.")
    app.config.from_mapping(SECRET_KEY=secret or "dev-only-change-me",DATABASE=os.getenv("DATABASE_PATH",str(Path(__file__).resolve().parent/"instance"/"library.sqlite3")),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=production or os.getenv("COOKIE_SECURE","false").lower()=="true",PERMANENT_SESSION_LIFETIME=60*60*8,DEBUG=False)
    if test_config: app.config.update(test_config)
    init_database(app)
    @app.get("/healthz")
    def health_check():
        try:
            get_db().execute("SELECT 1").fetchone()
            return jsonify(status="ok"), 200
        except Exception:
            app.logger.exception("Health check failed")
            return jsonify(status="unavailable"), 503

    @app.errorhandler(Exception)
    def safe_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unhandled application error")
        return jsonify(error="An unexpected error occurred. Please try again."), 500
    @app.cli.command("init-db")
    def initialize():
        init_db(); seed_database(get_db()); print("Database initialized and catalogue seeded.")
    @app.cli.command("create-demo-user")
    def create_demo_user():
        """Create a development-only account using environment-provided password."""
        from werkzeug.security import generate_password_hash
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise SystemExit("The demo account is disabled in production.")
        password=os.getenv("DEMO_PASSWORD")
        if not password: raise SystemExit("Set DEMO_PASSWORD before running this command.")
        db=get_db(); init_db()
        try: db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("student","student@example.edu","Student Reader",generate_password_hash(password)))
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc): raise SystemExit("Student account already exists; use set-demo-password to update its local credential.")
            raise
        db.commit()
        print("Demo user ready: student / student@example.edu")
    @app.cli.command("set-demo-password")
    def set_demo_password():
        """Set the local classroom demo password without touching other accounts."""
        from werkzeug.security import generate_password_hash
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise SystemExit("This local demo credential cannot be enabled in production or debug mode.")
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE username=?", ("student",)).fetchone()
        if not user:
            raise SystemExit("No existing student account found. Create the local demo account first.")
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash("2026"), user["id"]))
        db.commit()
        print("Local demo password updated for the existing student account.")
    def login_required(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not session.get("user_id"): return jsonify(error="Please sign in to continue."),401
            return fn(*args,**kwargs)
        return wrapped
    @app.get("/")
    def index(): return send_from_directory(app.static_folder,"index.html" if session.get("user_id") else "login.html")
    @app.get("/favicon.ico")
    def favicon(): return send_from_directory(Path(app.static_folder)/"assets","favicon.svg",mimetype="image/svg+xml")
    @app.post("/api/login")
    def login():
        data=request.get_json(silent=True) or {}; identity=(data.get("identity") or "").strip(); password=data.get("password") or ""
        if not identity or not password: return jsonify(error="Enter your username or email and password."),400
        user=AuthenticationService(get_db()).authenticate(identity,password)
        if not user: return jsonify(error="The username/email or password is incorrect."),401
        session.clear(); session["user_id"]=user["id"];session["user_name"]=user["full_name"];session.permanent=True
        return jsonify(user={"id":user["id"],"username":user["username"],"full_name":user["full_name"]})
    @app.post("/api/logout")
    def logout(): session.clear(); return jsonify(message="Signed out.")
    @app.get("/api/me")
    def me():
        if not session.get("user_id"): return jsonify(user=None)
        return jsonify(user={"id":session["user_id"],"full_name":session.get("user_name")})
    @app.get("/api/books")
    @login_required
    def books():
        try:
            page=max(1,int(request.args.get("page",1))); limit=min(36,max(1,int(request.args.get("limit",12))))
        except ValueError: return jsonify(error="Page and limit must be whole numbers."),400
        availability=request.args.get("availability", "")
        if availability not in ("", "available", "unavailable"): return jsonify(error="Availability must be available or unavailable."),400
        result=CatalogService(get_db()).search(request.args.get("q",""),request.args.get("category",""),request.args.get("sort","title"),page,limit,availability)
        result["categories"]=[r[0] for r in get_db().execute("SELECT DISTINCT category FROM books ORDER BY category")]
        return jsonify(result)
    @app.get("/api/books/<int:book_id>")
    @login_required
    def book_detail(book_id):
        row=get_db().execute("SELECT * FROM books WHERE id=?",(book_id,)).fetchone()
        if not row: return jsonify(error="Book not found."),404
        return jsonify(book=dict(row))
    @app.get("/api/borrowings")
    @login_required
    def borrowings(): return jsonify(items=BorrowingService(get_db()).mine(session["user_id"]))
    @app.post("/api/borrowings")
    @login_required
    def borrow():
        data=request.get_json(silent=True) or {}
        try: book_id=int(data.get("book_id")); record_id,due=BorrowingService(get_db()).borrow(session["user_id"],book_id)
        except (ValueError,TypeError) as exc: return jsonify(error=str(exc) or "A valid book is required."),400
        return jsonify(message="Book borrowed successfully.",record_id=record_id,due_at=due),201
    @app.post("/api/borrowings/<int:record_id>/return")
    @login_required
    def return_book(record_id):
        try: BorrowingService(get_db()).return_book(session["user_id"],record_id)
        except ValueError as exc: return jsonify(error=str(exc)),409
        return jsonify(message="Book returned successfully.")
    def report_params():
        start=request.args.get("start") or None; end=request.args.get("end") or None
        try:
            if start: date.fromisoformat(start)
            if end: date.fromisoformat(end)
            if start and end and start>end: raise ValueError()
        except ValueError: return None,None,(jsonify(error="Use valid dates and ensure the start date is not after the end date."),400)
        return start,end,None
    @app.get("/api/reports")
    @login_required
    def reports():
        start,end,error=report_params()
        if error:return error
        return jsonify(ReportService(get_db()).data(start,end))
    @app.get("/api/reports.csv")
    @login_required
    def report_csv():
        start,end,error=report_params()
        if error:return error
        report=ReportService(get_db()).data(start,end); output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=["id","borrowed_at","due_at","returned_at","status","full_name","username","title","authors"]);writer.writeheader();writer.writerows(report["records"])
        return Response(output.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=livre-borrowing-report.csv"})
    def pending_reservation_queue(db, book_id):
        rows = [dict(row) for row in db.execute("SELECT id,user_id,book_id,requested_at,status FROM reservations WHERE book_id=? AND status='pending' ORDER BY id",(book_id,)).fetchall()]
        queue = FIFOQueue(max(1, len(rows) + 1))
        for row in rows:
            queue.enqueue(row)
        return queue

    @app.get("/api/reservations")
    @login_required
    def list_reservations():
        db = get_db()
        pending_rows = [dict(row) for row in db.execute("SELECT id,user_id,book_id FROM reservations WHERE status='pending' ORDER BY id").fetchall()]
        by_book = {}
        for row in pending_rows:
            by_book.setdefault(row["book_id"], []).append(row)
        positions = {}
        for rows in by_book.values():
            queue = FIFOQueue(max(1, len(rows)))
            for row in rows:
                queue.enqueue(row)
            for position, row in enumerate(queue.to_list(), start=1):
                positions[row["id"]] = position
        rows = db.execute("SELECT r.id,r.book_id,r.requested_at,r.status,r.fulfilled_borrow_id,b.title,b.authors,b.available_copies FROM reservations r JOIN books b ON b.id=r.book_id WHERE r.user_id=? ORDER BY r.id DESC",(session["user_id"],)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["queue_position"] = positions.get(item["id"])
            items.append(item)
        return jsonify(items=items)

    @app.post("/api/reservations")
    @login_required
    def create_reservation():
        data = request.get_json(silent=True) or {}
        try:
            book_id = int(data.get("book_id"))
        except (TypeError, ValueError):
            return jsonify(error="A valid book ID is required."), 400
        db = get_db()
        db.execute("BEGIN IMMEDIATE")
        try:
            book = db.execute("SELECT id,available_copies FROM books WHERE id=?",(book_id,)).fetchone()
            if not book:
                db.rollback()
                return jsonify(error="Book not found."),404
            active = db.execute("SELECT id FROM borrow_records WHERE user_id=? AND book_id=? AND status='active'",(session["user_id"],book_id)).fetchone()
            if active:
                db.rollback()
                return jsonify(error="You already have this book on loan."),409
            pending = db.execute("SELECT id FROM reservations WHERE user_id=? AND book_id=? AND status='pending'",(session["user_id"],book_id)).fetchone()
            if pending:
                db.rollback()
                return jsonify(error="You already have a pending reservation for this title."),409
            queue = pending_reservation_queue(db, book_id)
            if book["available_copies"] > 0 and len(queue) == 0:
                db.rollback()
                return jsonify(error="This title is available. Borrow it directly instead of joining the queue."),409
            db.execute("INSERT INTO reservations(user_id,book_id,status) VALUES(?,?,'pending')",(session["user_id"],book_id))
            reservation_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            queue.enqueue({"id":reservation_id,"user_id":session["user_id"],"book_id":book_id,"status":"pending"})
            position = len(queue)
            db.commit()
            return jsonify(message="You joined the reservation queue.",reservation_id=reservation_id,queue_position=position),201
        except Exception:
            db.rollback()
            raise

    @app.delete("/api/reservations/<int:reservation_id>")
    @login_required
    def cancel_reservation(reservation_id):
        db = get_db()
        changed = db.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND user_id=? AND status='pending'",(reservation_id,session["user_id"])).rowcount
        if not changed:
            return jsonify(error="Pending reservation not found."),404
        return jsonify(message="Reservation cancelled.")

    @app.get("/api/dsa/lookup")
    @login_required
    def dsa_book_lookup():
        raw_key = (request.args.get("key") or "").strip()
        if not raw_key:
            return jsonify(error="Enter a book ID or ISBN. Prefix with ID: or ISBN: if needed."),400
        rows = [dict(row) for row in get_db().execute("SELECT * FROM books").fetchall()]
        table = build_book_hash_index(rows)
        try:
            resolved_key = resolve_book_lookup_key(raw_key)
        except (ValueError, TypeError):
            return jsonify(error="Use a valid book ID such as ID:12 or an ISBN value."),400
        book, comparisons = table.get_with_comparisons(resolved_key)
        return jsonify(found=book is not None,book=book,lookup_key=resolved_key,lookup_comparisons=comparisons,
                       indexed_books=len(rows),indexed_keys=len(table),hash_collisions=table.collisions,
                       complexity="Building the index is O(B); lookup is expected O(1), worst-case O(B) after build.")

    @app.get("/api/dsa/catalogue")
    @login_required
    def dsa_bst_catalogue():
        try:
            limit = min(60,max(1,int(request.args.get("limit",60))))
        except ValueError:
            return jsonify(error="Limit must be a whole number."),400
        rows = [dict(row) for row in get_db().execute("SELECT * FROM books").fetchall()]
        tree = build_title_bst(rows)
        ordered = tree.in_order()
        return jsonify(items=ordered[:limit],total=len(ordered),bst_nodes=tree.node_count,
                       bst_height=tree.height(),insert_comparisons=tree.insert_comparisons,
                       complexity="In-order traversal is O(B); unbalanced BST insertion is O(B log B) on average and O(B^2) in the worst case.")

    @app.get("/api/dsa/analysis")
    @login_required
    def dsa_analysis():
        db = get_db()
        rows = [dict(row) for row in db.execute("SELECT * FROM books").fetchall()]
        if not rows:
            return jsonify(error="The catalogue is empty."),404
        target = rows[-1]
        linear_comparisons = 0
        for row in rows:
            linear_comparisons += 1
            if int(row["id"]) == int(target["id"]):
                break
        table = build_book_hash_index(rows)
        _, hash_comparisons = table.get_with_comparisons("id:"+str(int(target["id"])))
        tree = build_title_bst(rows)
        sorted_by_merge, merge_comparisons = merge_sort(rows,key=lambda row:(str(row.get("title","")).casefold(),int(row["id"])))
        report_metrics = ReportService(db).data().get("dsa_metrics",{})
        return jsonify(catalogue_count=len(rows),target_title=target["title"],target_book_id=target["id"],
                       linear_search_comparisons=linear_comparisons,hash_lookup_comparisons=hash_comparisons,
                       hash_index_build_records=len(rows),hash_collisions=table.collisions,
                       bst_nodes=tree.node_count,bst_height=tree.height(),bst_insert_comparisons=tree.insert_comparisons,
                       merge_sort_comparisons=merge_comparisons,merge_sort_preview=sorted_by_merge[:10],
                       report_merge_sort_comparisons=report_metrics.get("popular_sort_comparisons",0),
                       note="Hash lookup comparisons exclude the one-time O(B) index-construction cost.")

    @app.get("/api/dashboard")
    @login_required
    def dashboard():
        db=get_db()
        return jsonify(total_books=db.execute("SELECT COALESCE(SUM(total_copies),0) FROM books").fetchone()[0],available=db.execute("SELECT COALESCE(SUM(available_copies),0) FROM books").fetchone()[0],borrowed=db.execute("SELECT COUNT(*) FROM borrow_records WHERE status='active'").fetchone()[0],overdue=db.execute("SELECT COUNT(*) FROM borrow_records WHERE status='active' AND due_at<?",(date.today().isoformat(),)).fetchone()[0],featured=[dict(r) for r in db.execute("SELECT * FROM books ORDER BY available_copies DESC,title LIMIT 4")])
    return app

app=create_app()
if __name__=="__main__": app.run(debug=os.getenv("FLASK_DEBUG","false").lower()=="true",port=int(os.getenv("PORT",5000)))
