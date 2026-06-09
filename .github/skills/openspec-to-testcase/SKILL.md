---
name: openspec-to-testcase
description: >
  Use this skill whenever the user wants to generate test plans, test cases, or a
  requirements traceability matrix (RTM) from OpenSpec spec.md files. Triggers include:
  "generate test cases from spec", "create test plan from openspec", "build RTM from
  requirements", "update test cases for capability", "generate tests for [feature/capability]",
  "create traceability matrix", "my spec changed update the tests", or any request to go
  from OpenSpec requirements to test documentation. Also triggers when the user wants to
  convert existing test markdown files into an Excel (.xlsx) workbook for test execution.
  Always use this skill — do not attempt to wing it — when spec.md files with REQ- IDs
  are involved and the output is test documentation.
---

# OpenSpec → Test Case Skill

Reads `openspec/specs/<capability>/spec.md` files, understands requirements, and produces
three markdown files per the project's "Test Management as Code" approach:

```
openspec/
  specs/
    Domain-or-Capability-1/spec.md
    Domain-or-Capability-2/spec.md
    ...

tests/
  test-plan.md              ← one global file
  rtm.md                    ← one global file
  Domain-or-Capability-1/
    test-cases.md           ← per capability
  Domain-or-Capability-2/
    test-cases.md
  ...
```

> **Path convention:** Spec files always live under `openspec/specs/*/spec.md`. Output test files live under `tests/` at the repo root.

**Source of truth = markdown in repo. XLSX = generated execution artifact.**

---

## Workflow

### Phase 1 — Understand the request scope

Determine what the user wants:

| Request | Action |
|---|---|
| "generate tests for Domain-or-Capability-1" | Process ONE capability only |
| "generate tests for all specs" | Process ALL `openspec/specs/*/spec.md` files |
| "update tests for Domain-or-Capability-1" | Re-read that spec, regenerate that folder only |
| "update tests for pending spec changes" | Auto-detect changed spec files from uncommitted/staged diffs and process ONLY those capabilities |
| "update tests for last commit spec changes" | Auto-detect changed spec files from `HEAD~1..HEAD` and process ONLY those capabilities |
| "generate the xlsx" | Read all `tests/` md files → produce xlsx (see Phase 5) |
| "update rtm" | Re-read all test-cases.md files → regenerate tests/rtm.md |

Ask the user to confirm scope if ambiguous.

### Phase 1b — Incremental scope detection (git diff mode)

Use this phase only when the user explicitly requests pending-change or last-commit mode.

1. Determine diff basis:
  - Pending mode: include staged and unstaged changes under `openspec/specs/*/spec.md`
  - Last-commit mode: diff `HEAD~1..HEAD` under `openspec/specs/*/spec.md`
2. Extract capability folder names from changed paths.
3. Present detected capability list and ask for confirmation before generation.
4. If no changed spec files are detected, return a no-op message and do not regenerate tests.

---

### Phase 2 — Parse spec.md

For each capability spec, extract:

1. **Capability name** — from the folder name and/or the `# Title` heading
2. **Requirements** — blocks matching the pattern:
   ```markdown
   ### Requirement: <Title>
   > `REQ-<AREA>-<NNN>`
   <body text>
   ```
3. **User scenarios / Notes** — any `> **Note:**` or `**Scenario:**` blocks following a requirement
4. **Enumerated sub-items** — bulleted/numbered lists within a requirement body that name specific values (capability, file types, models, error codes). **Each distinct sub-item = a separate TC expansion.**
5. **Existing TC back-links** — `<!-- TC-... -->` comments in the REQ block (use to avoid duplicating already-authored TCs)

> **Read the parsing rules reference before processing any spec:**
> `references/parsing-rules.md`

> **Stub spec handling:** If a spec.md contains no `### Requirement:` blocks, it is an unfinished stub — skip it, do not create an empty test-cases.md, and report it to the user. See `references/parsing-rules.md` § Empty / stub spec handling for the full procedure.

---

### Phase 3 — Generate `tests/<capability>/test-cases.md`

For each requirement, generate:
- **Positive cases (P):** One TC per named sub-item if enumerable (e.g., each capability, each file type, each capability model). If not enumerable, one TC for the happy path.
- **Negative cases (N):** At minimum — invalid input, missing dependency, permission/resource failure. Add more based on spec text.
- **Edge cases (E):** Boundary values, empty sets, concurrency, low-resource variants.

> **Read the TC generation rules before writing any test cases:**
> `references/tc-generation-rules.md`

> **Read the markdown output format spec before writing files:**
> `references/output-formats.md`

After generating, **write back-links into the spec file** — this is required, not optional. Add `<!-- TC-DOMN1-001-P TC-DOMN1-001-N -->` (space-separated) into the `> \`REQ-...\`` line in spec.md for each requirement processed. Back-links are the mechanism that prevents duplicate TC generation in future incremental runs; they have no value if not written.

> If the spec file cannot be written (e.g., read-only in CI), explicitly tell the user the back-links that need to be added and the exact lines to insert them on.

---

### Phase 4 — Generate `tests/test-plan.md` and `tests/rtm.md`

- **test-plan.md**: Global file. Use full regeneration for full-scope runs, and merge-safe updates for subset runs. Read `references/output-formats.md` for the required structure.
- **rtm.md**: Global file. Collects ALL REQ IDs × TC IDs across all capabilities. Use full regeneration for full-scope runs, and merge-safe updates for subset runs. Read `references/output-formats.md` for the grid format.

#### Subset update — required sequence of operations

When updating a subset of capabilities (single capability or incremental git-diff scope), follow this sequence **in order**:

1. **Read** the existing `tests/test-plan.md` and `tests/rtm.md` in full. Extract and hold in memory all rows that belong to capabilities **outside** the current update scope — these must be preserved verbatim.
2. **Confirm** all TC IDs from Phase 3 are available before writing any global file.
3. **Compute coverage** for each REQ in the changed capabilities by scanning the newly generated `test-cases.md` files: a REQ has **Full** coverage if at least one `-P` and one `-N` TC reference it; **Partial** if only one type is present; **None** if no TCs reference it.
4. **Merge**: replace/add rows for changed capabilities only; keep all preserved rows from step 1 unchanged.
5. **Recompute** all global summary metrics (total requirements, total TCs, coverage counts) from the merged result.
6. **Write** both global files in a single pass with the merged + recomputed content.

> Do NOT write global files before step 2 completes — doing so will produce RTM rows with missing or wrong TC IDs.
> Do NOT delete coverage rows for capabilities outside the current update scope (step 1 preservation is mandatory).

---

### Phase 5 — XLSX generation (on demand)

When the user says "generate the xlsx" or "create the Excel file for testing":

1. Resolve the script path. The script ships with this skill at:
   ```
   <skill-dir>/scripts/md_to_xlsx.py
   ```
   where `<skill-dir>` is the directory containing this SKILL.md file (typically `.github/skills/openspec-to-testcase/`). Use the **absolute path** when invoking it from the target repository.

2. Derive the project name (`<ProjectName>`) from the `project:` field in `tests/test-plan.md` frontmatter. If that field is absent, use the repository folder name in TitleCase. Do **not** leave the placeholder as-is.

3. Run the generation script from the **repo root**:
   ```bash
   python <absolute-path-to-skill>/scripts/md_to_xlsx.py \
     --tests-dir tests/ \
     --output <ProjectName>_Tests_$(date +%Y%m%d).xlsx
   ```
4. The script reads all `tests/` markdown files and produces a workbook with four sheets: README, Test_Plan, Test_Cases, RTM.
5. Tell the user the output file path so they can open or download it.

> **Prerequisite:** `pip install openpyxl pyyaml` must be run in the environment before invoking the script.

---

## ID Conventions

```
REQ-<AREA>-<NNN>    e.g.  REQ-DOMN1-001   (from spec.md — never change)
TC-<AREA>-<NNN>-P   e.g.  TC-DOMN1-001-P  (positive)
TC-<AREA>-<NNN>-N   e.g.  TC-DOMN1-001-N  (negative)
TC-<AREA>-<NNN>-E   e.g.  TC-DOMN1-001-E  (edge)
```

**Area codes** — derive from the capability folder name:
| Folder | Area code |
|---|---|
| Domain-or-Capability-1 | DOMN1 |
| Domain-or-Capability-2 | DOMN2 |
| Domain-or-Capability-3 | DOMN3 |
| Domain-or-Capability-4 | DOMN4 |
| installation | INSTALL |
| network | NET |
| ui / interface | UI |
| performance | PERF |
| security | SEC |

If the folder doesn't match above, use the first 4–6 uppercase letters of the folder name.

**TC numbering**: Within a capability, number TCs sequentially from 001 regardless of REQ number. So REQ-DOMN1-003 might generate TC-DOMN1-007-P through TC-DOMN1-014-E if earlier requirements generated TCs 001–006.

**Never reuse or renumber** existing IDs. Only append new ones.

---

## Quality gates — check before delivering output

- [ ] Every REQ in the spec has at least one P and one N test case
- [ ] All enumerable sub-items in a requirement have their own TC
- [ ] TC IDs in test-cases.md match what's referenced in rtm.md exactly
- [ ] RTM coverage column is computed correctly per the algorithm in `references/tc-generation-rules.md` (Full = P+N, Partial = P only or N only, None = no TCs)
- [ ] RTM YAML frontmatter summary counts match the actual coverage data in the Traceability Table
- [ ] No TC references a REQ ID that doesn't exist in any spec.md
- [ ] test-plan.md lists all capabilities in scope
- [ ] In subset updates, test-plan.md and rtm.md still contain unchanged capability rows
- [ ] Back-links written into spec.md (or user explicitly notified of lines to add if file is read-only)

## Incremental update prompts (operator patterns)

- Pending mode:
  - "Update tests for pending spec changes. Detect changed specs from uncommitted/staged diffs, confirm scope, then update only those capability test-cases plus global test-plan and RTM."
- Last-commit mode:
  - "Update tests for last commit spec changes. Detect changed specs from `HEAD~1..HEAD`, confirm scope, then update only those capability test-cases plus global test-plan and RTM."

---

## Reference files

| File | Read when |
|---|---|
| `references/parsing-rules.md` | Processing any spec.md |
| `references/tc-generation-rules.md` | Writing test cases |
| `references/output-formats.md` | Writing any markdown output file |
| `scripts/md_to_xlsx.py` | Generating xlsx (run it, don't read it) |
