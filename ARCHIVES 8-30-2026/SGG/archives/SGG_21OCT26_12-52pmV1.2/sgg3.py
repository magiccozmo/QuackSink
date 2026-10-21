#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spiffy's Gift tool — SGG v1.2.

A small, explicit state machine for the early SGG development workflow.
The Python code implements the machine; UI widgets are only its controls and view.

Startup contract:
    1. Create ./archives/<timestamped run archive>.
    2. Copy this exact source file and the main sgg.config snapshot into it.
    3. Create log.txt with the archive name on its first line.
    4. Load the main config and only then initialize and display the UI.

All note files are written inside the current run archive. The source version is
fixed in this file; launching it creates a new timestamped archive, not a new version.

Third-party dependency: pygame-ce==2.5.8
All other imports belong to Python's standard library.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Version and paths
# ---------------------------------------------------------------------------

PROGRAM_NAME = "Spiffy's Gift"
VERSION = "1.2"  # Fixed in code; launch creates another archive of this same version.
VERSION_TAG = f"V{VERSION}"
RUNTIME_FILE = "sgg3.py"
ARCHIVE_PREFIX = "SGG"
LOG_FILE_NAME = "log.txt"
NOTE_EXTENSION = ".NOTES"
CONFIG_FILE = "sgg.config"

SOURCE_FILE = Path(__file__).resolve()
SOURCE_DIR = SOURCE_FILE.parent
# Follow the PPR-style stable project-root convention: archive placement is
# anchored to the directory containing the launched source, not the shell CWD.
LAUNCH_DIR = SOURCE_DIR
PROJECT_DIR = SOURCE_DIR
ARCHIVE_ROOT = LAUNCH_DIR / "archives"
CONFIG_PATH = PROJECT_DIR / CONFIG_FILE

# The picker starts in <source directory>/assets, exactly as requested.
ASSET_START_DIR = LAUNCH_DIR / "assets"
if not ASSET_START_DIR.is_dir():
    ASSET_START_DIR = LAUNCH_DIR

FONT_SIZE_OPTIONS_PT = (20, 22, 24, 26, 28, 30, 32)
DEFAULT_FONT_SIZE_PT = 22


# ---------------------------------------------------------------------------
# Persistent project configuration
# ---------------------------------------------------------------------------

CONFIG_DEFAULTS = {
    "config_version": 1,
    "font_size_pt": DEFAULT_FONT_SIZE_PT,
    "last_png_path": "",
}


def _normalized_config(raw: object) -> dict:
    """Validate the settings SGG understands while preserving future keys."""
    result = dict(CONFIG_DEFAULTS)
    if isinstance(raw, dict):
        result.update(raw)
    else:
        raise ValueError("sgg.config must contain a JSON object")

    try:
        font_size = int(result.get("font_size_pt", DEFAULT_FONT_SIZE_PT))
    except (TypeError, ValueError):
        font_size = DEFAULT_FONT_SIZE_PT
    if font_size not in FONT_SIZE_OPTIONS_PT:
        font_size = DEFAULT_FONT_SIZE_PT
    result["font_size_pt"] = font_size

    last_png_path = result.get("last_png_path", "")
    if not isinstance(last_png_path, str):
        last_png_path = ""
    result["last_png_path"] = last_png_path
    result["config_version"] = 1
    return result


def _write_json_atomically(path: Path, data: dict) -> None:
    """Write JSON completely before replacing the prior config file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def ensure_main_config_exists() -> None:
    """Create the main config with defaults only on the first launch."""
    if not CONFIG_PATH.exists():
        _write_json_atomically(CONFIG_PATH, dict(CONFIG_DEFAULTS))
    elif not CONFIG_PATH.is_file():
        raise OSError(f"Configuration path exists but is not a file: {CONFIG_PATH}")


def load_main_config() -> tuple[dict, Optional[str]]:
    """Load the authoritative main config after its startup archive snapshot."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            raw = json.load(config_file)
        return _normalized_config(raw), None
    except Exception as exc:
        # Preserve a malformed config for inspection rather than overwriting it
        # automatically. Defaults remain in memory and will be saved only when
        # the user changes a preference successfully.
        warning = f"Could not read {CONFIG_FILE}; using defaults for this run: {type(exc).__name__}: {exc}"
        return dict(CONFIG_DEFAULTS), warning


def save_main_config(config: dict) -> None:
    """Persist settings to the project-root config, never the archive snapshot."""
    normalized = _normalized_config(config)
    _write_json_atomically(CONFIG_PATH, normalized)
    config.clear()
    config.update(normalized)


# ---------------------------------------------------------------------------
# Archive-first startup and run logging
# ---------------------------------------------------------------------------

class ArchiveError(RuntimeError):
    """Raised when a safe, self-contained run archive cannot be initialized."""


@dataclass(frozen=True)
class RunArchive:
    name: str
    directory: Path
    source_copy: Path
    log_path: Path


def _timestamp_archive_name(moment: datetime) -> str:
    date_part = moment.strftime("%d%b%y").upper()
    time_part = moment.strftime("%I-%M%p").lower()
    return f"{ARCHIVE_PREFIX}_{date_part}_{time_part}{VERSION_TAG}"


def initialize_archive() -> RunArchive:
    """Create a fresh archive before starting Pygame or the UI.

    The naming convention has minute precision. To retain the exact requested
    format without adding a suffix, a same-minute collision waits and retries,
    matching the established PPR archive behavior. Archives are always placed
    beneath the launch/source directory's archives folder.
    """
    if not SOURCE_FILE.is_file():
        raise ArchiveError(f"Cannot archive source; file not found: {SOURCE_FILE}")

    try:
        ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArchiveError(f"Could not create archive root at {ARCHIVE_ROOT}: {exc}") from exc

    while True:
        archive_name = _timestamp_archive_name(datetime.now().astimezone())
        archive_dir = ARCHIVE_ROOT / archive_name
        try:
            archive_dir.mkdir(parents=False, exist_ok=False)
            break
        except FileExistsError:
            print(
                f"Archive {archive_name} already exists. Waiting for the next minute "
                "to preserve the required archive-name format...",
                flush=True,
            )
            time.sleep(60)
        except OSError as exc:
            raise ArchiveError(
                f"Could not create run archive at {archive_dir}: {exc}"
            ) from exc

    log_path = archive_dir / LOG_FILE_NAME
    source_copy = archive_dir / RUNTIME_FILE

    # The first content written to log.txt is exactly the archive name.
    try:
        with log_path.open("x", encoding="utf-8", newline="") as log_file:
            log_file.write(archive_name + "\n")
            log_file.flush()
        shutil.copy2(SOURCE_FILE, source_copy)
        # The main config is the source of truth. Snapshot it into this run's
        # archive before the application reads it or modifies any preference.
        ensure_main_config_exists()
        shutil.copy2(CONFIG_PATH, archive_dir / CONFIG_FILE)
    except Exception as exc:
        try:
            with log_path.open("a", encoding="utf-8", newline="") as log_file:
                log_file.write(f"[STARTUP ERROR] Archive initialization failed: {exc}\n")
        except Exception:
            pass
        raise ArchiveError(
            f"Archive folder was created, but its source/log setup failed: {exc}"
        ) from exc

    archive = RunArchive(
        name=archive_name,
        directory=archive_dir,
        source_copy=source_copy,
        log_path=log_path,
    )
    append_log(archive, "ARCHIVE", f"Created {archive_name}")
    append_log(archive, "SOURCE", f"Copied running source to {source_copy.name}")
    append_log(archive, "CONFIG", f"Snapshotted main {CONFIG_FILE} to archive; live preferences remain in {CONFIG_PATH.name}")
    append_log(archive, "STARTUP", f"Python {sys.version.split()[0]} | {sys.executable}")
    append_log(archive, "PATHS", f"Project directory: {PROJECT_DIR}")
    append_log(archive, "PATHS", f"Launch directory: {LAUNCH_DIR}")
    append_log(archive, "PATHS", f"Archive root: {ARCHIVE_ROOT}")
    append_log(archive, "PATHS", f"Note destination: {archive.directory}")
    append_log(archive, "PATHS", f"Asset picker starts at: {ASSET_START_DIR}")
    return archive


def append_log(archive: RunArchive, category: str, message: str) -> None:
    """Append one timestamped event and flush it immediately."""
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %I:%M:%S %p %z")
    clean_message = str(message).replace("\r", "\\r").replace("\n", "\\n")
    with archive.log_path.open("a", encoding="utf-8", newline="") as log_file:
        log_file.write(f"[{stamp}] [{category}] {clean_message}\n")
        log_file.flush()


# ---------------------------------------------------------------------------
# Explicit state model
# ---------------------------------------------------------------------------

class AppState(Enum):
    MAIN = auto()
    ASSET_PREVIEW = auto()
    CONFIRM_OVERWRITE = auto()
    CLOSED = auto()


class FieldName(Enum):
    TITLE = auto()
    NOTES = auto()


@dataclass
class TextBuffer:
    """Small editable text buffer used by the Pygame text controls."""
    text: str = ""
    cursor: int = 0
    select_all: bool = False

    def set_text(self, value: str) -> None:
        self.text = value
        self.cursor = len(value)
        self.select_all = False

    def _replace_selection(self) -> bool:
        if self.select_all:
            self.text = ""
            self.cursor = 0
            self.select_all = False
            return True
        return False

    def insert(self, value: str) -> None:
        self._replace_selection()
        value = value.replace("\r", "")
        self.text = self.text[:self.cursor] + value + self.text[self.cursor:]
        self.cursor += len(value)

    def backspace(self) -> None:
        if self._replace_selection():
            return
        if self.cursor > 0:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1

    def delete_forward(self) -> None:
        if self._replace_selection():
            return
        if self.cursor < len(self.text):
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]

    def move(self, direction: int) -> None:
        self.select_all = False
        self.cursor = max(0, min(len(self.text), self.cursor + direction))

    def home(self) -> None:
        self.select_all = False
        self.cursor = self.text.rfind("\n", 0, self.cursor) + 1

    def end(self) -> None:
        self.select_all = False
        next_newline = self.text.find("\n", self.cursor)
        self.cursor = len(self.text) if next_newline < 0 else next_newline

    def vertical(self, direction: int) -> None:
        self.select_all = False
        line_start = self.text.rfind("\n", 0, self.cursor) + 1
        column = self.cursor - line_start
        if direction < 0:
            if line_start == 0:
                return
            previous_end = line_start - 1
            previous_start = self.text.rfind("\n", 0, previous_end) + 1
            self.cursor = min(previous_start + column, previous_end)
        else:
            line_end = self.text.find("\n", self.cursor)
            if line_end < 0:
                return
            next_start = line_end + 1
            next_end = self.text.find("\n", next_start)
            if next_end < 0:
                next_end = len(self.text)
            self.cursor = min(next_start + column, next_end)

    def select_everything(self) -> None:
        self.select_all = True

    def clear(self) -> None:
        self.text = ""
        self.cursor = 0
        self.select_all = False


# ---------------------------------------------------------------------------
# UI layout helpers (the view renders state; it does not own application state)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Layout:
    header: "pygame.Rect"
    menu_button: "pygame.Rect"
    menu_item_asset_preview: "pygame.Rect"
    title_label_y: int
    title_box: "pygame.Rect"
    notes_label_y: int
    notes_box: "pygame.Rect"
    make_note_button: "pygame.Rect"
    status_box: "pygame.Rect"
    preview_choose_button: "pygame.Rect"
    preview_back_button: "pygame.Rect"
    confirm_replace_button: "pygame.Rect"
    confirm_cancel_button: "pygame.Rect"
    font_down_button: "pygame.Rect"
    font_up_button: "pygame.Rect"


# pygame is imported after archive creation in main(); type names in this module
# are quoted where needed so importing the module itself doesn't initialize SDL.
pygame = None  # Assigned by main() after archive creation.


class StateMachine:
    """Owns the authoritative state and all state transitions/actions."""

    def __init__(self, archive: RunArchive, config: dict, config_warning: Optional[str] = None):
        self.archive = archive
        self.config = dict(config)
        self.font_size_pt = int(self.config.get("font_size_pt", DEFAULT_FONT_SIZE_PT))
        self.last_png_path = str(self.config.get("last_png_path", ""))
        self.state = AppState.MAIN
        self.previous_state = AppState.MAIN
        self.title_buffer = TextBuffer()
        self.notes_buffer = TextBuffer()
        self.active_field: Optional[FieldName] = None
        self.menu_open = False
        self.status = config_warning or "Ready. Enter a title and note, or open Menu → Asset Preview."
        self.status_error = bool(config_warning)
        self.preview_path: Optional[Path] = None
        self.preview_surface = None
        self.preview_dimensions: Optional[tuple[int, int]] = None
        self.pending_note_path: Optional[Path] = None
        self._log("STATE", "BOOT -> MAIN")
        self._log("ACCESSIBILITY", f"High-contrast black/white theme; font size {self.font_size_pt} pt; available sizes {FONT_SIZE_OPTIONS_PT}")
        self._log("CONFIG", f"Loaded main configuration from {CONFIG_PATH}")
        if config_warning:
            self._log("CONFIG ERROR", config_warning)

    def _log(self, category: str, message: str) -> None:
        append_log(self.archive, category, message)

    def _set_status(self, message: str, is_error: bool = False) -> None:
        self.status = message
        self.status_error = is_error
        self._log("STATUS", ("ERROR: " if is_error else "") + message)

    def transition(self, new_state: AppState, reason: str) -> None:
        if new_state is self.state:
            return
        old_state = self.state
        self.previous_state = old_state
        self.state = new_state
        self._log("STATE", f"{old_state.name} -> {new_state.name} | {reason}")

    def dispatch(self, event, ui: "SGGInterface") -> None:
        """Receive one SDL/UI event and route it through the current state."""
        if self.state is AppState.CLOSED:
            return

        if event.type == pygame.QUIT:
            self.transition(AppState.CLOSED, "Window close requested")
            return

        if event.type == pygame.VIDEORESIZE:
            ui.resize(event.w, event.h)
            self._log("UI", f"Window resized to {ui.width}x{ui.height}")
            return

        if self.state is AppState.MAIN:
            self._dispatch_main(event, ui)
        elif self.state is AppState.ASSET_PREVIEW:
            self._dispatch_asset_preview(event, ui)
        elif self.state is AppState.CONFIRM_OVERWRITE:
            self._dispatch_confirm_overwrite(event, ui)

    def _dispatch_main(self, event, ui: "SGGInterface") -> None:
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_ESCAPE:
                if self.menu_open:
                    self.menu_open = False
                    self._log("MENU", "Closed by Escape")
                else:
                    self.active_field = None
                return
            if (mods & pygame.KMOD_CTRL) and event.key == pygame.K_s:
                self.request_save_note()
                return
            if (mods & pygame.KMOD_CTRL) and event.key == pygame.K_a and self.active_field is not None:
                self._active_buffer().select_everything()
                return
            if mods & pygame.KMOD_CTRL:
                increase_keys = {pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS}
                decrease_keys = {pygame.K_MINUS, pygame.K_KP_MINUS}
                if event.key in increase_keys:
                    self.adjust_font_size(1, ui)
                    return
                if event.key in decrease_keys:
                    self.adjust_font_size(-1, ui)
                    return
            if event.key == pygame.K_TAB:
                self.active_field = (
                    FieldName.NOTES if self.active_field is FieldName.TITLE
                    else FieldName.TITLE
                )
                self.menu_open = False
                self._log("INPUT", f"Focus -> {self.active_field.name}")
                return
            if self.active_field is not None:
                buffer = self._active_buffer()
                if event.key == pygame.K_RETURN:
                    if self.active_field is FieldName.TITLE:
                        self.active_field = FieldName.NOTES
                        self._log("INPUT", "Enter moved focus TITLE -> NOTES")
                    else:
                        buffer.insert("\n")
                elif event.key == pygame.K_BACKSPACE:
                    buffer.backspace()
                elif event.key == pygame.K_DELETE:
                    buffer.delete_forward()
                elif event.key == pygame.K_LEFT:
                    buffer.move(-1)
                elif event.key == pygame.K_RIGHT:
                    buffer.move(1)
                elif event.key == pygame.K_UP and self.active_field is FieldName.NOTES:
                    buffer.vertical(-1)
                elif event.key == pygame.K_DOWN and self.active_field is FieldName.NOTES:
                    buffer.vertical(1)
                elif event.key == pygame.K_HOME:
                    buffer.home()
                elif event.key == pygame.K_END:
                    buffer.end()
                return

        if event.type == pygame.TEXTINPUT and self.active_field is not None:
            buffer = self._active_buffer()
            value = event.text
            if self.active_field is FieldName.TITLE:
                value = value.replace("\n", "").replace("\t", "")
            buffer.insert(value)
            self.menu_open = False
            return

        if event.type == pygame.MOUSEWHEEL:
            if ui.layout.notes_box.collidepoint(pygame.mouse.get_pos()):
                ui.scroll_notes(-event.y)
            return

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        point = event.pos
        if self.menu_open:
            if ui.layout.menu_item_asset_preview.collidepoint(point):
                self.menu_open = False
                self.open_asset_preview()
                ui.choose_png(self)
                return
            if ui.layout.menu_button.collidepoint(point):
                self.menu_open = False
                self._log("MENU", "Closed")
                return
            self.menu_open = False

        if ui.layout.font_down_button.collidepoint(point):
            self.adjust_font_size(-1, ui)
            self.menu_open = False
            return
        elif ui.layout.font_up_button.collidepoint(point):
            self.adjust_font_size(1, ui)
            self.menu_open = False
            return
        elif ui.layout.menu_button.collidepoint(point):
            self.menu_open = True
            self.active_field = None
            self._log("MENU", "Opened")
        elif ui.layout.title_box.collidepoint(point):
            self.active_field = FieldName.TITLE
            self.menu_open = False
            self.title_buffer.cursor = len(self.title_buffer.text)
            self.title_buffer.select_all = False
        elif ui.layout.notes_box.collidepoint(point):
            self.active_field = FieldName.NOTES
            self.menu_open = False
            ui.set_notes_cursor_from_mouse(self.notes_buffer, point)
        elif ui.layout.make_note_button.collidepoint(point):
            self.active_field = None
            self.menu_open = False
            self.request_save_note()
        else:
            self.active_field = None
            self.menu_open = False

    def _dispatch_asset_preview(self, event, ui: "SGGInterface") -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.transition(AppState.MAIN, "Escape from asset preview")
            self.status = "Returned from Asset Preview."
            self.status_error = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
            self.transition(AppState.MAIN, "Backspace from asset preview")
            self.status = "Returned from Asset Preview."
            self.status_error = False
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if ui.layout.preview_back_button.collidepoint(event.pos):
                self.transition(AppState.MAIN, "Back button in asset preview")
                self._set_status("Returned from Asset Preview.")
            elif ui.layout.preview_choose_button.collidepoint(event.pos):
                ui.choose_png(self)

    def _dispatch_confirm_overwrite(self, event, ui: "SGGInterface") -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.pending_note_path = None
            self.transition(AppState.MAIN, "Cancelled note overwrite")
            self._set_status("Kept the existing note. Nothing was changed.")
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if ui.layout.confirm_replace_button.collidepoint(event.pos):
                self._write_note(overwrite=True)
            elif ui.layout.confirm_cancel_button.collidepoint(event.pos):
                self.pending_note_path = None
                self.transition(AppState.MAIN, "Cancelled note overwrite")
                self._set_status("Kept the existing note. Nothing was changed.")

    def picker_start(self) -> tuple[Path, Optional[str]]:
        """Choose the previous selection's folder, or the default assets folder."""
        if self.last_png_path:
            last_path = Path(self.last_png_path).expanduser()
            try:
                last_parent = last_path.parent.resolve()
                if last_parent.is_dir():
                    return last_parent, last_path.name
            except OSError:
                pass
        fallback = ASSET_START_DIR if ASSET_START_DIR.is_dir() else LAUNCH_DIR
        return fallback, None

    def persist_preference(self, key: str, value) -> Optional[str]:
        """Update the main sgg.config; never edit this run's archived snapshot."""
        self.config[key] = value
        try:
            save_main_config(self.config)
        except Exception as exc:
            message = f"Could not save preference to main {CONFIG_FILE}: {type(exc).__name__}: {exc}"
            self._log("CONFIG ERROR", message)
            return message
        self._log("CONFIG", f"Saved preference {key} to main {CONFIG_FILE}")
        return None

    def adjust_font_size(self, direction: int, ui: "SGGInterface") -> None:
        current_index = FONT_SIZE_OPTIONS_PT.index(self.font_size_pt)
        next_index = max(0, min(len(FONT_SIZE_OPTIONS_PT) - 1, current_index + direction))
        next_size = FONT_SIZE_OPTIONS_PT[next_index]
        if next_size == self.font_size_pt:
            self._set_status(f"Font size is already at the {next_size} pt limit.")
            return
        previous_size = self.font_size_pt
        self.font_size_pt = next_size
        ui.update_fonts()
        ui.layout = ui.calculate_layout()
        ui.notes_scroll = 0
        self._log("ACCESSIBILITY", f"Font size {previous_size} pt -> {next_size} pt")
        config_error = self.persist_preference("font_size_pt", next_size)
        if config_error:
            self._set_status(
                f"Font size changed to {next_size} pt for this run, but wasn't saved: {config_error}",
                is_error=True,
            )
        else:
            self._set_status(f"Font size changed from {previous_size} pt to {next_size} pt and saved.")

    def _active_buffer(self) -> TextBuffer:
        return self.title_buffer if self.active_field is FieldName.TITLE else self.notes_buffer

    def open_asset_preview(self) -> None:
        self.preview_path = None
        self.preview_surface = None
        self.preview_dimensions = None
        self.transition(AppState.ASSET_PREVIEW, "Menu -> Asset Preview")
        initial_dir, _initial_file = self.picker_start()
        self._set_status(f"Choose a PNG. Initial folder: {initial_dir}")

    def choose_asset(self, selected_path: str | Path | None) -> None:
        if not selected_path:
            self._set_status("No PNG selected. Choose PNG to try again.")
            self._log("ASSET", "File picker cancelled")
            return

        path = Path(selected_path).expanduser().resolve()
        if path.suffix.lower() != ".png":
            self._set_status("Please choose a .png image.", is_error=True)
            self._log("ASSET ERROR", f"Rejected non-PNG file: {path}")
            return

        # Clear the previous preview as soon as a new file is selected, so a
        # load failure cannot misleadingly leave the old image on screen.
        self.preview_path = path
        self.preview_surface = None
        self.preview_dimensions = None
        try:
            surface = pygame.image.load(str(path)).convert_alpha()
            dimensions = surface.get_size()
        except Exception as exc:
            self._set_status(f"Could not load image: {exc}", is_error=True)
            self._log("ASSET ERROR", f"Could not load {path}: {type(exc).__name__}: {exc}")
            return

        self.preview_path = path
        self.preview_surface = surface
        self.preview_dimensions = dimensions
        self.last_png_path = str(path)
        config_error = self.persist_preference("last_png_path", self.last_png_path)
        if config_error:
            self._set_status(
                f"Loaded {path.name} ({dimensions[0]} x {dimensions[1]} px), but couldn't remember it: {config_error}",
                is_error=True,
            )
        else:
            self._set_status(f"Loaded {path.name} ({dimensions[0]} x {dimensions[1]} px); selection remembered.")
        self._log("ASSET", f"Loaded {path} | {dimensions[0]}x{dimensions[1]}")

    def request_save_note(self) -> None:
        raw_title = self.title_buffer.text.strip()
        note_content = self.notes_buffer.text
        valid_title, reason = validate_note_title(raw_title)
        if not valid_title:
            self._set_status(reason, is_error=True)
            self._log("NOTE ERROR", reason)
            return
        if not note_content.strip():
            self._set_status("The Notes box is empty. Enter the note before saving.", is_error=True)
            self._log("NOTE ERROR", "Save rejected: note content was empty")
            return

        note_path = self.archive.directory / f"{raw_title}{NOTE_EXTENSION}"
        self.pending_note_path = note_path
        if note_path.exists():
            self.transition(AppState.CONFIRM_OVERWRITE, f"Note already exists: {note_path.name}")
            self._set_status(f"{note_path.name} already exists. Replace it or cancel?")
            return
        self._write_note(overwrite=False)

    def _write_note(self, overwrite: bool) -> None:
        target = self.pending_note_path
        if target is None:
            self._set_status("No note was queued for saving.", is_error=True)
            self._log("NOTE ERROR", "Write requested without a pending note path")
            self.transition(AppState.MAIN, "Missing pending note path")
            return

        if target.exists() and not overwrite:
            self.transition(AppState.CONFIRM_OVERWRITE, f"Note already exists: {target.name}")
            self._set_status(f"{target.name} already exists. Replace it or cancel?")
            return

        note_content = self.notes_buffer.text
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=str(target.parent),
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(note_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomic replacement prevents a partial note if a write is interrupted.
            os.replace(temp_path, target)
            temp_path = None
        except Exception as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            self._set_status(f"Could not save note; fields were kept: {exc}", is_error=True)
            self._log("NOTE ERROR", f"Write failed for {target}: {type(exc).__name__}: {exc}")
            if self.state is AppState.CONFIRM_OVERWRITE:
                self.transition(AppState.MAIN, "Overwrite failed; return to note editor")
            self.pending_note_path = None
            return

        # Clear only after the file has been fully written and replaced.
        self.title_buffer.clear()
        self.notes_buffer.clear()
        self.active_field = None
        self.pending_note_path = None
        if self.state is AppState.CONFIRM_OVERWRITE:
            self.transition(AppState.MAIN, "Note overwrite succeeded")
        label = "Updated" if overwrite else "Saved"
        self._set_status(f"{label} note: {target.name}")
        self._log("NOTE", f"{label} {target.name} ({len(note_content)} characters)")


_WINDOWS_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{n}" for n in range(1, 10)),
    *(f"LPT{n}" for n in range(1, 10)),
}


def validate_note_title(title: str) -> tuple[bool, str]:
    """Validate a user-supplied Windows-safe base name without changing it."""
    if not title:
        return False, "Enter a title first; it becomes the .NOTES filename."
    if len(title) > 160:
        return False, "That title is too long for a safe filename (maximum 160 characters)."
    if _WINDOWS_INVALID_NAME.search(title):
        return False, 'The title contains a character Windows does not allow in filenames: < > : " / \\ | ? *'
    if title.endswith((".", " ")):
        return False, "A filename cannot end with a period or space."
    if title.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        return False, "That title is reserved by Windows. Please choose another."
    return True, ""


# ---------------------------------------------------------------------------
# Pygame interface: rendering and native file-dialog adapter
# ---------------------------------------------------------------------------

class SGGInterface:
    """Pure view/input adapter for StateMachine; durable state remains in machine."""

    MIN_WIDTH = 1120
    MIN_HEIGHT = 680

    # High-contrast accessibility palette: bright text on true black.
    BG = (0, 0, 0)
    PANEL = (0, 0, 0)
    PANEL_ALT = (14, 14, 14)
    HEADER = (0, 0, 0)
    HEADER_EDGE = (255, 255, 255)
    TEXT = (255, 255, 255)
    MUTED = (235, 235, 235)
    ACCENT = (255, 255, 255)
    ACCENT_HOVER = (255, 255, 255)
    GREEN = (255, 255, 255)
    RED = (255, 255, 255)
    BORDER = (220, 220, 220)
    FIELD_BG = (0, 0, 0)
    PLACEHOLDER = (220, 220, 220)

    @staticmethod
    def _pt_to_px(points: int) -> int:
        # Pygame font sizes are pixel heights; convert typical 96-DPI point sizes.
        return max(27, round(points * 4 / 3))

    def __init__(self, machine: StateMachine):
        self.machine = machine
        display_info = pygame.display.Info()
        desktop_width = max(self.MIN_WIDTH, int(display_info.current_w or 1360) - 60)
        desktop_height = max(self.MIN_HEIGHT, int(display_info.current_h or 920) - 90)
        self.width = min(1360, desktop_width)
        self.height = min(880, desktop_height)
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption(f"{PROGRAM_NAME} — {machine.archive.name}")
        pygame.display.set_icon(self._make_icon())
        self.notes_scroll = 0
        self.update_fonts()
        self.layout = self.calculate_layout()

    def update_fonts(self) -> None:
        base_px = self._pt_to_px(self.machine.font_size_pt)
        self.title_font = pygame.font.SysFont("segoeui", self._pt_to_px(min(32, self.machine.font_size_pt + 5)), bold=True)
        self.archive_font = pygame.font.SysFont("consolas", base_px)
        self.font = pygame.font.SysFont("segoeui", base_px)
        self.small_font = pygame.font.SysFont("segoeui", base_px)
        self.button_font = pygame.font.SysFont("segoeui", base_px, bold=True)
        self.label_font = pygame.font.SysFont("segoeui", base_px, bold=True)
        self.status_font = pygame.font.SysFont("segoeui", base_px)

    def _make_icon(self):
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.rect(icon, (49, 30, 82), (0, 0, 32, 32), border_radius=7)
        pygame.draw.polygon(icon, (207, 181, 255), [(5, 17), (16, 4), (27, 17)])
        pygame.draw.rect(icon, (166, 112, 255), (7, 16, 18, 11), border_radius=3)
        pygame.draw.circle(icon, (255, 242, 199), (16, 20), 3)
        return icon

    def calculate_layout(self) -> Layout:
        width, height = self.width, self.height
        header = pygame.Rect(0, 0, width, 100)
        menu_button = pygame.Rect(width - 158, 23, 132, 54)
        menu_item = pygame.Rect(width - 242, 78, 216, 58)
        font_down = pygame.Rect(width - 445, 24, 52, 52)
        font_up = pygame.Rect(width - 221, 24, 52, 52)

        title_box_y = 150
        title_box_h = max(58, self.font.get_linesize() + 20)
        title_box = pygame.Rect(42, title_box_y, width - 84, title_box_h)
        title_label_y = 111
        notes_label_y = title_box.bottom + 24
        notes_top = notes_label_y + self.font.get_linesize() + 10
        hint_line_height = self.small_font.get_linesize()
        hint_two_y = height - hint_line_height - 8
        hint_one_y = hint_two_y - hint_line_height - 6
        controls_y = hint_one_y - 72
        notes_bottom = controls_y - 32
        notes_height = max(150, notes_bottom - notes_top)
        notes_box = pygame.Rect(42, notes_top, width - 84, notes_height)

        make_note_button = pygame.Rect(width - 230, controls_y, 188, 62)
        status_box = pygame.Rect(42, controls_y, max(300, width - 300), 58)
        preview_choose = pygame.Rect(42, controls_y, 188, 62)
        preview_back = pygame.Rect(width - 230, controls_y, 188, 62)
        confirm_replace = pygame.Rect(width // 2 - 202, height // 2 + 62, 184, 62)
        confirm_cancel = pygame.Rect(width // 2 + 18, height // 2 + 62, 184, 62)
        return Layout(
            header=header,
            menu_button=menu_button,
            menu_item_asset_preview=menu_item,
            title_label_y=title_label_y,
            title_box=title_box,
            notes_label_y=notes_label_y,
            notes_box=notes_box,
            make_note_button=make_note_button,
            status_box=status_box,
            preview_choose_button=preview_choose,
            preview_back_button=preview_back,
            confirm_replace_button=confirm_replace,
            confirm_cancel_button=confirm_cancel,
            font_down_button=font_down,
            font_up_button=font_up,
        )

    def resize(self, width: int, height: int) -> None:
        self.width = max(self.MIN_WIDTH, width)
        self.height = max(self.MIN_HEIGHT, height)
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        self.layout = self.calculate_layout()
        self.notes_scroll = max(0, self.notes_scroll)

    def _draw_text(self, text: str, font, color, x: int, y: int, *, max_width: Optional[int] = None):
        rendered = font.render(str(text), True, color)
        if max_width is not None and rendered.get_width() > max_width:
            ellipsis = font.render("…", True, color)
            allowed = max(0, max_width - ellipsis.get_width())
            value = str(text)
            while value and font.size(value)[0] > allowed:
                value = value[:-1]
            rendered = font.render(value + ("…" if value != str(text) else ""), True, color)
        self.screen.blit(rendered, (x, y))
        return rendered.get_rect(topleft=(x, y))

    def _draw_button(self, rect, label: str, *, primary: bool = False, enabled: bool = True) -> None:
        mouse = pygame.mouse.get_pos()
        hovering = rect.collidepoint(mouse) and enabled
        if not enabled:
            fill = (20, 20, 20)
            foreground = self.MUTED
        elif primary:
            fill = self.ACCENT_HOVER if hovering else self.ACCENT
            foreground = (0, 0, 0)
        else:
            fill = (245, 245, 245) if hovering else (0, 0, 0)
            foreground = (0, 0, 0) if hovering else self.TEXT
        pygame.draw.rect(self.screen, fill, rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=10)
        label_surface = self.button_font.render(label, True, foreground)
        self.screen.blit(label_surface, label_surface.get_rect(center=rect.center))

    def draw(self) -> None:
        self.screen.fill(self.BG)
        self._draw_header()
        if self.machine.state is AppState.MAIN:
            self._draw_main()
            if self.machine.menu_open:
                self._draw_menu()
        elif self.machine.state is AppState.ASSET_PREVIEW:
            self._draw_asset_preview()
        elif self.machine.state is AppState.CONFIRM_OVERWRITE:
            self._draw_main()
            self._draw_confirm_overwrite()
        pygame.display.flip()

    def _draw_header(self) -> None:
        header = self.layout.header
        pygame.draw.rect(self.screen, self.HEADER, header)
        pygame.draw.line(self.screen, self.HEADER_EDGE, (0, header.bottom - 2), (self.width, header.bottom - 2), 2)
        self._draw_text(PROGRAM_NAME, self.title_font, self.TEXT, 24, 16)
        archive_x = 24 + self.title_font.size(PROGRAM_NAME)[0] + 26
        available = max(70, self.layout.font_down_button.x - archive_x - 18)
        self._draw_text(self.machine.archive.name, self.archive_font, self.TEXT, archive_x, 34, max_width=available)
        self._draw_button(self.layout.font_down_button, "−")
        font_label = f"{self.machine.font_size_pt} pt"
        label_surface = self.archive_font.render(font_label, True, self.TEXT)
        label_rect = pygame.Rect(self.layout.font_down_button.right + 8, 19,
                                 max(20, self.layout.font_up_button.left - self.layout.font_down_button.right - 16), 62)
        self.screen.blit(label_surface, label_surface.get_rect(center=label_rect.center))
        self._draw_button(self.layout.font_up_button, "+")
        self._draw_button(self.layout.menu_button, "Menu ▾")

    def _draw_main(self) -> None:
        layout = self.layout
        self._draw_text("Title", self.label_font, self.MUTED, layout.title_box.x, layout.title_label_y)
        self._draw_field(layout.title_box, self.machine.title_buffer, FieldName.TITLE)
        self._draw_text("Notes", self.label_font, self.MUTED, layout.notes_box.x, layout.notes_label_y)
        self._draw_notes_field(layout.notes_box)
        self._draw_button(layout.make_note_button, "Make Note", primary=True)
        self._draw_status(layout.status_box)
        hint_line_height = self.small_font.get_linesize()
        hint_two_y = self.height - hint_line_height - 8
        hint_one_y = hint_two_y - hint_line_height - 6
        self._draw_text("Ctrl+S = Make Note  ·  Tab = next field", self.small_font, self.TEXT, 42, hint_one_y)
        self._draw_text("Font size: click − / + above, or press Ctrl + / Ctrl −", self.small_font, self.TEXT, 42, hint_two_y)

    def _draw_field(self, rect, buffer: TextBuffer, field_name: FieldName) -> None:
        active = self.machine.active_field is field_name
        pygame.draw.rect(self.screen, self.FIELD_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, self.ACCENT if active else self.BORDER, rect, width=2 if active else 1, border_radius=8)
        inner_x = rect.x + 12
        inner_y = rect.y + max(5, (rect.height - self.font.get_linesize()) // 2)
        available = rect.width - 24
        if not buffer.text:
            self._draw_text("Name this note…", self.font, self.PLACEHOLDER, inner_x, inner_y, max_width=available)
        else:
            display_start = 0
            while display_start < buffer.cursor and self.font.size(buffer.text[display_start:buffer.cursor])[0] > available - 8:
                display_start += 1
            shown = buffer.text[display_start:]
            self._draw_text(shown, self.font, self.TEXT, inner_x, inner_y, max_width=available)
        if active:
            cursor_text = buffer.text[display_start:buffer.cursor] if buffer.text else ""
            cx = inner_x + self.font.size(cursor_text)[0]
            cx = min(cx, rect.right - 8)
            pygame.draw.line(self.screen, self.ACCENT_HOVER, (cx, rect.y + 9), (cx, rect.bottom - 9), 2)

    def _visual_lines(self, text: str, font, max_width: int) -> list[tuple[str, int, int]]:
        """Return visible text chunks with their absolute character ranges."""
        if max_width < 30:
            return [(text, 0, len(text))]
        chunks: list[tuple[str, int, int]] = []
        line_start = 0
        text_length = len(text)
        if not text:
            return [("", 0, 0)]
        while line_start < text_length:
            newline = text.find("\n", line_start)
            logical_end = text_length if newline < 0 else newline
            if logical_end == line_start:
                chunks.append(("", line_start, line_start))
                line_start += 1
                continue
            pos = line_start
            while pos < logical_end:
                end = pos
                last_space = -1
                while end < logical_end and font.size(text[pos:end + 1])[0] <= max_width:
                    if text[end].isspace():
                        last_space = end + 1
                    end += 1
                if end == pos:
                    end = pos + 1
                elif end < logical_end and last_space > pos:
                    end = last_space
                chunks.append((text[pos:end], pos, end))
                pos = end
            if newline < 0:
                line_start = text_length
            else:
                line_start = newline + 1
                if line_start == text_length:
                    chunks.append(("", line_start, line_start))
        return chunks or [("", 0, 0)]

    def _draw_notes_field(self, rect) -> None:
        buffer = self.machine.notes_buffer
        active = self.machine.active_field is FieldName.NOTES
        pygame.draw.rect(self.screen, self.FIELD_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, self.ACCENT if active else self.BORDER, rect, width=2 if active else 1, border_radius=8)
        inset_x = rect.x + 12
        inset_y = rect.y + 10
        available_width = rect.width - 24
        available_height = rect.height - 18
        line_height = self.font.get_linesize() + 4

        if not buffer.text:
            self._draw_text("Write the note here…", self.font, self.PLACEHOLDER, inset_x, inset_y)
            if active:
                pygame.draw.line(self.screen, self.ACCENT_HOVER, (inset_x, inset_y), (inset_x, inset_y + line_height - 3), 2)
            return

        lines = self._visual_lines(buffer.text, self.font, available_width)
        max_visible = max(1, available_height // line_height)
        total_scroll = max(0, len(lines) - max_visible)
        self.notes_scroll = max(0, min(total_scroll, self.notes_scroll))
        first = self.notes_scroll
        last = min(len(lines), first + max_visible)
        cursor_line_index = None
        cursor_x_text = ""
        for index, (line, start, end) in enumerate(lines):
            if start <= buffer.cursor <= end:
                cursor_line_index = index
                cursor_x_text = buffer.text[start:buffer.cursor]
                # Prefer the earlier line at an exact wrap boundary.
                break
        if active and cursor_line_index is not None:
            if cursor_line_index < first:
                first = cursor_line_index
                self.notes_scroll = first
            elif cursor_line_index >= last:
                first = cursor_line_index - max_visible + 1
                self.notes_scroll = max(0, first)
                first = self.notes_scroll
            last = min(len(lines), first + max_visible)

        pygame.draw.rect(self.screen, self.PANEL, (rect.x + 5, rect.y + 5, 6, rect.height - 10), border_radius=3)
        for index in range(first, last):
            line, start, end = lines[index]
            y = inset_y + (index - first) * line_height
            if index == cursor_line_index and active and buffer.select_all:
                selected = pygame.Rect(inset_x, y, min(available_width, max(10, self.font.size(line)[0])), line_height)
                pygame.draw.rect(self.screen, (70, 51, 109), selected, border_radius=3)
            self._draw_text(line, self.font, self.TEXT, inset_x, y, max_width=available_width)
            if active and index == cursor_line_index:
                cx = inset_x + self.font.size(cursor_x_text)[0]
                pygame.draw.line(self.screen, self.ACCENT_HOVER, (cx, y), (cx, y + line_height - 2), 2)

    def _draw_status(self, rect) -> None:
        # Keep bright white on black; error states carry an explicit ERROR prefix.
        self._draw_text(self.machine.status, self.status_font, self.TEXT, rect.x, rect.y + 6, max_width=rect.width)

    def _draw_menu(self) -> None:
        rect = self.layout.menu_item_asset_preview
        pygame.draw.rect(self.screen, (0, 0, 0), rect, border_radius=8)
        pygame.draw.rect(self.screen, self.BORDER, rect, width=2, border_radius=8)
        self._draw_text("Asset Preview", self.button_font, self.TEXT, rect.x + 14, rect.y + 8)

    def _draw_asset_preview(self) -> None:
        self._draw_text("Asset Preview", self.title_font, self.TEXT, 42, 112)
        picker_dir, _picker_file = self.machine.picker_start()
        self._draw_text(
            f"Picker starts in: {picker_dir}", self.small_font, self.TEXT, 44, 164,
            max_width=self.width - 90,
        )
        preview_height = max(120, self.layout.status_box.y - 244)
        preview_rect = pygame.Rect(42, 220, self.width - 84, preview_height)
        pygame.draw.rect(self.screen, (0, 0, 0), preview_rect, border_radius=9)
        pygame.draw.rect(self.screen, self.BORDER, preview_rect, width=1, border_radius=9)

        if self.machine.preview_surface is None:
            prompt = "Choose a PNG to display it here."
            if self.machine.preview_path is not None:
                prompt = "The selected image could not be displayed. Choose another PNG."
            rendered = self.font.render(prompt, True, self.TEXT)
            self.screen.blit(rendered, rendered.get_rect(center=preview_rect.center))
        else:
            original = self.machine.preview_surface
            max_w = max(1, preview_rect.width - 32)
            max_h = max(1, preview_rect.height - 74)
            scale = min(max_w / original.get_width(), max_h / original.get_height(), 1.0)
            display_w = max(1, int(original.get_width() * scale))
            display_h = max(1, int(original.get_height() * scale))
            shown = pygame.transform.scale(original, (display_w, display_h))
            image_area = pygame.Rect(preview_rect.x + 10, preview_rect.y + 42, preview_rect.width - 20, preview_rect.height - 52)
            self.screen.blit(shown, shown.get_rect(center=image_area.center))
            info = f"{self.machine.preview_path.name}  ·  {original.get_width()} × {original.get_height()} px"
            self._draw_text(info, self.small_font, self.TEXT, preview_rect.x + 12, preview_rect.y + 12, max_width=preview_rect.width - 24)

        self._draw_button(self.layout.preview_choose_button, "Choose PNG", primary=True)
        self._draw_button(self.layout.preview_back_button, "Back")
        self._draw_status(pygame.Rect(250, self.layout.status_box.y, max(280, self.width - 500), 58))

    def _draw_confirm_overwrite(self) -> None:
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))
        card = pygame.Rect(self.width // 2 - 360, self.height // 2 - 145, 720, 290)
        pygame.draw.rect(self.screen, (0, 0, 0), card, border_radius=8)
        pygame.draw.rect(self.screen, self.BORDER, card, width=2, border_radius=8)
        self._draw_text("Replace existing note?", self.title_font, self.TEXT, card.x + 28, card.y + 24)
        filename = self.machine.pending_note_path.name if self.machine.pending_note_path else "(unknown file)"
        self._draw_text(f"{filename} already exists.", self.font, self.TEXT, card.x + 28, card.y + 83, max_width=card.width - 56)
        self._draw_text("Replace its contents with the text currently in Notes?", self.small_font, self.TEXT, card.x + 28, card.y + 135, max_width=card.width - 56)
        self._draw_button(self.layout.confirm_replace_button, "Replace File", primary=True)
        self._draw_button(self.layout.confirm_cancel_button, "Cancel")

    def set_notes_cursor_from_mouse(self, buffer: TextBuffer, point: tuple[int, int]) -> None:
        rect = self.layout.notes_box
        inset_x = rect.x + 12
        inset_y = rect.y + 10
        available_width = rect.width - 24
        line_height = self.font.get_linesize() + 4
        lines = self._visual_lines(buffer.text, self.font, available_width)
        max_visible = max(1, (rect.height - 18) // line_height)
        self.notes_scroll = max(0, min(self.notes_scroll, len(lines) - max_visible))
        line_index = self.notes_scroll + max(0, (point[1] - inset_y) // line_height)
        line_index = max(self.notes_scroll, min(len(lines) - 1, line_index))
        line, start, end = lines[line_index]
        target_x = max(0, point[0] - inset_x)
        cursor = start
        for count in range(1, len(line) + 1):
            width = self.font.size(line[:count])[0]
            if width >= target_x:
                previous_width = self.font.size(line[:count - 1])[0]
                cursor = start + (count - 1 if target_x - previous_width < width - target_x else count)
                break
            cursor = start + count
        buffer.cursor = max(start, min(end, cursor))
        buffer.select_all = False

    def scroll_notes(self, lines: int) -> None:
        if self.machine.state is not AppState.MAIN:
            return
        visible = max(1, (self.layout.notes_box.height - 18) // (self.font.get_linesize() + 4))
        total = len(self._visual_lines(self.machine.notes_buffer.text, self.font, self.layout.notes_box.width - 24))
        self.notes_scroll = max(0, min(max(0, total - visible), self.notes_scroll + lines))

    def choose_png(self, machine: StateMachine) -> None:
        """Open the Windows-native file chooser at the configured assets folder."""
        import tkinter as tk
        from tkinter import filedialog

        initial_dir, initial_file = machine.picker_start()
        root = None
        selected = ""
        pygame.key.stop_text_input()
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                pass
            root.update_idletasks()
            selected = filedialog.askopenfilename(
                parent=root,
                title="Choose a PNG to preview — Spiffy's Gift",
                initialdir=str(initial_dir),
                initialfile=initial_file or "",
                filetypes=[("PNG images", "*.png"), ("All files", "*.*")],
            )
        except Exception as exc:
            machine._set_status(f"Could not open file picker: {exc}", is_error=True)
            machine._log("ASSET ERROR", f"File picker failed: {type(exc).__name__}: {exc}")
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
            pygame.key.start_text_input()
            # Drain stale window events emitted while Tk owned the foreground.
            pygame.event.clear(pygame.MOUSEMOTION)
        if selected:
            machine.choose_asset(selected)


# ---------------------------------------------------------------------------
# Application runner
# ---------------------------------------------------------------------------

def run_application(archive: RunArchive, config: dict, config_warning: Optional[str] = None) -> int:
    global pygame
    import pygame as pygame_module
    pygame = pygame_module

    pygame.init()
    pygame.font.init()
    machine = StateMachine(archive, config, config_warning)
    ui = SGGInterface(machine)
    clock = pygame.time.Clock()
    pygame.key.start_text_input()
    append_log(archive, "UI", "Main window opened")

    try:
        while machine.state is not AppState.CLOSED:
            for event in pygame.event.get():
                machine.dispatch(event, ui)
            ui.draw()
            clock.tick(60)
    except Exception as exc:
        append_log(archive, "FATAL ERROR", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        append_log(archive, "SHUTDOWN", f"Exited from state {machine.state.name}")
        try:
            pygame.key.stop_text_input()
            pygame.quit()
        except Exception:
            pass
    return 0


def main() -> int:
    # This is deliberately the first runtime operation: create the run archive,
    # preserve this source, and establish the log before initializing any UI.
    try:
        archive = initialize_archive()
    except Exception as exc:
        print(f"SGG startup failed before UI initialization: {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"SGG archive: {archive.name}", flush=True)
    try:
        # initialize_archive has already snapshotted main sgg.config into the
        # archive. Now read the authoritative main config for this live run.
        config, config_warning = load_main_config()
        if config_warning:
            append_log(archive, "CONFIG ERROR", config_warning)
        else:
            append_log(archive, "CONFIG", f"Loaded main settings from {CONFIG_PATH}")
        return run_application(archive, config, config_warning)
    except Exception as exc:
        print(f"SGG failed. See {archive.log_path}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
