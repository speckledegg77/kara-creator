from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
INSTRUMENTAL_TEXT = ". . ."


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as error:
        raise SystemExit(f"Could not read JSON: {path}\n{error}")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def as_float(value: Any, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(number) or math.isinf(number):
        return fallback
    return number


def round_time(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def line_id(line: dict[str, Any]) -> str:
    return str(line.get("id", ""))


def display_type(line: dict[str, Any]) -> str:
    return str(line.get("display_type", "lyric") or "lyric")


def is_lyric(line: dict[str, Any]) -> bool:
    return display_type(line) == "lyric"


def is_instrumental(line: dict[str, Any]) -> bool:
    return display_type(line) == "instrumental"


def words_for(line: dict[str, Any]) -> list[dict[str, Any]]:
    words = line.get("words", [])
    if not isinstance(words, list):
        return []
    output: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            continue
        copied = deepcopy(word)
        copied.setdefault("id", f"word-{index + 1:04d}")
        copied.setdefault("source", copied.get("source", "lyrics-aligner-word-start"))
        output.append(copied)
    return output


def lyric_word_start(line: dict[str, Any]) -> float | None:
    words = words_for(line)
    starts = [as_float(word.get("start")) for word in words]
    starts = [value for value in starts if value is not None]
    if starts:
        return min(starts)
    return as_float(line.get("start"))


def lyric_word_end(line: dict[str, Any]) -> float | None:
    words = words_for(line)
    ends = [as_float(word.get("end")) for word in words]
    ends = [value for value in ends if value is not None]
    if ends:
        return max(ends)
    return as_float(line.get("end"))


def flatten_lines(word_review: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    output: list[tuple[int, int, dict[str, Any]]] = []
    sections = word_review.get("sections", [])
    if not isinstance(sections, list):
        return output
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            continue
        for line_index, line in enumerate(lines):
            if isinstance(line, dict):
                output.append((section_index, line_index, line))
    return output


def add_flag(line: dict[str, Any], flag: str) -> None:
    flags = line.get("review_flags")
    if not isinstance(flags, list):
        flags = []
    if flag not in flags:
        flags.append(flag)
    line["review_flags"] = flags


def build_raw_lines(flat_lines: list[tuple[int, int, dict[str, Any]]], *, start_padding: float, next_line_gap: float, instrumental_before_next: float, starting_instrumental_before_first: float, final_line_hold: float) -> list[dict[str, Any]]:
    working: list[dict[str, Any]] = []

    for _, _, source_line in flat_lines:
        line = deepcopy(source_line)
        words = words_for(line)
        dtype = display_type(line)
        text = str(line.get("text", ""))

        if dtype == "instrumental":
            line["text"] = INSTRUMENTAL_TEXT
            line["display_type"] = "instrumental"
            line["words"] = []
            line["word_start"] = None
            line["last_word_start"] = None
            line["raw_word_end"] = None
        else:
            line["display_type"] = "lyric"
            line["text"] = text
            line["words"] = words
            starts = [as_float(word.get("start")) for word in words]
            starts = [value for value in starts if value is not None]
            ends = [as_float(word.get("end")) for word in words]
            ends = [value for value in ends if value is not None]
            first = min(starts) if starts else as_float(line.get("start"))
            last_start = max(starts) if starts else first
            raw_end = max(ends) if ends else as_float(line.get("end"))
            line["word_start"] = round_time(first)
            line["last_word_start"] = round_time(last_start)
            line["raw_word_end"] = round_time(raw_end)

        line["confidence"] = "draft"
        line["locked"] = bool(line.get("locked", False))
        line["anchor"] = bool(line.get("anchor", False))
        line["edited_manually"] = bool(line.get("edited_manually", False))
        working.append(line)

    # Initial starts.
    for index, line in enumerate(working):
        if is_lyric(line):
            first = as_float(line.get("word_start"))
            if first is not None:
                line["start"] = round_time(max(0.0, first - start_padding))
                line["line_anchor_start"] = line["start"]
                line["line_anchor_source"] = "raw-word-review-first-word"
                line["timing_source"] = "raw-word-review"
            else:
                line["start"] = round_time(as_float(line.get("start"), 0.0) or 0.0)
                line["timing_source"] = "raw-word-review-missing-words"
                add_flag(line, "raw_review_missing_word_timing_needs_review")
        else:
            line["timing_source"] = "raw-instrumental-placeholder-inferred"

    # Instrumental timings.
    for index, line in enumerate(working):
        if not is_instrumental(line):
            continue

        previous_lyric = None
        for previous_index in range(index - 1, -1, -1):
            if is_lyric(working[previous_index]):
                previous_lyric = working[previous_index]
                break

        next_lyric = None
        for next_index in range(index + 1, len(working)):
            if is_lyric(working[next_index]):
                next_lyric = working[next_index]
                break

        previous_end = as_float(previous_lyric.get("raw_word_end")) if previous_lyric else None
        next_start = as_float(next_lyric.get("start")) if next_lyric else None
        audio_duration = None

        if previous_end is None and next_start is not None:
            start = 0.0
            end = max(start, next_start - starting_instrumental_before_first)
            add_flag(line, "instrumental_at_start_needs_review")
        elif previous_end is not None and next_start is not None:
            start = previous_end + next_line_gap
            end = max(start + 0.1, next_start - instrumental_before_next)
            add_flag(line, "instrumental_timing_needs_review")
        elif previous_end is not None:
            start = previous_end + next_line_gap
            end = start + final_line_hold
            add_flag(line, "instrumental_at_end_needs_review")
        else:
            start = 0.0
            end = final_line_hold
            add_flag(line, "instrumental_timing_needs_review")

        line["start"] = round_time(start)
        line["end"] = round_time(end)

    # Lyric display ends.
    for index, line in enumerate(working):
        if not is_lyric(line):
            continue

        next_display_start = None
        for next_index in range(index + 1, len(working)):
            candidate = working[next_index]
            start = as_float(candidate.get("start"))
            if start is not None:
                next_display_start = start
                break

        raw_end = as_float(line.get("raw_word_end"))
        start = as_float(line.get("start"), 0.0) or 0.0
        if next_display_start is not None:
            end = max(start + 0.1, next_display_start - next_line_gap)
            source = "raw-inferred-from-next-display-line"
        elif raw_end is not None:
            end = max(start + 0.1, raw_end + final_line_hold)
            source = "raw-final-line-hold"
        else:
            end = start + final_line_hold
            source = "raw-fallback-line-end"
            add_flag(line, "raw_review_missing_end_timing_needs_review")

        line["end"] = round_time(end)
        line["line_end_source"] = source
        line["line_end_confidence"] = "raw"
        line["line_end_diagnostics"] = {
            "raw_builder": True,
            "aggressive_rescues_enabled": False,
        }

    # Guard monotonic overlaps without shifting lines before their own words.
    previous_end = None
    for line in working:
        start = as_float(line.get("start"))
        end = as_float(line.get("end"))
        if start is None:
            continue
        if previous_end is not None and start < previous_end - 0.001:
            add_flag(line, "raw_review_overlap_with_previous_needs_review")
        if end is not None and end <= start:
            line["end"] = round_time(start + 0.1)
            add_flag(line, "raw_review_short_duration_rescued_needs_review")
        previous_end = as_float(line.get("end"), previous_end)

    return working


def rebuild_sections(word_review: dict[str, Any], raw_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections_out: list[dict[str, Any]] = []
    cursor = 0

    for section_index, section in enumerate(word_review.get("sections", []), start=1):
        if not isinstance(section, dict):
            continue
        source_lines = section.get("lines", [])
        count = len(source_lines) if isinstance(source_lines, list) else 0
        lines = raw_lines[cursor:cursor + count]
        cursor += count

        starts = [as_float(line.get("start")) for line in lines]
        starts = [value for value in starts if value is not None]
        ends = [as_float(line.get("end")) for line in lines]
        ends = [value for value in ends if value is not None]

        section_out = {
            "id": section.get("id", f"section-{section_index:03d}"),
            "label": section.get("label", f"Section {section_index}"),
            "source": section.get("source"),
            "parser_mode": section.get("parser_mode"),
            "start": round_time(min(starts)) if starts else None,
            "end": round_time(max(ends)) if ends else None,
            "lines": lines,
        }
        sections_out.append(section_out)

    return sections_out


def collect_review_flags(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    for section in sections:
        label = str(section.get("label", ""))
        for line in section.get("lines", []):
            if not isinstance(line, dict):
                continue
            line_flags = line.get("review_flags", [])
            if not isinstance(line_flags, list):
                continue
            for flag in line_flags:
                flags.append(
                    {
                        "section": label,
                        "line_id": str(line.get("id", "")),
                        "text": str(line.get("text", "")),
                        "flag": str(flag),
                    }
                )
    return flags


def collect_all_words(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_words: list[dict[str, Any]] = []
    index = 0
    for section in sections:
        for line in section.get("lines", []):
            if not isinstance(line, dict) or not is_lyric(line):
                continue
            for word in line.get("words", []):
                if not isinstance(word, dict):
                    continue
                copied = deepcopy(word)
                copied["index"] = index
                copied["line_id"] = line.get("id")
                copied["line_text"] = line.get("text")
                all_words.append(copied)
                index += 1
    return all_words


def build_draft(word_review: dict[str, Any], source_word_review_path: Path, *, start_padding: float, next_line_gap: float, instrumental_before_next: float, starting_instrumental_before_first: float, final_line_hold: float) -> dict[str, Any]:
    flat = flatten_lines(word_review)
    raw_lines = build_raw_lines(
        flat,
        start_padding=start_padding,
        next_line_gap=next_line_gap,
        instrumental_before_next=instrumental_before_next,
        starting_instrumental_before_first=starting_instrumental_before_first,
        final_line_hold=final_line_hold,
    )
    sections = rebuild_sections(word_review, raw_lines)
    flags = collect_review_flags(sections)
    all_words = collect_all_words(sections)

    source = deepcopy(word_review.get("source", {}))
    source["word_review_json"] = str(source_word_review_path)

    lyric_count = sum(1 for _, _, line in flat if is_lyric(line))
    instrumental_count = sum(1 for _, _, line in flat if is_instrumental(line))

    return {
        "schema_version": "karaoke-draft-v3",
        "created_by": "kara-creator raw review draft builder",
        "source": source,
        "alignment": {
            "mode": "raw-word-review-to-line-draft",
            "status": "review-draft",
            "primary_aligner": word_review.get("alignment", {}).get("primary_aligner", "lyrics-aligner"),
            "builder_version": VERSION,
            "line_count": len(flat),
            "lyric_line_count": lyric_count,
            "instrumental_line_count": instrumental_count,
            "section_count": len(sections),
            "review_flag_count": len(flags),
            "review_flags": flags,
            "settings": {
                "start_padding_seconds": start_padding,
                "next_line_gap_seconds": next_line_gap,
                "instrumental_before_next_line_seconds": instrumental_before_next,
                "starting_instrumental_before_first_line_seconds": starting_instrumental_before_first,
                "final_line_hold_seconds": final_line_hold,
                "aggressive_rescues_enabled": False,
                "local_recovery_can_be_applied_after_review": True,
            },
        },
        "sections": sections,
        "all_words": all_words,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a conservative review draft directly from a karaoke word-review JSON without broad automatic rescue rules."
    )
    parser.add_argument("--word-review", required=True, help="Path to karaoke-word-review-v2 JSON.")
    parser.add_argument("--out", required=True, help="Path for the raw review karaoke-draft-v3 JSON.")
    parser.add_argument("--start-padding", type=float, default=0.15, help="Seconds to show a lyric line before its first word. Default: 0.15.")
    parser.add_argument("--next-line-gap", type=float, default=0.08, help="Gap before the next display line. Default: 0.08.")
    parser.add_argument("--instrumental-before-next", type=float, default=0.5, help="Seconds to leave before the next lyric after an instrumental. Default: 0.5.")
    parser.add_argument("--starting-instrumental-before-first", type=float, default=1.5, help="Seconds to leave before the first lyric after a starting instrumental. Default: 1.5.")
    parser.add_argument("--final-line-hold", type=float, default=2.5, help="Seconds to hold the final line when there is no next line. Default: 2.5.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    word_review_path = Path(args.word_review).resolve()
    out_path = Path(args.out).resolve()
    word_review = load_json(word_review_path)
    draft = build_draft(
        word_review,
        word_review_path,
        start_padding=max(0.0, args.start_padding),
        next_line_gap=max(0.0, args.next_line_gap),
        instrumental_before_next=max(0.0, args.instrumental_before_next),
        starting_instrumental_before_first=max(0.0, args.starting_instrumental_before_first),
        final_line_hold=max(0.1, args.final_line_hold),
    )
    write_json(out_path, draft)

    print("Raw review draft created.")
    print(f"Word review: {word_review_path}")
    print(f"Draft:       {out_path}")
    print(f"Lines:       {draft['alignment']['line_count']}")
    print(f"Flags:       {draft['alignment']['review_flag_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
