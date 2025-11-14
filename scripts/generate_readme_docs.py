import re
from pathlib import Path


def extract_section(markdown_content: str, section_title: str) -> str:
    """
    Extracts a section from markdown content based on its title.
    Assumes section titles are H2 (##) and sections end at the next H2 or end of file.
    """
    # Escape special characters in the section title for regex
    escaped_title = re.escape(section_title)

    # Regex to find the section:
    # - Starts with "## Section Title"
    # - Captures everything until the next "## " or end of string
    pattern = re.compile(
        rf"## {escaped_title}\n(.*?)(?=\n## |\Z)", re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(markdown_content)
    if match:
        content = match.group(1).strip()

        # Remove Markdown image syntax: ![]()
        content = re.sub(r"!\[.*?\]\(.*?\)", "", content)

        # Remove <details> blocks and their content
        content = re.sub(
            r"<details>.*?</details>", "", content, flags=re.DOTALL | re.IGNORECASE
        )

        return content
    return ""


def extract_intro(markdown_content: str) -> str:
    """
    Extracts the content before the first H2 heading.
    """
    pattern = re.compile(r"^(.*?)(?=\n## |\Z)", re.DOTALL)
    match = pattern.search(markdown_content)
    if match:
        content = match.group(1).strip()
        # Remove Markdown image syntax: ![]()
        content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
        return content
    return ""


def generate_readme_docs(readme_path: Path, output_dir: Path):
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()

    # Generate intro.md
    intro_content = extract_intro(readme_content)
    if intro_content:
        intro_frontmatter = "---\ntitle: Welcome\n---\n\n"
        (output_dir / "intro.md").write_text(
            intro_frontmatter + intro_content, encoding="utf-8"
        )
        print("Generated intro.md from README.md")
    else:
        print("Warning: Intro section not found in README.md")

    sections_to_extract = {
        "Features": "features.md",
        "Installation (for End-Users)": "installation-end-users.md",
        "Advanced Installation (Docker)": "installation-docker.md",
        "Development Setup": "development-setup.md",
        "Production and Release": "production-release.md",
        "APIs Used": "apis-used.md",
    }

    for title, filename in sections_to_extract.items():
        content = extract_section(readme_content, title)
        if content:
            # Add a frontmatter for Docusaurus
            frontmatter = f"---\ntitle: {title}\n---\n\n"
            (output_dir / filename).write_text(frontmatter + content, encoding="utf-8")
            print(f"Generated {filename} from README.md")
        else:
            print(f"Warning: Section '{title}' not found in README.md")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    readme_file = project_root / "README.md"
    docs_output_dir = project_root / "docs" / "docs"  # Output to docs/docs directory

    if not docs_output_dir.exists():
        docs_output_dir.mkdir(parents=True)

    generate_readme_docs(readme_file, docs_output_dir)
