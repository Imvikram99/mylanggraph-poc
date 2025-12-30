# Implement `<feature summary>` — Architecture Plan

> Persona: **architect**  
> Target stack: **LangGraph POC**

## Knowledge Base References
- [MCP_SERVER_ARCHITECTURE.md](../MCP_SERVER_ARCHITECTURE.md) — reuse the documented MCP gateway, RBAC enforcement, and provider-abstraction layers when defining the new LangGraph entry points and security flows.
- [CONVERSATIONAL_AI_ARCHITECTURE.md](../CONVERSATIONAL_AI_ARCHITECTURE.md) — align conversational safety, language-aware prompting, and circuit-breaker guidance with LangGraph nodes so the new feature inherits proven resiliency.

## Architecture Vision
1. **Graph-native orchestration:** Use LangGraph POC as the control plane that sequences MCP services, Spring Boot endpoints, and AI providers while preserving deterministic state transitions and auditability.
2. **Persona-aligned UX:** Provide the architect persona with composable blueprints (graph nodes, MCP services, and React widgets) that can be mixed to deliver `<feature summary>` faster without duplicating orchestration logic.
3. **MCP-aware adapters:** Treat LangGraph edges as intents routed through the RBAC-aware MCP gateway so that educator, student, and admin capabilities remain bounded as outlined in `MCP_SERVER_ARCHITECTURE.md`.
4. **Observability-first:** Every LangGraph step emits structured events (graph node, MCP service, provider metadata) enabling correlation with the circuit-breaker and language instrumentation patterns from `CONVERSATIONAL_AI_ARCHITECTURE.md`.

## System Changes
### 1. LangGraph Control Layer
- Define a `feature_summary_graph.yaml` that maps user triggers → intent classifier → MCP action nodes → validation / enrichment nodes.
- Embed guard nodes for provider selection and fallback, mirroring the circuit breaker table from `CONVERSATIONAL_AI_ARCHITECTURE.md`.
- Persist graph execution traces (inputs, outputs, chosen provider) so MCP audit trails stay intact.

### 2. MCP Gateway Extensions
- Add a `GRAPH_AGENT` service type that authorizes LangGraph-originated requests using the same JWT/RBAC middleware described in `MCP_SERVER_ARCHITECTURE.md`.
- Introduce minimal DTOs so LangGraph nodes can invoke `RoleBasedServiceRouter` safely (e.g., `GraphIntentRequest` → `McpServiceType`).
- Update audit logging to capture both graph step ID and MCP service name.

### 3. Backend Service Enhancements
- Surface Spring Boot endpoints (under `/api/graph/feature-summary/*`) that encapsulate any data fetches LangGraph needs, ensuring caching + pagination mirror existing admin/teacher flows.
- Extend AI provider configuration with LangGraph-specific policies (max tokens, timeout, preferred provider order).
- Add async workers that can be called from LangGraph when long-running MCP services are triggered; return job handles to keep the graph non-blocking.

### 4. Frontend/Experience Layer
- Deliver a thin React orchestrator widget that lets admins preview each LangGraph path, reusing prompt-building UX patterns from `CONVERSATIONAL_AI_ARCHITECTURE.md`.
- Expose a JSON schema describing the `<feature summary>` graph so future editors can visualize dependencies without reading YAML.

## Guardrails
- **Security:** Only allow LangGraph nodes to call MCP services they have scopes for; honor the RBAC contract defined in [MCP_SERVER_ARCHITECTURE.md](../MCP_SERVER_ARCHITECTURE.md).
- **Language Safety:** Reuse the language enforcement snippets from [CONVERSATIONAL_AI_ARCHITECTURE.md](../CONVERSATIONAL_AI_ARCHITECTURE.md) to avoid mixed-language responses or prompt drift.
- **Resource Limits:** Cap token counts, concurrent MCP invocations, and retry budgets per graph execution to keep provider costs predictable.
- **Schema Discipline:** Version every graph + DTO change (semantic versioning) and reject incompatible executions at startup.
- **Observability:** Require correlation IDs that flow from the LangGraph entry point through MCP logs and AI provider telemetry to simplify debugging.

## Success Metrics
- **Graph Reliability:** ≥99% of LangGraph runs finish without manual intervention, matching the circuit-breaker success targets from the conversational AI stack.
- **Latency:** New `<feature summary>` journeys complete within 1.5× the baseline MCP round trip, even when fallback providers fire.
- **Security Posture:** Zero unauthorized MCP invocations observed in audit logs after rollout.
- **Adoption:** Architect persona can configure or extend the graph within one working session (<2 hours) without code changes, demonstrating composability.
- **Quality:** User satisfaction (CSAT or quick pulse) improves by ≥15% for flows powered by the new graph vs legacy orchestration.

## Key Risks & Mitigations
- **Graph + MCP Drift:** Diverging schemas between LangGraph nodes and MCP DTOs could break production flows. *Mitigation:* introduce automated contract tests that load the graph against the `RoleBasedServiceRouter` before deployment.
- **Provider Cost Spikes:** LangGraph may amplify AI usage if loops or retries are misconfigured. *Mitigation:* enforce provider budgets per execution and emit spend telemetry modeled after the AI provider abstraction metrics.
- **Observability Gaps:** Without unified tracing, debugging multi-hop flows becomes opaque. *Mitigation:* adopt the structured logging templates defined in `MCP_SERVER_ARCHITECTURE.md` and couple them with LangGraph span IDs.
- **Persona Misalignment:** Architect stakeholders may find the graph DSL too rigid. *Mitigation:* bundle documentation + templates showing how to adapt `feature_summary_graph.yaml`, and collect feedback before general release.
- **Fallback Flooding:** Circuit breakers that trigger simultaneously may overwhelm backup providers. *Mitigation:* stagger retry schedules per node and keep warm caches of common responses as described in `CONVERSATIONAL_AI_ARCHITECTURE.md`.

## Reviewer Notes (Architecture Review)
### Acceptance Tests — Missing
- No acceptance criteria or end-to-end tests are defined. Please outline at least: (a) a multi-persona happy-path run that proves LangGraph correctly routes to educator/student/admin MCP services and logs correlation IDs; (b) a failure-path where RBAC blocks an unauthorized node and the graph surfaces the denial without leaking data; (c) a provider-fallback scenario that validates token/latency budgets plus audit logging; and (d) frontend orchestration smoke tests that confirm the React widget honors graph schema versions. Each scenario should describe inputs, expected outputs, and observability artifacts.
- Add contract tests that load `feature_summary_graph.yaml` against the DTOs introduced for `GRAPH_AGENT` so schema drift is caught before deployment. Document how these tests run in CI and required fixtures/mocks.

### Guardrail Depth — Needs Clarification
- Current guardrail bullets state intent but not enforcement points. Call out which LangGraph nodes own token-budget enforcement, which Spring Boot interceptors enforce scope filtering, and how violations are surfaced (reject vs. auto-remediation). Provide reference implementations or config snippets if reused from existing stacks.
- Document guardrails for long-running async jobs (timeout, retry, cancellation) and how job handles are validated before allowing clients to poll or retrieve results.
- Specify monitoring/alert thresholds for each guardrail (e.g., max concurrent MCP invocations per persona, acceptable error budget for provider fallbacks) plus owners for responding to breaches.
- Clarify how schema versioning guardrails interact with the frontend JSON schema—what happens when the widget loads an unsupported graph version, and how is the user warned?

## Reviewer Sign-off
### Acceptance Tests
- Multi-persona happy path that runs educator, student, and admin journeys through `feature_summary_graph.yaml`, proves correlation IDs land in LangGraph, MCP, and provider logs, and asserts the React orchestrator renders the expected state after each hop.
- RBAC denial path that injects an unauthorized node, verifies the MCP gateway rejects it through the `GRAPH_AGENT` middleware, returns a sanitized error to LangGraph, and records the violation in audit logs without leaking payloads.
- Provider fallback scenario that forces the primary AI provider to fail, validates token + latency budgets at the guard nodes, confirms the fallback honors retry spacing, and checks observability dashboards for the proper breaker state.
- Contract and frontend schema tests: CI loads the YAML graph against the DTOs introduced for `GRAPH_AGENT`, runs schema version compatibility checks, and executes widget smoke tests to ensure unsupported versions trigger the documented banner + remediation guidance.

### Guardrails
- Token budgets enforced by the provider-selection guard nodes, scope filtering via Spring Boot interceptors around `/api/graph/feature-summary/*`, and failure handling that either rejects the step or triggers auto-remediation per guardrail policy; each enforcement point links to the referenced architecture docs.
- Async job guardrails define max runtime, retry/cancel limits, and job-handle validation before exposing polling endpoints; alerts fire if handles are reused or exceed quotas.
- Monitoring thresholds cover max concurrent MCP invocations per persona, fallback error budgets, and schema-version mismatches surfaced by the frontend widget; ownership for these alerts is assigned to the architecture team’s on-call rotation.
- Widget/schema interoperability guardrail blocks rendering of unsupported versions, surfaces a UI warning, and forces operators to upgrade/rollback before LangGraph resumes, guaranteeing schema discipline.

Architecture reviewer approval is granted based on the acceptance coverage and guardrail enforcement summarized above.
