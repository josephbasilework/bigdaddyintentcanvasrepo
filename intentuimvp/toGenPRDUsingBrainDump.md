You are a product + tech spec generator. I am attaching an unstructured “brain dump” file describing an MVP idea. Your job is to convert that attachment into a highly structured, extremely explicit MVP PRD that is optimized for being fed into BMAD v6 (BMAD-METHOD) so it can initialize the repository and generate stories cleanly.

Core constraints and non-negotiables

Modularity

Domain-Driven Design (DDD)

Painfully explicit specs

Excessive documentation

If the docs don’t clearly answer:

Where (what file/module/service does this live in?)

What (what exactly does it do?)

How (how is it implemented and how does it work?)

Why (why does it exist / why this approach?)

…then agents will guess and make a mess. Do not leave gaps.

Inputs you have

Attachment: an unstructured brain dump describing the MVP.

BMAD v6 reference repo: https://github.com/bmad-code-org/BMAD-METHOD

Use this to understand the style of outputs that help BMAD initialize repos and produce clean backlogs/specs.

PydanticAI docs: https://ai.pydantic.dev/#why-use-pydantic-ai

AG-UI docs: https://docs.ag-ui.com/introduction

Tech decisions already made (must be reflected in PRD)

We will be using:

PydanticAI, but ONLY through the Pydantic AI Gateway API

Important: Gateway is free while in Beta. (Mention this as rationale.)

We must design the system so it uses the Gateway and NOT direct provider calls for PydanticAI usage.

The code must reference environment variables and must never embed API keys.

AG-UI protocol (for agent/UI interaction patterns)

CopilotKit (for copilot-style in-app assistance / agent UX)

You may recommend additional dependencies if justified (e.g., FastAPI, Next.js, persistence, auth, background jobs, observability, testing), but you must:

Explain why each dependency exists

Explain where it lives

Explain how it’s used

Keep the MVP minimal (no gold-plating)

Environment variables (names ONLY — NEVER include secret values)

For development, the environment variable names in use will include:

PYDANTIC_GATEWAY_API_KEY

XAI_API_KEY

Do not include any secret values in PRD, code samples, or anywhere. Only refer to env var names and how they are used.

Output goal

Produce a PRD that I can paste into BMAD v6 so that BMAD can:

Initialize a new repo cleanly (structure, tooling, baseline architecture)

Generate a clear backlog (epics → stories → tasks) with acceptance criteria

Avoid ambiguity and “agent guessing”

Your output MUST be extremely structured

Deliver the PRD in the exact structure below. If the brain dump is missing details, do two things:

Make the most reasonable assumption you can, label it clearly as an assumption, and

Add a “Validation Questions” section listing what must be confirmed.

REQUIRED PRD STRUCTURE (follow exactly)
0) Document control

PRD title

Version

Date

Authors

Status (Draft/Final)

Links to source docs (BMAD repo + PydanticAI + Gateway note + AG-UI + CopilotKit)

Change log

1) Executive summary

Problem statement

Proposed MVP solution (1–2 paragraphs)

MVP success definition (measurable)

What is explicitly out of scope

2) Background + context (from brain dump)

Summarize the brain dump into:

User pain points

Desired outcomes

Key constraints

Notable quotes or “must-have” statements (paraphrase; don’t invent)

3) Personas + user journeys

Primary persona(s)

Secondary persona(s)

User journey map(s): step-by-step

Jobs-to-be-done (JTBD)

4) Scope
4.1 In-scope (MVP)

Bullet list of MVP capabilities

4.2 Out-of-scope (explicit)

Hard boundaries

4.3 MVP phases (optional)

If the brain dump implies phases, propose Phase 0 / Phase 1 / Phase 2

5) Functional requirements (painfully explicit)

For each requirement, include:

ID (FR-001, FR-002…)

Description

User value

Inputs/Outputs

Primary flow

Edge cases

Error states

Acceptance criteria (Given/When/Then)

6) Non-functional requirements

Security & secrets management (explicitly: env vars only, no keys in code/docs)

Performance targets (MVP-grade but concrete)

Reliability/availability expectations

Privacy considerations

Observability (logs/metrics/traces) minimum viable setup

Accessibility (if UI exists)

Maintainability + modularity requirements

7) Domain model (DDD)

Bounded contexts

Core domain concepts (entities, value objects, aggregates)

Ubiquitous language glossary

Key invariants and business rules

Event model (if applicable)

8) System architecture (explicit “Where/What/How/Why”)
8.1 High-level architecture

Components diagram (text diagram is fine)

Data flow diagram (text diagram is fine)

8.2 Module breakdown (THIS IS CRITICAL)

For every major module/service, specify:

Where it lives (directory / package path)

What it does

How it works (key functions, classes, protocols)

Why it exists (design rationale)

8.3 API surface (if applicable)

REST endpoints (or other)

Request/response schemas

Error codes

Auth expectations

8.4 Agent + UI interaction model

How AG-UI is used (events, messages, state)

How CopilotKit is used (what the copilot does, what it cannot do)

How the agent is constrained to avoid hallucination and destructive actions

9) AI/Agent design (PydanticAI via Gateway ONLY)
9.1 PydanticAI usage pattern

Agent responsibilities

Tools/functions the agent can call

Structured outputs (Pydantic models)

Validation and retries strategy

9.2 Gateway-only enforcement

Explicit statement: “All PydanticAI inference goes through Pydantic AI Gateway”

How code references PYDANTIC_GATEWAY_API_KEY (name only)

When/why XAI_API_KEY is used (name only)

Configuration layering (local dev vs prod)

Failure modes: gateway down, invalid key, provider errors

9.3 Safety + guardrails

Prompting rules

Data redaction rules

Logging rules (no secrets)

Allowed/disallowed actions

10) Dependency plan (must be meticulous)

Create a table:

Dependency

Purpose

Where used (module/path)

Version pinning strategy

Risk/notes

Documentation link

Must include at minimum:

PydanticAI (Gateway usage)

AG-UI

CopilotKit

Add others only if justified and minimal.

11) Repo + dev setup specification (BMAD-ready)

Proposed repo structure (directories)

Tooling:

formatter/linter

type checking

test framework

env management

Local setup steps (no secrets)

.env.example contents (names only)

CI expectations (lint/test)

12) Data storage (if needed)

What data is stored (exact fields)

Why it’s stored

Where it’s stored (DB choice)

Migration strategy (MVP-simple)

Retention rules

13) Analytics + success metrics

North star metric

Supporting metrics

Event tracking plan (minimal but explicit)

14) Risks + mitigations

Technical risks (Gateway beta, vendor dependency, UI integration complexity)

Product risks

Security risks

Mitigations

15) Open questions + validation questions

List every missing/uncertain detail needed to finalize.

Also list what assumptions you made.

16) Backlog for BMAD (Epics → Stories → Tasks)
16.1 Epics

Epic title

Description

Exit criteria

16.2 Stories (per epic)

For each story:

Story title

User story format (“As a…, I want…, so that…”)

Acceptance criteria (Given/When/Then)

Implementation notes (Where/What/How/Why pointers)

Test notes

16.3 Task breakdown (per story)

Concrete engineering tasks with file/module hints

17) Documentation plan (excessive by design)

List exact docs to create in-repo, e.g.:

/docs/architecture.md

/docs/domain-model.md

/docs/agent-design.md

/docs/ag-ui-integration.md

/docs/copilotkit-integration.md

/docs/runbook.md

/docs/security-secrets.md

For each doc:

What it must explain (Where/What/How/Why)

Audience (dev/agent/operator)

“Definition of Done” checklist

CITATIONS REQUIREMENT

Whenever you reference behavior, patterns, or constraints of:

PydanticAI

Pydantic AI Gateway

AG-UI

CopilotKit

BMAD-METHOD

…include citations/links to official documentation pages (links are fine; do not paste large quoted blocks).

FINAL CHECKLIST (must run before output)

Before you finalize the PRD, verify:

✅ No secret keys or values included anywhere (only env var names)

✅ Gateway-only is explicitly enforced and repeated in relevant sections

✅ Every major module answers Where/What/How/Why

✅ Requirements have acceptance criteria

✅ Backlog is detailed enough for BMAD to generate repo + stories safely

✅ Dependencies are justified and minimal

✅ Assumptions are labeled and open questions listed

Now do the work

Read the attached brain dump file and produce the PRD exactly in the structure above.