from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pymysql
from pymysql.cursors import DictCursor

from opc_browse.config import get_settings


def get_connection():
    settings = get_settings()
    connect_kwargs = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "database": settings.mysql_database,
        "charset": settings.mysql_charset,
        "connect_timeout": settings.mysql_connect_timeout_seconds,
        "read_timeout": settings.mysql_read_timeout_seconds,
        "write_timeout": settings.mysql_write_timeout_seconds,
        "cursorclass": DictCursor,
        "autocommit": True,
    }
    if settings.mysql_ssl_ca:
        connect_kwargs["ssl"] = {"ca": settings.mysql_ssl_ca}

    connection = pymysql.connect(**connect_kwargs)
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")
    return connection


@contextmanager
def connection_context() -> Iterator:
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def get_db_connection():
    with connection_context() as connection:
        yield connection
