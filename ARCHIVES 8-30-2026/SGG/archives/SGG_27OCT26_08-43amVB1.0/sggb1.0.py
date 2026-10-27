#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spiffy's Gift tool — SGGB 1.0.

Major generation B introduces the Luma Draw Engine. The game reads reusable
procedural drawing recipes and area/object definitions from luma_assets.json.
The current world contains BritRun Market and the Alchemy Shop, including its
connected storeroom area, common carry/place/inventory interactions, and the
bucket-on-vendor-head exploit.

The playable slice includes keyboard movement, area-local collision, door
transitions, proximity-gated item interactions, a unified carry/place/inventory
state machine, vendor line-of-sight rules, bucket placement on any vendor, an
external JSON drawing interpreter, inventory/drop controls, and screenshots.

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
VERSION = "B1.0"  # Major letter = feature/UI generation; whole number = release; decimal = minor fix.
VERSION_TAG = f"V{VERSION}"
RUNTIME_FILE = "sggb1.0.py"
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
ASSET_JSON_FILE = "luma_assets.json"
ASSET_JSON_PATH = PROJECT_DIR / ASSET_JSON_FILE

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
        # Preserve the exact procedural artwork/world definition used in this run.
        if ASSET_JSON_PATH.is_file():
            shutil.copy2(ASSET_JSON_PATH, archive_dir / ASSET_JSON_FILE)
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
    append_log(archive, "DRAW ENGINE", f"Asset recipe path: {ASSET_JSON_PATH}; archive snapshot present={(archive_dir / ASSET_JSON_FILE).is_file()}")
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
    DRAW_STUDIO = auto()
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
    menu_item_draw_studio: "pygame.Rect"
    draw_studio_preview_rect: "pygame.Rect"
    draw_studio_prev_button: "pygame.Rect"
    draw_studio_next_button: "pygame.Rect"
    draw_studio_reload_button: "pygame.Rect"
    draw_studio_back_button: "pygame.Rect"


# pygame is imported after archive creation in main(); type names in this module
# are quoted where needed so importing the module itself doesn't initialize SDL.
pygame = None  # Assigned by main() after archive creation.


GAME_WIDTH = 1280
GAME_HEIGHT = 640

AREA_MARKET = "britrun_market"
AREA_ALCHEMY_SHOP = "alchemy_shop"


class AssetDefinitionError(RuntimeError):
    """A readable error in the external Luma Draw Engine recipe file."""


class LumaDrawEngine:
    """Interpret JSON drawing recipes into Pygame surfaces; recipes are external data."""

    SUPPORTED_OPS = {"rect", "line", "polygon", "circle", "ellipse"}

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {}
        self.assets: dict = {}
        self.world: dict = {}
        self.surface_cache: dict[tuple[str, int, int], object] = {}
        self.reload()

    def reload(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as recipe_file:
                data = json.load(recipe_file)
        except Exception as exc:
            raise AssetDefinitionError(
                f"Could not read {self.path.name}: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise AssetDefinitionError("luma_assets.json must contain one JSON object")
        if data.get("format") != "luma-draw-engine":
            raise AssetDefinitionError("Unrecognized recipe format; expected luma-draw-engine")
        assets = data.get("assets")
        world = data.get("world")
        if not isinstance(assets, dict) or not assets:
            raise AssetDefinitionError("The recipes file needs a non-empty 'assets' object")
        if not isinstance(world, dict):
            raise AssetDefinitionError("The recipes file needs a 'world' object")
        for name, asset in assets.items():
            if not isinstance(asset, dict):
                raise AssetDefinitionError(f"Asset '{name}' must be a JSON object")
            try:
                aw, ah = int(asset["width"]), int(asset["height"])
                commands = asset["commands"]
            except Exception as exc:
                raise AssetDefinitionError(f"Asset '{name}' needs width, height and commands") from exc
            if aw <= 0 or ah <= 0 or not isinstance(commands, list):
                raise AssetDefinitionError(f"Asset '{name}' has invalid dimensions or commands")
            for index, command in enumerate(commands):
                if not isinstance(command, dict) or command.get("op") not in self.SUPPORTED_OPS:
                    raise AssetDefinitionError(
                        f"Asset '{name}' command {index + 1} has an unsupported drawing operation"
                    )
        areas = world.get("areas")
        objects = world.get("objects")
        connections = world.get("connections")
        if not isinstance(areas, list) or not areas:
            raise AssetDefinitionError("The world needs at least one area")
        if not isinstance(objects, list) or not isinstance(connections, list):
            raise AssetDefinitionError("The world needs 'objects' and 'connections' lists")
        area_ids = set()
        for area in areas:
            if not isinstance(area, dict) or not area.get("area_id"):
                raise AssetDefinitionError("Every world area needs an area_id")
            area_ids.add(area["area_id"])
            bg = area.get("background_asset")
            if bg not in assets:
                raise AssetDefinitionError(f"Area '{area['area_id']}' references missing background '{bg}'")
        for obj in objects:
            if not isinstance(obj, dict) or not obj.get("object_id"):
                raise AssetDefinitionError("Every world object needs an object_id")
            if obj.get("kind") not in assets:
                raise AssetDefinitionError(
                    f"World object '{obj.get('object_id')}' references missing asset '{obj.get('kind')}'"
                )
            if obj.get("area_id") not in area_ids:
                raise AssetDefinitionError(f"World object '{obj['object_id']}' references an unknown area")
        initial_area = world.get("initial_area")
        if initial_area not in area_ids:
            raise AssetDefinitionError(f"Initial area '{initial_area}' does not exist")
        for connection in connections:
            if connection.get("from_area_id") not in area_ids or connection.get("to_area_id") not in area_ids:
                raise AssetDefinitionError(f"Connection '{connection.get('connection_id')}' references an unknown area")
        render_roles = data.get("render_roles", {})
        if not isinstance(render_roles, dict):
            raise AssetDefinitionError("'render_roles' must be a JSON object")
        for role_name, recipe_name in render_roles.items():
            if recipe_name not in assets:
                raise AssetDefinitionError(f"Render role '{role_name}' references missing asset '{recipe_name}'")
        self.data = data
        self.assets = assets
        self.world = world
        # Cache compiled surfaces; large scene recipes should be interpreted once,
        # not thousands of Python drawing calls every frame.
        self.surface_cache = {}

    def asset_names(self) -> list[str]:
        return list(self.assets.keys())

    def draw_asset(self, surface, name: str, target_rect=None) -> None:
        """Paint one named recipe; compile/cache its rendered surface at each size."""
        asset = self.assets.get(name)
        if asset is None:
            return
        if target_rect is None:
            target_rect = pygame.Rect(0, 0, int(asset["width"]), int(asset["height"]))
        target_w = max(1, int(target_rect.width))
        target_h = max(1, int(target_rect.height))
        cache_key = (name, target_w, target_h)
        rendered = self.surface_cache.get(cache_key)
        if rendered is None:
            rendered = pygame.Surface((target_w, target_h), flags=pygame.SRCALPHA)
            rendered.fill((0, 0, 0, 0))
            self._draw_asset_commands(rendered, asset, pygame.Rect(0, 0, target_w, target_h))
            self.surface_cache[cache_key] = rendered
        surface.blit(rendered, (int(target_rect.x), int(target_rect.y)))

    def _draw_asset_commands(self, surface, asset: dict, target_rect) -> None:
        """Interpret one ordered JSON recipe in a local target coordinate system."""
        base_w, base_h = float(asset["width"]), float(asset["height"])
        sx = target_rect.width / base_w
        sy = target_rect.height / base_h
        stroke_scale = max(0.2, (abs(sx) + abs(sy)) / 2.0)

        def px(value): return round(target_rect.x + float(value) * sx)
        def py(value): return round(target_rect.y + float(value) * sy)
        def mapped_rect(raw):
            x, y, w, h = raw
            left, top, right, bottom = px(x), py(y), px(float(x) + float(w)), py(float(y) + float(h))
            return pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))
        def mapped_points(raw): return [(px(x), py(y)) for x, y in raw]

        for command in asset["commands"]:
            op = command["op"]
            color = tuple(int(max(0, min(255, v))) for v in command.get("color", (255, 255, 255)))
            border = max(0, round(float(command.get("border", 0)) * stroke_scale))
            if op == "rect":
                r = mapped_rect(command["rect"])
                radius = max(0, round(float(command.get("radius", 0)) * stroke_scale))
                pygame.draw.rect(surface, color, r, width=border, border_radius=radius)
            elif op == "line":
                pts = mapped_points(command["points"])
                width = max(1, round(float(command.get("width", 1)) * stroke_scale))
                pygame.draw.line(surface, color, pts[0], pts[1], width)
            elif op == "polygon":
                pts = mapped_points(command["points"])
                pygame.draw.polygon(surface, color, pts, width=border)
            elif op == "circle":
                cx, cy = command["center"]
                radius = max(1, round(float(command["radius"]) * stroke_scale))
                pygame.draw.circle(surface, color, (px(cx), py(cy)), radius, width=border)
            elif op == "ellipse":
                pygame.draw.ellipse(surface, color, mapped_rect(command["rect"]), width=border)


@dataclass(frozen=True)
class AreaDefinition:
    """Area navigation, collision, sight and presentation rules loaded from JSON."""
    area_id: str
    display_name: str
    background_asset: str
    vendors: list[dict]
    solids: list[list[int]]
    sight_blockers: list[list[int]]
    conceal_zones: list[list[int]]


@dataclass(frozen=True)
class AreaConnection:
    """A graph edge from one area to another; trigger type selects activation."""
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
    """A world entity; common handling is independent of its art recipe/kind."""
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
    """Authoritative world state; static presentation and object placements come from JSON."""

    INTERACTION_REACH = 118.0

    def __init__(self, engine: LumaDrawEngine):
        self.engine = engine
        world = engine.world
        self.areas: dict[str, AreaDefinition] = {}
        for record in world["areas"]:
            area_id = record["area_id"]
            self.areas[area_id] = AreaDefinition(
                area_id=area_id,
                display_name=record.get("display_name", area_id),
                background_asset=record["background_asset"],
                vendors=list(record.get("vendors", [])),
                solids=list(record.get("solid_rects", [])),
                sight_blockers=list(record.get("sight_blockers", [])),
                conceal_zones=list(record.get("conceal_zones", [])),
            )
        self.connections = [AreaConnection(
            connection_id=record["connection_id"],
            from_area_id=record["from_area_id"],
            to_area_id=record["to_area_id"],
            trigger=record.get("trigger", "door"),
            source_object_id=record.get("source_object_id"),
            arrival_x=float(record.get("arrival_x", 640)),
            arrival_y=float(record.get("arrival_y", 490)),
            label=record.get("label", "Travel"),
            edge=record.get("edge"),
        ) for record in world["connections"]]
        self.objects = [GameObject(
            object_id=record["object_id"],
            name=record.get("name", record["object_id"]),
            kind=record["kind"],
            area_id=record["area_id"],
            x=float(record.get("x", 100)),
            y=float(record.get("y", 100)),
            width=int(record.get("width", 24)),
            height=int(record.get("height", 24)),
            takeable=bool(record.get("takeable", True)),
            stealable=bool(record.get("stealable", True)),
            on_shelf=bool(record.get("on_shelf", False)),
        ) for record in world["objects"]]
        self.current_area_id = world["initial_area"]
        start = world.get("player_start", {"x": 640, "y": 490})
        self.player_x = float(start.get("x", 640))
        self.player_y = float(start.get("y", 490))
        player_spec = world.get("player", {})
        self.player_width = int(player_spec.get("collision_width", 26))
        self.player_height = int(player_spec.get("collision_height", 36))
        self.inventory: list[str] = []
        self.inventory_open = False
        self.inventory_selected_id: Optional[str] = None
        self.carried_object_id: Optional[str] = None
        self.bucket_on_head_vendor_id: Optional[str] = None
        self.selected_object_id: Optional[str] = None

    @property
    def current_area(self) -> AreaDefinition:
        return self.areas[self.current_area_id]

    @property
    def bucket_carried(self) -> bool:
        obj = self.object_by_id(self.carried_object_id)
        return obj is not None and obj.kind == "bucket"

    @property
    def bucket_on_head(self) -> bool:
        return self.bucket_on_head_vendor_id is not None

    @property
    def bucket_on_head_in_current_area(self) -> bool:
        return any(v.get("vendor_id") == self.bucket_on_head_vendor_id for v in self.current_area.vendors)

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
            if obj.object_id == self.carried_object_id:
                continue
            if obj.kind == "bucket" and self.bucket_on_head_vendor_id is not None:
                continue
            result.append(obj)
        return result

    def hit_test(self, point: tuple[int, int]) -> Optional[GameObject]:
        for obj in reversed(self.live_objects()):
            if obj.rect().collidepoint(point) and (obj.kind in {"door", "path", "portal"} or obj.takeable):
                return obj
        return None

    def vendor_by_id(self, vendor_id: Optional[str]) -> Optional[dict]:
        if vendor_id is None:
            return None
        for area in self.areas.values():
            for vendor in area.vendors:
                if vendor.get("vendor_id") == vendor_id:
                    return vendor
        return None

    def vendor_position(self, vendor_id: Optional[str] = None) -> tuple[float, float]:
        if vendor_id:
            vendor = self.vendor_by_id(vendor_id)
            if vendor:
                return float(vendor["x"]), float(vendor["y"])
        if self.current_area.vendors:
            vendor = self.current_area.vendors[0]
            return float(vendor["x"]), float(vendor["y"])
        return (640.0, 230.0)

    def vendor_rect(self, vendor: dict):
        width, height = int(vendor.get("width", 56)), int(vendor.get("height", 77))
        return pygame.Rect(round(vendor["x"] - width / 2), round(vendor["y"] - height / 2), width, height)

    def vendor_head_rect(self, vendor: dict):
        x, y = float(vendor["x"]), float(vendor["y"])
        width, height = int(vendor.get("width", 56)), int(vendor.get("height", 77))
        return pygame.Rect(round(x - width * 0.31), round(y - height * 0.46), round(width * 0.62), round(height * 0.36))

    def vendor_at(self, point: tuple[int, int]) -> Optional[tuple[dict, str]]:
        for vendor in reversed(self.current_area.vendors):
            if self.vendor_head_rect(vendor).collidepoint(point):
                return vendor, "head"
            if self.vendor_rect(vendor).collidepoint(point):
                return vendor, "body"
        return None

    def player_rect_at(self, x: float, y: float):
        return pygame.Rect(round(x - self.player_width / 2), round(y - self.player_height / 2),
                           self.player_width, self.player_height)

    def held_object_rect(self, obj: Optional[GameObject] = None):
        obj = obj or self.object_by_id(self.carried_object_id)
        if obj is None:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(round(self.player_x + 9 - obj.width / 2),
                           round(self.player_y - self.player_height / 2 - obj.height + 4),
                           obj.width, obj.height)

    def sync_carried_position(self) -> None:
        obj = self.object_by_id(self.carried_object_id)
        if obj is None:
            return
        r = self.held_object_rect(obj)
        obj.area_id = self.current_area_id
        obj.x, obj.y = float(r.x), float(r.y)

    def has_edge_connection(self, edge: str) -> bool:
        return any(c.from_area_id == self.current_area_id and c.trigger == "edge" and c.edge == edge
                   for c in self.connections)

    def solid_rects(self):
        return [pygame.Rect(*map(int, record)) for record in self.current_area.solids]

    def can_move_to(self, x: float, y: float) -> bool:
        low_x = 20 if self.has_edge_connection("left") else 52
        high_x = GAME_WIDTH - 20 if self.has_edge_connection("right") else GAME_WIDTH - 52
        low_y = 30 if self.has_edge_connection("top") else 72
        high_y = GAME_HEIGHT - 24 if self.has_edge_connection("bottom") else GAME_HEIGHT - 62
        if not (low_x <= x <= high_x and low_y <= y <= high_y):
            return False
        player_rect = self.player_rect_at(x, y)
        return not any(player_rect.colliderect(rect) for rect in self.solid_rects())

    def close_to(self, x: float, y: float, reach: Optional[float] = None) -> bool:
        return math.hypot(self.player_x - x, self.player_y - y) <= (reach or self.INTERACTION_REACH)

    def close_to_object(self, obj: GameObject) -> bool:
        return self.close_to(obj.x + obj.width / 2, obj.y + obj.height / 2)

    def _in_conceal_zone(self, x: float, y: float) -> bool:
        for raw in self.current_area.conceal_zones:
            r = pygame.Rect(*map(int, raw))
            if r.collidepoint(round(x), round(y)):
                return True
        return False

    def _line_is_blocked(self, start: tuple[float, float], end: tuple[float, float], target_rect=None) -> bool:
        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        steps = max(2, int(distance / 8))
        blockers = [pygame.Rect(*map(int, raw)) for raw in self.current_area.sight_blockers]
        # A shelf/counter may support or visually contain the item being examined.
        # That target's own supporting surface must not occlude its line of sight.
        if target_rect is not None:
            blockers = [blocker for blocker in blockers if not blocker.colliderect(target_rect)]
        for i in range(2, steps - 1):
            t = i / steps
            x = round(start[0] + (end[0] - start[0]) * t)
            y = round(start[1] + (end[1] - start[1]) * t)
            if any(blocker.collidepoint(x, y) for blocker in blockers):
                return True
        return False

    def is_vendor_watching(self, obj: GameObject) -> bool:
        if not obj.stealable or obj.area_id != self.current_area_id:
            return False
        ox, oy = obj.x + obj.width / 2, obj.y + obj.height / 2
        if self._in_conceal_zone(ox, oy):
            return False
        for vendor in self.current_area.vendors:
            vendor_id = vendor.get("vendor_id")
            if vendor_id == self.bucket_on_head_vendor_id:
                continue
            vx, vy = float(vendor["x"]), float(vendor["y"])
            radius = float(vendor.get("sight_radius", 330))
            if math.hypot(ox - vx, oy - vy) <= radius and not self._line_is_blocked((vx, vy), (ox, oy), obj.rect()):
                return True
        return False

    def place_object_at(self, obj: GameObject, x: float, y: float, *, on_shelf: bool = False) -> None:
        obj.x = float(max(48, min(GAME_WIDTH - 48 - obj.width, x - obj.width / 2)))
        obj.y = float(max(72, min(GAME_HEIGHT - 58 - obj.height, y - obj.height / 2)))
        obj.area_id = self.current_area_id
        obj.in_inventory = False
        obj.on_shelf = on_shelf
        obj.moved = True
        self.selected_object_id = obj.object_id

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
        connection = self.connection_for(trigger, source_object_id, edge)
        if connection is None:
            return None
        self.current_area_id = connection.to_area_id
        self.player_x = connection.arrival_x
        self.player_y = connection.arrival_y
        self.selected_object_id = None
        self.inventory_open = False
        self.sync_carried_position()
        return connection

    def inventory_button_rect(self): return pygame.Rect(1080, 6, 180, 32)
    def inventory_panel_rect(self): return pygame.Rect(930, 47, 330, 474)
    def inventory_close_rect(self): return pygame.Rect(1214, 54, 34, 30)
    def inventory_drop_rect(self): return pygame.Rect(951, 462, 135, 38)
    def inventory_row_rect(self, index: int): return pygame.Rect(950, 92 + index * 29, 290, 25)


def clipboard_get_text() -> str:
    """Read Unicode text from the system clipboard (Windows first, Tk fallback)."""
    if os.name == "nt":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype = ctypes.c_int
            user32.GetClipboardData.argtypes = [ctypes.c_uint]
            user32.GetClipboardData.restype = ctypes.c_void_p
            user32.CloseClipboard.restype = ctypes.c_int
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_int
            if user32.OpenClipboard(None):
                try:
                    handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
                    if handle:
                        pointer = kernel32.GlobalLock(handle)
                        if pointer:
                            try:
                                return ctypes.wstring_at(pointer)
                            finally:
                                kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception:
        return ""


def clipboard_set_text(value: str) -> bool:
    """Write Unicode text to the system clipboard (Windows first, Tk fallback)."""
    if os.name == "nt":
        handle = None
        opened = False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype = ctypes.c_int
            user32.EmptyClipboard.restype = ctypes.c_int
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p
            user32.CloseClipboard.restype = ctypes.c_int
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_int
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            kernel32.GlobalFree.restype = ctypes.c_void_p
            raw = value.encode("utf-16-le", errors="replace") + b"\x00\x00"
            handle = kernel32.GlobalAlloc(0x0002, len(raw))  # GMEM_MOVEABLE
            if not handle:
                return False
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                handle = None
                return False
            try:
                ctypes.memmove(pointer, raw, len(raw))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.OpenClipboard(None):
                kernel32.GlobalFree(handle)
                handle = None
                return False
            opened = True
            user32.EmptyClipboard()
            if user32.SetClipboardData(13, handle):
                handle = None  # Windows owns the memory now.
                return True
        except Exception:
            pass
        finally:
            try:
                if opened:
                    user32.CloseClipboard()
            except Exception:
                pass
            try:
                if handle:
                    kernel32.GlobalFree(handle)
            except Exception:
                pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(value)
            root.update()
            return True
        finally:
            root.destroy()
    except Exception:
        return False


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
        self.draw_studio_index = 0
        self.draw_engine: Optional[LumaDrawEngine] = None
        self.draw_engine_error: Optional[str] = None
        try:
            self.draw_engine = LumaDrawEngine(ASSET_JSON_PATH)
        except Exception as exc:
            self.draw_engine_error = str(exc)
            self.status = f"DRAW ENGINE ERROR: {exc}"
            self.status_error = True
        self._log("STATE", "BOOT -> MAIN")
        self._log("ACCESSIBILITY", f"High-contrast black/white theme; font size {self.font_size_pt} pt; available sizes {FONT_SIZE_OPTIONS_PT}")
        self._log("CONFIG", f"Loaded main configuration from {CONFIG_PATH}")
        if self.draw_engine:
            self._log("DRAW ENGINE", f"Loaded {ASSET_JSON_FILE}: {len(self.draw_engine.assets)} named recipes")
        elif self.draw_engine_error:
            self._log("DRAW ENGINE ERROR", self.draw_engine_error)
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
        elif self.state is AppState.DRAW_STUDIO:
            self._dispatch_draw_studio(event, ui)
        elif self.state is AppState.CONFIRM_OVERWRITE:
            self._dispatch_confirm_overwrite(event, ui)
        elif self.state is AppState.PLAY_GAME:
            self._dispatch_game(event, ui)

    def start_game(self) -> None:
        if self.draw_engine is None:
            self._set_status(f"Cannot start the game: {self.draw_engine_error or 'Luma Draw Engine is not loaded.'}", is_error=True)
            return
        if self.game is None:
            self.game = GameModel(self.draw_engine)
            self._log("GAME", "Initialized SGGB1.0 JSON world: BritRun Market <-> Alchemy Shop + storeroom")
        self.menu_open = False
        self.active_field = None
        self.transition(AppState.PLAY_GAME, "Play Game button")
        self._set_status("Welcome to BritRun Market. Walk near items to carry them; click the carried item/player to take it, or click nearby ground to place it.")

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
        game.sync_carried_position()

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
            if event.key == pygame.K_SPACE and game.carried_object_id:
                held = game.object_by_id(game.carried_object_id)
                if held:
                    game.place_object_at(held, game.player_x + 24, game.player_y + 8)
                    game.carried_object_id = None
                    self._set_status(f"Set down {held.name}. Walk near it to carry it again.")
                    self._log("GAME OBJECT", f"Set down carried {held.name} with SPACE")
                return

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

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
                            self._set_status(f"Selected inventory item: {obj.name}. Use Drop Item to place it near you.")
                        return
                return
            game.inventory_open = False
            return

        if game.inventory_button_rect().collidepoint(point):
            game.inventory_open = True
            if game.inventory_selected_id not in game.inventory:
                game.inventory_selected_id = game.inventory[0] if game.inventory else None
            return

        held = game.object_by_id(game.carried_object_id)
        vendor_hit = game.vendor_at(point)
        object_hit = game.hit_test(point)

        # Bucket-on-head is the one intentional object/vendor exception.
        if held is None and vendor_hit and vendor_hit[1] == "head" and game.bucket_on_head_vendor_id == vendor_hit[0].get("vendor_id"):
            vendor = vendor_hit[0]
            vx, vy = float(vendor["x"]), float(vendor["y"])
            if not game.close_to(vx, vy, 135):
                self._set_status("Walk closer to retrieve the bucket from the vendor's head.")
                return
            bucket = next((obj for obj in game.objects if obj.kind == "bucket"), None)
            if bucket:
                bucket.area_id = game.current_area_id
                game.carried_object_id = bucket.object_id
                game.bucket_on_head_vendor_id = None
                game.sync_carried_position()
                self._set_status("You lifted the bucket off the vendor. It is now being carried.")
                self._log("GAME OBJECT", f"Removed bucket from vendor {vendor.get('vendor_id')}")
            return

        # Deliberate bucket/vendor exception is checked before the general carry
        # target so a head click always means the exploit when a bucket is carried.
        if held is not None and held.kind == "bucket" and vendor_hit and vendor_hit[1] == "head":
            vendor, _hit_part = vendor_hit
            vx, vy = float(vendor["x"]), float(vendor["y"])
            if not game.close_to(vx, vy, 135):
                self._set_status("Walk closer to the vendor before placing the bucket on their head.")
                return
            game.bucket_on_head_vendor_id = vendor["vendor_id"]
            held.area_id = game.current_area_id
            held.x = vx - held.width / 2
            held.y = vy - float(vendor.get("height", 77)) * 0.45 - held.height * 0.35
            game.carried_object_id = None
            game.selected_object_id = None
            self._set_status(f"BUCKET EXPLOIT: the {vendor.get('name', 'vendor')} cannot see goods directly.")
            self._log("EXPLOIT", f"Bucket placed on vendor {vendor['vendor_id']}")
            return

        if held is not None:
            held_rect = game.held_object_rect(held).inflate(12, 12)
            player_rect = game.player_rect_at(game.player_x, game.player_y).inflate(16, 16)

            # A click on the carried sprite itself is the explicit inventory action.
            if held_rect.collidepoint(point):
                if held.stealable and game.is_vendor_watching(held):
                    self._set_status(f"STEAL FAILED: a vendor can see you taking {held.name}. Keep carrying it and move behind cover first.", is_error=True)
                    self._log("GAME ACTION", f"Failed inventory take for carried {held.name}; visible to vendor")
                else:
                    held.in_inventory = True
                    if held.object_id not in game.inventory:
                        game.inventory.append(held.object_id)
                    game.inventory_selected_id = held.object_id
                    game.carried_object_id = None
                    game.selected_object_id = None
                    action = "Took" if held.stealable else "Collected"
                    self._set_status(f"{action} {held.name}. Inventory has {len(game.inventory)} item(s).")
                    self._log("GAME INVENTORY", f"{action} {held.name}; area={held.area_id}")
                return

            # A click on a vendor is a placement target, not a player click.
            # Only bucket + vendor head is special; that pair was handled above.
            if vendor_hit:
                vendor, _hit_part = vendor_hit
                vx, vy = float(vendor["x"]), float(vendor["y"])
                if not game.close_to(vx, vy, 135):
                    self._set_status("Walk closer to the vendor before placing the carried object.")
                    return
                drop_x = vx + int(vendor.get("width", 56)) / 2 + held.width / 2 + 8
                drop_y = vy + int(vendor.get("height", 77)) / 2 - held.height / 2
                game.place_object_at(held, drop_x, drop_y)
                game.carried_object_id = None
                self._set_status(f"Placed {held.name} beside {vendor.get('name', 'the vendor')}.")
                self._log("GAME OBJECT", f"Placed carried {held.name} by vendor {vendor['vendor_id']}")
                return

            # Clicking a world object places the carried item beside that target.
            # A door is not activated while carrying something; prevent teleport/drop surprises.
            if object_hit is not None:
                target_x = object_hit.x + object_hit.width / 2
                target_y = object_hit.y + object_hit.height / 2
                if not game.close_to(target_x, target_y, 135):
                    self._set_status("Move closer to the target before placing the carried object.")
                    return
                drop_x = target_x + object_hit.width / 2 + held.width / 2 + 4
                if drop_x + held.width / 2 > GAME_WIDTH - 48:
                    drop_x = target_x - object_hit.width / 2 - held.width / 2 - 4
                game.place_object_at(held, drop_x, target_y, on_shelf=object_hit.on_shelf)
                game.carried_object_id = None
                self._set_status(f"Placed {held.name} beside {object_hit.name}.")
                self._log("GAME OBJECT", f"Placed carried {held.name} beside {object_hit.name}")
                return

            # Clicking the player (rather than the carried sprite or another target)
            # attempts to transfer the carried item into inventory.
            if player_rect.collidepoint(point):
                if held.stealable and game.is_vendor_watching(held):
                    self._set_status(f"STEAL FAILED: a vendor can see you taking {held.name}. Keep carrying it and move behind cover first.", is_error=True)
                    self._log("GAME ACTION", f"Failed inventory take for carried {held.name}; visible to vendor")
                else:
                    held.in_inventory = True
                    if held.object_id not in game.inventory:
                        game.inventory.append(held.object_id)
                    game.inventory_selected_id = held.object_id
                    game.carried_object_id = None
                    game.selected_object_id = None
                    action = "Took" if held.stealable else "Collected"
                    self._set_status(f"{action} {held.name}. Inventory has {len(game.inventory)} item(s).")
                    self._log("GAME INVENTORY", f"{action} {held.name}; area={held.area_id}")
                return

            # Clicking open ground drops the carried item only within reach.
            if not game.close_to(point[0], point[1], 135):
                self._set_status("Move closer to where you want to place the carried object.")
                return
            game.place_object_at(held, point[0], point[1])
            game.carried_object_id = None
            self._set_status(f"Placed {held.name} on the ground. Walk near it to carry it again.")
            self._log("GAME OBJECT", f"Placed carried {held.name} on ground at {point}")
            return

        # Door activation is a world transition rather than an item pickup.
        if object_hit is not None and object_hit.kind in {"door", "path", "portal"}:
            if not game.close_to_object(object_hit):
                self._set_status(f"Walk closer to {object_hit.name} to use it.")
                return
            trigger = "door" if object_hit.kind == "door" else object_hit.kind
            connection = game.activate_connection(trigger, source_object_id=object_hit.object_id)
            if connection:
                self._log("AREA TRANSITION", f"{connection.from_area_id} -> {connection.to_area_id} via {trigger} {object_hit.object_id}")
                self._set_status(f"{connection.label}. Now in {game.current_area.display_name}.")
            else:
                self._set_status(f"{object_hit.name} is not connected yet.")
            return

        # A nearby clicked item enters the common carried state, regardless of kind.
        if object_hit is not None and object_hit.takeable:
            if not game.close_to_object(object_hit):
                self._set_status(f"Move closer to {object_hit.name} before picking it up.")
                return
            game.carried_object_id = object_hit.object_id
            object_hit.area_id = game.current_area_id
            game.selected_object_id = object_hit.object_id
            game.sync_carried_position()
            self._set_status(f"Carrying {object_hit.name}. Click the carried item/player to take it, or nearby ground/an object to place it.")
            self._log("GAME OBJECT", f"Picked up {object_hit.name} into carried state")
            return

        if vendor_hit:
            vendor, part = vendor_hit
            self._set_status(f"{vendor.get('name', 'Vendor')}: click a carried bucket on the head for the bucket exploit.")
            return

        game.selected_object_id = None

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
            if self.active_field is not None and (mods & pygame.KMOD_CTRL):
                buffer = self._active_buffer()
                if event.key == pygame.K_c:
                    ok = clipboard_set_text(buffer.text)
                    self._set_status("Copied field text to the system clipboard." if ok else "Could not access the system clipboard.", is_error=not ok)
                    return
                if event.key == pygame.K_x:
                    ok = clipboard_set_text(buffer.text)
                    if ok:
                        buffer.clear()
                        self._set_status("Cut field text to the system clipboard.")
                    else:
                        self._set_status("Could not access the system clipboard; field text was kept.", is_error=True)
                    return
                if event.key == pygame.K_v:
                    pasted = clipboard_get_text()
                    if self.active_field is FieldName.TITLE:
                        pasted = pasted.replace("\n", "").replace("\t", "")
                    if pasted:
                        buffer.insert(pasted)
                        self._set_status("Pasted clipboard text into the field.")
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
            if ui.layout.menu_item_draw_studio.collidepoint(point):
                self.menu_open = False
                self.open_draw_studio()
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

    def open_draw_studio(self) -> None:
        if self.draw_engine is None:
            self._set_status(f"Luma Draw Studio cannot open: {self.draw_engine_error or 'recipe file unavailable'}", is_error=True)
            return
        self.draw_studio_index = max(0, min(self.draw_studio_index, len(self.draw_engine.asset_names()) - 1))
        self.transition(AppState.DRAW_STUDIO, "Menu -> Luma Draw Studio")
        self._set_status(f"Loaded {len(self.draw_engine.assets)} recipes from {ASSET_JSON_FILE}.")

    def _dispatch_draw_studio(self, event, ui: "SGGInterface") -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.transition(AppState.MAIN, "Leave Luma Draw Studio")
                return
            if event.key == pygame.K_LEFT:
                self.draw_studio_index = max(0, self.draw_studio_index - 1)
                return
            if event.key == pygame.K_RIGHT and self.draw_engine:
                self.draw_studio_index = min(len(self.draw_engine.asset_names()) - 1, self.draw_studio_index + 1)
                return
            if (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_r:
                self._reload_draw_recipes()
                return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if ui.layout.draw_studio_prev_button.collidepoint(event.pos):
            self.draw_studio_index = max(0, self.draw_studio_index - 1)
        elif ui.layout.draw_studio_next_button.collidepoint(event.pos) and self.draw_engine:
            self.draw_studio_index = min(len(self.draw_engine.asset_names()) - 1, self.draw_studio_index + 1)
        elif ui.layout.draw_studio_reload_button.collidepoint(event.pos):
            self._reload_draw_recipes()
        elif ui.layout.draw_studio_back_button.collidepoint(event.pos):
            self.transition(AppState.MAIN, "Back from Luma Draw Studio")

    def _reload_draw_recipes(self) -> None:
        try:
            engine = LumaDrawEngine(ASSET_JSON_PATH)
            self.draw_engine = engine
            self.draw_engine_error = None
            self.game = None  # The next Play Game starts from the newly loaded world recipe.
            # Keep the run archive matched to the data actually loaded after edits.
            shutil.copy2(ASSET_JSON_PATH, self.archive.directory / ASSET_JSON_FILE)
            self.draw_studio_index = min(self.draw_studio_index, len(engine.asset_names()) - 1)
            self._set_status(f"Reloaded {len(engine.assets)} recipes from {ASSET_JSON_FILE}; archived the refreshed JSON. Next game uses the refreshed world.")
            self._log("DRAW ENGINE", f"Reloaded and archived {ASSET_JSON_FILE}")
        except Exception as exc:
            self.draw_engine_error = str(exc)
            self._set_status(f"Recipe reload failed; the previous engine remains active: {exc}", is_error=True)
            self._log("DRAW ENGINE ERROR", f"Reload failed: {type(exc).__name__}: {exc}")

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
        menu_item = pygame.Rect(width - 242, 78, 216, 48)
        menu_item_draw_studio = pygame.Rect(width - 242, 132, 216, 48)
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
        studio_preview = pygame.Rect(42, 190, width - 84, max(280, height - 318))
        studio_button_y = height - 82
        studio_prev = pygame.Rect(42, studio_button_y, 150, 60)
        studio_next = pygame.Rect(206, studio_button_y, 150, 60)
        studio_reload = pygame.Rect(370, studio_button_y, 200, 60)
        studio_back = pygame.Rect(width - 230, studio_button_y, 188, 60)
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
            menu_item_draw_studio=menu_item_draw_studio,
            draw_studio_preview_rect=studio_preview,
            draw_studio_prev_button=studio_prev,
            draw_studio_next_button=studio_next,
            draw_studio_reload_button=studio_reload,
            draw_studio_back_button=studio_back,
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
        elif self.machine.state is AppState.DRAW_STUDIO:
            self._draw_draw_studio()
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
        self._draw_text("Ctrl+S = Make Note  ·  Ctrl+C / X / V = copy, cut, paste  ·  Ctrl+A = select all", self.small_font, self.TEXT, 42, hint_one_y)
        self._draw_text("Tab = next field  ·  Font size: click − / + above, or press Ctrl + / Ctrl −", self.small_font, self.TEXT, 42, hint_two_y)

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
        for rect, label in ((self.layout.menu_item_asset_preview, "PNG Asset Preview"),
                            (self.layout.menu_item_draw_studio, "Luma Draw Studio")):
            pygame.draw.rect(self.screen, (0, 0, 0), rect, border_radius=8)
            pygame.draw.rect(self.screen, self.BORDER, rect, width=2, border_radius=8)
            self._draw_text(label, self.button_font, self.TEXT, rect.x + 12, rect.y + 8, max_width=rect.width - 24)

    def _draw_draw_studio(self) -> None:
        self._draw_text("Luma Draw Studio", self.title_font, self.TEXT, 42, 112)
        self._draw_text(f"Procedural art is interpreted from {ASSET_JSON_FILE}; no finished sprite sheet is required.",
                        self.small_font, self.TEXT, 44, 156, max_width=self.width - 90)
        rect = self.layout.draw_studio_preview_rect
        pygame.draw.rect(self.screen, (0, 0, 0), rect, border_radius=9)
        pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=9)
        engine = self.machine.draw_engine
        if engine is None:
            self._draw_text(self.machine.draw_engine_error or "Recipe file unavailable.", self.font, self.TEXT,
                            rect.x + 20, rect.y + 20, max_width=rect.width - 40)
        else:
            names = engine.asset_names()
            if names:
                self.machine.draw_studio_index = max(0, min(self.machine.draw_studio_index, len(names) - 1))
                name = names[self.machine.draw_studio_index]
                spec = engine.assets[name]
                header = f"{name}  ·  recipe {self.machine.draw_studio_index + 1} of {len(names)}  ·  {spec['width']} × {spec['height']}"
                self._draw_text(header, self.button_font, self.TEXT, rect.x + 16, rect.y + 14, max_width=rect.width - 32)
                preview_area = pygame.Rect(rect.x + 18, rect.y + 58, rect.width - 36, rect.height - 76)
                scale = min(preview_area.width / spec['width'], preview_area.height / spec['height'])
                pw, ph = max(1, int(spec['width'] * scale)), max(1, int(spec['height'] * scale))
                # Background recipes can be large; prop recipes are enlarged for inspection.
                preview_target = pygame.Rect(0, 0, pw, ph)
                preview_target.center = preview_area.center
                engine.draw_asset(self.screen, name, preview_target)
                self._draw_text(f"Drawing instructions: {len(spec['commands'])}", self.small_font, self.TEXT,
                                rect.x + 18, rect.bottom - 32)
        self._draw_button(self.layout.draw_studio_prev_button, "Previous")
        self._draw_button(self.layout.draw_studio_next_button, "Next", primary=True)
        self._draw_button(self.layout.draw_studio_reload_button, "Reload JSON")
        self._draw_button(self.layout.draw_studio_back_button, "Back")
        self._draw_status(pygame.Rect(42, self.height - 118, self.width - 84, 28))

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
    # Play Game view: the Luma Draw Engine paints every world asset from JSON.
    # ------------------------------------------------------------------
    def _draw_game_scene(self, surface, game: GameModel) -> None:
        engine = self.machine.draw_engine
        if engine is None:
            surface.fill((30, 0, 0))
            return
        engine.draw_asset(surface, game.current_area.background_asset,
                          pygame.Rect(0, 0, GAME_WIDTH, GAME_HEIGHT))

        # Background is data-driven; vendor, player, bucket-head and shelf-shadow
        # recipe names are also selected by JSON roles. Game code supplies state/placement.
        render_roles = engine.data.get("render_roles", {})
        vendor_recipe = render_roles.get("vendor", "vendor")
        player_recipe = render_roles.get("player", "player")
        bucket_head_recipe = render_roles.get("bucket_on_vendor_head", "bucket_inverted")
        shelf_shadow_recipe = render_roles.get("shelf_shadow", "shelf_shadow")
        for vendor in game.current_area.vendors:
            w, h = int(vendor.get("width", 56)), int(vendor.get("height", 77))
            target = pygame.Rect(round(vendor["x"] - w / 2), round(vendor["y"] - h / 2), w, h)
            engine.draw_asset(surface, vendor_recipe, target)

        for obj in game.live_objects():
            if obj.on_shelf:
                shadow_w = obj.width + 2
                engine.draw_asset(surface, shelf_shadow_recipe,
                                  pygame.Rect(round(obj.x) - 1, round(obj.y) + obj.height - 1, shadow_w, 3))
            engine.draw_asset(surface, obj.kind, obj.rect())

        if game.bucket_on_head_vendor_id:
            vendor = game.vendor_by_id(game.bucket_on_head_vendor_id)
            if vendor and any(v.get("vendor_id") == game.bucket_on_head_vendor_id for v in game.current_area.vendors):
                bucket = game.object_by_id(next((o.object_id for o in game.objects if o.kind == "bucket"), None))
                bw = bucket.width if bucket else 36
                bh = bucket.height if bucket else 25
                target = pygame.Rect(round(vendor["x"] - bw / 2),
                                     round(vendor["y"] - float(vendor.get("height", 77)) * 0.44 - bh * 0.55),
                                     bw, max(18, int(bh * 0.82)))
                engine.draw_asset(surface, bucket_head_recipe, target)

        # Held items use their ordinary asset recipe; the carry state changes
        # placement, not how the object is drawn or what object type it is.
        held = game.object_by_id(game.carried_object_id)
        if held:
            game.sync_carried_position()
            engine.draw_asset(surface, held.kind, held.rect())

        # Player appearance is a recipe as well. The current world state only
        # determines its position and hit box.
        player_spec = engine.world.get("player", {})
        player_draw_w = int(player_spec.get("draw_width", 40))
        player_draw_h = int(player_spec.get("draw_height", 58))
        player_target = pygame.Rect(round(game.player_x - player_draw_w / 2),
                                    round(game.player_y - player_draw_h / 2),
                                    player_draw_w, player_draw_h)
        engine.draw_asset(surface, player_recipe, player_target)

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

        # HUD elements are interface, not in-world artwork, so their typography
        # and panels remain ordinary UI code.
        pygame.draw.rect(surface, (20, 18, 22), (0, 0, GAME_WIDTH, 44))
        pygame.draw.line(surface, (187, 145, 83), (0, 43), (GAME_WIDTH, 43), 2)
        game_text(game.current_area.display_name.upper(), self.game_font, (255, 224, 168), 18, 8, max_width=310)
        instruction = "WASD/ARROWS MOVE  |  CARRY NEARBY ITEMS  |  CLICK CARRIED ITEM/PLAYER TO TAKE"
        game_text(instruction, self.game_small_font, (236, 232, 221), 330, 13, max_width=735)
        game_text("CTRL+S / F12: SCREENSHOT", self.game_small_font, (213, 197, 167), 836, 583, max_width=235)

        inventory_button = game.inventory_button_rect()
        pygame.draw.rect(surface, (47, 37, 49), inventory_button, border_radius=7)
        pygame.draw.rect(surface, (199, 160, 96), inventory_button, 2, border_radius=7)
        inventory_label = f"INVENTORY ({len(game.inventory)})"
        inv_label_surf = self.game_small_font.render(inventory_label, True, (255, 238, 199))
        surface.blit(inv_label_surf, inv_label_surf.get_rect(center=inventory_button.center))

        # Selection outline, carried state, and action label.
        selected = game.object_by_id(game.selected_object_id)
        if selected and selected.area_id == game.current_area_id and not selected.in_inventory:
            pygame.draw.rect(surface, (255, 221, 116), selected.rect().inflate(8, 8), 2, border_radius=4)

        screen_pointer = pygame.mouse.get_pos()
        point = self.screen_to_game(screen_pointer) if getattr(self, "game_blit_rect", None) else None
        hover = game.hit_test(point) if point is not None else None
        vendor_hover = game.vendor_at(point) if point is not None else None
        if held and point is not None and (game.held_object_rect(held).inflate(10, 10).collidepoint(point)
                                           or game.player_rect_at(game.player_x, game.player_y).collidepoint(point)):
            if held.stealable:
                watching = game.is_vendor_watching(held)
                action = "STEAL" if watching else "TAKE"
                tip = f"{held.name.upper()} — CARRIED; CLICK TO {action}"
                tip_color = (255, 105, 105) if watching else (145, 255, 169)
            else:
                tip = f"{held.name.upper()} — CARRIED; CLICK TO COLLECT"
                tip_color = (145, 255, 169)
        elif hover is not None:
            if hover.kind == "door":
                tip = "ENTER ALCHEMY SHOP" if game.current_area_id == AREA_MARKET else "RETURN TO MARKET"
                tip_color = (170, 215, 255)
            elif hover.kind in {"path", "portal"}:
                tip, tip_color = hover.name.upper(), (170, 215, 255)
            elif hover.takeable:
                watching = game.is_vendor_watching(hover)
                action = "STEAL" if watching and hover.stealable else ("TAKE" if hover.stealable else "TAKE — PERMITTED")
                tip = f"{hover.name}  |  {action}"
                tip_color = (255, 105, 105) if watching and hover.stealable else (145, 255, 169)
            else:
                tip, tip_color = hover.name, (235, 225, 196)
            label_surface = self.game_small_font.render(tip, True, tip_color)
            label_x = min(GAME_WIDTH - label_surface.get_width() - 8, max(8, point[0] + 14))
            label_y = min(GAME_HEIGHT - 28, max(50, point[1] + 10))
            label_rect = pygame.Rect(label_x - 5, label_y - 3, label_surface.get_width() + 10, label_surface.get_height() + 6)
            pygame.draw.rect(surface, (17, 14, 15), label_rect, border_radius=4)
            pygame.draw.rect(surface, tip_color, label_rect, 1, border_radius=4)
            surface.blit(label_surface, (label_x, label_y))
        elif vendor_hover:
            vendor, part = vendor_hover
            tip = "BUCKET ON HEAD" if vendor.get("vendor_id") == game.bucket_on_head_vendor_id else vendor.get("name", "VENDOR").upper()
            tip_color = (145, 255, 169) if vendor.get("vendor_id") == game.bucket_on_head_vendor_id else (235, 225, 196)
            label_surface = self.game_small_font.render(tip, True, tip_color)
            label_x = min(GAME_WIDTH - label_surface.get_width() - 8, max(8, point[0] + 14))
            label_y = min(GAME_HEIGHT - 28, max(50, point[1] + 10))
            label_rect = pygame.Rect(label_x - 5, label_y - 3, label_surface.get_width() + 10, label_surface.get_height() + 6)
            pygame.draw.rect(surface, (17, 14, 15), label_rect, border_radius=4)
            pygame.draw.rect(surface, tip_color, label_rect, 1, border_radius=4)
            surface.blit(label_surface, (label_x, label_y))

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
                selected_item = game.inventory_selected_id == object_id
                pygame.draw.rect(surface, (66, 77, 59) if selected_item else (41, 35, 38), row, border_radius=4)
                pygame.draw.rect(surface, (166, 220, 150) if selected_item else (107, 91, 73), row, 1, border_radius=4)
                game_text(obj.name, self.game_small_font, (239, 235, 221), row.x + 10, row.y + 3, max_width=row.width - 20)
            drop_rect = game.inventory_drop_rect()
            pygame.draw.rect(surface, (61, 89, 57), drop_rect, border_radius=6)
            pygame.draw.rect(surface, (156, 211, 133), drop_rect, 2, border_radius=6)
            drop_surf = self.game_small_font.render("DROP ITEM", True, (237, 255, 225))
            surface.blit(drop_surf, drop_surf.get_rect(center=drop_rect.center))
            game_text("I = close/open", self.game_small_font, (185, 177, 164), panel.x + 176, panel.y + 431,
                      max_width=142)

        prompt = "Click a nearby item to carry it. Click the carried item/player to take it, or nearby ground to place it."
        if game.current_area_id == AREA_MARKET:
            prompt += " The market has two vendors."
        else:
            prompt = "Storeroom is through the passage on the right. Goods behind the partition are concealed from the shopkeeper."
        if game.bucket_on_head_in_current_area:
            prompt = "BUCKET ON HEAD: this vendor is distracted; other vendors may still see you."
        elif held and held.kind == "bucket":
            prompt = "CARRYING BUCKET: click any vendor's HEAD nearby to trigger the special bucket exploit; ground clicks drop it."
        elif held:
            prompt = f"CARRYING {held.name.upper()}: click carried item/player to take it, or a nearby target to place it."
        pygame.draw.rect(surface, (18, 16, 17), (16, 574, 1248, 31), border_radius=5)
        pygame.draw.rect(surface, (174, 131, 74), (16, 574, 1248, 31), 1, border_radius=5)
        game_text(prompt, self.game_small_font, (247, 240, 222), 27, 581, max_width=1210)

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
