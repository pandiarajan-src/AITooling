# GitHub Copilot Instructions

This repository uses **OpenSpec** for spec-driven development. Business capability specifications
live in `openspec/specs/<domain>/spec.md`. Consult `domain-map.yaml` at the repository root
to understand which code paths belong to which business domain.

<!-- TODO(EM): Replace the section below with a brief description of this repository -->
## Repository Context

This is a brownfield mono-repository containing multiple projects, components, or services.
Capability domains have been identified and are mapped in `domain-map.yaml`.
Specifications describe observable system behavior using OpenSpec format (RFC 2119 keywords + BDD scenarios).

---

## OpenSpec Workflow

### Everyday development (for each new feature, fix, or change)

```
/opsx:propose <feature-name>   →   agree on specs before writing any code
/opsx:apply                    →   implement the tasks from tasks.md
/opsx:archive                  →   merge spec deltas into the source-of-truth specs
```

Each change lives in `openspec/changes/<name>/` with:
- `proposal.md` — why and what
- `specs/` — delta specs showing ADDED / MODIFIED / REMOVED requirements
- `design.md` — how (technical approach)
- `tasks.md` — implementation checklist

### Brownfield spec discovery (run once per domain, when no specs exist yet)

| Step | Command | What it does |
|---|---|---|
| 1 | `/opsx-discover-capabilities` | Scans the entire codebase, infers business domains, creates `domain-map.yaml` |
| 2 | Review `domain-map.yaml` | EM confirms the domain groupings are correct |
| 3 | `/opsx-onboard-domain` | Generates a functional `spec.md` for one domain — run once per domain, one Copilot session per domain |
| 4 | `/opsx-reverse-nfr` | Generates NFR requirements from code patterns for one domain |
| 5 | EM review | Fill `[PLACEHOLDER]` values with real SLA targets; resolve `TODO(EM-REVIEW)` comments |

---

## Spec Writing Standards

When you write, update, or review any spec file:

**Language:**
- Use **SHALL / MUST** for absolute requirements (no exceptions)
- Use **SHALL NOT / MUST NOT** for absolute prohibitions
- Use **SHOULD** for strong recommendations (rare justified exceptions possible)
- Use **MAY** for optional behavior

**Content rules:**
- Requirements describe **externally observable behavior** — what a user, API caller, or downstream system can observe
- Scenarios must be **testable** — a developer should be able to write an automated test from each GIVEN/WHEN/THEN
- **Do NOT** put class names, function names, library choices, or database table names in `spec.md` — those belong in `design.md`
- **Do NOT** describe implementation steps — specs describe outcomes, not procedures

**Uncertainty markers:**
- Add `<!-- TODO(EM-REVIEW): ... -->` when inferring behavior you are not certain about
- Explain what was inferred and what the alternative interpretation might be

---

## Code Review Guidance

When reviewing a pull request:

1. **Check for spec impact** — does this code change alter any externally observable behavior?
2. If yes, a `openspec/changes/<name>/specs/` delta spec should exist for this change
3. A change that modifies behavior without a spec update is incomplete
4. Spec changes in `changes/<name>/specs/` should match the code changes in scope — no broader, no narrower

---

## Domain Reference

See `domain-map.yaml` for:
- All business capability domains and their descriptions
- Which code paths belong to each domain
- NFR signals detected per domain
- Cross-cutting concerns (logging, error handling, config, shared libraries)

If `domain-map.yaml` does not exist yet, run `/opsx-discover-capabilities` in Copilot Chat.
