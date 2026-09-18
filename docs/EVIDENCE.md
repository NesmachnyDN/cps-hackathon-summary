# Acceptance Evidence

Date: 2026-09-18

## Automated
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — PASS, 46 tests.
- `.venv/bin/python -m py_compile app.py scripts/prepare_official_documents.py` — PASS.
- `git diff --check` — PASS.

## Organizer package
- 5 legacy Word `.doc` files received and copied to local-only `official_documents_inbox/original/`.
- All 5 converted locally to DOCX and extracted successfully.
- Generated `official_documents_inbox/official_corpus.json` with 5 distinct current job instructions.
- Documents are treated as separate instructions, not fabricated versions of one document.
- No previous revisions were supplied, so version-diff is explicitly unavailable.

## Runtime — official corpus
- Groq proxy preflight — PASS through `127.0.0.1:10809`.
- Leading specialist query — `llm_grounded`, source ДИ-11-992, required experience = 1 year.
- Chief specialist query — `llm_grounded`, source ДИ-11-993, required experience = 5 years.
- Weekend business-trip payment query — no grounded evidence; honest HR fallback.
- Original organizer `.doc` upload — PASS.
- Original ДИ-11-992 `.doc` upload auto-binds to the official corpus — PASS.
- Structured summary for ДИ-11-992 — correct source/topic/audience, 5 requirements, 5 rights, 1 prohibition; previous version explicitly unavailable.

Final code-level smoke after the safety hardening passes: role-specific retrieval selects ДИ-11-992/993/948 correctly, unsupported weekend-trip payment returns `not_regulated`, and structured summary remains source-bound. A single launcher restart is required to load the last backend hardening into the live Groq process because the API key exists only in that process environment.
