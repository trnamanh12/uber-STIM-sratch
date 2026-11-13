# AGENTS.md — Repository Engineering Rules

## Mission

Produce small, correct, maintainable changes that fit the existing system. Optimize for **verified behavior and clear boundaries**, not lines of code, commits, or agent throughput.

Treat the repository as the primary source of project context: its structure, interfaces, tests, and documented decisions. Use this file for durable working rules, not as a substitute for reading the code. Do not introduce separate agent-memory or retrieval systems unless the task genuinely requires them.

## 1. Understand before editing

1. Read the applicable `AGENTS.md` files, project README, build configuration, and relevant documentation. More-specific instructions apply to their directory; higher-priority user/system instructions take precedence.
2. Locate the feature by **business concept**. Inspect nearby domain models, services, handlers, UI components, contracts, and tests before creating new patterns.
3. Identify the smallest set of files and modules that should change. State assumptions and dependencies. For nontrivial changes, establish a short plan with scope, acceptance criteria, and verification steps.
4. Follow existing conventions **only when they are sound**. An existing shortcut is not necessarily a pattern to copy. If conflicting examples exist, favor the documented architecture and tested behavior.
5. Ask before proceeding if a decision is materially ambiguous, irreversible, security-sensitive, or likely to alter public behavior. For low-risk ambiguity, make a reasonable assumption and disclose it.
6. Before adding complexity for some speculative, near-impossible concurrency or security edge case, explain it clearly to the user first: what exact problem it causes, how likely it is, how much extra code it'll take—only add it once the user gives the nod. Don't quietly expand the scope just to make it "theoretically more robust".


## 2. Architectural boundaries

Organize by **business capability**, with layers separating distinct reasons to change. Names should map the same concept across the stack. For a feature named `loop`, use this layout **when those directories exist in the project**:

```text
backend/internal/domain/loop/     # concepts, types, invariants
backend/internal/service/loop/    # use cases and orchestration
backend/internal/handler/loop/    # HTTP/transport adaptation
web/src/components/loops/        # UI and interaction
```

Actual repository conventions take priority over these illustrative paths. Do not create directories or layers merely to match the example.

| Part | Owns | Must not own |
| --- | --- | --- |
| **Domain** | Business concepts, state, invariants, domain rules | HTTP details, UI, database queries, infrastructure SDKs |
| **Service / application** | Use cases, workflows, transactions, authorization decisions, coordination between domain objects and interfaces | Presentation details, transport parsing, raw DB access in handlers |
| **Handler / transport** | Request parsing, validation of transport shape, auth context extraction, invoking services, response/error mapping | Core business decisions, direct persistence queries |
| **UI component** | Rendering, local UI state, user interaction, calling an API/client abstraction | Server business rules, direct persistence access |
| **Repository / adapter** (when needed) | Persistence and external-system integration behind clear contracts | Business policy that belongs in the domain or service |

Follow these rules:

- Prefer dependency flow **transport/UI → application service → domain**; infrastructure implements interfaces used by the application. Avoid cycles.
- Keep business invariants enforceable independent of HTTP handlers and UI components.
- Validate incoming external data just once at the entry point, then pass around values with fixed types—don't re-check every layer down the line.
- A service must not bypass established persistence abstractions; a handler must not bypass its service to query the database.
- Share contracts deliberately. When changing APIs, update their schemas/types, generated clients, callers, and tests together.
- Cross-domain behavior belongs in an explicit coordinating use case or documented interface, not hidden imports into another domain's internals.
- Choose the **fewest boundaries that provide clear ownership**. Split a module when it develops a different reason to change, substantial independent complexity, or a stable interface. Merge or avoid layers that only forward calls without adding meaningful separation.

## 3. Code quality: do not amplify technical debt

- Match clear, well-tested patterns; do not replicate known shortcuts just because nearby code uses them.
- Do not introduce magic numbers, duplicated rules, hidden side effects, unexplained fallbacks, broad catch/ignore blocks, or suppressed type/lint errors.
- Prefer simple code and explicit names over clever abstractions. Avoid speculative generalization, new frameworks, and dependencies unless justified.
- Don't prematurely extract logic that's only used once into a function; just inline it at the call site, unless it'll be reused or it's hiding some genuinely complex chunk.
- Skip try/catch unless you have to, and if a function can be written in one go, don't split it up.
- Refactor locally when necessary to implement the requested change correctly. If broader debt blocks safe work, explain the problem and propose a separate focused cleanup; do not silently expand scope.
- Preserve backward compatibility unless an approved change explicitly breaks it. Make migrations and rollouts deliberate and reversible where possible.
- Never hard-code secrets; respect authentication, authorization, tenant isolation, data privacy, and existing threat boundaries.

## 4. Use types and contracts as quality gates

- Prefer explicit types and checked interfaces. Avoid `any`, unchecked casts, and equivalent escape hatches unless justified.
- For Go, TypeScript, Protocol Buffers, or other typed systems used here, keep definitions synchronized across backend, frontend, and wire contracts.
- Run the repository's configured formatters, code generation, compiler/type checks, and linters where applicable. **Never hand-edit generated artifacts** when a generator owns them.
- A successful compilation is necessary but not sufficient: types cannot prove business correctness, security, or full runtime integration.

## 5. Feedback loop: cheapest check first

After every meaningful change, verify in this order as applicable:

1. **Format / compile / type-check / lint:** catch structural errors immediately.
2. **Focused unit tests:** validate domain rules, service logic, failures, edge cases, and regressions.
3. **Integration / end-to-end tests:** verify real paths across APIs, persistence, and UI where affected.
4. **CI-equivalent checks:** run the broader suites and platform/build checks required by the repository before merge.

Testing rules:

- For changed behavior, add or update tests at the lowest useful level. Prefer assertions about behavior over implementation details.
- Include negative and boundary cases, especially authorization, tenant isolation, idempotency, concurrency, and failure handling when relevant.
- Start narrow and expand according to the blast radius. For cross-module or contract changes, verify downstream consumers.
- Never delete, weaken, skip, or rewrite a failing test merely to make a build green. Fix the defect or clearly explain why an expectation must legitimately change.
- Do not claim a command passed unless it actually ran successfully. Report skipped checks and environmental blockers explicitly.

**Project commands:** Discover authoritative commands from `README`, `Makefile`, `package.json`, CI configuration, or equivalent. Use those commands; do not invent project-specific scripts. Maintainers should document exact setup, test, build, lint, codegen, and E2E commands here once known.

## 6. Work in bounded tasks

Each implementation task should have:

- **Ownership:** named module(s), files, or interfaces the agent may modify.
- **Goal:** observable user or system behavior, not a vague request to “improve” things.
- **Acceptance criteria:** expected behavior plus important error/edge cases.
- **Definition of done:** code, tests, contracts/docs as needed, and a verification report.

Prefer small, independently reviewable diffs. Avoid drive-by formatting, unrelated refactors, sweeping renames, and dependency upgrades. Do not edit code you do not understand without first tracing its contract and callers.

## 8. Experiment safely

When implementation is cheap, prefer **small, reversible experiments** over prolonged speculation for uncertain engineering questions:

1. State a hypothesis and a measurable success/failure signal.
2. Test in a sandbox, test environment, or otherwise safe setting.
3. Observe actual failures; improve the design based on evidence.
4. Add regression tests for discovered failure modes before declaring the design stable.

Do not treat production as a disposable test environment. Changes affecting customer data, security, payments, infrastructure, or deployment require appropriate review, safeguards, and rollback plans.

## 10. Improve the harness

When an agent repeatedly makes the same mistake, fix the **source of ambiguity**: code structure, naming, contracts, types, tests, CI, or a short instruction in the appropriate `AGENTS.md`. Prefer enforceable checks over longer prompts. Add nested `AGENTS.md` files only for genuinely local rules; keep this root file concise and accurate.