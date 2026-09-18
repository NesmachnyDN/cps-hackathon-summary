# AI Usage Policy

AI is optional. Prefer the simplest reliable deterministic mechanism unless AI is explicitly required or adds observable material capability.

## Necessity gate

Before selecting AI:

1. Check official AI/provider/data-transfer/reuse rules independently.
2. Describe the simplest deterministic baseline.
3. Use AI only for a bounded semantic/generative/probabilistic capability where the deterministic baseline is insufficient or AI adds clear observable user/judging value.
4. Verify output can be evaluated and risk bounded by validation/grounding/human confirmation/fallback.
5. Verify a compliant reachable provider fits the environment/timebox.

Results:

- `USE_AI` — all gates pass.
- `NO_AI` — deterministic path is sufficient/preferable.
- `PROHIBITED` — explicit prohibition.
- `BLOCKED` — AI is mandatory but no compliant path exists.

AI is normally unjustified for exact calculations, CRUD, fixed filtering/sorting, known-schema validation, static formatting or a short deterministic rule set that already meets Must.

## Default hackathon provider profile

Unless official hackathon rules or explicit corporate policy require/prohibit another provider, model or network route, `USE_AI` uses this preselected **internet-development** operator profile:

- `AI_PROVIDER_PROFILE: GROQ_TEMP_48H_TUN`
- provider: Groq OpenAI-compatible API;
- base URL: `https://api.groq.com/openai/v1`;
- model: `openai/gpt-oss-120b`;
- credential: a separately generated operator-owned Groq API key with approximately 2-day lifetime;
- network route: VPN in `TUN` mode, recorded as `AI_NETWORK_PATH: SYSTEM_TUNNEL`;
- model/provider documentation discovery: **not required** during intake or implementation for this default profile.

The model identifier and endpoint are deliberate hackathon defaults. Do not spend event time searching provider documentation or selecting an alternative model merely because the profile is preconfigured. The live provider preflight still verifies that the actual temporary key, model and TUN route work from the application runtime. If official requirements override the profile, record the override explicitly.

The secret value itself is never stored in the repository, generated process documents, logs, evidence or presentation.

## CPS isolated-contour runtime profile

The same hackathon artifact may later need to be transferred to the isolated CPS corporate contour for review. Resolve this during intake as `CPS_ISOLATED_REVIEW=AUTO|YES|NO`. `AUTO` means treat isolated-contour demonstration as a real portability risk unless the official task/rules make it clearly irrelevant.

The CPS connection method is already captured in this template from a previously verified internal-contour implementation. **Do not inspect or depend on any external/reference repository during a hackathon to rediscover it.** This document is the canonical runtime contract for generated projects.

### Frozen CPS LLM wire contract

Unless current verified corporate facts or official task requirements explicitly override it:

- `CPS_AI_PROFILE: CPS_INTERNAL_OPENAI_COMPAT`;
- protocol: OpenAI-compatible Chat Completions over HTTP(S);
- base URL/IP: runtime/operator value; never invent it;
- chat URL: normalize configured base to `/v1/chat/completions`, while accepting a complete `/chat/completions` URL;
- model: runtime/operator value; never invent it;
- request method: `POST`;
- request headers: `Content-Type: application/json`; add `Authorization: Bearer <key>` only when a non-empty key is configured;
- authentication for the currently known CPS service: `NONE`; therefore no Authorization header is required in normal CPS mode;
- request body: OpenAI-compatible JSON with `model`, normalized `messages`, `stream`, and only supported generation fields required by the task;
- response: read the OpenAI-compatible choice/message content and finish status needed by the product;
- error behavior: non-2xx, malformed response, timeout or transport failure must be explicit; never convert them into fake AI success;
- network route: `INTERNAL`; CPS mode must not depend on Groq, public Internet or VPN-to-Groq availability;
- provider-specific connection details stay behind one narrow LLM adapter/configuration boundary so provider switching does not duplicate product/domain logic.

### Runtime bindings

The wire contract is fixed, but its client implementation follows the delivery stack. **CPS support is not an HTML-only feature.**

- `STATIC_SINGLE_FILE` / browser runtime: call the CPS endpoint with browser `fetch` or equivalent browser HTTP API.
- Python `LOCAL_APPLICATION` / service / CLI: call the same CPS endpoint through a Python HTTP or OpenAI-compatible client using the same base URL/model/request/auth/response semantics. A direct HTTP client is acceptable and often simplest for the current no-auth CPS mode because it can omit Authorization cleanly.
- `CONTAINERIZED`: use the selected application runtime's HTTP client; containerization does not change the LLM protocol.
- Other task-required runtime: implement the same wire contract through its native HTTP client.

Do not add Python/backend merely because CPS portability is possible. Conversely, if Python is already the correct stack for the task, the CPS profile **must be callable from Python** rather than requiring a browser sidecar or HTML workaround.

The exact CPS IP/base URL and served model are environment-specific corporate values. If they are unavailable to Chat/Codex, record `CPS_INTERNAL_PREFLIGHT=NOT_RUN` and `CPS_INTERNAL_VALIDATION_MODE=PORTABILITY_ONLY`. Never guess them merely to make configuration appear complete.

### CPS validation modes

- `PORTABILITY_ONLY` — used while developing outside the corporate contour. Verify the chosen runtime implements the frozen wire contract, has runtime-configurable base URL/model, no mandatory real key, no hardcoded Groq dependency in product/domain logic, no public-internet dependency, explicit error handling and deterministic tests around provider selection/request construction. This is **not** live internal-provider evidence.
- `LIVE_CORPORATE_CONTOUR` — run from the actual CPS workstation/network using the final application runtime/path. Execute one minimal real inference and the product happy path that depends on AI. Verify current internal base URL/model, no-auth behavior, network path and runtime-specific constraints. For browser delivery this includes CORS/origin/mixed-content. For Python/service delivery this includes the actual Python/process/container network path and configuration loading.

Only `LIVE_CORPORATE_CONTOUR` with factual successful inference may produce `CPS_INTERNAL_PREFLIGHT=PASS`.

## Credential/trust mode

AI/API credential presence does **not** automatically imply a backend. Resolve one explicit mode before locking delivery:

- `NONE` — no credential required.
- `OPERATOR_SESSION_BYOK` — the local demo operator supplies their own temporary credential for the current demo/runtime session.
- `SERVER_SIDE_SECRET` — a shared/long-lived/application credential must remain hidden from browser users; requires a server or approved gateway.
- `OFFICIAL_BROWSER_MECHANISM` — organizer/provider supplies a browser-safe delegated/auth mechanism.
- `INTERNAL_ENDPOINT_AUTH` — corporate/internal mechanism governs access when one actually exists.
- `N/A` — AI not used.

For the default `GROQ_TEMP_48H_TUN` profile, use `OPERATOR_SESSION_BYOK` unless official requirements establish a different trust boundary. For the currently known `CPS_INTERNAL_OPENAI_COMPAT` profile, use `NONE` unless actual corporate evidence establishes authentication.

Credential/config injection depends on the selected delivery profile:

- `STATIC_SINGLE_FILE`: expose a professional masked AI settings field for the Groq key. Keep the key in page memory only. Do not persist it in `localStorage`, IndexedDB, cookies, URL/query parameters, browser databases, source/config, analytics, logs, screenshots or evidence. Reload/close may require re-entry. Endpoint/model may be fixed in code/config as non-secret constants for Groq and need not be editable.
- Browser + CPS: internal base URL/model are runtime/application configuration; when no key is configured, omit Authorization and do not invent a credential field.
- Python/local runtime: read the temporary Groq key from process environment variable `GROQ_API_KEY`. Do not commit a real `.env`; `.env.example` may contain only the variable name and safe placeholder. For CPS, provide runtime configuration such as `CPS_LLM_BASE_URL`/`CPS_LLM_MODEL` or a clearly documented equivalent. Current no-auth CPS mode must not require a real key.
- Containerized runtime: inject Groq secrets only at runtime; CPS endpoint/model are runtime configuration. Do not bake either secrets or environment-specific internal addresses into the image.

This is a hackathon/demo trust model, not a production credential architecture. When production hardening matters, state the intended server-side gateway, corporate gateway, delegated token or equivalent approved mechanism.

## Provider readiness gate

`USE_AI` requires early provider viability evidence. Do not postpone this to finalization or demo rehearsal.

Record:

- `AI_PROVIDER_READINESS: PASS | DEGRADED | FAIL | NOT_RUN | N/A`;
- `AI_CREDENTIAL_MODE: NONE | OPERATOR_SESSION_BYOK | SERVER_SIDE_SECRET | OFFICIAL_BROWSER_MECHANISM | INTERNAL_ENDPOINT_AUTH | N/A`;
- `AI_BROWSER_DIRECT_READINESS: PASS | FAIL | NOT_RUN | N/A`;
- `AI_NETWORK_PATH: DIRECT | SYSTEM_TUNNEL | ENV_PROXY | INTERNAL | UNKNOWN | N/A`;
- `AI_MODEL_STATUS: CONFIGURED | ACCEPTED | REJECTED | UNKNOWN | N/A`;
- `AI_PREFLIGHT_EVIDENCE: <safe summary without secret values>`;
- `AI_PROVIDER_CONTINGENCY: <official override or deterministic fallback>`;
- `AI_PROVIDER_DEBUG_BUDGET_MIN: <bounded minutes; default 5 for GROQ_TEMP_48H_TUN during BUILD unless task/timebox justifies another value>`;
- `CPS_INTERNAL_PREFLIGHT: PASS | FAIL | NOT_RUN | N/A`;
- `CPS_INTERNAL_VALIDATION_MODE: LIVE_CORPORATE_CONTOUR | PORTABILITY_ONLY | N/A`;
- `CPS_INTERNAL_PREFLIGHT_EVIDENCE: <safe summary without confidential internal values when policy requires>`.

For the default Groq profile, the canonical network route is `SYSTEM_TUNNEL`. The VPN must be enabled in TUN mode before live preflight and demo. Do not introduce an application-specific HTTP/SOCKS proxy merely to reach Groq when the TUN route is the declared working path.

If a **Python** HTTP client is selected and can inherit environment proxies, prefer disabling `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` inheritance (`trust_env=False` or equivalent) when necessary to preserve the declared Groq TUN route. For CPS, follow the verified corporate network path; do not blindly force proxy behavior either way.

A valid live Groq preflight must run from the **same execution environment and transport path as the application**, not only from curl or another project. It must verify at minimum:

1. runtime/client dependencies can initialize;
2. DNS/TLS/network route works through the active TUN path;
3. the temporary credential is accepted without printing/persisting it;
4. configured model `openai/gpt-oss-120b` is accepted by the account/project;
5. a minimal real inference request succeeds;
6. required response mode (for example structured JSON/schema) works when the product depends on it.

For `STATIC_SINGLE_FILE` with direct browser AI/API use, the browser itself is the application runtime. The preflight must therefore use the **exact judged browser path** (direct file or chosen static origin) and additionally verify provider/browser-use policy, CORS/origin behavior, memory-only token handling and allowed data transfer.

Server-side success does not prove browser viability. Browser CORS/origin failure is a concrete reason to promote delivery to `LOCAL_APPLICATION`; “AI needs a token” by itself is not.

For CPS, validation must match the selected application runtime. Browser CPS validation proves only browser delivery; Python CPS validation must run through the Python path; containerized CPS validation must run from the container. A successful call from a different client/runtime is useful diagnosis but not FINAL evidence for the artifact.

Configured endpoint/model/key presence is **not** evidence of working AI. A mock success is also not live-provider evidence.

### Failure/timebox rule

For the fixed Groq profile, do not begin with provider/model research. Diagnose only within the recorded debug budget and in this order:

1. confirm VPN is enabled in TUN mode and the runtime follows `SYSTEM_TUNNEL`;
2. eliminate accidental environment-proxy routing when relevant to a non-browser client;
3. classify browser CORS/origin/provider-policy failure separately for static delivery;
4. classify temporary-key authentication/project permission failure;
5. confirm whether the fixed configured model is accepted by the live request;
6. use an explicit official/operator override only when one exists;
7. use deterministic fallback when AI is optional and Must still remains satisfied;
8. use `BLOCKED` when AI is mandatory and no compliant live path exists.

Do not spend hackathon time browsing model catalogs or silently substituting a different provider/model. A failed fixed-model preflight is an operational fact to resolve or escalate, not a reason for open-ended discovery.

Do not switch to a backend merely to hide the temporary operator key. Promote to `LOCAL_APPLICATION` when a real server trust/responsibility boundary is required or the browser path is forbidden/non-viable.

For CPS internal validation, do not spend internet-development time attempting to reach an unavailable corporate endpoint. Verify portability against the embedded wire contract using deterministic tests, then perform the separate `LIVE_CORPORATE_CONTOUR` gate with the **same runtime type as the final artifact** when corporate access is available.

If AI is mandatory and no live internet-development path is verified, surface the blocker **before** building an AI-dependent happy path. If AI is optional, the demo must remain useful without the provider. If CPS review is only a possible later path, `CPS_INTERNAL_PREFLIGHT=NOT_RUN` does not block BUILD, but it forbids claiming isolated-contour readiness.

## Implementation contract for USE_AI

- bounded AI responsibility and non-AI responsibilities;
- default internet provider profile `GROQ_TEMP_48H_TUN` unless explicit override is recorded;
- fixed Groq endpoint `https://api.groq.com/openai/v1` and model `openai/gpt-oss-120b` for that profile;
- explicit `AI_CREDENTIAL_MODE` and secret/config field names without values;
- static HTML Groq mode: masked key entry in settings, page-memory-only lifecycle, no persistence/logging/URL exposure, clear re-entry behavior;
- Python/local Groq mode: `GROQ_API_KEY` process environment variable, never a committed secret;
- early live Groq provider preflight or explicit `NOT_RUN` reason + first-task readiness gate;
- for browser-direct Groq AI: exact-browser CORS/origin/provider-policy preflight before substantial implementation;
- TUN/system-tunnel network semantics for Groq;
- CPS uses the embedded runtime-neutral OpenAI-compatible wire contract; no external reference-repository lookup is required;
- CPS runtime binding matches the chosen stack: browser HTTP for browser, Python HTTP/OpenAI-compatible client for Python, equivalent client elsewhere;
- CPS mode uses runtime base URL/model, `/v1/chat/completions`, JSON request semantics and Authorization only when a non-empty key exists;
- CPS mode has no public-internet/Groq dependency and does not force HTML or Python;
- CPS exact endpoint/model values are never invented; outside-contour development may use `PORTABILITY_ONLY`, while actual isolated readiness requires `LIVE_CORPORATE_CONTOUR` factual evidence through the final runtime;
- timeout/error/fallback behavior;
- output parsing/validation/grounding;
- representative evaluation scenarios;
- deterministic tests around parsing/validation/business behavior and provider-profile switching/request construction;
- ordinary unit tests do not require live external/internal provider unless explicitly justified;
- live-provider checks are small, explicit smoke/evidence checks, not hidden inside ordinary test suites.
