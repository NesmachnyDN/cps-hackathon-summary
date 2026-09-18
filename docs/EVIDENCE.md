# Acceptance Evidence

Date: 2026-09-18

## Automated
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — PASS, 41 tests.
- `.venv/bin/python -m py_compile app.py` — PASS.

## Runtime — deterministic fallback
- GET `/` — HTTP 200; both primary modes and «Скачать выжимку» present.
- Situational conflict query — 3 evidence fragments, conflict detected, winner = synthetic information-security standard.
- No-answer query — zero evidence; exact honest HR fallback returned.
- Summary of current remote-work document — previous version found; added/removed changes returned.
- DOCX upload through `/api/file` — PASS, extracted text returned.

## Runtime — real LLM
OpenAI-compatible local Ollama endpoint `llama3.1:8b` was used as a live CPS-style provider.
- direct OpenAI-compatible call — PASS;
- integrated `/api/normative/question` — PASS;
- response mode = `llm_grounded`;
- conflict = true;
- explicit winner = information-security standard;
- answer generated from provided evidence and priority context.

The current shell had no `GROQ_API_KEY`; public Groq was therefore not claimed as tested. Default no-key demo remains fully operable through the explicit offline fallback.

## Docker clean runtime
- `docker build -t cps-hackathon-summary:demo .` — PASS.
- container published on host port 18082 — GET `/` HTTP 200.
- UI marker present — PASS.
- no-answer API inside container returns HR-partner fallback — PASS.
