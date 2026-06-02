---
name: architecture-explainer
description: "Analyzes the current repository and generates a comprehensive architecture document saved to docs/ARCHITECTURE.md. Use when: explain architecture, document architecture, analyze repository, understand codebase, architecture overview, project structure, how does this project work, codebase documentation, onboarding documentation, technical overview, component responsibilities, data flow diagram, design patterns, build commands, high-level architecture."
argument-hint: "Optional: path to target repo (defaults to current workspace root)"
---

# Architecture Explainer

Explores the repository, analyzes its structure and code, then writes `docs/ARCHITECTURE.md` — a comprehensive architecture reference covering project goals, tech stack, components, data flows, build process, and design conventions.

## When to Use

- "Explain the architecture of this repo"
- "Document this codebase for onboarding"
- "Give me an architecture overview"
- "How does this project work?"
- "Create an ARCHITECTURE.md"
- "Analyze the repository structure"

## Output

Creates or overwrites `docs/ARCHITECTURE.md` with eight sections:

1. Project Overview & High-Level Goal
2. Tech Stack (core technologies, key APIs/frameworks, development tools)
3. Repository Structure
4. Architecture (components, responsibilities, interactions, third-party integrations)
5. Design Flow & Data Flow
6. Build Process, Commands & Scripts
7. Design Patterns, Conventions & Constraints
8. Summary

---

## Procedure

### Phase 1 — Discover the Repository

**Step 1.1 — Identify the target repository**

If an argument was provided, treat it as the repo root path. Otherwise use the current workspace root.

**Step 1.2 — Run the detect-stack skill**

Invoke the `detect-stack` skill to obtain structured tech stack data. This populates Section 2.

```bash
python .github/skills/detect-stack/detect_stack.py "<repo_path>" --output /tmp/arch_stack.json
```

Parse the JSON output. Key fields to extract: `languages`, `frameworks`, `build_tools`, `test_frameworks`, `summary`.

**Step 1.3 — Read key root files in parallel**

Read as many of the following as exist:

| File / Pattern | Purpose |
|----------------|---------|
| `README.md`, `README.rst` | Project overview, goals, usage |
| `CLAUDE.md`, `AGENTS.md`, `copilot-instructions.md` | Agent and developer context |
| `pyproject.toml`, `package.json`, `*.csproj`, `go.mod`, `Cargo.toml` | Dependencies and version pins |
| `Makefile`, `Taskfile.yml`, `justfile` | Build commands and recipes |
| `scripts/` directory | Custom helper scripts |
| `.github/workflows/*.yml` | CI/CD pipeline definitions |
| `config.md`, `*.config.*`, `*.env.example` | Configuration shape |

**Step 1.4 — Map repository structure**

List the top two directory levels. For each top-level folder note its inferred purpose. Use `list_dir` or equivalent — do not assume layout.

---

### Phase 2 — Deep Analysis

**Step 2.1 — Components & Responsibilities (→ Section 4)**

For each significant source module, package, or directory:

1. Read its entrypoint (`main.*`, `__init__.*`, `index.*`, `app.*`, `Program.*`)
2. Identify its **responsibility** — what it does in one sentence
3. Identify its **public interface** — exported classes, functions, CLI commands
4. Identify its **dependencies** — what it imports or calls

Build a mental map: `component → responsibility → dependencies → consumers`.

Look for:
- Entry-point files (CLI main functions, HTTP server bootstraps)
- Service/utility layers
- Configuration or DI wiring
- Shared helpers or cross-cutting concerns

**Step 2.2 — Design Flow & Data Flow (→ Section 5)**

Trace the primary happy path end-to-end:

- CLI: argument parsing → validation → core logic → outputs (files, stdout, API calls)
- API: request ingress → routing → handler → service → data store → response
- Pipeline: input source → transform stages → sink

Identify at least one complete flow. Capture any branching paths (error paths, alternate modes).

**Step 2.3 — Build Process (→ Section 6)**

From config files and scripts, document exact commands for:

- Installing dependencies
- Running the project / starting a dev server
- Running tests
- Building / packaging for release
- Any environment prerequisites (runtime versions, env vars, external services)

**Step 2.4 — Design Patterns & Conventions (→ Section 7)**

Identify:

- **Structural patterns**: layered architecture, plugin system, MVC, hexagonal, event-driven, etc.
- **Coding conventions**: naming styles, file organization rules, module boundaries
- **Constraints**: language version pins, required external tools, platform restrictions

---

### Phase 3 — Write `docs/ARCHITECTURE.md`

**Step 3.1 — Ensure `docs/` directory exists**

Create the `docs/` directory if it does not already exist before writing the file.

**Step 3.2 — Generate the document**

Use the [output template](./assets/architecture-template.md) as the structural scaffold.
Fill each section with findings from Phase 2. Follow these writing rules:

- **Factual only** — state what was found in code and config; do not speculate
- **Tables and bullets** over prose for structure/component listings
- **Mermaid diagrams** for data flow and component interactions (use `flowchart LR` or `graph TD`)
- **Proportional depth** — simple scripts need 2–3 bullets per section; large systems need sub-sections
- **No placeholders** — every section must be complete; no `TODO` or `TBD` text
- **Accurate commands** — copy build commands verbatim from config files; do not paraphrase

**Step 3.3 — Confirm completion**

After writing, print a brief confirmation:

```
✓ docs/ARCHITECTURE.md written
  Sections: Project Overview, Tech Stack, Repository Structure, Architecture,
            Design Flow & Data Flow, Build Process, Design Patterns, Summary
  Key findings:
    • <finding 1>
    • <finding 2>
    • <finding 3>
```

---

## Quality Checklist

Before finishing, verify:

- [ ] All 8 sections are present and non-empty
- [ ] Tech stack data came from `detect-stack` output, not guessed
- [ ] Every listed component has a stated responsibility
- [ ] At least one complete end-to-end data flow is documented
- [ ] Build/run commands are accurate and verified against config files
- [ ] Third-party integrations listed with their integration points
- [ ] No `TODO`, `TBD`, or placeholder text in the output file
- [ ] File saved to `docs/ARCHITECTURE.md`
