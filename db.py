"""SQLite storage layer for the News Dashboard."""

import sqlite3
from datetime import datetime, timezone

DB_NAME = "news.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create news.db and the articles table if they don't already exist."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT UNIQUE,
                source TEXT,
                published_date TEXT,
                fetched_date TEXT,
                tags TEXT,
                status TEXT DEFAULT 'new',
                notes TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_article(article):
    """Insert an article dict into the DB, skipping it if the URL already exists.

    Expected keys: title, url, source, published_date, tags (optional),
    status (optional, defaults to 'new'), notes (optional).

    Returns True if the article was inserted, False if it was a duplicate (by url).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (title, url, source, published_date, fetched_date, tags, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.get("title"),
                article.get("url"),
                article.get("source"),
                article.get("published_date"),
                article.get("fetched_date") or datetime.now(timezone.utc).isoformat(),
                article.get("tags"),
                article.get("status", "new"),
                article.get("notes"),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_articles(filters=None):
    """Return articles matching the given filters.

    filters is an optional dict that may contain:
        status: exact match on status
        source: exact match on source
        tags: substring match against the tags column
        keyword: substring match against title
        date_from: published_date >= this value
        date_to: published_date <= this value

    Returns a list of dicts, most recently fetched first.
    """
    filters = filters or {}
    query = "SELECT * FROM articles WHERE 1=1"
    params = []

    if filters.get("status"):
        query += " AND status = ?"
        params.append(filters["status"])

    if filters.get("source"):
        query += " AND source = ?"
        params.append(filters["source"])

    if filters.get("tags"):
        query += " AND tags LIKE ?"
        params.append(f"%{filters['tags']}%")

    if filters.get("keyword"):
        query += " AND title LIKE ?"
        params.append(f"%{filters['keyword']}%")

    if filters.get("date_from"):
        query += " AND published_date >= ?"
        params.append(filters["date_from"])

    if filters.get("date_to"):
        query += " AND published_date <= ?"
        params.append(filters["date_to"])

    query += " ORDER BY fetched_date DESC"

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_article_status(id, status, notes=None):
    """Update an article's status (and optionally its notes) by id.

    Returns True if a row was updated, False if no article had that id.
    """
    conn = get_connection()
    try:
        if notes is not None:
            cursor = conn.execute(
                "UPDATE articles SET status = ?, notes = ? WHERE id = ?",
                (status, notes, id),
            )
        else:
            cursor = conn.execute(
                "UPDATE articles SET status = ? WHERE id = ?",
                (status, id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
