# Git and File Safety

This project involves audio files and full song lyrics.

Be careful about what goes into Git.

## Do commit

Commit:

- source code
- documentation
- schema examples
- safe tiny demo data created specifically for the project
- test fixtures that do not create copyright or privacy problems

## Do not commit

Do not commit:

- commercial MP3 files
- isolated vocal stems from commercial recordings
- backing tracks
- large generated WAV files
- local source audio
- generated files containing full copyrighted lyrics unless you have made a deliberate private-repo decision
- private notes or tokens
- local run logs that include sensitive file paths if you do not want them stored

## Current folders to treat carefully

The current workflow may create these folders:

```text
incoming/
outputs/
alignment_lab/runs/
alignment_lab/singing-aligners/lyrics-aligner/outputs/
alignment_lab/singing-aligners/lyrics-aligner/files/kara_*
```

These may contain:

- uploaded source audio
- copied vocal files
- full lyric text
- generated draft JSON containing full lyrics
- edited JSON containing full lyrics
- diagnostic alignment files

Do not commit them unless you have checked the contents and made a deliberate decision.

## Suggested `.gitignore`

Use this as a starting point:

```gitignore
# Dependencies
node_modules/
.venv/
venv/
__pycache__/
*.pyc

# Build outputs
dist/
build/
.next/

# Local environment
.env
.env.local

# Local authoring source files and generated song data
incoming/
outputs/
exports/
working/
projects/
alignment_lab/runs/

# lyrics-aligner generated files for local songs
alignment_lab/singing-aligners/lyrics-aligner/outputs/
alignment_lab/singing-aligners/lyrics-aligner/files/kara_*

# Audio and media source files
*.mp3
*.wav
*.m4a
*.flac
*.aac
*.ogg

# OS files
.DS_Store
Thumbs.db
```

## Before every commit

Run:

```powershell
git status
```

Check the list carefully.

If you see audio, generated run folders, or full lyric JSON, do not commit until `.gitignore` is fixed or you have deliberately decided it is safe.

## Normal commit commands

```powershell
git add -A
git commit -m "Describe the change"
git push origin main
```

## Checkpoint commit

Use this before major changes:

```powershell
git add -A
git commit -m "Checkpoint before karaoke authoring change"
git tag "checkpoint-$(Get-Date -Format 'yyyyMMdd-HHmm')"
git push origin main --tags
```

## Unstage a file by mistake

```powershell
git restore --staged path\to\file
```

## Remove a committed file from future commits

If a generated or audio file has already been committed, ask for help before rewriting history.

Do not guess. Git history cleanup can go wrong if rushed.
