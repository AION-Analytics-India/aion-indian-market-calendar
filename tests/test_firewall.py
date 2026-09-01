from pathlib import Path
import re

def test_import_firewall():
    """
    Ensure no files in the workspace (excluding venv, .git, etc.) contain
    references to the legacy dot-path 'projects.aion_indian_market_calendar'.
    """
    repo_root = Path(__file__).resolve().parents[3]
    forbidden_pattern = re.compile(r"projects\.aion_indian_market_calendar")
    
    matches = []
    ignore_dirs = {".git", "venv", ".pytest_cache", "__pycache__", ".github", ".gitlab"}
    ignore_files = {
        "REPO_RESTRUCTURE_LOG.md", 
        "implementation_plan.md", 
        "walkthrough.md",
        "CHANGELOG.md",
        "verify_release_ready.sh",
        "bump_version.sh",
        Path(__file__).name
    }
    
    allowed_extensions = {".py", ".md", ".json", ".yml", ".yaml", ".plist", ".sh", ".toml", ".cfg", ".txt"}
    
    for path in repo_root.rglob("*"):
        if any(part in ignore_dirs for part in path.parts):
            continue
        if path.name in ignore_files:
            continue
        if path.is_file() and path.suffix in allowed_extensions:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if forbidden_pattern.search(content):
                    matches.append(str(path.relative_to(repo_root)))
            except Exception:
                pass
                
    assert not matches, f"Import firewall regression detected! The following files reference legacy projects dot-path: {matches}"

def test_oss_boundary():
    """
    Ensure no production code in OSS/aion_indian_market_calendar/src/
    references the 'projects/' folder, except 'projects/archive/' (or archive/).
    """
    src_root = Path(__file__).resolve().parents[1] / "src"
    
    matches = []
    allowed_extensions = {".py", ".md", ".json", ".yml", ".yaml", ".plist", ".sh", ".toml", ".cfg", ".txt"}
    
    for path in src_root.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        if path.is_file() and path.suffix in allowed_extensions:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for match in re.finditer(r"projects/", content):
                    start_idx = match.start()
                    snippet = content[start_idx : start_idx + 30]
                    if not snippet.startswith("projects/archive"):
                        matches.append(f"{path.relative_to(src_root)} (snippet: '{snippet.strip()}')")
            except Exception:
                pass
                
    assert not matches, f"OSS boundary violation! Production code contains references to projects/: {matches}"
