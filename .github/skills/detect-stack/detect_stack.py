#!/usr/bin/env python3
"""
detect_stack.py — GitHub Copilot Tech Stack Detector

Scans a repository and emits a structured JSON describing the technology stack,
including languages, frameworks, build scripts, packaging tools, test frameworks,
and CI markers.

Usage:
    python scripts/detect_stack.py [repo_path] [--output FILE] [--max-depth N]
    python scripts/detect_stack.py --help

Requires: Python 3.11+ (uses tomllib from stdlib). Zero pip dependencies.
Platform-independent: uses pathlib.Path throughout; no os.sep hardcoding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", "node_modules", "build", "bin", "obj",
    ".venv", "venv", "env", ".env", "dist", "target", ".idea", ".vs",
    "out", "output", ".cache", "coverage", ".tox", "site-packages",
    "Pods", "DerivedData", ".gradle", ".m2", ".dart_tool", ".pub-cache",
    "Packages", "packages", ".build",
})

DEFAULT_MAX_DEPTH = 8

# ---------------------------------------------------------------------------
# Tier 1: Ecosystem marker files (Option A)
# ---------------------------------------------------------------------------

# Maps ecosystem key → list of glob patterns whose presence indicates that ecosystem
ECOSYSTEM_MARKERS: dict[str, list[str]] = {
    "dotnet":   ["*.csproj", "*.sln", "*.fsproj", "*.vbproj"],
    "cpp":      ["CMakeLists.txt", "*.vcxproj", "*.pro", "*.cbp"],
    "nodejs":   ["package.json"],
    "python":   ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "setup.cfg"],
    "java":     ["pom.xml", "build.gradle", "build.gradle.kts"],
    "swift":    ["*.xcodeproj", "*.xcworkspace", "Package.swift", "Podfile"],
    "rust":     ["Cargo.toml"],
    "go":       ["go.mod"],
    "ruby":     ["Gemfile"],
    "php":      ["composer.json"],
    "flutter":  ["pubspec.yaml"],
    "elixir":   ["mix.exs"],
}

# ---------------------------------------------------------------------------
# Tier 2: File extension → (language, category) (Option D)
# ---------------------------------------------------------------------------

EXTENSION_LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    # Primary languages
    ".cs":          ("C#",                      "language"),
    ".fs":          ("F#",                      "language"),
    ".vb":          ("VB.NET",                  "language"),
    ".cpp":         ("C++",                     "language"),
    ".cxx":         ("C++",                     "language"),
    ".cc":          ("C++",                     "language"),
    ".c":           ("C",                       "language"),
    ".h":           ("C/C++",                   "language"),
    ".hpp":         ("C++",                     "language"),
    ".hxx":         ("C++",                     "language"),
    ".swift":       ("Swift",                   "language"),
    ".m":           ("Objective-C",             "language"),
    ".mm":          ("Objective-C++",           "language"),
    ".py":          ("Python",                  "language"),
    ".ts":          ("TypeScript",              "language"),
    ".tsx":         ("TypeScript",              "language"),
    ".js":          ("JavaScript",              "language"),
    ".jsx":         ("JavaScript",              "language"),
    ".java":        ("Java",                    "language"),
    ".kt":          ("Kotlin",                  "language"),
    ".kts":         ("Kotlin",                  "language"),
    ".go":          ("Go",                      "language"),
    ".rs":          ("Rust",                    "language"),
    ".rb":          ("Ruby",                    "language"),
    ".php":         ("PHP",                     "language"),
    ".dart":        ("Dart",                    "language"),
    ".ex":          ("Elixir",                  "language"),
    ".exs":         ("Elixir",                  "language"),
    ".lua":         ("Lua",                     "language"),
    ".r":           ("R",                       "language"),
    # Platform build scripts
    ".ps1":         ("PowerShell",              "script"),
    ".psm1":        ("PowerShell",              "script"),
    ".psd1":        ("PowerShell",              "script"),
    ".sh":          ("Bash/Shell",              "script"),
    ".bash":        ("Bash/Shell",              "script"),
    ".zsh":         ("Zsh",                     "script"),
    ".applescript": ("AppleScript",             "script"),
    ".scpt":        ("AppleScript",             "script"),
    ".bat":         ("Batch",                   "script"),
    ".cmd":         ("Batch",                   "script"),
    # Desktop-specific UI resources
    ".xaml":        ("XAML",                    "desktop"),
    ".rc":          ("Win32 Resource",          "desktop"),
    ".res":         ("Win32 Resource",          "desktop"),
    ".qrc":         ("Qt Resource",             "desktop"),
    ".ui":          ("Qt UI",                   "desktop"),
    ".nib":         ("macOS NIB",               "desktop"),
    ".xib":         ("macOS XIB",               "desktop"),
    ".storyboard":  ("macOS/iOS Storyboard",    "desktop"),
    # Desktop packaging
    ".nsi":         ("NSIS",                    "packaging"),
    ".nsis":        ("NSIS",                    "packaging"),
    ".iss":         ("Inno Setup",              "packaging"),
    ".wxs":         ("WiX",                     "packaging"),
    ".wixproj":     ("WiX",                     "packaging"),
    ".spec":        ("RPM Spec",                "packaging"),
}

# Script extension groups used for build_scripts output
_SCRIPT_GROUPS: list[tuple[str, str, set[str]]] = [
    ("windows", "powershell",   {".ps1", ".psm1", ".psd1"}),
    ("windows", "batch",        {".bat", ".cmd"}),
    ("linux",   "bash",         {".sh", ".bash", ".zsh"}),
    ("macos",   "applescript",  {".applescript", ".scpt"}),
]

# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def _walk(root: Path, max_depth: int):
    """Yield all files under root up to max_depth, skipping SKIP_DIRS."""
    def _recurse(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for child in sorted(path.iterdir()):
                if child.is_dir():
                    if child.name not in SKIP_DIRS and not child.name.startswith("."):
                        yield from _recurse(child, depth + 1)
                    elif child.name == ".github":
                        # Allow .github for Jenkinsfile-adjacent patterns, but skip others
                        pass
                elif child.is_file():
                    yield child
        except PermissionError:
            pass
    yield from _recurse(root, 0)


def _rel(path: Path, root: Path) -> str:
    """Return a forward-slash relative path, safe on all platforms."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _confidence(*, manifest: bool = False, census: bool = False) -> str:
    if manifest:
        return "high"
    if census:
        return "medium"
    return "low"


def _match_glob(filename: str, pattern: str) -> bool:
    """Simple glob match: supports leading/trailing * wildcard on extension."""
    if pattern.startswith("*"):
        return filename.endswith(pattern[1:])
    if pattern.endswith("*"):
        return filename.startswith(pattern[:-1])
    return filename == pattern


# ---------------------------------------------------------------------------
# Tier 1 — Marker scan (Option A)
# ---------------------------------------------------------------------------

def marker_scan(all_files: list[Path], root: Path) -> dict[str, list[str]]:
    """
    Fast first pass: for each ecosystem, check whether any marker file exists.
    Returns {ecosystem: [relative_paths_of_matching_markers]}.
    """
    found: dict[str, list[str]] = defaultdict(list)
    for ecosystem, patterns in ECOSYSTEM_MARKERS.items():
        for pat in patterns:
            for f in all_files:
                if _match_glob(f.name, pat):
                    found[ecosystem].append(_rel(f, root))
                    break  # one match per pattern is enough to confirm ecosystem
    return dict(found)


# ---------------------------------------------------------------------------
# Tier 2 — Extension census (Option D)
# ---------------------------------------------------------------------------

def extension_census(all_files: list[Path]) -> dict[str, int]:
    """Count files per lowercase extension."""
    counts: dict[str, int] = defaultdict(int)
    for f in all_files:
        ext = f.suffix.lower()
        if ext:
            counts[ext] += 1
    return dict(counts)


def _derive_languages_from_census(census: dict[str, int]) -> list[dict]:
    """Map extension counts to language entries with confidence: medium."""
    lang_counts: dict[str, int] = defaultdict(int)
    for ext, count in census.items():
        info = EXTENSION_LANGUAGE_MAP.get(ext)
        if info and info[1] == "language":
            lang_counts[info[0]] += count

    if not lang_counts:
        return []

    total = sum(lang_counts.values()) or 1
    result = []
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
        result.append({
            "name": lang,
            "confidence": "medium",
            "file_count": count,
            "percent": round(count / total * 100, 1),
            "evidence": [f"extension census ({count} files)"],
        })
    return result


def _derive_build_scripts(all_files: list[Path], root: Path) -> list[dict]:
    """Group platform build scripts into per-platform entries."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for f in all_files:
        ext = f.suffix.lower()
        for platform, script_type, extensions in _SCRIPT_GROUPS:
            if ext in extensions:
                groups[(platform, script_type)].append(_rel(f, root))

    result = []
    # Merge windows powershell and windows batch under same platform
    seen_platforms: dict[str, dict] = {}
    for (platform, script_type), files in groups.items():
        if not files:
            continue
        if platform not in seen_platforms:
            seen_platforms[platform] = {
                "platform": platform,
                "type": script_type,
                "files": files[:20],
            }
        else:
            # same platform, different script type — add a separate entry
            result.append({
                "platform": platform,
                "type": script_type,
                "files": files[:20],
            })
    result = list(seen_platforms.values()) + result
    # Stable sort: windows first, then linux, then macos
    order = {"windows": 0, "linux": 1, "macos": 2}
    result.sort(key=lambda x: order.get(x["platform"], 9))
    return result


# ---------------------------------------------------------------------------
# Tier 3 — Manifest parsers (Option B)
# ---------------------------------------------------------------------------

# ── Node.js ───────────────────────────────────────────────────────────────

_NODE_FRAMEWORK_MAP: dict[str, tuple[str, str]] = {
    # Desktop / cross-platform
    "electron":                 ("Electron",        "desktop"),
    "@tauri-apps/api":          ("Tauri",            "desktop"),
    "@tauri-apps/cli":          ("Tauri",            "desktop"),
    "nw":                       ("NW.js",            "desktop"),
    # Frontend
    "react":                    ("React",            "frontend"),
    "vue":                      ("Vue",              "frontend"),
    "@angular/core":            ("Angular",          "frontend"),
    "svelte":                   ("Svelte",           "frontend"),
    "solid-js":                 ("SolidJS",          "frontend"),
    "lit":                      ("Lit",              "frontend"),
    # Build tools
    "vite":                     ("Vite",             "build"),
    "webpack":                  ("Webpack",          "build"),
    "rollup":                   ("Rollup",           "build"),
    "esbuild":                  ("esbuild",          "build"),
    "parcel":                   ("Parcel",           "build"),
    "turbo":                    ("Turborepo",        "build"),
    "@swc/core":                ("SWC",              "build"),
    # Backend
    "express":                  ("Express",          "backend"),
    "fastify":                  ("Fastify",          "backend"),
    "@nestjs/core":             ("NestJS",           "backend"),
    "koa":                      ("Koa",              "backend"),
    "hapi":                     ("Hapi",             "backend"),
    "next":                     ("Next.js",          "fullstack"),
    "nuxt":                     ("Nuxt",             "fullstack"),
    # Test
    "jest":                     ("Jest",             "test"),
    "vitest":                   ("Vitest",           "test"),
    "mocha":                    ("Mocha",            "test"),
    "jasmine":                  ("Jasmine",          "test"),
    "cypress":                  ("Cypress",          "test"),
    "@playwright/test":         ("Playwright",       "test"),
    "@testing-library/react":   ("Testing Library",  "test"),
}


def parse_package_json(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    """Returns (frameworks, test_frameworks)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return [], []

    all_deps: dict[str, str] = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    frameworks, tests = [], []
    rel = _rel(path, root)
    seen: set[str] = set()

    for pkg, version in all_deps.items():
        if pkg in _NODE_FRAMEWORK_MAP and pkg not in seen:
            seen.add(pkg)
            name, category = _NODE_FRAMEWORK_MAP[pkg]
            ver = version.lstrip("^~>=") if isinstance(version, str) else None
            entry = {
                "name": name,
                "category": category,
                "language": "TypeScript/JavaScript",
                "version": ver or None,
                "confidence": "high",
                "evidence": [rel],
            }
            if category == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)

    return frameworks, tests


# ── Python ────────────────────────────────────────────────────────────────

_PYTHON_FRAMEWORK_MAP: dict[str, tuple[str, str]] = {
    "django":           ("Django",          "backend"),
    "flask":            ("Flask",           "backend"),
    "fastapi":          ("FastAPI",         "backend"),
    "starlette":        ("Starlette",       "backend"),
    "tornado":          ("Tornado",         "backend"),
    "aiohttp":          ("aiohttp",         "backend"),
    "litestar":         ("Litestar",        "backend"),
    "sqlalchemy":       ("SQLAlchemy",      "database"),
    "alembic":          ("Alembic",         "database"),
    "celery":           ("Celery",          "async"),
    "pydantic":         ("Pydantic",        "data"),
    "pyqt5":            ("PyQt5",           "desktop"),
    "pyqt6":            ("PyQt6",           "desktop"),
    "pyside2":          ("PySide2",         "desktop"),
    "pyside6":          ("PySide6",         "desktop"),
    "tkinter":          ("Tkinter",         "desktop"),
    "wx":               ("wxPython",        "desktop"),
    "wxpython":         ("wxPython",        "desktop"),
    "kivy":             ("Kivy",            "desktop"),
    "toga":             ("Toga",            "desktop"),
    "pytest":           ("pytest",          "test"),
    "nose2":            ("nose2",           "test"),
    "hypothesis":       ("Hypothesis",      "test"),
    "numpy":            ("NumPy",           "data-science"),
    "pandas":           ("Pandas",          "data-science"),
    "scikit_learn":     ("scikit-learn",    "ml"),
    "torch":            ("PyTorch",         "ml"),
    "tensorflow":       ("TensorFlow",      "ml"),
    "transformers":     ("HF Transformers", "ml"),
}


def _normalize_py_pkg(name: str) -> str:
    """Normalize a Python package name to the key format used in _PYTHON_FRAMEWORK_MAP."""
    return re.sub(r"[-_. ]+", "_", name.lower())


def _build_python_results(dep_names: list[str], evidence: str) -> tuple[list[dict], list[dict]]:
    frameworks, tests = [], []
    seen: set[str] = set()
    for raw in dep_names:
        key = _normalize_py_pkg(raw.split("[")[0])  # strip extras like package[extra]
        if key in _PYTHON_FRAMEWORK_MAP and key not in seen:
            seen.add(key)
            name, cat = _PYTHON_FRAMEWORK_MAP[key]
            entry = {
                "name": name,
                "category": cat,
                "language": "Python",
                "version": None,
                "confidence": "high",
                "evidence": [evidence],
            }
            if cat == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)
    return frameworks, tests


def _toml_extract_deps(text: str) -> list[str]:
    """
    Minimal TOML dep extractor for Python < 3.11 fallback.
    Extracts quoted package names from dependency arrays.
    """
    deps: list[str] = []
    in_array = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.search(r'dependencies\s*=\s*\[', stripped):
            in_array = True
        if in_array:
            for m in re.finditer(r'"([^"]+)"', stripped):
                deps.append(m.group(1))
            if "]" in stripped:
                in_array = False
    return deps


def parse_pyproject_toml(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    rel = _rel(path, root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    try:
        import tomllib  # Python 3.11+
        data = tomllib.loads(text)
    except ImportError:
        deps = _toml_extract_deps(text)
        return _build_python_results(deps, rel)
    except Exception:
        return [], []

    dep_names: list[str] = []
    # PEP 621
    for dep in data.get("project", {}).get("dependencies", []):
        m = re.match(r"^([A-Za-z0-9_.\-]+)", dep)
        if m:
            dep_names.append(m.group(1))
    # Poetry
    for pkg in data.get("tool", {}).get("poetry", {}).get("dependencies", {}):
        dep_names.append(pkg)
    for pkg in data.get("tool", {}).get("poetry", {}).get("dev-dependencies", {}):
        dep_names.append(pkg)
    # PDM / Hatch optional groups
    for group in data.get("tool", {}).get("pdm", {}).get("dev-dependencies", {}).values():
        for dep in group:
            m = re.match(r"^([A-Za-z0-9_.\-]+)", dep)
            if m:
                dep_names.append(m.group(1))

    return _build_python_results(dep_names, rel)


def parse_requirements_txt(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], []

    dep_names: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith(("#", "-r", "-c", "--")):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if m:
            dep_names.append(m.group(1))

    return _build_python_results(dep_names, _rel(path, root))


# ── .NET / C# ─────────────────────────────────────────────────────────────

_DOTNET_PACKAGE_MAP: dict[str, tuple[str, str]] = {
    "microsoft.aspnetcore":                         ("ASP.NET Core",         "backend"),
    "microsoft.entityframeworkcore":                ("Entity Framework Core","database"),
    "microsoft.windowsdesktop.app":                 ("WPF/WinForms",         "desktop"),
    "microsoft.maui":                               ("MAUI",                 "desktop"),
    "xamarin":                                      ("Xamarin",              "desktop"),
    "microsoft.ui.xaml":                            ("WinUI 3",              "desktop"),
    "avalonia":                                     ("Avalonia UI",          "desktop"),
    "eto.forms":                                    ("Eto.Forms",            "desktop"),
    "blazor":                                       ("Blazor",               "frontend"),
    "microsoft.aspnetcore.components.webassembly":  ("Blazor WASM",          "frontend"),
    "grpc":                                         ("gRPC",                 "rpc"),
    "nunit":                                        ("NUnit",                "test"),
    "xunit":                                        ("xUnit",                "test"),
    "mstest":                                       ("MSTest",               "test"),
    "moq":                                          ("Moq",                  "test"),
    "fluentassertions":                             ("FluentAssertions",     "test"),
    "nlog":                                         ("NLog",                 "logging"),
    "serilog":                                      ("Serilog",              "logging"),
    "newtonsoft.json":                              ("Newtonsoft.Json",      "data"),
    "system.text.json":                             ("System.Text.Json",     "data"),
    "dapper":                                       ("Dapper",               "database"),
    "autofac":                                      ("Autofac",              "di"),
    "prism":                                        ("Prism",                "mvvm"),
    "mvvmcross":                                    ("MvvmCross",            "mvvm"),
    "microsoft.extensions.dependencyinjection":     ("MS DI Extensions",    "di"),
    "reactiveui":                                   ("ReactiveUI",           "mvvm"),
}


def parse_csproj(path: Path, root: Path) -> tuple[list[dict], list[dict], str | None]:
    """Returns (frameworks, test_frameworks, output_type)."""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return [], [], None

    rel = _rel(path, root)
    output_type: str | None = None
    target_framework: str | None = None
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for elem in tree.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        text = (elem.text or "").strip()

        if tag == "OutputType" and text:
            output_type = text
        if tag in ("TargetFramework", "TargetFrameworks") and text:
            target_framework = text.split(";")[0]  # first framework if multi-targeting

        if tag == "PackageReference":
            include = (elem.get("Include") or elem.get("include") or "").lower()
            version = (elem.get("Version") or elem.get("version") or
                       next((c.text for c in elem if (c.tag.split("}")[-1]) == "Version"), None) or "")
            for prefix, (name, cat) in _DOTNET_PACKAGE_MAP.items():
                if include.startswith(prefix.lower()) and name not in seen:
                    seen.add(name)
                    entry = {
                        "name": name,
                        "category": cat,
                        "language": "C#",
                        "version": version or None,
                        "confidence": "high",
                        "evidence": [rel],
                    }
                    if cat == "test":
                        tests.append(entry)
                    else:
                        frameworks.append(entry)
                    break

    # Infer WPF/WinForms from OutputType when no explicit framework PackageRef found
    desktop_names = {"WPF/WinForms", "MAUI", "WinUI 3", "Avalonia UI", "Eto.Forms"}
    if output_type == "WinExe" and not any(f["name"] in desktop_names for f in frameworks):
        frameworks.append({
            "name": "WPF/WinForms",
            "category": "desktop",
            "language": "C#",
            "version": target_framework,
            "confidence": "medium",
            "evidence": [f"{rel} (OutputType=WinExe)"],
        })

    return frameworks, tests, output_type


# ── C++ (CMake + .vcxproj + .pro) ─────────────────────────────────────────

_CMAKE_PATTERNS: list[tuple[str, str, str]] = [
    (r"find_package\s*\(\s*Qt5",        "Qt5",          "desktop"),
    (r"find_package\s*\(\s*Qt6",        "Qt6",          "desktop"),
    (r"find_package\s*\(\s*GTK",        "GTK",          "desktop"),
    (r"find_package\s*\(\s*wxWidgets",  "wxWidgets",    "desktop"),
    (r"find_package\s*\(\s*FLTK",       "FLTK",         "desktop"),
    (r"find_package\s*\(\s*Boost",      "Boost",        "library"),
    (r"find_package\s*\(\s*OpenCV",     "OpenCV",       "vision"),
    (r"find_package\s*\(\s*SFML",       "SFML",         "desktop"),
    (r"find_package\s*\(\s*SDL2",       "SDL2",         "desktop"),
    (r"find_package\s*\(\s*GTest",      "GoogleTest",   "test"),
    (r"find_package\s*\(\s*Catch2",     "Catch2",       "test"),
    (r"enable_testing\s*\(\s*\)",       "CTest",        "test"),
    (r"#include\s+[<\"]gtest/gtest",    "GoogleTest",   "test"),
    (r"#include\s+[<\"]catch2/",        "Catch2",       "test"),
    (r"add_subdirectory.*doctest",      "doctest",      "test"),
]

_VCXPROJ_KEYWORDS: dict[str, tuple[str, str]] = {
    "use_of_mfc":   ("MFC",     "desktop"),
    "use_of_atl":   ("ATL",     "desktop"),
    "atmfc":        ("MFC",     "desktop"),
    "mfcisapiextension": ("MFC", "desktop"),
}

_QT_PRO_PATTERNS: list[tuple[str, str]] = [
    (r"QT\s*\+=.*widgets",   "Qt Widgets"),
    (r"QT\s*\+=.*quick",     "Qt Quick/QML"),
    (r"QT\s*\+=.*core",      "Qt Core"),
    (r"greaterThan\(QT_MAJOR_VERSION,\s*4\)", "Qt5+"),
]


def parse_cmake(cmake_files: list[Path], root: Path) -> tuple[list[dict], list[dict]]:
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for path in cmake_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = _rel(path, root)
        for pattern, name, cat in _CMAKE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE) and name not in seen:
                seen.add(name)
                entry = {
                    "name": name,
                    "category": cat,
                    "language": "C++",
                    "version": None,
                    "confidence": "high",
                    "evidence": [rel],
                }
                if cat == "test":
                    tests.append(entry)
                else:
                    frameworks.append(entry)

    return frameworks, tests


def parse_vcxproj(vcx_files: list[Path], root: Path) -> list[dict]:
    frameworks: list[dict] = []
    seen: set[str] = set()

    for path in vcx_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        rel = _rel(path, root)
        for keyword, (name, cat) in _VCXPROJ_KEYWORDS.items():
            if keyword in text and name not in seen:
                seen.add(name)
                frameworks.append({
                    "name": name,
                    "category": cat,
                    "language": "C++",
                    "version": None,
                    "confidence": "medium",
                    "evidence": [rel],
                })

    return frameworks


def parse_qt_pro(pro_files: list[Path], root: Path) -> list[dict]:
    """Parse Qt .pro project files."""
    frameworks: list[dict] = []
    seen: set[str] = set()

    for path in pro_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = _rel(path, root)
        for pattern, label in _QT_PRO_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE) and label not in seen:
                seen.add(label)
                frameworks.append({
                    "name": label,
                    "category": "desktop",
                    "language": "C++",
                    "version": None,
                    "confidence": "high",
                    "evidence": [rel],
                })

    return frameworks


# ── JVM (Maven + Gradle) ──────────────────────────────────────────────────

_JAVA_ARTIFACT_MAP: dict[str, tuple[str, str]] = {
    "spring-boot":          ("Spring Boot",      "backend"),
    "spring-core":          ("Spring",           "backend"),
    "spring-web":           ("Spring Web",       "backend"),
    "hibernate-core":       ("Hibernate",        "database"),
    "android":              ("Android SDK",      "mobile"),
    "javafx":               ("JavaFX",           "desktop"),
    "junit":                ("JUnit",            "test"),
    "testng":               ("TestNG",           "test"),
    "mockito":              ("Mockito",          "test"),
    "quarkus":              ("Quarkus",          "backend"),
    "micronaut":            ("Micronaut",        "backend"),
    "slf4j":                ("SLF4J",            "logging"),
    "log4j":                ("Log4j",            "logging"),
    "jackson":              ("Jackson",          "data"),
    "gson":                 ("Gson",             "data"),
}

_MAVEN_NS = "http://maven.apache.org/POM/4.0.0"


def parse_pom_xml(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for dep in tree.iter():
        # Handle both namespaced and non-namespaced elements
        raw_tag = dep.tag
        tag = raw_tag.replace(f"{{{_MAVEN_NS}}}", "") if _MAVEN_NS in raw_tag else raw_tag
        if tag != "dependency":
            continue

        artifact_id: str | None = None
        version: str | None = None
        for child in dep:
            child_tag = child.tag.replace(f"{{{_MAVEN_NS}}}", "") if _MAVEN_NS in child.tag else child.tag
            if child_tag == "artifactId" and child.text:
                artifact_id = child.text.strip().lower()
            elif child_tag == "version" and child.text:
                version = child.text.strip()

        if not artifact_id:
            continue
        for keyword, (name, cat) in _JAVA_ARTIFACT_MAP.items():
            if keyword in artifact_id and name not in seen:
                seen.add(name)
                entry = {
                    "name": name,
                    "category": cat,
                    "language": "Java",
                    "version": version,
                    "confidence": "high",
                    "evidence": [rel],
                }
                if cat == "test":
                    tests.append(entry)
                else:
                    frameworks.append(entry)
                break

    return frameworks, tests


def parse_build_gradle(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()
    text_lower = text.lower()

    for keyword, (name, cat) in _JAVA_ARTIFACT_MAP.items():
        if keyword in text_lower and name not in seen:
            seen.add(name)
            ver_m = re.search(rf'["\'].*{re.escape(keyword)}.*:([^"\']+)["\']', text, re.IGNORECASE)
            version = ver_m.group(1).strip().lstrip(":") if ver_m else None
            entry = {
                "name": name,
                "category": cat,
                "language": "Java/Kotlin",
                "version": version,
                "confidence": "high",
                "evidence": [rel],
            }
            if cat == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)

    return frameworks, tests


# ── Swift / Objective-C ───────────────────────────────────────────────────

_SWIFT_PACKAGE_MAP: dict[str, tuple[str, str]] = {
    "swiftui":          ("SwiftUI",     "desktop"),
    "appkit":           ("AppKit",      "desktop"),
    "uikit":            ("UIKit",       "mobile"),
    "combine":          ("Combine",     "async"),
    "alamofire":        ("Alamofire",   "networking"),
    "realm":            ("Realm",       "database"),
    "rxswift":          ("RxSwift",     "async"),
    "snapkit":          ("SnapKit",     "desktop"),
    "xctest":           ("XCTest",      "test"),
    "quick":            ("Quick",       "test"),
    "nimble":           ("Nimble",      "test"),
    "kingfisher":       ("Kingfisher",  "image"),
    "grdb":             ("GRDB",        "database"),
}


def parse_package_swift(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for keyword, (name, cat) in _SWIFT_PACKAGE_MAP.items():
        if keyword in text and name not in seen:
            seen.add(name)
            entry = {
                "name": name,
                "category": cat,
                "language": "Swift",
                "version": None,
                "confidence": "medium",
                "evidence": [rel],
            }
            if cat == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)

    return frameworks, tests


def parse_podfile(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for line in text.splitlines():
        m = re.match(r"\s*pod\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?", line)
        if m:
            pod_name = m.group(1)
            version = m.group(2)
            key = pod_name.lower()
            if key in _SWIFT_PACKAGE_MAP and pod_name not in seen:
                seen.add(pod_name)
                name, cat = _SWIFT_PACKAGE_MAP[key]
                entry = {
                    "name": name,
                    "category": cat,
                    "language": "Swift/ObjC",
                    "version": version,
                    "confidence": "high",
                    "evidence": [rel],
                }
                if cat == "test":
                    tests.append(entry)
                else:
                    frameworks.append(entry)

    return frameworks, tests


# ── Rust ──────────────────────────────────────────────────────────────────

_RUST_CRATE_MAP: dict[str, tuple[str, str]] = {
    "actix-web":    ("Actix-web",   "backend"),
    "axum":         ("Axum",        "backend"),
    "warp":         ("Warp",        "backend"),
    "rocket":       ("Rocket",      "backend"),
    "tokio":        ("Tokio",       "async"),
    "async-std":    ("async-std",   "async"),
    "serde":        ("Serde",       "data"),
    "diesel":       ("Diesel",      "database"),
    "sqlx":         ("SQLx",        "database"),
    "egui":         ("egui",        "desktop"),
    "iced":         ("Iced",        "desktop"),
    "slint":        ("Slint",       "desktop"),
    "tauri":        ("Tauri",       "desktop"),
    "druid":        ("Druid",       "desktop"),
    "clap":         ("clap",        "cli"),
    "rayon":        ("Rayon",       "parallel"),
}


def parse_cargo_toml(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    rel = _rel(path, root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    try:
        import tomllib
        data = tomllib.loads(text)
    except ImportError:
        # Fallback: extract quoted crate names
        frameworks: list[dict] = []
        seen: set[str] = set()
        for line in text.splitlines():
            m = re.match(r"^([a-z][a-z0-9_-]*)\s*=", line.strip())
            if m:
                crate = m.group(1).lower()
                if crate in _RUST_CRATE_MAP and crate not in seen:
                    seen.add(crate)
                    name, cat = _RUST_CRATE_MAP[crate]
                    frameworks.append({
                        "name": name, "category": cat, "language": "Rust",
                        "version": None, "confidence": "medium", "evidence": [rel],
                    })
        return frameworks, []
    except Exception:
        return [], []

    all_deps: dict = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("dev-dependencies", {}))

    frameworks_out: list[dict] = []
    seen: set[str] = set()
    for crate, ver_info in all_deps.items():
        key = crate.lower()
        if key in _RUST_CRATE_MAP and key not in seen:
            seen.add(key)
            name, cat = _RUST_CRATE_MAP[key]
            version = (
                ver_info if isinstance(ver_info, str)
                else ver_info.get("version") if isinstance(ver_info, dict)
                else None
            )
            frameworks_out.append({
                "name": name, "category": cat, "language": "Rust",
                "version": version, "confidence": "high", "evidence": [rel],
            })

    return frameworks_out, []


# ── Go ────────────────────────────────────────────────────────────────────

_GO_MODULE_MAP: dict[str, tuple[str, str]] = {
    "github.com/gin-gonic/gin":         ("Gin",             "backend"),
    "github.com/labstack/echo":         ("Echo",            "backend"),
    "github.com/gofiber/fiber":         ("Fiber",           "backend"),
    "github.com/beego/beego":           ("Beego",           "backend"),
    "gorm.io/gorm":                     ("GORM",            "database"),
    "go.mongodb.org/mongo-driver":      ("MongoDB Driver",  "database"),
    "github.com/fyne-io/fyne":          ("Fyne",            "desktop"),
    "github.com/wailsapp/wails":        ("Wails",           "desktop"),
    "github.com/spf13/cobra":           ("Cobra",           "cli"),
    "github.com/urfave/cli":            ("urfave/cli",      "cli"),
    "github.com/stretchr/testify":      ("Testify",         "test"),
    "github.com/onsi/ginkgo":           ("Ginkgo",          "test"),
}


def parse_go_mod(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for mod_path, (name, cat) in _GO_MODULE_MAP.items():
        if mod_path in text and mod_path not in seen:
            seen.add(mod_path)
            ver_m = re.search(rf'{re.escape(mod_path)}\s+(\S+)', text)
            version = ver_m.group(1) if ver_m else None
            entry = {
                "name": name, "category": cat, "language": "Go",
                "version": version, "confidence": "high", "evidence": [rel],
            }
            if cat == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)

    return frameworks, tests


# ── Ruby ──────────────────────────────────────────────────────────────────

_RUBY_GEM_MAP: dict[str, tuple[str, str]] = {
    "rails":        ("Rails",       "backend"),
    "sinatra":      ("Sinatra",     "backend"),
    "rspec":        ("RSpec",       "test"),
    "minitest":     ("Minitest",    "test"),
    "sidekiq":      ("Sidekiq",     "async"),
    "devise":       ("Devise",      "auth"),
    "activerecord": ("ActiveRecord","database"),
    "sequel":       ("Sequel",      "database"),
}


def parse_gemfile(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()

    for line in text.splitlines():
        m = re.match(r"\s*gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?", line)
        if m:
            gem_name = m.group(1).lower()
            version = m.group(2)
            if gem_name in _RUBY_GEM_MAP and gem_name not in seen:
                seen.add(gem_name)
                name, cat = _RUBY_GEM_MAP[gem_name]
                entry = {
                    "name": name, "category": cat, "language": "Ruby",
                    "version": version, "confidence": "high", "evidence": [rel],
                }
                if cat == "test":
                    tests.append(entry)
                else:
                    frameworks.append(entry)

    return frameworks, tests


# ── PHP ───────────────────────────────────────────────────────────────────

_PHP_PACKAGE_MAP: dict[str, tuple[str, str]] = {
    "laravel/framework":    ("Laravel",     "backend"),
    "symfony/symfony":      ("Symfony",     "backend"),
    "symfony/framework-bundle": ("Symfony", "backend"),
    "slim/slim":            ("Slim",        "backend"),
    "phpunit/phpunit":      ("PHPUnit",     "test"),
    "doctrine/orm":         ("Doctrine",    "database"),
    "guzzlehttp/guzzle":    ("Guzzle",      "networking"),
}


def parse_composer_json(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()
    all_deps: dict[str, str] = {}
    all_deps.update(data.get("require", {}))
    all_deps.update(data.get("require-dev", {}))

    for pkg, version in all_deps.items():
        if pkg in _PHP_PACKAGE_MAP and pkg not in seen:
            seen.add(pkg)
            name, cat = _PHP_PACKAGE_MAP[pkg]
            entry = {
                "name": name, "category": cat, "language": "PHP",
                "version": version, "confidence": "high", "evidence": [rel],
            }
            if cat == "test":
                tests.append(entry)
            else:
                frameworks.append(entry)

    return frameworks, tests


# ── Flutter / Dart ────────────────────────────────────────────────────────

_FLUTTER_PACKAGE_MAP: dict[str, tuple[str, str]] = {
    "flutter_riverpod":     ("Riverpod",    "state"),
    "riverpod":             ("Riverpod",    "state"),
    "provider":             ("Provider",    "state"),
    "bloc":                 ("BLoC",        "state"),
    "flutter_bloc":         ("BLoC",        "state"),
    "get":                  ("GetX",        "state"),
    "dio":                  ("Dio",         "networking"),
    "sqflite":              ("sqflite",     "database"),
    "hive":                 ("Hive",        "database"),
    "isar":                 ("Isar",        "database"),
    "flutter_test":         ("flutter_test","test"),
    "mockito":              ("Mockito",     "test"),
}


def parse_pubspec_yaml(path: Path, root: Path) -> tuple[list[dict], list[dict]]:
    """Minimal YAML dep parser — avoids PyYAML dependency."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []

    rel = _rel(path, root)
    frameworks: list[dict] = []
    tests: list[dict] = []
    seen: set[str] = set()
    in_deps = False

    for line in text.splitlines():
        if re.match(r"^(dependencies|dev_dependencies)\s*:", line):
            in_deps = True
            continue
        if in_deps and re.match(r"^\S", line):
            in_deps = False
        if in_deps:
            m = re.match(r"\s+([a-z_][a-z0-9_]*)\s*:", line)
            if m:
                pkg = m.group(1)
                if pkg in _FLUTTER_PACKAGE_MAP and pkg not in seen:
                    seen.add(pkg)
                    name, cat = _FLUTTER_PACKAGE_MAP[pkg]
                    entry = {
                        "name": name, "category": cat, "language": "Dart",
                        "version": None, "confidence": "high", "evidence": [rel],
                    }
                    if cat == "test":
                        tests.append(entry)
                    else:
                        frameworks.append(entry)

    return frameworks, tests


# ---------------------------------------------------------------------------
# Manifest parsing orchestrator
# ---------------------------------------------------------------------------

def run_manifest_parsers(
    root: Path,
    ecosystems: dict[str, list[str]],
    all_files: list[Path],
) -> tuple[list[dict], list[dict]]:
    """Run manifest parsers for all detected ecosystems. Returns (frameworks, tests)."""
    all_fw: list[dict] = []
    all_t: list[dict] = []

    def _extend(fw: list[dict], t: list[dict]) -> None:
        all_fw.extend(fw)
        all_t.extend(t)

    if "dotnet" in ecosystems:
        for f in all_files:
            if f.suffix.lower() in (".csproj", ".fsproj", ".vbproj"):
                fw, t, _ = parse_csproj(f, root)
                _extend(fw, t)

    if "cpp" in ecosystems:
        cmake_files = [f for f in all_files if f.name == "CMakeLists.txt"]
        if cmake_files:
            _extend(*parse_cmake(cmake_files, root))
        vcx_files = [f for f in all_files if f.suffix.lower() == ".vcxproj"]
        if vcx_files:
            all_fw.extend(parse_vcxproj(vcx_files, root))
        pro_files = [f for f in all_files if f.suffix.lower() == ".pro"]
        if pro_files:
            all_fw.extend(parse_qt_pro(pro_files, root))

    if "nodejs" in ecosystems:
        for f in all_files:
            if f.name == "package.json" and "node_modules" not in f.parts:
                _extend(*parse_package_json(f, root))

    if "python" in ecosystems:
        for f in all_files:
            if f.name == "pyproject.toml":
                _extend(*parse_pyproject_toml(f, root))
            elif re.match(r"requirements.*\.txt$", f.name, re.IGNORECASE):
                _extend(*parse_requirements_txt(f, root))

    if "java" in ecosystems:
        for f in all_files:
            if f.name == "pom.xml":
                _extend(*parse_pom_xml(f, root))
            elif f.name in ("build.gradle", "build.gradle.kts"):
                _extend(*parse_build_gradle(f, root))

    if "swift" in ecosystems:
        for f in all_files:
            if f.name == "Package.swift":
                _extend(*parse_package_swift(f, root))
            elif f.name == "Podfile":
                _extend(*parse_podfile(f, root))

    if "rust" in ecosystems:
        for f in all_files:
            if f.name == "Cargo.toml":
                _extend(*parse_cargo_toml(f, root))

    if "go" in ecosystems:
        for f in all_files:
            if f.name == "go.mod":
                _extend(*parse_go_mod(f, root))

    if "ruby" in ecosystems:
        for f in all_files:
            if f.name == "Gemfile":
                _extend(*parse_gemfile(f, root))

    if "php" in ecosystems:
        for f in all_files:
            if f.name == "composer.json":
                _extend(*parse_composer_json(f, root))

    if "flutter" in ecosystems:
        for f in all_files:
            if f.name == "pubspec.yaml":
                _extend(*parse_pubspec_yaml(f, root))

    return all_fw, all_t


# ---------------------------------------------------------------------------
# Tier 4 — Platform scan (Option C): packaging, build tools, test markers, CI
# ---------------------------------------------------------------------------

_PACKAGING_MARKERS: list[tuple[list[str], str, str]] = [
    # Windows
    (["*.nsi", "*.nsis"],                               "NSIS",             "windows"),
    (["*.iss"],                                          "Inno Setup",       "windows"),
    (["*.wxs", "*.wixproj"],                             "WiX",              "windows"),
    (["*.msixmanifest", "Package.appxmanifest"],         "MSIX/AppX",        "windows"),
    (["*.application"],                                  "ClickOnce",        "windows"),
    # macOS
    (["*.pkgproj"],                                      "Packages (macOS)", "macos"),
    # Linux
    (["*.spec"],                                         "RPM Spec",         "linux"),
    (["debian/control"],                                 "DEB",              "linux"),
    # Cross-platform desktop app
    (["electron-builder.yml", "electron-builder.json"],  "Electron Builder", "cross"),
    (["tauri.conf.json"],                                "Tauri Config",     "cross"),
    (["wails.json"],                                     "Wails Config",     "cross"),
]

_BUILD_TOOL_MARKERS: list[tuple[list[str], str]] = [
    (["Makefile", "GNUmakefile"],               "Make"),
    (["CMakeLists.txt"],                        "CMake"),
    (["meson.build"],                           "Meson"),
    (["*.vcxproj"],                             "MSBuild (VC++)"),
    (["*.csproj", "*.sln"],                     "MSBuild (.NET)"),
    (["build.gradle", "build.gradle.kts"],      "Gradle"),
    (["pom.xml"],                               "Maven"),
    (["Rakefile"],                              "Rake"),
    (["Makefile.am", "configure.ac"],           "Autotools"),
    (["SConstruct", "SConscript"],              "SCons"),
    (["BUILD", "BUCK"],                         "Bazel/Buck"),
    (["Cargo.toml"],                            "Cargo"),
    (["go.mod"],                                "Go Modules"),
    (["pyproject.toml"],                        "Python build (pyproject)"),
    (["setup.py"],                              "Python build (setup.py)"),
    (["xmake.lua"],                             "xmake"),
]

_TEST_MARKER_FILES: list[tuple[list[str], str, str]] = [
    (["pytest.ini", "conftest.py"],             "pytest",       "Python"),
    (["jest.config.js", "jest.config.ts",
      "jest.config.mjs", "jest.config.cjs"],    "Jest",         "JavaScript"),
    (["vitest.config.ts", "vitest.config.js"],  "Vitest",       "TypeScript"),
    (["karma.conf.js", "karma.conf.ts"],        "Karma",        "JavaScript"),
    ([".rspec"],                                "RSpec",        "Ruby"),
    (["CTestTestfile.cmake"],                   "CTest",        "C++"),
]


def platform_scan(
    root: Path,
    all_files: list[Path],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Returns (packaging_tools, build_tools, test_frameworks_from_scan, build_ci)."""
    packaging: list[dict] = []
    build_tools: list[dict] = []
    test_fw: list[dict] = []
    build_ci: list[dict] = []

    file_names = {f.name for f in all_files}
    rel_paths = {_rel(f, root) for f in all_files}

    def _find(patterns: list[str]) -> list[str]:
        found = []
        for pat in patterns:
            for f in all_files:
                if _match_glob(f.name, pat):
                    found.append(_rel(f, root))
                    break
        return found

    # Packaging
    for patterns, name, platform in _PACKAGING_MARKERS:
        evidence = _find(patterns)
        if evidence:
            packaging.append({
                "name": name,
                "platform": platform,
                "confidence": "high",
                "evidence": evidence,
            })

    # Build tools (deduplicated by name)
    seen_build: set[str] = set()
    for patterns, name in _BUILD_TOOL_MARKERS:
        if name not in seen_build:
            evidence = _find(patterns)
            if evidence:
                seen_build.add(name)
                build_tools.append({
                    "name": name,
                    "confidence": "high",
                    "evidence": evidence[:3],
                })

    # Test frameworks from marker files
    for patterns, name, lang in _TEST_MARKER_FILES:
        evidence = _find(patterns)
        if evidence:
            test_fw.append({
                "name": name,
                "language": lang,
                "confidence": "medium",
                "evidence": evidence,
            })

    # Jenkins CI
    for f in all_files:
        if f.name == "Jenkinsfile":
            build_ci.append({
                "name": "Jenkins",
                "confidence": "high",
                "evidence": [_rel(f, root)],
            })
            break

    return packaging, build_tools, test_fw, build_ci


# ---------------------------------------------------------------------------
# Language list builder — merges Tier 1 (marker) + Tier 2 (census)
# ---------------------------------------------------------------------------

_ECOSYSTEM_TO_LANGUAGE: dict[str, str] = {
    "dotnet":   "C#",
    "cpp":      "C++",
    "nodejs":   "JavaScript/TypeScript",
    "python":   "Python",
    "java":     "Java",
    "swift":    "Swift",
    "rust":     "Rust",
    "go":       "Go",
    "ruby":     "Ruby",
    "php":      "PHP",
    "flutter":  "Dart",
    "elixir":   "Elixir",
}

_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_language_list(
    ecosystems: dict[str, list[str]],
    census_languages: list[dict],
) -> list[dict]:
    """
    Merge manifest-detected languages (high confidence) with census-derived
    ones (medium). Ecosystem markers take precedence.
    """
    manifest_langs: dict[str, str] = {
        _ECOSYSTEM_TO_LANGUAGE[eco]: eco
        for eco in ecosystems
        if eco in _ECOSYSTEM_TO_LANGUAGE
    }

    result: list[dict] = []
    for lang, eco in manifest_langs.items():
        result.append({
            "name": lang,
            "confidence": "high",
            "evidence": ecosystems[eco][:3],
        })

    existing_lower = {e["name"].lower() for e in result}
    # Merge census entries not already covered by manifest detection
    for entry in census_languages:
        name_lower = entry["name"].lower()
        # Skip if already present (exact or partial — e.g. "C#" vs "C#")
        if name_lower not in existing_lower and not any(
            name_lower in existing.lower() for existing in existing_lower
        ):
            result.append(entry)
            existing_lower.add(name_lower)

    result.sort(key=lambda x: (_CONFIDENCE_ORDER.get(x["confidence"], 3), x["name"]))
    return result


# ---------------------------------------------------------------------------
# Summary generator
# ---------------------------------------------------------------------------

def generate_summary(
    languages: list[dict],
    frameworks: list[dict],
    build_scripts: list[dict],
    packaging: list[dict],
    build_tools: list[dict],
    build_ci: list[dict],
) -> str:
    parts: list[str] = []

    # Group non-test frameworks by language
    lang_fw: dict[str, list[str]] = defaultdict(list)
    for fw in frameworks:
        if fw.get("category") != "test":
            lang = fw.get("language", "?")
            name = fw["name"]
            if name not in lang_fw[lang]:
                lang_fw[lang].append(name)

    for lang_entry in languages:
        lname = lang_entry["name"]
        fws = lang_fw.get(lname, [])
        if fws:
            parts.append(f"{lname} ({', '.join(fws[:3])})")
        else:
            parts.append(lname)

    if build_scripts:
        platforms = [s["platform"] for s in build_scripts]
        parts.append(f"Scripts: {'/'.join(platforms)}")

    if build_tools:
        parts.append(f"Build: {', '.join(t['name'] for t in build_tools[:4])}")

    if packaging:
        parts.append(f"Package: {', '.join(p['name'] for p in packaging[:3])}")

    if build_ci:
        parts.append(f"CI: {', '.join(c['name'] for c in build_ci)}")

    return " | ".join(parts) if parts else "Unknown stack"


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

def _dedup_by_name(items: list[dict]) -> list[dict]:
    """Deduplicate a list of dicts by 'name', keeping the highest confidence entry."""
    best: dict[str, dict] = {}
    for item in items:
        name = item["name"]
        if name not in best:
            best[name] = item
        elif _CONFIDENCE_ORDER.get(item["confidence"], 3) < _CONFIDENCE_ORDER.get(best[name]["confidence"], 3):
            best[name] = item
    return sorted(best.values(), key=lambda x: (_CONFIDENCE_ORDER.get(x["confidence"], 3), x["name"]))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def detect(repo_path: str, max_depth: int = DEFAULT_MAX_DEPTH) -> dict:
    root = Path(repo_path).resolve()

    if not root.exists():
        return {"error": f"Path does not exist: {repo_path}"}
    if not root.is_dir():
        return {"error": f"Not a directory: {repo_path}"}

    # Walk once — all tiers share this list
    all_files = list(_walk(root, max_depth))

    # Tier 1: Ecosystem markers (Option A)
    ecosystems = marker_scan(all_files, root)

    # Tier 2: Extension census + platform scripts (Option D)
    census = extension_census(all_files)
    census_languages = _derive_languages_from_census(census)
    build_scripts = _derive_build_scripts(all_files, root)

    # Tier 3: Manifest content parsing (Option B)
    frameworks_raw, tests_raw = run_manifest_parsers(root, ecosystems, all_files)

    # Tier 4: Platform scan — packaging, build tools, test markers, CI (Option C)
    packaging, build_tools, tests_from_scan, build_ci = platform_scan(root, all_files)

    # Merge and deduplicate test frameworks
    all_tests = _dedup_by_name(tests_raw + tests_from_scan)

    # Deduplicate frameworks (non-test)
    frameworks = _dedup_by_name(frameworks_raw)

    # Build language list (Tier 1 high-confidence + Tier 2 census fill-in)
    languages = build_language_list(ecosystems, census_languages)

    # Summary
    summary = generate_summary(languages, frameworks, build_scripts, packaging, build_tools, build_ci)

    return {
        "repo_path": str(root),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "languages": languages,
        "frameworks": frameworks,
        "build_scripts": build_scripts,
        "packaging_tools": packaging,
        "build_tools": build_tools,
        "test_frameworks": all_tests,
        "build_ci": build_ci,
        "summary": summary,
        "_meta": {
            "max_depth": max_depth,
            "total_files_scanned": len(all_files),
            "ecosystems_detected": list(ecosystems.keys()),
            "extension_census": dict(
                sorted(census.items(), key=lambda x: -x[1])[:30]  # top 30 extensions
            ),
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="detect_stack",
        description=(
            "Detect the technology stack of a repository and emit structured JSON.\n"
            "Output is suitable for downstream GitHub Copilot agents and skills."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository root (default: current directory)",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write JSON to FILE instead of stdout",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        metavar="N",
        help=f"Maximum directory depth to scan (default: {DEFAULT_MAX_DEPTH})",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="Emit compact single-line JSON (default: pretty-printed)",
    )

    args = parser.parse_args()

    result = detect(args.repo_path, max_depth=args.max_depth)

    indent = None if args.compact else 2
    json_output = json.dumps(result, indent=indent, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output, encoding="utf-8")
        print(f"Stack detection complete → {out_path}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
