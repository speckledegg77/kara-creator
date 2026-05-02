from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def round_time(value: float) -> float:
    return round(float(value), 3)


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes:02d}:{remaining:06.3f}"


def flatten_lines(review: dict[str, Any]) -> list[dict[str, Any]]:
    flat_lines: list[dict[str, Any]] = []

    for section in review.get("sections", []):
        for line in section.get("lines", []):
            words = line.get("words", [])

            if not words:
                continue

            first_word = words[0]
            last_word = words[-1]

            flat_lines.append(
                {
                    "section": section.get("label", ""),
                    "line_id": line.get("id", ""),
                    "text": line.get("text", ""),
                    "start": as_float(line.get("start")),
                    "end": as_float(line.get("end")),
                    "first_word": first_word.get("text", ""),
                    "first_word_start": as_float(first_word.get("start")),
                    "last_word": last_word.get("text", ""),
                    "last_word_end": as_float(last_word.get("end")),
                    "word_count": len(words),
                }
            )

    flat_lines.sort(key=lambda item: item["start"])

    return flat_lines


def inspect_lines(lines: list[dict[str, Any]], overlap_tolerance: float, long_gap_threshold: float) -> dict[str, Any]:
    boundary_reports: list[dict[str, Any]] = []

    for index, line in enumerate(lines[:-1]):
        next_line = lines[index + 1]

        line_end = line["end"]
        next_start = next_line["start"]

        gap = next_start - line_end

        if gap < -overlap_tolerance:
            status = "overlap"
        elif gap > long_gap_threshold:
            status = "long_gap"
        else:
            status = "ok"

        boundary_reports.append(
            {
                "status": status,
                "from_line": line["line_id"],
                "from_text": line["text"],
                "from_section": line["section"],
                "from_end": round_time(line_end),
                "from_end_readable": format_time(line_end),
                "from_last_word": line["last_word"],
                "to_line": next_line["line_id"],
                "to_text": next_line["text"],
                "to_section": next_line["section"],
                "to_start": round_time(next_start),
                "to_start_readable": format_time(next_start),
                "to_first_word": next_line["first_word"],
                "gap_seconds": round_time(gap),
            }
        )

    overlaps = [item for item in boundary_reports if item["status"] == "overlap"]
    long_gaps = [item for item in boundary_reports if item["status"] == "long_gap"]

    return {
        "line_count": len(lines),
        "boundary_count": len(boundary_reports),
        "overlap_count": len(overlaps),
        "long_gap_count": len(long_gaps),
        "boundary_reports": boundary_reports,
    }


def print_report(report: dict[str, Any], only_problems: bool) -> None:
    print("")
    print("Word review timing inspection")
    print("")
    print(f"Lines:       {report['line_count']}")
    print(f"Boundaries:  {report['boundary_count']}")
    print(f"Overlaps:    {report['overlap_count']}")
    print(f"Long gaps:   {report['long_gap_count']}")
    print("")

    for item in report["boundary_reports"]:
        if only_problems and item["status"] == "ok":
            continue

        status = item["status"].upper()

        print(
            f"{status}: {item['from_line']} → {item['to_line']} | "
            f"gap {item['gap_seconds']}s"
        )
        print(
            f"  {item['from_section']} | {item['from_line']} ends at "
            f"{item['from_end_readable']} after '{item['from_last_word']}'"
        )
        print(
            f"  {item['to_section']} | {item['to_line']} starts at "
            f"{item['to_start_readable']} on '{item['to_first_word']}'"
        )
        print(f"  From: {item['from_text']}")
        print(f"  To:   {item['to_text']}")
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect line boundaries in a word review JSON."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to word review JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where inspection report JSON should be written.",
    )

    parser.add_argument(
        "--overlap-tolerance-ms",
        type=int,
        default=50,
        help="Allowed tiny overlap before warning. Default: 50ms.",
    )

    parser.add_argument(
        "--long-gap-threshold-ms",
        type=int,
        default=2500,
        help="Gap size that should be reported as long. Default: 2500ms.",
    )

    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show every boundary, not just problems.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(input_path, "Input word review JSON")

        review = load_json(input_path)
        lines = flatten_lines(review)

        if not lines:
            raise ValueError("No lines were found in the word review JSON.")

        report = inspect_lines(
            lines=lines,
            overlap_tolerance=args.overlap_tolerance_ms / 1000,
            long_gap_threshold=args.long_gap_threshold_ms / 1000,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print_report(report, only_problems=not args.show_all)

        print(f"Inspection report written to: {output_path}")
        print("")

    except Exception as error:
        print("")
        print("Could not inspect word review timings.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())