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
import subprocess
import shutil
import argparse
import platform
from pathlib import Path

# Directory containing this script (used to locate template files)
SCRIPT_DIR = Path(__file__).parent

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
        shell=platform.system() == "Windows",
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

def init_openspec(repo: Path) -> bool:
    section("Initialising OpenSpec in repository")
    info(f"Repository : {repo}")

    openspec_dir = repo / "openspec"
    if openspec_dir.exists():
        warn("openspec/ directory already exists.")
        answer = input(
            c("  Re-initialise and overwrite? [y/N]: ", YELLOW)
        ).strip().lower()
        if answer != "y":
            info("Skipping init – existing openspec/ left intact.")
            return True

    info("Running: openspec init --tools github-copilot --profile core")
    result = _run(
        ["openspec", "init", "--tools", "github-copilot", "--profile", "core"],
        capture=False,
        cwd=repo,
    )
    if result.returncode != 0:
        err("openspec init failed. Check the output above.")
        return False

    ok("OpenSpec initialised successfully")
    return True

# ─── Custom prompt deployment ─────────────────────────────────────────────────

TEMPLATES_DIR = SCRIPT_DIR / "scripts" / "templates"

def deploy_custom_prompts(repo: Path) -> bool:
    """Copy prompt templates, skill files, and copilot-instructions into the target repo."""
    section("Deploying capability-discovery prompts and skills")

    prompts_src = TEMPLATES_DIR / "prompts"
    if not prompts_src.is_dir():
        warn(f"Templates directory not found: {prompts_src}")
        warn("Skipping custom prompt deployment – prompts must be added manually.")
        return True  # non-fatal

    # ── Prompts ──────────────────────────────────────────────────────────────
    prompts_dst = repo / ".github" / "prompts"
    prompts_dst.mkdir(parents=True, exist_ok=True)

    deployed: list[str] = []
    skipped: list[str] = []

    for src_file in sorted(prompts_src.glob("*.prompt.md")):
        dst_file = prompts_dst / src_file.name
        if dst_file.exists():
            skipped.append(src_file.name)
        else:
            shutil.copy2(src_file, dst_file)
            deployed.append(src_file.name)

    for name in deployed:
        ok(f"Deployed  → .github/prompts/{name}")
    for name in skipped:
        dim(f"Exists, skipped → .github/prompts/{name}")

    # ── Skills ───────────────────────────────────────────────────────────────
    skills_src = TEMPLATES_DIR / "skills"
    if skills_src.is_dir():
        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            dst_skill_dir = repo / ".github" / "skills" / skill_dir.name
            dst_skill_file = dst_skill_dir / "SKILL.md"
            if dst_skill_file.exists():
                dim(f"Exists, skipped → .github/skills/{skill_dir.name}/SKILL.md")
            else:
                dst_skill_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(skill_file, dst_skill_file)
                ok(f"Deployed  → .github/skills/{skill_dir.name}/SKILL.md")

    # ── copilot-instructions.md ───────────────────────────────────────────────
    ci_src = TEMPLATES_DIR / "copilot-instructions.md"
    ci_dst = repo / ".github" / "copilot-instructions.md"
    if ci_src.is_file():
        if ci_dst.exists():
            dim("Exists, skipped → .github/copilot-instructions.md")
        else:
            ci_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ci_src, ci_dst)
            ok("Deployed  → .github/copilot-instructions.md")

    if deployed:
        info("Custom prompts are available as slash commands in VS Code Copilot Chat.")
        info("Start with:  /opsx-full-onboard  (full workflow, state-aware)")
        info("  or step-by-step:  /opsx-discover-capabilities → /opsx-onboard-domain → /opsx-reverse-nfr")
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
 ├── skills/         ← OpenSpec + custom onboarding skill files Copilot reads automatically.
 │   └── openspec-custom-onboard/SKILL.md
 └── prompts/        ← /opsx-* slash commands for Copilot Chat.
     ├── opsx-full-onboard.prompt.md       ← START HERE (orchestrates all steps)
     ├── opsx-discover-capabilities.prompt.md
     ├── opsx-onboard-domain.prompt.md
     └── opsx-reverse-nfr.prompt.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1 – ONBOARD THE REPO (state-aware, resumable)
────────────────────────────────────────────────────
In VS Code Copilot Chat (agent mode), run:

  /opsx-full-onboard

This single command is state-aware. It will:
  • Run capability discovery (first time only) → creates domain-map.yaml
  • For each run after that: generate a functional spec.md + NFR section
    for one domain at a time.

Review domain-map.yaml before continuing. Correct any misidentified
capabilities, then run /opsx-full-onboard again for each domain.
Clear Copilot context between domain sessions.

STEP-BY-STEP ALTERNATIVE (if you prefer manual control)
────────────────────────────────────────────────────────
  /opsx-discover-capabilities  ← capability discovery only → domain-map.yaml
  /opsx-onboard-domain         ← functional spec.md for one domain
  /opsx-reverse-nfr            ← NFR section for one domain

After each domain: review the spec, fill in [PLACEHOLDER] values
(NFR targets), and resolve TODO(EM-REVIEW) comments.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 3 – EVERYDAY WORKFLOW (per new feature or fix)
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

  C# / .NET repos   →  specs/device-communication/, specs/device-discovery/
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
        "--no-prompts",
        action="store_true",
        help="Skip deploying custom capability-discovery prompt templates.",
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

    # Deploy custom prompts
    if not args.no_prompts:
        deploy_custom_prompts(repo)

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
