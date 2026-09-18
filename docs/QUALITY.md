# Quality, Architecture & Security

Compact runtime contract. Apply only to the actual changed surface.

## Architecture

- One obvious owner for each material behavior/state.
- Keep business policy out of transport/UI/persistence/provider adapters.
- Cross-feature/context access uses intentional seams, not private imports.
- External/internal provider details stay behind a narrow boundary when non-trivial.
- Shared abstractions require real reuse; avoid generic dumping grounds.
- No circular dependencies or unrelated repository-wide cleanup.
- Add runtime/framework/database/container/supporting service only for Must/official/security/reproducibility value.
- Do not add a backend solely because an external API uses a credential; distinguish operator session BYOK from a shared/application secret and apply `docs/DELIVERY.md`.
- When CPS isolated-contour portability is in scope, use the embedded OpenAI-compatible wire contract. Switch Groq -> CPS through configuration/provider boundary rather than duplicated business logic. CPS portability itself does not privilege HTML or Python.

## Code quality

- Small readable units; split materially oversized mixed-responsibility code.
- Happy path and error path locally understandable.
- Explicit validation/errors at boundaries; no silent fake success.
- No debug/dead/commented-out code or completion-blocking stale TODO in implemented behavior.
- Reuse focused existing contracts before inventing parallel helpers/services/DTOs.

## Security

- No secrets/real `.env`/tokens/passwords/private keys embedded in Git, logs, screenshots, CI or shipped browser code/config.
- `OPERATOR_SESSION_BYOK` is allowed only when the resolved contract permits it: operator-entered, memory-only, never persisted to browser storage/cookies/URL/logs, never echoed, and lost on reload/close unless an approved browser mechanism says otherwise.
- For the currently known CPS no-auth profile, omit the `Authorization` header when the configured key is empty. Do not invent a dummy secret or fake authentication requirement.
- Do not commit confidential internal endpoint/model/topology values when corporate policy forbids it; keep environment-specific CPS values in runtime/operator configuration.
- Treat user/file/external/model input as untrusted before SQL/shell/filesystem/HTML/URL/tool side effects.
- External/internal calls have explicit failure handling; timeouts/retries are added when supported/needed by the selected transport and task.
- Prevent obvious path traversal/unsafe upload placement when files exist.
- LLM/model output is data, not executable authority.
- Use synthetic demo data unless real data is explicitly authorized.
- Keep runtime/container/CI permissions minimal.

## UI/UX when applicable

Default without supplied design system: restrained, professional, content-first, high-clarity, low-decoration.

- clear primary task/action and information hierarchy;
- coherent semantic tokens/spacing/typography/components;
- loading/empty/error/success/disabled states where relevant;
- labels, validation and recovery are understandable;
- keyboard/focus and basic WCAG-AA-class contrast/readability for demo-critical controls;
- no fake metrics/non-functional controls/card soup/decorative generated-app filler;
- stable at declared demo viewport; broader responsiveness only when required.
- for `OPERATOR_SESSION_BYOK`, use a professional masked credential control/settings surface with explicit connection state; never render the token back to the user after entry.
- for `CPS_INTERNAL_OPENAI_COMPAT`, configuration UI is required only when the selected runtime actually uses UI configuration. Python/service delivery may use environment/CLI/config instead. Current no-auth CPS mode must not present a fake mandatory credential.

## ITERATION gate

For IMPLEMENT/FIX/CONTINUE:

- [ ] Diff is only the active slice/fix.
- [ ] Slice AC and REQUIRED_CHECKS pass or incompleteness is explicit.
- [ ] Changed happy path verified; meaningful negative path checked when introduced.
- [ ] Relevant lint/typecheck/build/test passes when configured.
- [ ] No obvious ownership/security/secret/error/reproducibility defect introduced.
- [ ] Resolved delivery/CI/AI/UI contract is not silently changed.
- [ ] If this slice introduces or depends on `USE_AI`, provider readiness is handled before substantive AI-dependent work: live same-runtime preflight PASS, or explicit NOT_RUN/FAIL with contingency/blocker executed within the bounded debug budget. Success in another app, configured credentials or mocks alone are insufficient.
- [ ] For `STATIC_SINGLE_FILE` + direct AI/API, the same-runtime preflight is executed in the target browser/origin and explicitly covers provider browser policy plus CORS/origin; server-side/curl success is insufficient.
- [ ] If `OPERATOR_SESSION_BYOK` is selected, token lifecycle is memory-only and no browser persistence/echo/log/URL leakage exists.
- [ ] If `LOCAL_APPLICATION` was selected over a browser-capable Must scope, the task/spec names a real server responsibility or concrete browser preflight/policy failure; “AI needs a token” alone is not sufficient.
- [ ] If external API networking is material, runtime route semantics (direct/system tunnel/env proxy/explicit proxy/internal) are explicit enough that VPN/proxy behavior cannot silently change the judged path.
- [ ] If `CPS_ISOLATED_REVIEW=AUTO|YES` + `USE_AI`, the changed slice implements the embedded runtime-neutral CPS contract: OpenAI-compatible `/v1/chat/completions`, runtime base URL/model, JSON `POST`, `Content-Type: application/json`, Authorization only for a non-empty key, explicit failures, internal network mode and no hardcoded Groq dependency in business logic.
- [ ] The CPS client binding matches the selected stack: browser client for browser delivery, Python client for Python delivery, equivalent HTTP client for another runtime. No browser-only dependency is introduced into a Python CPS path and no Python/backend dependency is introduced solely for a browser-capable CPS path.
- [ ] No external/reference repository lookup is required to implement the CPS connection method during the hackathon; the active task/docs are self-contained.
- [ ] `CPS_INTERNAL_PREFLIGHT=PASS` is never recorded from mocks, config presence, Groq success or another application's success. Outside the corporate contour use `CPS_INTERNAL_VALIDATION_MODE=PORTABILITY_ONLY` / `NOT_RUN` rather than fake live evidence.
- [ ] Evidence updated only for demonstrable changed facts.
- [ ] Required Git push/sync completed.

Do not expand ITERATION into final rehearsal or optional polish.

## FINAL gate

For FINALIZE verify integrated state:

- [ ] All Must AC have factual implementation + verification evidence.
- [ ] Official hard gates/submission requirements satisfied or blocker recorded.
- [ ] Architecture/ownership/dependencies remain coherent.
- [ ] No secret, unsafe sensitive side effect, fake-success path or unassessed demo-critical failure remains.
- [ ] Relevant regression/lint/typecheck/build/tests pass.
- [ ] Project CI status satisfies the resolved contract (`PASS`, `UNAVAILABLE` or `N/A` as applicable).
- [ ] Selected delivery lifecycle passes from committed state.
- [ ] README canonical first-run/install/start sequence has been executed exactly as documented from a clean or equivalently isolated committed checkout on the declared demo platform; it has no hidden dependency on shell activation, globally installed application packages/CLIs, IDE state, aliases or uncommitted files.
- [ ] README subsequent-run path works after stopping/restarting the application without repeating unnecessary setup.
- [ ] Human-facing UI demo flow/states/accessibility basics pass when applicable.
- [ ] For `USE_AI`, the actual AI happy path is verified from the declared demo environment through the same application/runtime/network route, with current selected model and required response validation. Provider configuration/mock tests alone are not FINAL evidence.
- [ ] For `STATIC_SINGLE_FILE` direct AI/API, FINAL evidence includes the exact judged browser/origin path, CORS/browser-policy viability and post-reopen credential re-entry behavior when `OPERATOR_SESSION_BYOK` is used.
- [ ] For optional AI, deterministic/provider contingency is verified and visibly distinguishable from AI success; for mandatory AI, unavailable provider path is a blocker rather than a hidden fallback.
- [ ] External-provider network/proxy/VPN assumptions are documented and repeatable after restart; no accidental dependency on ambient shell state remains.
- [ ] If CPS isolated-contour review remains applicable, README/RUNBOOK contains a separate internal-contour configuration/check path. `PORTABILITY_ONLY` is acceptable for internet-side finalization only when no internal demonstration has yet been required; it must not be described as live CPS PASS.
- [ ] Before an actual CPS isolated-contour demonstration, `CPS_INTERNAL_VALIDATION_MODE=LIVE_CORPORATE_CONTOUR` and `CPS_INTERNAL_PREFLIGHT=PASS` require a real inference from the final application runtime/path inside the corporate network. Browser delivery checks browser CORS/origin/mixed-content; Python/service/container delivery checks that actual runtime path instead.
- [ ] CPS mode satisfies the embedded wire contract, has no public-internet/Groq dependency and switching provider does not require business-logic edits.
- [ ] AI contract/evaluation passes when USE_AI; no hidden AI dependency otherwise.
- [ ] README/EVIDENCE/SUBMISSION match current facts and resolved language.
- [ ] Demo works after required reopen/restart/reset.
- [ ] Required remote/current-head parity passes or N/A.
