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


def mean_absolute(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(abs(value) for value in values) / len(values)


def find_section(review: dict[str, Any], truth_section: dict[str, Any]) -> dict[str, Any]:
    truth_id = str(truth_section.get("id", "")).strip().lower()
    truth_label = str(truth_section.get("label", "")).strip().lower()

    for section in review.get("sections", []):
        review_id = str(section.get("id", "")).strip().lower()

        if review_id == truth_id:
            return section

    for section in review.get("sections", []):
        review_label = str(section.get("label", "")).strip().lower()

        if review_label == truth_label:
            return section

    raise ValueError(f"Could not find section {truth_section.get('label')} in review JSON.")


def compare_truth_to_review(
    review: dict[str, Any],
    truth: dict[str, Any],
    review_name: str,
    truth_name: str,
) -> dict[str, Any]:
    truth_section = truth.get("section")

    if not isinstance(truth_section, dict):
        raise ValueError(f"{truth_name} does not contain a section object.")

    review_section = find_section(review, truth_section)

    review_lines = {
        line.get("id"): line
        for line in review_section.get("lines", [])
        if isinstance(line, dict)
    }

    comparisons: list[dict[str, Any]] = []

    for truth_line in truth_section.get("lines", []):
        line_id = truth_line.get("id")
        review_line = review_lines.get(line_id)

        if not review_line:
            comparisons.append(
                {
                    "line_id": line_id,
                    "text": truth_line.get("text", ""),
                    "status": "missing_from_review",
                }
            )
            continue

        review_start = as_float(review_line.get("start"))
        review_end = as_float(review_line.get("end"))
        truth_start = as_float(truth_line.get("start"))
        truth_end = as_float(truth_line.get("end"))

        start_error = review_start - truth_start
        end_error = review_end - truth_end
        duration_error = (review_end - review_start) - (truth_end - truth_start)

        comparisons.append(
            {
                "line_id": line_id,
                "text": truth_line.get("text", ""),
                "status": "compared",
                "review_start": round_time(review_start),
                "truth_start": round_time(truth_start),
                "start_error_seconds": round_time(start_error),
                "review_end": round_time(review_end),
                "truth_end": round_time(truth_end),
                "end_error_seconds": round_time(end_error),
                "review_duration": round_time(review_end - review_start),
                "truth_duration": round_time(truth_end - truth_start),
                "duration_error_seconds": round_time(duration_error),
            }
        )

    compared = [item for item in comparisons if item.get("status") == "compared"]

    start_errors = [as_float(item.get("start_error_seconds")) for item in compared]
    end_errors = [as_float(item.get("end_error_seconds")) for item in compared]
    duration_errors = [as_float(item.get("duration_error_seconds")) for item in compared]

    catastrophic_start_errors = [
        item
        for item in compared
        if abs(as_float(item.get("start_error_seconds"))) >= 1.0
    ]

    catastrophic_end_errors = [
        item
        for item in compared
        if abs(as_float(item.get("end_error_seconds"))) >= 2.0
    ]

    return {
        "review_name": review_name,
        "truth_name": truth_name,
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
            "catastrophic_start_error_count": len(catastrophic_start_errors),
            "catastrophic_end_error_count": len(catastrophic_end_errors),
        },
        "comparisons": comparisons,
    }


def collect_truth_files(truth_dir: Path) -> list[Path]:
    truth_files = sorted(truth_dir.glob("manual-truth-*.json"))

    if not truth_files:
        raise FileNotFoundError(f"No manual truth files found in {truth_dir}")

    return truth_files


def collect_review_files(review_paths: list[str]) -> list[Path]:
    paths = [Path(value).resolve() for value in review_paths]

    for path in paths:
        require_file(path, "Review JSON")

    return paths


def build_lab_report(
    truth_dir: Path,
    review_paths: list[Path],
) -> dict[str, Any]:
    truth_files = collect_truth_files(truth_dir)

    truth_items = [
        {
            "path": path,
            "name": path.stem,
            "json": load_json(path),
        }
        for path in truth_files
    ]

    review_items = [
        {
            "path": path,
            "name": path.stem,
            "json": load_json(path),
        }
        for path in review_paths
    ]

    all_results: list[dict[str, Any]] = []

    for review_item in review_items:
        for truth_item in truth_items:
            try:
                result = compare_truth_to_review(
                    review=review_item["json"],
                    truth=truth_item["json"],
                    review_name=review_item["name"],
                    truth_name=truth_item["name"],
                )
                all_results.append(result)
            except Exception as error:
                all_results.append(
                    {
                        "review_name": review_item["name"],
                        "truth_name": truth_item["name"],
                        "status": "failed",
                        "error": str(error),
                    }
                )

    grouped: dict[str, list[dict[str, Any]]] = {}

    for result in all_results:
        grouped.setdefault(result["review_name"], []).append(result)

    overall_results: list[dict[str, Any]] = []

    for review_name, results in grouped.items():
        compared_results = [
            result
            for result in results
            if result.get("status") != "failed"
        ]

        start_errors = [
            as_float(result["summary"]["mean_absolute_start_error_seconds"])
            for result in compared_results
        ]

        end_errors = [
            as_float(result["summary"]["mean_absolute_end_error_seconds"])
            for result in compared_results
        ]

        duration_errors = [
            as_float(result["summary"]["mean_absolute_duration_error_seconds"])
            for result in compared_results
        ]

        catastrophic_start_count = sum(
            int(result["summary"]["catastrophic_start_error_count"])
            for result in compared_results
        )

        catastrophic_end_count = sum(
            int(result["summary"]["catastrophic_end_error_count"])
            for result in compared_results
        )

        overall_results.append(
            {
                "review_name": review_name,
                "truth_sections_compared": len(compared_results),
                "failed_truth_sections": len(results) - len(compared_results),
                "overall_mean_start_error_seconds": round_time(mean_absolute(start_errors)),
                "overall_mean_end_error_seconds": round_time(mean_absolute(end_errors)),
                "overall_mean_duration_error_seconds": round_time(mean_absolute(duration_errors)),
                "catastrophic_start_error_count": catastrophic_start_count,
                "catastrophic_end_error_count": catastrophic_end_count,
            }
        )

    overall_results.sort(
        key=lambda item: (
            item["catastrophic_start_error_count"],
            item["overall_mean_start_error_seconds"],
            item["catastrophic_end_error_count"],
            item["overall_mean_end_error_seconds"],
        )
    )

    return {
        "schema_version": "kara-alignment-lab-report-v1",
        "truth_dir": str(truth_dir),
        "truth_files": [str(item["path"]) for item in truth_items],
        "review_files": [str(item["path"]) for item in review_items],
        "overall_results": overall_results,
        "section_results": all_results,
    }


def print_lab_report(report: dict[str, Any]) -> None:
    print("")
    print("Alignment lab results")
    print("")

    for index, item in enumerate(report["overall_results"], start=1):
        print(f"{index}. {item['review_name']}")
        print(f"   Truth sections compared: {item['truth_sections_compared']}")
        print(f"   Failed truth sections:    {item['failed_truth_sections']}")
        print(f"   Mean start error:         {item['overall_mean_start_error_seconds']}s")
        print(f"   Mean end error:           {item['overall_mean_end_error_seconds']}s")
        print(f"   Mean duration error:      {item['overall_mean_duration_error_seconds']}s")
        print(f"   Catastrophic starts:      {item['catastrophic_start_error_count']}")
        print(f"   Catastrophic ends:        {item['catastrophic_end_error_count']}")
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate multiple alignment review JSON files against manual truth files."
    )

    parser.add_argument(
        "--truth-dir",
        required=True,
        help="Folder containing manual-truth-*.json files.",
    )

    parser.add_argument(
        "--review",
        required=True,
        action="append",
        help="A word review JSON file to evaluate. Repeat this argument for multiple files.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the lab report JSON should be written.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    truth_dir = Path(args.truth_dir).resolve()
    output_path = Path(args.out).resolve()

    try:
        if not truth_dir.exists():
            raise FileNotFoundError(f"Truth directory does not exist: {truth_dir}")

        review_paths = collect_review_files(args.review)

        report = build_lab_report(
            truth_dir=truth_dir,
            review_paths=review_paths,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print_lab_report(report)
        print(f"Lab report written to: {output_path}")
        print("")

    except Exception as error:
        print("")
        print("Could not evaluate alignment lab.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())