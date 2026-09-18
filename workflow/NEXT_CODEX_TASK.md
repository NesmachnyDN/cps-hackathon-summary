# Next Execution Task

TASK_ID: DEMO-DOCUMENT-TONE-MAP
MODE: REVIEW
BASE_BRANCH: main
TARGET_BRANCH: feature/document-tone-map
EXECUTION_PATH: DIRECT

## Result
A separate HR-facing document tone/clarity map is implemented without changing the main Q&A, summary, ingestion or anonymization flows.

## Acceptance status
1. Separate «Карта тона документа» tab — PASS.
2. User can select an existing knowledge-base document — PASS.
3. User can upload a supported file for one-off analysis — PASS.
4. Analysis is local and does not invoke an external LLM — PASS.
5. Per-fragment complexity and communication-tone scores are calculated — PASS.
6. Clickable heat-map visualization highlights difficult/directive areas — PASS.
7. HR receives reasons and concrete editing guidance for each fragment — PASS.
8. Problem-only filtering and document-level recommendations are available — PASS.
9. Existing application behavior remains intact — PASS.

## Context pack
- AGENTS.md
- workflow/STATE.md
- workflow/NEXT_CODEX_TASK.md
- app.py HTTP routing
- tone_map.py
- static/index.html
- tests/test_app.py

## Required checks
- .venv/bin/python -m py_compile app.py tone_map.py
- .venv/bin/python -m unittest tests/test_app.py
- node --check on extracted inline UI script
- git diff --check
- HTTP smoke for /api/normative/tone-map
- real organizer-corpus smoke across all 5 documents

## Verification
- Python compile — PASS.
- unittest — 59 tests PASS.
- inline UI script node --check — PASS.
- git diff --check — PASS.
- isolated HTTP smoke on port 8015 — PASS.
- organizer corpus: all 5 documents analyzed locally — PASS.
- real corpus produces non-trivial heat-map distribution with high-complexity fragments reaching 77–84/100 — PASS.
