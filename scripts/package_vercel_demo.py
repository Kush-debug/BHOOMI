"""Create a clean source archive ready for GitHub and Vercel import."""

import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "bhoomi-ai-vercel-demo.zip"
SKIP_DIRS = {
    ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    "node_modules", "dist", "dist-ssr", "venv", ".venv", "env", "uploads",
}
SKIP_FILES = {".dev_secret", OUTPUT.name}
SKIP_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc", ".log"}


def include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if path.name in SKIP_FILES or path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    return path.is_file()


def main() -> None:
    files = []
    for current, directories, names in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        for name in names:
            candidate = Path(current) / name
            if include(candidate):
                files.append(candidate)
    prefix = "bhoomi-ai-vercel-demo"
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED, compresslevel=8) as archive:
        for path in files:
            archive.write(path, Path(prefix) / path.relative_to(ROOT))
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes; {len(files)} files)")


if __name__ == "__main__":
    main()
