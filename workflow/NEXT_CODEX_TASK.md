# Next Execution Task

TASK_ID: DEMO-PROTECTED-KB-UPLOAD
MODE: REVIEW
BASE_BRANCH: main
TARGET_BRANCH: feature/protected-demo-kb-upload
EXECUTION_PATH: DIRECT

## Result
Implementation is complete on the isolated feature branch. Do not merge into main while the current main-branch review is in progress.

## Acceptance status
1. Protected-mode switch enabled by default — PASS.
2. Policy transformation before every external LLM call and local reverse transformation — PASS.
3. Jury trace shows provider/route, original prompt, policy mapping, transformed outbound prompt, exact provider JSON, raw provider response and restored response; API key is excluded — PASS.
4. Seven prepared demo questions cover role disambiguation, same-role/different-department retrieval, hierarchy, protected-data handling and a not-regulated fallback — PASS.
5. UI ingestion persists a normative file under ignored official_documents_inbox/uploaded, stores its corpus record separately and makes it queryable without restart — PASS.
6. Existing one-off summary/upload behavior remains available — PASS.

## Verification
- .venv/bin/python -m unittest tests/test_app.py — 51 tests PASS.
- .venv/bin/python -m py_compile app.py — PASS.
- node --check on extracted UI script — PASS.
- git diff --check — PASS.
- HTTP smoke on isolated port 8011 — PASS.
- protected outbound smoke: ORG/SYSTEM/PROJECT/email absent from provider JSON and replaced by policy tokens — PASS.
- all seven demo questions checked against the official 5-document corpus; six return grounded evidence and one intentionally returns not-regulated — PASS.
