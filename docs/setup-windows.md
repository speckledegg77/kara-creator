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

## Step 3: Install Python

1. Go to the official Python downloads page.
2. Download the Windows installer.
3. Run it.
4. Tick `Add python.exe to PATH` before installing.
5. Finish installation.

Then check it in PowerShell:

```powershell
python --version
```

You should see a Python version number.

If that does not work, try:

```powershell
py --version
```

## Step 4: Install Node.js

1. Go to the official Node.js downloads page.
2. Download the current LTS version for Windows.
3. Run the installer.
4. Accept the default options.
5. Finish installation.

Then check it in PowerShell:

```powershell
node --version
npm --version
```

You should see version numbers for both.

## Step 5: Install FFmpeg

FFmpeg is used to read and convert audio files.

The easiest Windows route may vary. The project should later include one preferred method once tested on your PC.

After installing FFmpeg, check it in PowerShell:

```powershell
ffmpeg -version
```

You should see FFmpeg version information.

If PowerShell says `ffmpeg is not recognised`, FFmpeg is installed incorrectly or is not on your PATH.

## Step 6: Create your project folder

Choose where your coding projects live.

For example:

```powershell
cd $HOME
mkdir Projects
cd Projects
```

## Step 7: Clone the new repo

Once the repo exists on GitHub, clone it.

Replace `<repo-url>` with the real GitHub URL.

```powershell
git clone <repo-url>
cd karaoke-authoring-tool
```

## Step 8: Add these documents

Copy the generated files into the repo root so the folder looks like this:

```text
karaoke-authoring-tool
  README.md
  docs
    00-novice-start-here.md
    context.md
    decisions.md
    roadmap.md
    setup-windows.md
    architecture.md
    authoring-workflow.md
    json-schema.md
    testing-checklist.md
    troubleshooting.md
    new-chat-starter.md
```

## Step 9: First commit

Run this in PowerShell from the project folder:

```powershell
git add -A
git commit -m "Add project source docs"
git push origin main
```

## Step 10: Do not add audio files to Git

Commercial audio and generated local projects should stay on your PC.

They should not be committed to Git.

A `.gitignore` file should block folders such as:

```text
projects/
*.mp3
*.wav
*.m4a
```

## Basic checks

Run these commands any time you need to check whether the core tools are installed:

```powershell
python --version
node --version
npm --version
ffmpeg -version
git --version
```
