# Windows Setup Guide

This guide assumes you are a complete novice and you are using Windows with PowerShell.

Do each step in order.

## Step 1: Install VS Code

1. Open your browser.
2. Search for `Visual Studio Code download`.
3. Download the Windows installer from Microsoft.
4. Run the installer.
5. Accept the default options.
6. Tick the option to add VS Code to your PATH if the installer offers it.
7. Finish installation.

## Step 2: Install Git

You can use either GitHub Desktop or Git command line.

For easiest use:

1. Install GitHub Desktop.
2. Sign in to GitHub.
3. Use it to clone and commit if preferred.

For command-line use:

1. Search for `Git for Windows`.
2. Download and install it.
3. Accept the default options unless you know you need something else.

Check Git in PowerShell:

```powershell
git --version
```

## Step 3: Install Python

Some project tools use normal Python, and the current aligner uses a conda environment.

Check normal Python:

```powershell
python --version
```

If that does not work, try:

```powershell
py --version
```

## Step 4: Install Miniconda

The current `lyrics-aligner` workflow uses a conda environment called `aligner-win`.

Install Miniconda for Windows, then open a new PowerShell window and check:

```powershell
conda --version
```

The working environment should be activated with:

```powershell
conda activate aligner-win
```

If that environment does not exist, check the project notes or ask for the current setup commands.

## Step 5: Install FFmpeg

FFmpeg is used to read and convert audio files.

After installing FFmpeg, check it in PowerShell:

```powershell
ffmpeg -version
```

You should see FFmpeg version information.

If PowerShell says `ffmpeg is not recognised`, FFmpeg is installed incorrectly or is not on your PATH.

## Step 6: Install Node.js

Node.js may be needed later if the editor moves to React.

Check:

```powershell
node --version
npm --version
```

The current proof of concept uses static HTML and Python tools, so Node is not always needed for the immediate workflow.

## Step 7: Go to the project folder

Current project folder:

```powershell
cd C:\Users\mark\kara-creator
```

## Step 8: Activate the aligner environment

Before running the current pipeline:

```powershell
conda activate aligner-win
cd C:\Users\mark\kara-creator
```

## Step 9: Run the current pipeline

Example:

```powershell
python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"
```

## Step 10: Open the editor

```powershell
Start-Process .\tools\edit_karaoke_draft.html
```

Then load the prepared audio file and draft JSON shown by the pipeline.

## Step 11: Do not add audio files to Git

Commercial audio and generated local projects should stay on your PC.

They should not be committed to Git.

Run before commits:

```powershell
git status
```

## Basic checks

Run these commands any time you need to check whether the core tools are installed:

```powershell
python --version
conda --version
ffmpeg -version
git --version
node --version
npm --version
```
