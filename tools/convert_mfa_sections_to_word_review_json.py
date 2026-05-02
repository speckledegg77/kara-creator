from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SILENCE_LABELS = {"<eps>", "eps", "sil", "sp", ""}


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


def find_alignment_json(aligned_dir: Path, file_base: str) -> Path:
    direct_path = aligned_dir / f"{file_base}.json"

    if direct_path.exists():
        return direct_path

    matches = list(aligned_dir.rglob(f"{file_base}.json"))

    if matches:
        return matches[0]

    available = [path.name for path in aligned_dir.rglob("*.json")]

    raise FileNotFoundError(
        f"Could not find MFA JSON for {file_base}. Available JSON files: {available}"
    )


def extract_aligned_words(mfa_json: dict[str, Any], global_offset: float) -> list[dict[str, Any]]:
    tiers = mfa_json.get("tiers", {})
    words_tier = tiers.get("words", {})
    entries = words_tier.get("entries", [])

    if not isinstance(entries, list):
        raise ValueError("MFA JSON does not contain tiers.words.entries.")

    aligned_words: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 3:
            continue

        raw_label = str(entry[2]).strip()

        if is_silence_label(raw_label):
            continue

        label = normalise_word(raw_label)

        if not label or is_silence_label(label):
            continue

        local_start = as_float(entry[0])
        local_end = as_float(entry[1])

        aligned_words.append(
            {
                "mfa_word_index": len(aligned_words),
                "id": "",
                "text": label,
                "raw_text": raw_label,
                "local_start": round_time(local_start),
                "local_end": round_time(local_end),
                "start": round_time(global_offset + local_start),
                "end": round_time(global_offset + local_end),
                "duration": round_time(local_end - local_start),
            }
        )

    return aligned_words


def get_line_words(
    aligned_words: list[dict[str, Any]],
    line: dict[str, Any],
    global_word_counter: int,
) -> tuple[list[dict[str, Any]], list[str], int]:
    warnings: list[str] = []

    start_word_index = int(line.get("start_word_index", -1))
    end_word_index = int(line.get("end_word_index", -1))

    if start_word_index < 0 or end_word_index < start_word_index:
        warnings.append(f"{line.get('id', 'unknown')}: invalid word index range.")
        return [], warnings, global_word_counter

    if end_word_index >= len(aligned_words):
        warnings.append(
            f"{line.get('id', 'unknown')}: end word index {end_word_index} is outside aligned word count {len(aligned_words)}."
        )
        return [], warnings, global_word_counter

    selected_words = aligned_words[start_word_index:end_word_index + 1]
    expected_words = [normalise_word(word) for word in line.get("words", [])]
    actual_words = [word["text"] for word in selected_words]

    if expected_words != actual_words:
        warnings.append(
            f"{line.get('id', 'unknown')}: expected words do not match aligned words. "
            f"Expected {expected_words}; got {actual_words}."
        )

    output_words: list[dict[str, Any]] = []

    for local_line_word_index, word in enumerate(selected_words):
        global_word_counter += 1

        output_words.append(
            {
                "id": f"word-{global_word_counter:04d}",
                "mfa_word_index": word["mfa_word_index"],
                "line_word_index": local_line_word_index,
                "text": word["text"],
                "raw_text": word["raw_text"],
                "local_start": word["local_start"],
                "local_end": word["local_end"],
                "start": word["start"],
                "end": word["end"],
                "duration": word["duration"],
            }
        )

    return output_words, warnings, global_word_counter


def convert_sections(
    section_map_path: Path,
    aligned_dir: Path,
    output_path: Path,
) -> None:
    require_file(section_map_path, "Section line map")
    section_map = load_json(section_map_path)

    sections = section_map.get("sections", [])

    if not isinstance(sections, list) or not sections:
        raise ValueError("Section line map does not contain sections.")

    output_sections: list[dict[str, Any]] = []
    all_words: list[dict[str, Any]] = []
    warnings: list[str] = []
    global_word_counter = 0

    for section in sections:
        file_base = section.get("file_base")
        global_offset = as_float(section.get("global_start"))
        alignment_path = find_alignment_json(aligned_dir, str(file_base))
        mfa_json = load_json(alignment_path)

        section_aligned_words = extract_aligned_words(
            mfa_json=mfa_json,
            global_offset=global_offset,
        )

        line_entries: list[dict[str, Any]] = []

        for line in section.get("lines", []):
            output_words, line_warnings, global_word_counter = get_line_words(
                aligned_words=section_aligned_words,
                line=line,
                global_word_counter=global_word_counter,
            )

            warnings.extend(line_warnings)

            if not output_words:
                continue

            all_words.extend(output_words)

            line_entries.append(
                {
                    "id": line.get("id"),
                    "section": section.get("label"),
                    "text": line.get("text", ""),
                    "start": output_words[0]["start"],
                    "end": output_words[-1]["end"],
                    "words": output_words,
                }
            )

        if line_entries:
            output_sections.append(
                {
                    "id": section.get("id"),
                    "label": section.get("label"),
                    "start": line_entries[0]["start"],
                    "end": line_entries[-1]["end"],
                    "global_bound_start": section.get("global_start"),
                    "global_bound_end": section.get("global_end"),
                    "file_base": file_base,
                    "lines": line_entries,
                }
            )

    if not output_sections:
        raise ValueError("No output sections were created.")

    audio_duration = max(as_float(section.get("global_end")) for section in sections)

    output = {
        "schema_version": "karaoke-word-review-v1",
        "created_by": "kara-creator sectioned MFA converter",
        "source": {
            "section_line_map_json": str(section_map_path),
            "aligned_dir": str(aligned_dir),
            "audio_file": section_map.get("source", {}).get("audio_file"),
            "lyrics_file": section_map.get("source", {}).get("lyrics_file"),
            "audio_duration_seconds": round_time(audio_duration),
        },
        "alignment": {
            "mode": "sectioned-mfa-word-start-review",
            "status": "diagnostic",
            "word_count": len(all_words),
            "section_count": len(output_sections),
            "line_count": sum(len(section["lines"]) for section in output_sections),
            "warnings": warnings,
        },
        "sections": output_sections,
        "all_words": all_words,
        "review_notes": [
            "This file is for testing sectioned MFA word timing accuracy.",
            "Each section was aligned separately, then converted back to full-song time.",
            "This should reduce drift across section boundaries.",
            "Do not treat this as final karaoke display timing.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("")
    print("Sectioned MFA word review JSON created.")
    print(f"Output: {output_path}")
    print("")
    print(f"Sections: {output['alignment']['section_count']}")
    print(f"Lines:    {output['alignment']['line_count']}")
    print(f"Words:    {output['alignment']['word_count']}")
    print(f"Warnings: {len(output['alignment']['warnings'])}")
    print("")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert sectioned MFA JSON outputs into one full-song word review JSON."
    )

    parser.add_argument("--section-map", required=True, help="Path to section line map JSON.")
    parser.add_argument("--aligned-dir", required=True, help="Folder containing section MFA JSON outputs.")
    parser.add_argument("--out", required=True, help="Output word review JSON path.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        convert_sections(
            section_map_path=Path(args.section_map).resolve(),
            aligned_dir=Path(args.aligned_dir).resolve(),
            output_path=Path(args.out).resolve(),
        )

    except Exception as error:
        print("")
        print("Could not convert sectioned MFA output.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())