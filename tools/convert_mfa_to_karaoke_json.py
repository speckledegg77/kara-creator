from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SILENCE_LABELS = {"<eps>", "sil", "sp", ""}


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


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "section"


def normalise_word(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_mfa_words(mfa_json: dict[str, Any]) -> list[dict[str, Any]]:
    tiers = mfa_json.get("tiers", {})
    words_tier = tiers.get("words", {})
    entries = words_tier.get("entries", [])

    if not isinstance(entries, list):
        raise ValueError("MFA JSON does not contain tiers.words.entries.")

    words: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 3:
            continue

        start = as_float(entry[0])
        end = as_float(entry[1])
        label = normalise_word(entry[2])

        if label in SILENCE_LABELS:
            continue

        words.append(
            {
                "index": len(words),
                "word": label,
                "start": round_time(start),
                "end": round_time(end),
            }
        )

    if not words:
        raise ValueError("No aligned words were found in the MFA JSON.")

    return words


def group_line_map_by_section(line_map: dict[str, Any]) -> list[dict[str, Any]]:
    lines = line_map.get("lines", [])

    if not isinstance(lines, list) or not lines:
        raise ValueError("Line map does not contain any lines.")

    grouped_sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None

    for line in lines:
        section_label = str(line.get("section", "Song")).strip() or "Song"

        if current_section is None or current_section["label"] != section_label:
            current_section = {
                "label": section_label,
                "lines": [],
            }
            grouped_sections.append(current_section)

        current_section["lines"].append(line)

    return grouped_sections


def get_words_for_line(
    aligned_words: list[dict[str, Any]],
    line: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []

    start_index = int(line.get("start_word_index", -1))
    end_index = int(line.get("end_word_index", -1))

    if start_index < 0 or end_index < start_index:
        warnings.append(f"{line.get('id', 'unknown line')}: invalid word index range.")
        return [], warnings

    if end_index >= len(aligned_words):
        warnings.append(
            f"{line.get('id', 'unknown line')}: end word index {end_index} is outside aligned word count {len(aligned_words)}."
        )
        return [], warnings

    actual_words = aligned_words[start_index:end_index + 1]
    expected_words = [normalise_word(word) for word in line.get("words", [])]
    actual_labels = [word["word"] for word in actual_words]

    if expected_words != actual_labels:
        warnings.append(
            f"{line.get('id', 'unknown line')}: expected words do not exactly match MFA words. "
            f"Expected {expected_words}; got {actual_labels}."
        )

    return actual_words, warnings


def build_karaoke_json(
    mfa_json: dict[str, Any],
    line_map: dict[str, Any],
    mfa_path: Path,
    line_map_path: Path,
    start_padding_seconds: float,
    end_padding_seconds: float,
    next_line_gap_seconds: float,
) -> dict[str, Any]:
    aligned_words = extract_mfa_words(mfa_json)
    grouped_sections = group_line_map_by_section(line_map)

    all_line_warnings: list[str] = []
    section_entries: list[dict[str, Any]] = []
    section_counter = 1

    for section in grouped_sections:
        section_label = section["label"]
        line_entries: list[dict[str, Any]] = []

        for line in section["lines"]:
            line_words, warnings = get_words_for_line(
                aligned_words=aligned_words,
                line=line,
            )

            all_line_warnings.extend(warnings)

            if not line_words:
                continue

            first_word = line_words[0]
            last_word = line_words[-1]

            vocal_start = as_float(first_word["start"])
            vocal_end = as_float(last_word["end"])

            display_start = max(0.0, vocal_start - start_padding_seconds)
            display_end = vocal_end + end_padding_seconds

            line_entries.append(
                {
                    "id": line.get("id"),
                    "text": line.get("text", ""),
                    "start": round_time(display_start),
                    "end": round_time(display_end),
                    "vocal_start": round_time(vocal_start),
                    "vocal_end": round_time(vocal_end),
                    "confidence": "mfa-draft",
                    "locked": False,
                    "anchor": False,
                    "timing_source": "mfa-word-alignment",
                    "words": [
                        {
                            "index": word["index"],
                            "text": word["word"],
                            "start": word["start"],
                            "end": word["end"],
                        }
                        for word in line_words
                    ],
                }
            )

        for index, line_entry in enumerate(line_entries):
            if index < len(line_entries) - 1:
                next_start = as_float(line_entries[index + 1]["start"])
                latest_allowed_end = max(
                    as_float(line_entry["start"]) + 0.1,
                    next_start - next_line_gap_seconds,
                )

                if as_float(line_entry["end"]) > latest_allowed_end:
                    line_entry["end"] = round_time(latest_allowed_end)
                    line_entry["display_end_adjusted"] = True
                else:
                    line_entry["display_end_adjusted"] = False
            else:
                line_entry["display_end_adjusted"] = False

        if line_entries:
            section_entries.append(
                {
                    "id": f"{slugify(section_label)}-{section_counter:03d}",
                    "label": section_label,
                    "start": line_entries[0]["start"],
                    "end": line_entries[-1]["end"],
                    "lines": line_entries,
                }
            )
            section_counter += 1

    if not section_entries:
        raise ValueError("No karaoke sections could be created from MFA alignment.")

    audio_duration = as_float(mfa_json.get("end"))

    return {
        "schema_version": "karaoke-draft-mfa-v1",
        "created_by": "kara-creator MFA converter",
        "source": {
            "mfa_json": str(mfa_path),
            "line_map_json": str(line_map_path),
            "audio_file": line_map.get("source", {}).get("audio_file"),
            "lyrics_file": line_map.get("source", {}).get("lyrics_file"),
            "audio_duration_seconds": round_time(audio_duration),
        },
        "alignment": {
            "mode": "forced-alignment-known-lyrics",
            "status": "draft",
            "word_count": len(aligned_words),
            "section_count": len(section_entries),
            "line_count": sum(len(section["lines"]) for section in section_entries),
            "settings": {
                "start_padding_seconds": start_padding_seconds,
                "end_padding_seconds": end_padding_seconds,
                "next_line_gap_seconds": next_line_gap_seconds,
            },
            "warnings": all_line_warnings,
        },
        "sections": section_entries,
        "editor_notes": [
            "This draft was created from MFA word-level forced alignment.",
            "The supplied lyric file remains the source of truth.",
            "Line start/end timings are derived from first and last aligned words.",
            "Use the manual review tool to check whether the display padding feels right.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert MFA word alignment JSON into section-based karaoke draft JSON."
    )

    parser.add_argument(
        "--mfa",
        required=True,
        help="Path to MFA JSON output.",
    )

    parser.add_argument(
        "--line-map",
        required=True,
        help="Path to kara-creator line map JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where karaoke draft JSON should be written.",
    )

    parser.add_argument(
        "--start-padding-ms",
        type=int,
        default=150,
        help="How early each line should appear before the first aligned word. Default: 150.",
    )

    parser.add_argument(
        "--end-padding-ms",
        type=int,
        default=450,
        help="How long each line should remain after the final aligned word. Default: 450.",
    )

    parser.add_argument(
        "--next-line-gap-ms",
        type=int,
        default=80,
        help="Minimum gap before the next line appears. Default: 80.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    mfa_path = Path(args.mfa).resolve()
    line_map_path = Path(args.line_map).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(mfa_path, "MFA JSON")
        require_file(line_map_path, "Line map JSON")

        mfa_json = load_json(mfa_path)
        line_map = load_json(line_map_path)

        karaoke_json = build_karaoke_json(
            mfa_json=mfa_json,
            line_map=line_map,
            mfa_path=mfa_path,
            line_map_path=line_map_path,
            start_padding_seconds=args.start_padding_ms / 1000,
            end_padding_seconds=args.end_padding_ms / 1000,
            next_line_gap_seconds=args.next_line_gap_ms / 1000,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(karaoke_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("")
        print("MFA karaoke draft created.")
        print(f"Output: {output_path}")
        print("")
        print(f"Sections: {karaoke_json['alignment']['section_count']}")
        print(f"Lines:    {karaoke_json['alignment']['line_count']}")
        print(f"Words:    {karaoke_json['alignment']['word_count']}")
        print(f"Warnings: {len(karaoke_json['alignment']['warnings'])}")
        print("")

    except Exception as error:
        print("")
        print("Could not convert MFA alignment to karaoke JSON.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())