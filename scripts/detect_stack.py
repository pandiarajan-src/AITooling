#!/usr/bin/env python3
"""
scripts/detect_stack.py — Developer convenience shim.

The canonical implementation lives in:
    .github/skills/detect-stack/detect_stack.py

This shim forwards all arguments to it so developers can call:
    python scripts/detect_stack.py <repo_path> [options]
without needing to know the .github path.
"""
import subprocess
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parent.parent / ".github" / "skills" / "detect-stack" / "detect_stack.py"

if not _CANONICAL.exists():
    sys.exit(f"Error: canonical script not found at {_CANONICAL}")

sys.exit(subprocess.run([sys.executable, str(_CANONICAL), *sys.argv[1:]]).returncode)
