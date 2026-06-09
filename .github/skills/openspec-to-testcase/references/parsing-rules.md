# Parsing Rules — Reading spec.md Files

## Requirement block detection

A requirement block starts with a level-3 heading matching:
```
### Requirement: <Title>
```
And MUST contain a blockquote ID line immediately after:
```
> `REQ-<AREA>-<NNN>`
```

Everything between this heading and the next `### Requirement:` or `##` heading
belongs to this requirement (body text, notes, lists, sub-requirements).

### Example — simple requirement
```markdown
### Requirement: Project Capability or Domain — Multiple Files
> `REQ-DOMN1-001`

The system SHALL allow the user to download one or more files in a single request.
```

### Example — requirement with back-links (already has TCs)
```markdown
### Requirement: East Asian Language files Support
> `REQ-DOMN1-003` <!-- TC-DOMN1-007-P TC-DOMN1-008-P TC-DOMN1-009-N -->

The system SHALL support the following East Asian language files:
- Noto Sans JP
- Noto Serif CJK SC
- Source Han Sans KR
- MS Gothic
```
Back-links in `<!-- ... -->` mean TCs already exist — read them, don't regenerate those IDs.

---

## Sub-item extraction (auto-expand rule)

When a requirement body contains a **bulleted or numbered list of named items**,
treat each item as a distinct test subject requiring its own TC set.

### Signals that a list = expandable sub-items:
- Items are proper nouns (folder names, file names, error codes, device models)
- Items are distinct values of the same type (not steps in a sequence)
- The requirement body says "the following", "including", "SHALL support:"

### Signals that a list is NOT expandable:
- Items are procedural steps ("1. Open dialog, 2. Click install…")
- Items are conditions/constraints on a single behaviour
- Items describe how something works, not what values are valid

### Expansion example
Requirement body:
```
The system SHALL support the following East Asian language files:
- Noto Sans JP
- Noto Serif CJK SC
- Source Han Sans KR
- MS Gothic
```
→ Generate one positive TC per file type (4 TCs), plus shared negatives (corrupt file,
no network, disk full) that apply to the whole requirement (not per-file).

---

## Notes and scenarios

Blocks matching any of these patterns carry important context — include in TC description/preconditions:
```
> **Note:** ...
> **Scenario:** ...
> **Warning:** ...
> **Constraint:** ...
```

---

## Capability name derivation

1. Use the `# Title` heading in spec.md if present
2. Else titlecase the folder name: `domain-or-capability-1` → `Project Capability or Domain`

## Incremental scope path parsing (git diff mode)

When incremental update mode is requested, derive capabilities from changed spec paths only.

- Accepted path pattern: `openspec/specs/<capability>/spec.md`
- Extracted capability token: `<capability>`
- Ignore non-spec files and paths outside `openspec/specs/*/spec.md`

Examples:
- `openspec/specs/print-feature-settings/spec.md` → `print-feature-settings`
- `openspec/specs/xpse-configuration/spec.md` → `xpse-configuration`

---

## Shall / should / may interpretation

| Modal | Test obligation |
|---|---|
| SHALL / MUST | Mandatory — always generate P + N |
| SHOULD | Recommended — generate P + N, mark N as Medium priority |
| MAY | Optional — generate P only, mark as Low priority; N at discretion |

---

## What to skip

- `## Background` / `## Context` / `## Rationale` sections — no TCs
- `## Future Enhancements` — no TCs
- `## Revision History` — no TCs
- `## Appendix` sections — no TCs
- Developer-facing Notes (e.g., "Note: implement using libfiles") — not a test condition
- Any heading below `### Requirement:` that is a sub-heading of the requirement body
  (these are clarifications, not separate requirements)

---

## Empty / stub spec handling

A spec.md is considered a **stub** if it contains no `### Requirement:` blocks after parsing.
This happens with freshly scaffolded brownfield specs that haven't been authored yet.

**Do not** generate an empty `test-cases.md` for a stub spec — an empty file creates false completeness signals in the RTM.

**Required action when a stub is detected:**
1. Skip TC generation for that capability.
2. Report to the user: `"Skipped <capability>: spec.md contains no requirements yet (stub)."` 
3. Do NOT add a row for this capability in `tests/rtm.md` — absence of a row is correct until the spec is authored.
4. If the capability appears in a global file from a prior run, leave its existing rows untouched.

---

## REQ ID integrity rules

- Never invent or modify a REQ ID — use exactly what is in the spec
- If two requirements share the same REQ ID (authoring error), flag it to the user before proceeding
- If a REQ ID is missing from a `### Requirement:` block, flag it — do not generate TCs for unnamed requirements
