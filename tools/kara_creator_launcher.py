from __future__ import annotations

import html
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, abort, request, send_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT = 8765

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "song"


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def is_within_project(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def render_page(title: str, body: str) -> Response:
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
      --bg: #111827;
      --panel: #1f2937;
      --panel-soft: #263244;
      --text: #f9fafb;
      --muted: #9ca3af;
      --border: #374151;
      --good: #22c55e;
      --danger: #ef4444;
      --warning: #f59e0b;
      --button: #e5e7eb;
      --button-text: #111827;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
    }}

    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 24px;
    }}

    h1 {{
      margin: 0 0 10px;
      font-size: 30px;
    }}

    h2 {{
      margin-top: 0;
    }}

    p {{
      color: var(--muted);
      line-height: 1.5;
    }}

    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
      margin: 18px 0;
    }}

    label {{
      display: block;
      font-weight: bold;
      margin: 14px 0 6px;
    }}

    input {{
      width: 100%;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
    }}

    input[type="file"] {{
      padding: 0;
      border: none;
    }}

    button,
    .button-link {{
      display: inline-block;
      background: var(--button);
      color: var(--button-text);
      border: none;
      border-radius: 10px;
      padding: 11px 14px;
      cursor: pointer;
      font-weight: bold;
      text-decoration: none;
      margin: 6px 6px 6px 0;
    }}

    .good {{
      background: var(--good);
      color: #052e16;
    }}

    .danger {{
      background: var(--danger);
      color: white;
    }}

    .warning {{
      background: var(--warning);
      color: #111827;
    }}

    code,
    pre {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
    }}

    code {{
      padding: 2px 5px;
    }}

    pre {{
      padding: 12px;
      white-space: pre-wrap;
      overflow-x: auto;
      max-height: 420px;
    }}

    .path {{
      word-break: break-all;
      color: var(--text);
    }}

    .small {{
      color: var(--muted);
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>"""
    return Response(page, mimetype="text/html")


@app.get("/")
def index() -> Response:
    body = """
<h1>Kara Creator Launcher</h1>
<p>
  Upload an isolated vocal MP3 and exact sectioned lyrics TXT. The launcher will run the local lyrics-aligner pipeline and create a draft karaoke JSON.
</p>

<div class="panel">
  <h2>Create a draft</h2>

  <form method="post" action="/run" enctype="multipart/form-data">
    <label for="song_name">Song name</label>
    <input id="song_name" name="song_name" type="text" placeholder="for example: new_song_test" required />

    <label for="audio_file">Isolated vocal MP3</label>
    <input id="audio_file" name="audio_file" type="file" accept="audio/mpeg,audio/mp3,audio/*" required />

    <label for="lyrics_file">Exact lyrics TXT</label>
    <input id="lyrics_file" name="lyrics_file" type="file" accept=".txt,text/plain" required />

    <p class="small">
      Your lyrics TXT should use section headings like <code>[OPENING]</code>, <code>[VERSE]</code>, and <code>[CHORUS]</code>.
    </p>

    <button class="good" type="submit">Run pipeline</button>
  </form>
</div>

<div class="panel">
  <h2>Lyrics format</h2>
  <pre>[OPENING]
First lyric line here
Second lyric line here

[VERSE]
Next lyric line here
Next lyric line here

[CHORUS]
Next lyric line here</pre>
</div>

<div class="panel">
  <h2>Editor</h2>
  <p>
    Once a draft has been created, open the editor and load the generated audio file and draft JSON.
  </p>
  <a class="button-link" href="/editor" target="_blank">Open draft editor</a>
</div>
"""
    return render_page("Kara Creator Launcher", body)


@app.post("/run")
def run_pipeline() -> Response:
    song_name_raw = request.form.get("song_name", "")
    safe_name = slugify(song_name_raw)

    audio_file = request.files.get("audio_file")
    lyrics_file = request.files.get("lyrics_file")

    if audio_file is None or not audio_file.filename:
        return render_error("No audio file was uploaded.")

    if lyrics_file is None or not lyrics_file.filename:
        return render_error("No lyrics file was uploaded.")

    incoming_dir = PROJECT_ROOT / "incoming" / safe_name
    incoming_dir.mkdir(parents=True, exist_ok=True)

    audio_path = incoming_dir / "vocals.mp3"
    lyrics_path = incoming_dir / "lyrics.txt"

    audio_file.save(audio_path)
    lyrics_file.save(lyrics_path)

    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "run_lyrics_aligner_pipeline.py"),
        "--audio",
        str(audio_path),
        "--lyrics",
        str(lyrics_path),
        "--name",
        safe_name,
    ]

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    log_text = completed.stdout or ""
    run_dir = PROJECT_ROOT / "alignment_lab" / "runs" / safe_name
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / f"{safe_name}-pipeline-last-run.log"
    log_path.write_text(log_text, encoding="utf-8")

    if completed.returncode != 0:
        return render_pipeline_failure(
            safe_name=safe_name,
            started_at=started_at,
            command=command,
            log_text=log_text,
            log_path=log_path,
        )

    draft_path = PROJECT_ROOT / "outputs" / f"{safe_name}-draft-lyrics-aligner-v3.json"
    word_review_path = PROJECT_ROOT / "outputs" / f"{safe_name}-word-review-lyrics-aligner.json"
    prepared_audio_path = PROJECT_ROOT / "alignment_lab" / "runs" / safe_name / "audio" / f"{safe_name}.mp3"
    manifest_path = PROJECT_ROOT / "alignment_lab" / "runs" / safe_name / f"{safe_name}-run-manifest.json"

    return render_pipeline_success(
        safe_name=safe_name,
        started_at=started_at,
        log_text=log_text,
        log_path=log_path,
        draft_path=draft_path,
        word_review_path=word_review_path,
        prepared_audio_path=prepared_audio_path,
        manifest_path=manifest_path,
    )


def render_error(message: str) -> Response:
    body = f"""
<h1>Pipeline could not start</h1>
<div class="panel">
  <p>{escape(message)}</p>
  <a class="button-link" href="/">Back to launcher</a>
</div>
"""
    return render_page("Pipeline error", body)


def render_pipeline_failure(
    *,
    safe_name: str,
    started_at: str,
    command: list[str],
    log_text: str,
    log_path: Path,
) -> Response:
    missing_path = PROJECT_ROOT / "alignment_lab" / "singing-aligners" / "lyrics-aligner" / "files" / f"kara_{safe_name}_missing_words.txt"

    missing_words_html = ""

    if missing_path.exists():
        missing_words = missing_path.read_text(encoding="utf-8", errors="replace")
        missing_words_html = f"""
<div class="panel">
  <h2>Missing pronunciations</h2>
  <p>The pipeline stopped because some words need custom pronunciations.</p>
  <pre>{escape(missing_words)}</pre>
  <p class="path">Missing word file: {escape(missing_path)}</p>
</div>
"""

    body = f"""
<h1>Pipeline failed</h1>

<div class="panel">
  <p><strong>Song:</strong> {escape(safe_name)}</p>
  <p><strong>Started:</strong> {escape(started_at)}</p>
  <p class="path"><strong>Log file:</strong> {escape(log_path)}</p>
  <a class="button-link" href="/">Back to launcher</a>
</div>

{missing_words_html}

<div class="panel">
  <h2>Command</h2>
  <pre>{escape(" ".join(command))}</pre>
</div>

<div class="panel">
  <h2>Log</h2>
  <pre>{escape(log_text)}</pre>
</div>
"""
    return render_page("Pipeline failed", body)


def file_link(path: Path, label: str) -> str:
    if not path.exists():
        return f"<p class='path'>{escape(label)}: {escape(path)} <span class='small'>(not found)</span></p>"

    return (
        f"<p class='path'>{escape(label)}: {escape(path)}<br>"
        f"<a class='button-link' href='/project-file?path={escape(str(path))}' target='_blank'>Open {escape(label)}</a></p>"
    )


def render_pipeline_success(
    *,
    safe_name: str,
    started_at: str,
    log_text: str,
    log_path: Path,
    draft_path: Path,
    word_review_path: Path,
    prepared_audio_path: Path,
    manifest_path: Path,
) -> Response:
    body = f"""
<h1>Draft created</h1>

<div class="panel">
  <p><strong>Song:</strong> {escape(safe_name)}</p>
  <p><strong>Started:</strong> {escape(started_at)}</p>
  <p>
    The draft JSON has been created. Open the editor, then load the prepared audio file and draft JSON shown below.
  </p>

  <a class="button-link good" href="/editor" target="_blank">Open draft editor</a>
  <a class="button-link" href="/">Create another draft</a>
</div>

<div class="panel">
  <h2>Files to load in the editor</h2>
  <p class="path"><strong>Audio:</strong><br>{escape(prepared_audio_path)}</p>
  <p class="path"><strong>Draft JSON:</strong><br>{escape(draft_path)}</p>
</div>

<div class="panel">
  <h2>Generated files</h2>
  {file_link(draft_path, "Draft JSON")}
  {file_link(word_review_path, "Word review JSON")}
  {file_link(manifest_path, "Run manifest")}
  {file_link(log_path, "Pipeline log")}
</div>

<div class="panel">
  <h2>Pipeline log</h2>
  <pre>{escape(log_text)}</pre>
</div>
"""
    return render_page("Draft created", body)


@app.get("/editor")
def editor() -> Response:
    editor_path = PROJECT_ROOT / "tools" / "edit_karaoke_draft.html"

    if not editor_path.exists():
        abort(404)

    return send_file(editor_path)


@app.get("/project-file")
def project_file():
    raw_path = request.args.get("path", "")

    if not raw_path:
        abort(400)

    path = Path(raw_path).resolve()

    if not is_within_project(path):
        abort(403)

    if not path.exists() or not path.is_file():
        abort(404)

    return send_file(path)


def main() -> int:
    print("")
    print("Kara Creator Launcher")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Open: http://127.0.0.1:{PORT}")
    print("")
    print("Press Ctrl+C to stop the launcher.")
    print("")

    app.run(host="127.0.0.1", port=PORT, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())