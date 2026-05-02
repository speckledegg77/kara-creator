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


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def round_time(value: float) -> float:
    return round(float(value), 3)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_draft_section(draft: dict[str, Any], truth_section: dict[str, Any]) -> dict[str, Any]:
    truth_id = truth_section.get("id")
    truth_label = truth_section.get("label")

    for section in draft.get("sections", []):
        if section.get("id") == truth_id:
            return section

    for section in draft.get("sections", []):
        if str(section.get("label", "")).strip().lower() == str(truth_label).strip().lower():
            return section

    raise ValueError(
        f"Could not find matching section in draft for truth section: {truth_label}"
    )


def compare_lines(
    draft_section: dict[str, Any],
    truth_section: dict[str, Any],
) -> list[dict[str, Any]]:
    draft_lines = {
        line.get("id"): line
        for line in draft_section.get("lines", [])
        if isinstance(line, dict)
    }

    comparisons: list[dict[str, Any]] = []

    for truth_line in truth_section.get("lines", []):
        line_id = truth_line.get("id")
        draft_line = draft_lines.get(line_id)

        if not draft_line:
            comparisons.append(
                {
                    "line_id": line_id,
                    "text": truth_line.get("text", ""),
                    "status": "missing-from-draft",
                }
            )
            continue

        draft_start = as_float(draft_line.get("start"))
        draft_end = as_float(draft_line.get("end"))
        truth_start = as_float(truth_line.get("start"))
        truth_end = as_float(truth_line.get("end"))

        start_error = draft_start - truth_start
        end_error = draft_end - truth_end
        duration_error = (draft_end - draft_start) - (truth_end - truth_start)

        comparisons.append(
            {
                "line_id": line_id,
                "text": truth_line.get("text", ""),
                "status": "compared",
                "draft_start": round_time(draft_start),
                "truth_start": round_time(truth_start),
                "start_error_seconds": round_time(start_error),
                "draft_end": round_time(draft_end),
                "truth_end": round_time(truth_end),
                "end_error_seconds": round_time(end_error),
                "draft_duration": round_time(draft_end - draft_start),
                "truth_duration": round_time(truth_end - truth_start),
                "duration_error_seconds": round_time(duration_error),
            }
        )

    return comparisons


def mean_absolute(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(abs(value) for value in values) / len(values)


def build_report(
    draft_path: Path,
    truth_path: Path,
    draft: dict[str, Any],
    truth: dict[str, Any],
) -> dict[str, Any]:
    truth_section = truth.get("section")

    if not isinstance(truth_section, dict):
        raise ValueError("Truth JSON does not contain a valid section object.")

    draft_section = find_draft_section(draft, truth_section)
    comparisons = compare_lines(draft_section, truth_section)

    compared = [
        item
        for item in comparisons
        if item.get("status") == "compared"
    ]

    start_errors = [
        as_float(item.get("start_error_seconds"))
        for item in compared
    ]

    end_errors = [
        as_float(item.get("end_error_seconds"))
        for item in compared
    ]

    duration_errors = [
        as_float(item.get("duration_error_seconds"))
        for item in compared
    ]

    report = {
        "schema_version": "karaoke-comparison-report-v1",
        "draft_file": str(draft_path),
        "truth_file": str(truth_path),
        "section": {
          "id": truth_section.get("id"),
          "label": truth_section.get("label"),
        },
        "summary": {
            "lines_in_truth": len(truth_section.get("lines", [])),
            "lines_compared": len(compared),
            "mean_absolute_start_error_seconds": round_time(mean_absolute(start_errors)),
            "mean_absolute_end_error_seconds": round_time(mean_absolute(end_errors)),
            "mean_absolute_duration_error_seconds": round_time(mean_absolute(duration_errors)),
        },
        "comparisons": comparisons,
    }

    return report


def print_human_summary(report: dict[str, Any]) -> None:
    section = report["section"]
    summary = report["summary"]

    print("")
    print(f"Comparison for section: {section.get('label')}")
    print("")
    print(f"Lines compared: {summary['lines_compared']} of {summary['lines_in_truth']}")
    print(f"Mean absolute start error:    {summary['mean_absolute_start_error_seconds']}s")
    print(f"Mean absolute end error:      {summary['mean_absolute_end_error_seconds']}s")
    print(f"Mean absolute duration error: {summary['mean_absolute_duration_error_seconds']}s")
    print("")
    print("Line details:")
    print("")

    for item in report["comparisons"]:
        if item.get("status") != "compared":
            print(f"{item.get('line_id')}: {item.get('status')}")
            continue

        print(
            f"{item['line_id']} | "
            f"start error {item['start_error_seconds']}s | "
            f"end error {item['end_error_seconds']}s | "
            f"duration error {item['duration_error_seconds']}s | "
            f"{item['text']}"
        )

    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare generated karaoke draft timings against manually timed source-of-truth timings."
    )

    parser.add_argument(
        "--draft",
        required=True,
        help="Path to generated draft JSON.",
    )

    parser.add_argument(
        "--truth",
        required=True,
        help="Path to manually timed truth JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where comparison report JSON should be written.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    truth_path = Path(args.truth).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(draft_path, "Draft JSON")
        require_file(truth_path, "Truth JSON")

        draft = load_json(draft_path)
        truth = load_json(truth_path)

        report = build_report(
            draft_path=draft_path,
            truth_path=truth_path,
            draft=draft,
            truth=truth,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print_human_summary(report)
        print(f"Comparison report written to: {output_path}")
        print("")

    except Exception as error:
        print("")
        print("Could not compare draft against truth.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())