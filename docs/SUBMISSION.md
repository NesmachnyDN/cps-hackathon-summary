# Demo / Submission Runbook

## Scenario 1 — situational conflict
1. Open the app.
2. Stay on «Спросить по ситуации».
3. Click «Показать пример конфликта».
4. Show:
   - plain-language answer;
   - conflict banner;
   - winning higher-priority source;
   - exact quotes, versions and effective dates.

Expected business point: the assistant does not merely summarize — it finds the applicable norm and makes contradictions visible.

## Scenario 2 — new document + changes
1. Open «Выжимка документа».
2. Upload `demo/remote-work-v2.txt`.
3. Click «Сделать выжимку».
4. Show topic/audience/requirements/prohibitions/rights.
5. Show added/removed items vs version 1.0.
6. Click «Скачать выжимку».

## Stable fallback
If the configured LLM is unavailable, keep the demo running. The UI explicitly labels the deterministic mode and continues to show source evidence, conflict, version and diff. Do not present fallback output as an LLM response.

## 5-minute pitch emphasis
- Employee asks in their own words; the assistant maps the situation back to the governing norm.
- Evidence + version + conflict handling reduce hallucination risk and make the answer verifiable.
- HR gains fewer repetitive consultations; security/privacy controls remain behind the business flow rather than dominating it.
