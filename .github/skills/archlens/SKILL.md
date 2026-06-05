---
name: archlens
description: "Engineer-grade architecture documentation skill. Use when: analyze architecture, document codebase, create ARCHITECTURE.md, architecture overview, reverse-engineer design, understand system structure, update architecture docs, detect tech stack, trace data flow, document components, onboard engineers, architecture audit, architecture diff, brownfield analysis, ArchLens."
argument-hint: "Optional: path to target repo (defaults to current workspace root)"
---

# ArchLens

Reads a codebase and produces a precise, engineer-grade architecture document. Traces actual structure, flows, and decisions evidenced in code — never infers or hallucinate. Supports two modes: full initial analysis or incremental update with changelog.

## When to Use

- "Run ArchLens on this repo"
- "Document the architecture"
- "Update the architecture doc"
- "Create ARCHITECTURE.md"
- "Analyze the codebase structure and flows"
- "Diff the architecture against the code"

## Output

Writes a single file: `docs/ARCHITECTURE{mmddyyyy}.md` (today's date, e.g. `docs/ARCHITECTURE06052026.md`).

---

## Phase 0 — Mode Detection

Before any analysis, determine the operating mode.

### Step 0.1 — Find prior architecture doc

Search `docs/` for any file matching `ARCHITECTURE*.md`.

- **INITIAL MODE** — no such file exists → proceed to Phase 1 with a full analysis.
- **UPDATE MODE** — one or more files exist → take the most recent one and continue with Steps 0.2–0.3 before Phase 1.

### Step 0.2 — Parse the prior document (UPDATE MODE)

Run [`archlens_parse.py`](./scripts/archlens_parse.py) to extract the prior doc's sections as structured JSON:

```bash
python .github/skills/archlens/scripts/archlens_parse.py \
  docs/<prior_ARCHITECTURE_file>.md \
  --output /tmp/archlens_prior_sections.json
```

Load `/tmp/archlens_prior_sections.json`. This tells you exactly what was documented in each section last time, so you only re-analyse what may have changed.

Key fields to read:
- `sections[].heading` + `sections[].content` — prior section text
- `sections[].flags.has_warnings` — sections that had unresolved `⚠️` items
- `changelog_entries` — dates of previous runs
- `open_questions` — carry-forward items unless resolved

### Step 0.3 — Diff repo state against prior snapshot (UPDATE MODE)

Check if a snapshot file exists alongside the prior architecture doc (e.g. `docs/archlens_snapshot.json`).

**If the snapshot exists**, run a diff:

```bash
python .github/skills/archlens/scripts/archlens_snapshot.py <repo_path> \
  --compare docs/archlens_snapshot.json \
  --output /tmp/archlens_current_snapshot.json
```

The diff (printed to stdout as JSON) tells you:
- `added` — new files since last run
- `removed` — deleted files since last run
- `modified` — changed files since last run (size or mtime)
- `dep_changes` — dependency version changes
- `summary` — human-readable change count

Focus deep analysis only on components that own modified/added/removed files. Unchanged areas carry forward from the prior doc verbatim.

**If no snapshot exists** (first time UPDATE MODE runs with a pre-existing doc), generate one now and perform a full re-analysis:

```bash
python .github/skills/archlens/scripts/archlens_snapshot.py <repo_path> \
  --output /tmp/archlens_current_snapshot.json
```

Record the detected mode and change scope; they control which sections to rewrite and whether to append the changelog.

---

## Phase 1 — Tech Stack Resolution

> Do not proceed to analysis until this phase is complete.

1. Check if `stack.json` exists at the repo root.
2. **If YES** — load it; treat it as the authoritative tech stack reference.
3. **If NO** — invoke the `detect-stack` skill:
   ```bash
   python .github/skills/detect-stack/detect_stack.py "<repo_path>" --output stack.json
   ```
   Parse the generated `stack.json`. Key fields: `languages`, `frameworks`, `build_tools`, `test_frameworks`, `summary`.

---

## Phase 2 — Repository Discovery

### Step 2.1 — Read root context files (in parallel)

| File / Pattern | Purpose |
|---|---|
| `README.md`, `README.rst` | Project goals, overview, usage |
| `CLAUDE.md`, `AGENTS.md`, `copilot-instructions.md` | Agent/developer context |
| `pyproject.toml`, `package.json`, `*.csproj`, `go.mod`, `Cargo.toml` | Dependencies and version pins |
| `Makefile`, `Taskfile.yml`, `justfile`, `scripts/` | Build recipes and helper scripts |
| `.github/workflows/*.yml` | CI/CD pipeline definitions |
| `config.md`, `*.config.*`, `*.env.example`, `.env.example` | Configuration shape and env vars |
| `docker-compose.yml`, `Dockerfile`, `*.tf`, `*.bicep` | Deployment topology |

### Step 2.2 — Map directory structure

List the top 2–3 directory levels with `list_dir`. For each top-level folder, note its inferred role. Do not assume layout.

---

## Phase 3 — Deep Analysis

### Step 3.1 — Component inventory (→ Section 4)

For each significant source module, package, or directory:
1. Read its entrypoint (`main.*`, `__init__.*`, `index.*`, `app.*`, `Program.*`).
2. Identify its **responsibility** (one sentence).
3. Identify its **public interface** (exported functions, classes, CLI commands, API routes).
4. Identify its **dependencies** (imports, calls, external services).

Build the map: `component → responsibility → dependencies → consumers`.

Annotation rules:
- Ambiguous or unclear findings → `⚠️ Requires verification`
- Dead code, orphaned modules, unused deps → `🗑️ Possibly unused`

### Step 3.2 — Data flow analysis (→ Section 5)

Trace the primary happy path end-to-end for the 1–2 most critical flows:
- **CLI**: arg parsing → validation → core logic → outputs (files, stdout, API)
- **API**: ingress → routing → handler → service → data store → response
- **Pipeline**: source → transform stages → sink

Capture branching paths (error paths, alternate modes) where evidenced.

### Step 3.3 — Build, run & environment (→ Section 6)

From config files and scripts, extract exact commands for:
- Installing dependencies
- Running the project / starting a dev server
- Running tests
- Building / packaging for release
- Required env vars (names only, no values; flag required vs optional)

### Step 3.4 — Design patterns & conventions (→ Section 7)

Identify:
- **Structural patterns**: layered architecture, event-driven, CQRS, MVC, hexagonal, plugin, etc.
- **Code conventions**: naming styles, file organization, error handling patterns
- **Constraints**: language version pins, required external tools, platform restrictions

### Step 3.5 — Dependencies & environment (→ Section 8)

From lockfiles / manifests:
- Group runtime dependencies: core / dev / optional
- Minimum runtime/platform requirements (Node version, Python version, etc.)
- External service dependencies (DBs, queues, auth providers, third-party APIs)

---

## Phase 4 — Write `docs/ARCHITECTURE{mmddyyyy}.md`

### Step 4.1 — Ensure `docs/` directory exists

Create it if absent before writing.

### Step 4.2 — Document structure

Produce the file in this exact section order:

```
## 1. Project Overview
## 2. Tech Stack
## 3. Repository Structure
## 4. Architecture
## 5. Data Flow
## 6. Build, Run & Scripts
## 7. Design Patterns & Conventions
## 8. Dependencies & Environment
## 9. Changelog            ← UPDATE MODE only
## 10. Open Questions
```

#### Section writing rules

**§1 Project Overview**
- Purpose and primary goal (one paragraph max)
- Target users / consumers of this system
- Scope boundaries: what this repo does and does not own

**§2 Tech Stack**
- Core languages and runtimes (from `stack.json`)
- Key frameworks and libraries with versions if detectable
- External APIs and third-party services
- Dev tooling: linters, formatters, test runners, CI

**§3 Repository Structure**
- Annotated directory tree (top 2–3 levels, use code block)
- One-line role description per top-level folder

**§4 Architecture**
- Component inventory table: `| Component | Responsibility | Interface | Consumers |`
- Inter-component interaction diagram (Mermaid `flowchart TD` or `graph LR`)
- Third-party integration points
- Deployment topology if infra config is present

**§5 Data Flow**
- Key data flows in prose (entry → processing → persistence → response)
- Mermaid `sequenceDiagram` for the 1–2 most critical flows
- Data models: schema or shape only (not full ORM definitions)

**§6 Build, Run & Scripts**
- Commands as verbatim code blocks, copied from config files
- Table of key scripts: `| Script | Purpose |`
- Env vars table: `| Variable | Required | Description |`

**§7 Design Patterns & Conventions**
- Architectural patterns in use
- Observed code conventions (naming, structure, error handling)
- Known constraints and hard limitations

**§8 Dependencies & Environment**
- Grouped dependency table: `| Package | Group | Version | Purpose |`
- Minimum runtime / platform requirements
- External service dependencies

**§9 Changelog** *(UPDATE MODE only)*
```markdown
## Changelog
### {mmddyyyy} — Updated by ArchLens
- [Changed] ...
- [Added] ...
- [Removed] ...
- [Flagged] ...
```

**§10 Open Questions**
- Bullet list of unresolved ambiguities requiring human review
- Include all `⚠️ Requires verification` items surfaced during analysis

### Step 4.3 — Save snapshot alongside the document (both modes)

After the document is written, persist the current repo snapshot so future UPDATE MODE runs can diff against it:

```bash
python .github/skills/archlens/scripts/archlens_snapshot.py <repo_path> \
  --output docs/archlens_snapshot.json
```

If a snapshot from a previous run is at `/tmp/archlens_current_snapshot.json`, copy it rather than regenerating:
```bash
cp /tmp/archlens_current_snapshot.json docs/archlens_snapshot.json
```

### Step 4.4 — Output rules (enforce strictly)

- Output is a **single Markdown file only**. No console output, no JSON, no split files.
- Use Mermaid syntax for all diagrams (`flowchart TD` or `sequenceDiagram`).
- All section headings use `##` and `###`. No custom HTML.
- Be terse and precise — engineer audience, no marketing language.
- **Do not document what you cannot evidence.** Flag gaps explicitly with `⚠️`.
- **UPDATE MODE**: preserve all prior content; only mutate sections where changes are detected; always append changelog entry.

---

## Quality Checklist

Before saving the file, verify:

- [ ] Mode correctly detected (INITIAL or UPDATE)
- [ ] In UPDATE MODE: `archlens_parse.py` was run and prior sections loaded
- [ ] In UPDATE MODE: snapshot diff run (if prior snapshot existed); only changed components re-analysed
- [ ] `docs/archlens_snapshot.json` written after document is saved
- [ ] Tech stack sourced from `stack.json`, not guessed
- [ ] All 10 sections present and non-empty (§9 only in UPDATE MODE)
- [ ] Every component has a stated responsibility
- [ ] At least one complete end-to-end data flow documented with a Mermaid diagram
- [ ] Build/run commands are verbatim from config files
- [ ] All `⚠️ Requires verification` and `🗑️ Possibly unused` flags resolved or listed in §10
- [ ] No `TODO`, `TBD`, or placeholder text
- [ ] File saved to `docs/ARCHITECTURE{mmddyyyy}.md` with today's date
