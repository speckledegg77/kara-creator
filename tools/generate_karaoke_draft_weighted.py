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
class LyricSection:
    index: int
    label: str
    lines: list[LyricLine]


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
            "FFmpeg was not found. Install it, close PowerShell, reopen PowerShell, then try again."
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


def parse_lyrics(lyrics_path: Path) -> list[LyricSection]:
    text = lyrics_path.read_text(encoding="utf-8-sig")
    raw_lines = text.splitlines()

    sections: list[LyricSection] = []
    current_section = LyricSection(index=0, label="Song", lines=[])
    sections.append(current_section)

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        section_match = re.match(r"^\[(.+?)\]$", line)

        if section_match:
            label = section_match.group(1).strip() or "Section"
            current_section = LyricSection(
                index=len(sections),
                label=label,
                lines=[],
            )
            sections.append(current_section)
            continue

        current_section.lines.append(
            LyricLine(
                section_index=current_section.index,
                section_label=current_section.label,
                text=line,
            )
        )

    return [section for section in sections if section.lines]


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def line_weight(text: str) -> float:
    words = count_words(text)
    characters = len(re.sub(r"\s+", "", text))

    word_score = words * 1.0
    character_score = characters / 18

    return max(1.5, word_score + character_score)


def section_weight(section: LyricSection) -> float:
    return sum(line_weight(line.text) for line in section.lines)


def find_nearby_audio_regions(
    regions: list[AudioRegion],
    start: float,
    end: float,
) -> list[AudioRegion]:
    matching: list[AudioRegion] = []

    for region in regions:
        overlaps = region.start <= end and region.end >= start

        if overlaps:
            matching.append(region)

    return matching


def load_calibration_truth(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None

    require_file(path, "Calibration truth JSON")

    truth = json.loads(path.read_text(encoding="utf-8"))

    section = truth.get("section")

    if not isinstance(section, dict):
        raise ValueError("Calibration truth JSON does not contain a section object.")

    lines = section.get("lines")

    if not isinstance(lines, list) or not lines:
        raise ValueError("Calibration truth JSON does not contain section lines.")

    return truth


def calibration_seconds_per_weight(truth: dict[str, Any] | None) -> float | None:
    if not truth:
        return None

    section = truth["section"]
    total_weight = 0.0
    total_duration = 0.0

    for line in section["lines"]:
        text = str(line.get("text", ""))
        start = float(line.get("start", 0))
        end = float(line.get("end", 0))
        duration = max(0.0, end - start)

        if duration > 0:
            total_weight += line_weight(text)
            total_duration += duration

    if total_weight <= 0 or total_duration <= 0:
        return None

    return total_duration / total_weight


def build_weighted_output(
    input_audio: Path,
    lyrics_path: Path,
    sample_rate: int,
    audio_duration: float,
    regions: list[AudioRegion],
    region_stats: dict[str, Any],
    lyric_sections: list[LyricSection],
    settings: dict[str, Any],
    calibration_truth: dict[str, Any] | None,
) -> dict[str, Any]:
    if regions:
        vocal_start = regions[0].start
        vocal_end = regions[-1].end
    else:
        vocal_start = 0.0
        vocal_end = audio_duration

    detected_vocal_span = max(0.1, vocal_end - vocal_start)

    weights_by_section = [section_weight(section) for section in lyric_sections]
    total_weight = sum(weights_by_section)

    if total_weight <= 0:
        raise ValueError("Could not calculate lyric weights.")

    calibration_rate = calibration_seconds_per_weight(calibration_truth)

    if calibration_rate:
        estimated_span_from_calibration = total_weight * calibration_rate
        working_span = min(audio_duration - vocal_start, max(detected_vocal_span, estimated_span_from_calibration))
        timing_mode = "weighted-lyrics-with-calibration"
    else:
        working_span = detected_vocal_span
        timing_mode = "weighted-lyrics"

    section_entries: list[dict[str, Any]] = []
    line_number = 1
    cursor = vocal_start

    for section_index, section in enumerate(lyric_sections, start=1):
        this_section_weight = weights_by_section[section_index - 1]
        raw_section_duration = working_span * (this_section_weight / total_weight)

        is_last_section = section_index == len(lyric_sections)

        if is_last_section:
            section_start = cursor
            section_end = min(audio_duration, vocal_start + working_span)
        else:
            section_start = cursor
            section_end = cursor + raw_section_duration

        section_regions = find_nearby_audio_regions(
            regions=regions,
            start=section_start,
            end=section_end,
        )

        if section_regions:
            section_start = min(section_start, section_regions[0].start)
            section_end = max(section_end, section_regions[-1].end)

        line_weights = [line_weight(line.text) for line in section.lines]
        section_line_weight = sum(line_weights)

        line_cursor = section_start
        line_entries: list[dict[str, Any]] = []

        for local_line_index, lyric_line in enumerate(section.lines):
            this_line_weight = line_weights[local_line_index]

            if local_line_index == len(section.lines) - 1:
                line_start = line_cursor
                line_end = section_end
            else:
                line_duration = max(0.8, (section_end - section_start) * (this_line_weight / section_line_weight))
                line_start = line_cursor
                line_end = line_start + line_duration

            nearby_regions = find_nearby_audio_regions(
                regions=regions,
                start=line_start,
                end=line_end,
            )

            vocal_reference_start = nearby_regions[0].start if nearby_regions else None
            vocal_reference_end = nearby_regions[-1].end if nearby_regions else None

            line_entries.append(
                {
                    "id": f"line-{line_number:04d}",
                    "text": lyric_line.text,
                    "start": round_time(line_start),
                    "end": round_time(line_end),
                    "confidence": "draft",
                    "locked": False,
                    "anchor": False,
                    "timing_source": "weighted_lyrics",
                    "lyric_weight": round(this_line_weight, 3),
                    "vocal_reference_start": round_time(vocal_reference_start) if vocal_reference_start is not None else None,
                    "vocal_reference_end": round_time(vocal_reference_end) if vocal_reference_end is not None else None,
                }
            )

            line_number += 1
            line_cursor = line_end

        section_entries.append(
            {
                "id": f"{slugify(section.label)}-{section_index:03d}",
                "label": section.label,
                "start": round_time(line_entries[0]["start"]),
                "end": round_time(line_entries[-1]["end"]),
                "lines": line_entries,
            }
        )

        cursor = section_end

    return {
        "schema_version": "karaoke-draft-v2",
        "created_by": "kara-creator weighted phase 1b cli",
        "source": {
            "audio_file": str(input_audio),
            "lyrics_file": str(lyrics_path),
            "audio_duration_seconds": round_time(audio_duration),
            "analysis_sample_rate": sample_rate,
        },
        "alignment": {
            "mode": timing_mode,
            "status": "draft",
            "detected_vocal_start": round_time(vocal_start),
            "detected_vocal_end": round_time(vocal_end),
            "detected_vocal_span": round_time(detected_vocal_span),
            "working_span": round_time(working_span),
            "section_count": len(lyric_sections),
            "lyric_line_count": sum(len(section.lines) for section in lyric_sections),
            "detected_audio_region_count": len(regions),
            "settings": settings,
            "region_detection_stats": region_stats,
            "calibration": {
                "used": bool(calibration_truth),
                "seconds_per_weight": round_time(calibration_rate) if calibration_rate else None,
            },
        },
        "sections": section_entries,
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
            "This draft uses lyric length and section structure to create more karaoke-like display timings.",
            "Raw vocal detections are preserved as reference regions only.",
            "Review the first section against the manual truth file before using this for a full song.",
        ],
    }


def generate_draft(args: argparse.Namespace) -> None:
    input_audio = Path(args.audio).resolve()
    lyrics_path = Path(args.lyrics).resolve()
    output_path = Path(args.out).resolve()
    calibration_path = Path(args.calibration_truth).resolve() if args.calibration_truth else None

    require_file(input_audio, "Audio file")
    require_file(lyrics_path, "Lyrics file")

    lyric_sections = parse_lyrics(lyrics_path)

    if not lyric_sections:
        raise ValueError("No lyric lines were found.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {
        "frame_ms": args.frame_ms,
        "hop_ms": args.hop_ms,
        "sensitivity": args.sensitivity,
        "min_region_ms": args.min_region_ms,
        "max_gap_ms": args.max_gap_ms,
        "pad_ms": args.pad_ms,
    }

    calibration_truth = load_calibration_truth(calibration_path)

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

    output = build_weighted_output(
        input_audio=input_audio,
        lyrics_path=lyrics_path,
        sample_rate=args.sample_rate,
        audio_duration=audio_duration,
        regions=regions,
        region_stats=region_stats,
        lyric_sections=lyric_sections,
        settings=settings,
        calibration_truth=calibration_truth,
    )

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("")
    print("Weighted karaoke draft created.")
    print(f"Output: {output_path}")
    print("")
    print(f"Sections: {output['alignment']['section_count']}")
    print(f"Lyric lines: {output['alignment']['lyric_line_count']}")
    print(f"Detected vocal regions: {output['alignment']['detected_audio_region_count']}")
    print(f"Mode: {output['alignment']['mode']}")
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a more forgiving section-based karaoke draft using lyric-weighted timing."
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
        "--calibration-truth",
        help="Optional path to a manually timed section truth JSON.",
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
        help="Detection sensitivity from 0.05 to 0.95. Default: 0.30.",
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
        print("Could not create weighted karaoke draft.")
        print(str(error))
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())