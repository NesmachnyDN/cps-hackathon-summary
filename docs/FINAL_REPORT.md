# Final Report — Hackathon MVP

## Implemented
The MVP answers situational questions over the organizer's official document package, shows verbatim evidence and source metadata, refuses unsupported answers, and creates downloadable structured summaries.

## Organizer data integration
The received package contains five separate job instructions in legacy `.doc` format. They are stored locally only, converted to DOCX, parsed, and indexed into `official_documents_inbox/official_corpus.json`. The package includes instructions for a brand/communications lead, recruiting lead, department head, leading specialist and chief specialist.

The system does not invent version relationships: no previous revisions were supplied, so change comparison is marked unavailable.

## Retrieval and AI
Retrieval is role/department-aware to avoid mixing highly similar HR instructions. Groq GPT-OSS 120B is used only after source retrieval, through the local VPN proxy, and is instructed to answer from retrieved clauses only. Unsupported questions return an explicit no-regulation response.

## Verification
46 unit tests pass. Legacy DOC extraction passes. Live Groq Q&A on the official corpus passes: ДИ-11-992 yields one year of experience for the leading specialist; ДИ-11-993 yields five years for the chief specialist. Unsupported unanchored questions are prevented from becoming answers through loose LLM query expansion.

Official documents and the generated local corpus are excluded from Git. Only integration code, tests, documentation and launch tooling are committed.
