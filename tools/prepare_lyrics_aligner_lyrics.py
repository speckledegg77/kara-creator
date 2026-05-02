from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def clean_line(line: str) -> str:
    line = line.strip()
    line = line.replace("’", "'")
    line = re.sub(r"\s+", " ", line)
    return line


def prepare_lyrics(input_path: Path, output_path: Path) -> None:
    require_file(input_path, "Input lyrics file")

    output_lines: list[str] = []

    for raw_line in input_path.read_text(encoding="utf-8-sig").splitlines():
        line = clean_line(raw_line)

        if not line:
            continue

        if line.startswith("#"):
            continue

        if re.match(r"^\[.+?\]$", line):
            continue

        output_lines.append(line)

    if not output_lines:
        raise ValueError("No lyric lines were found after removing headings.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    print("")
    print("Clean lyrics prepared for lyrics-aligner.")
    print(f"Output: {output_path}")
    print(f"Lines:  {len(output_lines)}")
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare clean lyrics for the singing-specific lyrics-aligner test."
    )

    parser.add_argument("--input", required=True, help="Path to source lyrics TXT.")
    parser.add_argument("--out", required=True, help="Path to clean output lyrics TXT.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        prepare_lyrics(
            input_path=Path(args.input).resolve(),
            output_path=Path(args.out).resolve(),
        )
    except Exception as error:
        print("")
        print("Could not prepare lyrics.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())