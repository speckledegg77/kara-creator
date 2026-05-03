from __future__ import annotations

import argparse
import json
import statistics
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


def collect_ordered_lines(word_review: dict[str, Any]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []

    for section_index, section in enumerate(word_review.get("sections", [])):
        for line_index, line in enumerate(section.get("lines", [])):
            ordered.append(
                {
                    "section_index": section_index,
                    "section_id": section.get("id"),
                    "section_label": section.get("label"),
                    "line_index": line_index,
                    "id": line.get("id"),
                    "text": line.get("text", ""),
                    "display_type": line.get("display_type", "lyric"),
                    "review_flags": list(line.get("review_flags", [])),
                    "words": line.get("words", []),
                }
            )

    return ordered


def build_word_objects(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output_words = []

    for word in words:
        output_words.append(
            {
                "id": word.get("id"),
                "text": word.get("text"),
                "start": word.get("start"),
                "end": word.get("end"),
                "source": "lyrics-aligner-word-start",
            }
        )

    return output_words


def word_start_values(words: list[dict[str, Any]]) -> list[float]:
    starts = [as_float(word.get("start"), fallback=-1.0) for word in words]
    return [start for start in starts if start >= 0]


def internal_word_gaps_seconds(words: list[dict[str, Any]]) -> list[float]:
    starts = word_start_values(words)

    if len(starts) < 2:
        return []

    gaps = [next_start - current_start for current_start, next_start in zip(starts, starts[1:])]
    return [gap for gap in gaps if gap >= 0]


def max_internal_word_gap_seconds(words: list[dict[str, Any]]) -> float:
    gaps = internal_word_gaps_seconds(words)
    return max(gaps) if gaps else 0.0


def first_internal_word_gap_seconds(words: list[dict[str, Any]]) -> float:
    gaps = internal_word_gaps_seconds(words)
    return gaps[0] if gaps else 0.0


def later_internal_word_gap_typical_seconds(words: list[dict[str, Any]]) -> float:
    gaps = internal_word_gaps_seconds(words)

    if len(gaps) <= 1:
        return 0.0

    later_gaps = gaps[1:]

    if not later_gaps:
        return 0.0

    return float(statistics.median(later_gaps))


def should_auto_correct_first_word_anchor(
    words: list[dict[str, Any]],
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
) -> bool:
    starts = word_start_values(words)

    if len(starts) < 3:
        return False

    first_gap = first_internal_word_gap_seconds(words)

    if first_gap < suspicious_first_word_gap_seconds:
        return False

    later_typical_gap = later_internal_word_gap_typical_seconds(words)

    if later_typical_gap <= 0:
        return first_gap >= suspicious_first_word_gap_seconds

    return first_gap >= max(
        suspicious_first_word_gap_seconds,
        later_typical_gap * first_gap_ratio_threshold,
    )


def corrected_line_anchor_start(
    words: list[dict[str, Any]],
    start_padding_seconds: float,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
    auto_anchor_lead_in_min_seconds: float,
    auto_anchor_lead_in_max_seconds: float,
    auto_anchor_lead_in_gap_fraction: float,
) -> tuple[float, str, list[str], dict[str, float]]:
    starts = word_start_values(words)

    if not starts:
        return 0.0, "missing-word-starts", ["missing_word_starts_needs_review"], {}

    raw_first_start = starts[0]
    normal_display_start = max(0.0, raw_first_start - start_padding_seconds)
    flags: list[str] = []
    diagnostics = {
        "first_internal_word_gap": round_time(first_internal_word_gap_seconds(words)),
        "max_internal_word_gap": round_time(max_internal_word_gap_seconds(words)),
        "later_internal_word_gap_typical": round_time(later_internal_word_gap_typical_seconds(words)),
    }

    if not should_auto_correct_first_word_anchor(
        words=words,
        suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
        first_gap_ratio_threshold=first_gap_ratio_threshold,
    ):
        return normal_display_start, "first-word", flags, diagnostics

    first_gap = first_internal_word_gap_seconds(words)
    second_word_start = starts[1]
    lead_in = min(
        auto_anchor_lead_in_max_seconds,
        max(auto_anchor_lead_in_min_seconds, first_gap * auto_anchor_lead_in_gap_fraction),
    )
    corrected_start = max(0.0, second_word_start - lead_in)

    # If the correction barely moves the line, keep the simpler first-word anchor.
    if abs(corrected_start - normal_display_start) < 0.25:
        return normal_display_start, "first-word", flags, diagnostics

    diagnostics["auto_anchor_lead_in_seconds"] = round_time(lead_in)
    diagnostics["uncorrected_display_start"] = round_time(normal_display_start)
    diagnostics["auto_corrected_display_start"] = round_time(corrected_start)

    flags.extend(
        [
            "first_word_anchor_suspect",
            "line_start_auto_adjusted_needs_review",
        ]
    )

    return corrected_start, "corrected-word-cluster", flags, diagnostics


def previous_lyric_line(lines: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for index in range(start_index - 1, -1, -1):
        candidate = lines[index]

        if candidate.get("display_type") == "lyric" and candidate.get("start") is not None:
            return candidate

    return None


def next_lyric_line(lines: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for index in range(start_index + 1, len(lines)):
        candidate = lines[index]

        if candidate.get("display_type") == "lyric" and candidate.get("start") is not None:
            return candidate

    return None


def assign_instrumental_run(
    lines: list[dict[str, Any]],
    run_indexes: list[int],
    next_line_gap_seconds: float,
    instrumental_fallback_seconds: float,
    audio_duration_seconds: float | None,
    instrumental_after_previous_word_seconds: float,
    instrumental_before_next_line_seconds: float,
    starting_instrumental_before_first_line_seconds: float,
) -> None:
    if not run_indexes:
        return

    first_index = run_indexes[0]
    last_index = run_indexes[-1]
    previous_line = previous_lyric_line(lines, first_index)
    following_line = next_lyric_line(lines, last_index)
    count = len(run_indexes)
    min_each = 0.5
    total_minimum = count * min_each
    flags_for_all = ["instrumental_timing_needs_review"]

    if previous_line and following_line:
        following_start = as_float(following_line.get("start"))
        previous_start = as_float(previous_line.get("start"))
        previous_last_word_start = as_float(previous_line.get("last_word_start"), previous_start)

        gap_start = max(
            previous_start + 0.75,
            previous_last_word_start + instrumental_after_previous_word_seconds,
        )
        gap_end = following_start - max(next_line_gap_seconds, instrumental_before_next_line_seconds)

        if gap_end - gap_start < total_minimum:
            gap_start = max(
                0.0,
                following_start
                - max(next_line_gap_seconds, instrumental_before_next_line_seconds)
                - max(total_minimum, instrumental_fallback_seconds * count),
            )
            flags_for_all.append("instrumental_gap_too_short_needs_review")

        if gap_end <= gap_start:
            gap_end = gap_start + total_minimum
            flags_for_all.append("instrumental_overlap_risk_needs_review")

    elif following_line:
        following_start = as_float(following_line.get("start"))
        gap_start = 0.0
        gap_end = max(total_minimum, following_start - starting_instrumental_before_first_line_seconds)
        flags_for_all.append("instrumental_at_start_needs_review")

        if gap_end <= gap_start:
            gap_end = gap_start + max(total_minimum, instrumental_fallback_seconds * count)
            flags_for_all.append("instrumental_overlap_risk_needs_review")

    elif previous_line:
        previous_start = as_float(previous_line.get("start"))
        previous_last_word_start = as_float(previous_line.get("last_word_start"), previous_start)
        gap_start = max(
            previous_start + 0.75,
            previous_last_word_start + instrumental_after_previous_word_seconds,
        )

        if audio_duration_seconds and audio_duration_seconds > gap_start + min_each:
            gap_end = audio_duration_seconds
        else:
            gap_end = gap_start + instrumental_fallback_seconds * count

        flags_for_all.append("instrumental_at_end_needs_review")

    else:
        gap_start = 0.0
        gap_end = instrumental_fallback_seconds * count
        flags_for_all.append("instrumental_no_surrounding_lyrics_needs_review")

    available = max(total_minimum, gap_end - gap_start)
    segment = available / count

    for offset, line_index in enumerate(run_indexes):
        line_start = gap_start + (segment * offset)
        line_end = gap_start + (segment * (offset + 1))

        if offset < count - 1:
            line_end = max(line_start + min_each, line_end - next_line_gap_seconds)

        line = lines[line_index]
        line["start"] = round_time(line_start)
        line["end"] = round_time(max(line_start + min_each, line_end))
        line["confidence"] = "draft"
        line["locked"] = False
        line["anchor"] = False
        line["timing_source"] = "instrumental-placeholder-inferred"
        line["review_flags"] = sorted(set(list(line.get("review_flags", [])) + flags_for_all))
        line["words"] = []
        line["edited_manually"] = False


def assign_all_instrumental_timings(
    lines: list[dict[str, Any]],
    next_line_gap_seconds: float,
    instrumental_fallback_seconds: float,
    audio_duration_seconds: float | None,
    instrumental_after_previous_word_seconds: float,
    instrumental_before_next_line_seconds: float,
    starting_instrumental_before_first_line_seconds: float,
) -> None:
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.get("display_type") != "instrumental":
            index += 1
            continue

        run_indexes: list[int] = []

        while index < len(lines) and lines[index].get("display_type") == "instrumental":
            run_indexes.append(index)
            index += 1

        assign_instrumental_run(
            lines=lines,
            run_indexes=run_indexes,
            next_line_gap_seconds=next_line_gap_seconds,
            instrumental_fallback_seconds=instrumental_fallback_seconds,
            audio_duration_seconds=audio_duration_seconds,
            instrumental_after_previous_word_seconds=instrumental_after_previous_word_seconds,
            instrumental_before_next_line_seconds=instrumental_before_next_line_seconds,
            starting_instrumental_before_first_line_seconds=starting_instrumental_before_first_line_seconds,
        )


def next_display_line_with_timing(lines: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for index in range(start_index + 1, len(lines)):
        candidate = lines[index]

        if candidate.get("start") is not None:
            return candidate

    return None


def build_review_flags(
    line: dict[str, Any],
    next_display_line: dict[str, Any] | None,
    previous_display_line: dict[str, Any] | None,
    long_tail_threshold_seconds: float,
    short_line_threshold_seconds: float,
    large_internal_word_gap_seconds: float,
) -> list[str]:
    flags: list[str] = list(line.get("review_flags", []))

    line_start = as_float(line.get("start"))
    line_end = as_float(line.get("end"))
    last_word_start = as_float(line.get("last_word_start"), line_start)

    if next_display_line and next_display_line.get("display_type") != "instrumental":
        next_start = as_float(next_display_line.get("start"))
        tail_after_last_word = next_start - last_word_start

        if tail_after_last_word >= long_tail_threshold_seconds:
            flags.append("long_tail_after_last_word_needs_review")

    if previous_display_line:
        previous_start = as_float(previous_display_line.get("start"))

        if line_start < previous_start:
            flags.append("line_start_before_previous_line")

    if line_end - line_start <= short_line_threshold_seconds:
        flags.append("very_short_display_duration_needs_review")

    max_internal_gap = as_float(line.get("max_internal_word_gap"), fallback=0.0)

    if max_internal_gap >= large_internal_word_gap_seconds:
        flags.append("large_internal_word_gap_needs_review")

    return sorted(set(flags))


def build_draft(
    word_review: dict[str, Any],
    word_review_path: Path,
    start_padding_seconds: float,
    next_line_gap_seconds: float,
    final_line_hold_seconds: float,
    long_tail_threshold_seconds: float,
    short_line_threshold_seconds: float,
    large_internal_word_gap_seconds: float,
    instrumental_fallback_seconds: float,
    auto_correct_suspicious_first_word: bool,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
    auto_anchor_lead_in_min_seconds: float,
    auto_anchor_lead_in_max_seconds: float,
    auto_anchor_lead_in_gap_fraction: float,
    instrumental_after_previous_word_seconds: float,
    instrumental_before_next_line_seconds: float,
    starting_instrumental_before_first_line_seconds: float,
) -> dict[str, Any]:
    ordered_lines = collect_ordered_lines(word_review)

    if not ordered_lines:
        raise ValueError("No usable lines were found in the word review JSON.")

    lyric_line_count = 0

    for line in ordered_lines:
        words = line.get("words", [])
        display_type = line.get("display_type", "lyric")

        if display_type == "instrumental":
            line["text"] = ". . ."
            line["words"] = []
            continue

        if not words:
            continue

        first_word = words[0]
        last_word = words[-1]
        raw_start = as_float(first_word.get("start"))
        anchor_start = max(0.0, raw_start - start_padding_seconds)
        line_anchor_source = "first-word"
        anchor_flags: list[str] = []
        anchor_diagnostics = {
            "first_internal_word_gap": round_time(first_internal_word_gap_seconds(words)),
            "max_internal_word_gap": round_time(max_internal_word_gap_seconds(words)),
            "later_internal_word_gap_typical": round_time(later_internal_word_gap_typical_seconds(words)),
        }

        if auto_correct_suspicious_first_word:
            anchor_start, line_anchor_source, anchor_flags, anchor_diagnostics = corrected_line_anchor_start(
                words=words,
                start_padding_seconds=start_padding_seconds,
                suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
                first_gap_ratio_threshold=first_gap_ratio_threshold,
                auto_anchor_lead_in_min_seconds=auto_anchor_lead_in_min_seconds,
                auto_anchor_lead_in_max_seconds=auto_anchor_lead_in_max_seconds,
                auto_anchor_lead_in_gap_fraction=auto_anchor_lead_in_gap_fraction,
            )

        line["display_type"] = "lyric"
        line["start"] = round_time(anchor_start)
        line["end"] = None
        line["word_start"] = round_time(raw_start)
        line["last_word_start"] = round_time(as_float(last_word.get("start")))
        line["line_anchor_start"] = round_time(anchor_start)
        line["line_anchor_source"] = line_anchor_source
        line["confidence"] = "draft"
        line["locked"] = False
        line["anchor"] = False
        line["timing_source"] = "lyrics-aligner-word-starts" if line_anchor_source == "first-word" else "lyrics-aligner-corrected-word-cluster"
        line["review_flags"] = sorted(set(list(line.get("review_flags", [])) + anchor_flags))
        line["words"] = build_word_objects(words)
        line["first_internal_word_gap"] = round_time(first_internal_word_gap_seconds(words))
        line["max_internal_word_gap"] = round_time(max_internal_word_gap_seconds(words))
        line["later_internal_word_gap_typical"] = round_time(later_internal_word_gap_typical_seconds(words))
        line["anchor_diagnostics"] = anchor_diagnostics
        line["edited_manually"] = False
        lyric_line_count += 1

    if lyric_line_count == 0:
        raise ValueError("No lyric lines with word timings were found in the word review JSON.")

    audio_duration_raw = word_review.get("source", {}).get("audio_duration_seconds")
    audio_duration_seconds = None if audio_duration_raw is None else as_float(audio_duration_raw, fallback=0.0)

    assign_all_instrumental_timings(
        lines=ordered_lines,
        next_line_gap_seconds=next_line_gap_seconds,
        instrumental_fallback_seconds=instrumental_fallback_seconds,
        audio_duration_seconds=audio_duration_seconds,
        instrumental_after_previous_word_seconds=instrumental_after_previous_word_seconds,
        instrumental_before_next_line_seconds=instrumental_before_next_line_seconds,
        starting_instrumental_before_first_line_seconds=starting_instrumental_before_first_line_seconds,
    )

    for index, line in enumerate(ordered_lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        next_display_line = next_display_line_with_timing(ordered_lines, index)

        if next_display_line:
            display_end = max(
                as_float(line.get("start")) + 0.1,
                as_float(next_display_line.get("start")) - next_line_gap_seconds,
            )
        else:
            display_end = as_float(line.get("line_anchor_start", line.get("word_start"))) + final_line_hold_seconds

        line["end"] = round_time(display_end)

    for index, line in enumerate(ordered_lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        previous_display_line = None
        for previous_index in range(index - 1, -1, -1):
            if ordered_lines[previous_index].get("start") is not None:
                previous_display_line = ordered_lines[previous_index]
                break

        next_display_line = next_display_line_with_timing(ordered_lines, index)
        line["review_flags"] = build_review_flags(
            line=line,
            next_display_line=next_display_line,
            previous_display_line=previous_display_line,
            long_tail_threshold_seconds=long_tail_threshold_seconds,
            short_line_threshold_seconds=short_line_threshold_seconds,
            large_internal_word_gap_seconds=large_internal_word_gap_seconds,
        )

    output_sections: list[dict[str, Any]] = []

    for section_index, source_section in enumerate(word_review.get("sections", [])):
        output_lines: list[dict[str, Any]] = []

        for line in ordered_lines:
            if line.get("section_index") != section_index:
                continue

            if line.get("start") is None or line.get("end") is None:
                continue

            output_lines.append(
                {
                    "id": line.get("id"),
                    "display_type": line.get("display_type", "lyric"),
                    "text": line.get("text", ""),
                    "start": line.get("start"),
                    "end": line.get("end"),
                    **({"word_start": line.get("word_start")} if line.get("display_type") == "lyric" else {}),
                    **({"last_word_start": line.get("last_word_start")} if line.get("display_type") == "lyric" else {}),
                    **({"line_anchor_start": line.get("line_anchor_start")} if line.get("display_type") == "lyric" else {}),
                    **({"line_anchor_source": line.get("line_anchor_source")} if line.get("display_type") == "lyric" else {}),
                    **({"first_internal_word_gap": line.get("first_internal_word_gap", 0.0)} if line.get("display_type") == "lyric" else {}),
                    **({"max_internal_word_gap": line.get("max_internal_word_gap", 0.0)} if line.get("display_type") == "lyric" else {}),
                    **({"later_internal_word_gap_typical": line.get("later_internal_word_gap_typical", 0.0)} if line.get("display_type") == "lyric" else {}),
                    **({"anchor_diagnostics": line.get("anchor_diagnostics", {})} if line.get("display_type") == "lyric" else {}),
                    "confidence": line.get("confidence", "draft"),
                    "locked": line.get("locked", False),
                    "anchor": line.get("anchor", False),
                    "timing_source": line.get("timing_source", "unknown"),
                    "review_flags": line.get("review_flags", []),
                    "words": line.get("words", []),
                    "edited_manually": line.get("edited_manually", False),
                }
            )

        if output_lines:
            output_sections.append(
                {
                    "id": source_section.get("id"),
                    "label": source_section.get("label"),
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

    auto_adjusted_line_count = sum(
        1
        for section in output_sections
        for line in section["lines"]
        if line.get("line_anchor_source") == "corrected-word-cluster"
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
            "lyric_line_count": sum(1 for section in output_sections for line in section["lines"] if line.get("display_type") == "lyric"),
            "instrumental_line_count": sum(1 for section in output_sections for line in section["lines"] if line.get("display_type") == "instrumental"),
            "section_count": len(output_sections),
            "auto_adjusted_line_count": auto_adjusted_line_count,
            "settings": {
                "start_padding_seconds": start_padding_seconds,
                "next_line_gap_seconds": next_line_gap_seconds,
                "final_line_hold_seconds": final_line_hold_seconds,
                "long_tail_threshold_seconds": long_tail_threshold_seconds,
                "short_line_threshold_seconds": short_line_threshold_seconds,
                "large_internal_word_gap_seconds": large_internal_word_gap_seconds,
                "instrumental_fallback_seconds": instrumental_fallback_seconds,
                "auto_correct_suspicious_first_word": auto_correct_suspicious_first_word,
                "suspicious_first_word_gap_seconds": suspicious_first_word_gap_seconds,
                "first_gap_ratio_threshold": first_gap_ratio_threshold,
                "auto_anchor_lead_in_min_seconds": auto_anchor_lead_in_min_seconds,
                "auto_anchor_lead_in_max_seconds": auto_anchor_lead_in_max_seconds,
                "auto_anchor_lead_in_gap_fraction": auto_anchor_lead_in_gap_fraction,
                "instrumental_after_previous_word_seconds": instrumental_after_previous_word_seconds,
                "instrumental_before_next_line_seconds": instrumental_before_next_line_seconds,
                "starting_instrumental_before_first_line_seconds": starting_instrumental_before_first_line_seconds,
            },
            "review_flag_count": len(review_flags),
            "review_flags": review_flags,
        },
        "sections": output_sections,
        "editor_notes": [
            "This draft uses singing-specific word starts as timing anchors.",
            "Line starts normally come from the first word in each lyric line.",
            "If the first word looks like an early outlier, the line start may be auto-adjusted from the later word cluster and flagged for review.",
            "Line ends are inferred from the next display line, not from word endings.",
            "Instrumental placeholders are kept as editable display lines with empty words arrays.",
            "Lines with long held notes, suspicious internal word gaps, short timings, inferred instrumental timings, or auto-adjusted starts are flagged for review.",
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
        help="Path to karaoke-word-review JSON created from lyrics-aligner.",
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
        help="Gap before the next display line appears. Default: 80.",
    )

    parser.add_argument(
        "--final-line-hold-ms",
        type=int,
        default=2500,
        help="How long to hold the final line after its anchor if no next line exists. Default: 2500.",
    )

    parser.add_argument(
        "--long-tail-threshold-ms",
        type=int,
        default=3500,
        help="Flag lines where the last word starts a long time before the next display line. Default: 3500.",
    )

    parser.add_argument(
        "--short-line-threshold-ms",
        type=int,
        default=1200,
        help="Flag lines with very short inferred display duration. Default: 1200.",
    )

    parser.add_argument(
        "--large-internal-word-gap-ms",
        type=int,
        default=1750,
        help="Flag lyric lines where word starts inside the same line have a large gap. Default: 1750.",
    )

    parser.add_argument(
        "--instrumental-fallback-ms",
        type=int,
        default=2500,
        help="Fallback duration for instrumental placeholders at the start or end. Default: 2500.",
    )

    parser.add_argument(
        "--no-auto-correct-suspicious-first-word",
        action="store_true",
        help="Turn off experimental correction for suspicious first-word anchors.",
    )

    parser.add_argument(
        "--suspicious-first-word-gap-ms",
        type=int,
        default=1750,
        help="Auto-adjust a line if the first-to-second word gap is at least this large and looks like an outlier. Default: 1750.",
    )

    parser.add_argument(
        "--first-gap-ratio-threshold",
        type=float,
        default=2.5,
        help="The first word gap must be this many times larger than the typical later gap before auto-adjusting. Default: 2.5.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-min-ms",
        type=int,
        default=350,
        help="Minimum lead-in before the second word when auto-adjusting a suspicious line start. Default: 350.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-max-ms",
        type=int,
        default=1000,
        help="Maximum lead-in before the second word when auto-adjusting a suspicious line start. Default: 1000.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-gap-fraction",
        type=float,
        default=0.33,
        help="Lead-in as a fraction of the suspicious first-word gap. Default: 0.33.",
    )

    parser.add_argument(
        "--instrumental-after-previous-word-ms",
        type=int,
        default=2500,
        help="For instrumental gaps, start this long after the previous lyric line's last word start. Default: 2500.",
    )

    parser.add_argument(
        "--instrumental-before-next-line-ms",
        type=int,
        default=500,
        help="For instrumental gaps, end this long before the next lyric line starts. Default: 500.",
    )

    parser.add_argument(
        "--starting-instrumental-before-first-line-ms",
        type=int,
        default=1500,
        help="For an opening instrumental, end this long before the first lyric line starts. Default: 1500.",
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
            large_internal_word_gap_seconds=args.large_internal_word_gap_ms / 1000,
            instrumental_fallback_seconds=args.instrumental_fallback_ms / 1000,
            auto_correct_suspicious_first_word=not args.no_auto_correct_suspicious_first_word,
            suspicious_first_word_gap_seconds=args.suspicious_first_word_gap_ms / 1000,
            first_gap_ratio_threshold=args.first_gap_ratio_threshold,
            auto_anchor_lead_in_min_seconds=args.auto_anchor_lead_in_min_ms / 1000,
            auto_anchor_lead_in_max_seconds=args.auto_anchor_lead_in_max_ms / 1000,
            auto_anchor_lead_in_gap_fraction=args.auto_anchor_lead_in_gap_fraction,
            instrumental_after_previous_word_seconds=args.instrumental_after_previous_word_ms / 1000,
            instrumental_before_next_line_seconds=args.instrumental_before_next_line_ms / 1000,
            starting_instrumental_before_first_line_seconds=args.starting_instrumental_before_first_line_ms / 1000,
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
        print(f"Sections:            {draft['alignment']['section_count']}")
        print(f"Display lines:       {draft['alignment']['line_count']}")
        print(f"Lyric lines:         {draft['alignment']['lyric_line_count']}")
        print(f"Instrumentals:       {draft['alignment']['instrumental_line_count']}")
        print(f"Auto-adjusted lines: {draft['alignment']['auto_adjusted_line_count']}")
        print(f"Review flags:        {draft['alignment']['review_flag_count']}")
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
