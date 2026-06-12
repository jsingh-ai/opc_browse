# opc_browse

`opc_browse` is a FastAPI app for exploring OPC/MySQL tag data, running relationship analysis, plotting time-series trends, and saving lightweight dashboards as JSON files.

Current path:

`DB access -> tag browsing -> relationship engine -> frontend explorer -> saved dashboards`

## What It Does

- Browse enabled machines from MySQL.
- Browse and search numeric OPC tags.
- Profile tags and inspect sample activity.
- Query chart-ready downsampled time series.
- Run exploratory relationship analysis on numeric tags.
- Save dashboard layouts and reusable panels to local JSON files.

## Stack

- FastAPI
- PyMySQL
- Pydantic
- NumPy
- plain HTML/CSS/JS
- Chart.js via CDN
- pytest

## Requirements

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Then fill in your MySQL settings in `.env`.

## Environment Variables

The app uses:

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=opcua_collector
MYSQL_CHARSET=utf8mb4
MYSQL_CONNECT_TIMEOUT_SECONDS=10
MYSQL_READ_TIMEOUT_SECONDS=60
MYSQL_WRITE_TIMEOUT_SECONDS=60
MYSQL_SSL_CA=
DASHBOARD_STORAGE_DIR=dashboards
```

## Start The App

```bash
uvicorn --app-dir src opc_browse.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Swagger docs:

```text
http://127.0.0.1:8000/docs
```

## Quick Workflow

1. Select a machine.
2. Load numeric tags.
3. Pick a target tag.
4. Set a UTC time range and bucket size.
5. Run relationship analysis.
6. Select related tags.
7. Plot target + related series.
8. Add chart or results to a dashboard.
9. Save the dashboard JSON.

## Real DB Validation Commands

List machines:

```bash
python scripts/list_machines.py
```

Inspect numeric tags for one machine:

```bash
python scripts/inspect_machine_tags.py --machine-id 1 --numeric-only --limit 50
```

Run relationship analysis from the terminal:

```bash
python scripts/run_relationship_analysis.py --machine-id 1 --target-tag-id 123 --start-utc 2026-06-11T00:00:00Z --end-utc 2026-06-12T00:00:00Z
```

Save a relationship snapshot:

```bash
python scripts/save_relationship_snapshot.py --machine-id 1 --target-tag-id 123 --start-utc 2026-06-11T00:00:00Z --end-utc 2026-06-12T00:00:00Z
```

Compare two saved snapshots:

```bash
python scripts/compare_relationship_snapshots.py snapshots/a.json snapshots/b.json
```

Run the basic DB smoke test:

```bash
python scripts/inspect_db.py
```

## Data Explorer

The browser UI is a plain JS MVP served by FastAPI static files.

Main workflow:

1. Open `/`
2. Select a machine
3. Search or filter tags
4. Pick one numeric target tag
5. Run relationships
6. Select related tags
7. Plot trends

Phase 6 usability features:

- workspace state persists in browser `localStorage`
- tags are grouped by OPC parent folder
- relationship results can be filtered and sorted
- chart supports raw and normalized modes

## Saved Dashboards

Dashboards are stored as local JSON files under:

```text
DASHBOARD_STORAGE_DIR=dashboards
```

Dashboard workflow:

1. Explore data in the `Explore` tab.
2. Run relationship analysis.
3. Plot target + selected related tags.
4. Add the current chart as a panel.
5. Add relationship results as a panel.
6. Switch to the `Dashboards` tab.
7. Resize and move panels.
8. Refresh panels individually or all at once.
9. Save the dashboard.
10. Reload it later from the dashboard selector.

Phase 8 layout actions:

- 12-column saved panel grid
- move left/right/up/down buttons
- width controls: `4`, `6`, `8`, `12`
- height controls: `3`, `4`, `6`, `8`
- per-panel refresh
- refresh all panels sequentially
- unsaved changes indicator before save

Current limitations:

- local JSON persistence only
- no drag/drop layout yet
- no authentication
- no MySQL-backed dashboard storage

## Relationship Analysis Notes

Relationship types:

- `moves_together`
- `possible_driver`
- `possible_effect`
- `changes_together`

This analysis is exploratory. Correlation does not prove causation.

Good first target tags:

- numeric tags that change often
- tags with recent `last_seen_utc`
- tags with higher `sample_count`

Avoid at first:

- constant parameters
- text/state/alarm tags

## Tests

Run the full test suite:

```bash
pytest
```

Current tests do not require a live MySQL database.

## GitHub Push Checklist

Before pushing:

1. Confirm `.env` is not tracked.
2. Confirm generated `dashboards/` and `snapshots/` files are not tracked.
3. Run:

```bash
pytest
```

4. Start the app once:

```bash
uvicorn --app-dir src opc_browse.main:app --reload
```

5. Review `README.md`, `.env.example`, and `requirements.txt`.

## Project Status

Implemented phases:

- Phase 1: MySQL access, machine browsing, tag trees, tag profile, time series
- Phase 2: relationship analysis engine
- Phase 3: diagnostics and safer query controls
- Phase 4: analysis snapshots and mocked API tests
- Phase 5: frontend Data Explorer MVP
- Phase 6: workspace persistence and explorer usability improvements
- Phase 7: saved dashboards backed by JSON files
- Phase 8: dashboard layout builder with panel lifecycle controls

Next likely step:

- richer dashboard interactions such as drag/drop layout and smarter panel packing
