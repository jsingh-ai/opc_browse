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
from opc_browse.services.sql_builders import build_tag_tree_filters  # noqa: E402
from opc_browse.services.tag_tree import build_tag_tree  # noqa: E402


def main():
    with connection_context() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db_name")
            db_name = cursor.fetchone()["db_name"]

            cursor.execute("SELECT COUNT(*) AS count FROM machines")
            machine_count = cursor.fetchone()["count"]

            cursor.execute(
                """
                SELECT id, machine_name, endpoint_url, enabled
                FROM machines
                WHERE enabled = %s
                ORDER BY machine_name ASC
                """,
                (1,),
            )
            enabled_machines = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) AS count FROM tag_samples")
            sample_row_count = cursor.fetchone()["count"]

            print(f"Database: {db_name}")
            print(f"Machine count: {machine_count}")
            print("Enabled machines:")
            for machine in enabled_machines:
                print(
                    f"  - id={machine['id']} name={machine['machine_name']} "
                    f"endpoint={machine['endpoint_url']}"
                )
            print(f"tag_samples rows: {sample_row_count}")

            if not enabled_machines:
                print("No enabled machines found; skipping tag tree sample.")
                return

            first_machine_id = enabled_machines[0]["id"]
            where_sql, params = build_tag_tree_filters(
                machine_id=first_machine_id,
                search=None,
                numeric_only=False,
                active_since_utc=None,
            )
            sql = f"""
                SELECT
                    t.id AS tag_id,
                    t.opc_path,
                    t.display_name,
                    t.browse_name,
                    t.data_type,
                    t.parent_branch,
                    MAX(ts.sampled_at_utc) AS last_seen_utc,
                    COUNT(ts.id) AS sample_count,
                    MAX(CASE WHEN ts.value_numeric IS NOT NULL THEN 1 ELSE 0 END) AS has_numeric_samples
                FROM tags t
                INNER JOIN tag_samples ts
                    ON ts.tag_id = t.id
                    AND ts.machine_id = %s
                {where_sql}
                GROUP BY
                    t.id,
                    t.opc_path,
                    t.display_name,
                    t.browse_name,
                    t.data_type,
                    t.parent_branch
                ORDER BY t.opc_path ASC
                LIMIT 25
            """
            cursor.execute(sql, [first_machine_id, *params])
            rows = cursor.fetchall()
            for row in rows:
                row["sample_count"] = int(row["sample_count"] or 0)
                row["is_numeric"] = bool(row.pop("has_numeric_samples"))

            tree = build_tag_tree(rows)
            print(f"Sample tag tree root children: {len(tree['children'])}")
            print(f"Sample tag tree root tags: {len(tree['tags'])}")


if __name__ == "__main__":
    main()
