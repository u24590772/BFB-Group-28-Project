import os
import pymysql
import pymysql.cursors
from flask import g, has_app_context
from config import get_config

cfg = get_config()


def connect():
    """
    Opens a direct connection to Aiven MySQL with DictCursor.
    Reads host, port, user, password, and database from config.
    """
    return pymysql.connect(
        host=cfg.DB_HOST,
        port=cfg.DB_PORT,
        user=cfg.DB_USER,
        password=cfg.DB_PASSWORD,
        database=cfg.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=15,
    )


def get_db():
    """
    Returns the database connection for the current Flask request context.
    Stored on flask.g so connections are reused across the request lifecycle.
    """
    if has_app_context():
        if "db" not in g:
            g.db = connect()
        return g.db
    return connect()


def close_db(exception=None):
    """
    Closes the database connection on request teardown, preventing connection leaks.
    """
    db = g.pop("db", None) if has_app_context() else None
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_app(app):
    """
    Registers the connection teardown hook with the Flask application.
    """
    app.teardown_appcontext(close_db)


def query_all(sql, params=None):
    """
    Runs a SELECT query using %s placeholders and returns all rows as a list of dicts.
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    """
    Runs a SELECT query using %s placeholders and returns the first row or None.
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    """
    Runs an INSERT, UPDATE, or DELETE query and commits the transaction.
    Returns the newly inserted row ID (cur.lastrowid) or affected rows.
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        new_id = cur.lastrowid
    conn.commit()
    return new_id
