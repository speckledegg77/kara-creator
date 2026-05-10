from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
INSTRUMENTAL_DISPLAY_TEXT = ". . ."
DEFAULT_MAX_WORD_DISPLAY_SECONDS = 0.9
DEFAULT_FINAL_WORD_DISPLAY_SECONDS = 0.9


@dataclass
class FlatLine:
    index: int
    section_index: int
    line_index: int
    line: dict[str, Any]


@dataclass
class RecoveryGroup:
    key: str
    target_ids: list[str]
    context_ids: list[str]
    alignment_ids: list[str]
    window_start: float
    window_end: float


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


def round_time(value: float) -> float:
    return round(float(value), 3)


def slugify(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "local_recovery"


def normalise_word(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("’", "'")
    text = text.replace("-", "")
    return "".join(character for character in text if character.isalnum() or character == "'")


def words_from_text(text: str) -> list[str]:
    cleaned = str(text or "").replace("’", "'").replace("-", "")
    raw_words = re.findall(r"[A-Za-z0-9']+", cleaned)
    return [normalise_word(word) for word in raw_words if normalise_word(word)]


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} does not exist: {path}")
    if not path.is_file():
        raise SystemExit(f"{label} is not a file: {path}")


def require_dir(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise SystemExit(f"{label} is not a folder: {path}")


def run_command(command: list[str], cwd: Path | None = None) -> None:
    print("")
    print("Running:")
    print(" ".join(f'\"{part}\"' if " " in str(part) else str(part) for part in command))
    print("")

    completed = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True)
    if completed.returncode != 0:
        raise SystemExit(f"Command failed with exit code {completed.returncode}.")


def flatten_lines(document: dict[str, Any]) -> list[FlatLine]:
    flat: list[FlatLine] = []
    for section_index, section in enumerate(document.get("sections", [])):
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            continue
        for line_index, line in enumerate(lines):
            if isinstance(line, dict):
                flat.append(
                    FlatLine(
                        index=len(flat),
                        section_index=section_index,
                        line_index=line_index,
                        line=line,
                    )
                )
    return flat


def is_lyric(line: dict[str, Any]) -> bool:
    return str(line.get("display_type", "lyric")) == "lyric"


def is_instrumental(line: dict[str, Any]) -> bool:
    return str(line.get("display_type", "lyric")) == "instrumental"


def line_id(line: dict[str, Any]) -> str:
    return str(line.get("id", ""))


def line_words(line: dict[str, Any]) -> list[str]:
    words = line.get("words", [])
    if isinstance(words, list) and words:
        output: list[str] = []
        for word in words:
            if isinstance(word, dict):
                cleaned = normalise_word(word.get("text"))
            else:
                cleaned = normalise_word(word)
            if cleaned:
                output.append(cleaned)
        if output:
            return output
    return words_from_text(str(line.get("text", "")))


def read_diagnostics(path: Path) -> dict[str, dict[str, Any]]:
    require_file(path, "Diagnostics CSV")
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            lid = str(row.get("line_id", "")).strip()
            if lid:
                rows[lid] = row
    return rows


def categories_for(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    return str(row.get("diagnostic_category", ""))


def parse_line_number(line_id_value: str) -> int:
    match = re.search(r"(\d+)$", line_id_value)
    if not match:
        return -1
    return int(match.group(1))


def is_repeated_or_knock_on(row: dict[str, Any] | None) -> bool:
    categories = categories_for(row)
    return (
        "repeated_word_or_held_word_collapse" in categories
        or "draft_builder_rescue_applied" in categories
        or "very_short_display_duration" in categories
    )


def selected_target_ids(
    diagnostics: dict[str, dict[str, Any]],
    explicit_line_ids: list[str],
    min_severity: int,
) -> set[str]:
    if explicit_line_ids:
        return {str(value).strip() for value in explicit_line_ids if str(value).strip()}

    selected: set[str] = set()
    for lid, row in diagnostics.items():
        severity = int(float(str(row.get("severity") or 0)))
        categories = categories_for(row)
        if "local_realignment_candidate" in categories or severity >= min_severity and "very_large_internal_word_gap" in categories:
            selected.add(lid)
    return selected


def build_groups(
    word_review: dict[str, Any],
    draft: dict[str, Any],
    diagnostics: dict[str, dict[str, Any]],
    target_ids: set[str],
    *,
    context_before: int,
    context_after: int,
    window_preroll_seconds: float,
    window_postroll_seconds: float,
) -> list[RecoveryGroup]:
    draft_flat = flatten_lines(draft)
    review_flat = flatten_lines(word_review)
    draft_by_id = {line_id(item.line): item for item in draft_flat}
    review_by_id = {line_id(item.line): item for item in review_flat}

    valid_targets = sorted(
        [lid for lid in target_ids if lid in draft_by_id and lid in review_by_id],
        key=parse_line_number,
    )

    if not valid_targets:
        return []

    target_indexes = sorted(draft_by_id[lid].index for lid in valid_targets)

    clusters: list[list[int]] = []
    current: list[int] = []
    for index in target_indexes:
        if not current:
            current = [index]
        elif index <= current[-1] + 1:
            current.append(index)
        else:
            clusters.append(current)
            current = [index]
    if current:
        clusters.append(current)

    groups: list[RecoveryGroup] = []

    for cluster in clusters:
        target_index_set = set(cluster)

        # Include immediate repeated one-word/held-word knock-on lines after a bad cluster.
        right = max(cluster)
        while right + 1 < len(draft_flat):
            next_lid = line_id(draft_flat[right + 1].line)
            next_row = diagnostics.get(next_lid)
            if not is_lyric(draft_flat[right + 1].line):
                break
            if is_repeated_or_knock_on(next_row):
                right += 1
                target_index_set.add(right)
                continue
            break

        left = min(cluster)

        context_left = max(0, left - context_before)
        context_right = min(len(draft_flat) - 1, right + context_after)

        alignment_indexes: list[int] = []
        context_ids: list[str] = []
        target_group_ids: list[str] = []

        for index in range(context_left, context_right + 1):
            draft_line = draft_flat[index].line
            lid = line_id(draft_line)
            if lid not in review_by_id:
                continue
            if is_instrumental(draft_line):
                context_ids.append(lid)
                continue
            if not is_lyric(draft_line):
                continue
            alignment_indexes.append(index)
            if index in target_index_set:
                target_group_ids.append(lid)
            else:
                context_ids.append(lid)

        if not target_group_ids or not alignment_indexes:
            continue

        starts: list[float] = []
        ends: list[float] = []
        for index in range(context_left, context_right + 1):
            line = draft_flat[index].line
            start = as_float(line.get("start"))
            end = as_float(line.get("end"))
            if start is not None:
                starts.append(start)
            if end is not None:
                ends.append(end)

        if not starts or not ends:
            continue

        window_start = max(0.0, min(starts) - window_preroll_seconds)
        audio_duration = as_float(draft.get("source", {}).get("audio_duration_seconds"))
        raw_window_end = max(ends) + window_postroll_seconds
        if audio_duration is not None and audio_duration > 0:
            window_end = min(audio_duration, raw_window_end)
        else:
            window_end = raw_window_end

        first_id = target_group_ids[0]
        last_id = target_group_ids[-1]
        key = f"{first_id}_to_{last_id}"

        groups.append(
            RecoveryGroup(
                key=key,
                target_ids=target_group_ids,
                context_ids=context_ids,
                alignment_ids=[line_id(draft_flat[index].line) for index in alignment_indexes],
                window_start=round_time(window_start),
                window_end=round_time(window_end),
            )
        )

    return groups


def load_pipeline_helpers(project_root: Path):
    tools_dir = project_root / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    try:
        import run_lyrics_aligner_pipeline as pipeline  # type: ignore
    except Exception as error:
        raise SystemExit(
            "Could not import tools/run_lyrics_aligner_pipeline.py. "
            "Run this script from inside C:\\Users\\mark\\kara-creator.\n"
            f"Import error: {error}"
        )

    return pipeline


def create_audio_window(source_audio: Path, output_audio: Path, start: float, end: float) -> None:
    duration = max(0.1, end - start)
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_audio),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(output_audio),
    ]
    run_command(command)


def write_local_lyrics(path: Path, lines: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text_lines = [str(line.get("text", "")).strip() for line in lines if is_lyric(line) and str(line.get("text", "")).strip()]
    path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")


def parse_aligner_output(path: Path, offset_seconds: float) -> list[dict[str, Any]]:
    require_file(path, "Local lyrics-aligner output")
    words: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        word = normalise_word(parts[0])
        try:
            start = float(parts[1]) + offset_seconds
        except ValueError:
            continue
        if word:
            words.append({"text": word, "start": round_time(start)})
    return words


def add_word_end_times(words: list[dict[str, Any]], max_word_display_seconds: float, final_word_display_seconds: float) -> None:
    for index, word in enumerate(words):
        start = as_float(word.get("start"), 0.0) or 0.0
        if index < len(words) - 1:
            next_start = as_float(words[index + 1].get("start"), start + 0.05) or start + 0.05
            end = min(next_start, start + max_word_display_seconds)
            if end <= start:
                end = start + 0.05
        else:
            end = start + final_word_display_seconds
        word["end"] = round_time(end)
        word["duration"] = round_time(end - start)


def run_local_alignment(
    *,
    project_root: Path,
    aligner_dir: Path,
    group: RecoveryGroup,
    draft: dict[str, Any],
    word_review: dict[str, Any],
    run_root: Path,
    vad_threshold: float,
    keep_previous: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    pipeline = load_pipeline_helpers(project_root)

    source_audio_raw = draft.get("source", {}).get("audio_file") or word_review.get("source", {}).get("audio_file")
    if not source_audio_raw:
        raise SystemExit("Could not find source audio_file in the draft or word-review JSON.")
    source_audio = Path(str(source_audio_raw))
    require_file(source_audio, "Source audio")

    draft_by_id = {line_id(item.line): item.line for item in flatten_lines(draft)}
    alignment_lines = [draft_by_id[lid] for lid in group.alignment_ids if lid in draft_by_id and is_lyric(draft_by_id[lid])]

    safe_group_name = slugify(group.key)
    dataset_name = f"kara_local_{safe_group_name}"
    group_dir = run_root / safe_group_name
    audio_dir = group_dir / "audio"
    lyrics_dir = group_dir / "lyrics"
    local_audio = audio_dir / f"{safe_group_name}.wav"
    local_lyrics = lyrics_dir / f"{safe_group_name}.txt"

    if group_dir.exists() and not keep_previous:
        shutil.rmtree(group_dir)

    create_audio_window(source_audio, local_audio, group.window_start, group.window_end)
    write_local_lyrics(local_lyrics, alignment_lines)

    custom_pronunciations = pipeline.load_custom_pronunciations(project_root)

    removed_files: list[str] = []
    if not keep_previous:
        removed_files = pipeline.clean_previous_aligner_files(aligner_dir, dataset_name)

    pipeline.run_command(
        [
            sys.executable,
            "make_word_list.py",
            str(lyrics_dir),
            "--dataset-name",
            dataset_name,
        ],
        cwd=aligner_dir,
    )

    word_list_path = aligner_dir / "files" / f"{dataset_name}_word_list.txt"
    word2phonemes_path = aligner_dir / "files" / f"{dataset_name}_word2phonemes.txt"
    missing_path = aligner_dir / "files" / f"{dataset_name}_missing_words.txt"

    pipeline.create_word2phonemes_file(
        word_list_path=word_list_path,
        output_path=word2phonemes_path,
        missing_path=missing_path,
        custom_pronunciations=custom_pronunciations,
    )

    pipeline.run_command(
        [
            sys.executable,
            "make_word2phoneme_dict.py",
            "--dataset-name",
            dataset_name,
        ],
        cwd=aligner_dir,
    )

    pipeline.run_command(
        [
            sys.executable,
            "align.py",
            str(audio_dir),
            str(lyrics_dir),
            "--lyrics-format",
            "w",
            "--onsets",
            "w",
            "--dataset-name",
            dataset_name,
            "--vad-threshold",
            f"{vad_threshold:g}",
        ],
        cwd=aligner_dir,
    )

    aligner_output = aligner_dir / "outputs" / dataset_name / "word_onsets" / f"{safe_group_name}.txt"
    local_words = parse_aligner_output(aligner_output, group.window_start)
    add_word_end_times(local_words, DEFAULT_MAX_WORD_DISPLAY_SECONDS, DEFAULT_FINAL_WORD_DISPLAY_SECONDS)

    return local_words, removed_files


def assign_words_to_lines(local_words: list[dict[str, Any]], alignment_lines: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    assignments: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    position = 0

    for line in alignment_lines:
        expected = line_words(line)
        count = len(expected)
        selected = local_words[position:position + count]
        position += count

        actual = [normalise_word(word.get("text")) for word in selected]
        if expected != actual:
            warnings.append(
                f"{line_id(line)}: local alignment words did not match expected words. "
                f"Expected {expected}; got {actual}."
            )
        assignments[line_id(line)] = selected

    if position != len(local_words):
        warnings.append(
            f"Local aligner returned {len(local_words)} words but {position} words were expected from the selected lyric lines."
        )

    return assignments, warnings


def replace_line_words(
    word_review: dict[str, Any],
    line_id_value: str,
    replacement_words: list[dict[str, Any]],
    group: RecoveryGroup,
) -> None:
    for item in flatten_lines(word_review):
        line = item.line
        if line_id(line) != line_id_value:
            continue
        if not is_lyric(line):
            return

        existing_words = line.get("words", [])
        if not isinstance(existing_words, list) or len(existing_words) != len(replacement_words):
            return

        for index, replacement in enumerate(replacement_words):
            existing = existing_words[index]
            if not isinstance(existing, dict):
                continue
            existing["original_start_before_local_recovery"] = existing.get("start")
            existing["original_end_before_local_recovery"] = existing.get("end")
            existing["start"] = replacement["start"]
            existing["end"] = replacement["end"]
            existing["duration"] = replacement["duration"]
            existing["source"] = "lyrics-aligner-local-recovery"
            existing["local_recovery"] = {
                "group": group.key,
                "window_start": group.window_start,
                "window_end": group.window_end,
                "tool_version": VERSION,
            }

        starts = [as_float(word.get("start")) for word in existing_words if isinstance(word, dict) and as_float(word.get("start")) is not None]
        ends = [as_float(word.get("end")) for word in existing_words if isinstance(word, dict) and as_float(word.get("end")) is not None]
        if starts:
            line["start"] = round_time(min(starts))
        if ends:
            line["end"] = round_time(max(ends))
        flags = line.get("review_flags")
        if not isinstance(flags, list):
            flags = []
        if "local_alignment_recovery_applied_needs_review" not in flags:
            flags.append("local_alignment_recovery_applied_needs_review")
        line["review_flags"] = flags
        line["local_recovery"] = {
            "group": group.key,
            "window_start": group.window_start,
            "window_end": group.window_end,
            "target_ids": group.target_ids,
            "context_ids": group.context_ids,
            "tool_version": VERSION,
        }
        return


def update_section_ranges(word_review: dict[str, Any]) -> None:
    for section in word_review.get("sections", []):
        if not isinstance(section, dict):
            continue
        starts: list[float] = []
        ends: list[float] = []
        for line in section.get("lines", []):
            if not isinstance(line, dict):
                continue
            start = as_float(line.get("start"))
            end = as_float(line.get("end"))
            if start is not None:
                starts.append(start)
            if end is not None:
                ends.append(end)
        if starts:
            section["start"] = round_time(min(starts))
        if ends:
            section["end"] = round_time(max(ends))


def run_draft_builder(project_root: Path, word_review_path: Path, draft_path: Path) -> None:
    run_command(
        [
            sys.executable,
            str(project_root / "tools" / "build_karaoke_draft_from_word_starts.py"),
            "--word-review",
            str(word_review_path),
            "--out",
            str(draft_path),
        ],
        cwd=project_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local lyrics-aligner recovery for low-confidence regions detected by diagnose_alignment_quality.py."
    )
    parser.add_argument("--draft", required=True, help="Path to the current karaoke-draft-v3 JSON.")
    parser.add_argument("--diagnostics", required=True, help="Path to the diagnostics CSV for the draft.")
    parser.add_argument("--word-review", help="Path to the source word-review JSON. Defaults to draft.source.word_review_json.")
    parser.add_argument("--out-word-review", required=True, help="Path for the recovered word-review JSON.")
    parser.add_argument("--out-draft", required=True, help="Path for the rebuilt recovered draft JSON.")
    parser.add_argument("--aligner-dir", default=r"C:\Users\mark\kara-creator\alignment_lab\singing-aligners\lyrics-aligner", help="Path to the cloned lyrics-aligner folder.")
    parser.add_argument("--line-id", action="append", default=[], help="Specific line id to recover. Can be used more than once. If omitted, local_realignment_candidate lines are used.")
    parser.add_argument("--min-severity", type=int, default=70, help="Minimum severity for automatic recovery candidates when --line-id is not used. Default: 70.")
    parser.add_argument("--context-before", type=int, default=1, help="Number of nearby lyric lines before the candidate to include as alignment context. Default: 1.")
    parser.add_argument("--context-after", type=int, default=1, help="Number of nearby lyric lines after the candidate to include as alignment context. Default: 1.")
    parser.add_argument("--window-preroll-seconds", type=float, default=1.25, help="Audio included before the first context/candidate line. Default: 1.25.")
    parser.add_argument("--window-postroll-seconds", type=float, default=1.75, help="Audio included after the final context/candidate line. Default: 1.75.")
    parser.add_argument("--vad-threshold", type=float, default=0.0, help="lyrics-aligner VAD threshold for local recovery windows. Default: 0.0.")
    parser.add_argument("--keep-previous", action="store_true", help="Keep previous temporary local recovery files and lyrics-aligner outputs.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    draft_path = Path(args.draft).resolve()
    diagnostics_path = Path(args.diagnostics).resolve()
    aligner_dir = Path(args.aligner_dir).resolve()
    out_word_review_path = Path(args.out_word_review).resolve()
    out_draft_path = Path(args.out_draft).resolve()

    require_file(draft_path, "Draft JSON")
    require_file(diagnostics_path, "Diagnostics CSV")
    require_dir(aligner_dir, "lyrics-aligner folder")

    draft = load_json(draft_path)
    word_review_path = Path(args.word_review).resolve() if args.word_review else Path(str(draft.get("source", {}).get("word_review_json", ""))).resolve()
    require_file(word_review_path, "Word-review JSON")
    word_review = load_json(word_review_path)
    diagnostics = read_diagnostics(diagnostics_path)

    targets = selected_target_ids(diagnostics, args.line_id, args.min_severity)
    groups = build_groups(
        word_review=word_review,
        draft=draft,
        diagnostics=diagnostics,
        target_ids=targets,
        context_before=max(0, args.context_before),
        context_after=max(0, args.context_after),
        window_preroll_seconds=max(0.0, args.window_preroll_seconds),
        window_postroll_seconds=max(0.0, args.window_postroll_seconds),
    )

    print("")
    print("Local alignment recovery")
    print(f"Tool version: {VERSION}")
    print(f"Draft:        {draft_path}")
    print(f"Diagnostics:  {diagnostics_path}")
    print(f"Word review:  {word_review_path}")
    print(f"Candidates:   {', '.join(sorted(targets, key=parse_line_number)) if targets else 'none'}")
    print(f"Groups:       {len(groups)}")

    if not groups:
        print("")
        print("No recovery groups found. Nothing changed.")
        write_json(out_word_review_path, word_review)
        run_draft_builder(project_root, out_word_review_path, out_draft_path)
        return 0

    run_root = project_root / "alignment_lab" / "local_recovery"
    draft_by_id = {line_id(item.line): item.line for item in flatten_lines(draft)}

    recovery_report: list[dict[str, Any]] = []
    total_replaced_lines = 0

    for group in groups:
        print("")
        print(f"Recovering group: {group.key}")
        print(f"Target lines:     {', '.join(group.target_ids)}")
        print(f"Alignment lines:  {', '.join(group.alignment_ids)}")
        print(f"Audio window:     {group.window_start:.3f}s to {group.window_end:.3f}s")

        local_words, removed_files = run_local_alignment(
            project_root=project_root,
            aligner_dir=aligner_dir,
            group=group,
            draft=draft,
            word_review=word_review,
            run_root=run_root,
            vad_threshold=args.vad_threshold,
            keep_previous=args.keep_previous,
        )

        alignment_lines = [draft_by_id[lid] for lid in group.alignment_ids if lid in draft_by_id and is_lyric(draft_by_id[lid])]
        assignments, warnings = assign_words_to_lines(local_words, alignment_lines)

        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")

        for target_id in group.target_ids:
            if target_id not in assignments:
                continue
            replace_line_words(word_review, target_id, assignments[target_id], group)
            total_replaced_lines += 1

        recovery_report.append(
            {
                "group": group.key,
                "target_ids": group.target_ids,
                "context_ids": group.context_ids,
                "alignment_ids": group.alignment_ids,
                "window_start": group.window_start,
                "window_end": group.window_end,
                "local_word_count": len(local_words),
                "warnings": warnings,
                "removed_previous_aligner_files": removed_files,
            }
        )

    update_section_ranges(word_review)
    word_review.setdefault("alignment", {})["local_recovery"] = {
        "tool_version": VERSION,
        "source_draft": str(draft_path),
        "source_diagnostics": str(diagnostics_path),
        "source_word_review": str(word_review_path),
        "group_count": len(recovery_report),
        "replaced_line_count": total_replaced_lines,
        "vad_threshold": args.vad_threshold,
        "groups": recovery_report,
    }

    write_json(out_word_review_path, word_review)
    run_draft_builder(project_root, out_word_review_path, out_draft_path)

    print("")
    print("Local alignment recovery complete.")
    print(f"Recovered word review: {out_word_review_path}")
    print(f"Recovered draft:       {out_draft_path}")
    print(f"Recovered lines:       {total_replaced_lines}")
    print("")
    print("Open the recovered draft in the editor and check the recovered windows first.")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
