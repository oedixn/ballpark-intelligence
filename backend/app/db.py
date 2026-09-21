"""Shared PostgreSQL connection configuration for the backend and ML modules."""

from __future__ import annotations

import os

import psycopg2
from psycopg2.extensions import connection


DATABASE_URL = os.getenv("DATABASE_URL")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "ballpark"),
    "user": os.getenv("DB_USER", "ballpark"),
    "password": os.getenv("DB_PASSWORD", "ballpark1234"),
}


def get_connection() -> connection:
    """Create a PostgreSQL connection from DATABASE_URL or DB_* variables."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(**DB_CONFIG)
