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


def round_time(value: float) -> float:
    return round(float(value), 3)


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def flatten_lines(word_review: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []

    for section_index, section in enumerate(word_review.get("sections", [])):
        for line_index, line in enumerate(section.get("lines", [])):
            words = line.get("words", [])

            if not words:
                continue

            first_word = words[0]
            last_word = words[-1]

            lines.append(
                {
                    "section_index": section_index,
                    "section_id": section.get("id"),
                    "section_label": section.get("label"),
                    "line_index": line_index,
                    "id": line.get("id"),
                    "text": line.get("text", ""),
                    "first_word_start": as_float(first_word.get("start")),
                    "last_word_start": as_float(last_word.get("start")),
                    "words": words,
                }
            )

    lines.sort(key=lambda item: as_float(item.get("first_word_start")))

    return lines


def build_review_flags(
    line: dict[str, Any],
    next_line: dict[str, Any] | None,
    previous_line: dict[str, Any] | None,
    long_tail_threshold_seconds: float,
    short_line_threshold_seconds: float,
) -> list[str]:
    flags: list[str] = []

    line_start = as_float(line.get("first_word_start"))
    last_word_start = as_float(line.get("last_word_start"))

    if next_line:
        next_start = as_float(next_line.get("first_word_start"))
        tail_after_last_word = next_start - last_word_start

        if tail_after_last_word >= long_tail_threshold_seconds:
            flags.append("long_tail_after_last_word_needs_review")

    if previous_line:
        previous_start = as_float(previous_line.get("first_word_start"))

        if line_start < previous_start:
            flags.append("line_start_before_previous_line")

    if next_line:
        next_start = as_float(next_line.get("first_word_start"))
        implied_duration = next_start - line_start

        if implied_duration <= short_line_threshold_seconds:
            flags.append("very_short_display_duration_needs_review")

    return flags


def build_draft(
    word_review: dict[str, Any],
    word_review_path: Path,
    start_padding_seconds: float,
    next_line_gap_seconds: float,
    final_line_hold_seconds: float,
    long_tail_threshold_seconds: float,
    short_line_threshold_seconds: float,
) -> dict[str, Any]:
    flat_lines = flatten_lines(word_review)

    if not flat_lines:
        raise ValueError("No usable lines were found in the word review JSON.")

    line_timings: dict[str, dict[str, Any]] = {}

    for index, line in enumerate(flat_lines):
        previous_line = flat_lines[index - 1] if index > 0 else None
        next_line = flat_lines[index + 1] if index < len(flat_lines) - 1 else None

        raw_start = as_float(line.get("first_word_start"))
        display_start = max(0.0, raw_start - start_padding_seconds)

        if next_line:
            next_raw_start = as_float(next_line.get("first_word_start"))
            display_end = max(display_start + 0.1, next_raw_start - next_line_gap_seconds)
        else:
            display_end = raw_start + final_line_hold_seconds

        flags = build_review_flags(
            line=line,
            next_line=next_line,
            previous_line=previous_line,
            long_tail_threshold_seconds=long_tail_threshold_seconds,
            short_line_threshold_seconds=short_line_threshold_seconds,
        )

        words = []

        for word in line["words"]:
            words.append(
                {
                    "id": word.get("id"),
                    "text": word.get("text"),
                    "start": word.get("start"),
                    "end": word.get("end"),
                    "source": "lyrics-aligner-word-start",
                }
            )

        line_timings[str(line["id"])] = {
            "id": line["id"],
            "text": line["text"],
            "start": round_time(display_start),
            "end": round_time(display_end),
            "word_start": round_time(raw_start),
            "last_word_start": round_time(as_float(line.get("last_word_start"))),
            "confidence": "draft",
            "locked": False,
            "anchor": False,
            "timing_source": "lyrics-aligner-word-starts",
            "review_flags": flags,
            "words": words,
        }

    output_sections: list[dict[str, Any]] = []

    for section in word_review.get("sections", []):
        output_lines: list[dict[str, Any]] = []

        for line in section.get("lines", []):
            line_id = str(line.get("id"))

            if line_id in line_timings:
                output_lines.append(line_timings[line_id])

        if output_lines:
            output_sections.append(
                {
                    "id": section.get("id"),
                    "label": section.get("label"),
                    "start": output_lines[0]["start"],
                    "end": output_lines[-1]["end"],
                    "lines": output_lines,
                }
            )

    review_flags = []

    for section in output_sections:
        for line in section["lines"]:
            for flag in line.get("review_flags", []):
                review_flags.append(
                    {
                        "section": section["label"],
                        "line_id": line["id"],
                        "text": line["text"],
                        "flag": flag,
                    }
                )

    return {
        "schema_version": "karaoke-draft-v3",
        "created_by": "kara-creator lyrics-aligner draft builder",
        "source": {
            "word_review_json": str(word_review_path),
            "audio_file": word_review.get("source", {}).get("audio_file"),
            "lyrics_file": word_review.get("source", {}).get("lyrics_file"),
            "audio_duration_seconds": word_review.get("source", {}).get("audio_duration_seconds"),
        },
        "alignment": {
            "mode": "singing-specific-word-starts-to-line-draft",
            "status": "draft",
            "primary_aligner": "lyrics-aligner",
            "line_count": sum(len(section["lines"]) for section in output_sections),
            "section_count": len(output_sections),
            "settings": {
                "start_padding_seconds": start_padding_seconds,
                "next_line_gap_seconds": next_line_gap_seconds,
                "final_line_hold_seconds": final_line_hold_seconds,
                "long_tail_threshold_seconds": long_tail_threshold_seconds,
                "short_line_threshold_seconds": short_line_threshold_seconds,
            },
            "review_flag_count": len(review_flags),
            "review_flags": review_flags,
        },
        "sections": output_sections,
        "editor_notes": [
            "This draft uses singing-specific word starts as timing anchors.",
            "Line starts come from the first word in each lyric line.",
            "Line ends are inferred from the next line start, not from word endings.",
            "Lines with long held notes or suspiciously short timings are flagged for review.",
            "This is an editable draft, not a final export.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build section-based karaoke draft JSON from singing-aligner word starts."
    )

    parser.add_argument(
        "--word-review",
        required=True,
        help="Path to karaoke-word-review-v1 JSON created from lyrics-aligner.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the draft karaoke JSON should be written.",
    )

    parser.add_argument(
        "--start-padding-ms",
        type=int,
        default=150,
        help="Show each line slightly before its first word. Default: 150.",
    )

    parser.add_argument(
        "--next-line-gap-ms",
        type=int,
        default=80,
        help="Gap before the next line appears. Default: 80.",
    )

    parser.add_argument(
        "--final-line-hold-ms",
        type=int,
        default=2500,
        help="How long to hold the final line after its first word if no next line exists. Default: 2500.",
    )

    parser.add_argument(
        "--long-tail-threshold-ms",
        type=int,
        default=3500,
        help="Flag lines where the last word starts a long time before the next line. Default: 3500.",
    )

    parser.add_argument(
        "--short-line-threshold-ms",
        type=int,
        default=1200,
        help="Flag lines with very short inferred display duration. Default: 1200.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    word_review_path = Path(args.word_review).resolve()
    output_path = Path(args.out).resolve()

    try:
        require_file(word_review_path, "Word review JSON")

        word_review = load_json(word_review_path)

        draft = build_draft(
            word_review=word_review,
            word_review_path=word_review_path,
            start_padding_seconds=args.start_padding_ms / 1000,
            next_line_gap_seconds=args.next_line_gap_ms / 1000,
            final_line_hold_seconds=args.final_line_hold_ms / 1000,
            long_tail_threshold_seconds=args.long_tail_threshold_ms / 1000,
            short_line_threshold_seconds=args.short_line_threshold_ms / 1000,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("")
        print("Karaoke draft created from singing-aligner word starts.")
        print(f"Output: {output_path}")
        print("")
        print(f"Sections:     {draft['alignment']['section_count']}")
        print(f"Lines:        {draft['alignment']['line_count']}")
        print(f"Review flags: {draft['alignment']['review_flag_count']}")
        print("")

        if draft["alignment"]["review_flags"]:
            print("Review flags:")
            for item in draft["alignment"]["review_flags"]:
                print(f"- {item['section']} | {item['line_id']} | {item['flag']} | {item['text']}")
            print("")

    except Exception as error:
        print("")
        print("Could not build karaoke draft.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())