from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any


VERSION = "0.1.0"


# These defaults are deliberately conservative. The aim is not to prove a line is
# wrong. The aim is to highlight lines where the aligner or draft builder may need
# review before the JSON is treated as final.
DEFAULT_LARGE_INTERNAL_GAP_SECONDS = 1.75
DEFAULT_VERY_LARGE_INTERNAL_GAP_SECONDS = 3.0
DEFAULT_SUSPICIOUS_FIRST_GAP_SECONDS = 1.75
DEFAULT_MIN_DISPLAY_DURATION_SECONDS = 0.75
DEFAULT_VERY_SHORT_DURATION_SECONDS = 0.4
DEFAULT_SHORT_INSTRUMENTAL_SECONDS = 3.0
DEFAULT_LONG_TAIL_SECONDS = 4.0
DEFAULT_SHORT_FINAL_HOLD_SECONDS = 0.6
DEFAULT_RATIO_THRESHOLD = 2.5


TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as error:
        raise SystemExit(f"Could not read JSON: {path}\n{error}")


def as_float(value: Any, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    try:
        result = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(result) or math.isinf(result):
        return fallback
    return result


def round_or_blank(value: Any, digits: int = 3) -> str:
    number = as_float(value)
    if number is None:
        return ""
    return f"{round(number, digits):.{digits}f}"


def text_words(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text or "")]


def join_flags(flags: Any) -> str:
    if not flags:
        return ""
    if isinstance(flags, list):
        return "|".join(str(flag) for flag in flags)
    return str(flags)


def words_from_line(line: dict[str, Any]) -> list[dict[str, Any]]:
    words = line.get("words", [])
    if isinstance(words, list):
        return [word for word in words if isinstance(word, dict)]
    return []


def get_word_starts(words: list[dict[str, Any]]) -> list[float]:
    starts: list[float] = []
    for word in words:
        start = as_float(word.get("start"))
        if start is not None:
            starts.append(start)
    return starts


def gap_details(words: list[dict[str, Any]]) -> tuple[list[float], float, float, int, str, str]:
    starts = get_word_starts(words)
    if len(starts) < 2:
        return [], 0.0, 0.0, -1, "", ""

    gaps = [starts[index + 1] - starts[index] for index in range(len(starts) - 1)]
    max_gap = max(gaps) if gaps else 0.0
    first_gap = gaps[0] if gaps else 0.0
    max_index = gaps.index(max_gap) if gaps else -1

    before = ""
    after = ""
    if 0 <= max_index < len(words) - 1:
        before = str(words[max_index].get("text", ""))
        after = str(words[max_index + 1].get("text", ""))

    return gaps, first_gap, max_gap, max_index, before, after


def typical_later_gap(gaps: list[float]) -> float:
    if not gaps:
        return 0.0
    later = gaps[1:] if len(gaps) > 1 else gaps
    return float(median(later)) if later else 0.0


def flatten_lines(document: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_row: dict[str, Any] | None = None

    for section_index, section in enumerate(document.get("sections", []), start=1):
        section_id = str(section.get("id", ""))
        section_label = str(section.get("label", f"Section {section_index}")).strip() or f"Section {section_index}"
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            continue

        for line_index, line in enumerate(lines, start=1):
            if not isinstance(line, dict):
                continue

            words = words_from_line(line)
            word_starts = get_word_starts(words)
            gaps, first_gap, max_gap, max_gap_index, max_gap_before, max_gap_after = gap_details(words)
            typical_gap = typical_later_gap(gaps)

            start = as_float(line.get("start"))
            end = as_float(line.get("end"))
            word_start = as_float(line.get("word_start"))
            last_word_start = as_float(line.get("last_word_start"))

            duration = (end - start) if start is not None and end is not None else None
            start_to_first_word = (word_start - start) if start is not None and word_start is not None else None
            final_word_hold = (end - last_word_start) if end is not None and last_word_start is not None else None
            word_span = (last_word_start - word_start) if word_start is not None and last_word_start is not None else None

            row: dict[str, Any] = {
                "section": section_label,
                "section_id": section_id,
                "line_id": str(line.get("id", "")),
                "line_index_in_section": line_index,
                "display_type": str(line.get("display_type", "lyric")),
                "text": str(line.get("text", "")),
                "start": start,
                "end": end,
                "duration": duration,
                "word_start": word_start,
                "last_word_start": last_word_start,
                "word_span": word_span,
                "start_to_first_word": start_to_first_word,
                "final_word_hold": final_word_hold,
                "word_count": len(words),
                "text_word_count": len(text_words(str(line.get("text", "")))),
                "first_internal_word_gap": as_float(line.get("first_internal_word_gap"), first_gap) or 0.0,
                "max_internal_word_gap": as_float(line.get("max_internal_word_gap"), max_gap) or 0.0,
                "computed_first_word_gap": first_gap,
                "computed_max_word_gap": max_gap,
                "computed_later_gap_typical": typical_gap,
                "max_gap_index": max_gap_index,
                "max_gap_before_word": max_gap_before,
                "max_gap_after_word": max_gap_after,
                "line_anchor_source": str(line.get("line_anchor_source", "")),
                "line_end_source": str(line.get("line_end_source", "")),
                "line_end_confidence": str(line.get("line_end_confidence", "")),
                "timing_source": str(line.get("timing_source", "")),
                "review_flags": line.get("review_flags", []),
                "review_flags_joined": join_flags(line.get("review_flags", [])),
                "edited_manually": bool(line.get("edited_manually", False)),
                "raw_line": line,
                "previous_line_id": previous_row.get("line_id", "") if previous_row else "",
                "previous_display_type": previous_row.get("display_type", "") if previous_row else "",
                "previous_text": previous_row.get("text", "") if previous_row else "",
                "gap_from_previous_end": None,
                "next_line_id": "",
                "next_display_type": "",
                "next_text": "",
                "gap_to_next_start": None,
            }

            if previous_row and start is not None and previous_row.get("end") is not None:
                row["gap_from_previous_end"] = start - previous_row["end"]
                previous_row["gap_to_next_start"] = start - previous_row["end"]
                previous_row["next_line_id"] = row["line_id"]
                previous_row["next_display_type"] = row["display_type"]
                previous_row["next_text"] = row["text"]

            rows.append(row)
            previous_row = row

    return rows


def has_flag(row: dict[str, Any], needle: str) -> bool:
    flags = row.get("review_flags", [])
    if isinstance(flags, list):
        return any(needle in str(flag) for flag in flags)
    return needle in str(flags)


def contains_unusual_token(text: str) -> bool:
    # This is not a judgement that the word is wrong. It simply marks things that
    # often benefit from a pronunciation/tokenisation check in sung alignment.
    if re.search(r"[-–—]", text):
        return True
    if re.search(r"['’]", text):
        return True
    for token in text_words(text):
        if len(token) >= 12:
            return True
    return False


def repeated_single_word_context(row: dict[str, Any], rows_by_index: list[dict[str, Any]], index: int) -> bool:
    if row.get("display_type") != "lyric":
        return False
    words = text_words(row.get("text", ""))
    if len(words) != 1:
        return False
    current_word = words[0]
    previous = rows_by_index[index - 1] if index > 0 else None
    if not previous:
        return False
    previous_words = text_words(previous.get("text", ""))
    return bool(previous_words and previous_words[-1] == current_word)


def classify_row(row: dict[str, Any], rows: list[dict[str, Any]], index: int, args: argparse.Namespace) -> tuple[int, list[str], str]:
    categories: list[str] = []
    actions: list[str] = []
    severity = 0

    display_type = row.get("display_type", "lyric")
    duration = as_float(row.get("duration"))
    max_gap = as_float(row.get("max_internal_word_gap"), 0.0) or 0.0
    first_gap = as_float(row.get("first_internal_word_gap"), 0.0) or 0.0
    typical_gap = as_float(row.get("computed_later_gap_typical"), 0.0) or 0.0
    final_hold = as_float(row.get("final_word_hold"))
    start_to_first = as_float(row.get("start_to_first_word"))
    word_count = int(row.get("word_count", 0) or 0)
    text = str(row.get("text", ""))
    timing_source = str(row.get("timing_source", ""))
    line_anchor_source = str(row.get("line_anchor_source", ""))
    previous_type = str(row.get("previous_display_type", ""))
    next_type = str(row.get("next_display_type", ""))

    if display_type == "instrumental":
        categories.append("instrumental_placeholder")
        if duration is not None and duration < args.short_instrumental_seconds:
            categories.append("short_instrumental_placeholder")
            actions.append("Check whether the . . . line needs more time or whether the next lyric starts too early.")
            severity += 35
        if has_flag(row, "instrumental"):
            severity += 10
        if not actions:
            actions.append("Check only if the visual instrumental gap feels wrong in the editor.")
        return severity, categories, " ".join(actions)

    if duration is not None and duration < args.very_short_duration_seconds:
        categories.append("very_short_display_duration")
        actions.append("Check immediately in the editor. This line is probably too short to read.")
        severity += 60
    elif duration is not None and duration < args.min_display_duration_seconds:
        categories.append("short_display_duration")
        actions.append("Check readability and timing. The display duration is short.")
        severity += 30

    if max_gap >= args.very_large_internal_gap_seconds:
        categories.append("very_large_internal_word_gap")
        actions.append("Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair.")
        severity += 55
    elif max_gap >= args.large_internal_gap_seconds:
        categories.append("large_internal_word_gap")
        actions.append("Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate.")
        severity += 35

    if first_gap >= args.suspicious_first_gap_seconds:
        categories.append("first_word_anchor_suspect")
        actions.append("Check whether the first word has been placed too early or too late.")
        severity += 25

    if typical_gap > 0 and first_gap / typical_gap >= args.ratio_threshold and first_gap >= 0.9:
        categories.append("first_gap_outlier")
        actions.append("Compare the first word against the rest of the line. The opening anchor may be unreliable.")
        severity += 20

    if has_flag(row, "first_word_anchor_suspect"):
        if "first_word_anchor_suspect" not in categories:
            categories.append("first_word_anchor_suspect")
        severity += 10

    if has_flag(row, "large_internal_word_gap"):
        if "large_internal_word_gap" not in categories and "very_large_internal_word_gap" not in categories:
            categories.append("large_internal_word_gap")
        severity += 10

    if has_flag(row, "repeated_final_word") or repeated_single_word_context(row, rows, index):
        categories.append("repeated_word_or_held_word_collapse")
        actions.append("Check repeated-word timing. If word anchors are collapsed, a local realignment or repeated-word recovery is needed.")
        severity += 35

    if previous_type == "instrumental" and (max_gap >= args.large_internal_gap_seconds or has_flag(row, "first_word_anchor_suspect")):
        categories.append("post_instrumental_reentry_suspect")
        actions.append("Check the first vocal entry after . . . . The next lyric may start later than the aligner thinks.")
        severity += 35

    if next_type == "instrumental" and final_hold is not None and final_hold < args.short_final_hold_seconds:
        categories.append("possible_line_end_too_early_before_instrumental")
        actions.append("The final word may be held into the instrumental. Check the audio-backed line end.")
        severity += 30

    if final_hold is not None and final_hold >= args.long_tail_seconds:
        categories.append("long_tail_after_last_word")
        actions.append("Check whether the line should really remain visible this long after the final word start.")
        severity += 20

    if contains_unusual_token(text) and (max_gap >= args.large_internal_gap_seconds or has_flag(row, "first_word_anchor_suspect")):
        categories.append("pronunciation_or_tokenisation_check")
        actions.append("Check contractions, hyphens, rare words, and custom pronunciations.")
        severity += 20

    if "kara-creator" in timing_source or "rescue" in line_anchor_source:
        categories.append("draft_builder_rescue_applied")
        actions.append("This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.")
        severity += 10

    if max_gap >= args.very_large_internal_gap_seconds and ("kara-creator" in timing_source or has_flag(row, "late_next_line_anchor_rescue")):
        categories.append("local_realignment_candidate")
        actions.append("Best next step: local realignment of this phrase window, not another display timing patch.")
        severity += 25

    if max_gap >= args.large_internal_gap_seconds and row.get("next_display_type") == "lyric" and "audio-phrase-boundary" in line_anchor_source:
        categories.append("alignment_confidence_boundary_used")
        actions.append("Audio phrase-boundary rescue was used. Check that the display looks right, but treat word timings with caution.")
        severity += 10

    if not categories:
        categories.append("ok")
        actions.append("No obvious diagnostic issue detected.")

    # Avoid repeated advice in the CSV.
    deduped_actions: list[str] = []
    for action in actions:
        if action not in deduped_actions:
            deduped_actions.append(action)

    return min(severity, 100), categories, " ".join(deduped_actions)


def build_diagnostics(document: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = flatten_lines(document)
    output: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        severity, categories, recommended_action = classify_row(row, rows, index, args)
        output.append(
            {
                "severity": severity,
                "diagnostic_category": "|".join(categories),
                "recommended_action": recommended_action,
                "section": row.get("section", ""),
                "line_id": row.get("line_id", ""),
                "display_type": row.get("display_type", ""),
                "text": row.get("text", ""),
                "start": round_or_blank(row.get("start")),
                "end": round_or_blank(row.get("end")),
                "duration": round_or_blank(row.get("duration")),
                "word_start": round_or_blank(row.get("word_start")),
                "last_word_start": round_or_blank(row.get("last_word_start")),
                "word_span": round_or_blank(row.get("word_span")),
                "start_to_first_word": round_or_blank(row.get("start_to_first_word")),
                "final_word_hold": round_or_blank(row.get("final_word_hold")),
                "word_count": row.get("word_count", 0),
                "text_word_count": row.get("text_word_count", 0),
                "first_internal_word_gap": round_or_blank(row.get("first_internal_word_gap")),
                "max_internal_word_gap": round_or_blank(row.get("max_internal_word_gap")),
                "computed_later_gap_typical": round_or_blank(row.get("computed_later_gap_typical")),
                "max_gap_before_word": row.get("max_gap_before_word", ""),
                "max_gap_after_word": row.get("max_gap_after_word", ""),
                "gap_from_previous_end": round_or_blank(row.get("gap_from_previous_end")),
                "gap_to_next_start": round_or_blank(row.get("gap_to_next_start")),
                "previous_line_id": row.get("previous_line_id", ""),
                "previous_display_type": row.get("previous_display_type", ""),
                "next_line_id": row.get("next_line_id", ""),
                "next_display_type": row.get("next_display_type", ""),
                "line_anchor_source": row.get("line_anchor_source", ""),
                "line_end_source": row.get("line_end_source", ""),
                "line_end_confidence": row.get("line_end_confidence", ""),
                "timing_source": row.get("timing_source", ""),
                "review_flags": row.get("review_flags_joined", ""),
                "edited_manually": str(row.get("edited_manually", False)),
            }
        )

    return output


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    columns = [
        "severity",
        "diagnostic_category",
        "recommended_action",
        "section",
        "line_id",
        "display_type",
        "text",
        "start",
        "end",
        "duration",
        "word_start",
        "last_word_start",
        "word_span",
        "start_to_first_word",
        "final_word_hold",
        "word_count",
        "text_word_count",
        "first_internal_word_gap",
        "max_internal_word_gap",
        "computed_later_gap_typical",
        "max_gap_before_word",
        "max_gap_after_word",
        "gap_from_previous_end",
        "gap_to_next_start",
        "previous_line_id",
        "previous_display_type",
        "next_line_id",
        "next_display_type",
        "line_anchor_source",
        "line_end_source",
        "line_end_confidence",
        "timing_source",
        "review_flags",
        "edited_manually",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_summary(rows: list[dict[str, Any]], summary_path: Path, draft_path: Path, top_n: int) -> None:
    total = len(rows)
    high = [row for row in rows if int(row.get("severity", 0)) >= 70]
    medium = [row for row in rows if 35 <= int(row.get("severity", 0)) < 70]
    local = [row for row in rows if "local_realignment_candidate" in str(row.get("diagnostic_category", ""))]
    repeated = [row for row in rows if "repeated_word_or_held_word_collapse" in str(row.get("diagnostic_category", ""))]
    instrumental = [row for row in rows if "instrumental" in str(row.get("diagnostic_category", ""))]
    pronunciation = [row for row in rows if "pronunciation_or_tokenisation_check" in str(row.get("diagnostic_category", ""))]

    worst = sorted(rows, key=lambda row: int(row.get("severity", 0)), reverse=True)[:top_n]

    lines: list[str] = []
    lines.append(f"# Alignment diagnostics summary")
    lines.append("")
    lines.append(f"Draft: `{draft_path}`")
    lines.append(f"Tool version: `{VERSION}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Total lines: {total}")
    lines.append(f"- High severity lines: {len(high)}")
    lines.append(f"- Medium severity lines: {len(medium)}")
    lines.append(f"- Local realignment candidates: {len(local)}")
    lines.append(f"- Repeated or held word collapse candidates: {len(repeated)}")
    lines.append(f"- Instrumental placeholder checks: {len(instrumental)}")
    lines.append(f"- Pronunciation or tokenisation checks: {len(pronunciation)}")
    lines.append("")
    lines.append("## Worst lines")
    lines.append("")

    if not worst:
        lines.append("No lines found.")
    else:
        for row in worst:
            lines.append(
                f"- {row['severity']} | {row['line_id']} | {row['diagnostic_category']} | {row['text']}"
            )
            lines.append(f"  - Action: {row['recommended_action']}")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(rows: list[dict[str, Any]], output_path: Path, summary_path: Path | None, top_n: int) -> None:
    total = len(rows)
    high = [row for row in rows if int(row.get("severity", 0)) >= 70]
    medium = [row for row in rows if 35 <= int(row.get("severity", 0)) < 70]
    local = [row for row in rows if "local_realignment_candidate" in str(row.get("diagnostic_category", ""))]

    print("")
    print("Alignment diagnostics complete.")
    print("")
    print(f"Total lines:                   {total}")
    print(f"High severity lines:           {len(high)}")
    print(f"Medium severity lines:         {len(medium)}")
    print(f"Local realignment candidates:  {len(local)}")
    print(f"CSV written to:                {output_path}")
    if summary_path:
        print(f"Summary written to:            {summary_path}")
    print("")

    worst = sorted(rows, key=lambda row: int(row.get("severity", 0)), reverse=True)[:top_n]
    if worst:
        print("Worst lines:")
        for row in worst:
            print(
                f"- {row['severity']:>3} | {row['line_id']} | "
                f"{row['diagnostic_category']} | {row['text']}"
            )
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose likely alignment quality problems in a karaoke-draft-v3 JSON file."
    )

    parser.add_argument("--draft", required=True, help="Path to a karaoke-draft-v3 JSON file.")
    parser.add_argument("--out", required=True, help="Path where the diagnostics CSV should be written.")
    parser.add_argument("--summary", help="Optional path for a Markdown summary report.")
    parser.add_argument("--top", type=int, default=12, help="How many worst lines to print/show in the summary. Default: 12.")

    parser.add_argument("--large-internal-gap-seconds", type=float, default=DEFAULT_LARGE_INTERNAL_GAP_SECONDS)
    parser.add_argument("--very-large-internal-gap-seconds", type=float, default=DEFAULT_VERY_LARGE_INTERNAL_GAP_SECONDS)
    parser.add_argument("--suspicious-first-gap-seconds", type=float, default=DEFAULT_SUSPICIOUS_FIRST_GAP_SECONDS)
    parser.add_argument("--min-display-duration-seconds", type=float, default=DEFAULT_MIN_DISPLAY_DURATION_SECONDS)
    parser.add_argument("--very-short-duration-seconds", type=float, default=DEFAULT_VERY_SHORT_DURATION_SECONDS)
    parser.add_argument("--short-instrumental-seconds", type=float, default=DEFAULT_SHORT_INSTRUMENTAL_SECONDS)
    parser.add_argument("--long-tail-seconds", type=float, default=DEFAULT_LONG_TAIL_SECONDS)
    parser.add_argument("--short-final-hold-seconds", type=float, default=DEFAULT_SHORT_FINAL_HOLD_SECONDS)
    parser.add_argument("--ratio-threshold", type=float, default=DEFAULT_RATIO_THRESHOLD)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    output_path = Path(args.out).resolve()
    summary_path = Path(args.summary).resolve() if args.summary else None

    document = load_json(draft_path)
    rows = build_diagnostics(document, args)

    write_csv(rows, output_path)
    if summary_path:
        write_summary(rows, summary_path, draft_path, args.top)

    print_summary(rows, output_path, summary_path, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
