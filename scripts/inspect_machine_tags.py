from __future__ import annotations

import argparse
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
from opc_browse.services.time_utils import (  # noqa: E402
    normalize_datetime_to_utc_naive_for_mysql,
    parse_utc_datetime,
)


NUMERIC_TYPE_TOKENS = (
    "float",
    "double",
    "decimal",
    "int",
    "integer",
    "short",
    "long",
    "byte",
    "sbyte",
    "uint",
    "ulong",
    "ushort",
    "number",
    "real",
)


def is_numeric_type(data_type: str | None) -> bool:
    normalized = (data_type or "").strip().lower()
    return any(token in normalized for token in NUMERIC_TYPE_TOKENS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect machine tags from MySQL.")
    parser.add_argument("--machine-id", required=True, type=int)
    parser.add_argument("--search")
    parser.add_argument("--numeric-only", action="store_true")
    parser.add_argument("--active-since-utc")
    parser.add_argument("--limit", type=int, default=100)
    return parser


def format_cell(value, width: int) -> str:
    text = "-" if value is None else str(value)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def main() -> int:
    args = build_parser().parse_args()
    active_since_utc = (
        normalize_datetime_to_utc_naive_for_mysql(parse_utc_datetime(args.active_since_utc))
        if args.active_since_utc
        else None
    )

    where_sql, params = build_tag_tree_filters(
        machine_id=args.machine_id,
        search=args.search,
        numeric_only=args.numeric_only,
        active_since_utc=active_since_utc,
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
            MIN(ts.sampled_at_utc) AS first_seen_utc,
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
        ORDER BY t.opc_path ASC, t.display_name ASC, t.browse_name ASC
    """

    try:
        with connection_context() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, machine_name, endpoint_url
                    FROM machines
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (args.machine_id,),
                )
                machine = cursor.fetchone()
                if not machine:
                    print(f"Machine {args.machine_id} not found.", file=sys.stderr)
                    return 1

                cursor.execute(sql, [args.machine_id, *params])
                rows = cursor.fetchall()
    except Exception as exc:
        print(f"Database query failed: {exc}", file=sys.stderr)
        return 1

    for row in rows:
        row["sample_count"] = int(row["sample_count"] or 0)
        row["is_numeric"] = bool(row["has_numeric_samples"]) or is_numeric_type(
            row.get("data_type")
        )

    total_matching = len(rows)
    numeric_looking = sum(1 for row in rows if row["is_numeric"])
    tags_with_samples = sum(1 for row in rows if row["sample_count"] > 0)
    earliest_seen = min((row["first_seen_utc"] for row in rows if row["first_seen_utc"]), default=None)
    latest_seen = max((row["last_seen_utc"] for row in rows if row["last_seen_utc"]), default=None)

    print(f"Machine: {machine['id']} {machine['machine_name']}")
    print(f"Endpoint: {machine['endpoint_url']}")
    print(f"Total matching tags: {total_matching}")
    print(f"Numeric-looking tags: {numeric_looking}")
    print(f"Tags with samples: {tags_with_samples}")
    print(f"Earliest sample in set: {earliest_seen}")
    print(f"Latest sample in set: {latest_seen}")
    print("")

    headers = [
        ("tag_id", 8),
        ("data_type", 14),
        ("sample_count", 12),
        ("last_seen_utc", 20),
        ("parent_branch", 18),
        ("opc_path", 60),
    ]
    print(" ".join(format_cell(name, width) for name, width in headers))
    print(" ".join("-" * width for _, width in headers))
    for row in rows[: args.limit]:
        print(
            " ".join(
                [
                    format_cell(row["tag_id"], 8),
                    format_cell(row.get("data_type"), 14),
                    format_cell(row["sample_count"], 12),
                    format_cell(row.get("last_seen_utc"), 20),
                    format_cell(row.get("parent_branch"), 18),
                    format_cell(row.get("opc_path"), 60),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
