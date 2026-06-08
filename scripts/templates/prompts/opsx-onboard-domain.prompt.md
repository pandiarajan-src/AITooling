---
mode: 'agent'
description: 'Generate a functional OpenSpec spec.md for one business capability domain from existing code'
---

Generate a **functional specification** in OpenSpec format for a specific business capability domain by reverse-engineering behavior from the existing codebase.

**Ask the user which domain to onboard** if they haven't specified one. Reference `domain-map.yaml` at the repository root for available domains and their paths. Remind the user: run one domain per Copilot session for best results.

---

## Setup

1. Read `domain-map.yaml` to find:
   - The domain's `label` (human-readable name)
   - The domain's `name` (slug, used as the folder name under `openspec/specs/`)
   - The domain's `paths` (directories/files to scan)
   - The domain's `description` (high-level summary)

2. If `domain-map.yaml` doesn't exist, ask the user to run `/opsx-discover-capabilities` first, or ask them to specify the domain name and relevant paths manually.

3. Check if `openspec/specs/<domain-name>/spec.md` already exists — if so, ask the user whether to overwrite or append.

---

## Deep Scan — Functional Behavior Extraction

Scan **all files** under the domain's paths. Focus on extracting WHAT the system does, not HOW it does it.

### Entry Points (start here)
- **HTTP handlers / controllers**: For every route, extract: HTTP method, path pattern, inputs accepted (path params, query params, body schema), outputs returned (response shapes), authentication requirements, error responses
- **Message consumers / event handlers**: What event/message triggers it? What does it do? What side effects does it have?
- **Scheduled jobs**: When does it run? What does it do?
- **Exported public functions** (for shared libraries): What inputs and outputs? What guarantees does it make?
- **CLI commands**: What arguments/flags? What does each command do?

### Business Rules (critical for accurate specs)
- Conditional logic that enforces rules (if X then Y, only allow if Z)
- Validation schemas and constraints (required fields, format rules, min/max values)
- State machine transitions (what states can a domain object be in? What events trigger transitions?)
- Authorization rules (who can do what, under what conditions?)
- Calculation or transformation rules (what formulas or mappings are applied?)

### Data Contracts
- What data shapes flow in and out? (describe the data, not the class names)
- What external systems are called? (describe the interaction, not the library used)
- What is persisted and what are the persistence semantics?

### Error Conditions
- Explicitly handled error cases (what causes them? what is returned?)
- Validation failure messages
- Retry or fallback behavior on external failures

### Test Files (highest signal for intent)
Read any test files in or near the domain paths. Test `describe` blocks and test case names often state requirements in plain language. Use them to:
- Verify your inferences about behavior
- Find edge cases you might have missed
- Understand the intended contract more precisely

---

## Generate `openspec/specs/<domain-name>/spec.md`

Create the spec file with this structure:

```markdown
# <Domain Label> Specification

## Purpose
<2–3 paragraphs describing what this capability does and why it exists.
Write from a business perspective: who uses it, what problem it solves, what value it delivers.
Do NOT describe classes, databases, or implementation technology.>

## Scope

**In scope:**
- <Bullet list of what IS covered by this spec>

**Out of scope:**
- <Bullet list of what is explicitly NOT covered — helps set boundaries>

## Requirements

### Requirement: <Behavior Name>
The system SHALL|MUST|SHOULD <observable behavior statement written from outside the system>.

> Rationale: <optional — why this requirement exists, if non-obvious>

#### Scenario: <Happy path scenario name>
- GIVEN <precondition — system or user context that must be true>
- WHEN <trigger — the user action or system event that initiates the behavior>
- THEN <primary outcome — what the user or calling system observes>
- AND <secondary outcome, if applicable>

#### Scenario: <Error or edge case scenario name>
- GIVEN <precondition>
- WHEN <trigger>
- THEN <outcome>

[Repeat ### Requirement blocks for each distinct, observable behavior]
```

---

## RFC 2119 Keywords — When to Use Each

| Keyword | Meaning | Use when |
|---|---|---|
| **SHALL / MUST** | Absolute requirement | The system always does this without exception |
| **SHALL NOT / MUST NOT** | Absolute prohibition | The system never does this |
| **SHOULD** | Strong recommendation | The system usually does this; rare justified exceptions exist |
| **MAY** | Optional | The system might do this, but is not required to |

---

## Requirements Quality Rules

Each requirement must pass these checks before it belongs in the spec:

1. **Testable** — could a developer write an automated test from the scenario? If not, the scenario is too vague.
2. **Observable from outside** — does it describe behavior a user, API caller, or downstream system can observe? Internal implementation details (class names, function names, library choices, DB schema) belong in `design.md`, not `spec.md`.
3. **One behavior per requirement** — split compound behaviors into separate requirements.
4. **Covers failure cases** — every significant requirement should have at least one error or edge case scenario.

---

## Handling Uncertainty

When you infer a behavior from code but are not certain about the intended business rule, add:
```markdown
<!-- TODO(EM-REVIEW): Inferred from [file/line]. Confirm: is the intended rule "[your inference]"?
     Alternative interpretation: "[other possibility]" -->
```

When code clearly does something but you cannot determine WHAT business need it serves:
```markdown
<!-- TODO(EM-REVIEW): [file/function] performs [technical action] but the business scenario
     it serves is unclear. Please add context or correct this requirement. -->
```

When a behavior is present in some code paths but appears inconsistent:
```markdown
<!-- TODO(EM-REVIEW): Inconsistent behavior found — [describe the inconsistency].
     Clarify the intended rule. -->
```

---

## After Creating the Spec

Print this summary:

```
Spec created: openspec/specs/<name>/spec.md

Requirements documented:  N
Scenarios documented:     M  (happy paths: X, error/edge cases: Y)
TODO(EM-REVIEW) comments: K  ← these need your attention

Suggested actions:
  1. Open openspec/specs/<name>/spec.md and review each requirement
  2. Resolve all TODO(EM-REVIEW) comments
  3. Run /opsx-reverse-nfr to add non-functional requirements for this domain
  4. Once satisfied, commit the spec to source control
```
