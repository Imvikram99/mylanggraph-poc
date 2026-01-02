# Feature Delivery Plan — `<feature summary>`

> Personas: **product_owner**, **ui_ux_designer**, **architect**, **backend_lead**, **frontend_tech_lead**, **reviewer**, **qa/ops**  
> Target stack: **LangGraph POC** + target repo (service + UI)

## Guiding Principles
- **Single-writer rule:** Each role edits only its designated plan file(s).
- **Current-first architecture:** The architect must document the current system before proposing changes.
- **API ownership:** The architect designs the API contract; backend leads implement to spec.
- **Handoff discipline:** Backend leads deliver a green build + API tests and a runnable service before frontend starts integration.
- **Traceability:** Every phase links back to upstream plans (product → UX → architecture → lead plans).

## Role Outputs (Single-Writer Rule)
| Role | File(s) | Purpose |
| --- | --- | --- |
| Product Owner | `docs/product_plan.md` | Requirement enhancement, scope, success metrics, dependencies |
| UI/UX Designer | `docs/ui_ux_plan.md` | Screens, flows, interactions, UX acceptance criteria |
| Architect | `docs/architecture_plan.md`, `docs/api_spec.md` | System design + API contract + data model |
| Backend Lead (Java/Python) | `docs/backend_plan_<stack>.md`, `docs/backend_test_report_<stack>.md` | Implementation plan + API test results |
| Frontend Tech Lead | `docs/frontend_plan.md`, `docs/frontend_test_report.md` | UI implementation plan + UI test results |
| Reviewer | `docs/review_notes.md` | Codex review findings + action items |
| QA/Ops | `docs/validation_report.md` | End-to-end validation + release readiness |

## Phase 1 — Product Requirement Enhancement (Owner: Product Owner)
**Deliverables (write to `docs/product_plan.md`):**
- Problem statement, target personas, and user value.
- In-scope vs out-of-scope features.
- Functional requirements and non-functional requirements.
- Dependencies (services, configs, docs, data).
- Success metrics and acceptance criteria.

**Acceptance Gates:**
- Requirements are testable (clear inputs/outputs).
- Dependencies and constraints are listed.
- At least one end-to-end scenario is documented.

## Phase 2 — UI/UX Design (Owner: UI/UX Designer)
**Deliverables (write to `docs/ui_ux_plan.md`):**
- Screen list with user journeys and navigation flow.
- Wireframe-level layout (textual or diagram reference).
- Interaction details (buttons, forms, error states).
- Data needed per screen (from API contract placeholder).
- UX acceptance criteria per screen.

**Acceptance Gates:**
- Every screen maps to a product requirement.
- All actions and error states are specified.
- Screens list is complete for the target persona(s).

## Phase 3 — Architecture + API Design (Owner: Architect)
**Deliverables (write to `docs/architecture_plan.md`):**
- **Current state summary** (services, data flow, constraints).
- Proposed architecture changes (modules, endpoints, data model).
- Risk analysis + mitigations.
- Observability, security, and performance considerations.

**Deliverables (write to `docs/api_spec.md`):**
- Endpoint list with request/response schemas.
- Auth/role requirements and error contracts.
- Versioning strategy + backward compatibility notes.
- Example payloads for critical flows.

**Acceptance Gates:**
- API spec supports every UX screen and workflow.
- Data model changes and migrations are documented.
- Risks + mitigations are explicit and owned.

## Phase 4 — Lead Planning + Stack Selection (Owner: Tech Leads)
**Goal:** Choose backend lead(s) by stack (Java/Python) based on the repo or services involved.

**Deliverables (backend lead writes `docs/backend_plan_<stack>.md`):**
- Endpoint-to-implementation mapping (ties to `docs/api_spec.md`).
- DB changes, migrations, and data access plan.
- API testing plan (unit + integration + contract tests).
- Build + run instructions for local verification.

**Deliverables (frontend lead writes `docs/frontend_plan.md`):**
- Screen-to-endpoint mapping (ties to `docs/ui_ux_plan.md` + `docs/api_spec.md`).
- State management + routing approach.
- UI test plan (component + smoke tests).
- Feature flag or rollout plan if needed.

**Acceptance Gates:**
- Each plan references the upstream files it depends on.
- Backend plan includes API test coverage and build steps.
- Frontend plan lists every screen + required endpoints.

## Phase 5 — Backend Implementation (Owner: Backend Lead)
**Execution Checklist (code + `docs/backend_test_report_<stack>.md`):**
- Implement endpoints per `docs/api_spec.md`.
- Add/extend data access, migrations, and validations.
- Run unit + integration tests (record commands + results).
- **Build green** (record build command + output summary).
- **Run backend locally** (record run command + health check).
- Produce API test report (pass/fail + evidence).

**Acceptance Gates:**
- Build is green and service starts locally.
- API tests pass (or explicit waivers with owners).
- Backend is ready for frontend integration.

## Phase 6 — Frontend Implementation (Owner: Frontend Tech Lead)
**Execution Checklist (code + `docs/frontend_test_report.md`):**
- Implement screens and flows from `docs/ui_ux_plan.md`.
- Connect screens to API endpoints from `docs/api_spec.md`.
- Validate buttons, forms, and error handling.
- Run UI tests and smoke checks (record commands + results).

**Acceptance Gates:**
- All planned screens and actions are present.
- UI errors match UX plan and API error contracts.
- UI tests pass (or waivers with owners).

## Phase 7 — Integration + Validation (Owner: QA/Ops)
**Deliverables (write to `docs/validation_report.md`):**
- End-to-end scenarios and outcomes.
- Cross-role handoff verification (backend ready → frontend ready).
- Observability checks (logs, metrics, tracing).
- Release readiness checklist + final sign-off.

**Acceptance Gates:**
- All core scenarios pass end-to-end.
- Backend + frontend test reports are attached.
- No critical gaps remain from review notes.

## Review + Correction Loop (Owner: Reviewer)
**Deliverables (write to `docs/review_notes.md`):**
- High-risk gaps, missing tests, or unclear requirements.
- Required corrections by role and file.
- Status updates until each gate is satisfied.

**Rule:** If any phase lacks owners/tests or fails acceptance gates, loop back to the responsible role before proceeding.
