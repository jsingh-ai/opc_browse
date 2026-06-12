# opc_browse

Backend API for browsing OPC/MySQL tag data, returning chart-ready time-series data, suggesting likely tag relationships, and validating behavior against a real MySQL database for Pinch dashboard exploration.

Phase 1 focuses on:

- verifying MySQL connectivity
- browsing enabled machines
- building nested OPC path trees
- profiling tags
- querying downsampled numeric trends

Phase 2 adds:

- smart relationship scanning for numeric target tags
- same-time correlation
- lagged correlation for possible lead/follow behavior
- change correlation based on first differences

Phase 3 adds:

- CLI diagnostics for real database validation
- safer relationship scan guardrails and warnings
- richer analysis diagnostics for why tags were skipped

Phase 5 adds:

- a minimal frontend Data Explorer MVP served by FastAPI
- machine and tag browsing from the browser
- relationship analysis and trend plotting in one page

Phase 6 adds:

- workspace state persisted in browser localStorage
- grouped tag browsing by opc_path parent folder
- relationship result filtering and sorting
- raw and normalized chart modes for easier comparison

Phase 7 adds:

- a simple saved dashboard builder backed by local JSON files
- reusable timeseries, relationship-results, and tag-profile panels
- save, reload, and delete dashboard definitions through the API

This project is still backend only. It does not include a frontend dashboard, deep learning, or the future saved-dashboard features yet.

## Setup

```bash
pip install -r requirements.txt
```

Create a local `.env` from the example values in `.env.example`.

Dashboard storage defaults to:

```text
DASHBOARD_STORAGE_DIR=dashboards
```

## Run API

```bash
uvicorn --app-dir src opc_browse.main:app --reload
```

## Phase 5 Frontend MVP

Run API:

```bash
uvicorn --app-dir src opc_browse.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Workflow:

1. Select machine.
2. Pick numeric target tag.
3. Run relationship analysis.
4. Select related tags.
5. Plot trends.

This is the MVP explorer only. It is not the final drag/drop dashboard builder yet.

Phase 6 notes:

- Workspace state persists in browser localStorage under `opc_browse_workspace_v1`.
- The tag browser is grouped by `opc_path` parent folder with quick filters and badges.
- Relationship results can be filtered by type and sorted client-side.
- The chart supports raw and normalized comparison modes.
- This is still not the final saved dashboard builder.

## Phase 7 Saved Dashboard Builder

Dashboards are saved as local JSON files in `DASHBOARD_STORAGE_DIR`.

Suggested workflow:

1. Explore data.
2. Run relationship analysis.
3. Plot target + selected related tags.
4. Add chart/results to dashboard.
5. Save dashboard.
6. Reload dashboard later.

Current limitations:

- local JSON persistence only
- no drag/drop positioning yet
- no user authentication yet
- no database-backed dashboard storage yet

## Run Tests

```bash
.venv/bin/python -m pytest
```

## Manual DB Smoke Test

```bash
.venv/bin/python scripts/inspect_db.py
```

## Real DB Validation Workflow

1. Copy `.env.example` to `.env` and fill in `MYSQL_*` values.
2. Run:

```bash
python scripts/list_machines.py
```

3. Pick a machine id, then run:

```bash
python scripts/inspect_machine_tags.py --machine-id 1 --numeric-only --limit 50
```

4. Pick a numeric tag id, then run:

```bash
python scripts/run_relationship_analysis.py --machine-id 1 --target-tag-id 123 --start-utc 2026-06-11T00:00:00Z --end-utc 2026-06-12T00:00:00Z
```

5. Save a snapshot:

```bash
python scripts/save_relationship_snapshot.py --machine-id 1 --target-tag-id 123 --start-utc 2026-06-11T00:00:00Z --end-utc 2026-06-12T00:00:00Z
```

6. Compare snapshots after changes:

```bash
python scripts/compare_relationship_snapshots.py snapshots/a.json snapshots/b.json
```

7. Start API:

```bash
uvicorn --app-dir src opc_browse.main:app --reload
```

8. Test Swagger docs:

```text
http://127.0.0.1:8000/docs
```

How to pick the first target tag:

- Start with a numeric tag that changes often.
- Avoid constant parameters at first.
- Avoid text/state/alarm tags for the Phase 2 relationship endpoint.
- Use `inspect_machine_tags.py` to find candidates with high `sample_count` and recent `last_seen_utc`.

Suggested workflow:

1. list machines
2. inspect tags
3. run relationship analysis in terminal
4. save snapshot
5. compare snapshots after changes
6. only then build frontend widgets around stable payloads

## Phase 2 Relationship Analysis

Endpoint:

```text
POST /api/analysis/relationships
```

Support endpoint:

```text
GET /api/analysis/methods
```

Purpose:

1. Browse the tag tree and pick a numeric target tag.
2. Run the relationships endpoint for a time window.
3. Review the top suggested tags.
4. Plot the target against the top suggestions.

Relationship types:

- `moves_together`: strongest signal is same-time correlation
- `possible_driver`: candidate appears to lead the target
- `possible_effect`: candidate appears to follow the target
- `changes_together`: first-difference correlation is strongest

The Phase 2 analysis is exploratory. Correlation does not prove causation.

## Saving And Comparing Relationship Snapshots

Commands:

```bash
python scripts/save_relationship_snapshot.py --machine-id 1 --target-tag-id 123 --start-utc 2026-06-11T00:00:00Z --end-utc 2026-06-12T00:00:00Z
python scripts/compare_relationship_snapshots.py snapshots/a.json snapshots/b.json
```

Why snapshots are useful:

- validate real DB behavior
- compare algorithm changes
- attach examples before frontend development
- debug skipped tags and warnings

## Planned Next Phases

- Phase 8 drag/drop dashboard builder
- Phase 9 database-backed dashboards and ML feature scoring
# opc_browse
