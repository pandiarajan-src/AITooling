# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`aitooling` is a Python 3.14 project (managed via `pyproject.toml`) that currently contains one substantive script: `setup_openspec.py`. This script installs and initializes [OpenSpec](https://www.npmjs.com/package/@fission-ai/openspec) (`@fission-ai/openspec` npm package) in a target repository for GitHub Copilot–assisted brownfield development.

`main.py` is a placeholder entry point not yet wired to any real logic.

## Environment Setup

Python version is pinned to `3.14.5` via `.python-version` (read by `uv` or `pyenv`). `pyproject.toml` declares `requires-python = ">=3.12"` — the pin is the operative constraint.

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the main script
python main.py

# Run the OpenSpec setup script
python setup_openspec.py                  # interactive (prompts for repo path)
python setup_openspec.py /path/to/repo   # non-interactive
python setup_openspec.py --check         # prerequisite checks only
python setup_openspec.py --no-scaffold   # skip brownfield spec stub creation
```

Hard external dependency: **Node.js 20.19.0+** with npm must be on `PATH`. There is no test suite configured yet.

## setup_openspec.py Architecture

Single-file CLI with no third-party Python dependencies. Execution flows through these phases in order:

1. **Prerequisite checks** (`check_node`, `check_npm`, `check_git`) — verify environment before any side effects. `--check` exits here.
2. **Install** (`install_openspec`) — runs `npm install -g @fission-ai/openspec@latest`. Idempotent.
3. **Repo resolution** (`resolve_repo_path`) — accepts a CLI arg or prompts interactively; `sys.exit(1)` on invalid paths.
4. **OpenSpec init** (`init_openspec`) — runs `openspec init --tools github-copilot --profile extended` in the target repo. Prompts before overwriting an existing `openspec/` directory.
5. **Stack detection** (`detect_stack`) — called inside `init_openspec` for display, then re-called after; uses `Path.rglob()` heuristics against five stacks: C# / .NET, Swift / iOS, Angular / Node, PowerShell, VC++.
6. **Brownfield scaffold** (`create_brownfield_scaffold`) — writes `openspec/specs/<domain>/spec.md` stubs from `SPEC_TEMPLATE` for each detected stack domain (defined in `BROWNFIELD_DOMAINS`). Skipped with `--no-scaffold` or when no stack is detected.
7. **Guidance output** — prints `GUIDANCE` (a multi-section usage guide) after successful setup.

Color output is ANSI-based, with Windows support via `ctypes`; gracefully degrades when not a TTY. The `c()` helper wraps any string in ANSI codes only when `USE_COLOR` is True.
