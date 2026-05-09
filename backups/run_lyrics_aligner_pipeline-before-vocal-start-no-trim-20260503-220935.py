from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pronouncing


CLITIC_SUFFIXES = [
    ("n't", "N T"),
    ("'ve", "V"),
    ("'m", "M"),
    ("'re", "R"),
    ("'d", "D"),
    ("'ll", "L"),
    ("'s", "Z"),
]

UNVOICED_FOR_S = {"P", "T", "K", "F", "TH"}
INSTRUMENTAL_DISPLAY_TEXT = ". . ."
AUTO_SECTION_SIZE = 8


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def require_dir(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise FileNotFoundError(f"{label} is not a folder: {path}")


def run_command(command: list[str], cwd: Path | None = None) -> None:
    print("")
    print("Running:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    print("")

    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}.")


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "song"


def section_id_from_label(label: str, index: int) -> str:
    safe = slugify(label).replace("_", "-")
    return f"{safe}-{index:03d}"


def clean_lyric_line(line: str) -> str:
    line = line.strip()
    line = line.replace("’", "'")
    line = line.replace("…", "…")
    line = re.sub(r"\s+", " ", line)
    return line


def is_section_heading(line: str) -> bool:
    return bool(re.match(r"^\[(.+?)\]$", line.strip()))


def section_label_from_heading(line: str) -> str:
    match = re.match(r"^\[(.+?)\]$", line.strip())

    if not match:
        return "Section"

    return match.group(1).strip() or "Section"


def is_comment_line(line: str) -> bool:
    return line.strip().startswith("#")


def is_instrumental_placeholder(line: str) -> bool:
    value = line.strip()

    if value == "…":
        return True

    if value == "...":
        return True

    compact = re.sub(r"\s+", "", value)
    return compact == "..."


def normalise_word(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = value.replace("-", "")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def words_from_line(line: str) -> list[str]:
    cleaned = line.replace("’", "'")
    cleaned = cleaned.replace("-", "")
    raw_words = re.findall(r"[A-Za-z0-9']+", cleaned)
    return [normalise_word(word) for word in raw_words if normalise_word(word)]


def make_line_entry(raw_line: str, section_label: str, line_counter: int) -> dict[str, Any] | None:
    line = clean_lyric_line(raw_line)

    if not line:
        return None

    if is_comment_line(line):
        return None

    if is_section_heading(line):
        return None

    if is_instrumental_placeholder(line):
        return {
            "id": f"line-{line_counter:04d}",
            "section": section_label,
            "text": INSTRUMENTAL_DISPLAY_TEXT,
            "display_type": "instrumental",
            "words": [],
        }

    words = words_from_line(line)

    if not words:
        return None

    return {
        "id": f"line-{line_counter:04d}",
        "section": section_label,
        "text": line,
        "display_type": "lyric",
        "words": words,
    }


def parse_lyrics_with_explicit_sections(raw_lines: list[str]) -> tuple[list[dict[str, Any]], str]:
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_label = "Song"
    line_counter = 0

    def ensure_section(label: str) -> dict[str, Any]:
        nonlocal current_section

        if current_section is None or current_section["label"] != label:
            current_section = {
                "label": label,
                "source": "explicit_heading" if label != "Song" else "implicit_default",
                "lines": [],
            }
            sections.append(current_section)

        return current_section

    ensure_section(current_label)

    for raw_line in raw_lines:
        line = clean_lyric_line(raw_line)

        if not line:
            continue

        if is_comment_line(line):
            continue

        if is_section_heading(line):
            current_label = section_label_from_heading(line)
            ensure_section(current_label)
            continue

        line_counter += 1
        entry = make_line_entry(
            raw_line=raw_line,
            section_label=current_label,
            line_counter=line_counter,
        )

        if entry is None:
            continue

        ensure_section(current_label)["lines"].append(entry)

    sections = [section for section in sections if section["lines"]]
    return sections, "explicit_headings"


def parse_lyrics_with_blank_groups(raw_lines: list[str]) -> tuple[list[dict[str, Any]], str]:
    groups: list[list[str]] = []
    current_group: list[str] = []
    saw_blank_between_content = False
    seen_content = False

    for raw_line in raw_lines:
        line = clean_lyric_line(raw_line)

        if is_comment_line(line):
            continue

        if not line:
            if current_group:
                groups.append(current_group)
                current_group = []
                saw_blank_between_content = True
            continue

        seen_content = True
        current_group.append(raw_line)

    if current_group:
        groups.append(current_group)

    if not groups:
        return [], "blank_groups"

    if len(groups) > 1 and saw_blank_between_content and seen_content:
        sections: list[dict[str, Any]] = []
        line_counter = 0

        for group_index, group in enumerate(groups, start=1):
            section_label = f"Section {group_index}"
            section = {
                "label": section_label,
                "source": "blank_line_group",
                "lines": [],
            }

            for raw_line in group:
                line_counter += 1
                entry = make_line_entry(
                    raw_line=raw_line,
                    section_label=section_label,
                    line_counter=line_counter,
                )

                if entry is not None:
                    section["lines"].append(entry)

            if section["lines"]:
                sections.append(section)

        return sections, "blank_line_groups"

    return parse_lyrics_with_auto_sections(groups[0])


def parse_lyrics_with_auto_sections(raw_lines: list[str]) -> tuple[list[dict[str, Any]], str]:
    display_entries: list[dict[str, Any]] = []
    line_counter = 0

    for raw_line in raw_lines:
        line = clean_lyric_line(raw_line)

        if not line or is_comment_line(line):
            continue

        line_counter += 1
        entry = make_line_entry(
            raw_line=raw_line,
            section_label="Section 1",
            line_counter=line_counter,
        )

        if entry is not None:
            display_entries.append(entry)

    sections: list[dict[str, Any]] = []

    for section_index, start in enumerate(range(0, len(display_entries), AUTO_SECTION_SIZE), start=1):
        label = f"Section {section_index}"
        chunk = display_entries[start:start + AUTO_SECTION_SIZE]

        for entry in chunk:
            entry["section"] = label

        sections.append(
            {
                "label": label,
                "source": "automatic_8_line_group",
                "lines": chunk,
            }
        )

    sections = [section for section in sections if section["lines"]]
    return sections, "automatic_8_line_sections"


def parse_sectioned_lyrics(lyrics_path: Path) -> list[dict[str, Any]]:
    require_file(lyrics_path, "Lyrics file")

    raw_lines = lyrics_path.read_text(encoding="utf-8-sig").splitlines()
    cleaned_lines = [clean_lyric_line(line) for line in raw_lines]
    has_explicit_headings = any(
        is_section_heading(line)
        for line in cleaned_lines
        if line and not is_comment_line(line)
    )

    if has_explicit_headings:
        sections, parser_mode = parse_lyrics_with_explicit_sections(raw_lines)
    else:
        sections, parser_mode = parse_lyrics_with_blank_groups(raw_lines)

    display_line_count = sum(len(section["lines"]) for section in sections)
    lyric_line_count = sum(
        1
        for section in sections
        for line in section["lines"]
        if line.get("display_type") == "lyric"
    )

    if display_line_count == 0:
        raise ValueError("No lyric or instrumental display lines were found. Check your lyrics TXT file.")

    if lyric_line_count == 0:
        raise ValueError(
            "No lyric lines with words were found. The aligner needs at least one real lyric line."
        )

    for section in sections:
        section["parser_mode"] = parser_mode

    return sections


def write_clean_lyrics(sections: list[dict[str, Any]], output_path: Path) -> None:
    output_lines: list[str] = []

    for section in sections:
        for line in section["lines"]:
            if line.get("display_type") != "lyric":
                continue

            output_lines.append(line["text"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def write_line_map(
    sections: list[dict[str, Any]],
    output_path: Path,
    source_audio: Path,
    source_lyrics: Path,
) -> None:
    flat_lines: list[dict[str, Any]] = []
    word_index = 0
    section_summaries: list[dict[str, Any]] = []

    for section_index, section in enumerate(sections, start=1):
        section_id = section_id_from_label(section["label"], section_index)
        section_lyric_count = 0
        section_instrumental_count = 0

        for line in section["lines"]:
            display_type = line.get("display_type", "lyric")
            words = line.get("words", [])

            if display_type == "instrumental":
                start_word_index = None
                end_word_index = None
                section_instrumental_count += 1
            else:
                start_word_index = word_index
                end_word_index = word_index + len(words) - 1
                word_index = end_word_index + 1
                section_lyric_count += 1

            flat_lines.append(
                {
                    "id": line["id"],
                    "section_id": section_id,
                    "section": section["label"],
                    "text": line["text"],
                    "display_type": display_type,
                    "words": words,
                    "start_word_index": start_word_index,
                    "end_word_index": end_word_index,
                }
            )

        section_summaries.append(
            {
                "id": section_id,
                "label": section["label"],
                "source": section.get("source", section.get("parser_mode", "unknown")),
                "parser_mode": section.get("parser_mode", "unknown"),
                "line_count": len(section["lines"]),
                "lyric_line_count": section_lyric_count,
                "instrumental_line_count": section_instrumental_count,
            }
        )

    line_map = {
        "schema_version": "kara-line-map-v2",
        "created_by": "kara-creator lyrics-aligner pipeline",
        "source": {
            "audio_file": str(source_audio),
            "lyrics_file": str(source_lyrics),
            "tokenisation": {
                "hyphenated_words": "merged",
                "apostrophes": "kept",
                "instrumental_placeholders": "excluded_from_aligner",
            },
        },
        "parser": {
            "auto_section_size": AUTO_SECTION_SIZE,
            "instrumental_placeholder_inputs": [". . .", "...", "…"],
            "instrumental_placeholder_output": INSTRUMENTAL_DISPLAY_TEXT,
        },
        "line_count": len(flat_lines),
        "lyric_line_count": sum(1 for line in flat_lines if line.get("display_type") == "lyric"),
        "instrumental_line_count": sum(1 for line in flat_lines if line.get("display_type") == "instrumental"),
        "word_count": word_index,
        "sections": section_summaries,
        "lines": flat_lines,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(line_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def strip_stress(phones: str) -> str:
    phones = re.sub(r"\d", "", phones)
    phones = re.sub(r"\s+", " ", phones).strip()
    return phones


def get_direct_phones(word: str) -> str | None:
    options = pronouncing.phones_for_word(word)

    if not options:
        return None

    return strip_stress(options[0])


def plural_s_phone(base_phones: str) -> str:
    phones = base_phones.split()
    last_phone = phones[-1] if phones else ""

    if last_phone in UNVOICED_FOR_S:
        return "S"

    return "Z"


def get_contraction_phones(word: str) -> str | None:
    for suffix, suffix_phones in CLITIC_SUFFIXES:
        if not word.endswith(suffix):
            continue

        base = word[: -len(suffix)]

        if not base:
            return None

        base_phones = get_direct_phones(base)

        if not base_phones:
            return None

        if suffix == "'s":
            suffix_phones = plural_s_phone(base_phones)

        return f"{base_phones} {suffix_phones}".strip()

    return None


def load_custom_pronunciations(project_root: Path) -> dict[str, str]:
    custom_path = project_root / "config" / "custom_pronunciations.json"

    if not custom_path.exists():
        return {}

    data = json.loads(custom_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Custom pronunciations file must be a JSON object: {custom_path}")

    custom: dict[str, str] = {}

    for raw_word, raw_phones in data.items():
        word = normalise_word(str(raw_word))
        phones = strip_stress(str(raw_phones).upper())

        if word and phones:
            custom[word] = phones

    return custom


def get_word_phones(word: str, custom_pronunciations: dict[str, str]) -> str | None:
    if word in custom_pronunciations:
        return custom_pronunciations[word]

    direct = get_direct_phones(word)

    if direct:
        return direct

    contraction = get_contraction_phones(word)

    if contraction:
        return contraction

    return None


def create_word2phonemes_file(
    word_list_path: Path,
    output_path: Path,
    missing_path: Path,
    custom_pronunciations: dict[str, str],
) -> None:
    require_file(word_list_path, "Word list")

    words: list[str] = []

    for raw_line in word_list_path.read_text(encoding="utf-8-sig").splitlines():
        word = normalise_word(raw_line)

        if word:
            words.append(word)

    words = sorted(set(words))

    output_lines: list[str] = []
    missing_words: list[str] = []

    for word in words:
        phones = get_word_phones(word, custom_pronunciations)

        if phones:
            output_lines.append(f"{word}\t{phones}")
        else:
            missing_words.append(word)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    if missing_path.exists():
        missing_path.unlink()

    if missing_words:
        missing_path.parent.mkdir(parents=True, exist_ok=True)
        missing_path.write_text("\n".join(missing_words) + "\n", encoding="utf-8")
        raise ValueError(
            f"{len(missing_words)} words are missing pronunciations. "
            f"Open this file and send the words here: {missing_path}"
        )


def clean_previous_aligner_files(aligner_dir: Path, dataset_name: str) -> list[str]:
    removed: list[str] = []

    files_dir = aligner_dir / "files"
    outputs_dir = aligner_dir / "outputs" / dataset_name

    if files_dir.exists():
        for path in files_dir.glob(f"{dataset_name}*"):
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                shutil.rmtree(path)
                removed.append(str(path))

    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
        removed.append(str(outputs_dir))

    return removed


def write_run_manifest(
    manifest_path: Path,
    *,
    safe_name: str,
    dataset_name: str,
    source_audio: Path,
    source_lyrics: Path,
    clean_audio_path: Path,
    clean_lyrics_path: Path,
    line_map_path: Path,
    word_review_path: Path,
    draft_path: Path,
    sections: list[dict[str, Any]],
    removed_files: list[str],
) -> None:
    manifest = {
        "schema_version": "kara-run-manifest-v2",
        "song_name": safe_name,
        "dataset_name": dataset_name,
        "source": {
            "audio_file": str(source_audio),
            "lyrics_file": str(source_lyrics),
        },
        "prepared_inputs": {
            "audio_file": str(clean_audio_path),
            "lyrics_file": str(clean_lyrics_path),
            "line_map_json": str(line_map_path),
        },
        "outputs": {
            "word_review_json": str(word_review_path),
            "draft_json": str(draft_path),
        },
        "parser": {
            "auto_section_size": AUTO_SECTION_SIZE,
            "instrumental_placeholder_inputs": [". . .", "...", "…"],
            "instrumental_placeholder_output": INSTRUMENTAL_DISPLAY_TEXT,
            "aligner_lyrics_exclude_instrumentals": True,
        },
        "sections": [
            {
                "label": section["label"],
                "source": section.get("source", section.get("parser_mode", "unknown")),
                "parser_mode": section.get("parser_mode", "unknown"),
                "line_count": len(section["lines"]),
                "lyric_line_count": sum(1 for line in section["lines"] if line.get("display_type") == "lyric"),
                "instrumental_line_count": sum(1 for line in section["lines"] if line.get("display_type") == "instrumental"),
            }
            for section in sections
        ],
        "cleanup": {
            "removed_previous_aligner_files": removed_files,
        },
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_pipeline(
    project_root: Path,
    audio_path: Path,
    lyrics_path: Path,
    name: str,
    aligner_dir: Path,
    clean_previous: bool,
) -> None:
    require_file(audio_path, "Input vocal MP3")
    require_file(lyrics_path, "Input lyrics TXT")
    require_dir(aligner_dir, "lyrics-aligner folder")

    safe_name = slugify(name)
    dataset_name = f"kara_{safe_name}"

    run_dir = project_root / "alignment_lab" / "runs" / safe_name
    run_audio_dir = run_dir / "audio"
    run_lyrics_dir = run_dir / "lyrics"

    clean_audio_path = run_audio_dir / f"{safe_name}{audio_path.suffix.lower()}"
    clean_lyrics_path = run_lyrics_dir / f"{safe_name}.txt"
    line_map_path = run_dir / f"{safe_name}-line-map.json"
    manifest_path = run_dir / f"{safe_name}-run-manifest.json"

    word_review_path = project_root / "outputs" / f"{safe_name}-word-review-lyrics-aligner.json"
    draft_path = project_root / "outputs" / f"{safe_name}-draft-lyrics-aligner-v3.json"

    removed_files: list[str] = []

    if clean_previous:
        removed_files = clean_previous_aligner_files(
            aligner_dir=aligner_dir,
            dataset_name=dataset_name,
        )

    custom_pronunciations = load_custom_pronunciations(project_root)
    sections = parse_sectioned_lyrics(lyrics_path)

    run_audio_dir.mkdir(parents=True, exist_ok=True)
    run_lyrics_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "outputs").mkdir(parents=True, exist_ok=True)

    shutil.copy2(audio_path, clean_audio_path)
    write_clean_lyrics(sections, clean_lyrics_path)
    write_line_map(
        sections=sections,
        output_path=line_map_path,
        source_audio=audio_path,
        source_lyrics=lyrics_path,
    )

    write_run_manifest(
        manifest_path=manifest_path,
        safe_name=safe_name,
        dataset_name=dataset_name,
        source_audio=audio_path,
        source_lyrics=lyrics_path,
        clean_audio_path=clean_audio_path,
        clean_lyrics_path=clean_lyrics_path,
        line_map_path=line_map_path,
        word_review_path=word_review_path,
        draft_path=draft_path,
        sections=sections,
        removed_files=removed_files,
    )

    print("")
    print("Prepared song files.")
    print(f"Run folder:    {run_dir}")
    print(f"Clean audio:   {clean_audio_path}")
    print(f"Clean lyrics:  {clean_lyrics_path}")
    print(f"Line map:      {line_map_path}")
    print(f"Manifest:      {manifest_path}")
    print(f"Custom pronunciations loaded: {len(custom_pronunciations)}")
    print(f"Display lines: {sum(len(section['lines']) for section in sections)}")
    print(f"Lyric lines sent to aligner: {sum(1 for section in sections for line in section['lines'] if line.get('display_type') == 'lyric')}")
    print(f"Instrumental placeholders: {sum(1 for section in sections for line in section['lines'] if line.get('display_type') == 'instrumental')}")

    if clean_previous:
        print(f"Previous aligner files removed: {len(removed_files)}")

    run_command(
        [
            sys.executable,
            "make_word_list.py",
            str(run_lyrics_dir),
            "--dataset-name",
            dataset_name,
        ],
        cwd=aligner_dir,
    )

    word_list_path = aligner_dir / "files" / f"{dataset_name}_word_list.txt"
    word2phonemes_path = aligner_dir / "files" / f"{dataset_name}_word2phonemes.txt"
    missing_path = aligner_dir / "files" / f"{dataset_name}_missing_words.txt"

    create_word2phonemes_file(
        word_list_path=word_list_path,
        output_path=word2phonemes_path,
        missing_path=missing_path,
        custom_pronunciations=custom_pronunciations,
    )

    run_command(
        [
            sys.executable,
            "make_word2phoneme_dict.py",
            "--dataset-name",
            dataset_name,
        ],
        cwd=aligner_dir,
    )

    run_command(
        [
            sys.executable,
            "align.py",
            str(run_audio_dir),
            str(run_lyrics_dir),
            "--lyrics-format",
            "w",
            "--onsets",
            "w",
            "--dataset-name",
            dataset_name,
            "--vad-threshold",
            "0",
        ],
        cwd=aligner_dir,
    )

    aligner_output_path = (
        aligner_dir
        / "outputs"
        / dataset_name
        / "word_onsets"
        / f"{safe_name}.txt"
    )

    require_file(aligner_output_path, "lyrics-aligner word onset output")

    run_command(
        [
            sys.executable,
            str(project_root / "tools" / "convert_lyrics_aligner_to_word_review_json.py"),
            "--aligner-output",
            str(aligner_output_path),
            "--line-map",
            str(line_map_path),
            "--out",
            str(word_review_path),
        ],
        cwd=project_root,
    )

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

    print("")
    print("Done.")
    print("")
    print(f"Word review JSON: {word_review_path}")
    print(f"Draft JSON:       {draft_path}")
    print("")
    print("Open the editor and load:")
    print(f"Audio: {clean_audio_path}")
    print(f"JSON:  {draft_path}")
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local lyrics-aligner karaoke draft pipeline."
    )

    parser.add_argument(
        "--audio",
        required=True,
        help="Path to isolated vocal MP3.",
    )

    parser.add_argument(
        "--lyrics",
        required=True,
        help="Path to exact lyrics TXT. Section headings are optional. Blank lines can create sections. . . . lines are instrumental placeholders.",
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Short song name, for example miss_the_mountains.",
    )

    parser.add_argument(
        "--aligner-dir",
        default=r"C:\Users\mark\kara-creator\alignment_lab\singing-aligners\lyrics-aligner",
        help="Path to the cloned lyrics-aligner folder.",
    )

    parser.add_argument(
        "--keep-previous",
        action="store_true",
        help="Do not clean previous lyrics-aligner files for this song name before running.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]

    try:
        run_pipeline(
            project_root=project_root,
            audio_path=Path(args.audio).resolve(),
            lyrics_path=Path(args.lyrics).resolve(),
            name=args.name,
            aligner_dir=Path(args.aligner_dir).resolve(),
            clean_previous=not args.keep_previous,
        )
    except Exception as error:
        print("")
        print("Pipeline failed.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
