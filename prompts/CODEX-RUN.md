# CODEX-RUN — autonomous bounded execution

`workflow/NEXT_CODEX_TASK.md` is the self-contained task contract and context manifest. Optimize for minimum context loading as well as minimum implementation scope.

Every Codex invocation must carry `EXPECTED_TASK_ID=<actual TASK_ID>` and an invocation mode:

- `LOCAL_DELEGATED` — ChatGPT has already safely synchronized/prepared the local task branch. Codex edits and verifies only, then leaves the candidate diff uncommitted for ChatGPT review.
- `STANDALONE` — manual/fallback Codex execution. Codex owns the full freshness gate plus task commit/push as before.

Never use `--dangerously-bypass-approvals-and-sandbox` or an equivalent unsafe bypass merely for speed.

## 0. Pre-run orchestration freshness gate — before reading NEXT

Inspect `git status --short`, current branch, remotes and refs before any checkout-changing operation. Never overwrite unexpected user changes.

If the index or worktree is dirty, stop `BLOCKED` before switching branches or synchronizing orchestration state.

For `LOCAL_DELEGATED`, the caller already owns freshness and branch preparation. Read `workflow/STATE.md` and `workflow/NEXT_CODEX_TASK.md` now and verify all of the following before edits:

- `STATE.EXECUTION_MODE == LOCAL_ORCHESTRATED`;
- launcher `EXPECTED_TASK_ID == STATE.CURRENT_TASK_ID == NEXT.TASK_ID`;
- `NEXT.EXECUTION_PATH == CODEX_DELEGATED` (or `AUTO` explicitly resolved to delegation by the caller);
- current branch equals `NEXT.TARGET_BRANCH`.

On mismatch stop `BLOCKED` and report facts. Do not fetch, switch branches, merge, commit, push, rewrite history or mutate STATE/NEXT in `LOCAL_DELEGATED`; ChatGPT owns those operations. After these checks skip the remaining standalone freshness steps and section 1, then continue at section 2.

For `STANDALONE`, continue with the full freshness gate below. Read only the repository-topology keys from the local `workflow/STATE.md` needed to identify the orchestration remote; do **not** read `workflow/NEXT_CODEX_TASK.md` yet.

- `GITHUB_PRIMARY`: orchestration source is `origin/main`.
- allowed GitLab/V-Works mirror: orchestration source is `github/main`; official product history remains `origin`.
- `*_ONLY`: use only the configured official remote; never create an external mirror.

For the selected orchestration remote run a safe fetch such as `git fetch --prune <remote> main`. Fetch must not mutate the working tree.

Refresh local `main` without history rewriting:

1. If local `main` does not exist but `<remote>/main` does, create a tracking `main` from that remote ref.
2. If local `main` is ahead of or diverged from `<remote>/main`, stop `BLOCKED`; do not reset, rebase, force-push or discard local commits.
3. If the current branch is not `main` and the worktree is clean, `git switch main`.
4. Fast-forward only with `git merge --ff-only <remote>/main` (or an equivalent non-rewriting fast-forward operation).
5. Verify local `main` and the orchestration ref resolve to the same commit before loading the active task.

Only after that synchronization read refreshed `workflow/STATE.md` and `workflow/NEXT_CODEX_TASK.md`.

Compare all three values:

- launcher `EXPECTED_TASK_ID`;
- `STATE.CURRENT_TASK_ID`;
- `NEXT_CODEX_TASK.TASK_ID`.

They must be identical and not `NONE`. On mismatch, stop `BLOCKED`, report the three IDs plus local/remote main SHAs, and make no product edits. This is the stale-checkout guard.

After the task is validated, resolve `BASE_BRANCH` and `TARGET_BRANCH` from NEXT. Stay on `main` when the task targets main. Otherwise switch/create the target branch safely from the refreshed base. If an existing target branch needs the refreshed base/orchestration state, integrate it with normal non-rewriting Git; a merge conflict or unsafe history condition is `BLOCKED`. Do not execute the task from a branch that still carries an older NEXT contract.

## 1. Repository and one-time mirror setup — STANDALONE only

`LOCAL_DELEGATED` skips this section; ChatGPT owns local orchestration/remotes.

For `STANDALONE`, read topology from the refreshed `workflow/STATE.md`.

- `GITHUB_PRIMARY`: `origin` is official.
- allowed mirror: official GitLab/V-Works must be `origin`, GitHub control plane `github`.
- `*_ONLY`: never create GitHub mirror.

If `REMOTE_SETUP_STATUS=PENDING_CODEX_SETUP`, perform the one-time non-rewriting setup before product work: configure the approved remotes, fetch, verify safe DAG compatibility to the extent required, synchronize compatible main history, verify parity, set setup READY and commit/sync that state. Never force/rebase/reset/cherry-pick to manufacture parity. A real topology/history conflict is BLOCKED.

## 2. Load minimum context

For IMPLEMENT/FIX/CONTINUE read only:

1. `AGENTS.md`
2. `workflow/STATE.md`
3. `workflow/NEXT_CODEX_TASK.md`
4. the task's explicit `## Context pack`
5. the smallest source/test files needed for the requested change.

Do not preload the repository README or the full SPEC/PLAN/QUALITY/DELIVERY/AI/EVIDENCE/SUBMISSION set.

Treat the task `Resolved contract snapshot`, scope, acceptance criteria and Required checks as the execution contract. If one execution-critical fact is genuinely absent, open only the single canonical document that owns it, report that context-pack gap, and continue if safe.

In `LOCAL_DELEGATED`, do not spend the session on repository-wide discovery, architecture/planning, restating the task contract, Git/PR/CI administration, documentation-only work, final review or broad repeated test orchestration unless a specific Required check explicitly makes that execution work part of the delegated slice. The orchestrator has already resolved those concerns. Move from the minimum fit/reuse inspection directly into implementation and targeted verification.

For FINALIZE, load the broader finalization pack and always include `docs/QUALITY.md`, `docs/EVIDENCE.md` and `docs/SUBMISSION.md`.

## 3. Execute smallest complete change

Follow only In scope. Preserve ownership/dependency/security boundaries. Do not add runtime/framework/database/container/supporting service without a resolved Must/official/security/reproducibility reason.

Use the resolved task snapshot for delivery/CI/UI/AI decisions. Read full `docs/DELIVERY.md` or `docs/AI.md` only when the Context pack explicitly requires them or a concrete missing fact blocks safe execution.

In `LOCAL_DELEGATED`, do not mutate `workflow/STATE.md` or replace `workflow/NEXT_CODEX_TASK.md`; ChatGPT owns orchestration. Factual `docs/EVIDENCE.md` changes are allowed only when the demonstrated fact actually changed and the active task permits them.

## 4. Verify

IMPLEMENT/FIX/CONTINUE: apply the compact iteration baseline from AGENTS plus every task Required checks item. Read full `docs/QUALITY.md` only when the Context pack lists it.

FINALIZE: apply the full FINAL gate in `docs/QUALITY.md`.

Record exact commands/scenarios/results; unrun check is never PASS. Fix concrete in-scope defects and rerun affected checks. Do not expand into optional polish.

## 5. Evidence and finalize

For an ordinary iteration, do not preload `docs/EVIDENCE.md`. Open it only after verification when a demonstrated capability/fact actually needs to be recorded, then update only that fact.

For `LOCAL_DELEGATED` FINALIZE, perform the requested full verification and leave any in-scope candidate changes uncommitted. Do not record final acceptance SHA, set READY, merge, push or update orchestration state; ChatGPT performs those acceptance/Git steps after independent review of the candidate diff.

For `STANDALONE` FINALIZE:
1. complete product/evidence verification;
2. commit accepted content baseline;
3. record its SHA and final facts in `docs/SUBMISSION.md`;
4. apply FINAL gate;
5. set READY only if it passes; otherwise leave NOT_READY/BLOCKED;
6. commit final process metadata, push required remotes and verify current main parity.

## 6. Finish according to invocation mode

For `LOCAL_DELEGATED`, stop after implementation + required verification and leave the complete candidate diff in the current worktree for ChatGPT review. Do **not** commit, push, merge, change remotes, synchronize `main`, alter STATE/NEXT or claim final acceptance. Final response: status; current branch; context actually loaded; files changed; exact verification/results; applicable AI/CI/delivery/UI/security notes; blockers only. If Codex auth/network/backend transport fails before a trustworthy candidate is produced, report the execution-tool failure; the local orchestrator may continue the task `DIRECT`.

For `STANDALONE` IMPLEMENT/FIX/CONTINUE: commit target branch and push required remotes; verify required parity. Do not merge unless NEXT task mode requires integration.

For `STANDALONE` FINALIZE: integrate accepted work to main using normal history-preserving Git, no new features, push/sync all required remotes and verify current main parity.

Standalone final response: status; branch/commit; **context actually loaded**; quality result; exact verification; applicable AI/CI/delivery/UI/security; evidence/submission changes; observed refs/parity; blockers only.

After standalone push stop. ChatGPT review chooses the next action.
