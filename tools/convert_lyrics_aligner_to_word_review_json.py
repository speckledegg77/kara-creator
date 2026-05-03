from __future__ import annotations

import argparse
import json
import re
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


def round_time(value: float) -> float:
    return round(float(value), 3)


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "section"


def normalise_word(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def parse_lyrics_aligner_output(path: Path) -> list[dict[str, Any]]:
    require_file(path, "Lyrics-aligner output")

    words: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()

        if not line:
            continue

        parts = re.split(r"\s+", line)

        if len(parts) < 2:
            raise ValueError(
                f"Could not parse line {line_number} in lyrics-aligner output: {raw_line}"
            )

        word = normalise_word(parts[0])
        start = as_float(parts[1], fallback=-1)

        if not word:
            continue

        if start < 0:
            raise ValueError(
                f"Invalid start time on line {line_number} in lyrics-aligner output: {raw_line}"
            )

        words.append(
            {
                "index": len(words),
                "id": f"word-{len(words) + 1:04d}",
                "text": word,
                "start": round_time(start),
            }
        )

    if not words:
        raise ValueError("No word onsets were found in the lyrics-aligner output.")

    return words


def add_word_end_times(
    words: list[dict[str, Any]],
    max_word_display_seconds: float,
    final_word_display_seconds: float,
) -> None:
    for index, word in enumerate(words):
        start = as_float(word["start"])

        if index < len(words) - 1:
            next_start = as_float(words[index + 1]["start"])
            end = min(next_start, start + max_word_display_seconds)

            if end <= start:
                end = start + 0.05
        else:
            end = start + final_word_display_seconds

        word["end"] = round_time(end)
        word["duration"] = round_time(end - start)


def group_lines_by_section(line_map: dict[str, Any]) -> list[dict[str, Any]]:
    lines = line_map.get("lines", [])

    if not isinstance(lines, list) or not lines:
        raise ValueError("Line map does not contain any lines.")

    section_lookup: dict[str, dict[str, Any]] = {}

    for index, section in enumerate(line_map.get("sections", []), start=1):
        section_id = str(section.get("id") or f"section-{index:03d}")
        section_lookup[section_id] = section

    grouped_sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_key: str | None = None

    for line in lines:
        section_label = str(line.get("section", "Song")).strip() or "Song"
        section_id = str(line.get("section_id") or f"{slugify(section_label)}-{len(grouped_sections) + 1:03d}")
        section_key = f"{section_id}|{section_label}"

        if current_section is None or current_key != section_key:
            source_section = section_lookup.get(section_id, {})
            current_section = {
                "id": section_id,
                "label": section_label,
                "source": source_section.get("source"),
                "parser_mode": source_section.get("parser_mode"),
                "lines": [],
            }
            grouped_sections.append(current_section)
            current_key = section_key

        current_section["lines"].append(line)

    return grouped_sections


def get_words_for_line(
    aligned_words: list[dict[str, Any]],
    line: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []

    if line.get("display_type") == "instrumental":
        return [], warnings

    start_index = line.get("start_word_index")
    end_index = line.get("end_word_index")

    if start_index is None or end_index is None:
        warnings.append(f"{line.get('id', 'unknown line')}: lyric line has no word index range.")
        return [], warnings

    start_index = int(start_index)
    end_index = int(end_index)

    if start_index < 0 or end_index < start_index:
        warnings.append(f"{line.get('id', 'unknown line')}: invalid word index range.")
        return [], warnings

    if end_index >= len(aligned_words):
        warnings.append(
            f"{line.get('id', 'unknown line')}: end word index {end_index} is outside aligned word count {len(aligned_words)}."
        )
        return [], warnings

    selected_words = aligned_words[start_index:end_index + 1]

    expected_words = [
        normalise_word(word)
        for word in line.get("words", [])
    ]

    actual_words = [
        word["text"]
        for word in selected_words
    ]

    if expected_words != actual_words:
        warnings.append(
            f"{line.get('id', 'unknown line')}: expected words do not match lyrics-aligner words. "
            f"Expected {expected_words}; got {actual_words}."
        )

    return selected_words, warnings


def build_word_review_json(
    lyrics_aligner_path: Path,
    line_map_path: Path,
    max_word_display_seconds: float,
    final_word_display_seconds: float,
    next_line_gap_seconds: float,
) -> dict[str, Any]:
    line_map = load_json(line_map_path)

    aligned_words = parse_lyrics_aligner_output(lyrics_aligner_path)
    add_word_end_times(
        words=aligned_words,
        max_word_display_seconds=max_word_display_seconds,
        final_word_display_seconds=final_word_display_seconds,
    )

    grouped_sections = group_lines_by_section(line_map)

    output_sections: list[dict[str, Any]] = []
    warnings: list[str] = []

    for section in grouped_sections:
        output_lines: list[dict[str, Any]] = []

        for line in section["lines"]:
            display_type = str(line.get("display_type", "lyric"))

            if display_type == "instrumental":
                output_lines.append(
                    {
                        "id": line.get("id"),
                        "section": section["label"],
                        "text": ". . .",
                        "display_type": "instrumental",
                        "start": None,
                        "end": None,
                        "timing_source": "instrumental-placeholder-pending-draft-builder",
                        "review_flags": ["instrumental_timing_needs_review"],
                        "words": [],
                    }
                )
                continue

            line_words, line_warnings = get_words_for_line(
                aligned_words=aligned_words,
                line=line,
            )

            warnings.extend(line_warnings)

            if not line_words:
                continue

            output_words = []

            for line_word_index, word in enumerate(line_words):
                output_words.append(
                    {
                        "id": word["id"],
                        "aligner_word_index": word["index"],
                        "line_word_index": line_word_index,
                        "text": word["text"],
                        "start": word["start"],
                        "end": word["end"],
                        "duration": word["duration"],
                    }
                )

            output_lines.append(
                {
                    "id": line.get("id"),
                    "section": section["label"],
                    "text": line.get("text", ""),
                    "display_type": "lyric",
                    "start": output_words[0]["start"],
                    "end": output_words[-1]["end"],
                    "review_flags": [],
                    "words": output_words,
                }
            )

        if output_lines:
            timed_lines = [line for line in output_lines if line.get("start") is not None and line.get("end") is not None]

            output_sections.append(
                {
                    "id": section["id"],
                    "label": section["label"],
                    "source": section.get("source"),
                    "parser_mode": section.get("parser_mode"),
                    "start": timed_lines[0]["start"] if timed_lines else None,
                    "end": timed_lines[-1]["end"] if timed_lines else None,
                    "lines": output_lines,
                }
            )

    if not output_sections:
        raise ValueError("No output sections were created.")

    all_lines: list[dict[str, Any]] = []

    for section in output_sections:
        for line in section["lines"]:
            all_lines.append(line)

    timed_lyric_lines = [line for line in all_lines if line.get("display_type") == "lyric" and line.get("start") is not None]

    for index, line in enumerate(timed_lyric_lines[:-1]):
        next_line = timed_lyric_lines[index + 1]
        next_start = as_float(next_line["start"])
        latest_allowed_end = max(
            as_float(line["start"]) + 0.05,
            next_start - next_line_gap_seconds,
        )

        if as_float(line["end"]) > latest_allowed_end:
            line["original_unclamped_end"] = line["end"]
            line["end"] = round_time(latest_allowed_end)
            line["display_end_clamped_to_next_line"] = True
        else:
            line["display_end_clamped_to_next_line"] = False

    if timed_lyric_lines:
        timed_lyric_lines[-1]["display_end_clamped_to_next_line"] = False

    for section in output_sections:
        timed_lines = [line for line in section["lines"] if line.get("start") is not None and line.get("end") is not None]

        if timed_lines:
            section["start"] = timed_lines[0]["start"]
            section["end"] = timed_lines[-1]["end"]

    audio_duration = max(as_float(word["start"]) for word in aligned_words) + final_word_display_seconds

    return {
        "schema_version": "karaoke-word-review-v2",
        "created_by": "kara-creator lyrics-aligner converter",
        "source": {
            "lyrics_aligner_output": str(lyrics_aligner_path),
            "line_map_json": str(line_map_path),
            "audio_file": line_map.get("source", {}).get("audio_file"),
            "lyrics_file": line_map.get("source", {}).get("lyrics_file"),
            "audio_duration_seconds": round_time(audio_duration),
        },
        "alignment": {
            "mode": "singing-specific-lyrics-aligner-word-onsets",
            "status": "diagnostic",
            "word_count": len(aligned_words),
            "section_count": len(output_sections),
            "line_count": sum(len(section["lines"]) for section in output_sections),
            "lyric_line_count": sum(1 for line in all_lines if line.get("display_type") == "lyric"),
            "instrumental_line_count": sum(1 for line in all_lines if line.get("display_type") == "instrumental"),
            "settings": {
                "max_word_display_seconds": max_word_display_seconds,
                "final_word_display_seconds": final_word_display_seconds,
                "next_line_gap_seconds": next_line_gap_seconds,
            },
            "warnings": warnings,
        },
        "sections": output_sections,
        "all_words": [
            {
                "id": word["id"],
                "index": word["index"],
                "text": word["text"],
                "start": word["start"],
                "end": word["end"],
                "duration": word["duration"],
            }
            for word in aligned_words
        ],
        "review_notes": [
            "This file was created from singing-specific lyrics-aligner word onsets.",
            "The aligner output provides word starts only.",
            "Word and line ends are inferred for review purposes and should not be treated as final timing truth.",
            "Instrumental placeholder lines are preserved here with empty words arrays and are timed in the draft builder.",
            "Use this mainly to judge word starts and line starts.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert singing-specific lyrics-aligner word onsets into kara-creator word review JSON."
    )

    parser.add_argument(
        "--aligner-output",
        required=True,
        help="Path to lyrics-aligner word_onsets output TXT.",
    )

    parser.add_argument(
        "--line-map",
        required=True,
        help="Path to kara-creator line map JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where word review JSON should be written.",
    )

    parser.add_argument(
        "--max-word-display-ms",
        type=int,
        default=900,
        help="Maximum display duration inferred for a word. Default: 900.",
    )

    parser.add_argument(
        "--final-word-display-ms",
        type=int,
        default=1200,
        help="Fallback duration for the final word. Default: 1200.",
    )

    parser.add_argument(
        "--next-line-gap-ms",
        type=int,
        default=50,
        help="Gap before the next line starts. Default: 50.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    lyrics_aligner_path = Path(args.aligner_output).resolve()
    line_map_path = Path(args.line_map).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(lyrics_aligner_path, "Lyrics-aligner output")
        require_file(line_map_path, "Line map JSON")

        output = build_word_review_json(
            lyrics_aligner_path=lyrics_aligner_path,
            line_map_path=line_map_path,
            max_word_display_seconds=args.max_word_display_ms / 1000,
            final_word_display_seconds=args.final_word_display_ms / 1000,
            next_line_gap_seconds=args.next_line_gap_ms / 1000,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("")
        print("Lyrics-aligner word review JSON created.")
        print(f"Output: {output_path}")
        print("")
        print(f"Sections:      {output['alignment']['section_count']}")
        print(f"Display lines: {output['alignment']['line_count']}")
        print(f"Lyric lines:   {output['alignment']['lyric_line_count']}")
        print(f"Instrumentals: {output['alignment']['instrumental_line_count']}")
        print(f"Words:         {output['alignment']['word_count']}")
        print(f"Warnings:      {len(output['alignment']['warnings'])}")
        print("")

        if output["alignment"]["warnings"]:
            print("Warnings:")
            for warning in output["alignment"]["warnings"]:
                print(f"- {warning}")
            print("")

    except Exception as error:
        print("")
        print("Could not convert lyrics-aligner output.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
