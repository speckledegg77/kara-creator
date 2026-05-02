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


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "karaoke_test"


def normalise_word(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


def words_from_line(line: str) -> list[str]:
    raw_words = re.findall(r"[A-Za-z0-9']+", line.replace("’", "'"))
    return [normalise_word(word) for word in raw_words if normalise_word(word)]


def parse_lyrics(lyrics_path: Path) -> tuple[str, list[dict[str, Any]]]:
    text = lyrics_path.read_text(encoding="utf-8-sig")
    raw_lines = text.splitlines()

    current_section = "Song"
    line_entries: list[dict[str, Any]] = []
    transcript_words: list[str] = []
    line_number = 1

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        section_match = re.match(r"^\[(.+?)\]$", line)
        if section_match:
            current_section = section_match.group(1).strip() or "Section"
            continue

        line_words = words_from_line(line)

        if not line_words:
            continue

        start_word_index = len(transcript_words)
        transcript_words.extend(line_words)
        end_word_index = len(transcript_words) - 1

        line_entries.append(
            {
                "id": f"line-{line_number:04d}",
                "section": current_section,
                "text": line,
                "words": line_words,
                "start_word_index": start_word_index,
                "end_word_index": end_word_index,
            }
        )

        line_number += 1

    if not transcript_words:
        raise ValueError("No lyric words were found.")

    transcript = " ".join(transcript_words)

    return transcript, line_entries


def convert_audio_to_wav(input_audio: Path, output_wav: Path, sample_rate: int) -> None:
    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        raise RuntimeError("FFmpeg was not found. Check that ffmpeg -version works in PowerShell.")

    command = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_audio),
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
            "FFmpeg could not convert the audio file.\n\n"
            f"Error:\n{completed.stderr.strip()}"
        )


def write_outputs(
    name: str,
    audio_path: Path,
    lyrics_path: Path,
    output_dir: Path,
    sample_rate: int,
) -> None:
    safe_name = slugify(name)

    corpus_dir = output_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    wav_path = corpus_dir / f"{safe_name}.wav"
    lab_path = corpus_dir / f"{safe_name}.lab"
    line_map_path = output_dir / f"{safe_name}-line-map.json"

    transcript, line_entries = parse_lyrics(lyrics_path)

    convert_audio_to_wav(
        input_audio=audio_path,
        output_wav=wav_path,
        sample_rate=sample_rate,
    )

    lab_path.write_text(transcript + "\n", encoding="utf-8")

    line_map = {
        "schema_version": "kara-mfa-line-map-v1",
        "source": {
            "audio_file": str(audio_path),
            "lyrics_file": str(lyrics_path),
            "mfa_wav_file": str(wav_path),
            "mfa_lab_file": str(lab_path),
            "sample_rate": sample_rate,
        },
        "transcript_word_count": len(transcript.split()),
        "lines": line_entries,
    }

    line_map_path.write_text(
        json.dumps(line_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("")
    print("MFA input prepared.")
    print("")
    print(f"WAV:      {wav_path}")
    print(f"LAB:      {lab_path}")
    print(f"Line map: {line_map_path}")
    print("")
    print("Next command to run:")
    print("")
    print(
        f'mfa align_one --output_format json "{wav_path}" "{lab_path}" english_us_arpa english_us_arpa "{output_dir / "aligned" / f"{safe_name}.json"}"'
    )
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare one isolated vocal file and lyric file for Montreal Forced Aligner."
    )

    parser.add_argument(
        "--audio",
        required=True,
        help="Path to the isolated vocal MP3.",
    )

    parser.add_argument(
        "--lyrics",
        required=True,
        help="Path to the exact lyrics TXT file.",
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Short name for this MFA test, for example miss_the_mountains.",
    )

    parser.add_argument(
        "--out-dir",
        default="mfa_test",
        help="Output folder for MFA files. Default: mfa_test.",
    )

    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="WAV sample rate for MFA. Default: 16000.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    lyrics_path = Path(args.lyrics).resolve()
    output_dir = Path(args.out_dir).resolve()

    try:
        require_file(audio_path, "Audio file")
        require_file(lyrics_path, "Lyrics file")

        (output_dir / "aligned").mkdir(parents=True, exist_ok=True)

        write_outputs(
            name=args.name,
            audio_path=audio_path,
            lyrics_path=lyrics_path,
            output_dir=output_dir,
            sample_rate=args.sample_rate,
        )

    except Exception as error:
        print("")
        print("Could not prepare MFA input.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())