#!/usr/bin/env python3
"""
archlens_parse.py — Parses an existing ARCHITECTURE*.md into structured JSON.

Used by ArchLens UPDATE MODE to extract what was previously documented, so the
model can compare it section-by-section against the current repo state instead
of doing a full re-analysis from scratch.

Usage:
  python archlens_parse.py <architecture_file.md> [--output <sections.json>]

  If --output is omitted, JSON is printed to stdout.

Output schema:
  {
    "source_file": "docs/ARCHITECTURE06052026.md",
    "generated_date": "06052026",           // extracted from filename, or null
    "sections": [
      {
        "heading": "1. Project Overview",
        "level": 2,                         // ## = 2, ### = 3, etc.
        "content": "...",                   // raw markdown text of this section
        "flags": {                          // quick-scan flags
          "has_mermaid": true,
          "has_warnings": false,           // ⚠️ present?
          "has_unused_flags": false        // 🗑️ present?
        }
      }
    ],
    "changelog_entries": [                  // parsed from ## Changelog if present
      {
        "date": "06052026",
        "items": ["[Changed] ...", "[Added] ..."]
      }
    ],
    "open_questions": [                     // bullet items under ## 10. Open Questions
      "Unresolved ambiguity about X"
    ]
  }
"""

import argparse
import json
import re
import sys
from pathlib import Path


DATE_PATTERN = re.compile(r"ARCHITECTURE(\d{8})\.md", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
CHANGELOG_DATE_PATTERN = re.compile(r"###\s+(\d{8})")
MERMAID_PATTERN = re.compile(r"```mermaid", re.IGNORECASE)
WARNING_FLAG = "⚠️"
UNUSED_FLAG = "🗑️"


def extract_date_from_filename(filepath: str) -> str | None:
    m = DATE_PATTERN.search(Path(filepath).name)
    return m.group(1) if m else None


def parse_sections(text: str) -> list[dict]:
    """
    Split markdown into sections by ## headings (level 2+).
    Returns list of section dicts in document order.
    """
    lines = text.splitlines(keepends=True)
    sections: list[dict] = []
    current_heading: str | None = None
    current_level: int = 0
    current_lines: list[str] = []

    def flush():
        if current_heading is not None:
            content = "".join(current_lines).strip()
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "content": content,
                "flags": {
                    "has_mermaid": bool(MERMAID_PATTERN.search(content)),
                    "has_warnings": WARNING_FLAG in content,
                    "has_unused_flags": UNUSED_FLAG in content,
                },
            })

    for line in lines:
        m = HEADING_PATTERN.match(line.rstrip())
        if m:
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            if level <= 2:
                # Top-level section boundary — flush previous
                flush()
                current_heading = heading_text
                current_level = level
                current_lines = []
            else:
                # Sub-heading — keep inside current section
                current_lines.append(line)
        else:
            current_lines.append(line)

    flush()  # flush last section
    return sections


def parse_changelog(sections: list[dict]) -> list[dict]:
    """Extract structured changelog entries from the Changelog section."""
    entries = []
    changelog_section = next(
        (s for s in sections if "changelog" in s["heading"].lower()), None
    )
    if not changelog_section:
        return entries

    current_date: str | None = None
    current_items: list[str] = []

    for line in changelog_section["content"].splitlines():
        date_match = CHANGELOG_DATE_PATTERN.search(line)
        if date_match:
            if current_date is not None:
                entries.append({"date": current_date, "items": current_items})
            current_date = date_match.group(1)
            current_items = []
        elif line.strip().startswith("-") and current_date:
            current_items.append(line.strip().lstrip("- ").strip())

    if current_date is not None:
        entries.append({"date": current_date, "items": current_items})

    return entries


def parse_open_questions(sections: list[dict]) -> list[str]:
    """Extract bullet items from the Open Questions section."""
    oq_section = next(
        (s for s in sections if "open question" in s["heading"].lower()), None
    )
    if not oq_section:
        return []
    questions = []
    for line in oq_section["content"].splitlines():
        stripped = line.strip()
        if stripped.startswith("-") or stripped.startswith("*"):
            item = stripped.lstrip("-* ").strip()
            if item:
                questions.append(item)
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse an ARCHITECTURE*.md file into structured JSON."
    )
    parser.add_argument("architecture_file", help="Path to the ARCHITECTURE*.md file")
    parser.add_argument(
        "--output",
        metavar="OUTPUT_FILE",
        help="Write JSON to this path instead of stdout",
    )
    args = parser.parse_args()

    src_path = Path(args.architecture_file)
    if not src_path.exists():
        print(f"ERROR: '{src_path}' not found", file=sys.stderr)
        sys.exit(1)

    text = src_path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    changelog_entries = parse_changelog(sections)
    open_questions = parse_open_questions(sections)

    result = {
        "source_file": str(src_path),
        "generated_date": extract_date_from_filename(str(src_path)),
        "sections": sections,
        "changelog_entries": changelog_entries,
        "open_questions": open_questions,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
