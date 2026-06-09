# TC Generation Rules

## Core principle

Think like a tester, not a spec transcriber. The spec says *what* the system shall do.
Your job is to think: "What are all the ways this can succeed, fail, or behave unexpectedly?"

A useful mental model: each requirement is a lock. A positive TC is the correct key.
A negative TC is a wrong key (wrong shape, broken, missing). An edge TC is a key that
technically fits but tests the limits of the mechanism.

---

## Positive cases (suffix -P)

### One TC per named sub-item (auto-expand rule)
If the requirement lists specific named values (files, formats, device models, etc.),
generate one positive TC per item. They share the same structure but differ in test data.

### One TC for the happy path (non-enumerable requirements)
If the requirement describes a single behaviour with no enumerable sub-items,
one positive TC covers the happy path.

### Additional positive TCs to always consider
- **Idempotency**: Does doing it twice produce the same result without error?
- **Batch/multiple**: Does it work when applied to multiple items at once?
- **Post-action state**: Is the system in the correct state after the action completes?
- **Visual/output verification**: For rendering requirements, always add a TC that
  verifies the output looks correct (not just that no error was thrown).

---

## Negative cases (suffix -N)

Generate at minimum one TC per failure mode implied by the requirement.

### Standard negative cases to always consider
| Failure mode | Example |
|---|---|
| Missing dependency | Network unavailable, device not connected |
| Invalid / corrupt input | Corrupted file, wrong format, unsupported value |
| Resource exhaustion | Disk full, memory limit, timeout |
| Permission / auth failure | Insufficient rights, locked resource |
| Partial failure | Multi-item operation where one item fails |
| Interrupted operation | Connection dropped mid-transfer |
| Duplicate / already-exists | Installing something already installed (if not idempotent) |
| Out-of-scope input | Value outside the spec's defined set |

### Negative TCs for auto-expanded requirements
Negatives are **shared** across sub-items unless the failure mode is item-specific.
- One "no network" TC covers all files — do not repeat it per file.
- One "corrupt file" TC per requirement (use first file as test data).
- BUT: if a specific file has a known unique failure mode, create a dedicated TC.

---

## Edge cases (suffix -E)

Edge cases test boundary conditions. Generate when:
- The requirement specifies device variants with different constraints (e.g., Low-End controller)
- Concurrency is plausible (two operations at the same time)
- Large volume / high count is a realistic scenario
- Empty set is a valid input (zero files selected, empty list)
- Sequence matters (install → uninstall → reinstall)

---

## TC fields — how to fill each one

### TC ID
Format: `TC-<AREA>-<NNN>-<P|N|E>`
Number sequentially within the capability. Never skip or reuse numbers.

### REQ ID(s)
The REQ ID this TC validates. A single TC can reference multiple REQ IDs if it
genuinely validates more than one requirement (rare — prefer separate TCs).

### Test Case Name
- Verb-first, specific: "Install Noto Sans JP — successful download and install"
- Include the sub-item name for expanded TCs: "Render Noto Serif CJK SC glyphs — correct output"
- Include the failure mode for negatives: "Install files — network unavailable"
- Max ~80 characters

### Description
One or two sentences. Answers: what scenario does this cover, and why does it matter?

### Type
`P`, `N`, or `E` — one letter only.

### Preconditions
State the system must be in BEFORE this TC runs:
- Device connection state
- Which software/files are already installed (or not)
- Network state
- Any required test fixtures or harness setup

### Steps to Test
Numbered, atomic, human-executable steps. Each step is one discrete action.
Do not combine "click X and observe Y" — split into two steps.
If automated, describe what the test harness does.

### Test Data
Specific values: exact folder names, file paths, input strings, character sequences.
For files TCs always include a sample string in the target language.
Example: `String: こんにちは世界` / `File: Noto Sans JP` / `Size: 12pt`

### Expected Result
Precise and verifiable. Not "works correctly." Not "no errors."
- ✅ "file status changes to 'Installed'. File appears in installed files list. No error dialogs."
- ❌ "file installs correctly."

For visual TCs: "All [N] glyphs render correctly. No tofu (□) placeholders. No substitution."
For negative TCs: always specify the exact error message or state expected.

### Actual Result
Leave blank — filled at execution time.

### Status
Default: `Not Run`

### Automation
- `Manual` — visual inspection required, or no automation harness exists
- `Automated` — can be fully automated via API / test harness
- `Both` — regression suite covers it AND manual sign-off required

### Notes / Defect
Leave blank unless there is a known dependency, harness requirement, or workaround.
Example: "Requires test harness network injection endpoint" or "Visual inspection only."

---

## Priority assignment

Derive from the requirement's modal and the failure severity:

| Situation | Priority |
|---|---|
| SHALL requirement, positive TC | High |
| SHALL requirement, negative TC | High |
| SHOULD requirement | Medium |
| MAY requirement | Low |
| Edge case on SHALL | Medium |
| Visual/rendering verification | High (regression risk) |

---

## What NOT to generate

- TCs for implementation details ("Verify the file is stored in /usr/share/files")
- TCs for developer-facing notes that aren't user-visible behaviours
- Duplicate TCs for the same scenario under different names
- TCs for requirements marked as Future Enhancements or archived

---

## Coverage computation — how to derive RTM coverage per REQ

After generating all TCs for a capability (or when re-reading existing test-cases.md files for RTM updates), compute coverage for each REQ ID using this algorithm:

1. Collect all TC IDs that reference a given REQ ID in their `REQ ID(s)` field across all test-cases.md files in scope.
2. Check the suffix of each TC ID:
   - Does at least one TC end in `-P`? → has positive coverage
   - Does at least one TC end in `-N`? → has negative coverage
3. Assign the coverage value:

| Positive TCs | Negative TCs | Coverage |
|---|---|---|
| ✅ at least one | ✅ at least one | **Full** |
| ✅ at least one | ❌ none | **Partial** |
| ❌ none | ✅ at least one | **Partial** |
| ❌ none | ❌ none | **None** |

4. Edge TCs (`-E`) do **not** affect the coverage classification on their own — they are supplemental.
5. Record the result in:
   - The `<!-- req-coverage -->` comment at the top of the relevant test-cases.md
   - The `Coverage` column of the Traceability Table in `tests/rtm.md`
   - The RTM YAML frontmatter summary counts (`coverage-full`, `coverage-partial`, `coverage-none`)

> Run this algorithm **after** all TC generation for the scope is complete, not incrementally per requirement — a later requirement may add a `-N` TC that changes the coverage of an earlier REQ.
