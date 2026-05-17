from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_diagnostics(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(dict(row))
    return rows


def safe_existing_file(raw_path: Any) -> Path | None:
    if not raw_path:
        return None
    path = Path(str(raw_path)).expanduser()
    try:
        path = path.resolve()
    except Exception:
        return None
    if path.exists() and path.is_file():
        return path
    return None


def guess_word_review_path(draft: dict[str, Any]) -> Path | None:
    raw = draft.get("source", {}).get("word_review_json")
    return safe_existing_file(raw)


class EditorRecoveryServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], *, args: argparse.Namespace) -> None:
        super().__init__(server_address, handler_class)
        self.args = args
        self.root = project_root()
        self.tools_dir = self.root / "tools"
        self.outputs_dir = self.root / "outputs"
        self.aligner_dir = Path(args.aligner_dir).resolve()
        self.vad_threshold = str(args.vad_threshold)
        self.audio_path = safe_existing_file(args.audio)
        self.draft_path = safe_existing_file(args.draft)
        self.diagnostics_path = safe_existing_file(args.diagnostics)
        self.last_word_review_path: Path | None = None
        self.last_draft_path: Path | None = self.draft_path


def response_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def response_text(handler: BaseHTTPRequestHandler, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
    data = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    log = "Running:\n" + " ".join(f'\"{part}\"' if " " in str(part) else str(part) for part in command) + "\n\n"
    log += completed.stdout or ""
    log += f"\nExit code: {completed.returncode}\n"
    return completed.returncode, log


class Handler(BaseHTTPRequestHandler):
    server: EditorRecoveryServer

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the PowerShell window readable.
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in {"/", "/editor"}:
            editor_path = self.server.tools_dir / "edit_karaoke_draft.html"
            if not editor_path.exists():
                response_text(self, f"Editor file not found: {editor_path}", 404)
                return
            response_text(self, editor_path.read_text(encoding="utf-8"), 200, "text/html; charset=utf-8")
            return

        if path == "/api/context":
            self.handle_context()
            return

        if path == "/api/audio":
            raw = query.get("path", [str(self.server.audio_path or "")])[0]
            audio_path = safe_existing_file(raw)
            if not audio_path:
                response_text(self, "Audio file not found.", 404)
                return
            self.serve_file(audio_path)
            return

        if path == "/api/json":
            raw = query.get("path", [""])[0]
            json_path = safe_existing_file(raw)
            if not json_path:
                response_json(self, {"ok": False, "error": "JSON file not found."}, 404)
                return
            response_json(self, {"ok": True, "data": load_json(json_path), "path": str(json_path)})
            return

        response_text(self, "Not found.", 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/recover":
            self.handle_recover()
            return
        response_text(self, "Not found.", 404)

    def serve_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with path.open("rb") as file:
            while True:
                chunk = file.read(1024 * 256)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def handle_context(self) -> None:
        draft_path = self.server.last_draft_path or self.server.draft_path
        audio_path = self.server.audio_path
        diagnostics_path = self.server.diagnostics_path
        draft: dict[str, Any] | None = None
        word_review_path: Path | None = self.server.last_word_review_path

        if draft_path and draft_path.exists():
            try:
                draft = load_json(draft_path)
                if word_review_path is None:
                    word_review_path = guess_word_review_path(draft)
            except Exception as error:
                response_json(self, {"ok": False, "error": f"Could not read draft: {error}"}, 500)
                return

        response_json(
            self,
            {
                "ok": True,
                "context": {"vad_threshold": self.server.vad_threshold},
                "draft": draft,
                "draft_path": str(draft_path) if draft_path else "",
                "draft_name": draft_path.name if draft_path else "",
                "audio_path": str(audio_path) if audio_path else "",
                "audio_name": audio_path.name if audio_path else "",
                "audio_url": f"/api/audio?path={urllib.parse.quote(str(audio_path))}" if audio_path else "",
                "diagnostics_path": str(diagnostics_path) if diagnostics_path else "",
                "word_review_path": str(word_review_path) if word_review_path else "",
                "diagnostics_rows": read_diagnostics(diagnostics_path),
            },
        )

    def handle_recover(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as error:
            response_json(self, {"ok": False, "error": f"Could not read request JSON: {error}"}, 400)
            return

        draft_path = safe_existing_file(payload.get("draft_path")) or self.server.last_draft_path or self.server.draft_path
        diagnostics_path = safe_existing_file(payload.get("diagnostics_path")) or self.server.diagnostics_path
        word_review_path = safe_existing_file(payload.get("word_review_path"))
        line_ids = [str(item).strip() for item in payload.get("line_ids", []) if str(item).strip()]
        vad_threshold = str(payload.get("vad_threshold") or self.server.vad_threshold or "0")

        if not draft_path or not draft_path.exists():
            response_json(self, {"ok": False, "error": "Draft path is missing or does not exist."}, 400)
            return
        if not diagnostics_path or not diagnostics_path.exists():
            response_json(self, {"ok": False, "error": "Diagnostics path is missing or does not exist."}, 400)
            return
        if not line_ids:
            response_json(self, {"ok": False, "error": "No line IDs were selected for recovery."}, 400)
            return

        try:
            draft_data = load_json(draft_path)
            if word_review_path is None:
                word_review_path = guess_word_review_path(draft_data)
        except Exception as error:
            response_json(self, {"ok": False, "error": f"Could not read draft JSON: {error}"}, 500)
            return

        if not word_review_path or not word_review_path.exists():
            response_json(self, {"ok": False, "error": "Could not find the source word-review JSON. The draft should contain source.word_review_json."}, 400)
            return

        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = draft_path.stem
        out_word_review = self.server.outputs_dir / f"{base}-selected-recovery-{stamp}-word-review.json"
        temp_draft = self.server.outputs_dir / f"{base}-selected-recovery-{stamp}-temp-draft.json"
        final_draft = self.server.outputs_dir / f"{base}-selected-recovery-{stamp}-raw-review.json"

        recovery_tool = self.server.tools_dir / "run_local_alignment_recovery.py"
        raw_builder = self.server.tools_dir / "build_review_draft_from_word_review.py"
        if not recovery_tool.exists():
            response_json(self, {"ok": False, "error": f"Missing tool: {recovery_tool}"}, 500)
            return
        if not raw_builder.exists():
            response_json(self, {"ok": False, "error": f"Missing tool: {raw_builder}"}, 500)
            return

        command = [
            sys.executable,
            str(recovery_tool),
            "--draft",
            str(draft_path),
            "--diagnostics",
            str(diagnostics_path),
            "--word-review",
            str(word_review_path),
            "--out-word-review",
            str(out_word_review),
            "--out-draft",
            str(temp_draft),
            "--aligner-dir",
            str(self.server.aligner_dir),
            "--vad-threshold",
            vad_threshold,
        ]
        for line_id in line_ids:
            command.extend(["--line-id", line_id])

        code, log = run_command(command, self.server.root)
        if code != 0:
            response_json(self, {"ok": False, "error": "Local recovery failed.", "log": log}, 500)
            return

        command2 = [
            sys.executable,
            str(raw_builder),
            "--word-review",
            str(out_word_review),
            "--out",
            str(final_draft),
        ]
        code2, log2 = run_command(command2, self.server.root)
        full_log = log + "\n" + log2
        if code2 != 0:
            response_json(self, {"ok": False, "error": "Raw-review rebuild failed.", "log": full_log}, 500)
            return

        try:
            recovered_draft = load_json(final_draft)
        except Exception as error:
            response_json(self, {"ok": False, "error": f"Recovery finished but could not read final draft: {error}", "log": full_log}, 500)
            return

        self.server.last_word_review_path = out_word_review
        self.server.last_draft_path = final_draft

        response_json(
            self,
            {
                "ok": True,
                "draft": recovered_draft,
                "draft_path": str(final_draft),
                "word_review_path": str(out_word_review),
                "temp_draft_path": str(temp_draft),
                "diagnostics_rows": read_diagnostics(diagnostics_path),
                "log": full_log,
            },
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the Kara Creator editor with selected local recovery support.")
    parser.add_argument("--audio", help="Path to the vocal MP3 to auto-load.")
    parser.add_argument("--draft", help="Path to the draft JSON to auto-load.")
    parser.add_argument("--diagnostics", help="Path to the diagnostics CSV to auto-load.")
    parser.add_argument("--aligner-dir", default=r"C:\Users\mark\kara-creator\alignment_lab\singing-aligners\lyrics-aligner")
    parser.add_argument("--vad-threshold", default="0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    port = args.port
    server = EditorRecoveryServer((HOST, port), Handler, args=args)
    url = f"http://{HOST}:{port}/"
    print("Kara Creator editor recovery server")
    print(f"URL:         {url}")
    print(f"Project:     {server.root}")
    print(f"Audio:       {server.audio_path or 'not set'}")
    print(f"Draft:       {server.draft_path or 'not set'}")
    print(f"Diagnostics: {server.diagnostics_path or 'not set'}")
    print("Press Ctrl+C to stop the server.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
