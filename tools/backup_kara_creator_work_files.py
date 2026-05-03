from __future__ import annotations

import argparse
import datetime as dt
import zipfile
from pathlib import Path


SAFE_ROOT_FILES = [
    "README.md",
    ".gitignore",
]

SAFE_FOLDERS = [
    "tools",
    "docs",
    "config",
]

EXCLUDED_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
}


def should_include(path: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False

    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False

    return path.is_file()


def add_file(zip_file: zipfile.ZipFile, project_root: Path, path: Path) -> None:
    if should_include(path):
        zip_file.write(path, path.relative_to(project_root))


def create_backup(project_root: Path, output_dir: Path) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"kara-creator-source-backup-{timestamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for root_file in SAFE_ROOT_FILES:
            path = project_root / root_file
            if path.exists():
                add_file(zip_file, project_root, path)

        for folder in SAFE_FOLDERS:
            folder_path = project_root / folder
            if not folder_path.exists():
                continue

            for path in folder_path.rglob("*"):
                add_file(zip_file, project_root, path)

    return zip_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a safe source-code backup zip for Kara Creator."
    )

    parser.add_argument(
        "--out-dir",
        default="backups",
        help="Folder where the backup zip should be created. Default: backups",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output_dir = (project_root / args.out_dir).resolve()
    zip_path = create_backup(project_root, output_dir)

    print("")
    print("Backup created.")
    print(zip_path)
    print("")
    print("This backup includes source files from tools, docs, config, README.md, and .gitignore.")
    print("It does not include incoming audio, generated outputs, or alignment run folders.")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
