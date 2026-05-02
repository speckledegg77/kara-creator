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


def round_time(value: float) -> float:
    return round(float(value), 3)


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_draft_section(draft: dict[str, Any], truth_section: dict[str, Any]) -> dict[str, Any]:
    truth_id = truth_section.get("id")
    truth_label = str(truth_section.get("label", "")).strip().lower()

    for section in draft.get("sections", []):
        if section.get("id") == truth_id:
            return section

    for section in draft.get("sections", []):
        draft_label = str(section.get("label", "")).strip().lower()

        if draft_label == truth_label:
            return section

    raise ValueError(f"Could not find matching draft section for: {truth_section.get('label')}")


def get_regions_inside_bounds(
    draft: dict[str, Any],
    section_start: float,
    section_end: float,
    edge_tolerance_seconds: float,
) -> list[dict[str, Any]]:
    regions = draft.get("raw_audio_regions", [])

    if not isinstance(regions, list):
        return []

    matching_regions: list[dict[str, Any]] = []

    lower_bound = section_start - edge_tolerance_seconds
    upper_bound = section_end + edge_tolerance_seconds

    for region in regions:
        start = as_float(region.get("start"))
        end = as_float(region.get("end"))

        overlaps = end >= lower_bound and start <= upper_bound

        if overlaps:
            matching_regions.append(region)

    matching_regions.sort(key=lambda item: as_float(item.get("start")))

    return matching_regions


def choose_region_indexes(region_count: int, line_count: int) -> list[int]:
    if line_count <= 0:
        return []

    if region_count <= 0:
        return []

    if line_count == 1:
        return [0]

    if region_count < line_count:
        return list(range(region_count))

    chosen: list[int] = []
    previous = -1

    for line_index in range(line_count):
        raw_index = round(line_index * (region_count - 1) / (line_count - 1))

        min_allowed = previous + 1
        max_allowed = region_count - (line_count - line_index)

        index = max(min_allowed, min(raw_index, max_allowed))

        chosen.append(index)
        previous = index

    return chosen


def evenly_space_section(
    lines: list[dict[str, Any]],
    section_start: float,
    section_end: float,
    line_end_gap_seconds: float,
) -> list[dict[str, Any]]:
    line_count = len(lines)

    if line_count == 0:
        return []

    duration = max(0.1, section_end - section_start)
    slot = duration / line_count

    mapped_lines: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        start = section_start + index * slot

        if index < line_count - 1:
            end = section_start + (index + 1) * slot - line_end_gap_seconds
        else:
            end = section_end

        if end <= start:
            end = start + 0.1

        mapped_lines.append(
            {
                **line,
                "start": round_time(start),
                "end": round_time(end),
                "timing_source": "section-even-fallback",
                "selected_region_id": None,
                "selected_region_start": None,
            }
        )

    return mapped_lines


def map_lines_using_regions(
    lines: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    section_start: float,
    section_end: float,
    line_end_gap_seconds: float,
    first_line_start_mode: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []

    line_count = len(lines)

    if line_count == 0:
        return [], ["No lines found in section."]

    if len(regions) < line_count:
        warnings.append(
            f"Only {len(regions)} vocal regions were found for {line_count} lyric lines. Used even spacing fallback."
        )

        return evenly_space_section(
            lines=lines,
            section_start=section_start,
            section_end=section_end,
            line_end_gap_seconds=line_end_gap_seconds,
        ), warnings

    chosen_indexes = choose_region_indexes(
        region_count=len(regions),
        line_count=line_count,
    )

    chosen_regions = [regions[index] for index in chosen_indexes]

    starts: list[float] = []

    for index, region in enumerate(chosen_regions):
        region_start = as_float(region.get("start"))

        if index == 0 and first_line_start_mode == "section":
            starts.append(section_start)
        else:
            starts.append(region_start)

    mapped_lines: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        start = starts[index]

        if index < line_count - 1:
            next_start = starts[index + 1]
            end = next_start - line_end_gap_seconds
        else:
            end = section_end

        if end <= start:
            end = start + 0.1
            warnings.append(
                f"{line.get('id', f'line-{index + 1}')}: end had to be adjusted because the line was too short."
            )

        selected_region = chosen_regions[index]

        mapped_lines.append(
            {
                **line,
                "original_draft_start": round_time(as_float(line.get("start"))),
                "original_draft_end": round_time(as_float(line.get("end"))),
                "start": round_time(start),
                "end": round_time(end),
                "timing_source": "manual-section-bounds-plus-vocal-onsets",
                "selected_region_id": selected_region.get("id"),
                "selected_region_start": round_time(as_float(selected_region.get("start"))),
                "selected_region_end": round_time(as_float(selected_region.get("end"))),
            }
        )

    return mapped_lines, warnings


def rebuild_matching_section(
    draft: dict[str, Any],
    truth: dict[str, Any],
    line_end_gap_seconds: float,
    edge_tolerance_seconds: float,
    first_line_start_mode: str,
) -> dict[str, Any]:
    truth_section = truth.get("section")

    if not isinstance(truth_section, dict):
        raise ValueError("Truth JSON does not contain a valid section object.")

    section_start = as_float(truth_section.get("start"))
    section_end = as_float(truth_section.get("end"))

    if section_end <= section_start:
        raise ValueError("Truth section has invalid start/end timings.")

    draft_section = find_draft_section(draft, truth_section)
    draft_lines = draft_section.get("lines", [])

    if not isinstance(draft_lines, list) or not draft_lines:
        raise ValueError("Matching draft section does not contain lines.")

    regions = get_regions_inside_bounds(
        draft=draft,
        section_start=section_start,
        section_end=section_end,
        edge_tolerance_seconds=edge_tolerance_seconds,
    )

    mapped_lines, warnings = map_lines_using_regions(
        lines=draft_lines,
        regions=regions,
        section_start=section_start,
        section_end=section_end,
        line_end_gap_seconds=line_end_gap_seconds,
        first_line_start_mode=first_line_start_mode,
    )

    draft_section["start"] = round_time(section_start)
    draft_section["end"] = round_time(section_end)
    draft_section["lines"] = mapped_lines
    draft_section["manual_section_bounds"] = {
        "source": "manual truth section start/end",
        "start": round_time(section_start),
        "end": round_time(section_end),
    }

    draft["schema_version"] = draft.get("schema_version", "karaoke-draft-v1")
    draft["section_onset_mapping_experiment"] = {
        "mode": "manual-section-bounds-plus-vocal-onsets",
        "section_id": draft_section.get("id"),
        "section_label": draft_section.get("label"),
        "line_end_gap_seconds": round_time(line_end_gap_seconds),
        "edge_tolerance_seconds": round_time(edge_tolerance_seconds),
        "first_line_start_mode": first_line_start_mode,
        "vocal_regions_available_in_manual_bounds": len(regions),
        "warnings": warnings,
    }

    editor_notes = draft.get("editor_notes", [])

    if not isinstance(editor_notes, list):
        editor_notes = []

    editor_notes.append(
        "One section was remapped using manual section bounds and vocal onset grouping."
    )

    draft["editor_notes"] = editor_notes

    return draft


def print_summary(draft: dict[str, Any]) -> None:
    experiment = draft.get("section_onset_mapping_experiment", {})

    print("")
    print("Section onset mapping complete.")
    print("")
    print(f"Section: {experiment.get('section_label')}")
    print(f"Vocal regions in manual bounds: {experiment.get('vocal_regions_available_in_manual_bounds')}")
    print(f"Line end gap: {experiment.get('line_end_gap_seconds')}s")
    print("")

    warnings = experiment.get("warnings", [])

    if warnings:
        print("Warnings:")

        for warning in warnings:
            print(f"- {warning}")

        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remap one draft section using manual section bounds and vocal onset grouping."
    )

    parser.add_argument(
        "--draft",
        required=True,
        help="Path to the draft JSON that contains sections and raw_audio_regions.",
    )

    parser.add_argument(
        "--truth",
        required=True,
        help="Path to the manually timed truth JSON for one section.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the remapped draft JSON should be written.",
    )

    parser.add_argument(
        "--line-end-gap-ms",
        type=int,
        default=800,
        help="Gap before the next line starts. Default: 800.",
    )

    parser.add_argument(
        "--edge-tolerance-ms",
        type=int,
        default=500,
        help="Extra tolerance around manual section bounds when collecting vocal regions. Default: 500.",
    )

    parser.add_argument(
        "--first-line-start",
        choices=["section", "region"],
        default="section",
        help="Use the manual section start or first detected region start for the first lyric line. Default: section.",
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

        rebuilt = rebuild_matching_section(
            draft=draft,
            truth=truth,
            line_end_gap_seconds=args.line_end_gap_ms / 1000,
            edge_tolerance_seconds=args.edge_tolerance_ms / 1000,
            first_line_start_mode=args.first_line_start,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(rebuilt, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print_summary(rebuilt)
        print(f"Output written to: {output_path}")
        print("")

    except Exception as error:
        print("")
        print("Could not map section using vocal onsets.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())