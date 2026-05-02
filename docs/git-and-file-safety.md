# Git and File Safety

This project will involve audio files.

Be careful about what goes into Git.

## Do commit

Commit:

- source code
- documentation
- schema examples
- safe tiny demo data if created specifically for the project
- test fixtures that do not create copyright or privacy problems

## Do not commit

Do not commit:

- commercial MP3 files
- isolated vocal stems from commercial recordings
- backing tracks
- large generated WAV files
- local project folders containing source audio
- private notes or tokens

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

# Local authoring projects
projects/

# Audio and media source files
*.mp3
*.wav
*.m4a
*.flac
*.aac
*.ogg

# Generated exports that may include copyrighted lyrics
exports/
working/

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

If you see an audio file, do not commit until `.gitignore` is fixed.

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
