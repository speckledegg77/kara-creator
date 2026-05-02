from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

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

UNVOICED_FOR_S = {
    "P",
    "T",
    "K",
    "F",
    "TH",
}


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def normalise_word(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", "", value)
    return value


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
    last_phone = base_phones.split()[-1] if base_phones.split() else ""

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


def get_word_phones(word: str) -> str | None:
    direct = get_direct_phones(word)

    if direct:
        return direct

    contraction = get_contraction_phones(word)

    if contraction:
        return contraction

    return None


def build_phoneme_file(word_list_path: Path, output_path: Path, missing_path: Path) -> int:
    require_file(word_list_path, "Word list")

    words = []

    for raw_line in word_list_path.read_text(encoding="utf-8-sig").splitlines():
        word = normalise_word(raw_line)

        if word:
            words.append(word)

    words = sorted(set(words))

    if not words:
        raise ValueError("The word list is empty.")

    output_lines = []
    missing_words = []

    for word in words:
        phones = get_word_phones(word)

        if phones:
            output_lines.append(f"{word}\t{phones}")
        else:
            missing_words.append(word)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    if missing_words:
        missing_path.parent.mkdir(parents=True, exist_ok=True)
        missing_path.write_text("\n".join(missing_words) + "\n", encoding="utf-8")

    print("")
    print("Pronunciation file generated.")
    print(f"Word list:       {word_list_path}")
    print(f"Output:          {output_path}")
    print(f"Words converted: {len(output_lines)}")
    print(f"Missing words:   {len(missing_words)}")

    if missing_words:
        print(f"Missing list:    {missing_path}")
        print("")
        print("Open the missing list and send it here. We will add those pronunciations manually.")
        print("")
        return 1

    print("")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create lyrics-aligner CMU-style word2phonemes file from a word list."
    )

    parser.add_argument(
        "--word-list",
        required=True,
        help="Path to files/kara_test_word_list.txt.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Path to files/kara_test_word2phonemes.txt.",
    )

    parser.add_argument(
        "--missing",
        required=True,
        help="Path where missing words should be written.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return build_phoneme_file(
            word_list_path=Path(args.word_list).resolve(),
            output_path=Path(args.out).resolve(),
            missing_path=Path(args.missing).resolve(),
        )
    except Exception as error:
        print("")
        print("Could not create pronunciation file.")
        print(str(error))
        print("")
        return 1


if __name__ == "__main__":
    sys.exit(main())