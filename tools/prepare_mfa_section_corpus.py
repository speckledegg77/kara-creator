from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
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


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "section"


def normalise_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def normalise_word(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def words_from_line(line: str) -> list[str]:
    raw_words = re.findall(r"[A-Za-z0-9']+", line.replace("’", "'"))
    return [normalise_word(word) for word in raw_words if normalise_word(word)]


def parse_lyrics_by_section(lyrics_path: Path) -> list[dict[str, Any]]:
    text = lyrics_path.read_text(encoding="utf-8-sig")
    raw_lines = text.splitlines()

    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    line_number = 1

    def ensure_section(label: str) -> dict[str, Any]:
        nonlocal current_section

        if current_section is None or current_section["label"] != label:
            current_section = {
                "label": label,
                "lines": [],
            }
            sections.append(current_section)

        return current_section

    ensure_section("Song")

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        section_match = re.match(r"^\[(.+?)\]$", line)

        if section_match:
            label = section_match.group(1).strip() or "Section"
            ensure_section(label)
            continue

        words = words_from_line(line)

        if not words:
            continue

        current_section = ensure_section(current_section["label"] if current_section else "Song")

        current_section["lines"].append(
            {
                "id": f"line-{line_number:04d}",
                "section": current_section["label"],
                "text": line,
                "words": words,
            }
        )

        line_number += 1

    return [section for section in sections if section["lines"]]


def load_section_bounds(bounds_path: Path) -> list[dict[str, Any]]:
    data = load_json(bounds_path)
    sections = data.get("sections", [])

    if not isinstance(sections, list) or not sections:
        raise ValueError("Section bounds JSON must contain a non-empty sections array.")

    cleaned_sections: list[dict[str, Any]] = []

    for section in sections:
        label = str(section.get("label", "")).strip()
        start = as_float(section.get("start"))
        end = as_float(section.get("end"))

        if not label:
            raise ValueError("A section in the bounds file has no label.")

        if end <= start:
            raise ValueError(f"Section {label} has invalid start/end times.")

        cleaned_sections.append(
            {
                "label": label,
                "start": round_time(start),
                "end": round_time(end),
            }
        )

    return cleaned_sections


def find_matching_lyrics_section(
    lyric_sections: list[dict[str, Any]],
    bounds_label: str,
) -> dict[str, Any]:
    target = normalise_label(bounds_label)

    for section in lyric_sections:
        if normalise_label(section["label"]) == target:
            return section

    available = ", ".join(section["label"] for section in lyric_sections)

    raise ValueError(
        f"Could not find lyrics section '{bounds_label}'. Available sections: {available}"
    )


def convert_audio_section_to_wav(
    input_audio: Path,
    output_wav: Path,
    start: float,
    end: float,
    sample_rate: int,
) -> None:
    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        raise RuntimeError("FFmpeg was not found. Check that ffmpeg -version works in PowerShell.")

    duration = max(0.1, end - start)

    command = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_audio),
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        str(output_wav),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"FFmpeg could not create section WAV: {output_wav}\n\n"
            f"{completed.stderr.strip()}"
        )


def build_section_transcript_and_line_map(section: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    transcript_words: list[str] = []
    mapped_lines: list[dict[str, Any]] = []

    for line in section["lines"]:
        start_word_index = len(transcript_words)
        transcript_words.extend(line["words"])
        end_word_index = len(transcript_words) - 1

        mapped_lines.append(
            {
                "id": line["id"],
                "section": line["section"],
                "text": line["text"],
                "words": line["words"],
                "start_word_index": start_word_index,
                "end_word_index": end_word_index,
            }
        )

    return " ".join(transcript_words), mapped_lines


def prepare_section_corpus(
    audio_path: Path,
    lyrics_path: Path,
    bounds_path: Path,
    output_dir: Path,
    name: str,
    sample_rate: int,
) -> None:
    require_file(audio_path, "Audio file")
    require_file(lyrics_path, "Lyrics file")
    require_file(bounds_path, "Section bounds file")

    lyric_sections = parse_lyrics_by_section(lyrics_path)
    bounds_sections = load_section_bounds(bounds_path)

    corpus_dir = output_dir / "corpus"
    aligned_dir = output_dir / "aligned"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    aligned_dir.mkdir(parents=True, exist_ok=True)

    section_map_entries: list[dict[str, Any]] = []
    safe_song_name = slugify(name)

    for index, bounds_section in enumerate(bounds_sections, start=1):
        lyrics_section = find_matching_lyrics_section(
            lyric_sections=lyric_sections,
            bounds_label=bounds_section["label"],
        )

        transcript, mapped_lines = build_section_transcript_and_line_map(lyrics_section)

        file_base = f"{safe_song_name}_{index:02d}_{slugify(bounds_section['label'])}"
        wav_path = corpus_dir / f"{file_base}.wav"
        lab_path = corpus_dir / f"{file_base}.lab"

        convert_audio_section_to_wav(
            input_audio=audio_path,
            output_wav=wav_path,
            start=bounds_section["start"],
            end=bounds_section["end"],
            sample_rate=sample_rate,
        )

        lab_path.write_text(transcript + "\n", encoding="utf-8")

        section_map_entries.append(
            {
                "id": f"{slugify(bounds_section['label']).replace('_', '-')}-{index:03d}",
                "label": bounds_section["label"],
                "file_base": file_base,
                "wav_file": str(wav_path),
                "lab_file": str(lab_path),
                "global_start": bounds_section["start"],
                "global_end": bounds_section["end"],
                "local_duration": round_time(bounds_section["end"] - bounds_section["start"]),
                "transcript_word_count": len(transcript.split()),
                "lines": mapped_lines,
            }
        )

    section_map = {
        "schema_version": "kara-mfa-section-line-map-v1",
        "song_name": name,
        "source": {
            "audio_file": str(audio_path),
            "lyrics_file": str(lyrics_path),
            "bounds_file": str(bounds_path),
            "sample_rate": sample_rate,
            "corpus_dir": str(corpus_dir),
            "aligned_dir": str(aligned_dir),
        },
        "sections": section_map_entries,
    }

    map_path = output_dir / f"{safe_song_name}-section-line-map.json"
    map_path.write_text(
        json.dumps(section_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("")
    print("Sectioned MFA corpus prepared.")
    print(f"Corpus folder: {corpus_dir}")
    print(f"Section map:   {map_path}")
    print("")
    print("Next command:")
    print("")
    print(
        f'mfa align --output_format json "{corpus_dir}" english_us_arpa english_us_arpa "{aligned_dir}" --clean'
    )
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare section-based MFA corpus from one audio file, exact lyrics, and section bounds."
    )

    parser.add_argument("--audio", required=True, help="Path to isolated vocal MP3.")
    parser.add_argument("--lyrics", required=True, help="Path to exact lyrics TXT file.")
    parser.add_argument("--bounds", required=True, help="Path to section bounds JSON.")
    parser.add_argument("--out-dir", required=True, help="Output folder for sectioned MFA files.")
    parser.add_argument("--name", required=True, help="Short song name.")
    parser.add_argument("--sample-rate", type=int, default=16000, help="WAV sample rate. Default: 16000.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        prepare_section_corpus(
            audio_path=Path(args.audio).resolve(),
            lyrics_path=Path(args.lyrics).resolve(),
            bounds_path=Path(args.bounds).resolve(),
            output_dir=Path(args.out_dir).resolve(),
            name=args.name,
            sample_rate=args.sample_rate,
        )

    except Exception as error:
        print("")
        print("Could not prepare sectioned MFA corpus.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())