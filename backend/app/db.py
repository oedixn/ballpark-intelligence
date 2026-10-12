"""Shared PostgreSQL connection configuration for the backend and ML modules."""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import wraps
from threading import local
from typing import Callable, Iterator, TypeVar

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


_connection_scope = local()
_T = TypeVar("_T")


def get_connection() -> connection:
    """Create a PostgreSQL connection from DATABASE_URL or DB_* variables."""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = psycopg2.connect(**DB_CONFIG)

    # API 요청 범위가 활성화된 경우 연결을 등록합니다. 정상 경로에서 직접
    # 닫더라도 안전하며, 예외 경로에서 남은 연결은 요청 종료 시 정리됩니다.
    active_connections = getattr(_connection_scope, "connections", None)
    if active_connections is not None:
        active_connections.append(conn)
    return conn


@contextmanager
def connection_cleanup_scope() -> Iterator[None]:
    """Close every PostgreSQL connection opened during one synchronous request."""
    previous_connections = getattr(_connection_scope, "connections", None)
    current_connections: list[connection] = []
    _connection_scope.connections = current_connections
    try:
        yield
    finally:
        for conn in reversed(current_connections):
            try:
                if not conn.closed:
                    conn.close()
            except Exception:
                # 연결 정리 실패가 원래 API 응답을 덮어쓰지 않게 합니다.
                pass

        if previous_connections is None:
            try:
                del _connection_scope.connections
            except AttributeError:
                pass
        else:
            _connection_scope.connections = previous_connections


def with_connection_cleanup(func: Callable[..., _T]) -> Callable[..., _T]:
    """Ensure DB connections opened by a FastAPI sync endpoint never leak."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with connection_cleanup_scope():
            return func(*args, **kwargs)

    return wrapper
