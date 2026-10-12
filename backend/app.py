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
    @app.get("/api/dashboard")
    @login_required
    def dashboard():
        db=get_db()
        return jsonify(total_books=db.execute("SELECT COALESCE(SUM(total_copies),0) FROM books").fetchone()[0],available=db.execute("SELECT COALESCE(SUM(available_copies),0) FROM books").fetchone()[0],borrowed=db.execute("SELECT COUNT(*) FROM borrow_records WHERE status='active'").fetchone()[0],overdue=db.execute("SELECT COUNT(*) FROM borrow_records WHERE status='active' AND due_at<?",(date.today().isoformat(),)).fetchone()[0],featured=[dict(r) for r in db.execute("SELECT * FROM books ORDER BY available_copies DESC,title LIMIT 4")])
    return app

app=create_app()
if __name__=="__main__": app.run(debug=os.getenv("FLASK_DEBUG","false").lower()=="true",port=int(os.getenv("PORT",5000)))
