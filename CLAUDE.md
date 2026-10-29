# HR backend (Flask + SQL Server)

**Before touching the server, deployment, clients or security, read [OPERATIONS.md](OPERATIONS.md)** —
architecture, server layout, deploy flow, the `hr` command, rules, change log and the open task list.

Key rules (details in OPERATIONS.md §7):
- Production client **jana** must not be disrupted: propose server changes with their impact first and wait for approval.
- Never hand-edit git-tracked files on the server; change them here, push to `production`, then deploy
  (`hr-dev/deploy/deploy-backend-saas.sh`, `hr-dev/deploy/release-frontend-saas.sh`).
- `app/config.py` is per environment (gitignored); new settings go into `app/config.example.py`.
- New DB columns: add an idempotent "add if missing" step in `create_app()` (`app/__init__.py`) — `db.create_all()` does not add columns.
- Never print secrets; take a verified backup before any destructive database operation.
- When a task in OPERATIONS.md §10 is finished, mark it `[x]` with the date and add a line to the change log (§9).
