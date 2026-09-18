# Demo / Submission Runbook

## Scenario 1 — grounded question over organizer documents
1. Open the app on `http://127.0.0.1:8001`.
2. Stay on «Спросить по ситуации».
3. Click «Показать пример по документам».
4. Show the answer for the leading specialist role.
5. Show exact source ДИ-11-992, revision period and verbatim clause.

Then ask: «Какой стаж работы требуется для главного специалиста отдела подбора и адаптации персонала?»
Expected source: ДИ-11-993. This demonstrates that similar instructions are not mixed.

## Scenario 2 — structured summary
1. Open «Выжимка документа».
2. Select any instruction from the organizer package or upload its original `.doc`.
3. Click «Сделать выжимку».
4. Show topic, audience, requirements, prohibitions and rights.
5. Show that no previous revision is claimed when none was supplied.
6. Download the summary.

## Safety / fallback
A question unsupported by the package must be answered as not regulated rather than from model memory. If Groq is unavailable, the grounded deterministic path remains available and is labeled explicitly.
