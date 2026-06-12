from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "opcua_collector"
    mysql_charset: str = "utf8mb4"
    mysql_connect_timeout_seconds: int = 10
    mysql_read_timeout_seconds: int = 60
    mysql_write_timeout_seconds: int = 60
    mysql_ssl_ca: str | None = None
    dashboard_storage_dir: str = "dashboards"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        mysql_database=os.getenv("MYSQL_DATABASE", "opcua_collector"),
        mysql_charset=os.getenv("MYSQL_CHARSET", "utf8mb4"),
        mysql_connect_timeout_seconds=int(
            os.getenv("MYSQL_CONNECT_TIMEOUT_SECONDS", "10")
        ),
        mysql_read_timeout_seconds=int(os.getenv("MYSQL_READ_TIMEOUT_SECONDS", "60")),
        mysql_write_timeout_seconds=int(os.getenv("MYSQL_WRITE_TIMEOUT_SECONDS", "60")),
        mysql_ssl_ca=os.getenv("MYSQL_SSL_CA") or None,
        dashboard_storage_dir=os.getenv("DASHBOARD_STORAGE_DIR", "dashboards"),
    )
