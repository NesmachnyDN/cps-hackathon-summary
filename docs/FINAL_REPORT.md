# Final Report — Hackathon MVP

## What the task requires
Two linked capabilities: priority situational Q&A over current normative documents with evidence/conflict handling, plus a structured document summary with version comparison and downloadable result.

## What is implemented
- configurable normative corpus with current-version selection;
- deterministic evidence retrieval and adaptive AI query expansion when lexical evidence is weak;
- grounded LLM explanation over retrieved evidence;
- explicit no-answer behavior;
- conflict detection and priority selection only from explicit numeric metadata;
- TXT/MD/CSV/JSON/DOCX/PDF intake;
- structured summary and previous-version diff;
- mandatory summary download;
- external editable `prompts.json`;
- secondary privacy policy layer reused from Secure AI Gateway;
- explicit offline fallback;
- Dockerfile and clean-run README;
- synthetic demo corpus and two stable demo scenarios.

## Reused work
From the previously validated Secure AI Gateway: local Python server, browser UI delivery pattern, file intake, pseudonymization/masking/block policy, OpenAI-compatible provider boundary, CPS/Groq runtime profiles and related regression tests.

## Deliberately out of scope
Production RBAC/SSO, vector database, microservices, OCR, graph visualization and tone-map bonus.

## External dependency still missing
The organizers' official 10–15 document dataset was not included with the assignment file available during this implementation. The repository therefore ships an explicitly synthetic corpus. Replace it through `NORMATIVE_CORPUS_PATH` when the official corpus arrives.

## Verification
41 unit tests PASS; compile PASS; runtime happy paths PASS; DOCX upload PASS; real OpenAI-compatible LLM call PASS through local Ollama; public Groq not tested because no key was present in the runtime shell.
