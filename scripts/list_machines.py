from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(PROJECT_ROOT / ".env")

from opc_browse.db import connection_context  # noqa: E402


def main() -> int:
    try:
        with connection_context() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM machines")
                total_count = int(cursor.fetchone()["count"])

                cursor.execute(
                    """
                    SELECT id, machine_name, endpoint_url, enabled
                    FROM machines
                    WHERE enabled = %s
                    ORDER BY machine_name ASC
                    """,
                    (1,),
                )
                enabled_rows = cursor.fetchall()
    except Exception as exc:
        print(f"Database connection failed: {exc}", file=sys.stderr)
        return 1

    print(f"Total machines: {total_count}")
    print(f"Enabled machines: {len(enabled_rows)}")
    print("")
    for row in enabled_rows:
        print(
            f"id={row['id']} "
            f"machine_name={row['machine_name']} "
            f"endpoint_url={row['endpoint_url']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
