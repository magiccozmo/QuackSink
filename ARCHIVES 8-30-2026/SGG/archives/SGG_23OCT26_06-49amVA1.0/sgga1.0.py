#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spiffy's Gift tool — SGGA 1.0.

Major generation A replaces the old split shop/storage screen with a small
area-based world: BritRun Market and the Alchemy Shop are independent screens
connected by doors. Area connections are data-driven, so future doors, paths,
and edge transitions can use the same transition mechanism.

The playable slice includes keyboard movement, area-local collision, door
transitions, hover labels with red/green take status, two-click item interaction,
drag-to-move merchandise, inventory/drop controls, the bucket gag, and screenshots.

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
import math
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
VERSION = "A1.0"  # Major letter = feature/UI generation; whole number = release; decimal = minor fix.
VERSION_TAG = f"V{VERSION}"
RUNTIME_FILE = "sgga1.0.py"
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
    PLAY_GAME = auto()
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
    play_button: "pygame.Rect"
    screenshot_button: "pygame.Rect"
    status_box: "pygame.Rect"
    preview_choose_button: "pygame.Rect"
    preview_back_button: "pygame.Rect"
    game_back_button: "pygame.Rect"
    game_screenshot_button: "pygame.Rect"
    game_view_rect: "pygame.Rect"
    confirm_replace_button: "pygame.Rect"
    confirm_cancel_button: "pygame.Rect"
    font_down_button: "pygame.Rect"
    font_up_button: "pygame.Rect"


# pygame is imported after archive creation in main(); type names in this module
# are quoted where needed so importing the module itself doesn't initialize SDL.
pygame = None  # Assigned by main() after archive creation.


GAME_WIDTH = 1280
GAME_HEIGHT = 640

AREA_MARKET = "britrun_market"
AREA_ALCHEMY_SHOP = "alchemy_shop"


@dataclass(frozen=True)
class AreaDefinition:
    """Data describing one single-screen world area."""
    area_id: str
    display_name: str
    visual_style: str


@dataclass(frozen=True)
class AreaConnection:
    """A reusable route between areas.

    trigger may be "door", "path", or "edge". Only door connections are
    populated in this first slice; an edge connection can later name left,
    right, top, or bottom without needing a different transition system.
    """
    connection_id: str
    from_area_id: str
    to_area_id: str
    trigger: str
    source_object_id: Optional[str]
    arrival_x: float
    arrival_y: float
    label: str
    edge: Optional[str] = None


@dataclass
class GameObject:
    """A world object that belongs to one area and may be interacted with."""
    object_id: str
    name: str
    kind: str
    area_id: str
    x: float
    y: float
    width: int
    height: int
    takeable: bool = True
    stealable: bool = True
    in_inventory: bool = False
    moved: bool = False
    on_shelf: bool = False

    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.width, self.height)


class GameModel:
    """The authoritative model for SGG's first two-area playable world."""

    def __init__(self):
        self.areas = {
            AREA_MARKET: AreaDefinition(AREA_MARKET, "BritRun Market", "market"),
            AREA_ALCHEMY_SHOP: AreaDefinition(AREA_ALCHEMY_SHOP, "Alchemy Shop", "shop"),
        }
        # This is the complete active travel graph for SGGA1.0. Additions are
        # data records; all connections call the same activate_connection().
        self.connections = [
            AreaConnection(
                "market_to_alchemy_shop", AREA_MARKET, AREA_ALCHEMY_SHOP,
                "door", "alchemy_shop_door", 640, 500,
                "Enter the Alchemy Shop",
            ),
            AreaConnection(
                "alchemy_shop_to_market", AREA_ALCHEMY_SHOP, AREA_MARKET,
                "door", "shop_exit_door", 640, 300,
                "Return to BritRun Market",
            ),
        ]
        self.current_area_id = AREA_MARKET
        self.player_x = 640.0
        self.player_y = 490.0
        self.player_width = 26
        self.player_height = 36

        self.bucket_carried = False
        self.bucket_on_head = False
        self.inventory: list[str] = []
        self.inventory_open = False
        self.inventory_selected_id: Optional[str] = None
        self.selected_object_id: Optional[str] = None
        self.drag_candidate_id: Optional[str] = None
        self.drag_start: Optional[tuple[int, int]] = None
        self.dragging_object_id: Optional[str] = None

        self.objects = [
            # BritRun Market: the front door is a real clickable world object.
            GameObject("market_apple", "Red Apple", "fruit", AREA_MARKET, 151, 246, 27, 27, True, True),
            GameObject("market_moonflower", "Market Moonflower", "herb", AREA_MARKET, 216, 242, 28, 33, True, False),
            GameObject("market_gold_pouch", "Gold Pouch", "gold", AREA_MARKET, 282, 247, 28, 24, True, True),
            GameObject("market_healing_potion", "Healing Potion", "potion", AREA_MARKET, 910, 245, 25, 31, True, True),
            GameObject("market_spell_scroll", "Spell Scroll", "scroll", AREA_MARKET, 974, 250, 29, 24, True, True),
            GameObject("market_free_sample", "Free Herb Sample", "herb", AREA_MARKET, 1040, 243, 28, 33, True, False),
            GameObject("alchemy_shop_door", "Alchemy Shop Door", "door", AREA_MARKET, 596, 149, 88, 99, False, False),

            # Alchemy Shop: a single interior screen, not a second storage room.
            GameObject("shop_moonflower", "Moonflower", "herb", AREA_ALCHEMY_SHOP, 137, 109, 28, 33, True, True, False, False, True),
            GameObject("shop_healing_potion", "Healing Potion", "potion", AREA_ALCHEMY_SHOP, 207, 110, 25, 31, True, True, False, False, True),
            GameObject("shop_spell_scroll", "Spell Scroll", "scroll", AREA_ALCHEMY_SHOP, 280, 114, 29, 24, True, True, False, False, True),
            GameObject("shop_gold_pouch", "Gold Pouch", "gold", AREA_ALCHEMY_SHOP, 878, 112, 28, 24, True, True, False, False, True),
            GameObject("shop_blue_vial", "Blue Vial", "potion_blue", AREA_ALCHEMY_SHOP, 957, 108, 25, 31, True, True, False, False, True),
            GameObject("shop_counter_sample", "Free Trial Vial", "potion_blue", AREA_ALCHEMY_SHOP, 775, 241, 25, 31, True, False),
            GameObject("shop_bucket", "Bucket", "bucket", AREA_ALCHEMY_SHOP, 157, 451, 36, 30, False, False),
            GameObject("shop_exit_door", "Door to BritRun Market", "door", AREA_ALCHEMY_SHOP, 590, 508, 100, 75, False, False),
        ]

    @property
    def current_area(self) -> AreaDefinition:
        return self.areas[self.current_area_id]

    def object_by_id(self, object_id: Optional[str]) -> Optional[GameObject]:
        if object_id is None:
            return None
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def live_objects(self) -> list[GameObject]:
        result = []
        for obj in self.objects:
            if obj.area_id != self.current_area_id or obj.in_inventory:
                continue
            if obj.kind == "bucket" and (self.bucket_carried or self.bucket_on_head):
                continue
            result.append(obj)
        return result

    def hit_test(self, point: tuple[int, int]) -> Optional[GameObject]:
        # Later-defined objects have priority if their rectangles overlap.
        for obj in reversed(self.live_objects()):
            if obj.rect().collidepoint(point):
                if obj.kind in {"door", "path", "portal", "bucket"} or obj.takeable:
                    return obj
        return None

    def vendor_position(self) -> tuple[float, float]:
        if self.current_area_id == AREA_MARKET:
            return (262.0, 229.0)
        return (640.0, 233.0)

    def vendor_rect(self):
        x, y = self.vendor_position()
        return pygame.Rect(round(x - 26), round(y - 20), 52, 64)

    def vendor_head_rect(self):
        x, y = self.vendor_position()
        return pygame.Rect(round(x - 19), round(y - 22), 38, 28)

    def player_rect_at(self, x: float, y: float):
        return pygame.Rect(
            round(x - self.player_width / 2),
            round(y - self.player_height / 2),
            self.player_width,
            self.player_height,
        )

    def has_edge_connection(self, edge: str) -> bool:
        return any(
            c.from_area_id == self.current_area_id and c.trigger == "edge" and c.edge == edge
            for c in self.connections
        )

    def solid_rects(self):
        """Collision geometry for the current area only."""
        if self.current_area_id == AREA_MARKET:
            return [
                pygame.Rect(90, 270, 335, 51),       # left market stall counter
                pygame.Rect(850, 270, 335, 51),      # right market stall counter
                pygame.Rect(469, 91, 342, 157),      # shopfront; its door is clicked
                pygame.Rect(30, 50, 10, GAME_HEIGHT - 95),
                pygame.Rect(GAME_WIDTH - 40, 50, 10, GAME_HEIGHT - 95),
            ]
        return [
            pygame.Rect(24, 44, GAME_WIDTH - 48, 25),
            pygame.Rect(24, 44, 24, GAME_HEIGHT - 88),
            pygame.Rect(GAME_WIDTH - 48, 44, 24, GAME_HEIGHT - 88),
            # Bottom wall leaves an opening where the market exit door sits.
            pygame.Rect(24, 590, 552, 26),
            pygame.Rect(704, 590, GAME_WIDTH - 728, 26),
            pygame.Rect(92, 142, 333, 31),           # left wall shelving
            pygame.Rect(850, 142, 315, 31),          # right wall shelving
            pygame.Rect(447, 268, 386, 68),          # shop counter
            pygame.Rect(814, 218, 262, 43),          # free-trial display counter
        ]

    def can_move_to(self, x: float, y: float) -> bool:
        edge_margin = 26
        low_x = 20 if self.has_edge_connection("left") else 52
        high_x = GAME_WIDTH - 20 if self.has_edge_connection("right") else GAME_WIDTH - 52
        low_y = 30 if self.has_edge_connection("top") else 72
        high_y = GAME_HEIGHT - 24 if self.has_edge_connection("bottom") else GAME_HEIGHT - 62
        if not (low_x <= x <= high_x and low_y <= y <= high_y):
            return False
        player_rect = self.player_rect_at(x, y)
        return not any(player_rect.colliderect(rect) for rect in self.solid_rects())

    def is_vendor_watching(self, obj: GameObject) -> bool:
        """A deliberately simple sight rule that makes the status discoverable."""
        if not obj.stealable or obj.area_id != self.current_area_id:
            return False
        if self.current_area_id == AREA_ALCHEMY_SHOP and self.bucket_on_head:
            return False
        vx, vy = self.vendor_position()
        ox = obj.x + obj.width / 2
        oy = obj.y + obj.height / 2
        sight_radius = 315 if self.current_area_id == AREA_MARKET else 365
        return math.hypot(ox - vx, oy - vy) <= sight_radius

    def place_dragged_object(self, obj: GameObject, point: tuple[int, int]) -> None:
        x, y = point
        obj.x = float(max(54, min(GAME_WIDTH - 54 - obj.width, x - obj.width / 2)))
        obj.y = float(max(82, min(GAME_HEIGHT - 72 - obj.height, y - obj.height / 2)))
        obj.area_id = self.current_area_id
        obj.moved = True

    def connection_for(self, trigger: str, source_object_id: Optional[str] = None,
                       edge: Optional[str] = None) -> Optional[AreaConnection]:
        for connection in self.connections:
            if connection.from_area_id != self.current_area_id or connection.trigger != trigger:
                continue
            if connection.source_object_id != source_object_id:
                continue
            if trigger == "edge" and connection.edge != edge:
                continue
            return connection
        return None

    def activate_connection(self, trigger: str, source_object_id: Optional[str] = None,
                            edge: Optional[str] = None) -> Optional[AreaConnection]:
        """Follow a graph edge for any supported transition trigger."""
        connection = self.connection_for(trigger, source_object_id, edge)
        if connection is None:
            return None
        self.current_area_id = connection.to_area_id
        self.player_x = connection.arrival_x
        self.player_y = connection.arrival_y
        self.selected_object_id = None
        self.drag_candidate_id = None
        self.drag_start = None
        self.dragging_object_id = None
        self.inventory_open = False
        return connection

    def inventory_button_rect(self):
        return pygame.Rect(1080, 6, 180, 32)

    def inventory_panel_rect(self):
        return pygame.Rect(930, 47, 330, 474)

    def inventory_close_rect(self):
        return pygame.Rect(1214, 54, 34, 30)

    def inventory_drop_rect(self):
        return pygame.Rect(951, 462, 135, 38)

    def inventory_row_rect(self, index: int):
        return pygame.Rect(950, 92 + index * 29, 290, 25)


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
        self.game: Optional[GameModel] = None
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
        elif self.state is AppState.PLAY_GAME:
            self._dispatch_game(event, ui)

    def start_game(self) -> None:
        if self.game is None:
            self.game = GameModel()
            self._log("GAME", "Initialized SGGA1.0 world: BritRun Market <-> Alchemy Shop")
        self.menu_open = False
        self.active_field = None
        self.transition(AppState.PLAY_GAME, "Play Game button")
        self._set_status("Welcome to BritRun Market. Move with WASD or arrow keys; click the Alchemy Shop door to enter.")

    def update(self, elapsed_seconds: float, ui: "SGGInterface") -> None:
        if self.state is not AppState.PLAY_GAME or self.game is None:
            return
        dt = max(0.0, min(0.05, elapsed_seconds))
        if dt <= 0:
            return
        keys = pygame.key.get_pressed()
        dx = float(bool(keys[pygame.K_RIGHT] or keys[pygame.K_d])) - float(bool(keys[pygame.K_LEFT] or keys[pygame.K_a]))
        dy = float(bool(keys[pygame.K_DOWN] or keys[pygame.K_s])) - float(bool(keys[pygame.K_UP] or keys[pygame.K_w]))
        if dx == 0 and dy == 0:
            return
        # Ctrl+S is a screenshot command in game, not a downward movement key.
        if pygame.key.get_mods() & pygame.KMOD_CTRL and keys[pygame.K_s]:
            dy = 0.0
        if dx == 0 and dy == 0:
            return
        length = (dx * dx + dy * dy) ** 0.5
        dx = dx / length * 220.0 * dt
        dy = dy / length * 220.0 * dt
        game = self.game
        candidate_x = game.player_x + dx
        if game.can_move_to(candidate_x, game.player_y):
            game.player_x = candidate_x
        candidate_y = game.player_y + dy
        if game.can_move_to(game.player_x, candidate_y):
            game.player_y = candidate_y

        # Edge-triggered travel is dormant until a future area adds an edge link.
        edge = None
        if game.player_x <= 27:
            edge = "left"
        elif game.player_x >= GAME_WIDTH - 27:
            edge = "right"
        elif game.player_y <= 31:
            edge = "top"
        elif game.player_y >= GAME_HEIGHT - 25:
            edge = "bottom"
        if edge:
            connection = game.activate_connection("edge", edge=edge)
            if connection:
                self._log("AREA TRANSITION", f"{connection.from_area_id} -> {connection.to_area_id} via {edge} edge")
                self._set_status(f"Entered {game.current_area.display_name}.")

    def _dispatch_game(self, event, ui: "SGGInterface") -> None:
        game = self.game
        if game is None:
            self.transition(AppState.MAIN, "Missing game model; return safely")
            self._set_status("Game state was unavailable; returned to the tool.", is_error=True)
            return

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_ESCAPE:
                if game.inventory_open:
                    game.inventory_open = False
                    return
                self.transition(AppState.MAIN, "Returned from Play Game")
                self._set_status("Returned to the SGG tool.")
                return
            if event.key == pygame.K_F12 or ((mods & pygame.KMOD_CTRL) and event.key == pygame.K_s):
                ui.save_screenshot(self)
                return
            if event.key == pygame.K_i:
                game.inventory_open = not game.inventory_open
                return
            if event.key == pygame.K_SPACE and game.bucket_carried:
                bucket = game.object_by_id("shop_bucket")
                if bucket is not None:
                    bucket.area_id = game.current_area_id
                    bucket.x = game.player_x - bucket.width / 2
                    bucket.y = game.player_y + 10
                game.bucket_carried = False
                self._set_status("Set the bucket down. Click it to pick it up again.")
                self._log("GAME OBJECT", "Set down carried bucket with SPACE")
                return

        if event.type == pygame.MOUSEMOTION:
            buttons = getattr(event, "buttons", None)
            pressed = bool(buttons and buttons[0]) if buttons is not None else bool(pygame.mouse.get_pressed()[0])
            if game.drag_candidate_id and pressed and not game.inventory_open:
                point = ui.screen_to_game(event.pos)
                if point is None:
                    return
                start = game.drag_start or point
                distance = ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** 0.5
                if distance >= 8:
                    game.dragging_object_id = game.drag_candidate_id
                    obj = game.object_by_id(game.dragging_object_id)
                    if obj is not None:
                        obj.x = float(point[0] - obj.width / 2)
                        obj.y = float(point[1] - obj.height / 2)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # These controls live in the host window rather than in the game canvas.
            if ui.layout.game_back_button.collidepoint(event.pos):
                self.transition(AppState.MAIN, "Back to Tool button")
                self._set_status("Returned to the SGG tool.")
                return
            if ui.layout.game_screenshot_button.collidepoint(event.pos):
                ui.save_screenshot(self)
                return

            point = ui.screen_to_game(event.pos)
            if point is None:
                return

            if game.inventory_open:
                if game.inventory_close_rect().collidepoint(point):
                    game.inventory_open = False
                    return
                if game.inventory_drop_rect().collidepoint(point):
                    self._drop_inventory_selection(game)
                    return
                if game.inventory_panel_rect().collidepoint(point):
                    for index, object_id in enumerate(game.inventory):
                        if game.inventory_row_rect(index).collidepoint(point):
                            game.inventory_selected_id = object_id
                            obj = game.object_by_id(object_id)
                            if obj:
                                self._set_status(f"Selected inventory item: {obj.name}. Use Drop Item to put it down here.")
                            return
                    return
                # Clicking outside an open inventory closes it and consumes the click.
                game.inventory_open = False
                return

            if game.inventory_button_rect().collidepoint(point):
                game.inventory_open = True
                if game.inventory_selected_id not in game.inventory:
                    game.inventory_selected_id = game.inventory[0] if game.inventory else None
                return

            # Door transitions happen on a single click, from anywhere on screen.
            hit = game.hit_test(point)
            if hit is not None and hit.kind in {"door", "path", "portal"}:
                trigger = "door" if hit.kind == "door" else ("path" if hit.kind == "path" else "portal")
                connection = game.activate_connection(trigger, source_object_id=hit.object_id)
                if connection:
                    self._log("AREA TRANSITION", f"{connection.from_area_id} -> {connection.to_area_id} via {trigger} {hit.object_id}")
                    self._set_status(f"{connection.label}. Now in {game.current_area.display_name}.")
                else:
                    self._set_status(f"{hit.name} is not connected yet.")
                return

            # The bucket is a pick-up/use object with a special interaction.
            if game.bucket_carried:
                if game.vendor_head_rect().inflate(58, 48).collidepoint(point):
                    vx, vy = game.vendor_position()
                    distance = math.hypot(game.player_x - vx, game.player_y - vy)
                    if distance > 165:
                        self._set_status("Walk closer to the shopkeeper before putting the bucket on their head.")
                    else:
                        game.bucket_carried = False
                        if game.current_area_id == AREA_ALCHEMY_SHOP:
                            game.bucket_on_head = True
                            self._set_status("BUCKET EXPLOIT ACTIVE: the shopkeeper cannot see you taking shop goods.")
                            self._log("EXPLOIT", "Bucket placed on Alchemy Shop shopkeeper; watched goods are safe to take")
                        else:
                            bucket = game.object_by_id("shop_bucket")
                            if bucket:
                                bucket.area_id = game.current_area_id
                                bucket.x = game.player_x - bucket.width / 2
                                bucket.y = game.player_y + 6
                            self._set_status("The bucket is a poor fit for this market stall. You set it down.")
                    return
                bucket = game.object_by_id("shop_bucket")
                if bucket is not None:
                    bucket.area_id = game.current_area_id
                    bucket.x = game.player_x - bucket.width / 2
                    bucket.y = game.player_y + 6
                game.bucket_carried = False
                self._set_status("Set the bucket down. Walk near a shopkeeper and click their head to try the trick.")
                self._log("GAME OBJECT", "Set down carried bucket after ground click")
                return

            if game.bucket_on_head and game.current_area_id == AREA_ALCHEMY_SHOP and game.vendor_head_rect().inflate(26, 22).collidepoint(point):
                vx, vy = game.vendor_position()
                distance = math.hypot(game.player_x - vx, game.player_y - vy)
                if distance <= 165:
                    game.bucket_on_head = False
                    game.bucket_carried = True
                    self._set_status("You lifted the bucket off the shopkeeper. The shop is watching again.")
                    self._log("GAME OBJECT", "Removed bucket from shopkeeper head")
                else:
                    self._set_status("Move closer to the shopkeeper to retrieve the bucket.")
                return

            if hit is None:
                game.selected_object_id = None
                return
            if hit.kind == "bucket":
                game.bucket_carried = True
                game.selected_object_id = None
                self._set_status("Picked up the bucket. Click the shopkeeper's head nearby, or press SPACE to set it down.")
                self._log("GAME OBJECT", "Picked up bucket")
                return
            if hit.takeable:
                game.drag_candidate_id = hit.object_id
                game.drag_start = point
                game.dragging_object_id = None
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if game.drag_candidate_id is None:
                return
            candidate = game.object_by_id(game.drag_candidate_id)
            dragging_id = game.dragging_object_id
            point = ui.screen_to_game(event.pos)
            if dragging_id and candidate is not None:
                if point is not None:
                    game.place_dragged_object(candidate, point)
                game.selected_object_id = candidate.object_id
                place = "the Market" if game.current_area_id == AREA_MARKET else "the shop"
                self._set_status(f"Moved {candidate.name} in {place}. Click it again to try taking it.")
                self._log("GAME OBJECT", f"Dragged {candidate.name} to ({int(candidate.x)},{int(candidate.y)}) in {game.current_area_id}")
            elif candidate is not None and point is not None and candidate.rect().inflate(12, 12).collidepoint(point):
                if game.selected_object_id == candidate.object_id:
                    if candidate.stealable and game.is_vendor_watching(candidate):
                        self._set_status(f"STEAL FAILED: the vendor can see you taking {candidate.name}. Move it out of sight or use a distraction.")
                        self._log("GAME ACTION", f"Failed take attempt for {candidate.name}; vendor had line of sight")
                    else:
                        candidate.in_inventory = True
                        if candidate.object_id not in game.inventory:
                            game.inventory.append(candidate.object_id)
                        game.inventory_selected_id = candidate.object_id
                        game.selected_object_id = None
                        action = "Took" if candidate.stealable else "Collected"
                        self._set_status(f"{action} {candidate.name}. Inventory has {len(game.inventory)} item(s).")
                        self._log("GAME ACTION", f"{action} {candidate.name}; stealable={candidate.stealable}; area={game.current_area_id}")
                else:
                    game.selected_object_id = candidate.object_id
                    verb = "try taking" if candidate.stealable else "collect"
                    self._set_status(f"Interacted with {candidate.name}. Click it again to {verb}, or drag it to move it.")
            game.drag_candidate_id = None
            game.drag_start = None
            game.dragging_object_id = None

    def _drop_inventory_selection(self, game: GameModel) -> None:
        object_id = game.inventory_selected_id
        if object_id not in game.inventory:
            self._set_status("Select an inventory item before using Drop Item.")
            return
        obj = game.object_by_id(object_id)
        if obj is None:
            game.inventory.remove(object_id)
            game.inventory_selected_id = None
            self._set_status("That inventory record was missing; removed the stale entry.", is_error=True)
            return
        game.inventory.remove(object_id)
        obj.in_inventory = False
        obj.area_id = game.current_area_id
        obj.x = max(58.0, min(GAME_WIDTH - 58.0 - obj.width, game.player_x + 24 - obj.width / 2))
        obj.y = max(84.0, min(GAME_HEIGHT - 80.0 - obj.height, game.player_y + 12))
        obj.moved = True
        game.selected_object_id = obj.object_id
        game.inventory_selected_id = game.inventory[0] if game.inventory else None
        self._set_status(f"Dropped {obj.name} in {game.current_area.display_name}.")
        self._log("GAME INVENTORY", f"Dropped {obj.name} into {game.current_area_id}")

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
        elif ui.layout.play_button.collidepoint(point):
            self.start_game()
            return
        elif ui.layout.screenshot_button.collidepoint(point):
            ui.save_screenshot(self)
            return
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
        self.game_font = pygame.font.SysFont("consolas", 22, bold=True)
        self.game_small_font = pygame.font.SysFont("consolas", 16, bold=True)

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
        status_y = controls_y - 54
        notes_bottom = status_y - 24
        notes_height = max(150, notes_bottom - notes_top)
        notes_box = pygame.Rect(42, notes_top, width - 84, notes_height)

        play_button = pygame.Rect(42, controls_y, 180, 62)
        screenshot_button = pygame.Rect(236, controls_y, 174, 62)
        make_note_button = pygame.Rect(width - 230, controls_y, 188, 62)
        status_box = pygame.Rect(430, status_y, max(220, width - 430 - 260), 42)
        preview_choose = pygame.Rect(42, controls_y, 188, 62)
        preview_back = pygame.Rect(width - 230, controls_y, 188, 62)
        game_view = pygame.Rect(24, 108, width - 48, height - 200)
        game_back = pygame.Rect(42, height - 82, 180, 60)
        game_screenshot = pygame.Rect(236, height - 82, 190, 60)
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
            play_button=play_button,
            screenshot_button=screenshot_button,
            status_box=status_box,
            preview_choose_button=preview_choose,
            preview_back_button=preview_back,
            game_back_button=game_back,
            game_screenshot_button=game_screenshot,
            game_view_rect=game_view,
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

    def screen_to_game(self, point: tuple[int, int]) -> Optional[tuple[int, int]]:
        """Map window coordinates into the fixed-size game world."""
        target = getattr(self, "game_blit_rect", None)
        if target is None or target.width <= 0 or target.height <= 0 or not target.collidepoint(point):
            return None
        x = round((point[0] - target.x) * GAME_WIDTH / target.width)
        y = round((point[1] - target.y) * GAME_HEIGHT / target.height)
        return max(0, min(GAME_WIDTH - 1, x)), max(0, min(GAME_HEIGHT - 1, y))

    def save_screenshot(self, machine: StateMachine) -> None:
        """Save the current SGG window inside this run's archive."""
        stamp = datetime.now().astimezone().strftime("%d%b%y_%I-%M-%S%p").upper()
        stamp = stamp.replace("AM", "am").replace("PM", "pm")
        base = f"SGG_SCREEN_{stamp}"
        # Screenshots are run artifacts, so they belong beside this run's
        # source copy, config snapshot, and log—not in the project root.
        target = machine.archive.directory / f"{base}.png"
        suffix = 2
        while target.exists():
            target = machine.archive.directory / f"{base}_{suffix:02d}.png"
            suffix += 1
        try:
            pygame.image.save(self.screen, str(target))
            machine._log("SCREENSHOT", f"Saved current window to run archive: {target.name}")
            machine._set_status(f"Screenshot saved in this run's archive: {target.name}")
        except Exception as exc:
            machine._log("SCREENSHOT ERROR", f"Could not save screenshot to {target}: {type(exc).__name__}: {exc}")
            machine._set_status(f"Screenshot failed: {type(exc).__name__}: {exc}", is_error=True)

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
        elif self.machine.state is AppState.PLAY_GAME:
            self._draw_game()
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
        self._draw_status(layout.status_box)
        self._draw_button(layout.play_button, "Play Game", primary=True)
        self._draw_button(layout.screenshot_button, "Screenshot")
        self._draw_button(layout.make_note_button, "Make Note", primary=True)
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

    # ------------------------------------------------------------------
    # Play Game view: a deliberately small, self-contained 2D prototype.
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_brick_wall(surface, rect) -> None:
        pygame.draw.rect(surface, (92, 85, 76), rect)
        pygame.draw.rect(surface, (151, 133, 111), rect, width=3)
        brick_h = 16
        row = 0
        for y in range(rect.y + 2, rect.bottom, brick_h):
            pygame.draw.line(surface, (54, 48, 42), (rect.x, y), (rect.right, y), 2)
            offset = 0 if row % 2 == 0 else 16
            for x in range(rect.x + offset, rect.right, 32):
                pygame.draw.line(surface, (54, 48, 42), (x, y), (x, min(rect.bottom, y + brick_h)), 2)
            row += 1

    @staticmethod
    def _draw_wood_floor(surface) -> None:
        palette = [(107, 70, 42), (118, 79, 48), (128, 87, 52), (113, 74, 44)]
        for row, y in enumerate(range(48, GAME_HEIGHT - 48, 32)):
            for col, x in enumerate(range(48, GAME_WIDTH - 48, 32)):
                color = palette[(row * 3 + col * 5 + (row % 2)) % len(palette)]
                pygame.draw.rect(surface, color, (x, y, 32, 32))
                pygame.draw.line(surface, (78, 48, 28), (x, y + 1), (x + 31, y + 1), 2)
                pygame.draw.line(surface, (78, 48, 28), (x + 1, y + 31), (x + 31, y + 31), 2)
                if (row + col) % 3 == 0:
                    pygame.draw.line(surface, (145, 101, 61), (x + 5, y + 9), (x + 24, y + 9), 2)
                if (row * 7 + col) % 5 == 0:
                    pygame.draw.rect(surface, (65, 41, 25), (x + 7, y + 22, 3, 2))

    @staticmethod
    def _draw_shelf(surface, x: int, y: int, width: int) -> None:
        pygame.draw.rect(surface, (47, 28, 18), (x, y + 5, width, 35))
        pygame.draw.rect(surface, (107, 64, 35), (x, y, width, 9))
        pygame.draw.rect(surface, (164, 111, 64), (x, y, width, 4))
        pygame.draw.rect(surface, (67, 38, 24), (x + 5, y + 10, width - 10, 24))
        pygame.draw.rect(surface, (120, 75, 42), (x + 2, y + 32, width - 4, 7))
        for px in range(x + 14, x + width - 8, 29):
            pygame.draw.rect(surface, (73, 42, 27), (px, y + 9, 3, 24))

    @staticmethod
    def _draw_counter(surface) -> None:
        # The vendor's lower body is partly hidden behind this foreground counter.
        pygame.draw.rect(surface, (64, 37, 23), (267, 173, 310, 69))
        pygame.draw.rect(surface, (119, 68, 37), (259, 167, 326, 26))
        pygame.draw.rect(surface, (173, 111, 56), (259, 167, 326, 6))
        pygame.draw.rect(surface, (82, 47, 29), (271, 194, 302, 42))
        for x in (288, 365, 442, 519):
            pygame.draw.rect(surface, (148, 89, 44), (x, 201, 42, 28))
            pygame.draw.rect(surface, (61, 37, 24), (x + 5, 206, 32, 18))
        pygame.draw.rect(surface, (51, 31, 21), (267, 236, 310, 8))

    @staticmethod
    def _draw_actor(surface, x: float, y: float, *, vendor: bool = False) -> None:
        x, y = int(x), int(y)
        if vendor:
            # Stocky shopkeeper with brown hair and a blue-green apron.
            pygame.draw.rect(surface, (35, 25, 18), (x - 18, y + 6, 36, 36))
            pygame.draw.rect(surface, (61, 101, 85), (x - 15, y + 10, 30, 29))
            pygame.draw.rect(surface, (193, 139, 91), (x - 12, y - 17, 24, 26))
            pygame.draw.rect(surface, (81, 48, 27), (x - 14, y - 22, 28, 10))
            pygame.draw.rect(surface, (104, 61, 30), (x - 17, y - 17, 7, 19))
            pygame.draw.rect(surface, (104, 61, 30), (x + 10, y - 17, 7, 19))
            pygame.draw.rect(surface, (35, 28, 22), (x - 7, y - 7, 4, 4))
            pygame.draw.rect(surface, (35, 28, 22), (x + 4, y - 7, 4, 4))
            pygame.draw.rect(surface, (114, 57, 38), (x - 5, y + 2, 10, 3))
            pygame.draw.rect(surface, (209, 177, 126), (x - 14, y + 29, 28, 4))
        else:
            # Player: short cloak, face, dark boots and a contrasting belt.
            pygame.draw.rect(surface, (30, 23, 21), (x - 12, y + 8, 9, 10))
            pygame.draw.rect(surface, (30, 23, 21), (x + 3, y + 8, 9, 10))
            pygame.draw.rect(surface, (48, 59, 112), (x - 14, y - 2, 28, 20))
            pygame.draw.rect(surface, (87, 102, 170), (x - 10, y + 1, 20, 12))
            pygame.draw.rect(surface, (186, 133, 88), (x - 9, y - 17, 18, 17))
            pygame.draw.rect(surface, (75, 43, 25), (x - 10, y - 21, 20, 7))
            pygame.draw.rect(surface, (75, 43, 25), (x - 12, y - 16, 5, 12))
            pygame.draw.rect(surface, (32, 25, 19), (x - 5, y - 10, 3, 3))
            pygame.draw.rect(surface, (32, 25, 19), (x + 3, y - 10, 3, 3))
            pygame.draw.rect(surface, (188, 153, 68), (x - 11, y + 12, 22, 4))

    @staticmethod
    def _draw_object_art(surface, obj: GameObject) -> None:
        r = obj.rect()
        x, y, w, h = r.x, r.y, r.width, r.height
        if obj.kind == "bucket":
            pygame.draw.polygon(surface, (75, 76, 78), [(x + 3, y + 4), (x + w - 3, y + 4), (x + w - 7, y + h - 2), (x + 7, y + h - 2)])
            pygame.draw.rect(surface, (177, 181, 177), (x + 2, y + 2, w - 4, 5))
            pygame.draw.rect(surface, (120, 129, 130), (x + 5, y + 9, 4, h - 12))
            pygame.draw.rect(surface, (120, 129, 130), (x + w - 9, y + 9, 4, h - 12))
            pygame.draw.line(surface, (215, 215, 207), (x + 6, y + 1), (x + w - 6, y + 1), 2)
        elif obj.kind in {"potion", "potion_blue"}:
            liquid = (149, 52, 75) if obj.kind == "potion" else (50, 136, 190)
            pygame.draw.rect(surface, (75, 47, 35), (x + 8, y, max(2, w - 16), 5))
            pygame.draw.rect(surface, (193, 205, 193), (x + 6, y + 5, max(5, w - 12), 6))
            pygame.draw.rect(surface, liquid, (x + 3, y + 10, max(5, w - 6), max(5, h - 13)))
            pygame.draw.rect(surface, (187, 209, 204), (x + 3, y + 10, max(5, w - 6), max(5, h - 13)), 2)
            pygame.draw.rect(surface, (226, 238, 225), (x + 7, y + 12, 3, max(3, h - 18)))
        elif obj.kind == "herb":
            pygame.draw.rect(surface, (98, 65, 35), (x + 3, y + h - 9, max(4, w - 6), 8))
            for i, c in enumerate(((80, 153, 61), (110, 184, 70), (48, 125, 59), (167, 194, 63))):
                lx = x + 4 + i * max(3, (w - 10) // 4)
                pygame.draw.polygon(surface, c, [(lx + 3, y + 4 + (i % 2) * 5), (lx + 7, y + 1), (lx + 10, y + 7 + (i % 2) * 4), (lx + 5, y + 10)])
            pygame.draw.line(surface, (62, 99, 44), (x + w // 2, y + 7), (x + w // 2, y + h - 7), 2)
        elif obj.kind == "scroll":
            pygame.draw.rect(surface, (195, 160, 98), (x + 4, y + 3, max(5, w - 8), max(5, h - 5)))
            pygame.draw.rect(surface, (235, 211, 156), (x + 6, y + 5, max(3, w - 12), max(3, h - 9)))
            pygame.draw.rect(surface, (113, 77, 42), (x + 2, y + 1, 5, max(3, h - 2)))
            pygame.draw.rect(surface, (113, 77, 42), (x + w - 7, y + 1, 5, max(3, h - 2)))
            pygame.draw.line(surface, (133, 91, 47), (x + 10, y + 10), (x + w - 10, y + 10), 2)
        elif obj.kind == "gold":
            pygame.draw.ellipse(surface, (71, 43, 23), (x + 1, y + 5, max(3, w - 2), max(3, h - 7)))
            pygame.draw.ellipse(surface, (168, 125, 45), (x + 4, y + 3, max(3, w - 8), max(3, h - 9)))
            pygame.draw.ellipse(surface, (226, 190, 77), (x + 7, y + 5, max(3, w - 14), max(3, h - 13)))
            pygame.draw.rect(surface, (102, 71, 30), (x + 10, y + 1, max(3, w - 20), 4))
        elif obj.kind == "fruit":
            pygame.draw.ellipse(surface, (128, 37, 39), (x + 2, y + 5, w - 4, h - 6))
            pygame.draw.ellipse(surface, (202, 57, 54), (x + 4, y + 3, w - 8, h - 7))
            pygame.draw.ellipse(surface, (247, 128, 86), (x + 7, y + 8, 5, 8))
            pygame.draw.line(surface, (69, 91, 39), (x + w // 2, y + 5), (x + w // 2 + 3, y), 3)
        else:
            pygame.draw.rect(surface, (150, 128, 90), r, border_radius=3)

    def _draw_market_scene(self, surface, game: GameModel) -> None:
        """Paint the single-screen outdoor Market."""
        surface.fill((63, 91, 67))
        # Distant town wall and the open, cobbled market square.
        pygame.draw.rect(surface, (104, 113, 91), (0, 45, GAME_WIDTH, 84))
        pygame.draw.rect(surface, (139, 125, 99), (0, 118, GAME_WIDTH, 20))
        for x in range(0, GAME_WIDTH, 52):
            pygame.draw.rect(surface, (92, 101, 80), (x + 3, 56, 43, 52))
            pygame.draw.line(surface, (155, 145, 116), (x + 4, 58), (x + 44, 58), 3)
        pygame.draw.rect(surface, (139, 124, 94), (0, 138, GAME_WIDTH, GAME_HEIGHT - 138))
        for row, y in enumerate(range(144, GAME_HEIGHT, 38)):
            offset = 0 if row % 2 == 0 else 24
            for x in range(-offset, GAME_WIDTH, 48):
                tile_color = (157, 143, 111) if (row + x // 48) % 3 else (148, 133, 103)
                pygame.draw.rect(surface, tile_color, (x + 2, y + 2, 43, 32), border_radius=3)
                pygame.draw.line(surface, (119, 105, 82), (x + 4, y + 33), (x + 43, y + 33), 2)

        # Alchemy Shop frontage. The clickable door rectangle is aligned to the
        # actual painted door; the player enters by clicking it, not by walking
        # into a stitched-together second room.
        facade = pygame.Rect(469, 91, 342, 157)
        pygame.draw.rect(surface, (178, 157, 119), facade)
        pygame.draw.rect(surface, (102, 78, 57), facade, 5)
        pygame.draw.polygon(surface, (67, 42, 56), [(448, 108), (640, 48), (832, 108)])
        pygame.draw.polygon(surface, (116, 65, 66), [(468, 106), (640, 58), (812, 106)])
        pygame.draw.rect(surface, (55, 34, 28), (596, 149, 88, 99))
        pygame.draw.rect(surface, (122, 76, 44), (604, 155, 72, 91))
        pygame.draw.rect(surface, (180, 126, 70), (612, 161, 56, 85))
        pygame.draw.rect(surface, (69, 42, 29), (620, 170, 40, 76))
        pygame.draw.circle(surface, (222, 190, 97), (650, 205), 4)
        pygame.draw.rect(surface, (47, 28, 31), (514, 104, 252, 35), border_radius=5)
        pygame.draw.rect(surface, (199, 156, 84), (514, 104, 252, 35), 2, border_radius=5)
        shop_sign = self.game_font.render("ALCHEMY SHOP", True, (255, 229, 177))
        surface.blit(shop_sign, shop_sign.get_rect(center=(640, 122)))
        # A small hanging sign reads clearly as the door's target.
        pygame.draw.line(surface, (71, 46, 30), (640, 138), (640, 149), 4)

        # Market stalls and vendors.
        for rect, color in ((pygame.Rect(88, 181, 340, 144), (133, 61, 63)),
                            (pygame.Rect(846, 181, 342, 144), (63, 91, 119))):
            pygame.draw.rect(surface, (81, 54, 38), rect, border_radius=4)
            pygame.draw.rect(surface, (197, 164, 112), (rect.x, rect.y + 45, rect.width, 10))
            canopy = pygame.Rect(rect.x - 4, rect.y, rect.width + 8, 51)
            pygame.draw.rect(surface, color, canopy, border_radius=5)
            pygame.draw.rect(surface, (231, 207, 154), canopy, 2, border_radius=5)
            stripe_w = max(1, canopy.width // 8)
            for i in range(0, canopy.width, stripe_w * 2):
                pygame.draw.rect(surface, (224, 201, 154), (canopy.x + i, canopy.y + 1, stripe_w, canopy.height - 2))
            pygame.draw.rect(surface, (89, 53, 33), (rect.x + 5, rect.y + 77, rect.width - 10, 45))
            pygame.draw.rect(surface, (174, 121, 65), (rect.x - 4, rect.y + 72, rect.width + 8, 12))
            pygame.draw.rect(surface, (219, 172, 96), (rect.x - 4, rect.y + 72, rect.width + 8, 4))

        self._draw_actor(surface, 262, 224, vendor=True)
        self._draw_actor(surface, 1015, 224, vendor=True)
        # Goods are drawn on top of counter surfaces and stay individually clickable.
        for obj in game.live_objects():
            if obj.kind == "door":
                continue
            self._draw_object_art(surface, obj)
            if obj.on_shelf:
                pygame.draw.rect(surface, (49, 35, 27), (int(obj.x) - 1, int(obj.y) + obj.height - 1, obj.width + 2, 3))

        # Street furniture and location marker.
        pygame.draw.rect(surface, (94, 67, 43), (480, 405, 320, 38), border_radius=4)
        pygame.draw.rect(surface, (172, 125, 72), (480, 405, 320, 7), border_radius=3)
        for x in (495, 770):
            pygame.draw.rect(surface, (83, 58, 40), (x, 442, 14, 40))
        pygame.draw.rect(surface, (72, 42, 44), (36, 470, 180, 60), border_radius=4)
        pygame.draw.rect(surface, (194, 156, 96), (36, 470, 180, 60), 2, border_radius=4)
        marker = self.game_small_font.render("BRITRUN MARKET", True, (255, 231, 180))
        surface.blit(marker, marker.get_rect(center=(126, 499)))

    def _draw_shop_scene(self, surface, game: GameModel) -> None:
        """Paint the independent Alchemy Shop interior."""
        surface.fill((71, 47, 32))
        self._draw_wood_floor(surface)
        # Outer stone walls, leaving a bottom opening for the return door.
        for wall in (pygame.Rect(24, 44, GAME_WIDTH - 48, 25),
                     pygame.Rect(24, 44, 24, GAME_HEIGHT - 88),
                     pygame.Rect(GAME_WIDTH - 48, 44, 24, GAME_HEIGHT - 88),
                     pygame.Rect(24, 590, 552, 26),
                     pygame.Rect(704, 590, GAME_WIDTH - 728, 26)):
            self._draw_brick_wall(surface, wall)

        # Rear cabinets and shelves.
        pygame.draw.rect(surface, (47, 28, 18), (88, 76, 340, 91))
        pygame.draw.rect(surface, (130, 83, 49), (82, 72, 352, 12))
        pygame.draw.rect(surface, (176, 126, 72), (82, 72, 352, 4))
        pygame.draw.rect(surface, (47, 28, 18), (842, 76, 326, 91))
        pygame.draw.rect(surface, (130, 83, 49), (836, 72, 338, 12))
        pygame.draw.rect(surface, (176, 126, 72), (836, 72, 338, 4))
        self._draw_shelf(surface, 92, 135, 333)
        self._draw_shelf(surface, 850, 135, 315)

        # Shopkeeper and counter are independent of area navigation.
        self._draw_actor(surface, 640, 231, vendor=True)
        # Counter and collision geometry share the same footprint.
        pygame.draw.rect(surface, (64, 37, 23), (455, 276, 370, 58))
        pygame.draw.rect(surface, (119, 68, 37), (447, 268, 386, 28))
        pygame.draw.rect(surface, (173, 111, 56), (447, 268, 386, 6))
        pygame.draw.rect(surface, (82, 47, 29), (459, 296, 362, 31))
        for counter_x in (475, 565, 655, 745):
            pygame.draw.rect(surface, (148, 89, 44), (counter_x, 302, 48, 22))
            pygame.draw.rect(surface, (61, 37, 24), (counter_x + 5, 306, 38, 14))
        # Extra counter display on the right gives the free trial a visible home.
        pygame.draw.rect(surface, (68, 39, 25), (820, 224, 250, 37))
        pygame.draw.rect(surface, (160, 101, 53), (814, 218, 262, 13))
        pygame.draw.rect(surface, (206, 147, 78), (814, 218, 262, 4))

        # Back door is aligned to the connection record, and is the only route
        # back to the Market in this first playable slice.
        pygame.draw.rect(surface, (54, 31, 25), (590, 508, 100, 75))
        pygame.draw.rect(surface, (133, 79, 44), (598, 512, 84, 71))
        pygame.draw.rect(surface, (194, 135, 72), (606, 518, 68, 63))
        pygame.draw.rect(surface, (72, 42, 27), (614, 524, 52, 57))
        pygame.draw.circle(surface, (224, 191, 101), (655, 554), 4)
        label = self.game_small_font.render("MARKET", True, (255, 221, 160))
        surface.blit(label, label.get_rect(center=(640, 494)))

        for obj in game.live_objects():
            if obj.kind == "door":
                continue
            self._draw_object_art(surface, obj)
            if obj.on_shelf:
                pygame.draw.rect(surface, (33, 24, 18), (int(obj.x) - 1, int(obj.y) + obj.height - 1, obj.width + 2, 3))

    def _draw_game_scene(self, surface, game: GameModel) -> None:
        def game_text(value, font, color, x, y, max_width=None):
            rendered = font.render(str(value), True, color)
            if max_width is not None and rendered.get_width() > max_width:
                text_value = str(value)
                suffix = "…"
                while text_value and font.size(text_value + suffix)[0] > max_width:
                    text_value = text_value[:-1]
                rendered = font.render(text_value + suffix, True, color)
            surface.blit(rendered, (x, y))
            return rendered.get_rect(topleft=(x, y))

        if game.current_area_id == AREA_MARKET:
            self._draw_market_scene(surface, game)
        else:
            self._draw_shop_scene(surface, game)

        # Consistent world bar across every area.
        pygame.draw.rect(surface, (20, 18, 22), (0, 0, GAME_WIDTH, 44))
        pygame.draw.line(surface, (187, 145, 83), (0, 43), (GAME_WIDTH, 43), 2)
        area_name = game.current_area.display_name.upper()
        game_text(area_name, self.game_font, (255, 224, 168), 18, 8, max_width=410)
        if game.current_area_id == AREA_MARKET:
            instruction = "WASD/ARROWS MOVE  |  CLICK SHOP DOOR TO ENTER  |  CLICK ITEMS TWICE TO TAKE"
        else:
            instruction = "WASD/ARROWS MOVE  |  CLICK MARKET DOOR TO LEAVE  |  BUCKET TRICK IS OPTIONAL"
        game_text(instruction, self.game_small_font, (236, 232, 221), 350, 13, max_width=700)
        game_text("CTRL+S / F12: SCREENSHOT", self.game_small_font, (213, 197, 167), 836, 583, max_width=235)

        inventory_button = game.inventory_button_rect()
        pygame.draw.rect(surface, (47, 37, 49), inventory_button, border_radius=7)
        pygame.draw.rect(surface, (199, 160, 96), inventory_button, 2, border_radius=7)
        inventory_label = f"INVENTORY ({len(game.inventory)})"
        inv_label_surf = self.game_small_font.render(inventory_label, True, (255, 238, 199))
        surface.blit(inv_label_surf, inv_label_surf.get_rect(center=inventory_button.center))

        # The player is the last world actor layer so movement remains readable.
        self._draw_actor(surface, game.player_x, game.player_y, vendor=False)
        if game.bucket_carried:
            bucket = game.object_by_id("shop_bucket")
            if bucket:
                carried = GameObject("carried_bucket", "Bucket", "bucket", game.current_area_id,
                                     game.player_x + 10, game.player_y - 31,
                                     bucket.width, bucket.height, False, False)
                self._draw_object_art(surface, carried)

        # Selection outline and actionable hover label: red means watched/steal;
        # green means permitted/safe. Non-takeable doors use a neutral blue label.
        if game.selected_object_id:
            selected = game.object_by_id(game.selected_object_id)
            if selected and selected.area_id == game.current_area_id and not selected.in_inventory:
                pygame.draw.rect(surface, (255, 221, 116), selected.rect().inflate(8, 8), 2, border_radius=4)
        screen_pointer = pygame.mouse.get_pos()
        point = self.screen_to_game(screen_pointer) if getattr(self, "game_blit_rect", None) else None
        hover = game.hit_test(point) if point is not None else None
        if hover is not None and not (game.inventory_open and game.inventory_panel_rect().collidepoint(point)):
            if hover.kind == "door":
                tip = "ENTER ALCHEMY SHOP" if game.current_area_id == AREA_MARKET else "RETURN TO MARKET"
                tip_color = (170, 215, 255)
            elif hover.kind in {"path", "portal"}:
                tip, tip_color = hover.name.upper(), (170, 215, 255)
            elif hover.kind == "bucket":
                tip, tip_color = "BUCKET — PICK UP", (156, 255, 180)
            elif hover.takeable:
                watched = game.is_vendor_watching(hover)
                action = "STEAL" if watched and hover.stealable else ("TAKE" if hover.stealable else "TAKE — PERMITTED")
                tip = f"{hover.name}  |  {action}"
                tip_color = (255, 105, 105) if watched and hover.stealable else (145, 255, 169)
            else:
                tip, tip_color = hover.name, (235, 225, 196)
            label_surface = self.game_small_font.render(tip, True, tip_color)
            tip_x = min(GAME_WIDTH - label_surface.get_width() - 8, max(8, point[0] + 14))
            tip_y = min(GAME_HEIGHT - 28, max(50, point[1] + 10))
            label_rect = pygame.Rect(tip_x - 5, tip_y - 3, label_surface.get_width() + 10, label_surface.get_height() + 6)
            pygame.draw.rect(surface, (17, 14, 15), label_rect, border_radius=4)
            pygame.draw.rect(surface, tip_color, label_rect, 1, border_radius=4)
            surface.blit(label_surface, (tip_x, tip_y))

        # Inventory is a small in-game overlay: select an item, then drop it here.
        if game.inventory_open:
            panel = game.inventory_panel_rect()
            pygame.draw.rect(surface, (22, 18, 23), panel, border_radius=8)
            pygame.draw.rect(surface, (198, 157, 94), panel, 2, border_radius=8)
            game_text("INVENTORY", self.game_font, (255, 226, 171), panel.x + 18, panel.y + 11)
            close_rect = game.inventory_close_rect()
            pygame.draw.rect(surface, (77, 52, 45), close_rect, border_radius=5)
            pygame.draw.rect(surface, (196, 157, 94), close_rect, 1, border_radius=5)
            close_surf = self.game_small_font.render("X", True, (255, 239, 207))
            surface.blit(close_surf, close_surf.get_rect(center=close_rect.center))
            if not game.inventory:
                game_text("Your inventory is empty.", self.game_small_font, (220, 214, 198), panel.x + 18, panel.y + 66)
            for index, object_id in enumerate(game.inventory[:12]):
                obj = game.object_by_id(object_id)
                if obj is None:
                    continue
                row = game.inventory_row_rect(index)
                selected = game.inventory_selected_id == object_id
                pygame.draw.rect(surface, (66, 77, 59) if selected else (41, 35, 38), row, border_radius=4)
                pygame.draw.rect(surface, (166, 220, 150) if selected else (107, 91, 73), row, 1, border_radius=4)
                game_text(obj.name, self.game_small_font, (239, 235, 221), row.x + 10, row.y + 3, max_width=row.width - 20)
            drop_rect = game.inventory_drop_rect()
            pygame.draw.rect(surface, (61, 89, 57), drop_rect, border_radius=6)
            pygame.draw.rect(surface, (156, 211, 133), drop_rect, 2, border_radius=6)
            drop_surf = self.game_small_font.render("DROP ITEM", True, (237, 255, 225))
            surface.blit(drop_surf, drop_surf.get_rect(center=drop_rect.center))
            game_text("I = close/open", self.game_small_font, (185, 177, 164), panel.x + 176, panel.y + 431,
                      max_width=142)

        prompt = "Click the shop door to enter. Hover goods to see whether taking them is safe."
        if game.current_area_id == AREA_ALCHEMY_SHOP:
            prompt = "Click the Market door to leave. Select a good, then click again to take it."
        if game.bucket_on_head and game.current_area_id == AREA_ALCHEMY_SHOP:
            prompt = "BUCKET ON HEAD: watched shop items are safe to take."
        elif game.bucket_carried:
            prompt = "BUCKET CARRIED: walk close to the shopkeeper and click their head."
        pygame.draw.rect(surface, (18, 16, 17), (16, 574, 1248, 31), border_radius=5)
        pygame.draw.rect(surface, (174, 131, 74), (16, 574, 1248, 31), 1, border_radius=5)
        game_text(prompt, self.game_small_font, (247, 240, 222), 27, 581, max_width=788)

    def _draw_game(self) -> None:
        game = self.machine.game
        if game is None:
            self._draw_text("Game state unavailable.", self.font, self.TEXT, 42, 130)
            return
        view = self.layout.game_view_rect
        scale = min(view.width / GAME_WIDTH, view.height / GAME_HEIGHT)
        draw_w = max(1, int(GAME_WIDTH * scale))
        draw_h = max(1, int(GAME_HEIGHT * scale))
        draw_x = view.x + (view.width - draw_w) // 2
        draw_y = view.y + (view.height - draw_h) // 2
        self.game_blit_rect = pygame.Rect(draw_x, draw_y, draw_w, draw_h)
        canvas = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self._draw_game_scene(canvas, game)
        scaled = pygame.transform.scale(canvas, (draw_w, draw_h))
        self.screen.blit(scaled, self.game_blit_rect)
        pygame.draw.rect(self.screen, (225, 225, 225), self.game_blit_rect, 2)
        self._draw_button(self.layout.game_back_button, "Back to Tool")
        self._draw_button(self.layout.game_screenshot_button, "Screenshot", primary=True)
        game_status_rect = pygame.Rect(440, self.height - 78, max(220, self.width - 700), 56)
        self._draw_status(game_status_rect)

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
            elapsed = clock.tick(60) / 1000.0
            machine.update(elapsed, ui)
            ui.draw()
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
