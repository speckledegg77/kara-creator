from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SILENCE_LABELS = {"<eps>", "eps", "sil", "sp", ""}
CLITIC_LABELS = {"'s", "'ve", "'m", "'re", "'d", "'ll", "n't"}


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


def is_silence_label(value: Any) -> bool:
    raw = str(value).strip().lower()
    cleaned = re.sub(r"[^a-z0-9<>']+", "", raw)
    cleaned_without_marks = cleaned.replace("<", "").replace(">", "")

    return raw in SILENCE_LABELS or cleaned in SILENCE_LABELS or cleaned_without_marks in SILENCE_LABELS


def normalise_word(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def is_clitic(value: str) -> bool:
    return normalise_word(value) in CLITIC_LABELS


def merge_clitic(previous_word: dict[str, Any], clitic_label: str, clitic_end: float) -> None:
    cleaned_clitic = normalise_word(clitic_label)

    previous_word["text"] = normalise_word(previous_word["text"] + cleaned_clitic)
    previous_word["raw_text"] = str(previous_word.get("raw_text", "")) + clitic_label
    previous_word["end"] = round_time(clitic_end)
    previous_word["duration"] = round_time(previous_word["end"] - previous_word["start"])
    previous_word["merged_clitic"] = cleaned_clitic


def extract_aligned_words(mfa_json: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    tiers = mfa_json.get("tiers", {})
    words_tier = tiers.get("words", {})
    entries = words_tier.get("entries", [])

    if not isinstance(entries, list):
        raise ValueError("MFA JSON does not contain tiers.words.entries.")

    aligned_words: list[dict[str, Any]] = []
    skipped_silence_count = 0
    merged_clitic_count = 0

    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 3:
            continue

        start = as_float(entry[0])
        end = as_float(entry[1])
        raw_label = str(entry[2]).strip()
        label = normalise_word(raw_label)

        if is_silence_label(raw_label):
            skipped_silence_count += 1
            continue

        if not label or is_silence_label(label):
            skipped_silence_count += 1
            continue

        if is_clitic(label) and aligned_words:
            merge_clitic(
                previous_word=aligned_words[-1],
                clitic_label=label,
                clitic_end=end,
            )
            merged_clitic_count += 1
            continue

        aligned_words.append(
            {
                "mfa_word_index": len(aligned_words),
                "id": f"word-{len(aligned_words) + 1:04d}",
                "text": label,
                "raw_text": raw_label,
                "start": round_time(start),
                "end": round_time(end),
                "duration": round_time(end - start),
            }
        )

    if not aligned_words:
        raise ValueError("No non-silence word timings were found in the MFA JSON.")

    return aligned_words, merged_clitic_count


def group_lines_by_section(line_map: dict[str, Any]) -> list[dict[str, Any]]:
    lines = line_map.get("lines", [])

    if not isinstance(lines, list) or not lines:
        raise ValueError("Line map does not contain any lines.")

    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None

    for line in lines:
        section_label = str(line.get("section", "Song")).strip() or "Song"

        if current_section is None or current_section["label"] != section_label:
            current_section = {
                "id": f"{slugify(section_label)}-{len(sections) + 1:03d}",
                "label": section_label,
                "lines": [],
            }
            sections.append(current_section)

        current_section["lines"].append(line)

    return sections


def get_line_words(
    aligned_words: list[dict[str, Any]],
    line: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []

    start_word_index = int(line.get("start_word_index", -1))
    end_word_index = int(line.get("end_word_index", -1))

    if start_word_index < 0 or end_word_index < start_word_index:
        warnings.append(f"{line.get('id', 'unknown')}: invalid word index range.")
        return [], warnings

    if end_word_index >= len(aligned_words):
        warnings.append(
            f"{line.get('id', 'unknown')}: end word index {end_word_index} is outside aligned word count {len(aligned_words)}."
        )
        return [], warnings

    line_words = aligned_words[start_word_index:end_word_index + 1]
    expected_words = [normalise_word(word) for word in line.get("words", [])]
    actual_words = [word["text"] for word in line_words]

    if expected_words != actual_words:
        warnings.append(
            f"{line.get('id', 'unknown')}: expected words do not match aligned words. "
            f"Expected {expected_words}; got {actual_words}."
        )

    return line_words, warnings


def build_word_review_json(
    mfa_json: dict[str, Any],
    line_map: dict[str, Any],
    mfa_path: Path,
    line_map_path: Path,
) -> dict[str, Any]:
    aligned_words, merged_clitic_count = extract_aligned_words(mfa_json)
    grouped_sections = group_lines_by_section(line_map)

    sections: list[dict[str, Any]] = []
    warnings: list[str] = []

    for section in grouped_sections:
        output_lines: list[dict[str, Any]] = []

        for line in section["lines"]:
            line_words, line_warnings = get_line_words(
                aligned_words=aligned_words,
                line=line,
            )

            warnings.extend(line_warnings)

            if not line_words:
                continue

            output_words = []

            for index, word in enumerate(line_words):
                output_words.append(
                    {
                        "id": word["id"],
                        "mfa_word_index": word["mfa_word_index"],
                        "line_word_index": index,
                        "text": word["text"],
                        "raw_text": word["raw_text"],
                        "start": word["start"],
                        "end": word["end"],
                        "duration": word["duration"],
                        "merged_clitic": word.get("merged_clitic"),
                    }
                )

            output_lines.append(
                {
                    "id": line.get("id"),
                    "section": line.get("section"),
                    "text": line.get("text", ""),
                    "start": output_words[0]["start"],
                    "end": output_words[-1]["end"],
                    "words": output_words,
                }
            )

        if output_lines:
            sections.append(
                {
                    "id": section["id"],
                    "label": section["label"],
                    "start": output_lines[0]["start"],
                    "end": output_lines[-1]["end"],
                    "lines": output_lines,
                }
            )

    if not sections:
        raise ValueError("No sections could be created from the MFA word timings.")

    audio_duration = as_float(mfa_json.get("end"))

    return {
        "schema_version": "karaoke-word-review-v1",
        "created_by": "kara-creator MFA word review converter",
        "source": {
            "mfa_json": str(mfa_path),
            "line_map_json": str(line_map_path),
            "audio_file": line_map.get("source", {}).get("audio_file"),
            "lyrics_file": line_map.get("source", {}).get("lyrics_file"),
            "audio_duration_seconds": round_time(audio_duration),
        },
        "alignment": {
            "mode": "mfa-word-start-review",
            "status": "diagnostic",
            "word_count": len(aligned_words),
            "section_count": len(sections),
            "line_count": sum(len(section["lines"]) for section in sections),
            "merged_clitic_count": merged_clitic_count,
            "warnings": warnings,
        },
        "sections": sections,
        "all_words": aligned_words,
        "review_notes": [
            "This file is for testing MFA word timing accuracy.",
            "MFA silence entries such as <eps> have been removed.",
            "Split clitics such as 's are merged back onto the previous word.",
            "Each remaining word has an MFA start and end time.",
            "Use the review page to check whether each word highlights when it is sung.",
            "Do not treat this as final karaoke display timing.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert MFA alignment JSON into a per-word review JSON."
    )

    parser.add_argument(
        "--mfa",
        required=True,
        help="Path to MFA alignment JSON.",
    )

    parser.add_argument(
        "--line-map",
        required=True,
        help="Path to kara-creator MFA line map JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the word review JSON should be written.",
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

        output = build_word_review_json(
            mfa_json=mfa_json,
            line_map=line_map,
            mfa_path=mfa_path,
            line_map_path=line_map_path,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("")
        print("MFA word review JSON created.")
        print(f"Output: {output_path}")
        print("")
        print(f"Sections: {output['alignment']['section_count']}")
        print(f"Lines:    {output['alignment']['line_count']}")
        print(f"Words:    {output['alignment']['word_count']}")
        print(f"Merged clitics: {output['alignment']['merged_clitic_count']}")
        print(f"Warnings: {len(output['alignment']['warnings'])}")
        print("")

        if output["alignment"]["warnings"]:
            print("Warnings:")
            for warning in output["alignment"]["warnings"]:
                print(f"- {warning}")
            print("")

    except Exception as error:
        print("")
        print("Could not create MFA word review JSON.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())