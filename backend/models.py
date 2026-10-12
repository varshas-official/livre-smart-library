"""Small domain objects used by services and API responses (Entity layer)."""
from dataclasses import dataclass

@dataclass
class User:
    id: int
    username: str
    email: str
    full_name: str

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["username"], row["email"], row["full_name"])

@dataclass
class Book:
    id: int
    title: str
    authors: str
    category: str
    available_copies: int
    total_copies: int

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["title"], row["authors"], row["category"], row["available_copies"], row["total_copies"])

@dataclass
class BorrowRecord:
    id: int
    user_id: int
    book_id: int
    borrowed_at: str
    due_at: str
    returned_at: str | None
    status: str

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["user_id"], row["book_id"], row["borrowed_at"], row["due_at"], row["returned_at"], row["status"])
