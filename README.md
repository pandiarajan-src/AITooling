# AITooling

A repository-agnostic hub of GitHub Copilot tooling — agents, skills, prompt templates, and
Copilot instructions — that can be deployed into **any** local repository in one command.

## Purpose

AITooling centralises reusable AI development assets so they stay maintained in one place and
can be stamped into target repositories without manual copying:

| Asset | What it does |
|---|---|
| `.github/agents/` | Custom Copilot agent modes (Code Archaeologist) |
| `.github/skills/detect-stack/` | Python script that detects the full tech stack of any repo and emits structured JSON |
| `.github/skills/archlens/` | Skill + scripts for generating and diff-tracking `ARCHITECTURE.md` |
| `.github/skills/openspec-custom-onboard/` | State-aware skill that orchestrates the full OpenSpec brownfield onboarding workflow |
| `scripts/templates/skills/` | Skill templates deployed into target repos (currently: `openspec-custom-onboard`) |
| `scripts/templates/prompts/` | Slash-command prompt templates — `/opsx-full-onboard` (orchestrator) + three step-by-step commands |
| `scripts/templates/copilot-instructions.md` | Copilot workspace instructions template |

Once deployed to a target repository every agent, skill, and prompt is immediately available
in VS Code Copilot Chat without any additional configuration.

---

## Scripts

### `deploy_tooling.py` — Deploy all AI assets to a target repo

Copies all agents, skills, prompt templates, and Copilot instructions from AITooling into
a target repository, then runs `detect_stack.py` to produce `stack.json` at the repo root
and finally invokes `setup_openspec.py` to bootstrap OpenSpec.

**Requirements:** Python 3.8+

```bash
# Deploy everything (interactive – prompts for repo path)
python deploy_tooling.py

# Deploy everything (non-interactive)
python deploy_tooling.py /path/to/target-repo

# Preview what would be copied without writing any files
python deploy_tooling.py /path/to/target-repo --dry-run

# Replace files that already exist in the target repo
python deploy_tooling.py /path/to/target-repo --overwrite

# Deploy only selected categories
python deploy_tooling.py /path/to/target-repo --agents --skills
python deploy_tooling.py /path/to/target-repo --prompts --instructions

# Skip specific steps
python deploy_tooling.py /path/to/target-repo --no-detect      # skip stack.json generation
python deploy_tooling.py /path/to/target-repo --no-openspec    # skip OpenSpec setup
python deploy_tooling.py /path/to/target-repo --no-detect --no-openspec  # assets only

# Check prerequisites only (no files copied)
python deploy_tooling.py --check
```

**What gets deployed:**

```
<target-repo>/
├── .github/
│   ├── agents/
│   │   └── code-archaeologist.agent.md
│   ├── skills/
│   │   ├── archlens/                      ← full subtree
│   │   ├── detect-stack/                  ← full subtree
│   │   └── openspec-custom-onboard/       ← brownfield onboarding skill
│   ├── prompts/
│   │   ├── opsx-full-onboard.prompt.md           ← START HERE (orchestrates all steps)
│   │   ├── opsx-discover-capabilities.prompt.md
│   │   ├── opsx-onboard-domain.prompt.md
│   │   └── opsx-reverse-nfr.prompt.md
│   └── copilot-instructions.md
└── stack.json                 ← tech stack snapshot (for agents and skills to consume)
```

By default, existing files are **skipped** (safe to re-run). Use `--overwrite` to replace them.

---

### `setup_openspec.py` — Install and initialise OpenSpec in a target repo

Installs the `@fission-ai/openspec` npm package globally and runs `openspec init` inside a
target repository to scaffold the `openspec/` spec directory structure.

**Requirements:** Python 3.8+, Node.js 20.19.0+, npm

```bash
# Interactive – prompts for repo path
python setup_openspec.py

# Non-interactive
python setup_openspec.py /path/to/target-repo

# Check prerequisites only (no install)
python setup_openspec.py --check

# Skip deploying prompt templates
python setup_openspec.py /path/to/target-repo --no-prompts
```

**What it does:**

1. Checks for Node.js 20.19.0+, npm, and git
2. Installs (or updates) `@fission-ai/openspec@latest` globally
3. Runs `openspec init --tools github-copilot --profile core` in the target repo
4. Deploys prompt templates to `.github/prompts/` and the `openspec-custom-onboard` skill to `.github/skills/` (unless `--no-prompts`)
5. Prints a brownfield quick-start guide

---

## Typical workflow

```bash
# One command to set up a new repository from scratch:
python deploy_tooling.py /path/to/my-repo
```

This single command:
1. Copies all agents, skills, and prompts into `.github/`
2. Generates `stack.json` at the repo root (tech stack snapshot)
3. Installs OpenSpec and scaffolds `openspec/specs/`
4. Deploys the `openspec-custom-onboard` skill so the team can use `/opsx-full-onboard` immediately

For repos where OpenSpec is already set up and you only want to refresh the AI assets:

```bash
python deploy_tooling.py /path/to/my-repo --no-openspec
```

---

## OpenSpec brownfield onboarding

After running `deploy_tooling.py` (or `setup_openspec.py`) on a repo, the team uses these
slash commands in **VS Code Copilot Chat (agent mode)**:

### Recommended: single entry point

```
/opsx-full-onboard
```

This command is **state-aware and resumable**. Run it in any repo that has been set up with
OpenSpec. It detects what has already been done and continues from where it left off:

| Run | What happens |
|---|---|
| First run (no `domain-map.yaml`) | Scans the codebase, identifies business capability domains, writes `domain-map.yaml` — then **stops** for human review |
| After reviewing `domain-map.yaml` | Generates a full `spec.md` (functional requirements + NFR section) for one domain, reports progress, tells you which domain is next |
| Every subsequent run | Same — one domain per session. Clear Copilot context between domains. |

**Team workflow:**

```
# Step 1 — set up the repo (you, once)
python deploy_tooling.py /path/to/my-repo

# Step 2 — in VS Code Copilot Chat on that repo (any team member)
/opsx-full-onboard        ← run once to create domain-map.yaml, review it, then run again per domain

# Step 3 — everyday development (any team member)
/opsx:propose <feature>   ← agree on specs before writing code
/opsx:apply               ← implement from tasks.md
/opsx:archive             ← merge spec deltas into source-of-truth specs
```

### Step-by-step alternative (manual control)

If you prefer to run each phase separately:

| Command | What it does |
|---|---|
| `/opsx-discover-capabilities` | Scans the codebase and writes `domain-map.yaml` |
| `/opsx-onboard-domain` | Generates a functional `spec.md` for one domain |
| `/opsx-reverse-nfr` | Appends an NFR section to a domain's `spec.md` |

Run one domain per Copilot session. Clear context between domains.

---

## Repository structure

```
AITooling/
├── .github/
│   ├── agents/
│   │   └── code-archaeologist.agent.md   ← reverse-engineer any repo into structured docs
│   └── skills/
│       ├── archlens/                     ← architecture documentation skill
│       ├── detect-stack/                 ← tech stack detection skill + script
│       └── openspec-custom-onboard/      ← brownfield OpenSpec onboarding skill (also in templates)
├── scripts/
│   ├── detect_stack.py                   ← forwarding shim to .github/skills/detect-stack/
│   └── templates/                        ← assets stamped into target repos by setup_openspec.py
│       ├── copilot-instructions.md
│       ├── prompts/                      ← /opsx-* slash commands
│       │   ├── opsx-full-onboard.prompt.md          ← orchestrator (start here)
│       │   ├── opsx-discover-capabilities.prompt.md
│       │   ├── opsx-onboard-domain.prompt.md
│       │   └── opsx-reverse-nfr.prompt.md
│       └── skills/
│           └── openspec-custom-onboard/  ← skill template (deployed alongside prompts)
│               └── SKILL.md
├── deploy_tooling.py        ← deploy all assets to a target repo
├── setup_openspec.py        ← install + init OpenSpec in a target repo
└── pyproject.toml
```
