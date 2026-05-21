# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`aitooling` is a Python 3.14 project (managed via `pyproject.toml`) that currently contains one substantive script: `setup_openspec.py`. This script installs and initializes [OpenSpec](https://www.npmjs.com/package/@fission-ai/openspec) (`@fission-ai/openspec` npm package) in a target repository for GitHub Copilot–assisted brownfield development.

`main.py` is a placeholder entry point not yet wired to any real logic.

## Environment Setup

Python version is pinned to `3.14.5` via `.python-version` (read by `uv` or `pyenv`).

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

The script has a hard external dependency: **Node.js 20.19.0+** with npm must be on `PATH`.

## setup_openspec.py Architecture

The script is a single-file CLI with these distinct phases, each mapped to a function group:

1. **Prerequisite checks** — `check_node()`, `check_npm()`, `check_git()` verify the environment before any side effects.
2. **Install** — `install_openspec()` runs `npm install -g @fission-ai/openspec@latest`. Idempotent.
3. **Repo resolution** — `resolve_repo_path()` accepts a CLI arg or prompts interactively; exits on invalid paths.
4. **Stack detection** — `detect_stack(repo)` uses `Path.rglob()` heuristics to identify C# / .NET, Swift / iOS, Angular / Node, PowerShell, or VC++ codebases.
5. **OpenSpec init** — `init_openspec(repo)` runs `openspec init --tools github-copilot --profile core` in the target repo.
6. **Brownfield scaffold** — `create_brownfield_scaffold(repo, stacks)` writes `openspec/specs/<domain>/spec.md` stubs from `SPEC_TEMPLATE` for each detected stack domain (defined in `BROWNFIELD_DOMAINS`).
7. **Guidance output** — prints `GUIDANCE` (a multi-section usage guide) after successful setup.

Color output is ANSI-based, with Windows support via `ctypes`; gracefully degrades when not a TTY.
