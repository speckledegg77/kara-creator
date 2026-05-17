from __future__ import annotations

import base64
import json
import mimetypes
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any


APP_TITLE = "Kara Creator Launcher"
DEFAULT_ALIGNER_DIR = r"C:\Users\mark\kara-creator\alignment_lab\singing-aligners\lyrics-aligner"
VAD_OPTIONS = ["0", "0.05", "0.1", "0.2"]
SETTINGS_FILE_NAME = ".kara_creator_launcher_settings.json"


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "song"


def quote_command(command: list[str]) -> str:
    parts: list[str] = []

    for item in command:
        text = str(item)
        if not text:
            parts.append('""')
        elif any(char.isspace() for char in text) or any(char in text for char in ['`', '"', "'"]):
            parts.append('"' + text.replace('"', '\\"') + '"')
        else:
            parts.append(text)

    return " ".join(parts)


class KaraCreatorLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.project_root = Path(__file__).resolve().parents[1]
        self.outputs_dir = self.project_root / "outputs"
        self.tools_dir = self.project_root / "tools"
        self.config_dir = self.project_root / "config"
        self.custom_pronunciations_path = self.config_dir / "custom_pronunciations.json"
        self.settings_path = self.project_root / SETTINGS_FILE_NAME

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.current_process: subprocess.Popen[str] | None = None
        self.status_popup: tk.Toplevel | None = None
        self.status_popup_text: ScrolledText | None = None
        self.current_log_file: Path | None = None
        self.last_draft_path: Path | None = None
        self.last_word_review_path: Path | None = None
        self.last_raw_review_draft_path: Path | None = None
        self.last_diagnostics_csv_path: Path | None = None

        self.title(APP_TITLE)
        self.geometry("1040x860")
        self.minsize(900, 720)

        self.song_name_var = tk.StringVar()
        self.audio_path_var = tk.StringVar()
        self.lyrics_path_var = tk.StringVar()
        self.use_lyrics_editor_var = tk.BooleanVar(value=False)
        self.lyrics_editor_status_var = tk.StringVar(value="No pasted lyrics saved yet.")
        self.lyrics_editor_has_unsaved_changes = False
        self.vad_threshold_var = tk.StringVar(value="0")
        self.aligner_dir_var = tk.StringVar(value=DEFAULT_ALIGNER_DIR)
        self.status_var = tk.StringVar(value="Ready.")
        self.current_task_var = tk.StringVar(value="No command running.")
        self.current_state_var = tk.StringVar(value="Ready")
        self.elapsed_var = tk.StringVar(value="Elapsed: 0.0s")
        self.last_result_var = tk.StringVar(value="Last result: none yet.")
        self.show_completion_popup_var = tk.BooleanVar(value=True)
        self.command_started_at: float | None = None
        self.local_recovery_line_ids_var = tk.StringVar()
        self.local_recovery_min_severity_var = tk.StringVar(value="70")
        self.keep_previous_var = tk.BooleanVar(value=False)
        self.missing_words_path_var = tk.StringVar()
        self.custom_pronunciations_path_var = tk.StringVar(value=str(self.custom_pronunciations_path))
        self.pronunciation_status_var = tk.StringVar(value="No missing words loaded yet.")
        self.pronunciation_word_var = tk.StringVar()
        self.pronunciation_value_var = tk.StringVar()

        self._load_settings()
        self._build_ui()
        if self.lyrics_path_var.get().strip():
            self._load_selected_lyrics_into_editor(silent=True)
        self._refresh_predicted_paths()
        self.after(100, self._poll_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.geometry("1080x780")
        self.minsize(960, 650)

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky=tk.EW)
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="Kara Creator Launcher", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, sticky=tk.W)

        subtitle = ttk.Label(
            header,
            text="Choose an isolated vocal MP3 and exact lyrics, then run the local alignment pipeline.",
        )
        subtitle.grid(row=1, column=0, sticky=tk.W, pady=(2, 8))

        top_status_frame = ttk.LabelFrame(outer, text="Current status", padding=(10, 8))
        top_status_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        top_status_frame.columnconfigure(1, weight=1)
        top_status_frame.columnconfigure(3, weight=1)

        ttk.Label(top_status_frame, text="Task").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=2)
        ttk.Label(top_status_frame, textvariable=self.current_task_var, wraplength=360).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(top_status_frame, text="State").grid(row=0, column=2, sticky=tk.W, padx=(20, 6), pady=2)
        ttk.Label(top_status_frame, textvariable=self.current_state_var).grid(row=0, column=3, sticky=tk.W, pady=2)

        ttk.Label(top_status_frame, text="Elapsed").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=2)
        ttk.Label(top_status_frame, textvariable=self.elapsed_var).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(top_status_frame, text="Last result").grid(row=1, column=2, sticky=tk.W, padx=(20, 6), pady=2)
        ttk.Label(top_status_frame, textvariable=self.last_result_var, wraplength=520).grid(row=1, column=3, sticky=tk.W, pady=2)

        self.progress_bar = ttk.Progressbar(top_status_frame, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=(6, 0))

        action_frame = ttk.LabelFrame(outer, text="Actions", padding=(10, 8))
        action_frame.grid(row=2, column=0, sticky=tk.EW, pady=(0, 8))
        for col in range(10):
            action_frame.columnconfigure(col, weight=0)
        action_frame.columnconfigure(10, weight=1)

        self.run_button = ttk.Button(action_frame, text="1. Run pipeline", command=self._run_pipeline)
        self.run_button.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=3)

        self.raw_review_button = ttk.Button(action_frame, text="2. Build raw review", command=self._build_raw_review)
        self.raw_review_button.grid(row=0, column=1, sticky=tk.W, padx=(0, 8), pady=3)

        self.diagnostics_button = ttk.Button(action_frame, text="3. Run diagnostics", command=self._run_diagnostics)
        self.diagnostics_button.grid(row=0, column=2, sticky=tk.W, padx=(0, 8), pady=3)

        self.recovery_button = ttk.Button(action_frame, text="4. Run local recovery", command=self._run_local_recovery)
        self.recovery_button.grid(row=0, column=3, sticky=tk.W, padx=(0, 8), pady=3)

        self.open_raw_editor_button = ttk.Button(action_frame, text="Open raw editor", command=self._open_raw_editor)
        self.open_raw_editor_button.grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=3)

        self.open_editor_button = ttk.Button(action_frame, text="Open editor", command=self._open_editor)
        self.open_editor_button.grid(row=1, column=1, sticky=tk.W, padx=(0, 8), pady=3)

        self.open_outputs_button = ttk.Button(action_frame, text="Open outputs", command=self._open_outputs_folder)
        self.open_outputs_button.grid(row=1, column=2, sticky=tk.W, padx=(0, 8), pady=3)

        self.open_draft_button = ttk.Button(action_frame, text="Open draft JSON", command=self._open_current_draft)
        self.open_draft_button.grid(row=1, column=3, sticky=tk.W, padx=(0, 8), pady=3)

        ttk.Button(action_frame, text="Status window", command=lambda: self._open_run_status_window("Status")).grid(
            row=1,
            column=4,
            sticky=tk.W,
            padx=(0, 8),
            pady=3,
        )
        ttk.Button(action_frame, text="Stop", command=self._stop_current_process).grid(row=1, column=5, sticky=tk.W, pady=3)

        main_tabs = ttk.Notebook(outer)
        main_tabs.grid(row=3, column=0, sticky=tk.NSEW)

        song_tab = ttk.Frame(main_tabs, padding=12)
        run_tab = ttk.Frame(main_tabs, padding=12)
        pron_tab = ttk.Frame(main_tabs, padding=12)
        log_tab = ttk.Frame(main_tabs, padding=12)
        main_tabs.add(song_tab, text="Song and lyrics")
        main_tabs.add(run_tab, text="Outputs and recovery")
        main_tabs.add(pron_tab, text="Pronunciations")
        main_tabs.add(log_tab, text="Log")

        song_tab.columnconfigure(0, weight=1)
        song_tab.rowconfigure(1, weight=1)

        input_frame = ttk.LabelFrame(song_tab, text="Song input", padding=12)
        input_frame.grid(row=0, column=0, sticky=tk.EW)
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Song name").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        song_entry = ttk.Entry(input_frame, textvariable=self.song_name_var)
        song_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=4)
        song_entry.bind("<KeyRelease>", lambda _event: self._refresh_predicted_paths())

        ttk.Label(input_frame, text="Vocal MP3").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(input_frame, textvariable=self.audio_path_var).grid(row=1, column=1, sticky=tk.EW, pady=4)
        ttk.Button(input_frame, text="Browse...", command=self._browse_audio).grid(row=1, column=2, padx=(8, 0), pady=4)

        ttk.Label(input_frame, text="Lyrics TXT").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(input_frame, textvariable=self.lyrics_path_var).grid(row=2, column=1, sticky=tk.EW, pady=4)
        ttk.Button(input_frame, text="Browse...", command=self._browse_lyrics).grid(row=2, column=2, padx=(8, 0), pady=4)

        ttk.Label(input_frame, text="VAD threshold").grid(row=3, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        vad_row = ttk.Frame(input_frame)
        vad_row.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=4)
        vad_combo = ttk.Combobox(vad_row, textvariable=self.vad_threshold_var, values=VAD_OPTIONS, width=10)
        vad_combo.pack(side=tk.LEFT)
        ttk.Label(vad_row, text="Use 0 for clean stems. Try 0.1 or 0.2 for bleed or long instrumental gaps.").pack(
            side=tk.LEFT,
            padx=(12, 0),
        )

        ttk.Label(input_frame, text="lyrics-aligner folder").grid(row=4, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(input_frame, textvariable=self.aligner_dir_var).grid(row=4, column=1, sticky=tk.EW, pady=4)
        ttk.Button(input_frame, text="Browse...", command=self._browse_aligner_dir).grid(row=4, column=2, padx=(8, 0), pady=4)

        ttk.Checkbutton(
            input_frame,
            text="Keep previous run files for this song name",
            variable=self.keep_previous_var,
        ).grid(row=5, column=1, sticky=tk.W, pady=(4, 0))

        lyrics_frame = ttk.LabelFrame(song_tab, text="Lyrics", padding=8)
        lyrics_frame.grid(row=1, column=0, sticky=tk.NSEW, pady=(10, 0))
        lyrics_frame.rowconfigure(0, weight=1)
        lyrics_frame.columnconfigure(0, weight=1)

        lyrics_tabs = ttk.Notebook(lyrics_frame)
        lyrics_tabs.grid(row=0, column=0, sticky=tk.NSEW)

        lyrics_file_tab = ttk.Frame(lyrics_tabs, padding=10)
        lyrics_editor_tab = ttk.Frame(lyrics_tabs, padding=10)
        lyrics_tabs.add(lyrics_file_tab, text="Lyrics file")
        lyrics_tabs.add(lyrics_editor_tab, text="Paste / edit lyrics")

        lyrics_file_tab.columnconfigure(1, weight=1)
        ttk.Label(
            lyrics_file_tab,
            text="Use this tab when your lyrics are already saved as a .txt file.",
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))
        ttk.Label(lyrics_file_tab, text="Current lyrics TXT").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(lyrics_file_tab, textvariable=self.lyrics_path_var).grid(row=1, column=1, sticky=tk.EW, pady=4)
        ttk.Button(lyrics_file_tab, text="Browse...", command=self._browse_lyrics).grid(row=1, column=2, padx=(8, 0), pady=4)
        ttk.Button(
            lyrics_file_tab,
            text="Load selected file into editor tab",
            command=lambda: self._load_selected_lyrics_into_editor(silent=False),
        ).grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        lyrics_editor_tab.columnconfigure(0, weight=1)
        lyrics_editor_tab.rowconfigure(1, weight=1)
        ttk.Label(
            lyrics_editor_tab,
            text="Paste or edit exact lyrics here. Blank lines create sections. A line containing . . . creates an instrumental display line.",
            wraplength=850,
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        self.lyrics_editor = ScrolledText(lyrics_editor_tab, wrap=tk.WORD, height=16, font=("Consolas", 10))
        self.lyrics_editor.grid(row=1, column=0, sticky=tk.NSEW)
        self.lyrics_editor.bind("<KeyRelease>", self._mark_lyrics_editor_unsaved)

        lyrics_editor_buttons = ttk.Frame(lyrics_editor_tab)
        lyrics_editor_buttons.grid(row=2, column=0, sticky=tk.EW, pady=(8, 0))
        ttk.Checkbutton(
            lyrics_editor_buttons,
            text="Use pasted/edited lyrics when running pipeline",
            variable=self.use_lyrics_editor_var,
        ).pack(side=tk.LEFT)
        ttk.Button(
            lyrics_editor_buttons,
            text="Save pasted lyrics for this song",
            command=self._save_lyrics_editor_to_default,
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(
            lyrics_editor_buttons,
            text="Save lyrics as...",
            command=self._save_lyrics_editor_as,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            lyrics_editor_buttons,
            text="Clear pasted lyrics",
            command=self._clear_lyrics_editor,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(lyrics_editor_tab, textvariable=self.lyrics_editor_status_var, wraplength=850).grid(
            row=3,
            column=0,
            sticky=tk.W,
            pady=(6, 0),
        )

        run_tab.columnconfigure(0, weight=1)
        run_tab.rowconfigure(2, weight=1)

        path_frame = ttk.LabelFrame(run_tab, text="Predicted output files", padding=12)
        path_frame.grid(row=0, column=0, sticky=tk.EW)
        path_frame.columnconfigure(0, weight=1)

        self.slug_label = ttk.Label(path_frame, text="")
        self.slug_label.grid(row=0, column=0, sticky=tk.W, pady=2)

        self.word_review_label = ttk.Label(path_frame, text="", wraplength=900)
        self.word_review_label.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.raw_review_label = ttk.Label(path_frame, text="", wraplength=900)
        self.raw_review_label.grid(row=2, column=0, sticky=tk.W, pady=2)

        self.draft_label = ttk.Label(path_frame, text="", wraplength=900)
        self.draft_label.grid(row=3, column=0, sticky=tk.W, pady=2)

        self.diagnostics_label = ttk.Label(path_frame, text="", wraplength=900)
        self.diagnostics_label.grid(row=4, column=0, sticky=tk.W, pady=2)

        recovery_frame = ttk.LabelFrame(run_tab, text="Optional local alignment recovery", padding=12)
        recovery_frame.grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        recovery_frame.columnconfigure(1, weight=1)

        ttk.Label(recovery_frame, text="Line IDs").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(recovery_frame, textvariable=self.local_recovery_line_ids_var).grid(row=0, column=1, sticky=tk.EW, pady=4)
        ttk.Label(recovery_frame, text="Leave blank to use diagnostics candidates. Example: line-0012,line-0040").grid(
            row=1,
            column=1,
            sticky=tk.W,
            pady=(0, 4),
        )

        ttk.Label(recovery_frame, text="Min severity").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(recovery_frame, textvariable=self.local_recovery_min_severity_var, width=10).grid(
            row=2,
            column=1,
            sticky=tk.W,
            pady=4,
        )

        ttk.Checkbutton(
            recovery_frame,
            text="Show pop-up when a command finishes or fails",
            variable=self.show_completion_popup_var,
        ).grid(row=3, column=1, sticky=tk.W, pady=(4, 0))

        summary_frame = ttk.LabelFrame(run_tab, text="Workflow", padding=12)
        summary_frame.grid(row=2, column=0, sticky=tk.NSEW, pady=(10, 0))
        summary_text = (
            "Recommended order:\n"
            "1. Choose audio and lyrics on the Song and lyrics tab.\n"
            "2. Run pipeline.\n"
            "3. Run diagnostics.\n"
            "4. If diagnostics finds clear local realignment candidates, run local recovery.\n"
            "5. Open the editor and polish timings.\n\n"
            "The status window opens automatically when a command runs. The Log tab keeps the same output inside the launcher."
        )
        ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT, wraplength=900).pack(anchor=tk.W)

        pron_tab.columnconfigure(0, weight=1)
        pron_tab.rowconfigure(1, weight=1)

        pron_help = ttk.Label(
            pron_tab,
            text=(
                "If lyrics-aligner reports missing words, load them here, create a pronunciation, "
                "save it to config\\custom_pronunciations.json, then rerun the pipeline. "
                "Suggestions are a starting point only, so edit them if they look wrong."
            ),
            wraplength=930,
        )
        pron_help.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))

        pron_body = ttk.PanedWindow(pron_tab, orient=tk.HORIZONTAL)
        pron_body.grid(row=1, column=0, sticky=tk.NSEW)

        missing_frame = ttk.LabelFrame(pron_body, text="Missing words", padding=10)
        edit_frame = ttk.LabelFrame(pron_body, text="Create / edit pronunciation", padding=10)
        pron_body.add(missing_frame, weight=1)
        pron_body.add(edit_frame, weight=2)

        missing_frame.columnconfigure(0, weight=1)
        missing_frame.rowconfigure(3, weight=1)
        ttk.Label(missing_frame, text="Missing words file").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(missing_frame, textvariable=self.missing_words_path_var, wraplength=360).grid(
            row=1,
            column=0,
            sticky=tk.EW,
            pady=(2, 8),
        )
        missing_buttons = ttk.Frame(missing_frame)
        missing_buttons.grid(row=2, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(missing_buttons, text="Load missing words", command=lambda: self._load_missing_words_from_default(silent=False)).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        ttk.Button(missing_buttons, text="Open missing words file", command=self._open_missing_words_file).pack(side=tk.LEFT)

        self.missing_words_listbox = tk.Listbox(missing_frame, height=12, exportselection=False)
        self.missing_words_listbox.grid(row=3, column=0, sticky=tk.NSEW)
        self.missing_words_listbox.bind("<<ListboxSelect>>", self._on_missing_word_selected)

        edit_frame.columnconfigure(1, weight=1)
        ttk.Label(edit_frame, text="Custom pronunciations file").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Label(edit_frame, textvariable=self.custom_pronunciations_path_var, wraplength=520).grid(
            row=0,
            column=1,
            sticky=tk.EW,
            pady=4,
        )
        ttk.Button(edit_frame, text="Open file", command=self._open_custom_pronunciations_file).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(edit_frame, text="Word").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(edit_frame, textvariable=self.pronunciation_word_var).grid(row=1, column=1, sticky=tk.EW, pady=4)
        ttk.Button(edit_frame, text="Suggest", command=self._suggest_pronunciation_for_current_word).grid(row=1, column=2, padx=(8, 0), pady=4)

        ttk.Label(edit_frame, text="Pronunciation").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(edit_frame, textvariable=self.pronunciation_value_var).grid(row=2, column=1, sticky=tk.EW, pady=4)
        ttk.Button(edit_frame, text="Save pronunciation", command=self._save_current_pronunciation).grid(row=2, column=2, padx=(8, 0), pady=4)

        ttk.Label(
            edit_frame,
            text=(
                "Use space-separated phoneme symbols, like: F R AE K T AH L Z. "
                "After saving, rerun the pipeline."
            ),
            wraplength=680,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(8, 4))

        quick_frame = ttk.LabelFrame(edit_frame, text="Quick actions", padding=8)
        quick_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))
        ttk.Button(quick_frame, text="Add all loaded suggestions", command=self._save_all_loaded_suggestions).pack(side=tk.LEFT)
        ttk.Label(
            quick_frame,
            text="Only use this when the suggested pronunciations look sensible.",
            wraplength=500,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(edit_frame, textvariable=self.pronunciation_status_var, wraplength=680).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            pady=(10, 0),
        )

        log_tab.columnconfigure(0, weight=1)
        log_tab.rowconfigure(0, weight=1)
        log_frame = ttk.LabelFrame(log_tab, text="Command log", padding=8)
        log_frame.grid(row=0, column=0, sticky=tk.NSEW)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, height=18, font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)

        log_buttons = ttk.Frame(log_tab)
        log_buttons.grid(row=1, column=0, sticky=tk.EW, pady=(8, 0))
        self.status_label = ttk.Label(log_buttons, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT)
        ttk.Button(log_buttons, text="Clear log", command=self._clear_log).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(log_buttons, text="Open current log file", command=self._open_current_log_file).pack(side=tk.RIGHT)

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return

        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return

        self.song_name_var.set(str(data.get("song_name", "")))
        self.audio_path_var.set(str(data.get("audio_path", "")))
        self.lyrics_path_var.set(str(data.get("lyrics_path", "")))
        self.use_lyrics_editor_var.set(bool(data.get("use_lyrics_editor", False)))
        self.vad_threshold_var.set(str(data.get("vad_threshold", "0")))
        self.aligner_dir_var.set(str(data.get("aligner_dir", DEFAULT_ALIGNER_DIR)))
        self.local_recovery_line_ids_var.set(str(data.get("local_recovery_line_ids", "")))
        self.local_recovery_min_severity_var.set(str(data.get("local_recovery_min_severity", "70")))
        self.keep_previous_var.set(bool(data.get("keep_previous", False)))
        self.show_completion_popup_var.set(bool(data.get("show_completion_popup", True)))

    def _save_settings(self) -> None:
        data = {
            "song_name": self.song_name_var.get(),
            "audio_path": self.audio_path_var.get(),
            "lyrics_path": self.lyrics_path_var.get(),
            "use_lyrics_editor": self.use_lyrics_editor_var.get(),
            "vad_threshold": self.vad_threshold_var.get(),
            "aligner_dir": self.aligner_dir_var.get(),
            "local_recovery_line_ids": self.local_recovery_line_ids_var.get(),
            "local_recovery_min_severity": self.local_recovery_min_severity_var.get(),
            "keep_previous": self.keep_previous_var.get(),
            "show_completion_popup": self.show_completion_popup_var.get(),
        }

        try:
            self.settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_close(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(APP_TITLE, "A command is still running. Close anyway?"):
                return
            self._stop_current_process()
        if self.lyrics_editor_has_unsaved_changes and self.use_lyrics_editor_var.get():
            if messagebox.askyesno(APP_TITLE, "Save pasted/edited lyrics before closing?"):
                if not self._save_lyrics_editor_to_default():
                    return
        self._save_settings()
        self.destroy()

    def _browse_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose isolated vocal MP3",
            filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac"), ("All files", "*.*")],
        )
        if path:
            self.audio_path_var.set(path)
            if not self.song_name_var.get().strip():
                self.song_name_var.set(slugify(Path(path).parent.name or Path(path).stem))
            self._refresh_predicted_paths()

    def _browse_lyrics(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose exact lyrics TXT",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.lyrics_path_var.set(path)
            self._load_selected_lyrics_into_editor(silent=True)
            self._refresh_predicted_paths()

    def _mark_lyrics_editor_unsaved(self, _event: Any | None = None) -> None:
        self.lyrics_editor_has_unsaved_changes = True
        self.use_lyrics_editor_var.set(True)
        self.lyrics_editor_status_var.set("Pasted/edited lyrics have unsaved changes. They will be saved before the pipeline runs.")

    def _clear_lyrics_editor(self) -> None:
        self.lyrics_editor.delete("1.0", tk.END)
        self.lyrics_editor_has_unsaved_changes = True
        self.use_lyrics_editor_var.set(True)
        self.lyrics_editor_status_var.set("Lyrics editor cleared. Paste lyrics or load a file before running the pipeline.")

    def _load_selected_lyrics_into_editor(self, silent: bool = False) -> bool:
        raw_path = self.lyrics_path_var.get().strip()
        if not raw_path:
            if not silent:
                messagebox.showerror(APP_TITLE, "Choose a lyrics TXT file first.")
            return False

        path = Path(raw_path)
        if not path.exists():
            if not silent:
                messagebox.showerror(APP_TITLE, f"Lyrics file does not exist:\n{path}")
            return False

        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="cp1252")
            except Exception as error:
                if not silent:
                    messagebox.showerror(APP_TITLE, f"Could not read lyrics file:\n{path}\n\n{error}")
                return False
        except Exception as error:
            if not silent:
                messagebox.showerror(APP_TITLE, f"Could not read lyrics file:\n{path}\n\n{error}")
            return False

        self.lyrics_editor.delete("1.0", tk.END)
        self.lyrics_editor.insert("1.0", text)
        self.lyrics_editor_has_unsaved_changes = False
        self.lyrics_editor_status_var.set(f"Loaded into editor from: {path}")
        return True

    def _lyrics_editor_text(self) -> str:
        return self.lyrics_editor.get("1.0", tk.END).replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"

    def _default_lyrics_editor_path(self) -> Path:
        slug = self.current_slug()
        return self.project_root / "incoming" / slug / "lyrics.txt"

    def _save_lyrics_editor_to_default(self) -> bool:
        if not self.song_name_var.get().strip():
            messagebox.showerror(APP_TITLE, "Enter a song name before saving pasted lyrics.")
            return False

        text = self._lyrics_editor_text()
        if not text.strip():
            messagebox.showerror(APP_TITLE, "Paste or type lyrics before saving.")
            return False

        path = self._default_lyrics_editor_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"Could not save lyrics:\n{path}\n\n{error}")
            return False

        self.lyrics_path_var.set(str(path))
        self.use_lyrics_editor_var.set(True)
        self.lyrics_editor_has_unsaved_changes = False
        self.lyrics_editor_status_var.set(f"Saved pasted lyrics to: {path}")
        self._refresh_predicted_paths()
        return True

    def _save_lyrics_editor_as(self) -> None:
        text = self._lyrics_editor_text()
        if not text.strip():
            messagebox.showerror(APP_TITLE, "Paste or type lyrics before saving.")
            return

        initial_dir = self.project_root / "incoming" / self.current_slug()
        initial_dir.mkdir(parents=True, exist_ok=True)
        path_text = filedialog.asksaveasfilename(
            title="Save lyrics as TXT",
            initialdir=str(initial_dir),
            initialfile="lyrics.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path_text:
            return

        path = Path(path_text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"Could not save lyrics:\n{path}\n\n{error}")
            return

        self.lyrics_path_var.set(str(path))
        self.use_lyrics_editor_var.set(True)
        self.lyrics_editor_has_unsaved_changes = False
        self.lyrics_editor_status_var.set(f"Saved lyrics to: {path}")
        self._refresh_predicted_paths()

    def _prepare_lyrics_for_pipeline(self) -> bool:
        if self.use_lyrics_editor_var.get():
            return self._save_lyrics_editor_to_default()
        return True

    def _browse_aligner_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose lyrics-aligner folder")
        if path:
            self.aligner_dir_var.set(path)

    def _refresh_predicted_paths(self) -> None:
        slug = self.current_slug()
        draft = self.default_draft_path(slug)
        word_review = self.default_word_review_path(slug)
        raw_review = self.default_raw_review_draft_path(slug)
        diagnostics = self.default_diagnostics_csv_path(slug)

        self.slug_label.config(text=f"Song file name: {slug}")
        self.word_review_label.config(text=f"Word-review JSON: {word_review}")
        self.raw_review_label.config(text=f"Raw review draft: {raw_review}")
        self.draft_label.config(text=f"Standard draft JSON: {draft}")
        self.diagnostics_label.config(text=f"Diagnostics CSV: {diagnostics}")
        self.missing_words_path_var.set(str(self.default_missing_words_path(slug)))
        self.custom_pronunciations_path_var.set(str(self.custom_pronunciations_path))

        if self.last_draft_path is None:
            self.last_draft_path = draft
        if self.last_diagnostics_csv_path is None:
            self.last_diagnostics_csv_path = diagnostics

    def current_slug(self) -> str:
        return slugify(self.song_name_var.get())

    def default_draft_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-draft-lyrics-aligner-v3.json"

    def default_word_review_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-word-review-lyrics-aligner.json"

    def default_raw_review_draft_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-draft-raw-review.json"

    def default_raw_review_diagnostics_csv_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-raw-review-diagnostics.csv"

    def default_raw_review_diagnostics_summary_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-raw-review-diagnostics-summary.md"

    def default_diagnostics_csv_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-alignment-diagnostics.csv"

    def default_diagnostics_summary_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-alignment-diagnostics-summary.md"

    def default_missing_words_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        aligner_dir = Path(self.aligner_dir_var.get().strip() or DEFAULT_ALIGNER_DIR)
        return aligner_dir / "files" / f"kara_{slug}_missing_words.txt"

    def default_recovered_word_review_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-word-review-local-recovery.json"

    def default_recovered_draft_path(self, slug: str | None = None) -> Path:
        slug = slug or self.current_slug()
        return self.outputs_dir / f"{slug}-draft-local-recovery.json"

    def _validate_common(self) -> bool:
        if not self.song_name_var.get().strip():
            messagebox.showerror(APP_TITLE, "Enter a song name first.")
            return False

        audio_path = Path(self.audio_path_var.get().strip())
        lyrics_path = Path(self.lyrics_path_var.get().strip())
        aligner_dir = Path(self.aligner_dir_var.get().strip())

        if not audio_path.exists():
            messagebox.showerror(APP_TITLE, f"Audio file does not exist:\n{audio_path}")
            return False

        if not lyrics_path.exists():
            messagebox.showerror(APP_TITLE, f"Lyrics file does not exist:\n{lyrics_path}")
            return False

        if not aligner_dir.exists():
            messagebox.showerror(APP_TITLE, f"lyrics-aligner folder does not exist:\n{aligner_dir}")
            return False

        try:
            float(self.vad_threshold_var.get())
        except ValueError:
            messagebox.showerror(APP_TITLE, "VAD threshold must be a number, such as 0, 0.05, 0.1, or 0.2.")
            return False

        return True

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in [
            self.run_button,
            self.raw_review_button,
            self.diagnostics_button,
            self.recovery_button,
            self.open_raw_editor_button,
            self.open_editor_button,
            self.open_outputs_button,
            self.open_draft_button,
        ]:
            button.config(state=state)

    def _safe_label_for_file(self, label: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_") or "command"

    def _open_run_status_window(self, label: str) -> None:
        if self.status_popup is not None and self.status_popup.winfo_exists():
            self.status_popup.deiconify()
            self.status_popup.lift()
            self.status_popup.title(f"Kara Creator Status - {label}")
            return

        popup = tk.Toplevel(self)
        popup.title(f"Kara Creator Status - {label}")
        popup.geometry("920x420")
        popup.minsize(760, 320)
        popup.protocol("WM_DELETE_WINDOW", popup.withdraw)

        frame = ttk.Frame(popup, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text="Current task").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=3)
        ttk.Label(frame, textvariable=self.current_task_var).grid(row=0, column=1, sticky=tk.W, pady=3)
        ttk.Label(frame, text="State").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=3)
        ttk.Label(frame, textvariable=self.current_state_var).grid(row=1, column=1, sticky=tk.W, pady=3)
        ttk.Label(frame, text="Elapsed").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=3)
        ttk.Label(frame, textvariable=self.elapsed_var).grid(row=2, column=1, sticky=tk.W, pady=3)
        ttk.Label(frame, text="Last result").grid(row=3, column=0, sticky=tk.W, padx=(0, 8), pady=3)
        ttk.Label(frame, textvariable=self.last_result_var, wraplength=760).grid(row=3, column=1, sticky=tk.W, pady=3)

        ttk.Label(frame, text="Live output").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 3))
        self.status_popup_text = ScrolledText(frame, wrap=tk.WORD, height=12, font=("Consolas", 10))
        self.status_popup_text.grid(row=5, column=0, columnspan=2, sticky=tk.NSEW)

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
        ttk.Button(buttons, text="Hide this window", command=popup.withdraw).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Stop running command", command=self._stop_current_process).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Open log file", command=self._open_current_log_file).pack(side=tk.LEFT)

        self.status_popup = popup

    def _open_current_log_file(self) -> None:
        if not self.current_log_file or not self.current_log_file.exists():
            messagebox.showinfo(APP_TITLE, "No command log file exists yet.")
            return
        os.startfile(str(self.current_log_file))  # type: ignore[attr-defined]

    def _new_log_file(self, label: str) -> Path:
        slug = self.current_slug()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_dir = self.outputs_dir / "launcher-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{stamp}-{slug}-{self._safe_label_for_file(label)}.log"

    def _write_log_file(self, text: str) -> None:
        if self.current_log_file is None:
            return
        try:
            with self.current_log_file.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(text)
        except Exception:
            pass

    def _run_command_async(self, command: list[str], label: str, on_success: Any | None = None) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo(APP_TITLE, "A command is already running.")
            return

        self._save_settings()
        self._set_controls_enabled(False)

        self.command_started_at = time.time()
        self.current_task_var.set(label)
        self.current_state_var.set("Running")
        self.elapsed_var.set("Elapsed: 0.0s")
        self.last_result_var.set("Last result: command is running.")
        self.status_var.set(f"Running: {label}")

        self.current_log_file = self._new_log_file(label)
        self._open_run_status_window(label)
        if self.status_popup_text is not None:
            self.status_popup_text.delete("1.0", tk.END)

        try:
            self.progress_bar.start(12)
        except Exception:
            pass

        self._append_log("\n" + "=" * 80 + "\n")
        self._append_log(f"{label}\n")
        self._append_log(f"Log file: {self.current_log_file}\n")
        self._append_log(quote_command(command) + "\n\n")

        def worker() -> None:
            started = time.time()
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(self.project_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                self.current_process = process

                assert process.stdout is not None
                for line in process.stdout:
                    self.log_queue.put(line)

                return_code = process.wait()
                elapsed = time.time() - started

                if return_code == 0:
                    self.log_queue.put(f"\nFinished successfully in {elapsed:.1f}s.\n")
                    self.log_queue.put({"type": "success", "label": label, "on_success": on_success})  # type: ignore[arg-type]
                else:
                    self.log_queue.put(f"\nCommand failed with exit code {return_code}.\n")
                    self.log_queue.put({"type": "failure", "label": label})  # type: ignore[arg-type]
            except Exception as error:
                self.log_queue.put(f"\nCommand could not start or crashed: {error}\n")
                self.log_queue.put({"type": "failure", "label": label})  # type: ignore[arg-type]
            finally:
                self.current_process = None

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _poll_log_queue(self) -> None:
        if self.command_started_at is not None:
            elapsed = time.time() - self.command_started_at
            self.elapsed_var.set(f"Elapsed: {elapsed:.1f}s")

        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, dict):
                    event_type = item.get("type")
                    label = item.get("label", "command")
                    elapsed_text = self.elapsed_var.get().replace("Elapsed: ", "")
                    try:
                        self.progress_bar.stop()
                    except Exception:
                        pass
                    self.command_started_at = None

                    if event_type == "success":
                        on_success = item.get("on_success")
                        if callable(on_success):
                            on_success()
                        self.current_state_var.set("Finished successfully")
                        self.last_result_var.set(f"Last result: {label} finished successfully in {elapsed_text}. Log file: {self.current_log_file}")
                        self.status_var.set(f"Finished: {label}")
                        if self.show_completion_popup_var.get():
                            messagebox.showinfo(APP_TITLE, f"{label} finished successfully.")
                    elif event_type == "failure":
                        self.current_state_var.set("Failed")
                        self.last_result_var.set(f"Last result: {label} failed after {elapsed_text}. Check the status window or log file: {self.current_log_file}")
                        self.status_var.set(f"Failed: {label}")
                        if self.show_completion_popup_var.get():
                            messagebox.showerror(APP_TITLE, f"{label} failed. Check the status window or log file:\n{self.current_log_file}")
                    self._set_controls_enabled(True)
                else:
                    self._append_log(str(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _append_log(self, text: str) -> None:
        self._write_log_file(text)
        try:
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
        except Exception:
            pass
        try:
            if self.status_popup_text is not None and self.status_popup_text.winfo_exists():
                self.status_popup_text.insert(tk.END, text)
                self.status_popup_text.see(tk.END)
        except Exception:
            pass

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _stop_current_process(self) -> None:
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.terminate()
                self._append_log("\nStop requested.\n")
            except Exception as error:
                self._append_log(f"\nCould not stop process: {error}\n")

    def _normalise_pronunciation_word(self, word: str) -> str:
        text = word.strip().lower().replace("’", "'")
        text = re.sub(r"[^a-z0-9']+", "", text)
        return text

    def _load_custom_pronunciations(self) -> dict[str, str]:
        if not self.custom_pronunciations_path.exists():
            return {}
        try:
            data = json.loads(self.custom_pronunciations_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        cleaned: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                cleaned[key] = value
        return cleaned

    def _write_custom_pronunciations(self, data: dict[str, str]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        ordered = {key: data[key] for key in sorted(data.keys())}
        self.custom_pronunciations_path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")

    def _load_missing_words_from_default(self, silent: bool = False) -> int:
        path = self.default_missing_words_path()
        self.missing_words_path_var.set(str(path))
        if not path.exists():
            if not silent:
                messagebox.showinfo(APP_TITLE, f"No missing words file found yet:\n{path}")
            self.pronunciation_status_var.set(f"No missing words file found: {path}")
            try:
                self.missing_words_listbox.delete(0, tk.END)
            except Exception:
                pass
            return 0

        try:
            raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as error:
            if not silent:
                messagebox.showerror(APP_TITLE, f"Could not read missing words file:\n{path}\n\n{error}")
            self.pronunciation_status_var.set(f"Could not read missing words file: {error}")
            return 0

        words: list[str] = []
        seen: set[str] = set()
        for line in raw_lines:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            # lyrics-aligner normally writes one word per line. If a future version adds columns,
            # use the first token as the word.
            cleaned = cleaned.split()[0]
            normalised = self._normalise_pronunciation_word(cleaned)
            if normalised and normalised not in seen:
                seen.add(normalised)
                words.append(normalised)

        try:
            self.missing_words_listbox.delete(0, tk.END)
            for word in words:
                self.missing_words_listbox.insert(tk.END, word)
        except Exception:
            pass

        if words:
            self.pronunciation_status_var.set(f"Loaded {len(words)} missing word(s). Select a word, check the suggestion, then save.")
            self.pronunciation_word_var.set(words[0])
            self.pronunciation_value_var.set(self._suggest_pronunciation(words[0]))
        else:
            self.pronunciation_status_var.set("Missing words file exists, but it did not contain any words.")
        return len(words)

    def _open_missing_words_file(self) -> None:
        path = self.default_missing_words_path()
        if not path.exists():
            messagebox.showinfo(APP_TITLE, f"No missing words file found yet:\n{path}")
            return
        os.startfile(str(path))  # type: ignore[attr-defined]

    def _open_custom_pronunciations_file(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.custom_pronunciations_path.exists():
            self.custom_pronunciations_path.write_text("{}\n", encoding="utf-8")
        os.startfile(str(self.custom_pronunciations_path))  # type: ignore[attr-defined]

    def _on_missing_word_selected(self, _event: Any | None = None) -> None:
        try:
            selection = self.missing_words_listbox.curselection()
        except Exception:
            return
        if not selection:
            return
        word = str(self.missing_words_listbox.get(selection[0]))
        self.pronunciation_word_var.set(word)
        data = self._load_custom_pronunciations()
        existing = data.get(word)
        self.pronunciation_value_var.set(existing or self._suggest_pronunciation(word))
        if existing:
            self.pronunciation_status_var.set(f"Existing pronunciation loaded for '{word}'. Edit it if needed.")
        else:
            self.pronunciation_status_var.set(f"Draft suggestion created for '{word}'. Check it before saving.")

    def _suggest_pronunciation_for_current_word(self) -> None:
        word = self._normalise_pronunciation_word(self.pronunciation_word_var.get())
        if not word:
            messagebox.showerror(APP_TITLE, "Enter or select a word first.")
            return
        self.pronunciation_word_var.set(word)
        self.pronunciation_value_var.set(self._suggest_pronunciation(word))
        self.pronunciation_status_var.set(f"Draft suggestion created for '{word}'. Check it before saving.")

    def _save_current_pronunciation(self) -> bool:
        word = self._normalise_pronunciation_word(self.pronunciation_word_var.get())
        pronunciation = re.sub(r"\s+", " ", self.pronunciation_value_var.get().strip().upper())
        if not word:
            messagebox.showerror(APP_TITLE, "Enter or select a word first.")
            return False
        if not pronunciation:
            messagebox.showerror(APP_TITLE, "Enter a pronunciation before saving.")
            return False
        if not re.fullmatch(r"[A-Z0-9 '\-]+", pronunciation):
            messagebox.showerror(
                APP_TITLE,
                "Pronunciation should use simple space-separated symbols, for example: F R AE K T AH L Z",
            )
            return False

        try:
            data = self._load_custom_pronunciations()
            data[word] = pronunciation
            self._write_custom_pronunciations(data)
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"Could not save pronunciation:\n{self.custom_pronunciations_path}\n\n{error}")
            return False

        self.pronunciation_word_var.set(word)
        self.pronunciation_value_var.set(pronunciation)
        self.pronunciation_status_var.set(f"Saved pronunciation for '{word}'. Rerun the pipeline when all missing words are saved.")
        self._remove_word_from_missing_listbox(word)
        return True

    def _remove_word_from_missing_listbox(self, word: str) -> None:
        try:
            for index in range(self.missing_words_listbox.size() - 1, -1, -1):
                if str(self.missing_words_listbox.get(index)) == word:
                    self.missing_words_listbox.delete(index)
        except Exception:
            pass

    def _save_all_loaded_suggestions(self) -> None:
        try:
            words = [str(self.missing_words_listbox.get(index)) for index in range(self.missing_words_listbox.size())]
        except Exception:
            words = []
        if not words:
            messagebox.showinfo(APP_TITLE, "No missing words are loaded.")
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "This will save draft suggested pronunciations for all loaded words.\n\n"
            "Only continue if the suggestions look sensible. Continue?",
        ):
            return
        try:
            data = self._load_custom_pronunciations()
            for word in words:
                data[word] = self._suggest_pronunciation(word)
            self._write_custom_pronunciations(data)
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"Could not save pronunciations:\n{error}")
            return
        self.missing_words_listbox.delete(0, tk.END)
        self.pronunciation_status_var.set(f"Saved {len(words)} suggested pronunciation(s). Rerun the pipeline.")

    def _suggest_pronunciation(self, word: str) -> str:
        word = self._normalise_pronunciation_word(word)
        special = {
            "arendelle": "AE R AH N D EH L",
            "elsa": "EH L S AH",
            "olaf": "OW L AH F",
            "anna": "AE N AH",
            "kristoff": "K R IH S T AO F",
            "sven": "S V EH N",
            "fractals": "F R AE K T AH L Z",
            "fractal": "F R AE K T AH L",
            "crystallizes": "K R IH S T AH L AY Z IH Z",
            "crystallise": "K R IH S T AH L AY Z",
            "crystallize": "K R IH S T AH L AY Z",
            "flurries": "F L ER IY Z",
            "swirling": "S W ER L IH NG",
            "spiraling": "S P AY R AH L IH NG",
            "unplayed": "AH N P L EY D",
            "lovestruck": "L AH V S T R AH K",
            "wideeyed": "W AY D AY D",
            "fedexed": "F EH D EH K S T",
            "specialism": "S P EH SH L IH Z M",
            "secondguessing": "S EH K AH N D G EH S IH NG",
        }
        if word in special:
            return special[word]

        # A deliberately simple ARPAbet-like fallback. It is meant to make editing quicker,
        # not to replace your judgement.
        chunks = [
            ("tion", "SH AH N"),
            ("sion", "ZH AH N"),
            ("cious", "SH AH S"),
            ("tious", "SH AH S"),
            ("ough", "OW"),
            ("augh", "AO"),
            ("eigh", "EY"),
            ("igh", "AY"),
            ("air", "EH R"),
            ("ear", "IH R"),
            ("eer", "IH R"),
            ("oor", "AO R"),
            ("ing", "IH NG"),
            ("ness", "N AH S"),
            ("less", "L AH S"),
            ("ment", "M AH N T"),
            ("able", "AH B AH L"),
            ("ible", "IH B AH L"),
            ("ed", "D"),
            ("er", "ER"),
            ("or", "AO R"),
            ("th", "TH"),
            ("sh", "SH"),
            ("ch", "CH"),
            ("ph", "F"),
            ("ck", "K"),
            ("qu", "K W"),
            ("wh", "W"),
            ("ng", "NG"),
            ("ee", "IY"),
            ("oo", "UW"),
            ("ou", "AW"),
            ("ow", "AW"),
            ("oy", "OY"),
            ("oi", "OY"),
            ("ay", "EY"),
            ("ai", "EY"),
            ("ea", "IY"),
            ("ie", "IY"),
        ]
        single = {
            "a": "AH",
            "b": "B",
            "c": "K",
            "d": "D",
            "e": "EH",
            "f": "F",
            "g": "G",
            "h": "HH",
            "i": "IH",
            "j": "JH",
            "k": "K",
            "l": "L",
            "m": "M",
            "n": "N",
            "o": "AO",
            "p": "P",
            "q": "K",
            "r": "R",
            "s": "S",
            "t": "T",
            "u": "AH",
            "v": "V",
            "w": "W",
            "x": "K S",
            "y": "IY",
            "z": "Z",
            "'": "",
        }
        out: list[str] = []
        index = 0
        while index < len(word):
            matched = False
            for letters, phones in chunks:
                if word.startswith(letters, index):
                    out.extend(phones.split())
                    index += len(letters)
                    matched = True
                    break
            if matched:
                continue
            phone = single.get(word[index], "")
            if phone:
                out.extend(phone.split())
            index += 1

        # Common plural cleanup: final s often sounds Z after a voiced sound.
        if word.endswith("s") and out and out[-1] == "S" and len(out) > 1 and out[-2] not in {"P", "T", "K", "F", "TH"}:
            out[-1] = "Z"
        return " ".join(out) or word.upper()

    def _run_pipeline(self) -> None:
        if not self._prepare_lyrics_for_pipeline():
            return

        if not self._validate_common():
            return

        slug = self.current_slug()
        self.last_draft_path = self.default_draft_path(slug)
        self.last_word_review_path = self.default_word_review_path(slug)
        self.last_raw_review_draft_path = self.default_raw_review_draft_path(slug)
        self.last_diagnostics_csv_path = self.default_diagnostics_csv_path(slug)
        self._refresh_predicted_paths()

        command = [
            sys.executable,
            str(self.tools_dir / "run_lyrics_aligner_pipeline.py"),
            "--audio",
            self.audio_path_var.get().strip(),
            "--lyrics",
            self.lyrics_path_var.get().strip(),
            "--name",
            self.song_name_var.get().strip(),
            "--aligner-dir",
            self.aligner_dir_var.get().strip(),
            "--vad-threshold",
            self.vad_threshold_var.get().strip(),
        ]

        if self.keep_previous_var.get():
            command.append("--keep-previous")

        self._run_command_async(command, "Run pipeline", on_success=lambda: self._after_pipeline_success(slug))

    def _after_pipeline_success(self, slug: str) -> None:
        self.last_draft_path = self.default_draft_path(slug)
        self.last_word_review_path = self.default_word_review_path(slug)
        self.last_raw_review_draft_path = self.default_raw_review_draft_path(slug)
        self.last_diagnostics_csv_path = self.default_diagnostics_csv_path(slug)
        self._refresh_predicted_paths()

    def _build_raw_review(self) -> None:
        slug = self.current_slug()
        word_review_path = self.last_word_review_path or self.default_word_review_path(slug)
        raw_review_path = self.default_raw_review_draft_path(slug)
        raw_builder = self.tools_dir / "build_review_draft_from_word_review.py"

        if not raw_builder.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Raw review builder is missing:\n{raw_builder}\n\nAdd tools/build_review_draft_from_word_review.py first.",
            )
            return

        if not word_review_path.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Word-review JSON does not exist yet:\n{word_review_path}\n\nRun the pipeline first.",
            )
            return

        command = [
            sys.executable,
            str(raw_builder),
            "--word-review",
            str(word_review_path),
            "--out",
            str(raw_review_path),
        ]

        def on_success() -> None:
            self.last_word_review_path = word_review_path
            self.last_raw_review_draft_path = raw_review_path
            self.last_draft_path = raw_review_path
            self.last_diagnostics_csv_path = self.default_raw_review_diagnostics_csv_path(slug)
            self._append_log(f"\nRaw review draft: {raw_review_path}\n")

        self._run_command_async(command, "Build raw review", on_success=on_success)

    def _run_diagnostics(self) -> None:
        slug = self.current_slug()
        draft_path = self.last_draft_path or self.default_draft_path(slug)
        if draft_path.name.endswith("-draft-raw-review.json"):
            diagnostics_csv = self.default_raw_review_diagnostics_csv_path(slug)
            diagnostics_summary = self.default_raw_review_diagnostics_summary_path(slug)
        else:
            diagnostics_csv = self.default_diagnostics_csv_path(slug)
            diagnostics_summary = self.default_diagnostics_summary_path(slug)

        if not draft_path.exists():
            messagebox.showerror(APP_TITLE, f"Draft JSON does not exist yet:\n{draft_path}\n\nRun the pipeline first, or check the song name.")
            return

        diagnostics_tool = self.tools_dir / "diagnose_alignment_quality.py"
        if not diagnostics_tool.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Diagnostics tool is missing:\n{diagnostics_tool}\n\nAdd tools/diagnose_alignment_quality.py first.",
            )
            return

        self.last_draft_path = draft_path
        self.last_diagnostics_csv_path = diagnostics_csv

        command = [
            sys.executable,
            str(diagnostics_tool),
            "--draft",
            str(draft_path),
            "--out",
            str(diagnostics_csv),
            "--summary",
            str(diagnostics_summary),
        ]

        self._run_command_async(command, "Run diagnostics")

    def _run_local_recovery(self) -> None:
        slug = self.current_slug()
        draft_path = self.last_draft_path or self.default_draft_path(slug)
        diagnostics_csv = self.last_diagnostics_csv_path or self.default_diagnostics_csv_path(slug)
        recovery_tool = self.tools_dir / "run_local_alignment_recovery.py"

        if not recovery_tool.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Local recovery tool is missing:\n{recovery_tool}\n\nAdd tools/run_local_alignment_recovery.py first.",
            )
            return

        if not draft_path.exists():
            messagebox.showerror(APP_TITLE, f"Draft JSON does not exist yet:\n{draft_path}")
            return

        if not diagnostics_csv.exists():
            messagebox.showerror(APP_TITLE, f"Diagnostics CSV does not exist yet:\n{diagnostics_csv}\n\nRun diagnostics first.")
            return

        try:
            int(self.local_recovery_min_severity_var.get())
        except ValueError:
            messagebox.showerror(APP_TITLE, "Minimum severity must be a whole number, such as 70.")
            return

        out_word_review = self.default_recovered_word_review_path(slug)
        out_draft = self.default_recovered_draft_path(slug)

        command = [
            sys.executable,
            str(recovery_tool),
            "--draft",
            str(draft_path),
            "--diagnostics",
            str(diagnostics_csv),
            "--out-word-review",
            str(out_word_review),
            "--out-draft",
            str(out_draft),
            "--aligner-dir",
            self.aligner_dir_var.get().strip(),
            "--min-severity",
            self.local_recovery_min_severity_var.get().strip(),
            "--vad-threshold",
            self.vad_threshold_var.get().strip(),
        ]

        line_ids = [part.strip() for part in self.local_recovery_line_ids_var.get().replace(";", ",").split(",") if part.strip()]
        for line_id in line_ids:
            command.extend(["--line-id", line_id])

        if self.keep_previous_var.get():
            command.append("--keep-previous")

        def on_success() -> None:
            self.last_draft_path = out_draft
            self.last_diagnostics_csv_path = diagnostics_csv
            self._append_log(f"\nRecovered draft: {out_draft}\n")

        self._run_command_async(command, "Run local recovery", on_success=on_success)

    def _current_editor_audio_path(self, slug: str) -> Path:
        clean_audio_path = self.project_root / "alignment_lab" / "runs" / slug / "audio" / f"{slug}.mp3"
        if clean_audio_path.exists():
            return clean_audio_path

        raw_audio = Path(self.audio_path_var.get().strip())
        if raw_audio.exists():
            return raw_audio

        return clean_audio_path

    def _create_autoload_editor_html(self, editor_path: Path, audio_path: Path, draft_path: Path) -> Path:
        marker = '    loadButton.addEventListener("click", loadDraft);'
        editor_html = editor_path.read_text(encoding="utf-8")

        if marker not in editor_html:
            raise RuntimeError("Could not find the editor script insertion point. Open the editor normally instead.")

        try:
            draft_json = json.loads(draft_path.read_text(encoding="utf-8"))
        except Exception as error:
            raise RuntimeError(f"Could not read the draft JSON: {error}") from error

        try:
            audio_bytes = audio_path.read_bytes()
        except Exception as error:
            raise RuntimeError(f"Could not read the audio file: {error}") from error

        mime_type = mimetypes.guess_type(str(audio_path))[0] or "audio/mpeg"
        audio_data_url = f"data:{mime_type};base64,{base64.b64encode(audio_bytes).decode('ascii')}"

        payload = {
            "audioFileName": audio_path.name,
            "draftFileName": draft_path.name,
            "draft": draft_json,
            "audioDataUrl": audio_data_url,
        }

        payload_json = json.dumps(payload, ensure_ascii=False)

        injected_script = f'''
    const __karaCreatorLauncherPayload = {payload_json};

    function __karaCreatorAutoLoadFromLauncher() {{
      clearError();

      try {{
        const payload = __karaCreatorLauncherPayload;
        draft = payload.draft;

        if (!draft || !draft.sections || !Array.isArray(draft.sections)) {{
          showError("The auto-loaded JSON does not contain a sections array.");
          return;
        }}

        sourceAudioFileName = payload.audioFileName || "audio.mp3";
        sourceDraftFileName = payload.draftFileName || "draft.json";
        audio.src = payload.audioDataUrl;

        rebuildFlatLines();

        if (!flatLines.length) {{
          showError("No lines were found in the auto-loaded draft JSON.");
          return;
        }}

        selectedIndex = 0;
        playingIndex = -1;
        setButtonsEnabled(true);
        rerenderAll();
        updateCurrentDisplay();

        const previousAutoplay = autoplayCheckbox.checked;
        autoplayCheckbox.checked = false;
        jumpToSelectedLine();
        autoplayCheckbox.checked = previousAutoplay;

        currentMeta.textContent = `Auto-loaded from Kara Creator Launcher: ${{sourceDraftFileName}}`;
      }} catch (error) {{
        showError(`Auto-load failed: ${{error.message}}`);
      }}
    }}

    window.addEventListener("load", () => {{
      setTimeout(__karaCreatorAutoLoadFromLauncher, 50);
    }});

'''

        autoload_html = editor_html.replace(marker, injected_script + marker)

        launch_dir = self.outputs_dir / "editor-launches"
        launch_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = self.current_slug()
        launch_path = launch_dir / f"{stamp}-{slug}-autoload-editor.html"
        launch_path.write_text(autoload_html, encoding="utf-8")
        return launch_path

    def _open_raw_editor(self) -> None:
        slug = self.current_slug()
        raw_draft_path = self.last_raw_review_draft_path or self.default_raw_review_draft_path(slug)
        if not raw_draft_path.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Raw review draft does not exist yet:\n{raw_draft_path}\n\nClick 'Build raw review' first.",
            )
            return

        diagnostics_path = self.default_raw_review_diagnostics_csv_path(slug)
        if not diagnostics_path.exists():
            fallback = self.last_diagnostics_csv_path or self.default_diagnostics_csv_path(slug)
            if fallback.exists():
                diagnostics_path = fallback

        if not diagnostics_path.exists():
            proceed = messagebox.askyesno(
                APP_TITLE,
                "No diagnostics CSV was found for this raw review draft.\n\n"
                "You can still open the editor, but selected recovery will need diagnostics.\n\n"
                "Open the raw editor anyway?",
            )
            if not proceed:
                return

        server_tool = self.tools_dir / "editor_recovery_server.py"
        if not server_tool.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Raw editor server is missing:\n{server_tool}\n\nAdd tools/editor_recovery_server.py first.",
            )
            return

        audio_path = self._current_editor_audio_path(slug)
        if not audio_path.exists():
            messagebox.showerror(APP_TITLE, f"Audio file not found:\n{audio_path}")
            return

        command = [
            sys.executable,
            str(server_tool),
            "--audio",
            str(audio_path),
            "--draft",
            str(raw_draft_path),
            "--aligner-dir",
            self.aligner_dir_var.get().strip(),
            "--vad-threshold",
            self.vad_threshold_var.get().strip(),
        ]
        if diagnostics_path.exists():
            command.extend(["--diagnostics", str(diagnostics_path)])

        try:
            subprocess.Popen(command, cwd=str(self.project_root))
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"Could not start the raw editor server:\n\n{error}")
            return

        self.last_raw_review_draft_path = raw_draft_path
        self.last_draft_path = raw_draft_path
        self.last_diagnostics_csv_path = diagnostics_path if diagnostics_path.exists() else self.last_diagnostics_csv_path
        self._append_log(
            "\nStarted raw editor server with auto-loaded files:\n"
            f"Audio: {audio_path}\n"
            f"Draft: {raw_draft_path}\n"
            f"Diagnostics: {diagnostics_path if diagnostics_path.exists() else 'not found'}\n"
        )
        self.last_result_var.set("Last result: raw editor server started.")

    def _open_editor(self) -> None:
        editor_path = self.tools_dir / "edit_karaoke_draft.html"
        if not editor_path.exists():
            messagebox.showerror(APP_TITLE, f"Editor file does not exist:\n{editor_path}")
            return

        slug = self.current_slug()
        draft_path = self.last_draft_path or self.default_draft_path(slug)
        audio_path = self._current_editor_audio_path(slug)

        if draft_path.exists() and audio_path.exists():
            try:
                launch_path = self._create_autoload_editor_html(editor_path, audio_path, draft_path)
            except Exception as error:
                messagebox.showwarning(
                    APP_TITLE,
                    f"Could not create the auto-load editor page. Opening the editor normally instead.\n\n{error}",
                )
                os.startfile(str(editor_path))  # type: ignore[attr-defined]
                return

            self._append_log(f"\nOpening editor with auto-loaded files:\nAudio: {audio_path}\nDraft: {draft_path}\nLaunch page: {launch_path}\n")
            os.startfile(str(launch_path))  # type: ignore[attr-defined]
            return

        missing_parts: list[str] = []
        if not draft_path.exists():
            missing_parts.append(f"Draft JSON not found:\n{draft_path}")
        if not audio_path.exists():
            missing_parts.append(f"Audio file not found:\n{audio_path}")

        if missing_parts:
            proceed = messagebox.askyesno(
                APP_TITLE,
                "The launcher could not find the files to auto-load.\n\n"
                + "\n\n".join(missing_parts)
                + "\n\nOpen the editor normally instead?",
            )
            if not proceed:
                return

        os.startfile(str(editor_path))  # type: ignore[attr-defined]

    def _open_outputs_folder(self) -> None:
        self.outputs_dir.mkdir(exist_ok=True)
        os.startfile(str(self.outputs_dir))  # type: ignore[attr-defined]

    def _open_current_draft(self) -> None:
        slug = self.current_slug()
        draft_path = self.last_draft_path or self.default_draft_path(slug)
        if not draft_path.exists():
            messagebox.showerror(APP_TITLE, f"Draft JSON does not exist yet:\n{draft_path}")
            return
        os.startfile(str(draft_path))  # type: ignore[attr-defined]


def main() -> int:
    app = KaraCreatorLauncher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
