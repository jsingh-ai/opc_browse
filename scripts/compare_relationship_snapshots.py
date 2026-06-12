from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from opc_browse.services.snapshots import compare_snapshots, load_snapshot  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two relationship snapshots.")
    parser.add_argument("snapshot_a")
    parser.add_argument("snapshot_b")
    parser.add_argument("--top", type=int, default=20)
    return parser


def format_cell(value, width: int) -> str:
    text = "-" if value is None else str(value)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def main() -> int:
    args = build_parser().parse_args()
    snapshot_a = load_snapshot(args.snapshot_a)
    snapshot_b = load_snapshot(args.snapshot_b)
    comparison = compare_snapshots(snapshot_a, snapshot_b, top=args.top)

    print(f"Snapshot A: {Path(args.snapshot_a)}")
    print(f"Snapshot B: {Path(args.snapshot_b)}")
    print(f"Target A: {comparison['snapshot_a']['target']}")
    print(f"Target B: {comparison['snapshot_b']['target']}")
    print(f"Result count A: {comparison['snapshot_a']['result_count']}")
    print(f"Result count B: {comparison['snapshot_b']['result_count']}")
    print(f"Tags added in B: {comparison['added_tag_ids']}")
    print(f"Tags removed from B: {comparison['removed_tag_ids']}")
    print("")

    print("Top score changes:")
    headers = [
        ("tag_id", 8),
        ("score_a", 8),
        ("score_b", 8),
        ("delta", 8),
        ("display_name", 24),
        ("opc_path", 50),
    ]
    print(" ".join(format_cell(name, width) for name, width in headers))
    print(" ".join("-" * width for _, width in headers))
    for row in comparison["score_changes"]:
        print(
            " ".join(
                [
                    format_cell(row.get("tag_id"), 8),
                    format_cell(f"{row.get('score_a', 0.0):.3f}", 8),
                    format_cell(f"{row.get('score_b', 0.0):.3f}", 8),
                    format_cell(f"{row.get('score_delta', 0.0):+.3f}", 8),
                    format_cell(row.get("display_name"), 24),
                    format_cell(row.get("opc_path"), 50),
                ]
            )
        )
    print("")

    print("Relationship type changes:")
    headers = [
        ("tag_id", 8),
        ("type_a", 18),
        ("type_b", 18),
        ("display_name", 24),
    ]
    print(" ".join(format_cell(name, width) for name, width in headers))
    print(" ".join("-" * width for _, width in headers))
    for row in comparison["relationship_type_changes"]:
        print(
            " ".join(
                [
                    format_cell(row.get("tag_id"), 8),
                    format_cell(row.get("relationship_type_a"), 18),
                    format_cell(row.get("relationship_type_b"), 18),
                    format_cell(row.get("display_name"), 24),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
