from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def round_time(value: float) -> float:
    return round(float(value), 3)


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


def line_duration(line: dict[str, Any]) -> float:
    return as_float(line.get("end")) - as_float(line.get("start"))


def preserve_vocal_timings(line: dict[str, Any]) -> None:
    if "vocal_start" not in line:
        line["vocal_start"] = round_time(as_float(line.get("start")))

    if "vocal_end" not in line:
        line["vocal_end"] = round_time(as_float(line.get("end")))


def section_has_enough_space(
    section_start: float,
    section_end: float,
    line_count: int,
    min_display_seconds: float,
) -> bool:
    section_duration = section_end - section_start
    return section_duration >= line_count * min_display_seconds


def evenly_space_lines(
    lines: list[dict[str, Any]],
    section_start: float,
    section_end: float,
    display_gap_seconds: float,
) -> None:
    line_count = len(lines)

    if line_count == 0:
        return

    section_duration = max(0.1, section_end - section_start)
    slot_duration = section_duration / line_count

    for index, line in enumerate(lines):
        start = section_start + index * slot_duration

        if index < line_count - 1:
            end = section_start + (index + 1) * slot_duration - display_gap_seconds
        else:
            end = section_end

        if end <= start:
            end = start + 0.1

        line["start"] = round_time(start)
        line["end"] = round_time(end)
        line["display_timing_source"] = "section-even-fallback"


def reflow_section(
    section: dict[str, Any],
    min_display_seconds: float,
    display_gap_seconds: float,
    max_push_seconds: float,
) -> list[str]:
    warnings: list[str] = []
    lines = section.get("lines", [])

    if not isinstance(lines, list) or not lines:
        return warnings

    for line in lines:
        preserve_vocal_timings(line)

    section_start = as_float(lines[0].get("vocal_start"))
    section_end = as_float(lines[-1].get("vocal_end"))

    if section_end <= section_start:
        section_start = as_float(section.get("start"))
        section_end = as_float(section.get("end"))

    if section_end <= section_start:
        warnings.append(f"{section.get('label', 'Unknown section')}: invalid section duration.")
        return warnings

    line_count = len(lines)

    if not section_has_enough_space(
        section_start=section_start,
        section_end=section_end,
        line_count=line_count,
        min_display_seconds=min_display_seconds,
    ):
        evenly_space_lines(
            lines=lines,
            section_start=section_start,
            section_end=section_end,
            display_gap_seconds=display_gap_seconds,
        )
        warnings.append(
            f"{section.get('label', 'Unknown section')}: section was too short for the requested minimum display time, so lines were spaced evenly."
        )
    else:
        display_starts: list[float] = []

        first_start = as_float(lines[0].get("vocal_start"), section_start)
        display_starts.append(first_start)

        for index in range(1, line_count):
            line = lines[index]
            detected_start = as_float(line.get("vocal_start"), display_starts[-1] + min_display_seconds)

            previous_start = display_starts[-1]
            minimum_allowed_start = previous_start + min_display_seconds

            remaining_lines_after_this = line_count - index - 1
            latest_allowed_start = section_end - remaining_lines_after_this * min_display_seconds

            proposed_start = max(detected_start, minimum_allowed_start)

            if proposed_start > detected_start + max_push_seconds:
                proposed_start = detected_start + max_push_seconds

            if proposed_start > latest_allowed_start:
                proposed_start = latest_allowed_start

            if proposed_start <= previous_start:
                proposed_start = previous_start + 0.1

            display_starts.append(proposed_start)

        for index, line in enumerate(lines):
            start = display_starts[index]

            if index < line_count - 1:
                end = display_starts[index + 1] - display_gap_seconds
            else:
                end = section_end

            if end <= start:
                end = start + 0.1

            original_duration = line_duration(line)

            line["start"] = round_time(start)
            line["end"] = round_time(end)
            line["display_timing_source"] = "minimum-display-reflow"

            new_duration = line_duration(line)

            if original_duration < min_display_seconds and new_duration >= min_display_seconds:
                line["display_note"] = "Extended from short detected vocal fragment."

    section["start"] = round_time(as_float(lines[0].get("start")))
    section["end"] = round_time(as_float(lines[-1].get("end")))

    for line in lines:
        duration = line_duration(line)

        if duration < 0.8:
            warnings.append(
                f"{line.get('id', 'unknown line')} is still very short: {duration:.3f}s"
            )

        if duration > 15:
            warnings.append(
                f"{line.get('id', 'unknown line')} is still very long: {duration:.3f}s"
            )

    return warnings


def reflow_draft(
    draft: dict[str, Any],
    min_display_seconds: float,
    display_gap_seconds: float,
    max_push_seconds: float,
) -> dict[str, Any]:
    sections = draft.get("sections", [])

    if not isinstance(sections, list):
        raise ValueError("The JSON does not contain a valid sections array.")

    warnings: list[str] = []

    for section in sections:
        if isinstance(section, dict):
            warnings.extend(
                reflow_section(
                    section=section,
                    min_display_seconds=min_display_seconds,
                    display_gap_seconds=display_gap_seconds,
                    max_push_seconds=max_push_seconds,
                )
            )

    draft["schema_version"] = draft.get("schema_version", "karaoke-draft-v1")
    draft["display_timing"] = {
        "mode": "minimum-display-reflow",
        "min_display_seconds": min_display_seconds,
        "display_gap_seconds": display_gap_seconds,
        "max_push_seconds": max_push_seconds,
        "meaning": "Display timings are made more forgiving while original detected vocal timings are preserved as vocal_start and vocal_end.",
    }

    draft["review_warnings"] = warnings

    editor_notes = draft.get("editor_notes", [])

    if not isinstance(editor_notes, list):
        editor_notes = []

    editor_notes.append(
        "Display timings have been reflowed so lyric lines stay on screen for longer."
    )
    editor_notes.append(
        "Original detected vocal timings are preserved as vocal_start and vocal_end."
    )

    draft["editor_notes"] = editor_notes

    return draft


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Make draft karaoke JSON display timings more forgiving."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the existing draft JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the reflowed JSON should be written.",
    )

    parser.add_argument(
        "--min-display-seconds",
        type=float,
        default=2.2,
        help="Minimum time a lyric line should stay on screen before the next line can take over. Default: 2.2.",
    )

    parser.add_argument(
        "--display-gap-ms",
        type=int,
        default=50,
        help="Small gap before the next line starts. Default: 50.",
    )

    parser.add_argument(
        "--max-push-seconds",
        type=float,
        default=1.2,
        help="Maximum amount a line start can be pushed later than the detected vocal start. Default: 1.2.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(input_path, "Input JSON")

        draft = json.loads(input_path.read_text(encoding="utf-8"))

        reflowed = reflow_draft(
            draft=draft,
            min_display_seconds=args.min_display_seconds,
            display_gap_seconds=args.display_gap_ms / 1000,
            max_push_seconds=args.max_push_seconds,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(reflowed, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("")
        print("Display timings reflowed.")
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")
        print("")
        print(f"Minimum display seconds: {args.min_display_seconds}")
        print(f"Max push seconds: {args.max_push_seconds}")
        print(f"Warnings: {len(reflowed.get('review_warnings', []))}")
        print("")

    except Exception as error:
        print("")
        print("Could not reflow display timings.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())