from __future__ import annotations

import argparse
import json
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
from opc_browse.services.relationship_analysis import run_relationship_analysis  # noqa: E402
from opc_browse.services.snapshots import (  # noqa: E402
    default_snapshot_path,
    relationship_response_to_jsonable,
)
from opc_browse.services.time_utils import parse_utc_datetime  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Save a relationship analysis snapshot.")
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
    parser.add_argument("--output")
    return parser


def parse_candidate_tag_ids(raw_value: str | None) -> list[int] | None:
    if not raw_value:
        return None
    return [int(part.strip()) for part in raw_value.split(",") if part.strip()]


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = RelationshipRequest(
            target={"machine_id": args.machine_id, "tag_id": args.target_tag_id},
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

    output_path = Path(args.output) if args.output else default_snapshot_path(
        args.machine_id,
        args.target_tag_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jsonable_payload = relationship_response_to_jsonable(response)
    output_path.write_text(json.dumps(jsonable_payload, indent=2), encoding="utf-8")

    print(f"Saved snapshot: {output_path}")
    print(
        f"Target: {response['target'].get('label')} "
        f"({response['target'].get('opc_path')})"
    )
    print(f"Results: {len(response.get('results', []))}")
    print(f"Skipped: {response.get('analysis', {}).get('skipped_count', 0)}")
    print(f"Warnings: {response.get('analysis', {}).get('warnings', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
