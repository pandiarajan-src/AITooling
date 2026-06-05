#!/usr/bin/env python3
"""
archlens_snapshot.py — Repo state snapshot generator and differ for ArchLens UPDATE MODE.

Usage:
  # Generate a fresh snapshot (called after writing a new ARCHITECTURE*.md):
  python archlens_snapshot.py <repo_path> --output <snapshot.json>

  # Compare current repo state against a prior snapshot and emit a diff:
  python archlens_snapshot.py <repo_path> --compare <prior_snapshot.json> [--output <current_snapshot.json>]

Output (--output only):
  JSON file with keys: timestamp, repo_path, files, dependencies, entry_points

Output (--compare):
  Prints a JSON diff to stdout with keys:
    added        — list of new file paths
    removed      — list of deleted file paths
    modified     — list of changed file paths (size or mtime changed)
    dep_changes  — dict of {package: {before, after}} for changed dep versions
    summary      — human-readable change summary string
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Directories to exclude from traversal
EXCLUDE_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".venv", "venv", ".env",
    "dist", "build", "out", ".next", ".nuxt", ".output",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "coverage", ".coverage", "htmlcov",
    ".terraform", ".serverless",
}

# File extensions worth tracking (source + config; skip binaries)
INCLUDE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".cs", ".go", ".rs", ".java", ".kt", ".swift",
    ".rb", ".php", ".cpp", ".c", ".h", ".hpp",
    ".json", ".toml", ".yaml", ".yml", ".xml",
    ".md", ".rst", ".txt",
    ".sh", ".bash", ".zsh", ".ps1",
    ".tf", ".bicep", ".hcl",
    ".sql", ".graphql", ".proto",
    ".env.example", ".env.template",
    ".dockerfile", "",  # extensionless files like Makefile, Dockerfile
}


def should_include(path: Path) -> bool:
    """Return True if this file should be included in the snapshot."""
    suffix = path.suffix.lower()
    # Always include files with no extension (Makefile, Dockerfile, etc.) if small
    if suffix == "":
        return path.stat().st_size < 100_000
    return suffix in INCLUDE_EXTENSIONS


def walk_repo(repo_root: Path) -> list[dict]:
    """Walk the repo and return a list of file records."""
    records = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune excluded dirs in-place so os.walk won't descend into them
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if not should_include(fpath):
                continue
            try:
                stat = fpath.stat()
                records.append({
                    "path": str(fpath.relative_to(repo_root)),
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                })
            except OSError:
                pass  # skip unreadable files
    records.sort(key=lambda r: r["path"])
    return records


def extract_dependencies(repo_root: Path) -> dict[str, str]:
    """
    Extract package → version mappings from common manifest files.
    Returns a flat dict. Version is a string (may include range specifiers).
    """
    deps: dict[str, str] = {}

    # pyproject.toml (PEP 517/518)
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # fallback
            except ImportError:
                tomllib = None  # type: ignore[assignment]
        if tomllib:
            try:
                data = tomllib.loads(pyproject.read_text())
                # PEP 621 dependencies
                for dep in data.get("project", {}).get("dependencies", []):
                    name, _, ver = dep.partition(">=")
                    deps[name.strip()] = ver.strip() or "*"
                # uv / poetry style
                for name, ver in data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
                    if isinstance(ver, str):
                        deps[name] = ver
            except Exception:
                pass
        else:
            # Fallback: regex parse
            text = pyproject.read_text()
            for m in re.finditer(r'"([a-zA-Z0-9_\-]+)\s*([><=!^~][^\s",]*)"', text):
                deps[m.group(1)] = m.group(2)

    # requirements.txt
    req_txt = repo_root / "requirements.txt"
    if req_txt.exists():
        for line in req_txt.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                m = re.match(r"([a-zA-Z0-9_\-]+)\s*([><=!^~][^\s;#]*)?", line)
                if m:
                    deps[m.group(1)] = m.group(2) or "*"

    # package.json
    pkg_json = repo_root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for name, ver in data.get(section, {}).items():
                    deps[name] = ver
        except (json.JSONDecodeError, OSError):
            pass

    # go.mod
    go_mod = repo_root / "go.mod"
    if go_mod.exists():
        for line in go_mod.read_text().splitlines():
            m = re.match(r"\s+([^\s]+)\s+([^\s]+)", line)
            if m:
                deps[m.group(1)] = m.group(2)

    # Cargo.toml
    cargo = repo_root / "Cargo.toml"
    if cargo.exists():
        for line in cargo.read_text().splitlines():
            m = re.match(r'([a-zA-Z0-9_\-]+)\s*=\s*"([^"]+)"', line)
            if m:
                deps[m.group(1)] = m.group(2)

    return deps


def find_entry_points(repo_root: Path) -> list[str]:
    """Heuristically identify likely entry-point files."""
    candidates = []
    for pattern in ("main.py", "main.ts", "main.js", "app.py", "app.ts",
                    "index.ts", "index.js", "server.py", "server.ts",
                    "Program.cs", "main.go", "main.rs"):
        for match in repo_root.rglob(pattern):
            rel = str(match.relative_to(repo_root))
            # Exclude deep nested paths inside node_modules etc.
            parts = Path(rel).parts
            if not any(p in EXCLUDE_DIRS for p in parts):
                candidates.append(rel)
    return sorted(candidates)


def build_snapshot(repo_root: Path) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(repo_root.resolve()),
        "files": walk_repo(repo_root),
        "dependencies": extract_dependencies(repo_root),
        "entry_points": find_entry_points(repo_root),
    }


def diff_snapshots(prior: dict, current: dict) -> dict:
    """Compare two snapshots and return a structured diff."""
    prior_files = {r["path"]: r for r in prior.get("files", [])}
    current_files = {r["path"]: r for r in current.get("files", [])}

    added = sorted(set(current_files) - set(prior_files))
    removed = sorted(set(prior_files) - set(current_files))
    modified = sorted(
        p for p in set(prior_files) & set(current_files)
        if prior_files[p]["mtime"] != current_files[p]["mtime"]
        or prior_files[p]["size"] != current_files[p]["size"]
    )

    prior_deps = prior.get("dependencies", {})
    current_deps = current.get("dependencies", {})
    all_pkg_names = set(prior_deps) | set(current_deps)
    dep_changes: dict[str, dict] = {}
    for pkg in sorted(all_pkg_names):
        before = prior_deps.get(pkg)
        after = current_deps.get(pkg)
        if before != after:
            dep_changes[pkg] = {"before": before, "after": after}

    total_changes = len(added) + len(removed) + len(modified) + len(dep_changes)
    summary_parts = []
    if added:
        summary_parts.append(f"{len(added)} file(s) added")
    if removed:
        summary_parts.append(f"{len(removed)} file(s) removed")
    if modified:
        summary_parts.append(f"{len(modified)} file(s) modified")
    if dep_changes:
        summary_parts.append(f"{len(dep_changes)} dependency version(s) changed")
    summary = ", ".join(summary_parts) if summary_parts else "No changes detected"

    return {
        "prior_timestamp": prior.get("timestamp"),
        "current_timestamp": current.get("timestamp"),
        "total_changes": total_changes,
        "summary": summary,
        "added": added,
        "removed": removed,
        "modified": modified,
        "dep_changes": dep_changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate or diff ArchLens repo snapshots."
    )
    parser.add_argument("repo_path", help="Path to the repository root")
    parser.add_argument(
        "--compare",
        metavar="PRIOR_SNAPSHOT",
        help="Path to a prior snapshot JSON to diff against",
    )
    parser.add_argument(
        "--output",
        metavar="OUTPUT_FILE",
        help="Path to write the current snapshot JSON (optional)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve()
    if not repo_root.is_dir():
        print(f"ERROR: '{repo_root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    current_snapshot = build_snapshot(repo_root)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(current_snapshot, indent=2))

    if args.compare:
        prior_path = Path(args.compare)
        if not prior_path.exists():
            print(f"ERROR: prior snapshot '{prior_path}' not found", file=sys.stderr)
            sys.exit(1)
        prior_snapshot = json.loads(prior_path.read_text())
        diff = diff_snapshots(prior_snapshot, current_snapshot)
        print(json.dumps(diff, indent=2))
    elif not args.output:
        # No flags: just print the snapshot
        print(json.dumps(current_snapshot, indent=2))


if __name__ == "__main__":
    main()
