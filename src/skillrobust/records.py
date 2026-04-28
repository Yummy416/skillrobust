from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".sh",
    ".ps1",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
}

DEFAULT_MAX_FILE_BYTES = 256_000


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_role(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name == "skill.md":
        return "skill_md"
    if normalized.startswith("scripts/") or normalized.endswith((".py", ".sh", ".ps1")):
        return "script"
    if normalized.startswith(("references/", "docs/")):
        return "reference"
    if name in {"readme.md", "readme.txt"}:
        return "repo_context"
    if normalized.startswith(("assets/", "templates/")):
        return "asset"
    return "other"


def is_text_candidate(path: Path) -> bool:
    if path.name.startswith(".") and path.suffix not in TEXT_SUFFIXES:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.upper() == "SKILL.MD"


def read_text_safely(path: Path, max_bytes: int) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def load_skill_package(root: Path, *, sample_id: str | None = None, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> dict[str, Any]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Skill package directory does not exist: {root}")

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_text_candidate(path):
            continue
        content = read_text_safely(path, max_file_bytes)
        if content is None:
            continue
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "role": infer_role(rel), "content": content})

    if not files:
        raise ValueError(f"No readable text files found under: {root}")

    skill_md = next((item for item in files if item["role"] == "skill_md"), None)
    frontmatter = {}
    if skill_md:
        frontmatter = parse_frontmatter(skill_md["content"])

    return {
        "sample_id": sample_id or root.name,
        "split": "ad_hoc",
        "subset": "unknown",
        "source": {"source_kind": "local_package", "local_path": str(root)},
        "skill": {
            "root_path": str(root),
            "frontmatter": frontmatter,
            "files": files,
        },
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values
