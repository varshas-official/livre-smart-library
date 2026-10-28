# LIVRE — Your Reading Space

A beginner-friendly library management application for an academic software engineering collection. The application uses vanilla HTML/CSS/JavaScript, Flask, and SQLite. Its interface follows the supplied visual reference's forest-green library shell and editorial book catalogue. Inventory counts and shelf codes are illustrative local data; bibliographic title/author fields are catalogue metadata, not claims about this institution's holdings.

## Four modules

1. **Login** — database-backed password hashing and Flask session.
2. **Search Books** — keyword, category, sorting, pagination, and book details.
3. **Borrow Books** — 14-day loans, five-active-loan limit, return tracking, and transactional stock changes.
4. **Generate Report** — date-filtered history, summary metrics, most-borrowed titles, trend chart, and CSV export.

The dashboard supports those modules; it is not a fifth primary module.

## Stack and architecture

- Frontend: semantic HTML5, CSS3, vanilla JavaScript, Fetch API; Chart.js from CDN for charts.
- Backend: Python 3.12+, Flask, Werkzeug password hashing.
- Database: SQLite with foreign keys, checks, indexes, parameterized queries, and explicit transactions.
- OOAD: Entity objects in `backend/models.py`; boundary in Flask API and browser pages; controls in `backend/services.py`; persistence in `backend/database.py`.

## Project structure

```text
frontend/                 login, app shell, CSS and browser code
backend/
  app.py                  Flask routes and application factory
  database.py             SQLite connection/schema setup
  schema.sql              relational schema and constraints
  models.py               User, Book, BorrowRecord entities
  services.py             authentication/catalogue/borrowing/report controls
  seed.py                 academic catalogue, sample inventory
  tests/test_api.py       Flask test-client acceptance tests
.env.example              documented environment configuration
render.yaml               Render full-stack deployment Blueprint
```

## Data model

`users` stores a unique username, email, full name, and password hash. `books` stores catalogue metadata and checked stock counts. `borrow_records` relates users and books and stores borrow, due, return dates, and active/returned state. Foreign keys and indexes are enabled for every connection. Demo inventory counts are sample values, not bibliographic facts.

## Windows PowerShell setup

From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
Copy-Item .env.example .env
$env:FLASK_APP = "backend\app.py"
flask init-db
$env:DEMO_PASSWORD = "choose-a-local-demo-password"
flask create-demo-user
Remove-Item Env:DEMO_PASSWORD
python backend\app.py
```

Install Python 3.12 first if `py -3.12` is not available.

Before setup, replace `SECRET_KEY` in `.env` with a long random local value. Open `http://127.0.0.1:5000`. Sign in as `student` (or `student@example.edu`). For the local classroom account, `flask set-demo-password` updates only the existing `student` account's Werkzeug password hash to `2026`; it preserves all other users, catalogue rows, and borrowing history. Do not enable this demo credential in a public deployment; set `APP_ENV=production`, which disables both demo-account commands. To create a new local demo account, use `DEMO_PASSWORD` with `flask create-demo-user`; that command refuses to overwrite an existing account. Account commands never print or save the password. The fallback development secret is not suitable for deployment. On Windows, if activation is blocked for the current shell, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that PowerShell session.

`flask init-db` creates and seeds the SQLite file at `backend/instance/library.sqlite3` by default. Set `DATABASE_PATH` to use another path. Seeding is safe to repeat; the required Ali Bahrami title and attribution are preserved exactly as requested, with edition, publisher, and ISBN left blank because the bibliographic record could not be verified under that exact title.

## DSA Lab extension

The DSA Lab page (#dsa) demonstrates four explicitly implemented algorithms/data structures:

- backend/dsa_algorithms.py contains a separate-chaining hash table for exact book-ID/ISBN lookup, a binary search tree for title ordering, a circular array FIFO queue for reservation ordering, and stable Merge Sort with comparison counting.
- Unavailable books can be placed on a persistent reservation queue. The first pending requester has borrowing priority when stock becomes available; later requesters cannot bypass the queue. Pending requests can be cancelled.
- /api/dsa/lookup, /api/dsa/catalogue, and /api/dsa/analysis provide demonstrations and operation counts. Hash-index construction is reported separately from lookup complexity.
- Popular-title report rows are sorted by the custom Merge Sort rather than delegated to SQL ORDER BY.
- The database schema creates the reservations table and pending-request indexes when flask init-db or WSGI database initialization is run.

The SQLite table is the durable reservation record; the custom queue is rebuilt from pending rows in ID order when a queue operation is needed. Thus the in-memory queue operation is O(Q) to hydrate from persistent rows plus O(1) per enqueue/dequeue. The BST is intentionally unbalanced, so insertion is O(B log B) on average and O(B^2) in the worst case. These limitations are surfaced in the UI rather than hidden.

## Tests

```powershell
python -m unittest discover -s backend\tests -v
```

Tests use a temporary database and Flask test client; they cover authentication, protected endpoints, catalogue search/filter/empty result, borrow and return stock consistency, duplicate return rejection, date validation, and CSV response. Availability search accepts `availability=available` or `availability=unavailable` in addition to the other catalogue filters.

## API endpoints

| Method | Path | Session | Purpose |
|---|---|---|---|
| POST | `/api/login` | No | Authenticate username/email and password |
| POST | `/api/logout` | No | Clear session |
| GET | `/api/me` | No | Current user summary |
| GET | `/api/books` | Yes | Search/filter/sort/page catalogue |
| GET | `/api/books/<id>` | Yes | Book details |
| GET | `/api/borrowings` | Yes | Current user's borrowing history |
| POST | `/api/borrowings` | Yes | Borrow a book |
| POST | `/api/borrowings/<id>/return` | Yes | Return an active loan |
| GET | `/api/reports` | Yes | Filtered report JSON |
| GET | `/api/reports.csv` | Yes | Same filtered rows as CSV |
| GET | `/api/dashboard` | Yes | Live catalogue and loan summaries |

Date filters use ISO `YYYY-MM-DD`; report dates filter on borrowing date. Search accepts `q`, `category`, `sort`, `page`, and `limit`.

## Rules and known limits

- A member may have at most five active loans; each loan is 14 days. These are constants in `BorrowingService` and easy to change for the lab.
- SQLite `BEGIN IMMEDIATE` and conditional stock decrement serialize competing last-copy borrows. Returning an inactive or foreign user's record is rejected.
- User Activity report rows include member names and are available to any authenticated demo user; add an administrator authorization boundary before using real member data.
- Chart.js and Google Fonts load from public CDNs; their failure does not break core login/catalogue functions, but the report chart and custom typography may fall back.
- No PDF generation, password reset, registration UI, or automated browser suite is included. A production deployment has not been performed.

## GitHub workflow (review before staging)

```powershell
git status --short
git diff --check
git add README.md .gitignore .env.example render.yaml frontend backend
git diff --cached --stat
git diff --cached
git commit -m "Refine LIVRE smart library system"
```

Never commit `.env`, `.venv`, checkpoints, or the local SQLite database. This folder may contain a local `docs/` report draft; it is not required for the running site and is intentionally excluded from the suggested stage command. Review `git status --short`, then `git diff --cached` before committing. To create and connect a GitHub repository, create an empty private or public repository in your GitHub account (do not initialize it with a README), then run `git remote add origin https://github.com/USER/REPOSITORY.git` and `git push -u origin master`. Replace `USER/REPOSITORY` locally; never paste a GitHub token into chat or a source file.

## Local and production configuration

The browser uses same-origin relative `/api/...` URLs, so the simplest deployment serves the existing HTML/CSS/JavaScript and Flask API from one HTTPS origin. No CORS extension or frontend API URL is needed. `/healthz` checks SQLite connectivity. Production requires a supplied `SECRET_KEY`, forces secure session cookies, and has debug disabled. Unexpected server errors are logged server-side and return a generic message to the browser.

### Run the production-style server locally (optional)

On Windows, use Flask's development server for local work. Gunicorn is intentionally installed only on non-Windows systems; the production command is defined by the Render Blueprint. To validate the WSGI entrypoint on Linux/macOS:

```sh
APP_ENV=production SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
DATABASE_PATH=/tmp/livre.sqlite3 INITIAL_USER_PASSWORD="use-a-private-16-character-or-longer-secret" \
gunicorn --chdir backend --workers 1 --threads 4 --bind 0.0.0.0:8000 wsgi:app
```

The production WSGI startup creates the schema and idempotently seeds catalogue entries on the mounted database; it never copies your local SQLite file. On a brand-new empty database, set `INITIAL_USER_PASSWORD` to a strong password of at least 16 characters. The first username/email/name default to `reader`, `reader@example.invalid`, and `Library Reader` and can be changed using `INITIAL_USER_USERNAME`, `INITIAL_USER_EMAIL`, and `INITIAL_USER_FULL_NAME`. It stores only a Werkzeug password hash. After first boot, remove the bootstrap secret from host settings. Existing accounts are never overwritten. The local `student` classroom account is not seeded on production.

### Render deployment (prepared; not deployed)

`render.yaml` defines one Python web service that serves both frontend and API over HTTPS with Gunicorn and a 1 GB SQLite persistent disk mounted at `/var/data`. This design avoids cross-origin browser requests. Render's free web services have ephemeral filesystems and cannot attach persistent disks; they also spin down after 15 minutes, and free Postgres expires after 30 days. A persistent SQLite setup therefore needs a paid service plan; Render currently lists the Starter service at about $7/month and the 1 GB disk at $0.25/month, before workspace or bandwidth charges. Check Render's current dashboard pricing before creating the service. A single disk-backed instance is appropriate for this small student demonstration; it is not a highly available multi-instance database. Set up a separate backup/export routine for data you need to retain.

Deployment steps:

1. Create an empty GitHub repository and push the reviewed project branch using the Git commands above.
2. Sign in to Render and choose **New → Blueprint**; connect that GitHub repository and select its `render.yaml`.
3. When prompted for `INITIAL_USER_PASSWORD`, enter a private, unique password of at least 16 characters directly in Render. Do not reuse the local demo password or share this value in chat.
4. Review the Blueprint's paid compute and disk charges, confirm the disk path is `/var/data`, and create the service only if those costs are acceptable.
5. Wait for the service to become Live, then open its actual `https://…onrender.com` URL and test `/healthz`, login, search, borrow/return, reports, and CSV export.
6. Remove `INITIAL_USER_PASSWORD` from the service environment after the first account is provisioned, then redeploy. The hashed user remains on the persistent disk.
7. Confirm the service is paid and disk-backed before using library data. Never upload the local `.env` or local database; Render seeds its own empty database.

GitHub Pages alone cannot host Flask or persistent SQLite operations. No GitHub remote or Render account has been connected from this workspace, so no public URL or completed deployment is claimed.
