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
from opc_browse.models import RelationshipRequest  # noqa: E402
from opc_browse.services.diagnostics import format_float, summarize_skipped  # noqa: E402
from opc_browse.services.relationship_analysis import run_relationship_analysis  # noqa: E402
from opc_browse.services.time_utils import parse_utc_datetime  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run relationship analysis from the CLI.")
    parser.add_argument("--machine-id", required=True, type=int)
    parser.add_argument("--target-tag-id", required=True, type=int)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--end-utc", required=True)
    parser.add_argument("--bucket-seconds", type=int, default=60)
    parser.add_argument(
        "--candidate-scope",
        choices=["same_machine", "same_folder", "selected_tags"],
        default="same_machine",
    )
    parser.add_argument("--candidate-tag-ids")
    parser.add_argument("--max-candidate-tags", type=int, default=300)
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--min-pair-count", type=int, default=30)
    parser.add_argument("--max-lag-seconds", type=int, default=1800)
    return parser


def parse_candidate_tag_ids(raw_value: str | None) -> list[int] | None:
    if not raw_value:
        return None
    return [int(part.strip()) for part in raw_value.split(",") if part.strip()]


def format_cell(value, width: int) -> str:
    text = "-" if value is None else str(value)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = RelationshipRequest(
            target={
                "machine_id": args.machine_id,
                "tag_id": args.target_tag_id,
            },
            start_utc=parse_utc_datetime(args.start_utc),
            end_utc=parse_utc_datetime(args.end_utc),
            bucket_seconds=args.bucket_seconds,
            max_points_per_series=2000,
            candidate_scope=args.candidate_scope,
            candidate_tag_ids=parse_candidate_tag_ids(args.candidate_tag_ids),
            max_candidate_tags=args.max_candidate_tags,
            max_results=args.max_results,
            min_pair_count=args.min_pair_count,
            max_lag_seconds=args.max_lag_seconds,
        )
    except Exception as exc:
        print(f"Invalid arguments: {exc}", file=sys.stderr)
        return 1

    try:
        with connection_context() as connection:
            response = run_relationship_analysis(connection, payload)
    except Exception as exc:
        print(f"Relationship analysis failed: {exc}", file=sys.stderr)
        return 1

    print("Target:")
    print(
        f"  machine_id={response['target']['machine_id']} "
        f"tag_id={response['target']['tag_id']} "
        f"display_name={response['target'].get('display_name')} "
        f"opc_path={response['target'].get('opc_path')}"
    )
    print(f"Actual bucket seconds: {response['window']['actual_bucket_seconds']}")
    print(f"Candidate count scanned: {response['analysis']['candidate_count_scanned']}")
    print(f"Candidate count analyzed: {response['analysis']['candidate_count_analyzed']}")
    print(f"Skipped by reason: {summarize_skipped(response['skipped'])}")
    if response["analysis"]["warnings"]:
        print("Warnings:")
        for warning in response["analysis"]["warnings"]:
            print(f"  - {warning}")
    print("")

    headers = [
        ("rank", 4),
        ("tag_id", 8),
        ("relationship_type", 18),
        ("score", 7),
        ("same_time_corr", 14),
        ("delta_corr", 10),
        ("best_lag_corr", 13),
        ("best_lag_seconds", 16),
        ("pair_count", 10),
        ("display_name", 24),
        ("opc_path", 50),
    ]
    print(" ".join(format_cell(name, width) for name, width in headers))
    print(" ".join("-" * width for _, width in headers))
    for index, row in enumerate(response["results"], start=1):
        print(
            " ".join(
                [
                    format_cell(index, 4),
                    format_cell(row["tag_id"], 8),
                    format_cell(row["relationship_type"], 18),
                    format_cell(format_float(row.get("score")), 7),
                    format_cell(format_float(row.get("same_time_corr")), 14),
                    format_cell(format_float(row.get("delta_corr")), 10),
                    format_cell(format_float(row.get("best_lag_corr")), 13),
                    format_cell(row.get("best_lag_seconds"), 16),
                    format_cell(row.get("pair_count"), 10),
                    format_cell(row.get("display_name"), 24),
                    format_cell(row.get("opc_path"), 50),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
