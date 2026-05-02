from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile


@dataclass
class LyricLine:
    section_index: int
    section_label: str
    text: str


@dataclass
class AudioRegion:
    start: float
    end: float
    peak_rms: float


def round_time(value: float) -> float:
    return round(float(value), 3)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "section"


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def convert_audio_to_wav(input_audio: Path, output_wav: Path, sample_rate: int) -> None:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError(
            "FFmpeg was not found. Install it, close PowerShell, reopen PowerShell, "
            "then run this command again."
        )

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
            f"Command:\n{' '.join(command)}\n\n"
            f"Error:\n{completed.stderr.strip()}"
        )


def read_wav_mono(wav_path: Path) -> tuple[int, np.ndarray]:
    sample_rate, audio = wavfile.read(str(wav_path))

    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    if np.issubdtype(audio.dtype, np.integer):
        max_value = np.iinfo(audio.dtype).max
        audio = audio.astype(np.float32) / max_value
    else:
        audio = audio.astype(np.float32)

    audio = np.nan_to_num(audio)

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak

    return sample_rate, audio


def moving_average(values: np.ndarray, window_size: int) -> np.ndarray:
    if window_size <= 1 or values.size == 0:
        return values

    window_size = min(window_size, values.size)
    kernel = np.ones(window_size, dtype=np.float32) / window_size
    return np.convolve(values, kernel, mode="same")


def calculate_rms_envelope(
    audio: np.ndarray,
    sample_rate: int,
    frame_ms: int,
    hop_ms: int,
    smooth_frames: int,
) -> tuple[np.ndarray, float]:
    frame_size = max(1, int(sample_rate * frame_ms / 1000))
    hop_size = max(1, int(sample_rate * hop_ms / 1000))

    if audio.size < frame_size:
        audio = np.pad(audio, (0, frame_size - audio.size))

    frame_count = 1 + max(0, (audio.size - frame_size) // hop_size)
    rms_values = np.zeros(frame_count, dtype=np.float32)

    for index in range(frame_count):
        start = index * hop_size
        end = start + frame_size
        frame = audio[start:end]

        if frame.size == 0:
            rms_values[index] = 0.0
        else:
            rms_values[index] = float(np.sqrt(np.mean(frame * frame)))

    rms_values = moving_average(rms_values, smooth_frames)
    hop_seconds = hop_size / sample_rate

    return rms_values, hop_seconds


def fill_short_gaps(active: np.ndarray, max_gap_frames: int) -> np.ndarray:
    if active.size == 0 or max_gap_frames <= 0:
        return active

    filled = active.copy()
    index = 0

    while index < filled.size:
        if filled[index]:
            index += 1
            continue

        gap_start = index
        while index < filled.size and not filled[index]:
            index += 1
        gap_end = index

        has_active_before = gap_start > 0 and filled[gap_start - 1]
        has_active_after = gap_end < filled.size and filled[gap_end]

        if has_active_before and has_active_after:
            gap_length = gap_end - gap_start
            if gap_length <= max_gap_frames:
                filled[gap_start:gap_end] = True

    return filled


def find_audio_regions(
    audio: np.ndarray,
    sample_rate: int,
    frame_ms: int,
    hop_ms: int,
    sensitivity: float,
    min_region_ms: int,
    max_gap_ms: int,
    pad_ms: int,
) -> tuple[list[AudioRegion], dict[str, Any]]:
    rms_values, hop_seconds = calculate_rms_envelope(
        audio=audio,
        sample_rate=sample_rate,
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        smooth_frames=7,
    )

    if rms_values.size == 0:
        return [], {
            "threshold": 0.0,
            "rms_p20": 0.0,
            "rms_p95": 0.0,
        }

    p20 = float(np.percentile(rms_values, 20))
    p95 = float(np.percentile(rms_values, 95))

    sensitivity = max(0.05, min(0.95, sensitivity))
    threshold = p20 + sensitivity * (p95 - p20)

    active = rms_values >= threshold

    max_gap_frames = int(max_gap_ms / hop_ms)
    active = fill_short_gaps(active, max_gap_frames=max_gap_frames)

    regions: list[AudioRegion] = []
    index = 0
    duration = audio.size / sample_rate
    min_region_seconds = min_region_ms / 1000
    pad_seconds = pad_ms / 1000

    while index < active.size:
        if not active[index]:
            index += 1
            continue

        start_frame = index

        while index < active.size and active[index]:
            index += 1

        end_frame = index

        start_seconds = max(0.0, start_frame * hop_seconds - pad_seconds)
        end_seconds = min(duration, end_frame * hop_seconds + pad_seconds)

        if end_seconds - start_seconds >= min_region_seconds:
            peak_rms = float(np.max(rms_values[start_frame:end_frame]))
            regions.append(
                AudioRegion(
                    start=start_seconds,
                    end=end_seconds,
                    peak_rms=peak_rms,
                )
            )

    merged = merge_close_regions(regions, max_gap_seconds=max_gap_ms / 1000)

    stats = {
        "threshold": round(float(threshold), 6),
        "rms_p20": round(float(p20), 6),
        "rms_p95": round(float(p95), 6),
    }

    return merged, stats


def merge_close_regions(regions: list[AudioRegion], max_gap_seconds: float) -> list[AudioRegion]:
    if not regions:
        return []

    merged: list[AudioRegion] = [regions[0]]

    for region in regions[1:]:
        previous = merged[-1]
        gap = region.start - previous.end

        if gap <= max_gap_seconds:
            previous.end = max(previous.end, region.end)
            previous.peak_rms = max(previous.peak_rms, region.peak_rms)
        else:
            merged.append(region)

    return merged


def parse_lyrics(lyrics_path: Path) -> tuple[list[str], list[LyricLine]]:
    text = lyrics_path.read_text(encoding="utf-8-sig")
    raw_lines = text.splitlines()

    section_labels: list[str] = []
    lyric_lines: list[LyricLine] = []

    current_section = "Song"
    current_section_index = 0
    section_labels.append(current_section)

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        section_match = re.match(r"^\[(.+?)\]$", line)
        if section_match:
            current_section = section_match.group(1).strip() or "Section"
            section_labels.append(current_section)
            current_section_index = len(section_labels) - 1
            continue

        lyric_lines.append(
            LyricLine(
                section_index=current_section_index,
                section_label=current_section,
                text=line,
            )
        )

    used_section_indexes = {line.section_index for line in lyric_lines}
    used_sections = [
        label for index, label in enumerate(section_labels) if index in used_section_indexes
    ]

    return used_sections, lyric_lines


def assign_regions_to_lines(
    regions: list[AudioRegion],
    lyric_line_count: int,
    audio_duration: float,
) -> list[tuple[float, float]]:
    if lyric_line_count <= 0:
        return []

    if not regions:
        fallback_duration = max(audio_duration, lyric_line_count * 3.0)
        line_duration = fallback_duration / lyric_line_count

        return [
            (index * line_duration, (index + 1) * line_duration)
            for index in range(lyric_line_count)
        ]

    region_count = len(regions)

    if region_count >= lyric_line_count:
        assignments: list[tuple[float, float]] = []

        for line_index in range(lyric_line_count):
            start_region_index = math.floor(line_index * region_count / lyric_line_count)
            end_region_index = math.floor((line_index + 1) * region_count / lyric_line_count) - 1

            start_region_index = max(0, min(region_count - 1, start_region_index))
            end_region_index = max(start_region_index, min(region_count - 1, end_region_index))

            start = regions[start_region_index].start
            end = regions[end_region_index].end

            assignments.append((start, end))

        return assignments

    assignments = []

    for region_index, region in enumerate(regions):
        start_line_index = math.floor(region_index * lyric_line_count / region_count)
        end_line_index = math.floor((region_index + 1) * lyric_line_count / region_count)
        lines_in_region = max(1, end_line_index - start_line_index)

        region_duration = max(0.2, region.end - region.start)
        sub_duration = region_duration / lines_in_region

        for local_index in range(lines_in_region):
            start = region.start + local_index * sub_duration
            end = region.start + (local_index + 1) * sub_duration
            assignments.append((start, end))

    while len(assignments) < lyric_line_count:
        last_start, last_end = assignments[-1]
        next_start = last_end
        next_end = next_start + max(1.0, last_end - last_start)
        assignments.append((next_start, next_end))

    return assignments[:lyric_line_count]


def build_output_json(
    input_audio: Path,
    lyrics_path: Path,
    output_path: Path,
    sample_rate: int,
    audio_duration: float,
    regions: list[AudioRegion],
    region_stats: dict[str, Any],
    lyric_lines: list[LyricLine],
    assignments: list[tuple[float, float]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    sections_by_index: dict[int, dict[str, Any]] = {}

    for line_number, lyric_line in enumerate(lyric_lines, start=1):
        start, end = assignments[line_number - 1]

        if lyric_line.section_index not in sections_by_index:
            section_number = len(sections_by_index) + 1
            section_label = lyric_line.section_label

            sections_by_index[lyric_line.section_index] = {
                "id": f"{slugify(section_label)}-{section_number:03d}",
                "label": section_label,
                "start": None,
                "end": None,
                "lines": [],
            }

        section = sections_by_index[lyric_line.section_index]

        line_entry = {
            "id": f"line-{line_number:04d}",
            "text": lyric_line.text,
            "start": round_time(start),
            "end": round_time(end),
            "confidence": "draft",
            "locked": False,
            "anchor": False,
        }

        section["lines"].append(line_entry)

    sections = list(sections_by_index.values())

    for section in sections:
        if section["lines"]:
            section["start"] = section["lines"][0]["start"]
            section["end"] = section["lines"][-1]["end"]
        else:
            section["start"] = 0.0
            section["end"] = 0.0

    return {
        "schema_version": "karaoke-draft-v1",
        "created_by": "kara-creator phase 1 cli",
        "source": {
            "audio_file": str(input_audio),
            "lyrics_file": str(lyrics_path),
            "audio_duration_seconds": round_time(audio_duration),
            "analysis_sample_rate": sample_rate,
        },
        "alignment": {
            "mode": "vocal-energy-to-known-lyrics",
            "status": "draft",
            "lyric_line_count": len(lyric_lines),
            "detected_audio_region_count": len(regions),
            "settings": settings,
            "region_detection_stats": region_stats,
        },
        "sections": sections,
        "raw_audio_regions": [
            {
                "id": f"region-{index:04d}",
                "start": round_time(region.start),
                "end": round_time(region.end),
                "peak_rms": round(float(region.peak_rms), 6),
            }
            for index, region in enumerate(regions, start=1)
        ],
        "editor_notes": [
            "This is a draft generated from isolated vocal energy and known lyric lines.",
            "Check section starts and ends first.",
            "Then correct line timings.",
            "Do not treat these timings as final without review.",
        ],
    }


def generate_draft(args: argparse.Namespace) -> None:
    input_audio = Path(args.audio).resolve()
    lyrics_path = Path(args.lyrics).resolve()
    output_path = Path(args.out).resolve()

    require_file(input_audio, "Audio file")
    require_file(lyrics_path, "Lyrics file")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    _, lyric_lines = parse_lyrics(lyrics_path)

    if not lyric_lines:
        raise ValueError(
            "No lyric lines were found. Add plain lyric lines to the TXT file. "
            "Section headings should look like [Verse 1]."
        )

    settings = {
        "frame_ms": args.frame_ms,
        "hop_ms": args.hop_ms,
        "sensitivity": args.sensitivity,
        "min_region_ms": args.min_region_ms,
        "max_gap_ms": args.max_gap_ms,
        "pad_ms": args.pad_ms,
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "analysis.wav"

        convert_audio_to_wav(
            input_audio=input_audio,
            output_wav=wav_path,
            sample_rate=args.sample_rate,
        )

        sample_rate, audio = read_wav_mono(wav_path)
        audio_duration = audio.size / sample_rate

        regions, region_stats = find_audio_regions(
            audio=audio,
            sample_rate=sample_rate,
            frame_ms=args.frame_ms,
            hop_ms=args.hop_ms,
            sensitivity=args.sensitivity,
            min_region_ms=args.min_region_ms,
            max_gap_ms=args.max_gap_ms,
            pad_ms=args.pad_ms,
        )

    assignments = assign_regions_to_lines(
        regions=regions,
        lyric_line_count=len(lyric_lines),
        audio_duration=audio_duration,
    )

    output = build_output_json(
        input_audio=input_audio,
        lyrics_path=lyrics_path,
        output_path=output_path,
        sample_rate=args.sample_rate,
        audio_duration=audio_duration,
        regions=regions,
        region_stats=region_stats,
        lyric_lines=lyric_lines,
        assignments=assignments,
        settings=settings,
    )

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("")
    print("Karaoke draft created.")
    print(f"Output: {output_path}")
    print("")
    print(f"Lyric lines: {len(lyric_lines)}")
    print(f"Detected vocal regions: {len(regions)}")
    print("")
    print("Open the JSON and check the section and line timings.")
    print("This is expected to need manual correction.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a draft section-based karaoke JSON from isolated vocals and exact lyrics."
    )

    parser.add_argument(
        "--audio",
        required=True,
        help="Path to the isolated vocal MP3 file.",
    )

    parser.add_argument(
        "--lyrics",
        required=True,
        help="Path to the clean lyrics TXT file.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path where the draft karaoke JSON should be written.",
    )

    parser.add_argument(
        "--sample-rate",
        type=int,
        default=22050,
        help="Sample rate used for analysis. Default: 22050.",
    )

    parser.add_argument(
        "--frame-ms",
        type=int,
        default=40,
        help="Analysis frame size in milliseconds. Default: 40.",
    )

    parser.add_argument(
        "--hop-ms",
        type=int,
        default=10,
        help="Analysis hop size in milliseconds. Default: 10.",
    )

    parser.add_argument(
        "--sensitivity",
        type=float,
        default=0.30,
        help=(
            "Detection sensitivity from 0.05 to 0.95. "
            "Lower values detect more vocal regions. Default: 0.30."
        ),
    )

    parser.add_argument(
        "--min-region-ms",
        type=int,
        default=350,
        help="Ignore detected vocal regions shorter than this. Default: 350.",
    )

    parser.add_argument(
        "--max-gap-ms",
        type=int,
        default=450,
        help="Merge vocal regions separated by gaps shorter than this. Default: 450.",
    )

    parser.add_argument(
        "--pad-ms",
        type=int,
        default=80,
        help="Add a little time before and after each detected region. Default: 80.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        generate_draft(args)
    except Exception as error:
        print("")
        print("Could not create karaoke draft.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())