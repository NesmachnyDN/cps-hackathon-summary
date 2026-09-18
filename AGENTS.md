# AGENTS.md

Repository-wide rules for Codex and coding agents.

## 1. Scope

Implement only the active contract in `workflow/NEXT_CODEX_TASK.md`; optimize for a demonstrable Must result, small diffs and fast verification. `PARTICIPATION_MODE`, sprint profile, integration strategy and clock gates in `workflow/STATE.md` are binding.

Do not stop after analysis unless a genuine blocker exists.

## 2. Context budget — task scoped by default

For every ordinary IMPLEMENT/FIX/CONTINUE run, preload only the execution core:

1. `AGENTS.md`
2. `workflow/STATE.md`
3. `workflow/NEXT_CODEX_TASK.md`

Then read only files/sections explicitly listed under the task's `## Context pack`, plus the smallest source/test files needed to execute the change.

Do **not** preload `README.md`, `docs/SPEC.md`, `docs/PLAN.md`, `docs/QUALITY.md`, `docs/DELIVERY.md`, `docs/AI.md`, `docs/EVIDENCE.md` or `docs/SUBMISSION.md` merely because they exist. The active task must carry the task-relevant acceptance criteria and resolved contract snapshot needed for normal execution.

A context-pack reference may name a whole file or a heading/range. Prefer the narrowest useful slice. Do not recursively open adjacent process documents unless the task requires them.

If a concrete execution-critical fact is missing, read the **single** canonical document that owns that fact, note the context-pack gap in the result, and continue when safe. Do not sweep the whole `docs/` directory.

FINALIZE is intentionally broader: read the finalization context named by the task and, at minimum, `docs/QUALITY.md`, `docs/EVIDENCE.md` and `docs/SUBMISSION.md`.

## 3. Execution mode and ownership

`workflow/STATE.md` records `EXECUTION_MODE`. Repository topology still owns the official source of record and remotes; execution mode only says where ChatGPT runs the orchestration loop.

### LOCAL_ORCHESTRATED — preferred when available

ChatGPT has authorized local filesystem/terminal access to the project checkout and is the orchestration/acceptance authority. It owns rules/intake, repository discovery, architecture/decomposition, task shaping, `STATE`/`NEXT`, documentation/process changes, small deterministic code changes, broad/repeated validation, branch/Git/CI integration, review, final acceptance, commit/push, report and presentation. Never persist the absolute workstation checkout path.

For each bounded task, use `EXECUTION_PATH` from NEXT:

- `DIRECT` — the default for orchestration/docs-only work, repository discovery, architecture/planning, narrow deterministic fixes, known small edits, integration/review/Git/CI work, broad/repeated validation, or any case where delegation overhead would dominate;
- `CODEX_DELEGATED` — only the minimum implementation-heavy slice where substantive multi-file code generation, test-heavy/repetitive implementation or focused code exploration materially improves throughput or quality;
- the presence of code alone is not a reason to delegate; split an oversized/ambiguous task before delegation.

Before delegation, ChatGPT resolves repository state, architecture, invariants and scope, then hands Codex only the exact goal, allowed/touched areas, acceptance criteria and targeted checks plus the minimum implementation context. Codex must not be used to rediscover already-resolved roadmap/architecture/Git state, generate orchestration prompts, administer branches/PRs/CI, write documentation-only changes, perform final review or rerun broad gates that ChatGPT can execute directly.

For `CODEX_DELEGATED`, prefer one substantive Codex invocation per bounded task. One focused retry is allowed only for a concrete missed defect or executor failure; after that, narrow the remaining slice or continue `DIRECT` instead of repeatedly rebuilding the same agent context. Codex follows `prompts/CODEX-RUN.md` in `LOCAL_DELEGATED` mode, receives the literal `EXPECTED_TASK_ID`, edits/verifies the bounded task and leaves the candidate diff uncommitted. Codex does **not** own orchestration state, final acceptance, commit, push, merge or remote synchronization in this mode. ChatGPT immediately inspects the actual local diff and verification result, applies the same quality gate, makes only tiny in-scope corrections directly, then commits/pushes accepted work.

A local `codex` executable/version check proves installation only, not auth/network/backend readiness. Do not spend event time on a separate catalog/preflight ceremony: the first real bounded invocation is the readiness check. If Codex fails before producing a trustworthy candidate because of auth/network/transport/backend availability, record it as an execution-tool issue and continue `DIRECT` when safe. Codex unavailability alone is not a project blocker. Never use dangerous approval/sandbox bypass flags.

### REMOTE_ORCHESTRATED / standalone fallback

When ChatGPT lacks authorized workstation access, preserve the repository/API orchestration flow. A separately launched Codex uses `STANDALONE_CODEX`, performs the full freshness gate itself, commits/pushes as required, and ChatGPT reviews the resulting repository diff. Local access or Codex installation must never be a project-start prerequisite.

## 4. Repository topology and orchestration freshness

Topology lives in `workflow/STATE.md`, but the active task must never be trusted from an arbitrary stale checkout.

Before reading `workflow/NEXT_CODEX_TASK.md`, every **standalone/manual** Codex run must follow the pre-run freshness gate in `prompts/CODEX-RUN.md`: clean-state check, safe fetch of the control-plane `main`, non-rewriting refresh of local `main`, then exact `EXPECTED_TASK_ID == STATE.CURRENT_TASK_ID == NEXT.TASK_ID` validation. In `LOCAL_DELEGATED`, ChatGPT performs that synchronization before invocation and Codex instead verifies the prepared branch/task IDs without fetching or mutating Git state. Dirty state, diverged/ahead local main, unsafe history or task-ID mismatch is `BLOCKED`; never repair it with reset/rebase/force-push.

- `GITHUB_PRIMARY`: `origin` is official and `origin/main` is the orchestration source.
- allowed mirror mode: official GitLab/V-Works remains `origin`; GitHub control plane is `github`, and `github/main` carries orchestration updates.
- `*_ONLY`: do not create an external mirror.

If `REMOTE_SETUP_STATUS=PENDING_CODEX_SETUP`, `prompts/CODEX-RUN.md` performs the one-time non-rewriting remote setup/sync before product work.

Never force-push/rebase/reset valid official history merely to create parity.

## 5. Task boundaries and architecture

Implement the smallest complete slice. No unrelated refactor, speculative shared abstraction, framework/runtime/database/container/service or cosmetic UI work without a Must/official/security/reproducibility reason.

Preserve clear ownership, dependency direction and external integration boundaries. Keep provider-specific details out of domain/application logic when a narrow adapter is sufficient.

## 6. Iteration quality baseline

For IMPLEMENT/FIX/CONTINUE, the default quality gate is intentionally compact and does not require loading the full quality document:

- satisfy every active acceptance criterion;
- run every task `Required checks` item and relevant existing focused tests;
- do not claim an unrun check as PASS;
- preserve security/data-integrity boundaries and do not commit secrets;
- avoid unrelated scope, dead code and obvious regression;
- keep the resolved delivery/AI/UI/CI contract intact;
- commit/push the required branch/remotes and verify required parity.

Read `docs/QUALITY.md` during an ordinary iteration only when the task Context pack explicitly lists it because the change is architecture/security/quality-sensitive or otherwise needs the detailed policy.

FINALIZE always uses the full FINAL gate in `docs/QUALITY.md`.

## 7. Resolved delivery, CI and AI contracts

Use the task's `## Resolved contract snapshot` as the execution-time cache of the current task-relevant decisions. The Chat orchestration stage owns keeping that snapshot aligned with canonical project state.

Read `docs/DELIVERY.md` or `docs/AI.md` only when explicitly listed in the Context pack or when a concrete missing fact prevents safe execution.

Project CI belongs to the official primary platform and is created only when the resolved task contract requires it, normally with the first runnable slice. It is verification-only unless official rules require more.

Never fake AI. `NO_AI` / `PROHIBITED` means no model dependency; `BLOCKED` means do not simulate mandatory AI; `USE_AI` must preserve data/secret boundaries and bounded output validation.

When `USE_AI` is selected and official rules do not require another provider/model/route, preserve the default hackathon AI profile from the resolved contract: Groq OpenAI-compatible API, model `openai/gpt-oss-120b`, operator-owned temporary key with a 2-day lifetime, and VPN `TUN`/`SYSTEM_TUNNEL` routing. Do not spend task time rediscovering the provider/model in documentation. For a static HTML delivery the key is entered through the masked settings UI and kept only in page memory; for a Python/local runtime it is read from process environment variable `GROQ_API_KEY`. Never commit, echo, log or persist the key.

When the resolved contract includes `CPS_ISOLATED_REVIEW=AUTO|YES`, use the CPS LLM contract already embedded in the task/docs. Do not inspect any external/reference repository during implementation merely to rediscover the connection method. Preserve this runtime-neutral wire contract unless an explicit current corporate/task override is recorded:

- OpenAI-compatible Chat Completions over HTTP(S);
- configured base URL normalized to `/v1/chat/completions` unless already complete;
- runtime-configured model;
- `POST` JSON with `Content-Type: application/json`, `model`, `messages`, `stream` and only needed supported generation fields;
- add `Authorization: Bearer ...` only for a non-empty configured key; current CPS no-auth mode omits Authorization;
- explicit non-2xx/transport/invalid-response failure;
- one narrow LLM boundary so Groq and CPS do not duplicate domain/business logic;
- runtime binding follows the chosen stack: browser HTTP for browser delivery, Python HTTP/OpenAI-compatible client for Python, equivalent HTTP client for another runtime.

Potential CPS transfer does not force HTML and does not force Python. If Python is already the justified stack, the same CPS LLM must be callable from Python. Missing internal base URL/model values must not be guessed; live CPS PASS is recorded only after the final artifact is exercised inside the corporate contour through its own runtime path.

## 8. Evidence and submission are lazy context

Do not preload evidence/submission state for ordinary implementation.

Read/update `docs/EVIDENCE.md` only at the evidence step when the completed change creates or changes a demonstrable fact. Read `docs/SUBMISSION.md` only for FINALIZE/submission work or when the active task explicitly lists it.

Unrun checks are never PASS. Record exact commands/scenarios actually executed when evidence is updated.

## 9. Git completion

In `LOCAL_ORCHESTRATED`, ChatGPT performs commit/push/parity only after reviewing the direct or delegated candidate diff. In `STANDALONE_CODEX`, Codex completes task → commit/push required branch/remotes → verify required parity → stop. Review selects the next action.

When `PARTICIPATION_MODE=SOLO`, `SPRINT_PROFILE=ULTRA_SHORT`, `EXECUTION_MODE=LOCAL_ORCHESTRATED`, and official rules do not require PRs/branches, use `SOLO_MAIN_CHECKPOINTS`: bounded tasks target `main`; ChatGPT reviews the actual diff and required checks before each commit; no PR/feature-branch ceremony is required. Use `TASK_BRANCHES` or `OFFICIAL_OVERRIDE` for team work, remote/manual execution, or explicit Git rules.

In `ULTRA_SHORT`, delegation must be clearly cheaper than DIRECT execution; do not spend the sprint rebuilding agent context for marginal work. After feature freeze, do not add Should/Could work. After demo freeze, only bounded demo-critical/Must/hard-gate fixes are allowed; prefer a last-known-good rollback to risky broad repair. After stop hacking, do not mutate product/runtime behavior: perform only packaging, report, presentation, or submission work.
