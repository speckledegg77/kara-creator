from __future__ import annotations

import argparse
import array
import json
import math
import shutil
import statistics
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


def normalise_word(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "".join(character for character in text if character.isalnum() or character == "'")


def normalised_word_texts(line: dict[str, Any]) -> list[str]:
    words = line.get("words", [])
    output: list[str] = []

    for word in words:
        cleaned = normalise_word(word.get("text"))
        if cleaned:
            output.append(cleaned)

    return output


def normalised_line_text(line: dict[str, Any]) -> str:
    return " ".join(normalised_word_texts(line))


def common_prefix_count(first: list[str], second: list[str]) -> int:
    count = 0

    for left, right in zip(first, second):
        if left != right:
            break
        count += 1

    return count


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


def word_starts(words: list[dict[str, Any]]) -> list[float]:
    return [as_float(word.get("start")) for word in words if word.get("start") is not None]


def line_last_word_end(line: dict[str, Any]) -> float:
    audio_estimated_end = line.get("audio_estimated_end")

    if audio_estimated_end is not None:
        return as_float(audio_estimated_end, as_float(line.get("last_word_start"), as_float(line.get("start"))))

    words = line.get("words", [])

    if words:
        last_word = words[-1]
        if last_word.get("end") is not None:
            return as_float(last_word.get("end"), as_float(line.get("last_word_start"), as_float(line.get("start"))))

    return as_float(line.get("last_word_start"), as_float(line.get("start")))


def next_authored_display_line(lines: list[dict[str, Any]], current_index: int) -> dict[str, Any] | None:
    for candidate in lines[current_index + 1:]:
        if candidate.get("display_type") in {"lyric", "instrumental"}:
            return candidate

    return None


def should_use_audio_line_end_for_line(
    lines: list[dict[str, Any]],
    current_index: int,
    scope: str,
) -> tuple[bool, str]:
    scope = str(scope or "before_instrumental").strip().lower()

    if scope == "all":
        return True, "scope_all"

    if scope in {"off", "none", "disabled"}:
        return False, "scope_disabled"

    next_display = next_authored_display_line(lines, current_index)

    if scope == "before_instrumental":
        if next_display and next_display.get("display_type") == "instrumental":
            return True, "next_display_line_is_instrumental"
        return False, "next_display_line_is_not_instrumental"

    if scope == "before_instrumental_or_final":
        if next_display is None:
            return True, "final_lyric_line"
        if next_display.get("display_type") == "instrumental":
            return True, "next_display_line_is_instrumental"
        return False, "next_display_line_is_not_instrumental"

    # Unknown values fall back to the safest useful mode.
    if next_display and next_display.get("display_type") == "instrumental":
        return True, "unknown_scope_defaulted_to_before_instrumental"

    return False, "unknown_scope_skipped_non_instrumental_transition"



def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0

    if len(values) == 1:
        return values[0]

    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * (percent / 100.0)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))

    if lower_index == upper_index:
        return sorted_values[lower_index]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    fraction = position - lower_index
    return lower_value + ((upper_value - lower_value) * fraction)


def resolve_audio_path(path_value: Any, word_review_path: Path) -> Path | None:
    if path_value is None:
        return None

    text = str(path_value).strip()
    if not text:
        return None

    path = Path(text)

    if path.exists():
        return path

    # If the path in the JSON is relative, try it from the word-review folder.
    relative_candidate = (word_review_path.parent / path).resolve()
    if relative_candidate.exists():
        return relative_candidate

    return path


def decode_audio_rms_frames(
    audio_path: Path,
    frame_ms: int,
    sample_rate: int = 16000,
) -> dict[str, Any]:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg was not found on PATH, so audio line-end estimation cannot run.")

    require_file(audio_path, "Audio file for line-end estimation")

    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]

    completed = subprocess.run(command, capture_output=True)

    if completed.returncode != 0:
        error_text = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg could not decode the audio file. {error_text}")

    raw_audio = completed.stdout
    bytes_per_sample = 2
    frame_sample_count = max(1, int(sample_rate * (frame_ms / 1000.0)))
    frame_byte_count = frame_sample_count * bytes_per_sample
    rms_values: list[float] = []

    for start in range(0, len(raw_audio), frame_byte_count):
        frame = raw_audio[start:start + frame_byte_count]

        if len(frame) < bytes_per_sample:
            continue

        if len(frame) % bytes_per_sample:
            frame = frame[:-1]

        samples = array.array("h")
        samples.frombytes(frame)

        if sys.byteorder != "little":
            samples.byteswap()

        if not samples:
            continue

        # Normalise to approximately 0.0 to 1.0.
        square_sum = 0.0
        for sample in samples:
            square_sum += float(sample) * float(sample)

        rms = math.sqrt(square_sum / len(samples)) / 32768.0
        rms_values.append(rms)

    if not rms_values:
        raise RuntimeError("No audio samples were decoded for line-end estimation.")

    smoothed: list[float] = []
    smoothing_radius = 2

    for index in range(len(rms_values)):
        left = max(0, index - smoothing_radius)
        right = min(len(rms_values), index + smoothing_radius + 1)
        smoothed.append(sum(rms_values[left:right]) / (right - left))

    duration_seconds = (len(raw_audio) / bytes_per_sample) / sample_rate
    non_zero_values = [value for value in smoothed if value > 0]
    noise_floor = percentile(non_zero_values, 20) if non_zero_values else 0.0

    return {
        "audio_path": str(audio_path),
        "frame_ms": frame_ms,
        "sample_rate": sample_rate,
        "duration_seconds": duration_seconds,
        "rms": smoothed,
        "noise_floor": noise_floor,
    }


def frame_index_for_time(audio_analysis: dict[str, Any], seconds: float) -> int:
    frame_ms = int(audio_analysis.get("frame_ms", 20))
    frame_count = len(audio_analysis.get("rms", []))
    index = int(max(0.0, seconds) / (frame_ms / 1000.0))
    return max(0, min(frame_count - 1, index)) if frame_count else 0


def time_for_frame_index(audio_analysis: dict[str, Any], index: int) -> float:
    frame_ms = int(audio_analysis.get("frame_ms", 20))
    return max(0.0, index * (frame_ms / 1000.0))


def estimate_line_vocal_offset(
    line: dict[str, Any],
    next_lyric_line: dict[str, Any] | None,
    audio_analysis: dict[str, Any],
    min_after_last_word_seconds: float,
    max_search_seconds: float,
    sustain_seconds: float,
    relative_threshold: float,
    noise_floor_multiplier: float,
    next_lyric_safety_gap_seconds: float,
) -> tuple[float | None, str, dict[str, Any]]:
    rms_values: list[float] = audio_analysis.get("rms", [])
    if not rms_values:
        return None, "no_audio_rms_values", {}

    line_start = as_float(line.get("start"))
    last_word_start = as_float(line.get("last_word_start"), as_float(line.get("word_start"), line_start))
    audio_duration_seconds = as_float(audio_analysis.get("duration_seconds"), last_word_start + max_search_seconds)

    if next_lyric_line and next_lyric_line.get("start") is not None:
        boundary_end = as_float(next_lyric_line.get("start")) - next_lyric_safety_gap_seconds
    else:
        boundary_end = min(audio_duration_seconds, last_word_start + max_search_seconds)

    search_start = last_word_start + min_after_last_word_seconds
    search_end = min(boundary_end, last_word_start + max_search_seconds, audio_duration_seconds)

    diagnostics = {
        "line_start": round_time(line_start),
        "last_word_start": round_time(last_word_start),
        "search_start": round_time(search_start),
        "search_end": round_time(search_end),
    }

    if search_end <= search_start + sustain_seconds:
        return None, "search_window_too_short", diagnostics

    frame_ms = int(audio_analysis.get("frame_ms", 20))
    sustain_frames = max(1, int(math.ceil(sustain_seconds / (frame_ms / 1000.0))))
    start_index = frame_index_for_time(audio_analysis, search_start)
    end_index = frame_index_for_time(audio_analysis, search_end)

    local_peak_start = frame_index_for_time(audio_analysis, max(line_start, last_word_start - 0.4))
    local_peak_end = frame_index_for_time(audio_analysis, min(search_start + 1.5, search_end))
    local_values = rms_values[local_peak_start:max(local_peak_start + 1, local_peak_end + 1)]
    local_peak = percentile(local_values, 95) if local_values else 0.0
    noise_floor = as_float(audio_analysis.get("noise_floor"), 0.0)
    threshold = max(noise_floor * noise_floor_multiplier, local_peak * relative_threshold)

    diagnostics.update(
        {
            "local_peak": round(local_peak, 6),
            "noise_floor": round(noise_floor, 6),
            "threshold": round(threshold, 6),
            "sustain_seconds": sustain_seconds,
            "sustain_frames": sustain_frames,
        }
    )

    if local_peak <= 0.00001:
        return None, "local_peak_too_low", diagnostics

    for index in range(start_index, max(start_index, end_index - sustain_frames + 1)):
        window = rms_values[index:index + sustain_frames]

        if len(window) < sustain_frames:
            break

        below_count = sum(1 for value in window if value <= threshold)
        mean_value = sum(window) / len(window)

        if below_count / len(window) >= 0.8 and mean_value <= threshold * 1.15:
            estimated_end = max(last_word_start + min_after_last_word_seconds, time_for_frame_index(audio_analysis, index))
            diagnostics["detected_frame_index"] = index
            diagnostics["detected_window_mean"] = round(mean_value, 6)
            diagnostics["detected_below_threshold_fraction"] = round(below_count / len(window), 3)
            return estimated_end, "audio-vocal-offset", diagnostics

    return None, "no_sustained_drop_detected", diagnostics


def apply_audio_line_end_estimates(
    lines: list[dict[str, Any]],
    word_review: dict[str, Any],
    word_review_path: Path,
    enabled: bool,
    scope: str,
    frame_ms: int,
    min_after_last_word_seconds: float,
    max_search_seconds: float,
    sustain_seconds: float,
    relative_threshold: float,
    noise_floor_multiplier: float,
    next_lyric_safety_gap_seconds: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "enabled": enabled,
        "status": "disabled" if not enabled else "not_started",
        "estimated_line_end_count": 0,
        "fallback_line_end_count": 0,
        "skipped_line_end_count": 0,
        "error": None,
    }

    if not enabled:
        return result

    audio_path = resolve_audio_path(word_review.get("source", {}).get("audio_file"), word_review_path)

    if audio_path is None:
        result["status"] = "no_audio_path_in_word_review"
        result["error"] = "Word review JSON does not contain source.audio_file."
        return result

    try:
        audio_analysis = decode_audio_rms_frames(audio_path=audio_path, frame_ms=frame_ms)
    except Exception as error:
        result["status"] = "audio_analysis_failed_falling_back_to_inferred_ends"
        result["error"] = str(error)
        return result

    estimated_count = 0
    fallback_count = 0
    skipped_count = 0

    for index, line in enumerate(lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        should_estimate, scope_reason = should_use_audio_line_end_for_line(
            lines=lines,
            current_index=index,
            scope=scope,
        )

        if not should_estimate:
            line["line_end_source"] = "inferred-from-next-display-line"
            line["line_end_confidence"] = "fallback"
            line["line_end_diagnostics"] = {
                "audio_line_end_status": "skipped_by_scope",
                "audio_line_end_scope": scope,
                "audio_line_end_scope_reason": scope_reason,
            }
            skipped_count += 1
            continue

        next_lyric = next_lyric_line(lines, index)
        estimated_end, source, diagnostics = estimate_line_vocal_offset(
            line=line,
            next_lyric_line=next_lyric,
            audio_analysis=audio_analysis,
            min_after_last_word_seconds=min_after_last_word_seconds,
            max_search_seconds=max_search_seconds,
            sustain_seconds=sustain_seconds,
            relative_threshold=relative_threshold,
            noise_floor_multiplier=noise_floor_multiplier,
            next_lyric_safety_gap_seconds=next_lyric_safety_gap_seconds,
        )

        line["line_end_diagnostics"] = diagnostics

        if estimated_end is None:
            line["line_end_source"] = "inferred-from-next-display-line"
            line["line_end_confidence"] = "fallback"
            line["line_end_diagnostics"]["audio_line_end_status"] = source
            add_flags(line, ["audio_line_end_estimation_fallback_needs_review"])
            fallback_count += 1
            continue

        line_start = as_float(line.get("start"))
        estimated_end = max(line_start + 0.1, estimated_end)
        next_lyric = next_lyric_line(lines, index)

        if next_lyric and next_lyric.get("start") is not None:
            latest_allowed = as_float(next_lyric.get("start")) - next_lyric_safety_gap_seconds
            if estimated_end > latest_allowed:
                estimated_end = max(line_start + 0.1, latest_allowed)
                add_flags(line, ["audio_estimated_line_end_clamped_to_next_lyric_needs_review"])

        line["audio_estimated_end"] = round_time(estimated_end)
        line["line_end_source"] = source
        line["line_end_confidence"] = "medium"
        line["line_end_diagnostics"]["audio_line_end_status"] = "estimated"

        words = line.get("words", [])
        if words:
            words[-1]["end"] = round_time(max(as_float(words[-1].get("start")), estimated_end))
            words[-1]["end_source"] = "audio-vocal-offset"

        estimated_count += 1

    result.update(
        {
            "status": "ok",
            "audio_path": str(audio_path),
            "frame_ms": frame_ms,
            "sample_rate": audio_analysis.get("sample_rate"),
            "audio_duration_seconds": round_time(as_float(audio_analysis.get("duration_seconds"))),
            "noise_floor": round(as_float(audio_analysis.get("noise_floor")), 6),
            "estimated_line_end_count": estimated_count,
            "fallback_line_end_count": fallback_count,
            "skipped_line_end_count": skipped_count,
            "settings": {
                "scope": scope,
                "min_after_last_word_seconds": min_after_last_word_seconds,
                "max_search_seconds": max_search_seconds,
                "sustain_seconds": sustain_seconds,
                "relative_threshold": relative_threshold,
                "noise_floor_multiplier": noise_floor_multiplier,
                "next_lyric_safety_gap_seconds": next_lyric_safety_gap_seconds,
            },
        }
    )
    return result


def calculate_gap_diagnostics(words: list[dict[str, Any]]) -> dict[str, float]:
    starts = word_starts(words)

    if len(starts) < 2:
        return {
            "first_internal_word_gap": 0.0,
            "max_internal_word_gap": 0.0,
            "later_internal_word_gap_typical": 0.0,
        }

    gaps = [max(0.0, starts[index + 1] - starts[index]) for index in range(len(starts) - 1)]
    first_gap = gaps[0]
    max_gap = max(gaps)
    later_gaps = gaps[1:]
    later_typical = statistics.median(later_gaps) if later_gaps else 0.0

    return {
        "first_internal_word_gap": round_time(first_gap),
        "max_internal_word_gap": round_time(max_gap),
        "later_internal_word_gap_typical": round_time(later_typical),
    }


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


def next_display_line_with_timing(lines: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for index in range(start_index + 1, len(lines)):
        candidate = lines[index]

        if candidate.get("start") is not None:
            return candidate

    return None


def previous_display_line_with_timing(lines: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for index in range(start_index - 1, -1, -1):
        candidate = lines[index]

        if candidate.get("start") is not None:
            return candidate

    return None


DERIVED_REVIEW_FLAGS = {
    "large_internal_word_gap_needs_review",
    "long_tail_after_last_word_needs_review",
    "very_short_display_duration_needs_review",
    "line_start_before_previous_line",
}


def add_flags(line: dict[str, Any], flags: list[str]) -> None:
    line["review_flags"] = sorted(set(list(line.get("review_flags", [])) + flags))


def should_auto_correct_first_word(
    line: dict[str, Any],
    previous_line: dict[str, Any] | None,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
    auto_anchor_min_words: int,
    long_tail_threshold_seconds: float,
) -> tuple[bool, bool]:
    """Return (should_correct, previous_line_suggests_held_tail)."""
    words = line.get("words", [])

    if len(words) <= auto_anchor_min_words:
        return False, False

    diagnostics = line.get("anchor_diagnostics", {})
    first_gap = as_float(diagnostics.get("first_internal_word_gap"))
    later_typical = as_float(diagnostics.get("later_internal_word_gap_typical"))

    if first_gap < suspicious_first_word_gap_seconds:
        return False, False

    if later_typical > 0 and first_gap < later_typical * first_gap_ratio_threshold:
        return False, False

    previous_line_suggests_held_tail = False

    if previous_line:
        previous_last_word_start = as_float(previous_line.get("last_word_start"), as_float(previous_line.get("start")))
        raw_start = as_float(line.get("word_start"), as_float(line.get("start")))
        previous_to_current_gap = raw_start - previous_last_word_start
        previous_line_suggests_held_tail = previous_to_current_gap >= long_tail_threshold_seconds

    return True, previous_line_suggests_held_tail


def apply_cautious_first_word_corrections(
    lines: list[dict[str, Any]],
    auto_correct_suspicious_first_word: bool,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
    auto_anchor_lead_in_min_seconds: float,
    auto_anchor_lead_in_max_seconds: float,
    auto_anchor_lead_in_extended_max_seconds: float,
    auto_anchor_lead_in_gap_fraction: float,
    auto_anchor_min_words: int,
    long_tail_threshold_seconds: float,
    start_padding_seconds: float,
) -> int:
    adjusted_count = 0

    for index, line in enumerate(lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        words = line.get("words", [])
        if len(words) < 2:
            continue

        first_gap = as_float(line.get("first_internal_word_gap"))
        if first_gap >= suspicious_first_word_gap_seconds:
            add_flags(line, ["first_word_anchor_suspect"])

        previous_line = previous_lyric_line(lines, index)
        should_correct, previous_line_suggests_held_tail = should_auto_correct_first_word(
            line=line,
            previous_line=previous_line,
            suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
            first_gap_ratio_threshold=first_gap_ratio_threshold,
            auto_anchor_min_words=auto_anchor_min_words,
            long_tail_threshold_seconds=long_tail_threshold_seconds,
        )

        if not auto_correct_suspicious_first_word or not should_correct:
            continue

        second_word_start = as_float(words[1].get("start"))
        lead_in_max = auto_anchor_lead_in_extended_max_seconds if previous_line_suggests_held_tail else auto_anchor_lead_in_max_seconds
        lead_in = min(
            lead_in_max,
            max(auto_anchor_lead_in_min_seconds, first_gap * auto_anchor_lead_in_gap_fraction),
        )
        corrected_start = max(0.0, second_word_start - lead_in)
        uncorrected_start = as_float(line.get("start"))

        if corrected_start <= uncorrected_start + start_padding_seconds:
            continue

        line["start"] = round_time(corrected_start)
        line["line_anchor_start"] = round_time(corrected_start)
        line["line_anchor_source"] = "corrected-word-cluster"
        line["timing_source"] = "lyrics-aligner-corrected-word-cluster"
        line["anchor_diagnostics"]["auto_anchor_lead_in_seconds"] = round_time(lead_in)
        line["anchor_diagnostics"]["uncorrected_display_start"] = round_time(uncorrected_start)
        line["anchor_diagnostics"]["auto_corrected_display_start"] = round_time(corrected_start)
        line["anchor_diagnostics"]["auto_anchor_reason"] = (
            "held_previous_line_and_suspicious_first_word"
            if previous_line_suggests_held_tail
            else "suspicious_first_word"
        )
        add_flags(line, ["line_start_auto_adjusted_needs_review"])
        adjusted_count += 1

    return adjusted_count


def apply_instrumental_following_anchor_rescue(
    lines: list[dict[str, Any]],
    enabled: bool,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
    auto_anchor_lead_in_min_seconds: float,
    auto_anchor_lead_in_max_seconds: float,
    auto_anchor_lead_in_gap_fraction: float,
    start_padding_seconds: float,
) -> int:
    """Move a lyric line later when it follows an explicit instrumental marker and word 1 looks too early.

    This is deliberately narrower than the general first-word correction. A manually placed
    instrumental line is a strong hint that there should be a real gap before the next lyric line.
    If the aligner places word 1 early but the rest of the line starts much later, the instrumental
    would otherwise be squeezed into a tiny display duration.
    """
    if not enabled:
        return 0

    rescued_count = 0

    for index, line in enumerate(lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        previous_index = index - 1
        follows_instrumental = False

        while previous_index >= 0:
            previous_line = lines[previous_index]
            if previous_line.get("display_type") == "instrumental":
                follows_instrumental = True
                previous_index -= 1
                continue
            break

        if not follows_instrumental:
            continue

        words = line.get("words", [])
        if len(words) < 2:
            add_flags(line, ["instrumental_before_single_word_line_needs_review"])
            continue

        diagnostics = line.get("anchor_diagnostics", {})
        first_gap = as_float(diagnostics.get("first_internal_word_gap"))
        later_typical = as_float(diagnostics.get("later_internal_word_gap_typical"))

        if first_gap < suspicious_first_word_gap_seconds:
            continue

        if later_typical > 0 and first_gap < later_typical * first_gap_ratio_threshold:
            continue

        second_word_start = as_float(words[1].get("start"))
        lead_in = min(
            auto_anchor_lead_in_max_seconds,
            max(auto_anchor_lead_in_min_seconds, first_gap * auto_anchor_lead_in_gap_fraction),
        )
        corrected_start = max(0.0, second_word_start - lead_in)
        uncorrected_start = as_float(line.get("start"))

        if corrected_start <= uncorrected_start + max(0.5, start_padding_seconds):
            continue

        line["start"] = round_time(corrected_start)
        line["line_anchor_start"] = round_time(corrected_start)
        line["line_anchor_source"] = "instrumental-following-line-anchor-rescue"
        line["timing_source"] = "kara-creator-instrumental-following-line-anchor-rescue"
        line.setdefault("anchor_diagnostics", {})["instrumental_following_uncorrected_display_start"] = round_time(uncorrected_start)
        line["anchor_diagnostics"]["instrumental_following_rescued_display_start"] = round_time(corrected_start)
        line["anchor_diagnostics"]["instrumental_following_rescue_lead_in_seconds"] = round_time(lead_in)
        line["anchor_diagnostics"]["instrumental_following_rescue_reason"] = "explicit_instrumental_before_suspicious_first_word"
        add_flags(line, ["instrumental_following_line_start_auto_adjusted_needs_review"])
        rescued_count += 1

    return rescued_count


def first_word_looks_like_early_outlier(
    line: dict[str, Any],
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
) -> bool:
    diagnostics = line.get("anchor_diagnostics", {})
    first_gap = as_float(diagnostics.get("first_internal_word_gap"))
    later_typical = as_float(diagnostics.get("later_internal_word_gap_typical"))

    if first_gap < suspicious_first_word_gap_seconds:
        return False

    if later_typical <= 0:
        return False

    return first_gap >= later_typical * first_gap_ratio_threshold


def has_explicit_instrumental_since_previous_lyric(lines: list[dict[str, Any]], current_index: int) -> bool:
    """Return True when an explicit instrumental placeholder sits between the previous lyric and this lyric."""
    probe_index = current_index - 1

    while probe_index >= 0:
        candidate = lines[probe_index]

        if candidate.get("display_type") == "instrumental":
            return True

        if candidate.get("display_type") == "lyric":
            return False

        probe_index -= 1

    return False


def estimate_display_step_after_line(line: dict[str, Any]) -> float:
    word_count = max(1, len(line.get("words", [])))
    return min(2.5, max(1.2, (word_count * 0.35) + 0.2))


def apply_late_next_line_anchor_rescue(
    lines: list[dict[str, Any]],
    enabled: bool,
    late_next_line_gap_seconds: float,
    late_next_line_after_previous_word_seconds: float,
    late_anchor_cascade_gap_seconds: float,
    suspicious_first_word_gap_seconds: float,
    first_gap_ratio_threshold: float,
) -> int:
    """Move a lyric line earlier when the next line's first word appears too late.

    This targets a different failure from first-word early-outlier correction.
    Example: a clean line ends on a word such as "specialism", then the next
    line's first aligned word, such as "Clear", arrives several seconds too
    late. In that case the previous lyric stays on screen too long and the
    next line is missed.

    The rule deliberately skips cases where word 1 looks like an early outlier,
    because those are better handled by the cautious first-word correction.
    """
    if not enabled:
        return 0

    rescued_count = 0

    for index, line in enumerate(lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        if has_explicit_instrumental_since_previous_lyric(lines, index):
            add_flags(line, ["late_anchor_rescue_skipped_after_instrumental_placeholder"])
            continue

        previous_line = previous_lyric_line(lines, index)
        if not previous_line or previous_line.get("start") is None:
            continue

        if first_word_looks_like_early_outlier(
            line=line,
            suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
            first_gap_ratio_threshold=first_gap_ratio_threshold,
        ):
            continue

        current_start = as_float(line.get("start"))
        current_word_start = as_float(line.get("word_start"), current_start)
        current_max_gap = as_float(line.get("max_internal_word_gap"))
        previous_start = as_float(previous_line.get("start"))
        previous_last_word_start = as_float(previous_line.get("last_word_start"), previous_start)
        previous_max_gap = as_float(previous_line.get("max_internal_word_gap"))
        gap_from_previous_last_word = current_word_start - previous_last_word_start
        previous_source = str(previous_line.get("line_anchor_source", ""))

        proposed_start: float | None = None
        reason = ""

        previous_line_is_clean_enough = previous_max_gap < suspicious_first_word_gap_seconds

        if (
            previous_line_is_clean_enough
            and current_max_gap >= suspicious_first_word_gap_seconds
            and gap_from_previous_last_word >= late_next_line_gap_seconds
        ):
            proposed_start = max(
                previous_start + 0.75,
                previous_last_word_start + late_next_line_after_previous_word_seconds,
            )
            reason = "clean_previous_line_then_late_suspicious_next_line"

            # Keep this rescue narrow. In fast or expressive sections, a larger
            # move often means the aligner has found a real held/split phrase,
            # not a missing line start. Those cases are better reviewed manually
            # than auto-pulled several seconds early.
            if current_start - proposed_start > 2.5:
                add_flags(line, ["late_anchor_rescue_skipped_large_shift_needs_review"])
                continue

        elif False:
            # The previous cascade rule helped one tuned example, but it damaged
            # fresh material by pulling a whole run of lines too early. Keep it
            # disabled until there is stronger evidence for a safer cascade rule.
            proposed_start = previous_start + estimate_display_step_after_line(previous_line)
            reason = "cascade_after_late_anchor_rescue"

        if proposed_start is None:
            continue

        if proposed_start >= current_start - 0.5:
            continue

        line["start"] = round_time(proposed_start)
        line["line_anchor_start"] = round_time(proposed_start)
        line["line_anchor_source"] = "late-anchor-cascade-rescue" if "cascade" in reason else "late-next-line-anchor-rescue"
        line["timing_source"] = "kara-creator-late-next-line-anchor-rescue"
        line.setdefault("anchor_diagnostics", {})["late_anchor_uncorrected_display_start"] = round_time(current_start)
        line["anchor_diagnostics"]["late_anchor_rescued_display_start"] = round_time(proposed_start)
        line["anchor_diagnostics"]["late_anchor_gap_from_previous_last_word"] = round_time(gap_from_previous_last_word)
        line["anchor_diagnostics"]["late_anchor_reason"] = reason
        add_flags(line, ["late_next_line_anchor_rescue_applied_needs_review"])
        rescued_count += 1

    return rescued_count



def apply_repeated_final_word_rescue(
    lines: list[dict[str, Any]],
    enabled: bool,
    repeated_final_word_min_span_seconds: float,
    repeated_final_word_collapse_window_seconds: float,
    repeated_final_word_start_fraction: float,
    repeated_final_word_spacing_seconds: float,
) -> int:
    """Spread repeated one-word display lines across a long held final word.

    This targets a different pattern from repeated-line rescue.
    Example:

        Then the future can begin today
        Today
        Today

    When the first "today" is held for a long time, the aligner can collapse
    all the repeated Today word starts onto the end of the phrase. The karaoke
    display needs those repeated one-word lines spread earlier across the held
    phrase.
    """
    if not enabled:
        return 0

    rescued_count = 0
    index = 0

    while index < len(lines) - 1:
        base_line = lines[index]

        if base_line.get("display_type") != "lyric" or base_line.get("start") is None:
            index += 1
            continue

        base_words = normalised_word_texts(base_line)
        if len(base_words) < 2:
            index += 1
            continue

        final_word = base_words[-1]
        if not final_word:
            index += 1
            continue

        run_indexes: list[int] = []
        probe_index = index + 1

        while probe_index < len(lines):
            candidate = lines[probe_index]

            if candidate.get("display_type") != "lyric" or candidate.get("start") is None:
                break

            candidate_words = normalised_word_texts(candidate)
            if candidate_words != [final_word]:
                break

            run_indexes.append(probe_index)
            probe_index += 1

        if not run_indexes:
            index += 1
            continue

        base_start = as_float(base_line.get("start"))
        base_last_word_start = as_float(base_line.get("last_word_start"), as_float(base_line.get("word_start"), base_start))
        held_span = base_last_word_start - base_start

        if held_span < repeated_final_word_min_span_seconds:
            index += 1
            continue

        # The collapse signal is that the repeated one-word lines' anchors are
        # very close to the base line's final-word anchor. If they are already
        # naturally spread out, do not move them.
        collapse_detected = False
        for run_index in run_indexes:
            candidate = lines[run_index]
            candidate_word_start = as_float(candidate.get("word_start"), as_float(candidate.get("start")))
            if abs(candidate_word_start - base_last_word_start) <= repeated_final_word_collapse_window_seconds:
                collapse_detected = True
                break

        if not collapse_detected:
            index += 1
            continue

        first_rescue_start = base_start + (held_span * repeated_final_word_start_fraction)
        first_rescue_start = max(base_start + 1.0, first_rescue_start)
        latest_start_for_last_repeat = max(base_start + 1.0, base_last_word_start - 1.0)

        for offset, run_index in enumerate(run_indexes):
            candidate = lines[run_index]
            current_start = as_float(candidate.get("start"))
            proposed_start = first_rescue_start + (offset * repeated_final_word_spacing_seconds)

            # Keep the final repeated display line before the aligner's collapsed
            # final-word anchor, leaving room for the display to move on.
            remaining_after_this = len(run_indexes) - offset - 1
            proposed_start = min(
                proposed_start,
                latest_start_for_last_repeat - (remaining_after_this * 1.0),
            )
            proposed_start = max(base_start + 0.75, proposed_start)

            if proposed_start >= current_start - 0.25:
                continue

            candidate["start"] = round_time(proposed_start)
            candidate["line_anchor_start"] = round_time(proposed_start)
            candidate["line_anchor_source"] = "repeated-final-word-rescue"
            candidate["timing_source"] = "kara-creator-repeated-final-word-rescue"
            candidate.setdefault("anchor_diagnostics", {})["repeated_final_word_uncorrected_display_start"] = round_time(current_start)
            candidate["anchor_diagnostics"]["repeated_final_word_rescued_display_start"] = round_time(proposed_start)
            candidate["anchor_diagnostics"]["repeated_final_word_base_line_id"] = base_line.get("id")
            candidate["anchor_diagnostics"]["repeated_final_word_held_span_seconds"] = round_time(held_span)
            candidate["anchor_diagnostics"]["repeated_final_word"] = final_word
            add_flags(candidate, ["repeated_final_word_line_start_auto_adjusted_needs_review"])
            rescued_count += 1

        if rescued_count:
            add_flags(base_line, ["repeated_final_word_run_needs_review"])

        index = run_indexes[-1] + 1

    return rescued_count



def apply_monotonic_lyric_start_guard(
    lines: list[dict[str, Any]],
    next_line_gap_seconds: float,
) -> int:
    """Prevent a lyric display line from starting before the previous lyric's final word anchor.

    Line starts include a small lead-in before the first word. That is usually helpful,
    but when adjacent word anchors are very close it can make the next display line
    appear before the previous line's final word has even started. This guard only
    makes the minimum adjustment needed to preserve word order. It does not cross
    explicit instrumental placeholders, because those are authored display breaks.
    """
    adjusted_count = 0

    for index, line in enumerate(lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        if has_explicit_instrumental_since_previous_lyric(lines, index):
            continue

        previous_line = previous_lyric_line(lines, index)
        if not previous_line or previous_line.get("start") is None:
            continue

        previous_last_word_start = as_float(
            previous_line.get("last_word_start"),
            as_float(previous_line.get("word_start"), as_float(previous_line.get("start"))),
        )
        current_start = as_float(line.get("start"))
        minimum_start = previous_last_word_start + next_line_gap_seconds + 0.02

        if current_start >= minimum_start:
            continue

        line["start"] = round_time(minimum_start)
        line["line_anchor_start"] = round_time(minimum_start)
        line.setdefault("anchor_diagnostics", {})["monotonic_guard_original_start"] = round_time(current_start)
        line["anchor_diagnostics"]["monotonic_guard_adjusted_start"] = round_time(minimum_start)
        add_flags(line, ["line_start_shifted_to_preserve_word_order_needs_review"])
        adjusted_count += 1

    return adjusted_count

def apply_repeated_phrase_rescue(
    lines: list[dict[str, Any]],
    enabled: bool,
    repeated_phrase_min_gap_seconds: float,
    repeated_phrase_after_previous_word_seconds: float,
    repeated_phrase_min_common_prefix_words: int,
    audio_duration_seconds: float | None,
) -> int:
    if not enabled:
        return 0

    rescued_count = 0

    # Rescue a line that begins like the previous line but whose anchors arrive implausibly late.
    for index in range(1, len(lines)):
        current = lines[index]
        previous = previous_lyric_line(lines, index)

        if not previous or current.get("display_type") != "lyric" or current.get("start") is None:
            continue

        current_words = normalised_word_texts(current)
        previous_words = normalised_word_texts(previous)
        if not current_words or not previous_words:
            continue

        prefix_count = common_prefix_count(previous_words, current_words)
        identical = normalised_line_text(previous) == normalised_line_text(current)

        if not identical and prefix_count < repeated_phrase_min_common_prefix_words:
            continue

        previous_last_word_start = as_float(previous.get("last_word_start"), as_float(previous.get("start")))
        current_word_start = as_float(current.get("word_start"), as_float(current.get("start")))
        previous_to_current_gap = current_word_start - previous_last_word_start
        current_max_gap = as_float(current.get("max_internal_word_gap"))

        if previous_to_current_gap < repeated_phrase_min_gap_seconds and current_max_gap < repeated_phrase_min_gap_seconds:
            continue

        proposed_start = previous_last_word_start + repeated_phrase_after_previous_word_seconds
        previous_start = as_float(previous.get("start"))
        current_start = as_float(current.get("start"))
        proposed_start = max(previous_start + 0.75, proposed_start)

        if proposed_start >= current_start - 0.5:
            continue

        current["start"] = round_time(proposed_start)
        current["line_anchor_start"] = round_time(proposed_start)
        current["line_anchor_source"] = "repeated-phrase-rescue"
        current["timing_source"] = "kara-creator-repeated-phrase-rescue"
        current.setdefault("anchor_diagnostics", {})["repeated_phrase_uncorrected_display_start"] = round_time(current_start)
        current["anchor_diagnostics"]["repeated_phrase_rescued_display_start"] = round_time(proposed_start)
        current["anchor_diagnostics"]["repeated_phrase_reason"] = "shared_opening_phrase_after_long_gap"
        add_flags(current, ["repeated_phrase_line_start_auto_adjusted_needs_review"])
        rescued_count += 1

    # Rescue later lines in a run of identical repeated lines by spreading them across the remaining phrase.
    index = 0
    while index < len(lines):
        line = lines[index]

        if line.get("display_type") != "lyric" or line.get("start") is None:
            index += 1
            continue

        line_key = normalised_line_text(line)
        if not line_key:
            index += 1
            continue

        run_indexes = [index]
        next_index = index + 1

        while next_index < len(lines):
            candidate = lines[next_index]
            if candidate.get("display_type") != "lyric" or candidate.get("start") is None:
                break
            if normalised_line_text(candidate) != line_key:
                break
            run_indexes.append(next_index)
            next_index += 1

        if len(run_indexes) < 2:
            index += 1
            continue

        first_line = lines[run_indexes[0]]
        boundary_line = next_lyric_line(lines, run_indexes[-1])
        boundary_end = as_float(boundary_line.get("start")) if boundary_line else None

        if boundary_end is None:
            boundary_end = audio_duration_seconds

        if boundary_end is None or boundary_end <= as_float(first_line.get("start")):
            index = run_indexes[-1] + 1
            continue

        first_start = as_float(first_line.get("start"))
        segment = (boundary_end - first_start) / len(run_indexes)

        if segment < 1.5:
            index = run_indexes[-1] + 1
            continue

        for offset, line_index in enumerate(run_indexes[1:], start=1):
            candidate = lines[line_index]
            current_start = as_float(candidate.get("start"))
            proposed_start = first_start + (segment * offset)

            if proposed_start >= current_start - 0.5:
                continue

            candidate["start"] = round_time(proposed_start)
            candidate["line_anchor_start"] = round_time(proposed_start)
            candidate["line_anchor_source"] = "repeated-identical-line-rescue"
            candidate["timing_source"] = "kara-creator-repeated-identical-line-rescue"
            candidate.setdefault("anchor_diagnostics", {})["repeated_line_uncorrected_display_start"] = round_time(current_start)
            candidate["anchor_diagnostics"]["repeated_line_rescued_display_start"] = round_time(proposed_start)
            candidate["anchor_diagnostics"]["repeated_line_phrase_boundary_end"] = round_time(boundary_end)
            add_flags(candidate, ["repeated_identical_line_start_auto_adjusted_needs_review"])
            rescued_count += 1

        index = run_indexes[-1] + 1

    return rescued_count


def assign_instrumental_run(
    lines: list[dict[str, Any]],
    run_indexes: list[int],
    next_line_gap_seconds: float,
    instrumental_fallback_seconds: float,
    audio_duration_seconds: float | None,
    instrumental_after_previous_word_seconds: float,
    instrumental_before_next_line_seconds: float,
    starting_instrumental_before_first_line_seconds: float,
    lyric_before_instrumental_min_hold_seconds: float,
) -> None:
    if not run_indexes:
        return

    first_index = run_indexes[0]
    last_index = run_indexes[-1]
    previous_line = previous_lyric_line(lines, first_index)
    following_line = next_lyric_line(lines, last_index)
    count = len(run_indexes)
    min_each = 0.5
    preferred_each = 3.0
    total_minimum = count * min_each
    preferred_minimum = count * preferred_each
    flags_for_all = ["instrumental_timing_needs_review"]

    if previous_line and following_line:
        following_start = as_float(following_line.get("start"))
        previous_start = as_float(previous_line.get("start"))
        previous_last_word_start = as_float(previous_line.get("last_word_start"), previous_start)
        previous_last_word_end = line_last_word_end(previous_line)
        previous_has_audio_end = previous_line.get("line_end_source") == "audio-vocal-offset"

        if previous_has_audio_end:
            previous_minimum_held_gap_start = previous_last_word_end + next_line_gap_seconds
            gap_start = max(previous_start + 0.75, previous_minimum_held_gap_start)
        else:
            previous_minimum_held_line_end = max(
                previous_last_word_end,
                previous_last_word_start + lyric_before_instrumental_min_hold_seconds,
            )
            previous_minimum_held_gap_start = previous_minimum_held_line_end + next_line_gap_seconds

            gap_start = max(
                previous_start + 0.75,
                previous_last_word_end + instrumental_after_previous_word_seconds,
                previous_minimum_held_gap_start,
            )
        gap_end = following_start - instrumental_before_next_line_seconds
        desired_minimum = max(total_minimum, instrumental_fallback_seconds * count)

        # If an explicit . . . line has been authored, avoid flashing it for a
        # fraction of a second when the following lyric has suspicious internal
        # word gaps. In that situation the following anchor is often unreliable,
        # so move it just enough to give the instrumental a readable display.
        following_max_gap = as_float(following_line.get("max_internal_word_gap"))
        following_first_gap = as_float(following_line.get("first_internal_word_gap"))
        readable_gap_start = max(previous_start + 0.75, previous_last_word_end + 0.25, previous_minimum_held_gap_start)
        readable_gap_end = gap_end
        if (
            readable_gap_end - readable_gap_start < preferred_minimum
            and max(following_max_gap, following_first_gap) >= 3.0
        ):
            corrected_following_start = readable_gap_start + preferred_minimum + instrumental_before_next_line_seconds
            if corrected_following_start > following_start + 0.25:
                following_line["start"] = round_time(corrected_following_start)
                following_line["line_anchor_start"] = round_time(corrected_following_start)
                following_line["line_anchor_source"] = "instrumental-minimum-gap-rescue"
                following_line["timing_source"] = "kara-creator-instrumental-minimum-gap-rescue"
                following_line.setdefault("anchor_diagnostics", {})["instrumental_minimum_gap_original_start"] = round_time(following_start)
                following_line["anchor_diagnostics"]["instrumental_minimum_gap_rescued_start"] = round_time(corrected_following_start)
                following_line["anchor_diagnostics"]["instrumental_minimum_gap_seconds"] = round_time(preferred_minimum)
                add_flags(following_line, ["instrumental_following_line_delayed_for_minimum_gap_needs_review"])
                following_start = corrected_following_start
                gap_end = following_start - instrumental_before_next_line_seconds
                flags_for_all.append("instrumental_minimum_gap_rescue_applied_needs_review")

        following_index = None
        for candidate_index, candidate in enumerate(lines):
            if candidate is following_line:
                following_index = candidate_index
                break

        following_is_last_lyric = following_index is not None and next_lyric_line(lines, following_index) is None
        has_audio_room_for_late_final_line = (
            audio_duration_seconds is not None
            and audio_duration_seconds > gap_start + desired_minimum + 0.75
        )

        if gap_end - gap_start < desired_minimum and following_is_last_lyric and has_audio_room_for_late_final_line:
            corrected_following_start = min(
                gap_start + desired_minimum + instrumental_before_next_line_seconds,
                max(gap_start + total_minimum + instrumental_before_next_line_seconds, audio_duration_seconds - 1.0),
            )

            if corrected_following_start > following_start:
                following_line["start"] = round_time(corrected_following_start)
                following_line["line_anchor_start"] = round_time(corrected_following_start)
                following_line["line_anchor_source"] = "final-instrumental-gap-rescue"
                following_line["timing_source"] = "kara-creator-final-instrumental-gap-rescue"
                following_line.setdefault("anchor_diagnostics", {})["final_instrumental_gap_original_start"] = round_time(following_start)
                following_line["anchor_diagnostics"]["final_instrumental_gap_rescued_start"] = round_time(corrected_following_start)
                following_line["anchor_diagnostics"]["final_instrumental_gap_desired_seconds"] = round_time(desired_minimum)
                add_flags(following_line, ["final_instrumental_following_line_auto_adjusted_needs_review"])
                following_start = corrected_following_start
                gap_end = following_start - instrumental_before_next_line_seconds
                flags_for_all.append("final_instrumental_gap_rescue_applied_needs_review")

        if gap_end - gap_start < desired_minimum:
            # Do not solve a squeezed explicit instrumental by moving it backwards
            # over the previous lyric. Instead, relax the post-lyric delay and use
            # the real available gap between the previous lyric and the next line.
            relaxed_gap_start = max(previous_start + 0.75, previous_last_word_end + 0.25, previous_minimum_held_gap_start)

            if gap_end - relaxed_gap_start > gap_end - gap_start:
                gap_start = relaxed_gap_start
                flags_for_all.append("instrumental_after_previous_word_delay_relaxed_needs_review")

        if gap_start >= previous_minimum_held_gap_start - 0.001:
            previous_hold_seconds = gap_start - next_line_gap_seconds - previous_last_word_start
            if previous_hold_seconds >= lyric_before_instrumental_min_hold_seconds - 0.05:
                flags_for_all.append("previous_lyric_min_hold_before_instrumental_applied_needs_review")
                add_flags(previous_line, ["held_final_word_before_instrumental_needs_review"])

        if gap_end - gap_start < total_minimum:
            # If the gap is still too short, keep the instrumental after the
            # previous lyric rather than letting it overlap backwards. This may
            # overlap the next lyric, so keep a clear review flag.
            gap_end = max(gap_end, gap_start + total_minimum)
            flags_for_all.append("instrumental_overlap_risk_needs_review")
            flags_for_all.append("instrumental_gap_too_short_needs_review")

        if gap_end - gap_start < desired_minimum:
            flags_for_all.append("instrumental_shorter_than_preferred_needs_review")

    elif following_line:
        following_start = as_float(following_line.get("start"))
        gap_end = max(0.0, following_start - starting_instrumental_before_first_line_seconds)
        gap_start = 0.0
        flags_for_all.append("instrumental_at_start_needs_review")

        if gap_end - gap_start < total_minimum:
            gap_start = max(0.0, gap_end - max(total_minimum, instrumental_fallback_seconds * count))
            flags_for_all.append("instrumental_gap_too_short_needs_review")

        if gap_end <= gap_start:
            gap_end = gap_start + total_minimum
            flags_for_all.append("instrumental_overlap_risk_needs_review")

    elif previous_line:
        previous_start = as_float(previous_line.get("start"))
        previous_last_word_start = as_float(previous_line.get("last_word_start"), previous_start)
        previous_last_word_end = line_last_word_end(previous_line)
        previous_has_audio_end = previous_line.get("line_end_source") == "audio-vocal-offset"

        if previous_has_audio_end:
            gap_start = max(previous_start + 0.75, previous_last_word_end + next_line_gap_seconds)
        else:
            previous_minimum_held_line_end = max(
                previous_last_word_end,
                previous_last_word_start + lyric_before_instrumental_min_hold_seconds,
            )
            gap_start = max(
                previous_start + 0.75,
                previous_last_word_start + instrumental_after_previous_word_seconds,
                previous_minimum_held_line_end + next_line_gap_seconds,
            )
        gap_end = gap_start + instrumental_fallback_seconds * count
        flags_for_all.append("instrumental_at_end_needs_review")

        if audio_duration_seconds and audio_duration_seconds > gap_start + min_each:
            gap_end = audio_duration_seconds
            flags_for_all.append("instrumental_extended_to_audio_end_needs_review")

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
        add_flags(line, flags_for_all)
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
    lyric_before_instrumental_min_hold_seconds: float,
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
            lyric_before_instrumental_min_hold_seconds=lyric_before_instrumental_min_hold_seconds,
        )


def display_gap_before_next_line(
    line: dict[str, Any],
    next_display_line: dict[str, Any] | None,
    next_line_gap_seconds: float,
    adjusted_next_line_gap_seconds: float,
) -> float:
    if not next_display_line:
        return next_line_gap_seconds

    next_flags = set(next_display_line.get("review_flags", []))
    next_source = str(next_display_line.get("line_anchor_source", ""))
    current_flags = set(line.get("review_flags", []))

    next_was_moved = (
        "line_start_auto_adjusted_needs_review" in next_flags
        or "repeated_phrase_line_start_auto_adjusted_needs_review" in next_flags
        or "repeated_identical_line_start_auto_adjusted_needs_review" in next_flags
        or "instrumental_following_line_start_auto_adjusted_needs_review" in next_flags
        or "late_next_line_anchor_rescue_applied_needs_review" in next_flags
        or "repeated_final_word_line_start_auto_adjusted_needs_review" in next_flags
        or next_source in {"corrected-word-cluster", "repeated-phrase-rescue", "repeated-identical-line-rescue", "instrumental-following-line-anchor-rescue", "late-next-line-anchor-rescue", "late-anchor-cascade-rescue", "repeated-final-word-rescue"}
    )

    if next_was_moved and "long_tail_after_last_word_needs_review" in current_flags:
        return adjusted_next_line_gap_seconds

    if next_was_moved:
        return max(next_line_gap_seconds, min(0.75, adjusted_next_line_gap_seconds))

    return next_line_gap_seconds


def build_review_flags(
    line: dict[str, Any],
    next_display_line: dict[str, Any] | None,
    previous_display_line: dict[str, Any] | None,
    long_tail_threshold_seconds: float,
    short_line_threshold_seconds: float,
    large_internal_word_gap_seconds: float,
) -> list[str]:
    flags: list[str] = [
        flag
        for flag in list(line.get("review_flags", []))
        if flag not in DERIVED_REVIEW_FLAGS
    ]

    line_start = as_float(line.get("start"))
    line_end = as_float(line.get("end"))
    last_word_start = as_float(line.get("last_word_start"), line_start)
    max_internal_gap = as_float(line.get("max_internal_word_gap"))

    if max_internal_gap >= large_internal_word_gap_seconds:
        flags.append("large_internal_word_gap_needs_review")

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

    return sorted(set(flags))


def initialise_lyric_lines(
    ordered_lines: list[dict[str, Any]],
    start_padding_seconds: float,
) -> int:
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
        display_start = max(0.0, raw_start - start_padding_seconds)
        diagnostics = calculate_gap_diagnostics(words)

        line["display_type"] = "lyric"
        line["start"] = round_time(display_start)
        line["end"] = None
        line["word_start"] = round_time(raw_start)
        line["last_word_start"] = round_time(as_float(last_word.get("start")))
        line["line_anchor_start"] = round_time(display_start)
        line["line_anchor_source"] = "first-word"
        line["first_internal_word_gap"] = diagnostics["first_internal_word_gap"]
        line["max_internal_word_gap"] = diagnostics["max_internal_word_gap"]
        line["later_internal_word_gap_typical"] = diagnostics["later_internal_word_gap_typical"]
        line["anchor_diagnostics"] = diagnostics
        line["confidence"] = "draft"
        line["locked"] = False
        line["anchor"] = False
        line["timing_source"] = "lyrics-aligner-word-starts"
        line["words"] = build_word_objects(words)
        line["edited_manually"] = False
        lyric_line_count += 1

    return lyric_line_count


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
    auto_anchor_lead_in_extended_max_seconds: float,
    auto_anchor_lead_in_gap_fraction: float,
    auto_anchor_min_words: int,
    repeated_phrase_rescue: bool,
    repeated_final_word_rescue: bool,
    repeated_final_word_min_span_seconds: float,
    repeated_final_word_collapse_window_seconds: float,
    repeated_final_word_start_fraction: float,
    repeated_final_word_spacing_seconds: float,
    instrumental_following_anchor_rescue: bool,
    late_next_line_anchor_rescue: bool,
    late_next_line_gap_seconds: float,
    late_next_line_after_previous_word_seconds: float,
    late_anchor_cascade_gap_seconds: float,
    repeated_phrase_min_gap_seconds: float,
    repeated_phrase_after_previous_word_seconds: float,
    repeated_phrase_min_common_prefix_words: int,
    adjusted_next_line_gap_seconds: float,
    instrumental_after_previous_word_seconds: float,
    instrumental_before_next_line_seconds: float,
    starting_instrumental_before_first_line_seconds: float,
    lyric_before_instrumental_min_hold_seconds: float,
    audio_line_end_estimation: bool,
    audio_line_end_scope: str,
    audio_line_end_frame_ms: int,
    audio_line_end_min_after_last_word_seconds: float,
    audio_line_end_max_search_seconds: float,
    audio_line_end_sustain_seconds: float,
    audio_line_end_relative_threshold: float,
    audio_line_end_noise_floor_multiplier: float,
    audio_line_end_next_lyric_safety_gap_seconds: float,
) -> dict[str, Any]:
    ordered_lines = collect_ordered_lines(word_review)

    if not ordered_lines:
        raise ValueError("No usable lines were found in the word review JSON.")

    lyric_line_count = initialise_lyric_lines(
        ordered_lines=ordered_lines,
        start_padding_seconds=start_padding_seconds,
    )

    if lyric_line_count == 0:
        raise ValueError("No lyric lines with word timings were found in the word review JSON.")

    audio_duration_raw = word_review.get("source", {}).get("audio_duration_seconds")
    audio_duration_seconds = None if audio_duration_raw is None else as_float(audio_duration_raw, fallback=0.0)

    auto_adjusted_line_count = apply_cautious_first_word_corrections(
        lines=ordered_lines,
        auto_correct_suspicious_first_word=auto_correct_suspicious_first_word,
        suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
        first_gap_ratio_threshold=first_gap_ratio_threshold,
        auto_anchor_lead_in_min_seconds=auto_anchor_lead_in_min_seconds,
        auto_anchor_lead_in_max_seconds=auto_anchor_lead_in_max_seconds,
        auto_anchor_lead_in_extended_max_seconds=auto_anchor_lead_in_extended_max_seconds,
        auto_anchor_lead_in_gap_fraction=auto_anchor_lead_in_gap_fraction,
        auto_anchor_min_words=auto_anchor_min_words,
        long_tail_threshold_seconds=long_tail_threshold_seconds,
        start_padding_seconds=start_padding_seconds,
    )

    instrumental_following_anchor_rescue_count = apply_instrumental_following_anchor_rescue(
        lines=ordered_lines,
        enabled=instrumental_following_anchor_rescue,
        suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
        first_gap_ratio_threshold=first_gap_ratio_threshold,
        auto_anchor_lead_in_min_seconds=auto_anchor_lead_in_min_seconds,
        auto_anchor_lead_in_max_seconds=auto_anchor_lead_in_extended_max_seconds,
        auto_anchor_lead_in_gap_fraction=auto_anchor_lead_in_gap_fraction,
        start_padding_seconds=start_padding_seconds,
    )

    late_next_line_anchor_rescue_count = apply_late_next_line_anchor_rescue(
        lines=ordered_lines,
        enabled=late_next_line_anchor_rescue,
        late_next_line_gap_seconds=late_next_line_gap_seconds,
        late_next_line_after_previous_word_seconds=late_next_line_after_previous_word_seconds,
        late_anchor_cascade_gap_seconds=late_anchor_cascade_gap_seconds,
        suspicious_first_word_gap_seconds=suspicious_first_word_gap_seconds,
        first_gap_ratio_threshold=first_gap_ratio_threshold,
    )

    repeated_final_word_rescue_count = apply_repeated_final_word_rescue(
        lines=ordered_lines,
        enabled=repeated_final_word_rescue,
        repeated_final_word_min_span_seconds=repeated_final_word_min_span_seconds,
        repeated_final_word_collapse_window_seconds=repeated_final_word_collapse_window_seconds,
        repeated_final_word_start_fraction=repeated_final_word_start_fraction,
        repeated_final_word_spacing_seconds=repeated_final_word_spacing_seconds,
    )

    repeated_phrase_rescue_count = apply_repeated_phrase_rescue(
        lines=ordered_lines,
        enabled=repeated_phrase_rescue,
        repeated_phrase_min_gap_seconds=repeated_phrase_min_gap_seconds,
        repeated_phrase_after_previous_word_seconds=repeated_phrase_after_previous_word_seconds,
        repeated_phrase_min_common_prefix_words=repeated_phrase_min_common_prefix_words,
        audio_duration_seconds=audio_duration_seconds,
    )

    monotonic_line_start_guard_count = apply_monotonic_lyric_start_guard(
        lines=ordered_lines,
        next_line_gap_seconds=next_line_gap_seconds,
    )

    audio_line_end_estimation_result = apply_audio_line_end_estimates(
        lines=ordered_lines,
        word_review=word_review,
        word_review_path=word_review_path,
        enabled=audio_line_end_estimation,
        scope=audio_line_end_scope,
        frame_ms=audio_line_end_frame_ms,
        min_after_last_word_seconds=audio_line_end_min_after_last_word_seconds,
        max_search_seconds=audio_line_end_max_search_seconds,
        sustain_seconds=audio_line_end_sustain_seconds,
        relative_threshold=audio_line_end_relative_threshold,
        noise_floor_multiplier=audio_line_end_noise_floor_multiplier,
        next_lyric_safety_gap_seconds=audio_line_end_next_lyric_safety_gap_seconds,
    )

    assign_all_instrumental_timings(
        lines=ordered_lines,
        next_line_gap_seconds=next_line_gap_seconds,
        instrumental_fallback_seconds=instrumental_fallback_seconds,
        audio_duration_seconds=audio_duration_seconds,
        instrumental_after_previous_word_seconds=instrumental_after_previous_word_seconds,
        instrumental_before_next_line_seconds=instrumental_before_next_line_seconds,
        starting_instrumental_before_first_line_seconds=starting_instrumental_before_first_line_seconds,
        lyric_before_instrumental_min_hold_seconds=lyric_before_instrumental_min_hold_seconds,
    )

    # First pass: mark long-tail and large-gap flags so end-timing can use them.
    for index, line in enumerate(ordered_lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        previous_display_line = previous_display_line_with_timing(ordered_lines, index)
        next_display_line = next_display_line_with_timing(ordered_lines, index)
        line["review_flags"] = build_review_flags(
            line=line,
            next_display_line=next_display_line,
            previous_display_line=previous_display_line,
            long_tail_threshold_seconds=long_tail_threshold_seconds,
            short_line_threshold_seconds=short_line_threshold_seconds,
            large_internal_word_gap_seconds=large_internal_word_gap_seconds,
        )

    for index, line in enumerate(ordered_lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        next_display_line = next_display_line_with_timing(ordered_lines, index)

        audio_estimated_end = line.get("audio_estimated_end")

        if audio_estimated_end is not None:
            display_end = as_float(audio_estimated_end)

            if next_display_line:
                gap_before_next = display_gap_before_next_line(
                    line=line,
                    next_display_line=next_display_line,
                    next_line_gap_seconds=next_line_gap_seconds,
                    adjusted_next_line_gap_seconds=adjusted_next_line_gap_seconds,
                )
                latest_allowed_end = as_float(next_display_line.get("start")) - gap_before_next

                if display_end > latest_allowed_end:
                    display_end = latest_allowed_end
                    add_flags(line, ["audio_estimated_line_end_clamped_to_next_display_needs_review"])

            display_end = max(as_float(line.get("start")) + 0.1, display_end)
        elif next_display_line:
            gap_before_next = display_gap_before_next_line(
                line=line,
                next_display_line=next_display_line,
                next_line_gap_seconds=next_line_gap_seconds,
                adjusted_next_line_gap_seconds=adjusted_next_line_gap_seconds,
            )
            display_end = max(
                as_float(line.get("start")) + 0.1,
                as_float(next_display_line.get("start")) - gap_before_next,
            )
        else:
            last_word_start = as_float(line.get("last_word_start"), as_float(line.get("word_start")))
            display_end = last_word_start + final_line_hold_seconds

            if audio_duration_seconds and audio_duration_seconds > as_float(line.get("start")):
                display_end = min(display_end, audio_duration_seconds)

        line["end"] = round_time(display_end)

    # Final pass: re-check very short timings after end times have been assigned.
    for index, line in enumerate(ordered_lines):
        if line.get("display_type") != "lyric" or line.get("start") is None:
            continue

        previous_display_line = previous_display_line_with_timing(ordered_lines, index)
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
                    **({"first_internal_word_gap": line.get("first_internal_word_gap")} if line.get("display_type") == "lyric" else {}),
                    **({"max_internal_word_gap": line.get("max_internal_word_gap")} if line.get("display_type") == "lyric" else {}),
                    **({"later_internal_word_gap_typical": line.get("later_internal_word_gap_typical")} if line.get("display_type") == "lyric" else {}),
                    **({"anchor_diagnostics": line.get("anchor_diagnostics", {})} if line.get("display_type") == "lyric" else {}),
                    **({"audio_estimated_end": line.get("audio_estimated_end")} if line.get("display_type") == "lyric" and line.get("audio_estimated_end") is not None else {}),
                    **({"line_end_source": line.get("line_end_source")} if line.get("display_type") == "lyric" and line.get("line_end_source") is not None else {}),
                    **({"line_end_confidence": line.get("line_end_confidence")} if line.get("display_type") == "lyric" and line.get("line_end_confidence") is not None else {}),
                    **({"line_end_diagnostics": line.get("line_end_diagnostics", {})} if line.get("display_type") == "lyric" and line.get("line_end_diagnostics") is not None else {}),
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
            "repeated_phrase_rescue_count": repeated_phrase_rescue_count,
            "repeated_final_word_rescue_count": repeated_final_word_rescue_count,
            "instrumental_following_anchor_rescue_count": instrumental_following_anchor_rescue_count,
            "late_next_line_anchor_rescue_count": late_next_line_anchor_rescue_count,
            "monotonic_line_start_guard_count": monotonic_line_start_guard_count,
            "audio_line_end_estimation": audio_line_end_estimation_result,
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
                "auto_anchor_min_words": auto_anchor_min_words,
                "auto_anchor_lead_in_min_seconds": auto_anchor_lead_in_min_seconds,
                "auto_anchor_lead_in_max_seconds": auto_anchor_lead_in_max_seconds,
                "auto_anchor_lead_in_extended_max_seconds": auto_anchor_lead_in_extended_max_seconds,
                "auto_anchor_lead_in_gap_fraction": auto_anchor_lead_in_gap_fraction,
                "repeated_phrase_rescue": repeated_phrase_rescue,
                "repeated_final_word_rescue": repeated_final_word_rescue,
                "repeated_final_word_min_span_seconds": repeated_final_word_min_span_seconds,
                "repeated_final_word_collapse_window_seconds": repeated_final_word_collapse_window_seconds,
                "repeated_final_word_start_fraction": repeated_final_word_start_fraction,
                "repeated_final_word_spacing_seconds": repeated_final_word_spacing_seconds,
                "instrumental_following_anchor_rescue": instrumental_following_anchor_rescue,
                "late_next_line_anchor_rescue": late_next_line_anchor_rescue,
                "late_next_line_gap_seconds": late_next_line_gap_seconds,
                "late_next_line_after_previous_word_seconds": late_next_line_after_previous_word_seconds,
                "late_anchor_cascade_gap_seconds": late_anchor_cascade_gap_seconds,
                "repeated_phrase_min_gap_seconds": repeated_phrase_min_gap_seconds,
                "repeated_phrase_after_previous_word_seconds": repeated_phrase_after_previous_word_seconds,
                "repeated_phrase_min_common_prefix_words": repeated_phrase_min_common_prefix_words,
                "adjusted_next_line_gap_seconds": adjusted_next_line_gap_seconds,
                "instrumental_after_previous_word_seconds": instrumental_after_previous_word_seconds,
                "instrumental_before_next_line_seconds": instrumental_before_next_line_seconds,
                "starting_instrumental_before_first_line_seconds": starting_instrumental_before_first_line_seconds,
                "lyric_before_instrumental_min_hold_seconds": lyric_before_instrumental_min_hold_seconds,
                "audio_line_end_estimation": audio_line_end_estimation,
                "audio_line_end_scope": audio_line_end_scope,
                "audio_line_end_frame_ms": audio_line_end_frame_ms,
                "audio_line_end_min_after_last_word_seconds": audio_line_end_min_after_last_word_seconds,
                "audio_line_end_max_search_seconds": audio_line_end_max_search_seconds,
                "audio_line_end_sustain_seconds": audio_line_end_sustain_seconds,
                "audio_line_end_relative_threshold": audio_line_end_relative_threshold,
                "audio_line_end_noise_floor_multiplier": audio_line_end_noise_floor_multiplier,
                "audio_line_end_next_lyric_safety_gap_seconds": audio_line_end_next_lyric_safety_gap_seconds,
            },
            "review_flag_count": len(review_flags),
            "review_flags": review_flags,
        },
        "sections": output_sections,
        "editor_notes": [
            "This draft uses singing-specific word starts as timing anchors.",
            "Line starts normally come from the first word in each lyric line.",
            "Cautious first-word correction is only applied to longer lines where word 1 looks like an early outlier.",
            "Short held lines are flagged, but they are not auto-corrected just because word 1 is followed by a gap.",
            "Repeated phrase rescue can pull repeated or shared-opening lines earlier when the word anchors arrive implausibly late.",
            "Lines after explicit instrumental placeholders can be moved later when word 1 looks too early and the rest of the line starts much later.",
            "A late next-line rescue can move a lyric line earlier when a clean previous line is followed by a suspiciously late next-line anchor, but it is deliberately narrow and does not cascade across a phrase.",
            "A monotonic line-start guard prevents the next lyric display line from appearing before the previous lyric's final word anchor.",
            "Line ends can be estimated from the vocal audio after the final word start; if audio analysis fails, the builder falls back to inferred line ends.",
            "Instrumental placeholders are kept as editable display lines with empty words arrays and are timed from audio-backed lyric ends where available.",
            "When no reliable audio-backed line end is found, the builder keeps the older safe fallback rules for held lyrics and instrumental gaps.",
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
        "--adjusted-next-line-gap-ms",
        type=int,
        default=1250,
        help="Larger gap before a corrected or repeated-phrase-rescued next line. Default: 1250.",
    )

    parser.add_argument(
        "--final-line-hold-ms",
        type=int,
        default=2500,
        help="How long to hold the final line after its last word if no next line exists. Default: 2500.",
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
        help="Flag lyric lines with a large internal word-start gap. Default: 1750.",
    )

    parser.add_argument(
        "--instrumental-fallback-ms",
        type=int,
        default=5000,
        help="Fallback duration for squeezed instrumental placeholders at the start, middle, or end. Default: 5000.",
    )

    parser.add_argument(
        "--instrumental-after-previous-word-ms",
        type=int,
        default=2500,
        help="Start an instrumental this long after the previous lyric's last word. Default: 2500.",
    )

    parser.add_argument(
        "--instrumental-before-next-line-ms",
        type=int,
        default=500,
        help="End an instrumental this long before the next lyric line. Default: 500.",
    )

    parser.add_argument(
        "--starting-instrumental-before-first-line-ms",
        type=int,
        default=1500,
        help="End a starting instrumental this long before the first lyric line. Default: 1500.",
    )

    parser.add_argument(
        "--lyric-before-instrumental-min-hold-ms",
        type=int,
        default=3000,
        help="When a lyric is followed by an explicit . . . line, keep the lyric visible for at least this long after its final word start when there is room. Default: 3000.",
    )

    parser.add_argument(
        "--no-audio-line-end-estimation",
        action="store_true",
        help="Disable audio-backed line-end estimation and use inferred display ends only.",
    )

    parser.add_argument(
        "--audio-line-end-scope",
        choices=["before_instrumental", "before_instrumental_or_final", "all"],
        default="before_instrumental",
        help="Choose where audio-backed line ends may override inferred display ends. Default: before_instrumental.",
    )

    parser.add_argument(
        "--audio-line-end-frame-ms",
        type=int,
        default=20,
        help="Audio analysis frame size in milliseconds. Default: 20.",
    )

    parser.add_argument(
        "--audio-line-end-min-after-last-word-ms",
        type=int,
        default=500,
        help="Do not search for a vocal offset until this long after the final word start. Default: 500.",
    )

    parser.add_argument(
        "--audio-line-end-max-search-ms",
        type=int,
        default=9000,
        help="Maximum time to search after the final word start for a vocal drop. Default: 9000.",
    )

    parser.add_argument(
        "--audio-line-end-sustain-ms",
        type=int,
        default=450,
        help="Low-energy audio must last this long before it counts as a vocal offset. Default: 450.",
    )

    parser.add_argument(
        "--audio-line-end-relative-threshold",
        type=float,
        default=0.18,
        help="Low-energy threshold as a fraction of local vocal energy. Default: 0.18.",
    )

    parser.add_argument(
        "--audio-line-end-noise-floor-multiplier",
        type=float,
        default=3.0,
        help="Low-energy threshold must also sit above the detected noise floor by this multiplier. Default: 3.0.",
    )

    parser.add_argument(
        "--audio-line-end-next-lyric-safety-gap-ms",
        type=int,
        default=250,
        help="Keep estimated line ends this far before the next lyric start. Default: 250.",
    )

    parser.add_argument(
        "--no-auto-correct-suspicious-first-word",
        action="store_true",
        help="Disable cautious first-word anchor correction. Lines will still be flagged.",
    )

    parser.add_argument(
        "--suspicious-first-word-gap-ms",
        type=int,
        default=1750,
        help="First-to-second word gap that can trigger cautious anchor correction. Default: 1750.",
    )

    parser.add_argument(
        "--first-gap-ratio-threshold",
        type=float,
        default=2.5,
        help="First gap must be this many times larger than the typical later gap. Default: 2.5.",
    )

    parser.add_argument(
        "--auto-anchor-min-words",
        type=int,
        default=3,
        help="Do not auto-correct lines with this many words or fewer. Default: 3.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-min-ms",
        type=int,
        default=350,
        help="Minimum lead-in before word 2 when auto-correcting. Default: 350.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-max-ms",
        type=int,
        default=1000,
        help="Normal maximum lead-in before word 2 when auto-correcting. Default: 1000.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-extended-max-ms",
        type=int,
        default=2500,
        help="Extended maximum lead-in when the previous line looks held. Default: 2500.",
    )

    parser.add_argument(
        "--auto-anchor-lead-in-gap-fraction",
        type=float,
        default=0.33,
        help="Fraction of first-word gap used as lead-in before word 2. Default: 0.33.",
    )

    parser.add_argument(
        "--no-repeated-phrase-rescue",
        action="store_true",
        help="Disable repeated/shared-opening phrase rescue.",
    )

    parser.add_argument(
        "--no-repeated-final-word-rescue",
        action="store_true",
        help="Disable rescue for repeated one-word lines after a long held final word.",
    )

    parser.add_argument(
        "--repeated-final-word-min-span-ms",
        type=int,
        default=8000,
        help="Minimum base-line start to final-word span for repeated final word rescue. Default: 8000.",
    )

    parser.add_argument(
        "--repeated-final-word-collapse-window-ms",
        type=int,
        default=1250,
        help="Repeated one-word anchors within this window of the base final word are treated as collapsed. Default: 1250.",
    )

    parser.add_argument(
        "--repeated-final-word-start-fraction",
        type=float,
        default=0.55,
        help="Where in the long held phrase to place the first repeated one-word line. Default: 0.55.",
    )

    parser.add_argument(
        "--repeated-final-word-spacing-ms",
        type=int,
        default=4200,
        help="Spacing between rescued repeated final-word display lines. Default: 4200.",
    )

    parser.add_argument(
        "--no-instrumental-following-anchor-rescue",
        action="store_true",
        help="Disable the rescue that can move a lyric line later when it follows an explicit instrumental placeholder.",
    )

    parser.add_argument(
        "--no-late-next-line-anchor-rescue",
        action="store_true",
        help="Disable rescue for lines whose first word appears too late after a clean previous line.",
    )

    parser.add_argument(
        "--late-next-line-gap-ms",
        type=int,
        default=2200,
        help="Gap after the previous last word that can trigger late next-line rescue. Default: 2200.",
    )

    parser.add_argument(
        "--late-next-line-after-previous-word-ms",
        type=int,
        default=1000,
        help="Place late-rescued lines this long after the previous lyric's last word. Default: 1000.",
    )

    parser.add_argument(
        "--late-anchor-cascade-gap-ms",
        type=int,
        default=6500,
        help="Gap from a rescued previous line that can trigger one cautious cascade rescue. Default: 6500.",
    )

    parser.add_argument(
        "--repeated-phrase-min-gap-ms",
        type=int,
        default=3000,
        help="Minimum suspicious gap for repeated phrase rescue. Default: 3000.",
    )

    parser.add_argument(
        "--repeated-phrase-after-previous-word-ms",
        type=int,
        default=4000,
        help="Place rescued shared-opening lines this long after the previous lyric's last word. Default: 4000.",
    )

    parser.add_argument(
        "--repeated-phrase-min-common-prefix-words",
        type=int,
        default=2,
        help="Shared opening words needed for repeated phrase rescue. Default: 2.",
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
            auto_anchor_lead_in_extended_max_seconds=args.auto_anchor_lead_in_extended_max_ms / 1000,
            auto_anchor_lead_in_gap_fraction=args.auto_anchor_lead_in_gap_fraction,
            auto_anchor_min_words=args.auto_anchor_min_words,
            repeated_phrase_rescue=not args.no_repeated_phrase_rescue,
            repeated_final_word_rescue=not args.no_repeated_final_word_rescue,
            repeated_final_word_min_span_seconds=args.repeated_final_word_min_span_ms / 1000,
            repeated_final_word_collapse_window_seconds=args.repeated_final_word_collapse_window_ms / 1000,
            repeated_final_word_start_fraction=args.repeated_final_word_start_fraction,
            repeated_final_word_spacing_seconds=args.repeated_final_word_spacing_ms / 1000,
            instrumental_following_anchor_rescue=not args.no_instrumental_following_anchor_rescue,
            late_next_line_anchor_rescue=not args.no_late_next_line_anchor_rescue,
            late_next_line_gap_seconds=args.late_next_line_gap_ms / 1000,
            late_next_line_after_previous_word_seconds=args.late_next_line_after_previous_word_ms / 1000,
            late_anchor_cascade_gap_seconds=args.late_anchor_cascade_gap_ms / 1000,
            repeated_phrase_min_gap_seconds=args.repeated_phrase_min_gap_ms / 1000,
            repeated_phrase_after_previous_word_seconds=args.repeated_phrase_after_previous_word_ms / 1000,
            repeated_phrase_min_common_prefix_words=args.repeated_phrase_min_common_prefix_words,
            adjusted_next_line_gap_seconds=args.adjusted_next_line_gap_ms / 1000,
            instrumental_after_previous_word_seconds=args.instrumental_after_previous_word_ms / 1000,
            instrumental_before_next_line_seconds=args.instrumental_before_next_line_ms / 1000,
            starting_instrumental_before_first_line_seconds=args.starting_instrumental_before_first_line_ms / 1000,
            lyric_before_instrumental_min_hold_seconds=args.lyric_before_instrumental_min_hold_ms / 1000,
            audio_line_end_estimation=not args.no_audio_line_end_estimation,
            audio_line_end_scope=args.audio_line_end_scope,
            audio_line_end_frame_ms=args.audio_line_end_frame_ms,
            audio_line_end_min_after_last_word_seconds=args.audio_line_end_min_after_last_word_ms / 1000,
            audio_line_end_max_search_seconds=args.audio_line_end_max_search_ms / 1000,
            audio_line_end_sustain_seconds=args.audio_line_end_sustain_ms / 1000,
            audio_line_end_relative_threshold=args.audio_line_end_relative_threshold,
            audio_line_end_noise_floor_multiplier=args.audio_line_end_noise_floor_multiplier,
            audio_line_end_next_lyric_safety_gap_seconds=args.audio_line_end_next_lyric_safety_gap_ms / 1000,
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
        print(f"Sections:                 {draft['alignment']['section_count']}")
        print(f"Display lines:            {draft['alignment']['line_count']}")
        print(f"Lyric lines:              {draft['alignment']['lyric_line_count']}")
        print(f"Instrumentals:            {draft['alignment']['instrumental_line_count']}")
        print(f"Auto-adjusted lines:      {draft['alignment']['auto_adjusted_line_count']}")
        print(f"Repeated-phrase rescues:  {draft['alignment']['repeated_phrase_rescue_count']}")
        print(f"Repeated final-word rescues: {draft['alignment']['repeated_final_word_rescue_count']}")
        print(f"Instrumental line rescues: {draft['alignment']['instrumental_following_anchor_rescue_count']}")
        print(f"Late next-line rescues:    {draft['alignment']['late_next_line_anchor_rescue_count']}")
        audio_status = draft['alignment'].get('audio_line_end_estimation', {})
        print(f"Audio line-end status:     {audio_status.get('status', 'unknown')}")
        print(f"Audio-estimated endings:   {audio_status.get('estimated_line_end_count', 0)}")
        print(f"Audio-end fallbacks:       {audio_status.get('fallback_line_end_count', 0)}")
        print(f"Audio-end skipped by scope: {audio_status.get('skipped_line_end_count', 0)}")
        print(f"Review flags:             {draft['alignment']['review_flag_count']}")
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
