# Next Execution Task

TASK_ID: DEMO-ANONYMIZATION-SETTINGS
MODE: REVIEW
BASE_BRANCH: main
TARGET_BRANCH: feature/anonymization-settings-ui
EXECUTION_PATH: DIRECT

## Result
A jury-facing anonymization settings surface is implemented on an isolated feature branch. It reuses the real local protection engine rather than a visual mock.

## Acceptance status
1. Separate «Защита данных» tab exposes per-category policy controls — PASS.
2. ORG/SYSTEM/PROJECT/PERSON/internal IDs can be pseudonymized or explicitly allowed; email/phone can be masked or explicitly allowed — PASS.
3. Credentials/private keys remain an immutable BLOCK boundary — PASS.
4. Local preview visibly compares original data, exact safe outbound text and reverse-restored text without invoking an external LLM — PASS.
5. Preview lists detected sensitive values and the action applied to each — PASS.
6. The selected policy is sent with protected normative questions and document summaries, so the settings affect the real user-facing external-call paths — PASS.
7. Existing protected-mode trace, normative Q&A, summaries and knowledge-base ingestion remain intact — PASS.

## Context pack
- AGENTS.md
- workflow/STATE.md
- workflow/NEXT_CODEX_TASK.md
- docs/QUALITY.md security/UI sections
- app.py protection-policy functions and normative LLM trace path
- static/index.html
- tests/test_app.py

## Required checks
- .venv/bin/python -m py_compile app.py
- .venv/bin/python -m unittest tests/test_app.py
- node --check on extracted inline UI script
- git diff --check
- isolated HTTP smoke for /api/analyze verifying custom policy, safe outbound and exact local restore

## Verification
- .venv/bin/python -m py_compile app.py — PASS.
- .venv/bin/python -m unittest tests/test_app.py — 55 tests PASS.
- node --check on extracted inline UI script — PASS.
- git diff --check — PASS.
- isolated HTTP smoke on port 8012 — PASS.
- preview smoke: custom ORG=ALLOW leaves organization visible, SYSTEM is pseudonymized, EMAIL is masked, reverse restore equals original — PASS.
- real normative-question trace with the same custom policy reflects the selected actions before provider dispatch — PASS (provider intentionally unavailable in isolated smoke).
- credential external-processing attempt returns HTTP 403 — PASS.
