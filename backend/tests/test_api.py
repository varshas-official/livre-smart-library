import os, sys, tempfile, unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from app import create_app
from database import init_db, get_db
from seed import seed_database
from werkzeug.security import generate_password_hash

class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)); self.app=create_app({"TESTING":True,"SECRET_KEY":"test-key","DATABASE":os.path.join(self.temp.name,"test.sqlite3")});self.client=self.app.test_client()
        with self.app.app_context():
            init_db();seed_database(get_db());get_db().execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("student","s@example.test","Test Student",generate_password_hash("test-pass")))
    def tearDown(self): self.temp.cleanup()
    def login(self): return self.client.post("/api/login",json={"identity":"student","password":"test-pass"})
    def test_login_and_protected_routes(self):
        self.assertEqual(self.client.get("/api/books").status_code,401)
        landing=self.client.get("/");self.assertIn(b"Sign in",landing.data);landing.close()
        self.assertEqual(self.login().status_code,200)
        landing=self.client.get("/");self.assertIn(b"page-content",landing.data);landing.close()
        self.assertEqual(self.client.get("/api/books").status_code,200)
        self.assertEqual(self.client.post("/api/login",json={"identity":"student","password":"wrong"}).status_code,401)
    def test_health_check_and_safe_unexpected_error(self):
        @self.app.get("/test-unexpected-error")
        def unexpected_error():
            raise RuntimeError("private filesystem path should not reach clients")
        self.assertEqual(self.client.get("/healthz").json,{"status":"ok"})
        response=self.client.get("/test-unexpected-error")
        self.assertEqual(response.status_code,500)
        self.assertNotIn("private filesystem path",response.get_data(as_text=True))
        self.assertEqual(response.json["error"],"An unexpected error occurred. Please try again.")
    def test_production_requires_external_secret_and_secure_cookie(self):
        with patch.dict(os.environ,{"APP_ENV":"production","SECRET_KEY":""}):
            with self.assertRaisesRegex(RuntimeError,"SECRET_KEY"):
                create_app()
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as temp, patch.dict(os.environ,{"APP_ENV":"production","SECRET_KEY":"a"*48,"COOKIE_SECURE":"false","DATABASE_PATH":os.path.join(temp,"prod.sqlite3")}):
            production_app=create_app({"TESTING":True})
            self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])
            self.assertFalse(production_app.config["DEBUG"])
    def test_search_filter_and_empty_result(self):
        self.login();self.assertGreater(self.client.get("/api/books?q=UML").json["total"],0);self.assertEqual(self.client.get("/api/books?q=definitely-no-match").json["total"],0)
        self.assertGreater(self.client.get("/api/books?category=UML%20and%20Modelling").json["total"],0)
        title_page=self.client.get("/api/books?sort=title&page=1&limit=3").json
        self.assertEqual([b["title"] for b in title_page["items"]],sorted(b["title"] for b in title_page["items"]))
        self.assertEqual(title_page["pages"],10);self.assertEqual(self.client.get("/api/books?page=2&limit=3").json["page"],2)
        available=self.client.get("/api/books?sort=availability&limit=30").json["items"]
        self.assertEqual([b["available_copies"] for b in available],sorted((b["available_copies"] for b in available),reverse=True))
    def test_availability_filter_uses_database_stock(self):
        self.login()
        self.assertEqual(self.client.get("/api/books?availability=maybe").status_code,400)
        data=self.client.get("/api/books?availability=available&limit=30").json
        self.assertTrue(data["items"])
        self.assertTrue(all(book["available_copies"]>0 for book in data["items"]))
        with self.app.app_context(): get_db().execute("UPDATE books SET available_copies=0 WHERE id=1")
        unavailable=self.client.get("/api/books?availability=unavailable&limit=30").json
        self.assertTrue(any(book["id"]==1 for book in unavailable["items"]))
        self.assertTrue(all(book["available_copies"]==0 for book in unavailable["items"]))
    def test_demo_password_command_updates_only_existing_student(self):
        with self.app.app_context():
            db=get_db();db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("other","other@example.test","Other User",generate_password_hash("other-pass")))
        result=self.app.test_cli_runner().invoke(args=["set-demo-password"])
        self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(self.client.post("/api/login",json={"identity":"student","password":"test-pass"}).status_code,401)
        self.assertEqual(self.client.post("/api/login",json={"identity":"student","password":"2026"}).status_code,200)
        with self.app.app_context():
            db=get_db();student=db.execute("SELECT password_hash FROM users WHERE username='student'").fetchone()[0]
            other=db.execute("SELECT password_hash FROM users WHERE username='other'").fetchone()[0]
            from werkzeug.security import check_password_hash
            self.assertTrue(check_password_hash(student,"2026"));self.assertFalse(check_password_hash(student,"test-pass"))
            self.assertTrue(check_password_hash(other,"other-pass"))
    def test_borrow_return_inventory_and_duplicate(self):
        self.login();book=self.client.get("/api/books?limit=1").json["items"][0];before=book["available_copies"]
        borrowed=self.client.post("/api/borrowings",json={"book_id":book["id"]});self.assertEqual(borrowed.status_code,201)
        with self.app.app_context(): self.assertEqual(get_db().execute("SELECT available_copies FROM books WHERE id=?",(book["id"],)).fetchone()[0],before-1)
        active=self.client.get("/api/borrowings").json["items"][0];self.assertEqual(self.client.post(f"/api/borrowings/{active['id']}/return").status_code,200);self.assertEqual(self.client.post(f"/api/borrowings/{active['id']}/return").status_code,409)
    def test_unavailable_book_and_active_loan_limit(self):
        self.login()
        with self.app.app_context():
            db=get_db();db.execute("UPDATE books SET available_copies=0 WHERE id=1")
            user_id=db.execute("SELECT id FROM users WHERE username='student'").fetchone()[0]
            db.execute("INSERT INTO borrow_records(user_id,book_id,borrowed_at,due_at,status) VALUES(?,?,date('now'),date('now','+14 days'),'active')",(user_id,2))
            db.execute("UPDATE books SET available_copies=available_copies-1 WHERE id=2")
            for book_id in (3,4,5,6):
                db.execute("INSERT INTO borrow_records(user_id,book_id,borrowed_at,due_at,status) VALUES(?,?,date('now'),date('now','+14 days'),'active')",(user_id,book_id))
                db.execute("UPDATE books SET available_copies=available_copies-1 WHERE id=?",(book_id,))
        self.assertEqual(self.client.post("/api/borrowings",json={"book_id":1}).status_code,400)
        self.assertIn("limit",self.client.post("/api/borrowings",json={"book_id":7}).json["error"])
    def test_concurrent_last_copy_has_one_winner(self):
        from werkzeug.security import generate_password_hash
        with self.app.app_context():
            db=get_db();db.execute("UPDATE books SET total_copies=1,available_copies=1 WHERE id=1")
            db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("reader2","reader2@example.test","Second Reader",generate_password_hash("pass-two")))
        def borrow_as(identity,password):
            client=self.app.test_client()
            self.assertEqual(client.post("/api/login",json={"identity":identity,"password":password}).status_code,200)
            return client.post("/api/borrowings",json={"book_id":1}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda pair:borrow_as(*pair),[("student","test-pass"),("reader2","pass-two")]))
        self.assertCountEqual(statuses,[201,400])
        with self.app.app_context():
            db=get_db();self.assertEqual(db.execute("SELECT available_copies FROM books WHERE id=1").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM borrow_records WHERE book_id=1 AND status='active'").fetchone()[0],1)
    def test_report_csv_and_invalid_dates(self):
        self.login();self.assertEqual(self.client.get("/api/reports?start=2030-01-02&end=2020-01-01").status_code,400)
        book=self.client.get("/api/books?limit=1").json["items"][0]
        self.client.post("/api/borrowings",json={"book_id":book["id"]})
        from datetime import date
        today=date.today().isoformat()
        report=self.client.get(f"/api/reports?start={today}&end={today}").json
        self.assertEqual(report["summary"]["total"],1);self.assertEqual(len(report["records"]),1)
        self.assertEqual(self.client.get("/api/reports?start=2030-01-01&end=2030-01-31").json["summary"]["total"],0)
        exported=self.client.get(f"/api/reports.csv?start={today}&end={today}")
        self.assertIn("text/csv",exported.content_type);self.assertIn(book["title"],exported.get_data(as_text=True))
        self.assertIn("filename=livre-borrowing-report.csv",exported.headers.get("Content-Disposition",""))

if __name__=="__main__": unittest.main()
