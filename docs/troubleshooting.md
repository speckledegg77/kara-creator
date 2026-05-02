# Troubleshooting

Use this when something goes wrong.

## PowerShell says Python is not recognised

Try:

```powershell
py --version
```

If that works, use `py` instead of `python`.

If neither works, reinstall Python and make sure `Add python.exe to PATH` is ticked.

## PowerShell says Node is not recognised

Close PowerShell and open a new PowerShell window.

Then try:

```powershell
node --version
npm --version
```

If that still fails, reinstall Node.js.

## PowerShell says FFmpeg is not recognised

FFmpeg is either not installed or not added to PATH.

Check where FFmpeg was installed.

The file you need is usually:

```text
ffmpeg.exe
```

Once PATH is fixed, this should work:

```powershell
ffmpeg -version
```

## The generated timing starts correctly and then drifts

Likely cause:

- the song was aligned as one long timeline
- not enough section anchors were used
- lyric phrase splitting does not match the sung phrasing

Fix:

- split the lyrics into sections
- add section anchors
- use section rescale
- check whether one printed lyric line should be split into two sung phrases

## The draft has overlapping phrases

Likely cause:

- edits were applied to one phrase only
- ripple behaviour was not used
- generated timings were too close together

Fix:

- use ripple edit
- shift or rescale the section
- check JSON for start/end errors

## The tool struggles with repeated lines

Repeated lyrics are hard because the same text appears more than once.

Fix:

- keep repeated phrases as separate IDs
- use section labels
- add manual anchor points around repeated sections

## The vocal file sounds clean but timing is still poor

Possible causes:

- lyrics do not match that exact recording
- lyric lines do not match sung phrases
- there are long held notes or delayed consonants
- there are harmony layers or backing vocals
- the alignment engine is not suitable for singing

Fix:

- check the lyric file line by line
- split phrases more carefully
- add section anchors
- try a different alignment strategy later

## The editor works but the exported JSON will not load

Check:

- JSON has no trailing commas
- every object has required fields
- timings are numbers, not strings
- section and phrase arrays are not empty

## Git tries to add audio files

Do not commit audio files.

Run:

```powershell
git status
```

If you see MP3, WAV, or project source files listed, fix `.gitignore` before committing.

If a file was accidentally staged, unstage it:

```powershell
git restore --staged path\to\file.mp3
```
