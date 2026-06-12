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
from opc_browse.services.tag_profile_queries import fetch_machine_tag_profiles  # noqa: E402
from opc_browse.services.time_utils import (  # noqa: E402
    normalize_datetime_to_utc_naive_for_mysql,
    parse_utc_datetime,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Profile and score machine tags.")
    parser.add_argument("--machine-id", required=True, type=int)
    parser.add_argument("--start-utc")
    parser.add_argument("--end-utc")
    parser.add_argument("--search")
    parser.add_argument("--numeric-only", action="store_true")
    parser.add_argument("--grade")
    parser.add_argument("--semantic-type")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--order-by",
        default="score",
        choices=["score", "last_seen", "sample_count", "display_name"],
    )
    return parser


def format_cell(value, width: int) -> str:
    text = "-" if value is None else str(value)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def main() -> int:
    args = build_parser().parse_args()

    start_utc = (
        normalize_datetime_to_utc_naive_for_mysql(parse_utc_datetime(args.start_utc))
        if args.start_utc
        else None
    )
    end_utc = (
        normalize_datetime_to_utc_naive_for_mysql(parse_utc_datetime(args.end_utc))
        if args.end_utc
        else None
    )

    try:
        with connection_context() as connection:
            profiles = fetch_machine_tag_profiles(
                connection,
                machine_id=args.machine_id,
                start_utc=start_utc,
                end_utc=end_utc,
                search=args.search,
                numeric_only=args.numeric_only,
                limit=args.limit,
                order_by=args.order_by,
            )
    except Exception as exc:
        print(f"Tag profiling failed: {exc}", file=sys.stderr)
        return 1

    if args.grade:
        profiles = [
            item for item in profiles if item.get("usefulness_score", {}).get("grade") == args.grade
        ]
    if args.semantic_type:
        profiles = [
            item
            for item in profiles
            if item.get("usefulness_score", {}).get("semantic_type") == args.semantic_type
        ]

    grade_counts: dict[str, int] = {}
    semantic_counts: dict[str, int] = {}
    for item in profiles:
        usefulness = item.get("usefulness_score", {})
        grade = usefulness.get("grade", "unknown")
        semantic_type = usefulness.get("semantic_type", "unknown")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        semantic_counts[semantic_type] = semantic_counts.get(semantic_type, 0) + 1

    print(f"Machine ID: {args.machine_id}")
    print(f"Profiles returned: {len(profiles)}")
    print(f"By grade: {grade_counts}")
    print(f"By semantic_type: {semantic_counts}")
    print("")

    headers = [
        ("score", 7),
        ("grade", 8),
        ("semantic_type", 20),
        ("tag_id", 8),
        ("sample_count", 12),
        ("last_seen_utc", 20),
        ("display_name", 24),
        ("opc_path", 50),
    ]
    print(" ".join(format_cell(name, width) for name, width in headers))
    print(" ".join("-" * width for _, width in headers))
    for row in profiles[: args.limit]:
        usefulness = row.get("usefulness_score", {})
        print(
            " ".join(
                [
                    format_cell(usefulness.get("score"), 7),
                    format_cell(usefulness.get("grade"), 8),
                    format_cell(usefulness.get("semantic_type"), 20),
                    format_cell(row.get("tag_id"), 8),
                    format_cell(row.get("sample_count"), 12),
                    format_cell(row.get("last_seen_utc"), 20),
                    format_cell(row.get("display_name"), 24),
                    format_cell(row.get("opc_path"), 50),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
