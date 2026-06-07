#!/usr/bin/env python3
"""
deploy_tooling.py
-----------------
Copies reusable AI tooling assets (agents, skills, prompt templates, and
Copilot instructions) from this AITooling repository into any target local
repository, then invokes setup_openspec.py against that repository.

Usage:
  python deploy_tooling.py                         # Interactive – prompts for repo path
  python deploy_tooling.py /path/to/repo           # Non-interactive
  python deploy_tooling.py /path/to/repo --dry-run # Preview without changes
  python deploy_tooling.py /path/to/repo --overwrite           # Replace existing files
  python deploy_tooling.py /path/to/repo --agents --skills     # Selective categories
  python deploy_tooling.py /path/to/repo --no-openspec         # Skip setup_openspec step
  python deploy_tooling.py --check                             # Prereq check only

Assets deployed (source → destination in target repo):
  .github/agents/*.agent.md          →  .github/agents/
  .github/skills/*/                  →  .github/skills/   (full subtrees)
  scripts/templates/prompts/*.md     →  .github/prompts/
  scripts/templates/copilot-instructions.md  →  .github/copilot-instructions.md

Requirements:
  • Python 3.8+
"""

import sys
import subprocess
import shutil
import argparse
import platform
from pathlib import Path

# Root of the AITooling repo (directory containing this script)
AITOOLING_ROOT = Path(__file__).resolve().parent

# ─── Source asset paths ───────────────────────────────────────────────────────

SRC_AGENTS      = AITOOLING_ROOT / ".github" / "agents"
SRC_SKILLS      = AITOOLING_ROOT / ".github" / "skills"
SRC_PROMPTS     = AITOOLING_ROOT / "scripts" / "templates" / "prompts"
SRC_COPILOT_INS = AITOOLING_ROOT / "scripts" / "templates" / "copilot-instructions.md"
SETUP_OPENSPEC  = AITOOLING_ROOT / "setup_openspec.py"
DETECT_STACK    = SRC_SKILLS / "detect-stack" / "detect_stack.py"

# ─── Colour helpers (Windows ANSI + graceful degradation) ────────────────────

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
def dry(msg: str):  print(c(f"  ~  [DRY RUN] {msg}", YELLOW))

def section(title: str):
    bar = "─" * 60
    print()
    print(c(bar, BOLD))
    print(c(f"  {title}", BOLD))
    print(c(bar, BOLD))

# ─── Prerequisite checks ──────────────────────────────────────────────────────

def check_python() -> bool:
    """Verify Python is 3.8+ (we're already running Python, so just report)."""
    v = sys.version_info
    if (v.major, v.minor) < (3, 8):
        err(f"Python 3.8+ required; found {v.major}.{v.minor}.{v.micro}")
        return False
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return True

def check_setup_openspec() -> bool:
    """Verify setup_openspec.py is present alongside this script."""
    if not SETUP_OPENSPEC.is_file():
        err(f"setup_openspec.py not found at: {SETUP_OPENSPEC}")
        err("This script must live in the same directory as setup_openspec.py.")
        return False
    ok(f"setup_openspec.py found")
    return True

def check_assets() -> bool:
    """Warn if any source asset directories are missing."""
    all_ok = True
    for label, path in [
        ("agents", SRC_AGENTS),
        ("skills", SRC_SKILLS),
        ("prompts", SRC_PROMPTS),
        ("copilot-instructions.md", SRC_COPILOT_INS),
        ("detect_stack.py", DETECT_STACK),
    ]:
        if not path.exists():
            warn(f"Asset not found (will be skipped): {path}")
            all_ok = False
        else:
            ok(f"Asset source found: {label}")
    return True  # missing assets are non-fatal; warn only

def run_prerequisite_checks() -> bool:
    section("Prerequisite checks")
    results = [check_python(), check_setup_openspec(), check_assets()]
    return results[0] and results[1]  # python + setup_openspec are required; assets warnings only

# ─── Target repository resolution ────────────────────────────────────────────

def resolve_target_path(arg: str | None) -> Path:
    """Return a validated, absolute Path for the target repository."""
    if arg:
        p = Path(arg).expanduser().resolve()
    else:
        raw = input(
            c("\n  Enter the absolute path to the target repository: ", CYAN)
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

    if not (p / ".git").exists():
        warn(f"No .git directory found in: {p}")
        warn("Proceeding anyway – assets will still be deployed.")

    return p

# ─── Copy engine ──────────────────────────────────────────────────────────────

def _copy_file(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> tuple[int, int]:
    """
    Copy a single file from src to dst.
    Returns (1, 0) if copied/would-copy, (0, 1) if skipped.
    """
    if dst.exists() and not overwrite:
        dim(f"skipped  (exists) → {dst}")
        return 0, 1

    if dry_run:
        dry(f"would copy → {dst}")
        return 1, 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    ok(f"copied   → {dst}")
    return 1, 0

def copy_asset_tree(
    src_dir: Path,
    dst_dir: Path,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Recursively copy all files under src_dir into dst_dir, preserving
    the relative directory structure.
    Returns (total_copied, total_skipped).
    """
    if not src_dir.is_dir():
        warn(f"Source directory not found, skipping: {src_dir}")
        return 0, 0

    copied = skipped = 0
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        c_, s_ = _copy_file(src_file, dst_file, overwrite, dry_run)
        copied += c_
        skipped += s_

    return copied, skipped

def copy_single_file(
    src: Path,
    dst: Path,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Copy a single asset file.
    Returns (1, 0) if copied/would-copy, (0, 1) if skipped.
    """
    if not src.is_file():
        warn(f"Source file not found, skipping: {src}")
        return 0, 0
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
    return _copy_file(src, dst, overwrite, dry_run)

# ─── Deployment orchestrator ─────────────────────────────────────────────────

def deploy_assets(target: Path, args: argparse.Namespace) -> dict[str, tuple[int, int]]:
    """
    Deploy selected asset categories into the target repository.
    Returns a dict mapping category name → (copied, skipped).
    """
    overwrite = args.overwrite
    dry_run = args.dry_run
    results: dict[str, tuple[int, int]] = {}

    if args.agents:
        section("Deploying agents  (.github/agents/)")
        dst = target / ".github" / "agents"
        results["agents"] = copy_asset_tree(SRC_AGENTS, dst, overwrite, dry_run)

    if args.skills:
        section("Deploying skills  (.github/skills/)")
        dst = target / ".github" / "skills"
        results["skills"] = copy_asset_tree(SRC_SKILLS, dst, overwrite, dry_run)

    if args.prompts:
        section("Deploying prompts  (.github/prompts/)")
        dst = target / ".github" / "prompts"
        results["prompts"] = copy_asset_tree(SRC_PROMPTS, dst, overwrite, dry_run)

    if args.instructions:
        section("Deploying Copilot instructions  (.github/copilot-instructions.md)")
        dst = target / ".github" / "copilot-instructions.md"
        results["instructions"] = copy_single_file(SRC_COPILOT_INS, dst, overwrite, dry_run)

    return results

def print_summary(results: dict[str, tuple[int, int]], dry_run: bool) -> None:
    """Print a per-category summary table."""
    section("Deployment summary")
    label_width = max((len(k) for k in results), default=12)
    mode_note = " (dry run)" if dry_run else ""

    for category, (copied, skipped) in results.items():
        tag = "~" if dry_run else "✓"
        line = f"{category:<{label_width}}  {tag} {copied} copied,  → {skipped} skipped{mode_note}"
        if copied > 0:
            print(c(f"  {line}", GREEN))
        else:
            print(c(f"  {line}", DIM))

# ─── detect-stack invocation ─────────────────────────────────────────────────

def run_detect_stack(target: Path, dry_run: bool) -> bool:
    """Run detect_stack.py against the target repo and write stack.json at its root."""
    section("Detecting tech stack  (stack.json)")

    if not DETECT_STACK.is_file():
        warn(f"detect_stack.py not found at: {DETECT_STACK}")
        warn("Skipping stack detection – stack.json will not be created.")
        return True  # non-fatal

    output_path = target / "stack.json"

    if dry_run:
        dry(f"would run: python {DETECT_STACK.name} {target} --output stack.json")
        return True

    info(f"Running: python {DETECT_STACK.name} {target}")
    result = subprocess.run(
        [
            sys.executable,
            str(DETECT_STACK),
            str(target),
            "--output", str(output_path),
        ],
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        err(f"detect_stack.py exited with code {result.returncode}.")
        return False

    ok(f"Stack detected  → {output_path}")
    return True


# ─── setup_openspec.py invocation ─────────────────────────────────────────────

def run_openspec(target: Path, dry_run: bool) -> bool:
    """Invoke setup_openspec.py with the target repository path."""
    section("Running setup_openspec.py")

    if dry_run:
        dry(f"would run: python {SETUP_OPENSPEC} {target}")
        return True

    info(f"Running: python {SETUP_OPENSPEC.name} {target}")
    result = subprocess.run(
        [sys.executable, str(SETUP_OPENSPEC), str(target)],
        # Inherit stdio so the user sees all colour output from setup_openspec
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        err(f"setup_openspec.py exited with code {result.returncode}.")
        return False

    return True

# ─── Argument parsing ─────────────────────────────────────────────────────────

def _all_category_flags_absent(args: argparse.Namespace) -> bool:
    """Return True when the user supplied no explicit category flags."""
    return not any([
        args._agents_explicit,
        args._skills_explicit,
        args._prompts_explicit,
        args._instructions_explicit,
    ])

class _CategoryAction(argparse.Action):
    """Custom action that records whether the flag was explicitly supplied."""
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        setattr(namespace, f"_{self.dest}_explicit", True)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Deploy AI tooling assets from AITooling into a target repository "
            "and optionally initialise OpenSpec."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Category flags (--agents, --skills, --prompts, --instructions):\n"
            "  When NONE are supplied, ALL categories are deployed (default).\n"
            "  When ANY are supplied, only those categories are deployed.\n"
        ),
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
        help="Run prerequisite checks only – no files are copied.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Preview which files would be copied without making any changes.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace files that already exist in the target repository.",
    )
    p.add_argument(
        "--no-openspec",
        action="store_true",
        dest="no_openspec",
        help="Skip invoking setup_openspec.py after deploying assets.",
    )
    p.add_argument(
        "--no-detect",
        action="store_true",
        dest="no_detect",
        help="Skip running detect_stack.py (stack.json will not be created).",
    )

    # Category flags – each uses _CategoryAction to record explicit supply
    for flag, dest, help_text in [
        ("--agents",       "agents",       "Deploy .github/agents/"),
        ("--skills",       "skills",       "Deploy .github/skills/"),
        ("--prompts",      "prompts",      "Deploy .github/prompts/"),
        ("--instructions", "instructions", "Deploy .github/copilot-instructions.md"),
    ]:
        p.add_argument(
            flag,
            dest=dest,
            nargs=0,
            action=_CategoryAction,
            default=False,
            help=help_text,
        )
        # Hidden sentinel tracking whether the flag was explicitly given
        p.set_defaults(**{f"_{dest}_explicit": False})

    args = p.parse_args()

    # If no category was explicitly requested → enable all
    if _all_category_flags_absent(args):
        args.agents = args.skills = args.prompts = args.instructions = True

    return args

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    print()
    print(c("  AITooling Deploy  –  GitHub Copilot · Agents · Skills · Prompts", BOLD + CYAN))
    print(c(f"  Source : {AITOOLING_ROOT}", DIM))
    print(c(f"  Platform: {platform.system()} {platform.machine()}", DIM))

    args = parse_args()

    if not run_prerequisite_checks():
        sys.exit(1)

    if args.check:
        ok("All prerequisites satisfied.")
        sys.exit(0)

    # Resolve and validate the target repository path
    target = resolve_target_path(args.repo)
    print()
    info(f"Target repository : {target}")

    # Deploy selected asset categories
    results = deploy_assets(target, args)
    print_summary(results, args.dry_run)

    # Detect tech stack and write stack.json unless skipped
    if not args.no_detect:
        if not run_detect_stack(target, args.dry_run):
            sys.exit(1)
    else:
        section("Stack detection")
        dim("Skipped (--no-detect).")

    # Run setup_openspec.py unless skipped
    if not args.no_openspec:
        if not run_openspec(target, args.dry_run):
            sys.exit(1)
    else:
        section("OpenSpec setup")
        dim("Skipped (--no-openspec).")

    section("Done")
    if args.dry_run:
        warn("Dry-run mode: no files were written. Re-run without --dry-run to apply.")
    else:
        ok(f"AITooling assets deployed to: {target}")
        if not args.no_detect:
            ok("stack.json created at repository root.")
        if not args.no_openspec:
            ok("OpenSpec setup complete.")


if __name__ == "__main__":
    main()
