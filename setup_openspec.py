#!/usr/bin/env python3
"""
setup_openspec.py
-----------------
Installs OpenSpec globally and initialises it in a target repository.
Configured for: GitHub Copilot · Windows & macOS/Linux · Brownfield multi-repo

Usage:
  python setup_openspec.py                     # Interactive – prompts for repo path
  python setup_openspec.py /path/to/repo       # Non-interactive
  python setup_openspec.py --check             # Prerequisite check only (no install)

Requirements:
  • Python 3.8+
  • Node.js 20.19.0+ (with npm)
"""

import sys
import os
import subprocess
import shutil
import argparse
import platform
from pathlib import Path

# ─── Colour helpers (gracefully degraded on Windows without ANSI support) ────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"

def _supports_color() -> bool:
    """Return True if the terminal supports ANSI colour codes."""
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

def c(text: str, *codes: str) -> str:
    if not USE_COLOR:
        return text
    return "".join(codes) + text + RESET

def ok(msg: str):   print(c(f"  ✓  {msg}", GREEN))
def warn(msg: str): print(c(f"  ⚠  {msg}", YELLOW))
def err(msg: str):  print(c(f"  ✗  {msg}", RED), file=sys.stderr)
def info(msg: str): print(c(f"  →  {msg}", CYAN))
def dim(msg: str):  print(c(f"     {msg}", DIM))
def section(title: str):
    bar = "─" * 60
    print()
    print(c(bar, BOLD))
    print(c(f"  {title}", BOLD))
    print(c(bar, BOLD))

# ─── Prerequisite checks ──────────────────────────────────────────────────────

MIN_NODE_MAJOR = 20
MIN_NODE_MINOR = 19

def _run(cmd: list[str], capture: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=str(cwd) if cwd else None,
    )

def check_node() -> bool:
    if not shutil.which("node"):
        err("Node.js not found. Install from https://nodejs.org (v20.19.0+)")
        return False
    result = _run(["node", "--version"])
    raw = result.stdout.strip().lstrip("v")
    parts = raw.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        err(f"Could not parse Node.js version: {raw}")
        return False
    if (major, minor) < (MIN_NODE_MAJOR, MIN_NODE_MINOR):
        err(
            f"Node.js {raw} found but {MIN_NODE_MAJOR}.{MIN_NODE_MINOR}.0+ required. "
            "Download from https://nodejs.org"
        )
        return False
    ok(f"Node.js {raw}")
    return True

def check_npm() -> bool:
    if not shutil.which("npm"):
        err("npm not found. It ships with Node.js – reinstall Node.")
        return False
    result = _run(["npm", "--version"])
    ok(f"npm {result.stdout.strip()}")
    return True

def check_git() -> bool:
    if not shutil.which("git"):
        warn("git not found. OpenSpec works without it, but you'll lose history tracking.")
        return True  # non-fatal
    result = _run(["git", "--version"])
    ok(result.stdout.strip())
    return True

def run_prerequisite_checks() -> bool:
    section("Prerequisite checks")
    results = [check_node(), check_npm(), check_git()]
    return all(results)

# ─── OpenSpec install ─────────────────────────────────────────────────────────

OPENSPEC_PACKAGE = "@fission-ai/openspec"

def is_openspec_installed() -> bool:
    result = _run(["npm", "list", "-g", "--depth=0", OPENSPEC_PACKAGE])
    return OPENSPEC_PACKAGE in result.stdout

def get_installed_version() -> str:
    result = _run(["openspec", "--version"])
    return result.stdout.strip() if result.returncode == 0 else "unknown"

def install_openspec() -> bool:
    section("Installing OpenSpec")
    if is_openspec_installed():
        ver = get_installed_version()
        info(f"OpenSpec already installed ({ver}). Checking for updates…")
    else:
        info("Installing @fission-ai/openspec globally…")

    result = _run(
        ["npm", "install", "-g", f"{OPENSPEC_PACKAGE}@latest"],
        capture=False,
    )
    if result.returncode != 0:
        err("npm install failed. Check the output above.")
        return False

    ver = get_installed_version()
    ok(f"OpenSpec {ver} ready")
    return True

# ─── Repository initialisation ────────────────────────────────────────────────

def resolve_repo_path(arg: str | None) -> Path:
    if arg:
        p = Path(arg).expanduser().resolve()
    else:
        raw = input(
            c("\n  Enter the absolute path to your repository: ", CYAN)
        ).strip()
        if not raw:
            err("No path provided.")
            sys.exit(1)
        p = Path(raw).expanduser().resolve()

    if not p.exists():
        err(f"Path does not exist: {p}")
        sys.exit(1)
    if not p.is_dir():
        err(f"Path is not a directory: {p}")
        sys.exit(1)
    return p

def detect_stack(repo: Path) -> str:
    """Heuristic stack detection for brownfield repos."""
    indicators = {
        "C# / .NET": ["*.csproj", "*.sln", "*.cs"],
        "Swift / iOS": ["*.xcodeproj", "*.xcworkspace", "*.swift"],
        "Angular / Node": ["angular.json", "package.json", "*.ts"],
        "PowerShell": ["*.ps1", "*.psm1"],
        "VC++": ["*.vcxproj", "*.cpp", "*.h"],
    }
    detected = []
    for stack, patterns in indicators.items():
        for pat in patterns:
            if list(repo.rglob(pat)):
                detected.append(stack)
                break
    return ", ".join(detected) if detected else "Unknown / not detected"

def init_openspec(repo: Path) -> bool:
    section("Initialising OpenSpec in repository")
    info(f"Repository : {repo}")

    stack = detect_stack(repo)
    info(f"Stack detected : {stack}")

    openspec_dir = repo / "openspec"
    if openspec_dir.exists():
        warn("openspec/ directory already exists.")
        answer = input(
            c("  Re-initialise and overwrite? [y/N]: ", YELLOW)
        ).strip().lower()
        if answer != "y":
            info("Skipping init – existing openspec/ left intact.")
            return True

    info("Running: openspec init --tools github-copilot --profile extended")
    result = _run(
        ["openspec", "init", "--tools", "github-copilot", "--profile", "extended"],
        capture=False,
        cwd=repo,
    )
    if result.returncode != 0:
        err("openspec init failed. Check the output above.")
        return False

    ok("OpenSpec initialised successfully")
    return True

# ─── Brownfield onboarding scaffold ──────────────────────────────────────────

BROWNFIELD_DOMAINS = {
    "C# / .NET":    ["printer-communication", "device-discovery", "configuration-management"],
    "Swift / iOS":  ["ui", "networking", "data-sync"],
    "Angular / Node": ["ui", "api-client", "auth"],
    "PowerShell":   ["automation", "deployment"],
    "VC++":         ["driver", "hardware-interface"],
}

SPEC_TEMPLATE = """\
# Spec: {domain_title}

> **Status:** Brownfield baseline – reverse-engineered from existing codebase  
> **Last updated:** {date}

---

## Overview

Describe what this capability does and its role in the system.  
*(Fill this in based on code review / existing documentation.)*

---

## Requirements

### Requirement: [REQ-{AREA}-0001] Placeholder – Replace with real requirement

The system SHALL *(describe the behaviour)*.

#### Scenario: Happy path

- GIVEN *(initial context)*
- WHEN *(action or event)*
- THEN *(expected outcome)*

---

## Open Questions

- [ ] *(List any unknowns discovered during reverse engineering)*

---

## References

- Source files: `*(add paths)*`
- ADO work items: *(link if available)*
"""

def create_brownfield_scaffold(repo: Path, stacks: list[str]) -> bool:
    section("Creating brownfield spec scaffold")

    specs_dir = repo / "openspec" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    from datetime import date
    today = date.today().isoformat()

    created = 0
    for stack in stacks:
        domains = BROWNFIELD_DOMAINS.get(stack, ["general"])
        for domain in domains:
            domain_dir = specs_dir / domain
            spec_file = domain_dir / "spec.md"
            if spec_file.exists():
                dim(f"Skipped (exists): openspec/specs/{domain}/spec.md")
                continue
            domain_dir.mkdir(parents=True, exist_ok=True)
            area = domain.upper().replace("-", "_")[:8]
            title = domain.replace("-", " ").title()
            spec_file.write_text(
                SPEC_TEMPLATE.format(domain_title=title, AREA=area, date=today),
                encoding="utf-8",
            )
            ok(f"Created: openspec/specs/{domain}/spec.md")
            created += 1

    if created == 0:
        info("All spec stubs already exist – nothing new created.")
    else:
        ok(f"{created} spec stub(s) created")

    return True

# ─── Post-init guidance ───────────────────────────────────────────────────────

GUIDANCE = """
╔══════════════════════════════════════════════════════════════╗
║           OPENSPEC – BROWNFIELD QUICK-START GUIDE            ║
╚══════════════════════════════════════════════════════════════╝

ANALOGY: Think of OpenSpec like a GPS for AI-assisted development.
Your code is the terrain that already exists. OpenSpec gives the AI
a map (specs/) so it navigates intentionally instead of guessing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT JUST HAPPENED
─────────────────
 openspec/
 ├── specs/          ← Source of truth. YOUR system's current behaviour.
 │   └── <domain>/
 │       └── spec.md ← Stub files created for each detected stack area.
 ├── changes/        ← One folder per in-flight feature/fix.
 └── config.yaml     ← Project config (tool = github-copilot, profile = core).

 .github/
 ├── skills/         ← OpenSpec skill files Copilot reads automatically.
 └── prompts/        ← /opsx-* slash commands for Copilot Chat.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1 – FILL THE MAP (Brownfield baseline, do once per repo)
──────────────────────────────────────────────────────────────
The spec stubs in openspec/specs/ are empty. Fill them by having
Copilot reverse-engineer each capability from your existing code.

In VS Code Copilot Chat, run:

  @workspace /opsx:onboard

This instructs Copilot to analyse the codebase and populate the
spec stubs for you. Review and adjust – Copilot will miss nuance.

Do this per domain (e.g., printer-communication, device-discovery)
rather than all at once. One domain = one Copilot session.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 2 – EVERYDAY WORKFLOW (per new feature or fix)
─────────────────────────────────────────────────────
1. PROPOSE  → agree on what to build before writing any code
   In Copilot Chat:  /opsx:propose <feature-description>
   This creates: openspec/changes/<name>/{proposal.md, specs/, design.md, tasks.md}

2. APPLY    → implement all tasks from tasks.md
   In Copilot Chat:  /opsx:apply
   Copilot works through each checkbox in tasks.md.

3. ARCHIVE  → merge delta specs into the main specs, close the change
   In Copilot Chat:  /opsx:archive
   Moves the change folder to openspec/changes/archive/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MULTI-REPO STRATEGY (your mixed stack situation)
────────────────────────────────────────────────
Run this script once per repo. Each repo gets its own openspec/
directory with stack-specific domain folders:

  C# / .NET repos   →  specs/printer-communication/, specs/device-discovery/
  Swift / iOS repos →  specs/ui/, specs/networking/
  Angular repos     →  specs/ui/, specs/api-client/

Keep specs per-repo. Don't share openspec/ across repos – each repo
is an independent map for its own terrain.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USEFUL CLI COMMANDS
────────────────────
  openspec list                  # list active changes
  openspec show <change-name>    # view change details
  openspec validate <change>     # validate spec formatting
  openspec view                  # interactive dashboard
  openspec update                # refresh Copilot skill/prompt files

KEEP COPILOT SKILLS FRESH: Run `openspec update` after upgrading
the npm package. New commands/skills won't appear until you do.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIPS FOR BROWNFIELD
────────────────────
• Don't try to spec the entire codebase on day one. Start with
  the capability you're actively changing next.

• A good spec is 80% accurate, committed, and iterable. Don't
  wait for perfection – Copilot will help you refine over time.

• Commit openspec/ to source control. It's documentation that
  evolves with the code, not a one-time deliverable.

• Add openspec/changes/archive/ to .gitignore if you don't want
  historical change folders in long-term git history.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ─── Entry point ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Install and initialise OpenSpec for a brownfield repo (GitHub Copilot).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="Path to the target repository (prompted if omitted).",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Run prerequisite checks only – no install or init.",
    )
    p.add_argument(
        "--no-scaffold",
        action="store_true",
        help="Skip creating brownfield spec stubs.",
    )
    return p.parse_args()

def main():
    print()
    print(c("  OpenSpec Setup  –  GitHub Copilot · Brownfield · Multi-repo", BOLD + CYAN))
    print(c(f"  Platform: {platform.system()} {platform.machine()}", DIM))

    args = parse_args()

    # Prerequisite checks
    if not run_prerequisite_checks():
        sys.exit(1)

    if args.check:
        ok("All prerequisites satisfied.")
        sys.exit(0)

    # Install
    if not install_openspec():
        sys.exit(1)

    # Resolve repo
    repo = resolve_repo_path(args.repo)

    # Init
    if not init_openspec(repo):
        sys.exit(1)

    # Brownfield scaffold
    if not args.no_scaffold:
        # Re-detect stack to pass split list
        raw_stack = detect_stack(repo)
        stacks = [s.strip() for s in raw_stack.split(",") if s.strip()]
        if stacks and stacks[0] != "Unknown / not detected":
            create_brownfield_scaffold(repo, stacks)
        else:
            warn("Stack not detected – skipping spec stub generation.")
            info("Run with a populated repo, or create openspec/specs/<domain>/spec.md manually.")

    # Print guidance
    section("Setup complete")
    ok(f"OpenSpec is ready in: {repo}")
    print()
    if USE_COLOR:
        print(c(GUIDANCE, CYAN))
    else:
        print(GUIDANCE)

if __name__ == "__main__":
    main()
