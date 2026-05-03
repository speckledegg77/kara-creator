# New Song Test: draft vs edited diagnostics

Compared:

- `new_song_test-draft-lyrics-aligner-v3.json`
- `new_song_test-draft-lyrics-aligner-v3-edited-2.json`

## Headline counts

- Total display lines: 36
- Lyric lines: 33
- Instrumental lines: 3
- Lines changed manually: 14
- Lyric lines changed: 11
- Instrumental lines changed: 3

## Main finding

The most important error is `line-0012`.

The generated draft started that line at 69.258s because the aligner placed the first word at 69.408s.
The edited version moved the displayed line start to 78.500s.

That means the instrumental line before it ended too early. The instrumental timing problem was caused by a bad lyric-word anchor after the instrumental gap.

## Top edited lines

| id | display_type | text | start_delta | end_delta | duration_delta | flags |
| --- | --- | --- | --- | --- | --- | --- |
| line-0001 | instrumental | . . . | -10.230 | -1.730 | 8.500 | instrumental_at_start_needs_review/instrumental_timing_needs_review |
| line-0012 | lyric | If I met myself again I wonder what she'd say | 9.242 | -0.290 | -9.532 |  |
| line-0011 | instrumental | . . . | 2.448 | 7.822 | 5.374 | instrumental_timing_needs_review |
| line-0033 | lyric | If I met myself again | 2.942 | -2.646 | -5.588 | long_tail_after_last_word_needs_review |
| line-0023 | lyric | If I met myself again | 0.000 | -4.205 | -4.205 | long_tail_after_last_word_needs_review |
| line-0035 | instrumental | . . . | 2.930 | -0.266 | -3.196 | instrumental_timing_needs_review |
| line-0003 | lyric | Would I tell that simple wide-eyed girl the truth | 1.567 | -1.499 | -3.066 |  |
| line-0022 | lyric | And go and do it all again | 0.000 | -2.808 | -2.808 | long_tail_after_last_word_needs_review |
| line-0010 | lyric | If I met myself again | 1.272 | 2.176 | 0.904 |  |
| line-0034 | lyric | If I met myself again | 0.000 | 1.823 | 1.823 |  |
| line-0032 | lyric | Cause I won't have my son | 0.000 | 1.544 | 1.544 |  |
| line-0002 | lyric | If I met myself back then I wonder what I'd say | 0.000 | 1.239 | 1.239 |  |
| line-0009 | lyric | I'd make her see her future's me | 0.000 | 1.169 | 1.169 |  |
| line-0036 | lyric | If I met myself again | -0.046 | -0.046 | -0.000 |  |

## Suggested next rule

Add a diagnostic flag when a lyric line has a very large internal word gap.

For example, `line-0012` has a gap of 9.792 seconds between word 1 and word 2.
That should be flagged as something like:

`large_internal_word_gap_needs_review`

Do not automatically fix it yet. Flag it first, because some long gaps may be musically correct.
