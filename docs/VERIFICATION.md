# Verification

Date: 2026-11-19 (America/New_York).

## Executed locally

- Python 3.12 environment: `pip install -e '.[dev]'`; locked installed dependencies in `requirements.lock`.
- `ruff check backend tests scripts` and formatter: passed after fixing reported import issues.
- `pytest -q`: **205 passed, 0 failed** (200 fixture-driven cases and 5 API/service integration tests).
- `python scripts/evaluate.py`: **200 passed, 0 failed**, category rates and timestamps in `evaluation.json` / `EVALUATION.md`.
- `npm run build`: TypeScript check and Vite production build passed.
- `npm test`: **3 component tests passed, 0 failed**.
- `pip-audit -r requirements.lock`: no known vulnerabilities found.
- `npm audit --audit-level=high`: zero vulnerabilities after upgrading Vite/Vitest and the React Vite plugin.

## Corrections found by verification

The first full fixture run found that the natural-language planner treated the word “deactivation” as an account name. Corrected parsing; rerun passed all cases. An initial npm install hit an existing root-owned user cache; a separate writable cache resolved installation. The initial test-tool dependency versions had published advisories and were upgraded before publication.

## Docker and end-to-end checks

- `docker compose up -d --build --wait`: backend and frontend images built; all five services healthy with PostgreSQL 16.
- `python scripts/demo.py`: passed actual HTTP approval workflow, unauthorized approval rejection, REST execution and audit checks.
- `npm run e2e`: **1 browser test passed** (Chromium, requester sign-in/submission, independent approver sign-in, approval/resume, completed tool audit). Screenshot saved as `docs/dashboard.png`.
- GitHub CI: pending first push; local equivalents executed as listed above.

## Scope

No paid credentials are required or used. No hosted LLM or cloud deployment is claimed. SQLite integration tests exercise graph restarts and REST handlers through an HTTP transport; separate Docker/browser checks validate real network calls and PostgreSQL. See ARCHITECTURE.md for single-worker and cross-database transaction limitations. Python static type checking is not configured; frontend TypeScript checking is configured and executed.
