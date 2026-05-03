from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def flatten_lines(document: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for section in document.get("sections", []):
        section_label = str(section.get("label", "Section")).strip() or "Section"

        for line in section.get("lines", []):
            start = as_float(line.get("start"))
            end = as_float(line.get("end"))

            words = line.get("words", [])
            internal_gaps: list[float] = []

            if isinstance(words, list) and len(words) >= 2:
                starts = [as_float(word.get("start")) for word in words]
                internal_gaps = [
                    starts[index + 1] - starts[index]
                    for index in range(len(starts) - 1)
                ]

            rows.append(
                {
                    "line_id": str(line.get("id", "")),
                    "section": section_label,
                    "display_type": str(line.get("display_type", "lyric")),
                    "text": str(line.get("text", "")),
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "word_start": line.get("word_start"),
                    "last_word_start": line.get("last_word_start"),
                    "edited_manually": bool(line.get("edited_manually", False)),
                    "review_flags": line.get("review_flags", []),
                    "max_internal_word_gap": max(internal_gaps) if internal_gaps else 0.0,
                }
            )

    return rows


def compare_drafts(draft: dict[str, Any], edited: dict[str, Any]) -> list[dict[str, Any]]:
    draft_lines = {line["line_id"]: line for line in flatten_lines(draft)}
    edited_lines = {line["line_id"]: line for line in flatten_lines(edited)}

    output: list[dict[str, Any]] = []

    for line_id, draft_line in draft_lines.items():
        edited_line = edited_lines.get(line_id)

        if not edited_line:
            output.append(
                {
                    "line_id": line_id,
                    "section": draft_line["section"],
                    "display_type": draft_line["display_type"],
                    "text": draft_line["text"],
                    "status": "missing_from_edited",
                }
            )
            continue

        start_delta = edited_line["start"] - draft_line["start"]
        end_delta = edited_line["end"] - draft_line["end"]
        duration_delta = edited_line["duration"] - draft_line["duration"]

        output.append(
            {
                "line_id": line_id,
                "section": draft_line["section"],
                "display_type": draft_line["display_type"],
                "text": draft_line["text"],
                "status": "compared",
                "draft_start": round(draft_line["start"], 3),
                "edited_start": round(edited_line["start"], 3),
                "start_delta": round(start_delta, 3),
                "draft_end": round(draft_line["end"], 3),
                "edited_end": round(edited_line["end"], 3),
                "end_delta": round(end_delta, 3),
                "draft_duration": round(draft_line["duration"], 3),
                "edited_duration": round(edited_line["duration"], 3),
                "duration_delta": round(duration_delta, 3),
                "edited_manually": edited_line["edited_manually"],
                "draft_review_flags": "|".join(str(flag) for flag in draft_line["review_flags"]),
                "draft_max_internal_word_gap": round(draft_line["max_internal_word_gap"], 3),
            }
        )

    return output


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    columns = [
        "line_id",
        "section",
        "display_type",
        "text",
        "status",
        "draft_start",
        "edited_start",
        "start_delta",
        "draft_end",
        "edited_end",
        "end_delta",
        "draft_duration",
        "edited_duration",
        "duration_delta",
        "edited_manually",
        "draft_review_flags",
        "draft_max_internal_word_gap",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def print_summary(rows: list[dict[str, Any]]) -> None:
    compared = [row for row in rows if row.get("status") == "compared"]

    changed = [
        row
        for row in compared
        if abs(as_float(row.get("start_delta"))) > 0.001
        or abs(as_float(row.get("end_delta"))) > 0.001
    ]

    lyric_changed = [
        row for row in changed
        if row.get("display_type") == "lyric"
    ]

    instrumental_changed = [
        row for row in changed
        if row.get("display_type") == "instrumental"
    ]

    large_internal_gap = [
        row for row in compared
        if as_float(row.get("draft_max_internal_word_gap")) >= 2.0
    ]

    print("")
    print("Karaoke draft comparison complete.")
    print("")
    print(f"Compared lines:              {len(compared)}")
    print(f"Changed lines:               {len(changed)}")
    print(f"Changed lyric lines:         {len(lyric_changed)}")
    print(f"Changed instrumental lines:  {len(instrumental_changed)}")
    print(f"Large internal word gaps:    {len(large_internal_gap)}")
    print("")

    if large_internal_gap:
        print("Large internal word gaps:")
        for row in large_internal_gap:
            print(
                f"- {row['line_id']} | {row['draft_max_internal_word_gap']}s | {row['text']}"
            )
        print("")

    if changed:
        print("Largest changes:")
        biggest = sorted(
            changed,
            key=lambda row: max(
                abs(as_float(row.get("start_delta"))),
                abs(as_float(row.get("end_delta"))),
                abs(as_float(row.get("duration_delta"))),
            ),
            reverse=True,
        )[:10]

        for row in biggest:
            print(
                f"- {row['line_id']} | start {row['start_delta']}s | "
                f"end {row['end_delta']}s | {row['text']}"
            )
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a generated karaoke draft JSON against a manually edited JSON."
    )

    parser.add_argument(
        "--draft",
        required=True,
        help="Path to the generated draft JSON.",
    )

    parser.add_argument(
        "--edited",
        required=True,
        help="Path to the manually edited JSON.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the diagnostics CSV should be written.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    edited_path = Path(args.edited).resolve()
    output_path = Path(args.out).resolve()

    draft = load_json(draft_path)
    edited = load_json(edited_path)

    rows = compare_drafts(draft, edited)
    write_csv(rows, output_path)
    print_summary(rows)

    print(f"Diagnostics CSV: {output_path}")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
