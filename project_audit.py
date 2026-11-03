
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

# =========================================================
# ACCESS ALGERIA - PROJECT AUDIT
# Read-only project scanner
# =========================================================

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "PROJECT_AUDIT_REPORT.md"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-comtrade",
    ".venv-marker",
    "venv",
    "__pycache__",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "site-packages",
}

EXCLUDED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".css", ".scss", ".json",
    ".yml", ".yaml", ".toml", ".ps1", ".sh",
}

DOC_EXTENSIONS = {".md", ".rst", ".txt"}
TEST_KEYWORDS = ("test", "spec")
CONFIG_FILES = {
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "requirements-dev.txt",
    "tsconfig.json",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.ts",
    "pytest.ini",
    "setup.cfg",
    "Dockerfile",
    ".gitignore",
}

TODO_MARKERS = (
    "TODO",
    "FIXME",
    "XXX",
    "NOT IMPLEMENTED",
    "IMPLEMENTATION PENDING",
)

def run_git(path, *args):
    """Run a read-only Git command."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None

def find_git_repositories():
    repositories = []

    for path in ROOT.rglob(".git"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue

        if path.is_dir() or path.is_file():
            repositories.append(path.parent)

    return sorted(set(repositories))

def collect_files():
    files = []

    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)

        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue

        if path.is_file() and path.name not in EXCLUDED_FILES:
            files.append(path)

    return sorted(files)

def scan_todos(files):
    findings = []

    for path in files:
        if path.suffix.lower() not in CODE_EXTENSIONS | DOC_EXTENSIONS:
            continue

        try:
            if path.stat().st_size > 2_000_000:
                continue

            content = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

            for line_number, line in enumerate(content.splitlines(), 1):
                upper_line = line.upper()

                for marker in TODO_MARKERS:
                    if marker in upper_line:
                        relative = path.relative_to(ROOT)
                        findings.append(
                            (str(relative), line_number, marker, line.strip())
                        )
                        break

        except (OSError, UnicodeError):
            continue

    return findings

def make_report():
    files = collect_files()
    repositories = find_git_repositories()

    extensions = Counter(
        path.suffix.lower() or "[no extension]"
        for path in files
    )

    documents = [
        path for path in files
        if path.suffix.lower() in DOC_EXTENSIONS
    ]

    tests = [
        path for path in files
        if any(word in path.name.lower() for word in TEST_KEYWORDS)
    ]

    configs = [
        path for path in files
        if path.name in CONFIG_FILES
    ]

    todos = scan_todos(files)

    lines = []

    def add(text=""):
        lines.append(text)

    add("# ACCESS ALGERIA - PROJECT AUDIT REPORT")
    add()
    add(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"**Project root:** `{ROOT}`")
    add("**Audit mode:** Read-only")
    add()
    add("---")
    add()
    add("## 1. Executive Summary")
    add()
    add(f"- Total files detected: **{len(files)}**")
    add(f"- Documentation files: **{len(documents)}**")
    add(f"- Test/spec-related files: **{len(tests)}**")
    add(f"- Configuration files: **{len(configs)}**")
    add(f"- Git repositories detected: **{len(repositories)}**")
    add(f"- TODO/FIXME markers detected: **{len(todos)}**")
    add()
    add("> Important: This automated scan identifies files and development")
    add("> indicators. It cannot independently prove that a feature works")
    add("> or that a project task is complete.")
    add()
    add("## 2. Completion Assessment")
    add()
    add("**Overall project completion: NOT DETERMINED**")
    add()
    add("A task must be assessed using implementation evidence, tests,")
    add("acceptance criteria, and verification results.")
    add()
    add("Recommended status vocabulary:")
    add()
    add("- IMPLEMENTED")
    add("- PARTIALLY IMPLEMENTED")
    add("- DESIGNED")
    add("- IN PROGRESS")
    add("- BLOCKED")
    add("- NOT STARTED")
    add("- NEEDS VERIFICATION")
    add()
    add("---")
    add()
    add("## 3. Project Structure")
    add()
    add("```text")
    add(ROOT.name + "/")

    top_level = sorted(ROOT.iterdir(), key=lambda p: p.name.lower())

    for item in top_level:
        if item.name in EXCLUDED_DIRS or item.name in EXCLUDED_FILES:
            continue

        if item.is_dir():
            add(f"  {item.name}/")
        else:
            add(f"  {item.name}")

    add("```")
    add()
    add("## 4. File Extension Statistics")
    add()
    add("| Extension | Number of files |")
    add("|---|---:|")

    for extension, count in extensions.most_common():
        add(f"| `{extension}` | {count} |")

    add()
    add("## 5. Documentation Inventory")
    add()

    if documents:
        for path in documents:
            add(f"- `{path.relative_to(ROOT)}`")
    else:
        add("- No documentation files detected.")

    add()
    add("## 6. Tests and Specifications")
    add()

    if tests:
        for path in tests:
            add(f"- `{path.relative_to(ROOT)}`")
    else:
        add("- No files with test/spec in their names were detected.")

    add()
    add("## 7. Configuration Files")
    add()

    if configs:
        for path in configs:
            add(f"- `{path.relative_to(ROOT)}`")
    else:
        add("- No recognized configuration files detected.")

    add()
    add("## 8. Git Repository Status")
    add()

    if repositories:
        for repo in repositories:
            add(f"### `{repo.relative_to(ROOT) or '.'}`")
            branch = run_git(repo, "branch", "--show-current")
            status = run_git(repo, "status", "--short")

            add(f"- Branch: `{branch or 'Unknown'}`")
            add("- Working tree:")

            if status:
                for entry in status.splitlines():
                    add(f"  - `{entry}`")
            else:
                add("  - No changes reported, or Git status unavailable.")

            add()
    else:
        add("No Git repositories detected.")

    add("## 9. TODO / FIXME Findings")
    add()

    if todos:
        for filename, line_number, marker, content in todos:
            add(f"- `{filename}:{line_number}` — **{marker}**")
            add(f"  - `{content[:250]}`")
    else:
        add("No recognized TODO/FIXME markers detected.")

    add()
    add("## 10. Files Inventory")
    add()

    for path in files:
        add(f"- `{path.relative_to(ROOT)}`")

    add()
    add("---")
    add()
    add("## 11. What This Audit Does Not Establish")
    add()
    add("- Whether the website runs correctly.")
    add("- Whether APIs connect successfully.")
    add("- Whether AI workflows are operational.")
    add("- Whether market intelligence data is accurate.")
    add("- Whether security controls are effective.")
    add("- Whether business requirements have been fulfilled.")
    add()
    add("## 12. Next Step")
    add()
    add("Create and maintain an IMPLEMENTATION_REGISTER.md containing:")
    add()
    add("| Task ID | Component | Status | Evidence | Owner |")
    add("|---|---|---|---|---|")
    add("| AA-001 | Example component | NEEDS VERIFICATION | Test or file reference | Claude |")
    add()
    add("Only mark a task IMPLEMENTED after its acceptance criteria")
    add("have been verified.")
    add()

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=" * 55)
    print("ACCESS ALGERIA PROJECT AUDIT COMPLETED")
    print("=" * 55)
    print(f"Project: {ROOT}")
    print(f"Files scanned: {len(files)}")
    print(f"Repositories found: {len(repositories)}")
    print(f"TODO/FIXME findings: {len(todos)}")
    print()
    print(f"Report created: {REPORT}")
    print("=" * 55)

if __name__ == "__main__":
    make_report()
