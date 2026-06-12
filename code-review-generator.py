import argparse
import json
import os
from pathlib import Path

# -----------------------------
# Utility functions
# -----------------------------

def read_template(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None

def warn(msg: str):
    print(f"[WARN] {msg}")

def info(msg: str):
    print(f"[INFO] {msg}")

# -----------------------------
# Main generator logic
# -----------------------------

def generate_skill(stack_path: Path, repo_path: Path, templates_root: Path):
    # Load stack.json
    if not stack_path.exists():
        raise FileNotFoundError(f"stack.json not found at: {stack_path}")

    stack = json.loads(stack_path.read_text(encoding="utf-8"))

    languages = [l["name"] for l in stack.get("languages", [])]
    frameworks = [f["name"] for f in stack.get("frameworks", [])]
    build_tools = [b["name"] for b in stack.get("build_tools", [])]

    info(f"Detected languages: {languages}")
    info(f"Detected frameworks: {frameworks}")
    info(f"Detected build tools: {build_tools}")

    # Output directory
    skill_dir = repo_path / ".github" / "skills" / "code-review"
    skill_dir.mkdir(parents=True, exist_ok=True)

    output_file = skill_dir / "SKILL.md"

    # -----------------------------
    # Build SKILL.md content
    # -----------------------------
    content = []

    # YAML frontmatter
    content.append("---")
    content.append("name: code-review")
    content.append("description: Repository-specific code review skill generated from stack.json.")
    content.append("---\n")

    # Global header
    header = read_template(templates_root / "global" / "header.md")
    if header:
        content.append(header)
    else:
        warn("Missing global/header.md")

    # Review process
    review_process = read_template(templates_root / "global" / "review_process.md")
    if review_process:
        content.append(review_process)
    else:
        warn("Missing global/review_process.md")

    # -----------------------------
    # Language templates
    # -----------------------------
    content.append("\n## Language-Specific Guidelines\n")

    for lang in languages:
        normalized = lang.lower().replace("#", "sharp").replace("++", "pp")
        template_path = templates_root / "languages" / f"{normalized}.md"
        template = read_template(template_path)

        if template:
            content.append(template)
        else:
            warn(f"No template found for language: {lang}")

    # -----------------------------
    # Framework templates
    # -----------------------------
    content.append("\n## Framework Guidelines\n")

    for fw in frameworks:
        normalized = fw.lower().replace(" ", "_").replace("sdk", "")
        template_path = templates_root / "frameworks" / f"{normalized}.md"
        template = read_template(template_path)

        if template:
            content.append(template)
        else:
            warn(f"No template found for framework: {fw}")

    # -----------------------------
    # Build tool templates
    # -----------------------------
    content.append("\n## Build Tool Guidelines\n")

    for bt in build_tools:
        normalized = bt.lower().replace(" ", "_")
        template_path = templates_root / "build_tools" / f"{normalized}.md"
        template = read_template(template_path)

        if template:
            content.append(template)
        else:
            warn(f"No template found for build tool: {bt}")

    # -----------------------------
    # Footer
    # -----------------------------
    footer = read_template(templates_root / "global" / "footer.md")
    if footer:
        content.append(footer)
    else:
        warn("Missing global/footer.md")

    # Write SKILL.md
    output_file.write_text("\n".join(content), encoding="utf-8")
    info(f"Generated skill at: {output_file}")


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Copilot code-review skill")
    parser.add_argument("--stack", help="Path to stack.json", required=False)
    parser.add_argument("--repo", help="Path to target repository", required=True)

    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()

    # Determine stack.json location
    if args.stack:
        stack_path = Path(args.stack).resolve()
    else:
        stack_path = repo_path / "stack.json"

    templates_root = Path(__file__).parent / "templates"

    generate_skill(stack_path, repo_path, templates_root)


if __name__ == "__main__":
    main()
