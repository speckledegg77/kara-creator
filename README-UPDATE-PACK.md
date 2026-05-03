# Kara Creator Phase 2 documentation update pack

Copy the `docs` folder in this zip over your project `docs` folder.

These updates reflect the validated Phase 1 workflow:

- lyrics-aligner is the current primary aligner
- section headings are optional for Phase 2
- blank lines can create automatic sections
- `. . .`, `...`, and `…` can represent instrumental placeholder lines
- `karaoke-draft-v3` is the current working draft format
- `incoming/`, `outputs/`, and `alignment_lab/runs/` should be treated carefully for Git safety

Suggested PowerShell after extracting:

```powershell
cd C:\Users\mark\kara-creator
git status
git add docs README-UPDATE-PACK.md
git commit -m "Update Kara Creator docs for Phase 2"
git push origin main
```

Do not run `git add -A` until you have checked that audio and generated song files are ignored.
