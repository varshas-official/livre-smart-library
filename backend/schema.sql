PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY,
 username TEXT NOT NULL UNIQUE,
 email TEXT NOT NULL UNIQUE,
 full_name TEXT NOT NULL,
 password_hash TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY,
 title TEXT NOT NULL,
 authors TEXT NOT NULL,
 category TEXT NOT NULL,
 edition TEXT,
 publisher TEXT,
 isbn TEXT UNIQUE,
 description TEXT NOT NULL DEFAULT '',
 cover TEXT NOT NULL DEFAULT '',
 total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
 available_copies INTEGER NOT NULL CHECK(available_copies >= 0 AND available_copies <= total_copies),
 shelf TEXT NOT NULL DEFAULT 'TBD',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS borrow_records (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id),
 borrowed_at TEXT NOT NULL,
 due_at TEXT NOT NULL,
 returned_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('active','returned')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_books_category ON books(category);
CREATE INDEX IF NOT EXISTS idx_borrow_user_status ON borrow_records(user_id,status);
CREATE INDEX IF NOT EXISTS idx_borrow_dates ON borrow_records(borrowed_at,due_at);


-- DSA extension: persistent FIFO reservation requests for unavailable titles.
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id),
 requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 status TEXT NOT NULL CHECK(status IN ('pending','fulfilled','cancelled')),
 fulfilled_borrow_id INTEGER REFERENCES borrow_records(id)
);
CREATE INDEX IF NOT EXISTS idx_reservations_book_status_id ON reservations(book_id,status,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_one_pending_per_user_book
 ON reservations(user_id,book_id) WHERE status='pending';
