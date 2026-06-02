---
name: detect-stack
description: "Detects the technology stack of a repository. Use when: asked to detect stack, identify tech stack, what technologies does this repo use, what frameworks are used, identify languages, list dependencies, analyze repo stack, stack detection, tech stack analysis, what is this repo built with, language detection, framework detection. Runs a Python helper script and returns structured JSON for downstream agents."
user-invocable: true
---

# Detect Tech Stack

Analyzes a repository to detect its full technology stack — languages, frameworks, build
scripts, packaging tools, test frameworks, and CI — then returns structured JSON suitable
for downstream agent and skill pipelines.

## When to Use

Invoke this skill whenever the user:

- Asks what technologies, languages, or frameworks a repository uses
- Wants a stack report before planning migration, onboarding, or spec generation
- Needs structured tech stack data to pass to another agent or skill (e.g. `setup-openspec`)

---

## Steps

### 1. Identify the target repository

If a `repo_path` argument is given, use it. Otherwise:

- If the user has a workspace open, use the workspace root.
- If neither is clear, ask: "Which repository path should I scan?"

### 2. Run the detection script

Execute the following command. The canonical script lives **inside this skill folder** so it travels with the skill when exported to any repository, Claude, or Codex.

**macOS / Linux (bash/zsh):**
```bash
python .github/skills/detect-stack/detect_stack.py "<repo_path>"
```

**Windows (PowerShell):**
```powershell
python .github\skills\detect-stack\detect_stack.py "<repo_path>"
```

To save the result for use by another agent, add `--output stack.json`:
```bash
python .github/skills/detect-stack/detect_stack.py "<repo_path>" --output stack.json
```

To emit compact (single-line) JSON for machine consumption, add `--compact`:
```bash
python .github/skills/detect-stack/detect_stack.py "<repo_path>" --compact --output stack.json
```

> **Developer shortcut:** `scripts/detect_stack.py` is a thin forwarding shim that delegates here — use it when typing the full `.github` path is inconvenient.
> **Requirements:** Python 3.11+ — uses only the standard library, no `pip install` needed.
> Add `--max-depth N` (default: 8) to control how deep the directory scan goes.

### 3. Interpret the output

The script emits JSON with these top-level keys:

| Key | Description |
|-----|-------------|
| `languages` | Detected programming languages with confidence levels |
| `frameworks` | Frameworks/libraries, each tagged with language and category |
| `build_scripts` | Platform-specific build scripts (PowerShell / Bash / AppleScript / Batch) |
| `packaging_tools` | Desktop packaging tools (NSIS, WiX, Inno Setup, create-dmg, etc.) |
| `build_tools` | Build systems (CMake, MSBuild, Make, Gradle, Cargo, etc.) |
| `test_frameworks` | Test frameworks detected via manifests or marker files |
| `build_ci` | CI system markers (e.g., Jenkinsfile) |
| `summary` | One-line human-readable description of the full stack |
| `_meta` | Scan metadata: depth limit, total file count, ecosystems found |

**Confidence levels:**
- `high` — confirmed via manifest or config file parsing
- `medium` — inferred from file extension census or directory markers
- `low` — weak signal only (single file, no corroboration)

### 4. Handle low-confidence or unknown items (LLM enrichment)

If any entry has `"confidence": "low"` **or** the `languages` list is empty after running
the script, perform a constrained enrichment pass:

1. Note which file extensions appear frequently in `_meta` but are unrecognized.
2. Use your file tools (`read_file`, `grep_search`) to read 3–5 representative source files
   from those extensions.
3. Based on the actual code content, fill in missing fields using **only** this structure —
   do **not** rename fields or add new top-level keys:

```json
{
  "languages": [
    { "name": "...", "confidence": "low", "evidence": ["manual review"] }
  ],
  "frameworks": [
    {
      "name": "...", "category": "...", "language": "...",
      "version": null, "confidence": "low", "evidence": ["manual review"]
    }
  ]
}
```

Merge these into the script output before presenting the final result.

### 5. Present the result

Always show:

1. The `summary` field as a bold one-line headline.
2. A formatted table of `languages` and `frameworks`, grouped by language.
3. `build_scripts`, `packaging_tools`, `build_tools`, and `build_ci` sections (if non-empty).
4. The full raw JSON in a collapsible `<details>` block so downstream agents can consume it.

### 6. Pass to downstream agents

When chaining to another skill or agent, pass the **full JSON object** — not just the
`summary` string. Downstream agents should use `frameworks[].category` to understand which
architecture layer each framework targets.

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `repo_path` does not exist | Report the `error` field from JSON; ask the user to verify the path |
| Python not found on PATH | Tell the user: "Python 3.11+ is required. Please ensure `python` is on your PATH." |
| Script returns empty `languages` and `frameworks` | Run the LLM enrichment step (Step 4) |
| Permission errors on subdirectories | Skipped automatically by the script; note this in output |
| Monorepo with multiple sub-projects | Each sub-project's manifests are scanned independently; evidence paths distinguish them |

---

## Example Output Summary

```
C# (WPF/WinForms, NUnit) | C++ (Qt6) | Scripts: windows/linux/macos | Build: MSBuild, CMake | Package: Inno Setup | CI: Jenkins
```
