#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SPIFFY'S GIFT D1.2 — player-first interface and run archive.

One complete Python program, built from the original SGG architecture and C1 mechanics.
No B1.0 or C1.0 Python file is loaded at runtime. The external combined Luma
JSON art/world data is required. Dependency: pygame-ce (tested against 2.5.8 API).
"""

from __future__ import annotations

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



import json
import random
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
VERSION = "D1.2"  # Major letter = feature/UI generation; whole number = release; decimal = minor fix.
VERSION_TAG = f"V{VERSION}"
RUNTIME_FILE = "sggd1.2.py"
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
    "soup_speed_multiplier": 2.0,
    "soup_effect_seconds": 20,
    "hidden_chest_hitbox_scale": 2.0,
    "bubble_duration_seconds": 3.0,
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
    # C1.3 game settings survive launches and coexist with the existing keyboard binds.
    try:
        multiplier = float(result.get("soup_speed_multiplier", 2.0))
    except (TypeError, ValueError):
        multiplier = 2.0
    if not math.isfinite(multiplier): multiplier = 2.0
    result["soup_speed_multiplier"] = round(min(4.0, max(1.0, multiplier)), 1)
    try:
        duration = int(result.get("soup_effect_seconds", 20))
    except (TypeError, ValueError, OverflowError):
        duration = 20
    result["soup_effect_seconds"] = min(90, max(5, duration))
    try:
        chest_scale = float(result.get("hidden_chest_hitbox_scale", 2.0))
    except (TypeError, ValueError, OverflowError):
        chest_scale = 2.0
    if not math.isfinite(chest_scale): chest_scale = 2.0
    result["hidden_chest_hitbox_scale"] = round(min(5.0, max(1.0, chest_scale)), 2)
    try:
        bubble = float(result.get("bubble_duration_seconds", 3.0))
    except (ValueError, TypeError, OverflowError):
        bubble = 3.0
    if not math.isfinite(bubble): bubble = 3.0
    result["bubble_duration_seconds"] = round(min(10.0, max(1.0, bubble)), 1)
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
        shutil.copy2(ASSET_JSON_PATH, archive_dir / ASSET_JSON_FILE)
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


# ---------------------------------------------------------------------------
# Luma Draw Engine and JSON-driven world (consolidated into C1.1).
# ---------------------------------------------------------------------------
ASSET_JSON_FILE = 'luma_assets_d12.json'
ASSET_JSON_PATH = PROJECT_DIR / ASSET_JSON_FILE

class AssetDefinitionError(RuntimeError):
    pass

class LumaDrawEngine:
    SUPPORTED_OPS = {'rect','line','polygon','circle','ellipse'}
    def __init__(self,path:Path):
        self.path=Path(path)
        self.reload()
    def reload(self):
        with self.path.open('r',encoding='utf-8') as f: data=json.load(f)
        if data.get('format')!='luma-draw-engine' or not isinstance(data.get('assets'),dict) or not isinstance(data.get('world'),dict):
            raise AssetDefinitionError('Expected Luma Draw Engine format: assets and world')
        self.data=data;self.world=data['world'];self.assets=data['assets'];self.surface_cache={}
        for area in self.world['areas']:
            if area['background_asset'] not in self.assets:
                raise AssetDefinitionError('Missing background for '+area['area_id'])
        for obj in self.world['objects']:
            if obj['kind'] not in self.assets:
                raise AssetDefinitionError('Missing art recipe for '+obj['object_id']+': '+obj['kind'])
    def draw_asset(self,surface,name,target_rect=None):
        a=self.assets.get(name)
        if a is None:return
        if target_rect is None:target_rect=pygame.Rect(0,0,a['width'],a['height'])
        tw,th=max(1,int(target_rect.width)),max(1,int(target_rect.height))
        key=(name,tw,th)
        render=self.surface_cache.get(key)
        if render is None:
            render=pygame.Surface((tw,th),pygame.SRCALPHA)
            render.fill((0,0,0,0))
            sx,sy=tw/float(a['width']),th/float(a['height'])
            stroke_scale=max(.2,(abs(sx)+abs(sy))/2)
            px=lambda v:round(float(v)*sx)
            py=lambda v:round(float(v)*sy)
            def rect(raw):
                x,y,w,h=raw
                x1,y1,x2,y2=px(x),py(y),px(x+w),py(y+h)
                return pygame.Rect(x1,y1,max(1,x2-x1),max(1,y2-y1))
            for c in a['commands']:
                op=c.get('op')
                col=tuple(int(v) for v in c.get('color',(255,255,255)))
                border=max(0,round(float(c.get('border',0))*stroke_scale))
                if op=='rect':pygame.draw.rect(render,col,rect(c['rect']),width=border,border_radius=max(0,round(c.get('radius',0)*stroke_scale)))
                elif op=='ellipse':pygame.draw.ellipse(render,col,rect(c['rect']),width=border)
                elif op=='polygon':pygame.draw.polygon(render,col,[(px(x),py(y)) for x,y in c['points']],width=border)
                elif op=='line':
                    # A recipe line can be a polyline with two or more points.
                    # Calling pygame.draw.line with unpacked 3+ points caused the
                    # C1.2 startup crash when Karlotta's three-point mouth rendered.
                    points=[(px(x),py(y)) for x,y in c['points']]
                    if len(points)<2:
                        raise AssetDefinitionError(f"Asset {name!r}: line requires at least two points")
                    pygame.draw.lines(render,col,False,points,max(1,round(c.get('width',1)*stroke_scale)))
                elif op=='circle':pygame.draw.circle(render,col,(px(c['center'][0]),py(c['center'][1])),max(1,round(float(c['radius'])*stroke_scale)),width=border)
            self.surface_cache[key]=render
        surface.blit(render,(round(target_rect.x),round(target_rect.y)))

@dataclass(frozen=True)
class AreaDefinition:
    area_id:str
    display_name:str
    background_asset:str
    vendors:list[dict]
    solids:list[list[int]]
    sight_blockers:list[list[int]]
    conceal_zones:list[list[int]]

@dataclass(frozen=True)
class AreaConnection:
    connection_id:str
    from_area_id:str
    to_area_id:str
    trigger:str
    source_object_id:Optional[str]
    arrival_x:float
    arrival_y:float
    label:str
    edge:Optional[str]=None

@dataclass
class GameObject:
    object_id:str
    name:str
    kind:str
    area_id:str
    x:float
    y:float
    width:int
    height:int
    takeable:bool=True
    stealable:bool=True
    in_inventory:bool=False
    moved:bool=False
    on_shelf:bool=False
    def rect(self):return pygame.Rect(round(self.x),round(self.y),self.width,self.height)

class GameModel:
    INTERACTION_REACH=118.0
    def __init__(self,engine:LumaDrawEngine):
        self.engine=engine
        w=engine.world
        self.areas={a['area_id']:AreaDefinition(a['area_id'],a.get('display_name',a['area_id']),a['background_asset'],list(a.get('vendors',[])),list(a.get('solid_rects',[])),list(a.get('sight_blockers',[])),list(a.get('conceal_zones',[]))) for a in w['areas']}
        self.connections=[AreaConnection(c['connection_id'],c['from_area_id'],c['to_area_id'],c.get('trigger','door'),c.get('source_object_id'),float(c.get('arrival_x',640)),float(c.get('arrival_y',490)),c.get('label','Travel'),c.get('edge')) for c in w['connections']]
        self.objects=[GameObject(o['object_id'],o.get('name',o['object_id']),o['kind'],o['area_id'],float(o.get('x',100)),float(o.get('y',100)),int(o.get('width',24)),int(o.get('height',24)),bool(o.get('takeable',True)),bool(o.get('stealable',True)),on_shelf=bool(o.get('on_shelf',False))) for o in w['objects']]
        self.current_area_id=w['initial_area']
        start=w.get('player_start',{})
        self.player_x=float(start.get('x',640));self.player_y=float(start.get('y',490))
        spec=w.get('player',{})
        self.player_width=int(spec.get('collision_width',26));self.player_height=int(spec.get('collision_height',36))
        self.inventory=[];self.inventory_open=False;self.inventory_selected_id=None
        self.carried_object_id=None;self.bucket_on_head_vendor_id=None;self.selected_object_id=None
    @property
    def current_area(self):return self.areas[self.current_area_id]
    @property
    def bucket_carried(self):
        o=self.object_by_id(self.carried_object_id)
        return bool(o and o.kind=='bucket')
    @property
    def bucket_on_head(self):return self.bucket_on_head_vendor_id is not None
    @property
    def bucket_on_head_in_current_area(self):return any(v.get('vendor_id')==self.bucket_on_head_vendor_id for v in self.current_area.vendors)
    def object_by_id(self,oid):return next((o for o in self.objects if o.object_id==oid),None)
    def live_objects(self):
        return [o for o in self.objects if o.area_id==self.current_area_id and not o.in_inventory and o.object_id!=self.carried_object_id and not (o.kind=='bucket' and self.bucket_on_head_in_current_area)]
    def hit_test(self,point):
        return next((o for o in reversed(self.live_objects()) if o.rect().collidepoint(point) and (o.takeable or o.kind in ('door','path','portal'))),None)
    def vendor_by_id(self,vid):return next((v for a in self.areas.values() for v in a.vendors if v.get('vendor_id')==vid),None)
    def vendor_position(self,vid=None):
        v=self.vendor_by_id(vid) if vid else (self.current_area.vendors[0] if self.current_area.vendors else None)
        return (float(v['x']),float(v['y'])) if v else (640.,230.)
    def vendor_rect(self,v):
        w,h=int(v.get('width',56)),int(v.get('height',77))
        return pygame.Rect(round(v['x']-w/2),round(v['y']-h/2),w,h)
    def vendor_head_rect(self,v):
        x,y,w,h=float(v['x']),float(v['y']),int(v.get('width',56)),int(v.get('height',77))
        return pygame.Rect(round(x-w*.31),round(y-h*.46),round(w*.62),round(h*.36))
    def vendor_at(self,point):
        for v in reversed(self.current_area.vendors):
            if self.vendor_head_rect(v).collidepoint(point):return (v,'head')
            if self.vendor_rect(v).collidepoint(point):return (v,'body')
        return None
    def player_rect_at(self,x,y):
        return pygame.Rect(round(x-self.player_width/2),round(y-self.player_height/2),self.player_width,self.player_height)
    def held_object_rect(self,obj=None):
        obj=obj or self.object_by_id(self.carried_object_id)
        if obj is None:return pygame.Rect(0,0,0,0)
        return pygame.Rect(round(self.player_x+9-obj.width/2),round(self.player_y-self.player_height/2-obj.height+4),obj.width,obj.height)
    def sync_carried_position(self):
        obj=self.object_by_id(self.carried_object_id)
        if obj:
            r=self.held_object_rect(obj);obj.area_id=self.current_area_id;obj.x=float(r.x);obj.y=float(r.y)
    def has_edge_connection(self,edge):return any(c.from_area_id==self.current_area_id and c.trigger=='edge' and c.edge==edge for c in self.connections)
    def solid_rects(self):return [pygame.Rect(*map(int,r)) for r in self.current_area.solids]
    def can_move_to(self,x,y):
        lo_x=20 if self.has_edge_connection('left') else 52
        hi_x=GAME_WIDTH-20 if self.has_edge_connection('right') else GAME_WIDTH-52
        lo_y=30 if self.has_edge_connection('top') else 72
        hi_y=GAME_HEIGHT-24 if self.has_edge_connection('bottom') else GAME_HEIGHT-62
        if not (lo_x<=x<=hi_x and lo_y<=y<=hi_y):return False
        return not any(self.player_rect_at(x,y).colliderect(r) for r in self.solid_rects())
    def close_to(self,x,y,reach=None):return math.hypot(self.player_x-x,self.player_y-y)<=(self.INTERACTION_REACH if reach is None else reach)
    def close_to_object(self,obj):return self.close_to(obj.x+obj.width/2,obj.y+obj.height/2)
    def _in_conceal_zone(self,x,y):return any(pygame.Rect(*map(int,r)).collidepoint(round(x),round(y)) for r in self.current_area.conceal_zones)
    def _line_is_blocked(self,start,end,target_rect=None):
        dist=math.dist(start,end);steps=max(2,int(dist/7))
        blockers=[pygame.Rect(*map(int,raw)) for raw in self.current_area.sight_blockers]
        if target_rect is not None:blockers=[block for block in blockers if not block.colliderect(target_rect)]
        for i in range(2,steps-1):
            t=i/steps
            p=(round(start[0]+(end[0]-start[0])*t),round(start[1]+(end[1]-start[1])*t))
            if any(b.collidepoint(p) for b in blockers):return True
        return False
    def is_vendor_watching(self,obj):
        if not obj.stealable or obj.area_id!=self.current_area_id:return False
        x,y=obj.x+obj.width/2,obj.y+obj.height/2
        if self._in_conceal_zone(x,y):return False
        for v in self.current_area.vendors:
            if v.get('vendor_id')==self.bucket_on_head_vendor_id:continue
            vx,vy=float(v['x']),float(v['y'])
            if math.hypot(x-vx,y-vy)<=float(v.get('sight_radius',330)) and not self._line_is_blocked((vx,vy),(x,y),obj.rect()):return True
        return False
    def place_object_at(self,obj,x,y,*,on_shelf=False):
        obj.x=float(max(48,min(GAME_WIDTH-48-obj.width,x-obj.width/2)))
        obj.y=float(max(72,min(GAME_HEIGHT-58-obj.height,y-obj.height/2)))
        obj.area_id=self.current_area_id;obj.in_inventory=False;obj.on_shelf=on_shelf;obj.moved=True
        self.selected_object_id=obj.object_id
    def connection_for(self,trigger,source_object_id=None,edge=None):
        for c in self.connections:
            if c.from_area_id==self.current_area_id and c.trigger==trigger and c.source_object_id==source_object_id and (trigger!='edge' or c.edge==edge):return c
        return None
    def activate_connection(self,trigger,source_object_id=None,edge=None):
        c=self.connection_for(trigger,source_object_id,edge)
        if c is None:return None
        self.current_area_id=c.to_area_id
        self.player_x,self.player_y=c.arrival_x,c.arrival_y
        self.selected_object_id=None;self.inventory_open=False
        self.sync_carried_position()
        return c
    def inventory_button_rect(self):return pygame.Rect(1080,6,180,32)
    def inventory_panel_rect(self):return pygame.Rect(930,47,330,474)
    def inventory_close_rect(self):return pygame.Rect(1214,54,34,30)
    def inventory_drop_rect(self):return pygame.Rect(951,462,135,38)
    def inventory_row_rect(self,index):return pygame.Rect(950,92+index*29,290,25)


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
    machine = D12StateMachine(archive, config, config_warning)
    machine.start_game()  # D1 launches directly into the active world.
    ui = D12Interface(machine)
    clock = pygame.time.Clock()
    pygame.key.start_text_input()
    append_log(archive, "UI", "D1.2 direct-to-game window opened")

    try:
        while machine.state is not AppState.CLOSED:
            for event in pygame.event.get():
                machine.dispatch(event, ui)
            elapsed = clock.tick(60) / 1000.0
            machine.update(elapsed, ui)
            ui.draw()
    except Exception as exc:
        # Record the stack frame as well as the exception text: a one-line
        # TypeError alone hides which UI draw call or art recipe failed.
        import traceback
        append_log(archive, "FATAL ERROR", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
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




class LumaInterface(SGGInterface):
    # Self-contained B-style procedural scene, fed by the existing Luma asset pack.
    def _draw_game_scene(self,surface,g):
        engine=self.machine.draw_engine
        roles=engine.data.get('render_roles',{})
        surface.fill((42,43,43))
        engine.draw_asset(surface,g.current_area.background_asset,pygame.Rect(0,0,GAME_WIDTH,GAME_HEIGHT))
        for v in g.current_area.vendors:
            w,h=int(v.get('width',56)),int(v.get('height',77))
            engine.draw_asset(surface,roles.get('vendor','vendor'),pygame.Rect(round(v['x']-w/2),round(v['y']-h/2),w,h))
            if g.bucket_on_head_vendor_id==v.get('vendor_id'):
                engine.draw_asset(surface,roles.get('bucket_on_vendor_head','bucket_inverted'),pygame.Rect(round(v['x']-31),round(v['y']-44),62,47))
        for obj in g.live_objects():
            if obj.kind=='chest' and obj.area_id=='stables' and obj.x>1100:
                mouse=self.screen_to_game(pygame.mouse.get_pos())
                if mouse is None or g.hit_test(mouse) is not obj:continue
            if obj.on_shelf:
                engine.draw_asset(surface,roles.get('shelf_shadow','shelf_shadow'),pygame.Rect(round(obj.x-5),round(obj.y+obj.height-2),obj.width+10,9))
            engine.draw_asset(surface,obj.kind,obj.rect())
            if obj.object_id==g.selected_object_id:
                pygame.draw.rect(surface,(245,208,137),obj.rect().inflate(6,6),2,border_radius=3)
        player=engine.world.get('player',{})
        pw,ph=int(player.get('draw_width',40)),int(player.get('draw_height',58))
        player_rect=pygame.Rect(round(g.player_x-pw/2),round(g.player_y-ph*.7),pw,ph)
        engine.draw_asset(surface,roles.get('player','player'),player_rect)
        held=g.object_by_id(g.carried_object_id)
        if held:engine.draw_asset(surface,held.kind,g.held_object_rect(held))
        pygame.draw.rect(surface,(20,18,22),(0,0,GAME_WIDTH,44))
        pygame.draw.line(surface,(187,145,83),(0,43),(GAME_WIDTH,43),2)
        button=g.inventory_button_rect()
        pygame.draw.rect(surface,(51,38,50),button,border_radius=7)
        pygame.draw.rect(surface,(210,174,105),button,2,border_radius=7)
        label=self.game_small_font.render(f'INVENTORY ({len(g.inventory)})',True,(255,236,197))
        surface.blit(label,label.get_rect(center=button.center))
        if g.inventory_open:
            panel=g.inventory_panel_rect()
            pygame.draw.rect(surface,(29,26,36),panel,border_radius=7)
            pygame.draw.rect(surface,(206,169,99),panel,2,border_radius=7)
            def txt(s,x,y,color=(243,236,212)):
                surface.blit(self.game_small_font.render(s,True,color),(x,y))
            txt('INVENTORY',950,59)
            pygame.draw.rect(surface,(117,52,49),g.inventory_close_rect(),border_radius=4)
            txt('X',1222,57)
            for index,oid in enumerate(g.inventory[getattr(g, "inventory_scroll", 0):getattr(g, "inventory_scroll", 0)+12]):
                o=g.object_by_id(oid)
                if o is None:continue
                rr=g.inventory_row_rect(index)
                if oid==g.inventory_selected_id:pygame.draw.rect(surface,(74,64,75),rr,border_radius=3)
                status=' [STOLEN]' if oid in g.c1_stolen else ''
                text=o.name+status
                while self.game_small_font.size(text)[0]>rr.width-10 and len(text)>3:text=text[:-2]
                txt(text,rr.x+6,rr.y+3,(247,132,132) if oid in g.c1_stolen else (236,238,215))
            drop=g.inventory_drop_rect()
            pygame.draw.rect(surface,(72,59,46),drop,border_radius=6)
            pygame.draw.rect(surface,(218,174,102),drop,2,border_radius=6)
            txt('DROP ITEM',drop.x+12,drop.y+7)


DEFAULT_KEYS={
    'up':'w','down':'s','left':'a','right':'d',
    'use':'e','inventory':'i','drop':'space','wait':'t','eat':'f',
    'buy':'b','sell':'v','respawn':'r','hints':'?','config':'f3','screenshot':'f12','exit':'escape',
    'quicksave':'f5','quickload':'f9','save_menu':'f6','game_config':'f1',
}
KEY_LABELS={
    'up':'Move up','down':'Move down','left':'Move left','right':'Move right',
    'use':'Use / Take / Talk','inventory':'Inventory','drop':'Drop carried item',
    'wait':'Wait one day','eat':'Eat soup','buy':'Buy potion','sell':'Sell item',
    'respawn':'Respawn after death','hints':'Toggle hint bar','config':'Configure keys','screenshot':'Screenshot',
    'exit':'Menu / Esc',
    'quicksave':'Quicksave','quickload':'Quickload','save_menu':'Save / Load menu',
    'game_config':'Game configuration'
}


def keycode(keyname):
    if keyname=='?':return pygame.K_SLASH
    try:return pygame.key.key_code(str(keyname).lower())
    except (ValueError,AttributeError):return None


def matches(event,name):
    if isinstance(name,str) and '+' in name:return c12_binding_matches(event,name)
    if name=='?' and event.unicode=='?':return True
    k=keycode(name)
    return k is not None and event.key==k


class C11GameModel(GameModel):
    """B1's model extended with world laws, NPCs, quests, money and respawns."""
    def __init__(self,engine):
        super().__init__(engine)
        self.item_meta={o['object_id']:dict(o) for o in engine.world['objects']}
        self.c1_day=1
        self.c1_gold=0
        self.c1_permissions=set()
        self.c1_flags={'heard_kart':False,'lout_warned':False,'quest_started':False,'quest_done':False,
                       'book_read':False,'pineapple_taken':False}
        self.c1_stolen=set()
        self.c1_owned_taken=set()
        self.c1_respawn_due={}
        self.c1_npcs={n['npc_id']:dict(n,alive=True) for n in engine.world.get('npcs',[])}
        self.c1_guard={'area_id':'britrun_market','x':914.0,'y':492.0,'name':'BritRun Guard',
                       'asset':'guard','width':62,'height':90,'alive':True,'facing':(-1.,0.),'sight_radius':365.}
        self.c1_guard_target=None
        self.c1_guard_bucketed=False
        self.c1_guard_bucket_object_id=None
        self.c1_troll_angry=False
        self.c1_soup_stacks=0
        self.c1_soup_seconds=0.0
        self.c1_soup_total=0
        self.c1_dead=None
        self.c1_launch_seconds=0.0
        self.c1_elapsed=0.0
        self.c1_naz_lines_at=0
        self.c1_selected_speech=''
        self.c1_speech_seconds=0.0
        self.c1_hint_visible=True
        self.c1_config_open=False
        self.c1_rebind=None
        self.c1_wait_banner=''
        self.c1_chest_next_day=1
        self.c1_item_counter=0
        self.c1_vault_entered=False
        self.c1_quest_log=[]
        self.c1_vendors_kart={'kart_lotta'}

    def meta(self,obj):
        return self.item_meta.get(obj.object_id,{}) if obj else {}

    def is_permitted(self,obj):
        return obj and (not obj.stealable or
                        (self.meta(obj).get('owner')=='kart_lotta' and 'kart_lotta' in self.c1_permissions))

    def is_unauthorized(self,obj):
        # Once actually stolen, an object remains stolen across drops, travel and restarts of pursuit.
        return bool(obj and (obj.object_id in self.c1_stolen or (obj.stealable and not self.is_permitted(obj))))

    def c1_inventory_add(self,obj):
        if obj.object_id==self.carried_object_id:self.carried_object_id=None
        obj.in_inventory=True
        if obj.object_id not in self.inventory:self.inventory.append(obj.object_id)
        self.inventory_selected_id=obj.object_id
        self.selected_object_id=None

    def c1_make_item(self,name,kind,*,price=0,area=None,stolen=False):
        self.c1_item_counter+=1
        oid=f'c1_generated_{self.c1_item_counter}'
        sizes={'potion':(25,31),'soup':(39,26),'gold':(28,24),'herb':(28,33),'cabbage':(34,31)}
        w,h=sizes.get(kind,(30,30))
        obj=GameObject(oid,name,kind,area or self.current_area_id,
                         self.player_x,self.player_y,w,h,takeable=True,stealable=stolen)
        self.objects.append(obj)
        self.item_meta[oid]={'object_id':oid,'name':name,'kind':kind,'value':price,'stealable':stolen}
        if stolen:self.c1_stolen.add(oid)
        self.c1_inventory_add(obj)
        return obj

    def c1_consume(self,obj):
        if obj.object_id in self.inventory:self.inventory.remove(obj.object_id)
        if self.inventory_selected_id==obj.object_id:self.inventory_selected_id=self.inventory[0] if self.inventory else None
        obj.in_inventory=False
        obj.area_id='__consumed__'
        if self.carried_object_id==obj.object_id:self.carried_object_id=None

    def c1_have(self,predicate):
        for oid in self.inventory:
            o=self.object_by_id(oid)
            if o and predicate(o):return o
        return None

    def c1_nearest(self,x,y,reach=150):
        choices=[(math.hypot(x-o.x-o.width/2,y-o.y-o.height/2),o)
                 for o in self.live_objects()]
        choices.sort(key=lambda x:x[0])
        return choices[0][1] if choices and choices[0][0]<reach else None

    def c1_npc_at(self,point):
        for n in self.c1_npcs.values():
            if not n.get('alive',True) or n['area_id']!=self.current_area_id:continue
            rect=pygame.Rect(int(n['x']-n.get('width',55)/2),int(n['y']-n.get('height',75)/2),
                             n.get('width',55),n.get('height',75))
            if rect.collidepoint(point):return n
        return None

    def c1_nearest_npc(self,maxdist=150):
        options=[(math.hypot(self.player_x-n['x'],self.player_y-n['y']),n)
                 for n in self.c1_npcs.values() if n['area_id']==self.current_area_id and n.get('alive',True)]
        options.sort(key=lambda x:x[0])
        return options[0][1] if options and options[0][0]<maxdist else None

    def c1_say(self,message,duration=4):
        self.c1_selected_speech=message
        self.c1_speech_seconds=duration

    def c1_wait(self):
        self.c1_day+=1
        spawned=[]
        for obj in self.objects:
            meta=self.meta(obj)
            if not meta.get('respawn') or obj.object_id not in self.c1_respawn_due:continue
            if self.c1_day<self.c1_respawn_due[obj.object_id]:continue
            # Spawn an actual new unit, preserving the player's previously taken item.
            oid=obj.object_id
            original=meta
            replacement=GameObject(f'{oid}_day{self.c1_day}',original['name'],original['kind'],original['area_id'],
                float(original['x']),float(original['y']),int(original['width']),int(original['height']),
                takeable=True,stealable=bool(original.get('stealable',False)),on_shelf=bool(original.get('on_shelf',False)))
            self.objects.append(replacement)
            self.item_meta[replacement.object_id]=dict(original,object_id=replacement.object_id)
            spawned.append(replacement.name)
            del self.c1_respawn_due[oid]
        # Every product tagged for respawn is eligible again once its own copy is picked.
        if self.c1_dead:self.c1_dead=None
        self.c1_soup_seconds=0.0
        self.c1_soup_stacks=0
        if self.c1_day>=self.c1_chest_next_day:self.c1_wait_banner='Caravan chest restocked.'
        else:self.c1_wait_banner=''
        return f'Day {self.c1_day}. ' + (f'Restocked {len(spawned)} vegetables. ' if spawned else '')+self.c1_wait_banner

    def c1_mark_respawn(self,obj):
        days=self.meta(obj).get('respawn')
        if days:self.c1_respawn_due[obj.object_id]=self.c1_day+int(days)

    def c1_witnesses(self,obj):
        """Witnessing is independent of the item's persistent ownership."""
        return self.is_vendor_watching(obj)


    def live_objects(self):
        return [o for o in super().live_objects()
                if not (self.c1_guard_bucketed and o.object_id==self.c1_guard_bucket_object_id)]

    def guard_head_rect(self):
        q=self.c1_guard
        if not q or q.get('area_id')!=self.current_area_id:return pygame.Rect(0,0,0,0)
        return pygame.Rect(round(q['x']-19),round(q['y']-43),38,34)

    def guard_sees(self,obj):
        q=self.c1_guard
        if not q or q.get('area_id')!=self.current_area_id or not q.get('alive',True) or self.c1_guard_bucketed:return False
        target=(obj.x+obj.width/2,obj.y+obj.height/2)
        source=(q['x'],q['y']-12)
        dx,dy=target[0]-source[0],target[1]-source[1]
        radius=float(q.get('sight_radius',365))
        distance=math.hypot(dx,dy)
        if distance>radius:return False
        # The standing market guard watches toward Naz; no supernatural 360-degree sight.
        face=q.get('facing',(-1.,0.))
        if distance>60 and (face[0]*dx+face[1]*dy)<-.15*distance:return False
        if self._in_conceal_zone(*target):return False
        return not self._line_is_blocked(source,target,obj.rect())

    def edge_markers(self):
        result=[]
        for c in self.connections:
            if c.from_area_id!=self.current_area_id or c.trigger!='edge':continue
            back=next((b for b in self.connections if b.from_area_id==c.to_area_id and b.to_area_id==c.from_area_id
                       and b.trigger=='edge'),None)
            if c.edge in ('left','right'):
                center=float(back.arrival_y if back else c.arrival_y)
            else:
                center=float(back.arrival_x if back else c.arrival_x)
            result.append((c,center))
        return result

    def connection_for(self,trigger,source_object_id=None,edge=None):
        if trigger=='edge':
            coord=self.player_y if edge in ('left','right') else self.player_x
            candidates=[(abs(coord-pos),c) for c,pos in self.edge_markers() if c.edge==edge]
            if not candidates:return None
            distance,choice=min(candidates,key=lambda pair:pair[0])
            return choice if distance<=80 else None
        return super().connection_for(trigger,source_object_id,edge)

    def collision_penalty_at(self,x,y):
        actor=self.player_rect_at(x,y)
        return sum(max(0,actor.clip(r).width)*max(0,actor.clip(r).height) for r in self.solid_rects())

    def can_move_to(self,x,y):
        # Normal collision prevents entry; a player accidentally embedded in scenery may walk OUT.
        lo_x=20 if self.has_edge_connection('left') else 52
        hi_x=GAME_WIDTH-20 if self.has_edge_connection('right') else GAME_WIDTH-52
        lo_y=30 if self.has_edge_connection('top') else 72
        hi_y=GAME_HEIGHT-24 if self.has_edge_connection('bottom') else GAME_HEIGHT-62
        if not (lo_x<=x<=hi_x and lo_y<=y<=hi_y):return False
        next_penalty=self.collision_penalty_at(x,y)
        return next_penalty==0 or (self.collision_penalty_at(self.player_x,self.player_y)>next_penalty)

    def ensure_safe_spawn(self,why='arrival'):
        old=(self.player_x,self.player_y)
        if self.can_move_to(*old) and self.collision_penalty_at(*old)==0:return False
        for radius in range(12,385,12):
            choices=[]
            for degrees in range(0,360,15):
                a=math.radians(degrees)
                x=old[0]+radius*math.cos(a);y=old[1]+radius*math.sin(a)
                if self.can_move_to(x,y) and self.collision_penalty_at(x,y)==0:
                    choices.append((math.hypot(x-old[0],y-old[1]),x,y))
            if choices:
                _,self.player_x,self.player_y=min(choices)
                return True
        # World authoring errors should be loudly diagnosable, never silently strand the player.
        for y in range(90,GAME_HEIGHT-38,16):
            for x in range(70,GAME_WIDTH-62,16):
                if self.can_move_to(x,y) and self.collision_penalty_at(x,y)==0:
                    self.player_x=float(x);self.player_y=float(y);return True
        raise RuntimeError(f'No navigable position in {self.current_area_id}, requested {old} ({why})')

    def activate_connection(self,trigger,source_object_id=None,edge=None):
        c=super().activate_connection(trigger,source_object_id,edge)
        if c:
            self.ensure_safe_spawn('transition '+c.connection_id)
            self.sync_carried_position()
        return c

    def reset_market_guard(self):
        self.c1_guard={'area_id':'britrun_market','x':914.0,'y':492.0,'name':'BritRun Guard',
                       'asset':'guard','width':62,'height':90,'alive':True,'facing':(-1.,0.),'sight_radius':365.}
        self.c1_guard_target=None;self.c1_guard_bucketed=False;self.c1_guard_bucket_object_id=None


class C11StateMachine(StateMachine):
    """Explicit player-action rules. B1 editor, screenshot and archives stay intact."""
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)
        saved=self.config.get('keybinds',{})
        self.c1_keys=dict(DEFAULT_KEYS)
        if isinstance(saved,dict):
            for action,key in saved.items():
                if action in DEFAULT_KEYS and isinstance(key,str) and keycode(key) is not None:self.c1_keys[action]=key
        self.c1_rng=random.Random()
        self._log('C1 CONFIG','Keyboard mappings: '+json.dumps(self.c1_keys))

    def start_game(self):
        if self.game is None:
            self.draw_engine=LumaDrawEngine(ASSET_JSON_PATH)
            self.game=C11GameModel(self.draw_engine)
            self.game.ensure_safe_spawn('initial')
            self._log('C11 WORLD',f'{len(self.game.areas)} areas, {len(self.game.objects)} objects, {len(self.game.c1_npcs)} NPCs.')
        self.menu_open=False
        self.active_field=None
        self.transition(AppState.PLAY_GAME,'Play Game button')
        self._set_status('C1.1: WASD/ARROWS move; E take/use/talk; click carry/drop; F3 configure; ? hints.')

    def _speech(self,message,seconds=4):
        game=self.game
        if game:game.c1_say(message,seconds)
        self._set_status(message)

    def _spawn_guard(self,target,source_obj,witness='vendor'):
        g=self.game
        if not g:return
        if g.current_area_id=='britrun_market':
            if not g.c1_guard:g.reset_market_guard()
            guard=g.c1_guard
            speaker='Guard' if witness=='guard' else 'Vendor'
            if witness=='guard':
                line='Guard: I have been waiting YEARS for this!' if target=='naz' else 'Guard: HALT! THIEF!'
            else:line='Kart-lotta: HELP! THIEF! GUARDS!' if g.meta(source_obj).get('owner')=='kart_lotta' else 'HELP! THIEF!'
        else:
            vendors=g.current_area.vendors
            if vendors:
                v=min(vendors,key=lambda v:math.hypot(v['x']-source_obj.x,v['y']-source_obj.y))
                x,y=float(v['x'])+68,float(v['y'])+72
                name=v.get('name','Vendor')
            else:
                x,y=g.player_x+90,g.player_y-60;name='Witness'
            g.c1_guard={'area_id':g.current_area_id,'x':x,'y':y,'name':'City Guard',
                        'asset':'guard','width':62,'height':90,'alive':True,'facing':(-1.,0.),'sight_radius':365.}
            line=f'{name}: HELP! THIEF! GUARDS!'
        g.c1_guard_target=target
        self._speech(line,6)
        self._log('CRIME',f'witness={witness}; accused={target}; item={source_obj.name}; area={g.current_area_id}')

    def _take(self,obj):
        g=self.game
        if not g or obj.in_inventory:return
        if not g.close_to_object(obj):
            self._speech(f'Move closer to {obj.name} first.');return
        if not obj.takeable:
            self._activate(obj);return
        illegal=g.is_unauthorized(obj)
        vendor_saw=bool(illegal and g.is_vendor_watching(obj))
        guard_saw=bool(illegal and g.guard_sees(obj))
        if illegal:
            g.c1_stolen.add(obj.object_id)
            g.c1_owned_taken.add(obj.object_id)
        # Direct take is permitted even when witnessed. Witnessing causes a guard!
        if obj.kind=='gold_pile':
            value=int(g.meta(obj).get('value',19000))
            g.c1_gold+=value
            obj.area_id='__consumed__';obj.in_inventory=False
            if g.carried_object_id==obj.object_id:g.carried_object_id=None
            self._speech(f'Pocketed {value:,} gold. Total: {g.c1_gold:,}.')
        else:
            g.c1_inventory_add(obj)
            self._speech(f'{"STOLEN" if g.is_unauthorized(obj) else "Took"}: {obj.name}. Inventory: {len(g.inventory)} items.')
        g.c1_mark_respawn(obj)
        self._log('C11 ITEM',f'E take: {obj.name}; illegal={illegal} vendor_saw={vendor_saw} guard_saw={guard_saw}')
        if guard_saw:self._spawn_guard('player',obj,witness='guard')
        elif vendor_saw:self._spawn_guard('player',obj,witness='vendor')
        if obj.object_id=='purple_passion_pineapple':
            g.c1_flags['pineapple_taken']=True
            g.c1_troll_angry=True
            self._speech('FROSTY ROARS! GET OUT! A bowl of Not-So-Tasty Soup makes a fast escape.',6)

    def _activate(self,obj):
        g=self.game
        if not g:return
        meta=g.meta(obj)
        kind=obj.kind
        if kind in ('door','path','portal'):
            if not g.close_to_object(obj):self._speech('Walk closer to the entrance.');return
            trigger='door' if kind=='door' else kind
            conn=g.activate_connection(trigger,source_object_id=obj.object_id)
            if conn:self._area_enter(conn)
            else:self._speech('That doorway is not connected yet.')
            return
        action=meta.get('activity')
        if action=='locked':
            self._speech('The treasure-room gate is LOCKED. Perhaps the wall has a weakness...')
        elif action=='clip':
            held=g.object_by_id(g.carried_object_id)
            if held and held.kind=='plate' and g.close_to_object(obj,):
                conn=g.activate_connection('clip',source_object_id=obj.object_id)
                if conn:
                    g.c1_vault_entered=True
                    self._area_enter(conn)
                    self._log('EXPLOIT','Plate clipped player through the intended castle wall seam')
            else:self._speech('An odd gap in the wall. A broad, flat platter might provide some leverage...')
        elif action=='book':
            g.c1_flags['book_read']=True
            self._speech('RECIPE: Purple Passion Pineapple + Redroot + Moonflower. Alchemy table crafts the enhancement potion.',8)
        elif action=='alchemy':self._alchemy()
        elif action=='cook':self._cook()
        elif action=='chest':self._chest()
        elif action in ('armor','weapons'):self._speech('The shop facade is here, but its interior will open in a later version.')
        else:self._speech(f'{obj.name} does nothing special... yet.')

    def _area_enter(self,conn):
        g=self.game
        if not g:return
        self._log('AREA TRANSITION',f'{conn.from_area_id} -> {conn.to_area_id} via {conn.trigger}')
        if g.current_area_id=='britrun_market' and (not g.c1_guard or g.c1_guard['area_id']!='britrun_market'):
            g.reset_market_guard()
        self._speech(f'{conn.label}.  {g.current_area.display_name}.')
        if g.current_area_id=='giant_camp':
            self._die('GIANT SPACE PROGRAM: you have been launched into orbit!',launch=True)
        elif g.current_area_id=='mudcrab_river':
            self._die('MUDCRABS: death by an astonishingly aggressive crustacean.')
        # C1.3: Southern Wilds now leads south to the mountain-side cave.

    def _die(self,reason,launch=False):
        g=self.game
        if not g or g.c1_dead:return
        g.c1_dead=reason
        g.c1_launch_seconds=1.3 if launch else 0
        g.c1_troll_angry=False
        g.c1_guard=None
        g.c1_guard_target=None
        self._speech('YOU DIED: '+reason+' Press R to respawn in BritRun Market.',10)
        self._log('PLAYER DEATH',reason)

    def _respawn(self):
        g=self.game
        if not g:return
        g.c1_dead=None
        g.c1_launch_seconds=0
        g.current_area_id='britrun_market'
        g.player_x,g.player_y=640.0,545.0
        g.ensure_safe_spawn('respawn')
        g.carried_object_id=None
        g.reset_market_guard()
        g.c1_troll_angry=False
        g.c1_soup_seconds=0.0;g.c1_soup_stacks=0
        if g.c1_flags['pineapple_taken'] and not g.c1_flags['quest_done']:
            pp=g.object_by_id('purple_passion_pineapple')
            if pp and pp.object_id in g.inventory:
                g.c1_consume(pp)
            if pp:
                pp.area_id='troll_cave';pp.x=638;pp.y=146;pp.in_inventory=False
            g.c1_flags['pineapple_taken']=False
        self._speech('Respawned in BritRun Market. Learn, adapt, and annoy Murphy.')

    def _chest(self):
        g=self.game
        if g.c1_day<g.c1_chest_next_day:
            self._speech(f'Hidden caravan chest is empty. Respawns on day {g.c1_chest_next_day}. Press T to wait.');return
        g.c1_gold+=2000
        for name,kind,price in [('Khajiit Trinket','gold',450),('Exotic Spice','herb',190),('Caravan Bauble','gold',320)]:
            g.c1_make_item(name,kind,price=price)
        g.c1_chest_next_day=g.c1_day+2
        self._speech(f'KITTY CARAVAN CHEST! +2,000 gold and 3 goods. Gold: {g.c1_gold:,}. Restocks in two days.',7)
        self._log('EXPLOIT',f'Hidden caravan chest loot; day {g.c1_day}; next {g.c1_chest_next_day}')

    def _alchemy(self):
        g=self.game
        if g.c1_flags['quest_done']:
            self._speech('The alchemy table still smells vaguely of purple pineapples.');return
        pineapple=g.c1_have(lambda o:o.kind=='pineapple')
        redroot=g.c1_have(lambda o:'redroot' in o.name.lower())
        moonflower=g.c1_have(lambda o:'moonflower' in o.name.lower())
        missing=[title for title,obj in [('Purple Passion Pineapple',pineapple),('Redroot',redroot),('Moonflower',moonflower)] if not obj]
        if missing:
            self._speech('ALCHEMY: missing '+', '.join(missing)+'. The recipe book explains why.',7);return
        for obj in (pineapple,redroot,moonflower):g.c1_consume(obj)
        g.c1_make_item('Potion of Increased Physical Enhancement','potion',price=69000)
        self._speech('SUCCESS! Crafted the Potion of Increased Physical Enhancement. Take it to Fearmonger!',7)
        self._log('CRAFT','Potion of Increased Physical Enhancement created from PPP, Redroot, Moonflower')

    def _cook(self):
        g=self.game
        tomato=g.c1_have(lambda o:o.kind=='tomato')
        cabbage=g.c1_have(lambda o:o.kind=='cabbage')
        if not tomato or not cabbage:
            self._speech('COOKPOT: a bowl of soup needs one tomato and one cabbage. Kart-lotta restocks daily.');return
        g.c1_consume(tomato);g.c1_consume(cabbage)
        g.c1_make_item('Vegetable Soup','soup',price=55)
        self._speech('Cooked Vegetable Soup! Press F to eat. Two bowls give you the speed to outrun Frosty.')
        self._log('CRAFT','Vegetable soup: tomato + cabbage')

    def _eat(self):
        g=self.game
        obj=g.c1_have(lambda o:o.kind=='soup')
        if not obj:self._speech('No vegetable soup in inventory. Use the inn cooking pot first.');return
        g.c1_consume(obj)
        g.c1_soup_stacks=min(2,g.c1_soup_stacks+1)
        g.c1_soup_seconds=max(13.0,g.c1_soup_seconds)+11.0
        speed='FULL CABBAGE POWER (470 px/s)' if g.c1_soup_stacks>=2 else 'warm legs (280 px/s)'
        self._speech(f'Ate soup. {speed}. {g.c1_soup_seconds:.0f}s remaining.')
        self._log('SOUP',f'stacks={g.c1_soup_stacks},duration={g.c1_soup_seconds:.1f}')

    def _buy(self):
        g=self.game
        if g.current_area_id!='alchemy_shop' or not g.close_to(550,231,220):
            self._speech('To buy the potion, visit the Alchemy Shopkeeper and press B.');return
        if g.c1_gold<69000:
            self._speech(f'Potion price: 69,000. You have {g.c1_gold:,} gold. Need {69000-g.c1_gold:,} more.');return
        g.c1_gold-=69000
        g.c1_make_item('Potion of Increased Physical Enhancement','potion',price=69000)
        self._speech('Bought the enhancement potion for 69,000 gold. The mage awaits!')
        self._log('TRADE',f'Bought quest potion; remaining gold {g.c1_gold}')

    def _sell(self):
        g=self.game
        if g.current_area_id!='alchemy_shop' or not g.close_to(550,231,220):
            self._speech('Press V near the Alchemy Shopkeeper to sell selected inventory goods.');return
        oid=g.inventory_selected_id
        obj=g.object_by_id(oid)
        if not obj or obj.object_id not in g.inventory:
            self._speech('Open inventory (I), click a good, and press V near the shopkeeper.');return
        if obj.kind=='potion' and 'Enhancement' in obj.name:
            self._speech('Better keep that potion for Fearmonger!');return
        val=int(g.meta(obj).get('value',g.meta(obj).get('price',65)))
        if val<=0:val={'gold':180,'herb':35,'potion':125,'plate':20,'cabbage':15,'tomato':12}.get(obj.kind,45)
        g.c1_consume(obj)
        g.c1_gold+=val
        self._speech(f'Sold {obj.name} for {val:,} gold. Purse: {g.c1_gold:,}.')
        self._log('TRADE',f'Sold {obj.name} for {val}; gold={g.c1_gold}')

    def _talk(self,n):
        g=self.game
        nid=n['npc_id']
        if nid=='naz':
            self._speech(self.c1_rng.choice(n.get('lines',['I live in the Gold District, you know.'])),5)
        elif nid=='inn_lout':
            if g.c1_flags['heard_kart'] and not g.c1_flags['lout_warned']:
                g.c1_flags['lout_warned']=True
                self._speech('You: Leave Kart-lotta alone!  Inn Lout: All right, all right! Tell her I am sorry!',7)
                self._log('QUEST','Confronted inn lout on Kart-lotta\'s behalf')
            elif g.c1_flags['lout_warned']:
                self._speech('Inn Lout: I said I would leave Kart-lotta alone!')
            else:self._speech('Inn Lout: That vegetable seller is far too good for this dump!')
        elif nid=='innkeeper':
            self._speech('Innkeeper: My cookpot is free for travelers. A tomato and a cabbage make a fine soup.')
        elif nid=='fearmonger':
            potion=g.c1_have(lambda o:'increased physical enhancement' in o.name.lower())
            if g.c1_flags['quest_done']:
                self._speech('Fearmonger: Ah, my heroic benefactor! I shall never forget your... assistance.')
            elif potion:
                g.c1_consume(potion)
                g.c1_gold+=5000
                g.c1_flags['quest_done']=True
                self._speech('MAIN QUEST COMPLETE! Fearmonger pays 5,000 gold. "My confidence has returned!"',9)
                self._log('QUEST','MAIN QUEST COMPLETE: delivered enhanced potion')
            else:
                g.c1_flags['quest_started']=True
                self._speech('Fearmonger: A delicate personal problem! Bring me a Potion of Increased Physical Enhancement. I will pay well!',9)
                self._log('QUEST','Quest accepted: acquire enhancement potion by any route')
        else:self._speech(n['name']+': Good day.')

    def _talk_vendor(self,v):
        g=self.game
        vid=v.get('vendor_id')
        if vid=='kart_lotta':
            if g.c1_flags['lout_warned'] and 'kart_lotta' not in g.c1_permissions:
                g.c1_permissions.add('kart_lotta')
                self._speech('Kart-lotta: Ohhh, my hero! Take my tomatoes and cabbages freely. They are sooooo firm!',9)
                self._log('QUEST','Kart-lotta befriended; vegetable permission granted')
            elif 'kart_lotta' in g.c1_permissions:
                self._speech(self.c1_rng.choice(['Kart-lotta: Those are the ripest cabbages in BritRun!',
                   'Kart-lotta: Anything on my stall is yours, darling!','Kart-lotta: My tomatoes are the BEST!']))
            else:
                g.c1_flags['heard_kart']=True
                self._speech(self.c1_rng.choice(['Kart-lotta: Ohhhh, my tomatoes are the best! But a lout at the inn keeps bothering me!',
                   'Kart-lotta: My cabbages are soooooo ripe and firm. If only that inn jerk would leave me alone!',
                   'Kart-lotta: Could somebody please tell that troublesome inn patron to stop pestering me?']),8)
        elif vid=='alchemy_vendor':
            self._speech(f'Alchemist: Enhancement potion? A mere 69,000 gold. Press B to buy, V to sell, E at the table to craft.')
        else:self._speech(f'{v.get("name","Vendor")}: Fresh goods and questionable prices!')

    def _use_nearest(self,ui):
        g=self.game
        point=ui.screen_to_game(pygame.mouse.get_pos())
        # A target under the cursor has highest priority, then nearest NPC/vendor/object.
        if point:
            obj=g.hit_test(point)
            if obj and (g.close_to_object(obj) or obj.kind in ('door','path','portal')):
                self._take(obj) if obj.takeable else self._activate(obj)
                return
            n=g.c1_npc_at(point)
            if n and g.close_to(n['x'],n['y'],180):self._talk(n);return
            vendor_hit=g.vendor_at(point)
            if vendor_hit:
                v=vendor_hit[0]
                if g.close_to(v['x'],v['y'],190):self._talk_vendor(v);return
        # If nothing was deliberately hovered, favor NPCs close enough to talk.
        n=g.c1_nearest_npc(105)
        if n:self._talk(n);return
        candidates=[(math.hypot(g.player_x-v['x'],g.player_y-v['y']),v)
                    for v in g.current_area.vendors]
        candidates.sort(key=lambda t:t[0])
        closest_obj=g.c1_nearest(g.player_x,g.player_y,118)
        if closest_obj:
            self._take(closest_obj) if closest_obj.takeable else self._activate(closest_obj)
            return
        if candidates and candidates[0][0]<175:
            self._talk_vendor(candidates[0][1]);return
        self._speech('Nothing close enough to activate. Move closer and point at it, then press E.')

    def _mouse_game(self,event,ui):
        g=self.game
        if ui.layout.game_back_button.collidepoint(event.pos):
            self.transition(AppState.MAIN,'Back to Tool button');return
        if ui.layout.game_screenshot_button.collidepoint(event.pos):ui.save_screenshot(self);return
        point=ui.screen_to_game(event.pos)
        if point is None:return
        if g.c1_config_open:
            # Rows of the keybind dialog are clickable to select a mapping.
            for i,k in enumerate(DEFAULT_KEYS):
                rect=pygame.Rect(380,94+i*29,490,27)
                if rect.collidepoint(point):g.c1_rebind=k;self._speech(f'Press any key for {KEY_LABELS[k]}...');return
            return
        if g.inventory_open:
            if g.inventory_close_rect().collidepoint(point):g.inventory_open=False;return
            if g.inventory_drop_rect().collidepoint(point):self._drop_inventory_selection(g);return
            if g.inventory_panel_rect().collidepoint(point):
                for i,oid in enumerate(g.inventory[:12]):
                    if g.inventory_row_rect(i).collidepoint(point):
                        g.inventory_selected_id=oid
                        obj=g.object_by_id(oid)
                        self._speech('Selected '+obj.name if obj else 'Missing inventory item')
                        return
                return
            g.inventory_open=False;return
        if g.inventory_button_rect().collidepoint(point):
            g.inventory_open=True
            if g.inventory_selected_id not in g.inventory:g.inventory_selected_id=g.inventory[0] if g.inventory else None
            return
        held=g.object_by_id(g.carried_object_id)
        # Guard bucket trick: block his eyes, but not a vendor's shouted alarm.
        guard_head=g.guard_head_rect()
        if guard_head.collidepoint(point) and g.c1_guard:
            q=g.c1_guard
            if not g.close_to(q['x'],q['y'],165):
                self._speech('Get closer to the guard first.');return
            if g.c1_guard_bucketed and held is None:
                bucket=g.object_by_id(g.c1_guard_bucket_object_id)
                if bucket:
                    g.carried_object_id=bucket.object_id;g.c1_guard_bucketed=False
                    g.c1_guard_bucket_object_id=None;g.sync_carried_position()
                    self._speech('Retrieved the guard bucket. Eyesight restored.');return
            if held and held.kind=='bucket' and not g.c1_guard_bucketed:
                g.c1_guard_bucketed=True;g.c1_guard_bucket_object_id=held.object_id
                held.area_id=g.current_area_id;held.x=q['x']-18;held.y=q['y']-44
                g.carried_object_id=None
                self._speech('BUCKET ON GUARD! He cannot see theft until the bucket comes off.')
                self._log('EXPLOIT','Bucket placed over market guard');return
        vendor_hit=g.vendor_at(point)
        obj=g.hit_test(point)
        if held is None and vendor_hit and vendor_hit[1]=='head' and g.bucket_on_head_vendor_id==vendor_hit[0].get('vendor_id'):
            if g.close_to(vendor_hit[0]['x'],vendor_hit[0]['y'],155):
                bucket=next((o for o in g.objects if o.kind=='bucket' and o.area_id==g.current_area_id),None)
                if bucket:
                    g.carried_object_id=bucket.object_id;g.bucket_on_head_vendor_id=None
                    g.sync_carried_position()
                    self._speech('Retrieved bucket. Click near a vendor head to cover their eyes.')
            return
        if held and held.kind=='bucket' and vendor_hit and vendor_hit[1]=='head':
            v=vendor_hit[0]
            if not g.close_to(v['x'],v['y'],155):self._speech('Move closer to the vendor first.');return
            g.bucket_on_head_vendor_id=v['vendor_id'];g.carried_object_id=None
            held.area_id=g.current_area_id
            held.x=float(v['x']-held.width/2);held.y=float(v['y']-43)
            self._speech('BUCKET ON FACE! Vendor cannot witness theft while properly bucketed.')
            self._log('EXPLOIT','Bucket placed covering '+v['vendor_id'])
            return
        if held:
            if not g.close_to(*point,reach=150):self._speech('Too far away to place the carried item.');return
            x,y=point
            if vendor_hit:
                v=vendor_hit[0];x=v['x']+58;y=v['y']+47
            elif obj and obj.object_id!=held.object_id:
                x=obj.x+obj.width+held.width/2+8;y=obj.y+obj.height/2
            # Clicking the carried item, or the player, no longer transfers to inventory.
            g.place_object_at(held,x,y,on_shelf=bool(obj and obj.on_shelf))
            g.carried_object_id=None
            self._speech(f'Placed {held.name}. E takes an item into inventory; clicks only carry/place.')
            return
        if obj:
            if not g.close_to_object(obj):self._speech(f'Move closer to {obj.name}.');return
            if obj.takeable:
                if obj.object_id=='purple_passion_pineapple':
                    g.c1_troll_angry=True
                    self._speech('FROSTY ROARS! The pineapple is HIS! Dash for the exit!')
                g.carried_object_id=obj.object_id;g.selected_object_id=obj.object_id
                g.sync_carried_position()
                self._speech(f'Carrying {obj.name}. Click nearby to place it; E puts it in inventory.')
            else:
                g.selected_object_id=obj.object_id
                self._speech(f'{obj.name} selected. Press E to activate it.')
            return
        if vendor_hit:
            self._speech(vendor_hit[0].get('name','Vendor')+': press E to talk; a carried bucket can be placed on the head.')
        else:
            n=g.c1_npc_at(point)
            if n:self._speech(n['name']+': press E to talk.')
            else:g.selected_object_id=None

    def _dispatch_game(self,event,ui):
        g=self.game
        if not g:
            self.transition(AppState.MAIN,'Missing game model');return
        if event.type==pygame.KEYDOWN:
            if g.c1_rebind:
                action=g.c1_rebind
                if event.key!=pygame.K_ESCAPE:
                    val='?' if event.unicode=='?' else pygame.key.name(event.key)
                    self.c1_keys[action]=val
                    self.config['keybinds']=dict(self.c1_keys)
                    err=self.persist_preference('keybinds',dict(self.c1_keys))
                    self._speech(f'{KEY_LABELS[action]} is now {val.upper()}.' if not err else f'Settings save failed: {err}')
                g.c1_rebind=None;return
            if matches(event,self.c1_keys['config']):
                g.c1_config_open=not g.c1_config_open
                self._speech('Keyboard configuration: click a row then press its new key.' if g.c1_config_open else 'Configuration closed.')
                return
            if g.c1_config_open:
                if event.key==pygame.K_ESCAPE:g.c1_config_open=False
                return
            if g.c1_dead:
                if matches(event,self.c1_keys['respawn']):self._respawn()
                return
            if matches(event,self.c1_keys['exit']):
                if g.inventory_open:g.inventory_open=False
                else:
                    self.transition(AppState.MAIN,'Returned from Play Game')
                    self._set_status('Returned to SGG tool.')
                return
            if matches(event,self.c1_keys['screenshot']) or (event.key==pygame.K_s and (pygame.key.get_mods()&pygame.KMOD_CTRL)):
                ui.save_screenshot(self);return
            if matches(event,self.c1_keys['hints']):
                g.c1_hint_visible=not g.c1_hint_visible
                self._speech('Hints '+('ON' if g.c1_hint_visible else 'OFF'))
                return
            if matches(event,self.c1_keys['inventory']):
                g.inventory_open=not g.inventory_open
                if g.inventory_selected_id not in g.inventory:g.inventory_selected_id=g.inventory[0] if g.inventory else None
                return
            if matches(event,self.c1_keys['wait']):self._speech(g.c1_wait());return
            if matches(event,self.c1_keys['eat']):self._eat();return
            if matches(event,self.c1_keys['buy']):self._buy();return
            if matches(event,self.c1_keys['sell']):self._sell();return
            if matches(event,self.c1_keys['drop']):
                if g.carried_object_id:
                    o=g.object_by_id(g.carried_object_id)
                    if o:g.place_object_at(o,g.player_x+31,g.player_y+17)
                    g.carried_object_id=None
                    self._speech('Dropped the carried item.')
                elif g.inventory_open:self._drop_inventory_selection(g)
                return
            if matches(event,self.c1_keys['use']):
                if g.inventory_open:
                    o=g.object_by_id(g.inventory_selected_id)
                    if o and o.kind=='soup':self._eat()
                    else:self._speech('Press F to eat soup. E works on objects, doors, tables and people.')
                elif g.carried_object_id:
                    o=g.object_by_id(g.carried_object_id)
                    if o:self._take(o)
                else:self._use_nearest(ui)
                return
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if not g.c1_dead:self._mouse_game(event,ui)

    def update(self,elapsed_seconds,ui):
        g=self.game
        if self.state is not AppState.PLAY_GAME or not g:return
        dt=max(0.0,min(0.05,elapsed_seconds))
        g.c1_elapsed+=dt
        if g.c1_speech_seconds>0:g.c1_speech_seconds=max(0.0,g.c1_speech_seconds-dt)
        if g.c1_soup_seconds>0:
            g.c1_soup_seconds=max(0.0,g.c1_soup_seconds-dt)
            if not g.c1_soup_seconds:g.c1_soup_stacks=0
        if g.c1_dead:
            g.c1_launch_seconds=max(0.0,g.c1_launch_seconds-dt)
            return
        if g.c1_config_open:return
        keys=pygame.key.get_pressed()
        def pressed(action):
            return c12_held(self.c1_keys[action],keys)
        dx=int(pressed('right') or keys[pygame.K_RIGHT])-int(pressed('left') or keys[pygame.K_LEFT])
        dy=int(pressed('down') or keys[pygame.K_DOWN])-int(pressed('up') or keys[pygame.K_UP])
        if pygame.key.get_mods()&pygame.KMOD_CTRL and pressed('down'):dy=0
        if dx or dy:
            length=math.hypot(dx,dy)
            speed=220 * (self.soup_speed_multiplier if g.c1_soup_seconds>0 else 1.0)
            nx=g.player_x+dx/length*speed*dt
            ny=g.player_y+dy/length*speed*dt
            if g.can_move_to(nx,g.player_y):g.player_x=nx
            if g.can_move_to(g.player_x,ny):g.player_y=ny
            g.sync_carried_position()
            edge=None
            if g.player_x<=27:edge='left'
            elif g.player_x>=GAME_WIDTH-27:edge='right'
            elif g.player_y<=46:edge='top'
            elif g.player_y>=GAME_HEIGHT-40:edge='bottom'
            if edge:
                conn=g.activate_connection('edge',edge=edge)
                if conn:self._area_enter(conn)
            # Hidden seam is passable ONLY while holding a platter and pressing toward it.
            if (g.current_area_id=='castle_hall' and not g.c1_dead and
                g.carried_object_id and (o:=g.object_by_id(g.carried_object_id)) and o.kind=='plate' and
                970<g.player_x<1070 and 210<g.player_y<405 and dx>0):
                conn=g.activate_connection('clip',source_object_id='vault_wall_seam')
                if conn:g.c1_vault_entered=True;self._area_enter(conn)
        self._npc_tick(dt)

    def _npc_tick(self,dt):
        g=self.game
        naz=g.c1_npcs.get('naz')
        if naz and naz.get('alive',True):
            # Slow wandering in the market; he notices dropped valuables near him.
            if g.current_area_id=='britrun_market':
                target=None
                for o in g.live_objects():
                    if o.kind in ('gold','gold_pile') and o.moved and not o.in_inventory and o.object_id!=g.carried_object_id:
                        if abs(o.x-naz['x'])<260:target=o;break
                if target:
                    dest=target.x+target.width/2
                    naz['x']+=max(-72*dt,min(72*dt,dest-naz['x']))
                    if abs(naz['x']-dest)<31:
                        # Naz is not the player; apply the SAME ownership and witness logic.
                        crime=bool(target.object_id in g.c1_stolen or target.stealable)
                        observed=bool(crime and g.guard_sees(target))
                        vendor_saw=bool(crime and g.is_vendor_watching(target))
                        target.area_id='__consumed__'
                        naz['holding']=target.name
                        self._log('NPC ACTION',f'Naz took {target.name}; stolen={crime} guard_saw={observed} vendor_saw={vendor_saw}')
                        if observed:self._spawn_guard('naz',target,witness='guard')
                        elif vendor_saw:self._spawn_guard('naz',target,witness='vendor')
                        else:g.c1_say('Naz: Finders keepers, peasants!',4)
                else:
                    naz['x']=min(1110,max(555,naz['x']+math.sin(g.c1_elapsed*.75)*35*dt))
            if g.c1_elapsed>g.c1_naz_lines_at+13 and g.current_area_id=='britrun_market':
                g.c1_naz_lines_at=g.c1_elapsed
                g.c1_say(self.c1_rng.choice(naz.get('lines',['I am important!'])),4)
        guard=g.c1_guard
        if guard and guard['area_id']==g.current_area_id and g.c1_guard_target is not None:
            if g.c1_guard_target=='naz':
                target=g.c1_npcs.get('naz')
                if not target or not target.get('alive',True):g.c1_guard=None;return
                tx,ty=target['x'],target['y']
            else:tx,ty=g.player_x,g.player_y
            vx=tx-guard['x'];vy=ty-guard['y'];length=math.hypot(vx,vy)
            if length>1:
                speed=330 if g.c1_guard_target=='player' else 370
                guard['x']+=vx/length*speed*dt;guard['y']+=vy/length*speed*dt
            if length<52:
                if g.c1_guard_target=='naz':
                    g.c1_npcs['naz']['alive']=False
                    g.c1_guard_target=None
                    self._speech('Guard: I have been waiting YEARS for him to do that!',7)
                    self._log('NPC DEATH','Naz the Jerk killed by guard for observed theft')
                else:self._die('Caught by a guard after a witnessed theft!')
        if g.current_area_id=='troll_cave' and g.c1_troll_angry:
            troll=g.c1_npcs.get('troll')
            if troll:
                vx=g.player_x-troll['x'];vy=g.player_y-troll['y'];dist=math.hypot(vx,vy)
                if dist>1:
                    speed=305
                    troll['x']+=vx/dist*speed*dt;troll['y']+=vy/dist*speed*dt
                if dist<67:self._die('Frosty the Trollman gives you a warm welcome with his claws!')


class C11Interface(LumaInterface):
    """Additional art/UI draw layer; the original B1.0 look remains unchanged."""
    def _draw_game_scene(self,surface,g):
        engine=self.machine.draw_engine
        if engine is None:return super()._draw_game_scene(surface,g)
        # Intercept TWO specific B1 rendering roles, without changing original art.
        draw_original=engine.draw_asset
        roles=engine.data.get('render_roles',{})
        vendor_asset=roles.get('vendor','vendor')
        bucket_asset=roles.get('bucket_on_vendor_head','bucket_inverted')
        def draw_override(dst,name,rect=None):
            # Hidden caravan chest is drawable only while the pointer is over
            # its configurable hitbox. C1.3 accidentally suppressed every draw.
            if name=='chest' and g.current_area_id=='stables' and rect is not None and rect.x>1100:
                pointer=self.screen_to_game(pygame.mouse.get_pos())
                chest=g.object_by_id('stable_caravan_chest')
                if pointer is None or chest is None or g.hit_test(pointer) is not chest:
                    return None
            if name==vendor_asset and rect is not None:
                for v in g.current_area.vendors:
                    if v.get('recipe') and abs(rect.centerx-v['x'])<4 and abs(rect.centery-v['y'])<4:
                        name=v['recipe'];break
            if name==bucket_asset and rect is not None and g.bucket_on_head_vendor_id:
                v=g.vendor_by_id(g.bucket_on_head_vendor_id)
                if v and any(z.get('vendor_id')==g.bucket_on_head_vendor_id for z in g.current_area.vendors):
                    rect=pygame.Rect(int(v['x']-31),int(v['y']-44),62,47)
            return draw_original(dst,name,rect)
        engine.draw_asset=draw_override
        try:super()._draw_game_scene(surface,g)
        finally:engine.draw_asset=draw_original
        # Additional characters retain the procedural recipe style.
        for npc in g.c1_npcs.values():
            if npc['area_id']!=g.current_area_id or not npc.get('alive',True):continue
            r=pygame.Rect(round(npc['x']-npc.get('width',60)/2),round(npc['y']-npc.get('height',80)/2),
                          npc.get('width',60),npc.get('height',80))
            engine.draw_asset(surface,npc['asset'],r)
        if g.c1_guard and g.c1_guard['area_id']==g.current_area_id:
            guard=g.c1_guard
            r=pygame.Rect(round(guard['x']-31),round(guard['y']-45),62,90)
            engine.draw_asset(surface,'guard',r)
            if g.c1_guard_bucketed:
                engine.draw_asset(surface,'bucket_inverted',pygame.Rect(round(guard['x']-31),round(guard['y']-47),62,47))
        # Replace the B1 status headline with the C1 interaction and currency HUD.
        pygame.draw.rect(surface,(20,18,22),(0,0,GAME_WIDTH,44))
        pygame.draw.line(surface,(187,145,83),(0,43),(GAME_WIDTH,43),2)
        self._c1_text(surface,g.current_area.display_name.upper(),20,12,(255,224,168),self.game_font,325)
        self._c1_text(surface,f'DAY {g.c1_day}  •  GOLD {g.c1_gold:,}',420,12,(247,226,171),self.game_small_font,285)
        self._c1_text(surface,'E USE  ·  F5 SAVE  ·  F9 LOAD  ·  F6 SLOTS',710,12,(236,232,221),self.game_small_font,350)
        if g.c1_flags['quest_done']:
            self._c1_text(surface,'QUEST COMPLETE',990,56,(127,255,165),self.game_font,268)
        elif g.c1_flags['quest_started']:
            self._c1_text(surface,'FIND ENHANCEMENT POTION',1013,57,(249,220,147),self.game_small_font,253)
        if g.c1_soup_seconds>0:
            self._c1_text(surface,f'SOUP {self.machine.soup_speed_multiplier:.1f}x  {g.c1_soup_seconds:.0f}s',25,52,
                          (156,255,157),self.game_small_font,260)
        if not getattr(self, "d1_external_hints", False):
            # The hint/status bar can be turned entirely off with '?' (no decorative empty panel).
            hint_rect=pygame.Rect(16,574,1248,31)
            if not g.c1_hint_visible:
                # Restore the original background pixels for the bottom of this canvas.
                # No animated character is stationed down here.
                bg=pygame.Surface((GAME_WIDTH,GAME_HEIGHT))
                engine.draw_asset(bg,g.current_area.background_asset,pygame.Rect(0,0,GAME_WIDTH,GAME_HEIGHT))
                surface.blit(bg,hint_rect,hint_rect)
            else:
                pygame.draw.rect(surface,(18,16,17),hint_rect,border_radius=5)
                pygame.draw.rect(surface,(174,131,74),hint_rect,1,border_radius=5)
                hint='E=USE/TALK  I=INVENTORY  F1=GAME SETTINGS  F3=KEYS  F5=SAVE  F9=LOAD  ?=HIDE'
                if g.current_area_id=='castle_hall':hint='TREASURE ROOM: the locked gate is not the only way in. A platter + a suspicious wall seam...'
                elif g.current_area_id=='troll_cave':hint='PURPLE PASSION PINEAPPLE! Frosty attacks when you take it. Eat Not-So-Tasty Soup to outrun him!'
                elif g.current_area_id=='stables':hint=f'KITTY CARAVAN: hidden chest 2,000 gold, respawns in two days. Day {g.c1_day}.'
                elif g.current_area_id=='alchemy_shop':hint='ALCHEMIST: B=buy enhancement potion (69,000g); V=sell; E=alchemy table or recipe book.'
                elif g.current_area_id=='inn_interior':hint='INN: E by the hearth/cookpot to cook; 2 tomatoes + 2 cabbages makes speed soup!'
                elif g.current_area_id=='mages_lab':hint='E to talk to Fearmonger and deliver his VERY PERSONAL enhancement potion.'
                self._c1_text(surface,hint,28,583,(247,240,222),self.game_small_font,1208)
        # World affordances: ownership is a separate flag from being witnessed.
        point=self.screen_to_game(pygame.mouse.get_pos()) if getattr(self,'game_blit_rect',None) else None
        if point is not None and not g.c1_config_open and not g.inventory_open:
            obj=g.hit_test(point)
            npc=g.c1_npc_at(point)
            v=g.vendor_at(point)
            if obj:
                if obj.kind in ('door','path','portal'): label=f'E: {obj.name}';color=(156,226,255)
                elif not obj.takeable:label=f'E: {obj.name}';color=(156,226,255)
                elif g.is_unauthorized(obj):
                    label=f'STOLEN / OWNED: {obj.name} (E to take)';color=(255,104,104)
                else:label=f'FREE / PERMITTED: {obj.name} (E to take)';color=(148,251,173)
            elif npc:label=f'E: TALK TO {npc["name"]}';color=(238,228,185)
            elif v:label=f'E: TALK TO {v[0]["name"]}';color=(238,228,185)
            else:label=None;color=(247,240,222)
            if label:
                font=self.game_small_font
                txt=font.render(label,True,color)
                px=min(GAME_WIDTH-txt.get_width()-12,max(8,point[0]+15))
                py=min(GAME_HEIGHT-64,max(50,point[1]+13))
                rr=pygame.Rect(px-6,py-4,txt.get_width()+12,txt.get_height()+8)
                pygame.draw.rect(surface,(17,14,15),rr,border_radius=4)
                pygame.draw.rect(surface,color,rr,1,border_radius=4)
                surface.blit(txt,(px,py))
        if not getattr(self, "d1_speech_bubbles", False) and g.c1_speech_seconds>0 and g.c1_selected_speech:
            rr=pygame.Rect(145,506,987,58)
            pygame.draw.rect(surface,(24,22,31),rr,border_radius=8)
            pygame.draw.rect(surface,(206,164,93),rr,2,border_radius=8)
            self._c1_wrapped(surface,g.c1_selected_speech,rr.x+15,rr.y+8,rr.width-30,(253,235,195))
        if g.c1_dead:
            pygame.draw.rect(surface,(0,0,0,190),(0,0,GAME_WIDTH,GAME_HEIGHT))
            self._c1_text(surface,'YOU DIED',414,170,(246,88,80),self.game_font,460)
            self._c1_wrapped(surface,g.c1_dead,363,246,585,(255,226,205))
            self._c1_text(surface,'PRESS R TO RESPAWN',397,362,(255,226,160),self.game_font,510)
        self._draw_edge_arrows(surface,g)
        if g.c1_config_open:self._c1_config_dialog(surface,g)

    def _draw_edge_arrows(self,surface,g):
        # Every edge link gets its own marker, including Gold District's TWO right-side exits.
        for conn,center in g.edge_markers():
            direction=conn.edge
            if direction in ('top','bottom'):
                x=int(max(60,min(GAME_WIDTH-60,center)))
                y=52 if direction=='top' else GAME_HEIGHT-24
                points=([(x,y-14),(x-13,y+4),(x-5,y+4),(x-5,y+12),(x+5,y+12),(x+5,y+4),(x+13,y+4)]
                        if direction=='top' else
                        [(x,y+13),(x-13,y-4),(x-5,y-4),(x-5,y-12),(x+5,y-12),(x+5,y-4),(x+13,y-4)])
                text_y=y+14 if direction=='top' else y-60
                label_rect=pygame.Rect(x-105,text_y,210,19)
            else:
                x=20 if direction=='left' else GAME_WIDTH-20
                y=int(max(105,min(GAME_HEIGHT-55,center)))
                points=([(x-14,y),(x+4,y-13),(x+4,y-5),(x+12,y-5),(x+12,y+5),(x+4,y+5),(x+4,y+13)]
                        if direction=='left' else
                        [(x+14,y),(x-4,y-13),(x-4,y-5),(x-12,y-5),(x-12,y+5),(x-4,y+5),(x-4,y+13)])
                label_rect=pygame.Rect(37 if direction=='left' else GAME_WIDTH-217,y-29,180,19)
            pygame.draw.polygon(surface,(30,28,37),points)
            pygame.draw.polygon(surface,(250,209,104),points,3)
            name=g.areas[conn.to_area_id].display_name
            caption=self.game_small_font.render(name[:21],True,(251,232,172))
            panel=caption.get_rect(center=label_rect.center).inflate(10,3)
            pygame.draw.rect(surface,(28,27,32),panel,border_radius=3)
            surface.blit(caption,caption.get_rect(center=label_rect.center))

    def _c1_text(self,surface,s,x,y,color,font,width):
        txt=str(s)
        while txt and font.size(txt)[0]>width:txt=txt[:-2]+'…'
        surface.blit(font.render(txt,True,color),(x,y))

    def _c1_wrapped(self,surface,s,x,y,w,color):
        words=str(s).split();line='';lines=[]
        for word in words:
            candidate=(line+' '+word).strip()
            if self.game_small_font.size(candidate)[0]>w and line:
                lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        for i,line in enumerate(lines[:3]):
            surface.blit(self.game_small_font.render(line,True,color),(x,y+i*19))

    def _c1_config_dialog(self,surface,g):
        rr=pygame.Rect(355,58,570,537)
        pygame.draw.rect(surface,(25,22,29),rr,border_radius=10)
        pygame.draw.rect(surface,(214,169,101),rr,3,border_radius=10)
        self._c1_text(surface,f'CONFIGURE CONTROLS   [{self.machine.c1_keys["config"].upper()} closes]',390,65,(255,230,176),self.game_font,525)
        for i,action in enumerate(DEFAULT_KEYS):
            row=pygame.Rect(380,94+i*29,490,27)
            bg=(107,73,69) if g.c1_rebind==action else ((51,47,58) if i%2==0 else (42,37,47))
            pygame.draw.rect(surface,bg,row,border_radius=3)
            self._c1_text(surface,KEY_LABELS[action],390,row.y+4,(239,229,202),self.game_small_font,310)
            self._c1_text(surface,self.machine.c1_keys[action].upper(),772,row.y+4,(145,244,169),self.game_small_font,92)
        self._c1_text(surface,'Click a row, then press the replacement key. Esc cancels.',383,544,(222,213,192),self.game_small_font,517)




# C1.2 extensions are below. The program remains one self-contained source file.


# ---------------------------------------------------------------------------
# C1.2 — persistent saves, branching conversations and reactive NPC pursuits
# ---------------------------------------------------------------------------

SAVE_FOLDER = PROJECT_DIR / 'saves'
SAVE_SCHEMA = 'spiffys-gift-save-v1'
SAVE_SLOTS = ('quick', 'slot1', 'slot2', 'slot3')


def c12_save_path(slot):
    if slot not in SAVE_SLOTS:
        raise ValueError('Unknown save slot')
    return SAVE_FOLDER / (slot + '.json')


def c12_binding_matches(event, binding):
    """Match a full chord rather than interpreting CTRL+S as plain S."""
    if not isinstance(binding, str):
        return False
    raw = binding.strip().lower().replace('control+', 'ctrl+')
    parts = raw.split('+')
    base = parts[-1]
    required = set(parts[:-1])
    if base == '?':
        key_ok = event.key == pygame.K_SLASH and bool(event.mod & pygame.KMOD_SHIFT or event.unicode == '?')
    else:
        key = keycode(base)
        key_ok = key is not None and event.key == key
    mods = getattr(event, 'mod', 0)
    actual = set()
    if mods & pygame.KMOD_CTRL:actual.add('ctrl')
    if mods & pygame.KMOD_SHIFT:actual.add('shift')
    if mods & pygame.KMOD_ALT:actual.add('alt')
    # Keep legacy unmodified single-key bindings usable with caps-lock etc.
    if base == '?':required.add('shift')
    return key_ok and required == actual


def c12_held(binding,pressed):
    raw=str(binding).strip().lower().split('+')
    code=keycode(raw[-1])
    if code is None or not pressed[code]:return False
    required=set(raw[:-1]);mod=pygame.key.get_mods()
    active=set()
    if mod & pygame.KMOD_CTRL:active.add('ctrl')
    if mod & pygame.KMOD_ALT:active.add('alt')
    if mod & pygame.KMOD_SHIFT:active.add('shift')
    return required==active


def c12_key_label(event):
    base = pygame.key.name(event.key)
    # Modifier keys can be bound alone (as in C1.1) without self-modification.
    if event.key in (pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT,
                     pygame.K_RALT, pygame.K_LSHIFT, pygame.K_RSHIFT):
        return base
    mods = getattr(event, 'mod', 0)
    prefix = []
    if mods & pygame.KMOD_CTRL:prefix.append('ctrl')
    if mods & pygame.KMOD_ALT:prefix.append('alt')
    if mods & pygame.KMOD_SHIFT and event.unicode != '?' and base != 'slash':prefix.append('shift')
    if event.unicode == '?':return '?'
    return '+'.join(prefix + [base])


class C12GameModel(C11GameModel):
    """No external baseline or imported C1 files: C1.2 remains stand-alone."""
    SAVE_FIELDS = (
        'current_area_id', 'player_x', 'player_y', 'player_width', 'player_height',
        'inventory', 'inventory_open', 'inventory_selected_id', 'carried_object_id',
        'bucket_on_head_vendor_id', 'selected_object_id', 'c1_day', 'c1_gold',
        'c1_flags', 'c1_respawn_due', 'c1_npcs', 'c1_guard', 'c1_guard_target',
        'c1_guard_bucketed', 'c1_guard_bucket_object_id', 'c1_troll_angry',
        'c1_soup_stacks', 'c1_soup_seconds', 'c1_soup_total', 'c1_dead',
        'c1_launch_seconds', 'c1_elapsed', 'c1_naz_lines_at', 'c1_chest_next_day',
        'c1_item_counter', 'c1_vault_entered', 'c1_quest_log',
        'c1_wait_banner',
    )
    SAVE_SET_FIELDS = ('c1_permissions', 'c1_stolen', 'c1_owned_taken')

    def __init__(self, engine):
        super().__init__(engine)
        self.c1_flags.update({'lout_challenged': False, 'lout_resolved': None,
                              'lout_demand': False})
        self.c1_dialogue = None
        self.c1_dialogue_selected = 0
        self.c1_save_panel = False
        self.c1_save_message = ''

    def is_permitted(self, obj):
        if not obj:return False
        if not obj.stealable:return True
        return (self.meta(obj).get('owner') == 'kart_lotta'
                and obj.kind in ('tomato', 'cabbage')
                and 'kart_lotta' in self.c1_permissions)

    def witnessing_details(self, obj):
        q = self.c1_guard
        if not q or q.get('area_id') != self.current_area_id:
            return 'guard=absent_or_other_area'
        source = (float(q['x']), float(q['y'])-12.)
        target = (obj.x+obj.width/2, obj.y+obj.height/2)
        distance = math.dist(source, target)
        face = q.get('facing', (-1., 0.))
        dot = face[0]*(target[0]-source[0])+face[1]*(target[1]-source[1])
        return (f'guard_pos=({source[0]:.0f},{source[1]:.0f})'
                f' item_pos=({target[0]:.0f},{target[1]:.0f})'
                f' distance={distance:.1f} radius={q.get("sight_radius",365)}'
                f' behind_guard={distance>60 and dot<-.15*distance}'
                f' conceal={self._in_conceal_zone(*target)}'
                f' blocked={self._line_is_blocked(source,target,obj.rect())}'
                f' bucketed={self.c1_guard_bucketed}')

    def snapshot(self):
        from dataclasses import fields
        object_fields = [f.name for f in fields(GameObject)]
        values = {k:getattr(self,k) for k in self.SAVE_FIELDS}
        return {'schema': SAVE_SCHEMA, 'source_version': VERSION,
                'saved_at': datetime.now().astimezone().isoformat(),
                'state': values,
                'sets': {k:sorted(getattr(self,k)) for k in self.SAVE_SET_FIELDS},
                'objects': [{k:getattr(o,k) for k in object_fields} for o in self.objects],
                'item_meta': self.item_meta}

    @classmethod
    def from_snapshot(cls, engine, data):
        """Build and validate a *new* world before replacing the live one."""
        if not isinstance(data,dict) or data.get('schema') != SAVE_SCHEMA:
            raise ValueError('Unknown or incompatible save format')
        state, saved_sets = data.get('state'),data.get('sets')
        if not isinstance(state,dict) or not isinstance(saved_sets,dict):
            raise ValueError('Save is missing world state')
        g = cls(engine)
        if state.get('current_area_id') not in g.areas:
            raise ValueError('Save refers to an unknown area')
        for key in cls.SAVE_FIELDS:
            if key not in state:raise ValueError('Save missing '+key)
            setattr(g,key,state[key])
        for key in cls.SAVE_SET_FIELDS:
            values=saved_sets.get(key)
            if not isinstance(values,list) or not all(isinstance(v,str) for v in values):
                raise ValueError('Invalid '+key)
            setattr(g,key,set(values))
        if not isinstance(data.get('objects'),list) or len(data['objects'])>5000:
            raise ValueError('Invalid saved object collection')
        from dataclasses import fields
        cols={f.name for f in fields(GameObject)}
        g.objects=[]
        for obj in data['objects']:
            if not isinstance(obj,dict) or not cols.issubset(obj):
                raise ValueError('Invalid saved object')
            g.objects.append(GameObject(**{k:obj[k] for k in cols}))
        ids=[o.object_id for o in g.objects]
        if len(ids)!=len(set(ids)) or len(ids)<len(engine.world['objects']):
            raise ValueError('Missing or duplicate object IDs in save')
        if not set(o['object_id'] for o in engine.world['objects']).issubset(ids):
            raise ValueError('Core world object missing from save')
        g.item_meta=data.get('item_meta')
        if not isinstance(g.item_meta,dict):raise ValueError('Missing item metadata')
        if not isinstance(g.inventory,list) or not set(g.inventory).issubset(ids):
            raise ValueError('Invalid inventory references')
        if not all(isinstance(x,(int,float)) and math.isfinite(x)
                   for x in (g.player_x,g.player_y)):
            raise ValueError('Invalid saved position')
        if not isinstance(g.c1_npcs,dict):
            raise ValueError('Invalid NPC state')
        if not set(n['npc_id'] for n in engine.world.get('npcs',[])).issubset(g.c1_npcs):
            raise ValueError('Missing NPC state')
        if g.carried_object_id is not None and g.carried_object_id not in ids:
            raise ValueError('Invalid carried item')
        if g.c1_guard_target not in (None,'player','naz','inn_lout'):
            raise ValueError('Unknown guard pursuit target')
        if not isinstance(g.c1_flags,dict):raise ValueError('Invalid quest state')
        g.c1_flags.setdefault('lout_challenged',False)
        g.c1_flags.setdefault('lout_resolved',None)
        g.c1_flags.setdefault('lout_demand',False)
        # Menus are transient UI, not gameplay. No mid-dialogue saves.
        g.c1_dialogue=None;g.c1_dialogue_selected=0;g.c1_save_panel=False
        g.c1_config_open=False;g.c1_rebind=None
        g.c1_selected_speech='';g.c1_speech_seconds=0
        g.inventory_open=False
        return g


class C12StateMachine(C11StateMachine):
    """Reusable dialogue choices with explicit actions and durable game snapshots."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # C1.1's loader accepts only plain keys; retain actual chord strings here.
        saved=self.config.get('keybinds',{})
        if isinstance(saved,dict):
            self.c1_keys.update({k:v for k,v in saved.items()
                                 if k in DEFAULT_KEYS and isinstance(v,str)
                                 and keycode(v.split('+')[-1]) is not None})
        self.c1_keys={**DEFAULT_KEYS,**self.c1_keys}

    def start_game(self):
        if self.game is None:
            self.draw_engine=LumaDrawEngine(ASSET_JSON_PATH)
            self.game=C12GameModel(self.draw_engine)
            self.game.ensure_safe_spawn('initial')
            self._log('C12 WORLD',f'{len(self.game.areas)} areas; '
                      f'{len(self.game.objects)} objects; {len(self.game.c1_npcs)} NPCs')
        super().start_game()
        self._set_status('C1.3: F1 game settings, F3 keyboard, I inventory, E use, F5/F9 save/load.')

    def _write_save(self,slot):
        g=self.game
        if not g:return
        try:
            data=g.snapshot()
            path=c12_save_path(slot)
            _write_json_atomically(path,data)
            self._log('SAVE',f'{slot} area={g.current_area_id} day={g.c1_day} '
                      f'objects={len(g.objects)} bytes={path.stat().st_size}')
            self._speech(f'Saved {slot} — {g.current_area.display_name}.')
        except Exception as exc:
            self._log('SAVE ERROR',f'{slot}: {type(exc).__name__}: {exc}')
            self._speech(f'Could not save {slot}: {exc}')

    def _read_save(self,slot):
        try:
            path=c12_save_path(slot)
            if not path.is_file():
                self._speech(f'No {slot} save exists yet.');return
            if path.stat().st_size>8_000_000:
                raise ValueError('Save file exceeds safety limit')
            with path.open('r',encoding='utf-8') as f:data=json.load(f)
            g=C131GameModel.from_snapshot(self.draw_engine,data)
            self.game=g  # Atomic game-world replacement only after all checks pass.
            self._log('LOAD',f'{slot} area={g.current_area_id} day={g.c1_day} '
                      f'objects={len(g.objects)} gold={g.c1_gold}')
            self._speech(f'Loaded {slot}: {g.current_area.display_name}, day {g.c1_day}.')
        except Exception as exc:
            self._log('LOAD ERROR',f'{slot}: {type(exc).__name__}: {exc}')
            self._speech(f'Could not load {slot}: {exc}')

    def _dialogue(self,speaker,line,options):
        g=self.game
        g.c1_dialogue={'speaker':speaker,'line':line,'options':options[:5]}
        g.c1_dialogue_selected=0
        self._log('DIALOGUE',f'{speaker}: {line[:115]} choices={len(options)}')

    def _talk_vendor(self,v):
        if v.get('vendor_id')!='kart_lotta':return super()._talk_vendor(v)
        g=self.game
        if g.c1_flags.get('lout_resolved') and 'kart_lotta' not in g.c1_permissions:
            outcome=g.c1_flags['lout_resolved']
            self._dialogue('Kart-lotta',
                'Oh, my hero! I could not charge YOU for my lovely veggies!',
                [{'text':'Thank you, Karlotta.','action':'kart_reward'}])
            return
        if 'kart_lotta' in g.c1_permissions:
            self._dialogue('Kart-lotta','My vegetables are yours, darling! They are absolutely lovely.',
                [{'text':'Thank you!','action':'close'}])
            return
        g.c1_flags['heard_kart']=True
        self._dialogue('Kart-lotta',
            'This twit in the inn keeps bothering me. I have no idea why!',
            [{'text':'I will see what I can do.','action':'close'},
             {'text':'Where can I find him?','action':'kart_hint'}])

    def _talk(self,n):
        if n.get('npc_id')!='inn_lout':return super()._talk(n)
        g=self.game
        if g.c1_flags.get('lout_resolved'):
            self._dialogue('Inn Lout','I told you I would leave her alone! Now go away.',
                           [{'text':'Good.','action':'close'}]);return
        if not g.c1_flags['heard_kart']:
            self._dialogue('Inn Lout','That vegetable seller is far too good for this dump!',
                           [{'text':'Right...','action':'close'}]);return
        if g.c1_flags.get('lout_challenged') and n.get('area_id')!='inn_interior':
            self._dialogue('Inn Lout','Well? You said you had something to say to me!',
                 [{'text':'I meant it. Leave Karlotta alone.','action':'lout_intimidate'},
                  {'text':'What will it take to make you leave her alone?','action':'lout_negotiate'},
                  {'text':'Never mind.','action':'close'}]);return
        self._dialogue('Inn Lout','What do YOU want, stranger?',
             [{'text':'Leave Karlotta alone, or else.','action':'lout_threat'},
              {'text':'What will it take to make you leave Karlotta alone?','action':'lout_negotiate'},
              {'text':'Nothing.','action':'close'}])

    def _choose_dialogue(self,index):
        g=self.game
        if not g or not g.c1_dialogue:return
        opts=g.c1_dialogue['options']
        if index<0 or index>=len(opts):return
        action=opts[index]['action']
        self._log('DIALOGUE CHOICE',f'{g.c1_dialogue["speaker"]}: {opts[index]["text"]} -> {action}')
        g.c1_dialogue=None
        if action=='kart_hint':
            self._dialogue('Kart-lotta','At the inn, dear. He practically lives there!',
                           [{'text':'I will find him.','action':'close'}])
        elif action=='kart_reward':
            g.c1_permissions.add('kart_lotta')
            g.c1_flags['lout_warned']=True
            self._speech('FRIENDSHIP! Karlotta\'s tomatoes and cabbages are GREEN / FREE to take.',8)
            self._log('QUEST',f'Karlotta befriended; lout={g.c1_flags["lout_resolved"]}; produce permission granted')
        elif action=='lout_threat':
            g.c1_flags['lout_challenged']=True
            g.c1_npcs['inn_lout']['follow_player']=True
            self._dialogue('Inn Lout','Step outside and say that!',
                           [{'text':'Fine. Follow me.','action':'close'}])
            self._log('QUEST','Inn lout challenged player to step outside')
        elif action=='lout_negotiate':
            g.c1_flags['lout_demand']=True
            got=g.c1_have(lambda o:o.kind=='mead' and 'black-briar' in o.name.lower())
            options=([{'text':'Here is your Black-Briar Mead.','action':'lout_pay'}] if got else [])
            options.append({'text':'I will find a bottle for you.','action':'close'})
            self._dialogue('Inn Lout','Bring me a bottle of Black-Briar Mead, and I will leave her alone.',options)
        elif action=='lout_pay':
            bottle=g.c1_have(lambda o:o.kind=='mead' and 'black-briar' in o.name.lower())
            if not bottle:self._speech('You need Black-Briar Mead first.');return
            g.c1_consume(bottle)
            self._resolve_lout('bribed')
            self._dialogue('Inn Lout','Fine! A deal is a deal. I will leave Karlotta alone.',
                           [{'text':'See that you do.','action':'close'}])
        elif action=='lout_intimidate':
            self._resolve_lout('intimidated')
            self._dialogue('Inn Lout','All right! All right! I will leave her alone!',
                           [{'text':'Good decision.','action':'close'}])

    def _resolve_lout(self,reason):
        g=self.game
        if g.c1_flags.get('lout_resolved'):return
        g.c1_flags['lout_resolved']=reason
        g.c1_flags['lout_warned']=True
        g.c1_npcs['inn_lout']['follow_player']=False
        self._log('QUEST',f'Karlotta problem resolved via {reason}')
        self._speech('Karlotta can hear the good news now.',5)

    def _area_enter(self,conn):
        super()._area_enter(conn)
        g=self.game
        lout=g.c1_npcs.get('inn_lout')
        if (lout and lout.get('alive',True) and lout.get('follow_player')
              and not g.c1_flags.get('lout_resolved')
              and conn.from_area_id==lout.get('area_id')
              and conn.to_area_id in ('inn_outside','britrun_market')):
            lout['area_id']=conn.to_area_id
            lout['x']=max(82,min(GAME_WIDTH-82,g.player_x+78))
            lout['y']=max(95,min(GAME_HEIGHT-80,g.player_y-16))
            self._log('NPC FOLLOW',f'Inn lout followed player into {conn.to_area_id} '
                      f'pos=({lout["x"]:.0f},{lout["y"]:.0f})')
            self._speech('Inn Lout: You wanted to say something? I am RIGHT HERE!',5)
        elif (lout and lout.get('follow_player') and not g.c1_flags.get('lout_resolved')
              and lout['area_id']=='inn_outside' and conn.to_area_id=='britrun_market'):
            lout['area_id']='britrun_market';lout['x']=g.player_x+80;lout['y']=g.player_y
            self._log('NPC FOLLOW','Inn lout continued pursuit into BritRun Market')

    def _take(self,obj):
        g=self.game
        if g and obj and g.close_to_object(obj) and g.is_unauthorized(obj):
            self._log('WITNESS DETAIL',f'player took {obj.name}; {g.witnessing_details(obj)}')
        return super()._take(obj)

    def _spawn_guard(self,target,source_obj,witness='vendor'):
        super()._spawn_guard(target,source_obj,witness)
        if target=='inn_lout':
            self._speech('Batguard: STOP RIGHT THERE, YOU CRIMINAL LOUT!',6)

    def _dispatch_game(self,event,ui):
        g=self.game
        if not g:return super()._dispatch_game(event,ui)
        if event.type==pygame.KEYDOWN:
            if g.c1_rebind:
                action=g.c1_rebind
                if event.key!=pygame.K_ESCAPE:
                    combo=c12_key_label(event)
                    self.c1_keys[action]=combo
                    self.config['keybinds']=dict(self.c1_keys)
                    err=self.persist_preference('keybinds',dict(self.c1_keys))
                    self._speech(f'{KEY_LABELS[action]}: {combo.upper()}' if not err else f'Bind save failed: {err}')
                    self._log('KEYBIND',f'{action}={combo}')
                g.c1_rebind=None
                return
            if g.c1_dialogue:
                if event.key==pygame.K_ESCAPE:g.c1_dialogue=None;return
                if event.key in (pygame.K_UP,pygame.K_w):
                    g.c1_dialogue_selected=(g.c1_dialogue_selected-1)%len(g.c1_dialogue['options']);return
                if event.key in (pygame.K_DOWN,pygame.K_s):
                    g.c1_dialogue_selected=(g.c1_dialogue_selected+1)%len(g.c1_dialogue['options']);return
                if event.key in (pygame.K_RETURN,pygame.K_SPACE):
                    self._choose_dialogue(g.c1_dialogue_selected);return
                if pygame.K_1<=event.key<=pygame.K_5:
                    self._choose_dialogue(event.key-pygame.K_1);return
                return
            if g.c1_save_panel:
                if event.key==pygame.K_ESCAPE or c12_binding_matches(event,self.c1_keys['save_menu']):
                    g.c1_save_panel=False;return
                if c12_binding_matches(event,self.c1_keys['quicksave']):
                    g.c1_save_panel=False;self._write_save('quick');return
                if c12_binding_matches(event,self.c1_keys['quickload']):
                    self._read_save('quick');self.game.c1_save_panel=False;return
                return
            if c12_binding_matches(event,self.c1_keys['quicksave']):
                self._write_save('quick');return
            if c12_binding_matches(event,self.c1_keys['quickload']):
                self._read_save('quick');return
            if c12_binding_matches(event,self.c1_keys['save_menu']):
                g.c1_save_panel=True;return
            if c12_binding_matches(event,self.c1_keys['config']):
                g.c1_config_open=not g.c1_config_open
                self._speech('Keyboard configuration: click a row then press the new chord.'
                             if g.c1_config_open else 'Configuration closed.')
                return
            if c12_binding_matches(event,self.c1_keys['screenshot']):
                ui.save_screenshot(self);return
            if (pygame.key.get_mods() & pygame.KMOD_CTRL and event.key==pygame.K_s):
                # Backward compatible with C1 screenshots only if bound to CTRL+S.
                if self.c1_keys['screenshot']=='ctrl+s':ui.save_screenshot(self)
                return
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            pt=ui.screen_to_game(event.pos)
            if pt and g.c1_config_open:
                for i,action in enumerate(DEFAULT_KEYS):
                    if pygame.Rect(355,65+i*28,570,26).collidepoint(pt):
                        g.c1_rebind=action
                        self._speech(f'Press a key or chord for {KEY_LABELS[action]}...')
                        return
                return
            if pt and g.c1_dialogue:
                for i in range(len(g.c1_dialogue['options'])):
                    rr=pygame.Rect(260,335+i*43,760,37)
                    if rr.collidepoint(pt):self._choose_dialogue(i);break
                return
            if pt and g.c1_save_panel:
                for i,slot in enumerate(SAVE_SLOTS):
                    y=195+i*77
                    if pygame.Rect(680,y,144,47).collidepoint(pt):
                        g.c1_save_panel=False;self._write_save(slot);return
                    if pygame.Rect(843,y,144,47).collidepoint(pt):
                        self._read_save(slot);self.game.c1_save_panel=False;return
                return
        return super()._dispatch_game(event,ui)

    def update(self,elapsed_seconds,ui):
        if self.game and (self.game.c1_dialogue or self.game.c1_save_panel):
            return  # UI modal: pause gameplay until choice is made.
        return super().update(elapsed_seconds,ui)

    def _npc_tick(self,dt):
        g=self.game
        # Each opportunist has the same pickup/witness rules, independent of quests.
        for nid in ('naz','inn_lout'):
            n=g.c1_npcs.get(nid)
            if not n or not n.get('alive',True) or n['area_id']!=g.current_area_id:continue
            if nid=='inn_lout' and n.get('follow_player') and not g.c1_flags.get('lout_resolved'):
                dx=g.player_x-n['x'];dy=g.player_y-n['y'];dist=math.hypot(dx,dy)
                if dist>105:
                    pace=min(95*dt,dist-105)
                    n['x']+=dx/dist*pace;n['y']+=dy/dist*pace
            if g.current_area_id=='britrun_market':
                valuables=[o for o in g.live_objects() if o.kind in ('gold','gold_pile')
                           and o.moved and not o.in_inventory and o.object_id!=g.carried_object_id]
                valuables.sort(key=lambda o:math.hypot(o.x-n['x'],o.y-n['y']))
                item=(next((o for o in valuables if abs(o.x-n['x'])<260),None)
                      if nid=='naz' else
                      next((o for o in valuables if math.hypot(o.x+o.width/2-n['x'],o.y+o.height/2-n['y'])<275),None))
                if item:
                    destx=item.x+item.width/2;desty=item.y+item.height/2
                    dx=destx-n['x'];dy=desty-n['y'];dist=math.hypot(dx,dy)
                    if (abs(dx)>31 if nid=='naz' else dist>30):
                        if nid=='naz':
                            n['x']+=max(-72*dt,min(72*dt,dx))
                        else:
                            step=min(83*dt,dist-30)
                            n['x']+=dx/dist*step;n['y']+=dy/dist*step
                    else:
                        illegal=g.is_unauthorized(item)
                        guard_saw=bool(illegal and g.guard_sees(item))
                        vendor_saw=bool(illegal and g.is_vendor_watching(item))
                        detail=g.witnessing_details(item)
                        item.area_id='__consumed__';n['holding']=item.name
                        self._log('NPC ACTION',f'{n["name"]} took {item.name}; stolen={illegal} '
                                  f'guard_saw={guard_saw} vendor_saw={vendor_saw}; {detail}')
                        if guard_saw:self._spawn_guard(nid,item,witness='guard')
                        elif vendor_saw:self._spawn_guard(nid,item,witness='vendor')
                        else:g.c1_say(n['name']+': Finders keepers!',4)
                elif nid=='naz':
                    n['x']=min(1110,max(555,n['x']+math.sin(g.c1_elapsed*.75)*35*dt))
            if nid=='naz' and g.current_area_id=='britrun_market' and g.c1_elapsed>g.c1_naz_lines_at+13:
                g.c1_naz_lines_at=g.c1_elapsed
                g.c1_say(self.c1_rng.choice(n.get('lines',['I am important!'])),4)
        guard=g.c1_guard
        if guard and guard['area_id']==g.current_area_id and g.c1_guard_target:
            target_id=g.c1_guard_target
            if target_id=='player':tx,ty=g.player_x,g.player_y
            else:
                target=g.c1_npcs.get(target_id)
                if not target or not target.get('alive',True):
                    g.c1_guard_target=None;return
                tx,ty=target['x'],target['y']
            dx=tx-guard['x'];dy=ty-guard['y'];dist=math.hypot(dx,dy)
            if dist>1:
                speed=330 if target_id=='player' else 370
                step=min(speed*dt,dist)
                guard['x']+=dx/dist*step;guard['y']+=dy/dist*step
            if dist<52:
                if target_id=='player':self._die('Caught by a guard after witnessed theft!')
                else:
                    target=g.c1_npcs.get(target_id)
                    target['alive']=False
                    g.c1_guard_target=None
                    if target_id=='naz':
                        self._speech('Guard: I have been waiting YEARS for him to do that!',7)
                    else:
                        self._resolve_lout('dead')
                        self._speech('BATGUARD: Criminal scum! Karlotta is safe now.',7)
                    self._log('NPC DEATH',f'{target["name"]} killed by guard for observed theft')
        if g.current_area_id=='troll_cave' and g.c1_troll_angry:
            troll=g.c1_npcs.get('troll')
            if troll:
                dx=g.player_x-troll['x'];dy=g.player_y-troll['y'];dist=math.hypot(dx,dy)
                if dist>1:
                    step=min(330*dt,dist)  # Frosty: 1.5 times the 220 px/s unboosted player
                    troll['x']+=dx/dist*step;troll['y']+=dy/dist*step
                if dist<67:self._die('Frosty the Trollman gives you a warm welcome with his claws!')


class C12Interface(C11Interface):
    def _draw_game_scene(self,surface,g):
        super()._draw_game_scene(surface,g)
        if g.c1_save_panel:self._draw_save_panel(surface)
        if g.c1_dialogue:self._draw_dialogue_panel(surface,g)

    def _draw_dialogue_panel(self,surface,g):
        info=g.c1_dialogue
        shade=pygame.Surface((GAME_WIDTH,GAME_HEIGHT),pygame.SRCALPHA)
        shade.fill((0,0,0,128));surface.blit(shade,(0,0))
        rr=pygame.Rect(213,115,853,440)
        pygame.draw.rect(surface,(26,22,35),rr,border_radius=12)
        pygame.draw.rect(surface,(233,190,113),rr,3,border_radius=12)
        self._c1_text(surface,info['speaker'].upper(),254,146,(255,218,152),self.game_font,760)
        self._c1_wrapped(surface,info['line'],254,207,750,(248,235,206))
        for i,option in enumerate(info['options']):
            row=pygame.Rect(260,335+i*43,760,37)
            pygame.draw.rect(surface,(88,64,78) if i==g.c1_dialogue_selected else (48,43,55),row,border_radius=5)
            pygame.draw.rect(surface,(230,184,110) if i==g.c1_dialogue_selected else (101,90,105),row,2,border_radius=5)
            self._c1_text(surface,f'{i+1}. {option["text"]}',276,row.y+7,(254,242,215),self.game_small_font,710)
        self._c1_text(surface,'1–5 / UP-DOWN + ENTER to choose   •   ESC to leave',254,521,(203,193,178),self.game_small_font,700)

    def _draw_save_panel(self,surface):
        shade=pygame.Surface((GAME_WIDTH,GAME_HEIGHT),pygame.SRCALPHA)
        shade.fill((0,0,0,145));surface.blit(shade,(0,0))
        rr=pygame.Rect(263,106,754,444)
        pygame.draw.rect(surface,(22,23,32),rr,border_radius=12)
        pygame.draw.rect(surface,(226,178,103),rr,3,border_radius=12)
        self._c1_text(surface,'SAVE / LOAD GAME',298,127,(254,228,170),self.game_font,630)
        self._c1_text(surface,'Quick: F5 save, F9 load. F6 / Esc closes.',298,163,(216,206,192),self.game_small_font,620)
        for i,slot in enumerate(SAVE_SLOTS):
            y=195+i*77
            p=c12_save_path(slot)
            state=('SAVED' if p.exists() else 'EMPTY')
            self._c1_text(surface,f'{slot.upper()}   [{state}]',298,y+12,(238,227,211),self.game_small_font,363)
            for title,x,color in [('SAVE',680,(78,94,67)),('LOAD',843,(75,72,96))]:
                btn=pygame.Rect(x,y,144,47)
                pygame.draw.rect(surface,color,btn,border_radius=5)
                pygame.draw.rect(surface,(208,182,121),btn,2,border_radius=5)
                self._c1_text(surface,title,x+33,y+11,(250,235,203),self.game_small_font,95)

    def _c1_config_dialog(self,surface,g):
        # C1.2 has 19 mappings; keep every key visible and clickable.
        rr=pygame.Rect(331,22,618,591)
        pygame.draw.rect(surface,(25,22,29),rr,border_radius=8)
        pygame.draw.rect(surface,(214,169,101),rr,3,border_radius=8)
        self._c1_text(surface,'CONFIGURE KEYS — ESC TO CLOSE',355,32,(254,223,169),self.game_font,560)
        for i,action in enumerate(DEFAULT_KEYS):
            row=pygame.Rect(355,65+i*28,570,26)
            bg=(107,73,69) if g.c1_rebind==action else ((51,47,58) if i%2==0 else (42,37,47))
            pygame.draw.rect(surface,bg,row,border_radius=3)
            self._c1_text(surface,KEY_LABELS[action],369,row.y+4,(239,229,202),self.game_small_font,388)
            self._c1_text(surface,self.machine.c1_keys[action].upper(),789,row.y+4,(145,244,169),self.game_small_font,126)
        self._c1_text(surface,'Click a row, then press a key or CTRL+S, etc.',355,599,(216,203,178),self.game_small_font,565)


# ---------------------------------------------------------------------------
# C1.3 — cooking, accessible game settings, and Frosty's mountain-side cave
# ---------------------------------------------------------------------------

C13_RECIPES = (
    ('Spaghetti Sauce', 'sauce', {'tomato': 2}, 30),
    ('Coleslaw', 'coleslaw', {'cabbage': 2}, 30),
    ('Not-So-Tasty Soup', 'soup', {'tomato': 2, 'cabbage': 2}, 55),
)
C13_EDIBLE = {'sauce', 'coleslaw', 'soup'}
C13_SLIDER_TRACKS = ((445, 280, 390, 15), (445, 420, 390, 15))
C13_GAME_CLOSE = (853, 118, 59, 40)
C13_COOK_ROWS = tuple((274, 270 + i * 75, 730, 67) for i in range(3))


class C13GameModel(C12GameModel):
    """C1.2 world and snapshots with transient C1.3 interaction panels."""
    def __init__(self, engine):
        super().__init__(engine)
        self.c13_game_config_open = False
        self.c13_cooking_open = False
        self.c13_recipe_selected = 0
        self.c13_slider_selected = 0
        self.c13_slider_dragging = False

    def hit_test(self, point):
        # C1.2 hit tests excluded non-takeable workstations; E and clicks
        # should both recognize the cooking pot and the hearth.
        if point is not None:
            for obj in reversed(self.live_objects()):
                if (obj.rect().collidepoint(point) and
                    (obj.takeable or obj.kind in ('door', 'path', 'portal', 'cookpot', 'hearth'))):
                    return obj
        return None

    def inventory_eat_rect(self):
        return pygame.Rect(1101, 462, 135, 38)

    @classmethod
    def from_snapshot(cls, engine, data):
        # A C1.2 save predates the mountain-side entrance and hearth. Add only
        # missing *new* core objects, leaving saved inventories/quests untouched.
        if isinstance(data, dict) and data.get('schema') == SAVE_SCHEMA and isinstance(data.get('objects'), list):
            data = dict(data)
            data['objects'] = list(data['objects'])
            existing = {o.get('object_id') for o in data['objects'] if isinstance(o, dict)}
            for spec in engine.world['objects']:
                if spec['object_id'] not in existing and spec['object_id'] in ('inn_hearth_c13', 'mountain_cave_entrance'):
                    obj = GameObject(spec['object_id'], spec.get('name', spec['object_id']),
                        spec['kind'], spec['area_id'], float(spec['x']), float(spec['y']),
                        int(spec['width']), int(spec['height']),
                        bool(spec.get('takeable', True)), bool(spec.get('stealable', True)),
                        False, False, bool(spec.get('on_shelf', False)))
                    from dataclasses import asdict
                    data['objects'].append(asdict(obj))
            if isinstance(data.get('item_meta'), dict):
                data['item_meta'] = dict(data['item_meta'])
                for spec in engine.world['objects']:
                    if spec['object_id'] in ('inn_hearth_c13', 'mountain_cave_entrance'):
                        data['item_meta'].setdefault(spec['object_id'], dict(spec))
        model = super().from_snapshot(engine, data)
        if data.get('source_version') not in ('C1.3', 'C1.3.1'):
            # C1.2 saves placed the innkeeper where the new hearth now burns,
            # and Frosty in a location that defeats even a soup-speed runner.
            keeper = model.c1_npcs.get('innkeeper')
            if keeper and keeper.get('x') == 343 and keeper.get('y') == 257:
                keeper['x'] = 510
            troll = model.c1_npcs.get('troll')
            if troll and not model.c1_troll_angry and troll.get('x') == 750 and troll.get('y') == 303:
                troll['x'], troll['y'] = 560, 180
                troll['name'] = 'Frosty the Ice Troll'
        model.c13_game_config_open = False
        model.c13_cooking_open = False
        model.c13_slider_dragging = False
        return model


class C13StateMachine(C12StateMachine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.soup_speed_multiplier = float(self.config.get('soup_speed_multiplier', 2.0))
        self.soup_effect_seconds = int(self.config.get('soup_effect_seconds', 20))
        self._log('GAME CONFIG', f'soup_multiplier={self.soup_speed_multiplier:.1f} '
                               f'soup_seconds={self.soup_effect_seconds}')

    def start_game(self):
        if self.game is None:
            self.draw_engine = LumaDrawEngine(ASSET_JSON_PATH)
            self.game = C13GameModel(self.draw_engine)
            self.game.ensure_safe_spawn('initial')
            self._log('C13 WORLD', f'{len(self.game.areas)} areas; '
                      f'{len(self.game.objects)} objects; {len(self.game.c1_npcs)} NPCs')
        super().start_game()

    def _cook(self):
        g = self.game
        if not g or g.c1_dead:return
        g.inventory_open = False
        g.c13_cooking_open = True
        g.c13_recipe_selected = 0
        self._log('COOK MENU', f'Opened at {g.current_area_id}')
        self._speech('INN COOKPOT: choose a recipe; unavailable recipes show missing vegetables.')

    def _recipe_counts(self):
        counts = {'tomato': 0, 'cabbage': 0}
        for oid in self.game.inventory:
            obj = self.game.object_by_id(oid)
            if obj and obj.kind in counts:counts[obj.kind] += 1
        return counts

    def _craft_recipe(self, index):
        if not 0 <= index < len(C13_RECIPES):return
        g = self.game
        name, kind, needed, price = C13_RECIPES[index]
        counts = self._recipe_counts()
        missing = [f'{amount-counts[item]} {item}' for item, amount in needed.items()
                   if counts[item] < amount]
        if missing:
            self._speech(f'Cannot make {name}: need '+', '.join(missing)+'.')
            self._log('COOK', f'Unavailable {name}; {missing}')
            return
        consumed = []
        for ingredient, amount in needed.items():
            matches = [g.object_by_id(oid) for oid in list(g.inventory)]
            matches = [o for o in matches if o is not None and o.kind == ingredient]
            consumed.extend(matches[:amount])
        for obj in consumed:g.c1_consume(obj)
        cooked = g.c1_make_item(name, kind, price=price)
        self._log('CRAFT', f'{name} from '+', '.join(f'{n} {k}' for k,n in needed.items())+
                           f'; item={cooked.object_id}')
        self._speech(f'Cooked {name}! Check inventory (I) to EAT or DROP it.', 6)
        g.c13_cooking_open = False

    def _use_nearest(self, ui):
        # C1.2 would always talk to the innkeeper before checking the cookpot.
        # Choose whichever interactive target is physically closer instead.
        g = self.game
        if g and g.current_area_id == 'inn_interior':
            stations = [g.object_by_id(oid) for oid in ('inn_cookpot','inn_hearth_c13')]
            stations = [o for o in stations if o is not None and o.area_id==g.current_area_id]
            if stations:
                pot = min(stations,key=lambda o:math.hypot(g.player_x-o.x-o.width/2,
                                                          g.player_y-o.y-o.height/2))
                pot_dist = math.hypot(g.player_x-pot.x-pot.width/2,
                                      g.player_y-pot.y-pot.height/2)
                npc = g.c1_nearest_npc(150)
                npc_dist = (math.hypot(g.player_x-npc['x'],g.player_y-npc['y'])
                            if npc else float('inf'))
                if pot_dist < npc_dist and g.close_to_object(pot):
                    self._activate(pot);return
        return super()._use_nearest(ui)

    def _mouse_game(self, event, ui):
        # C1.2 already wakes Frosty as soon as the pineapple is clicked/carried.
        # Mark that pickup in quest state as well, so a death can reliably reset
        # the pineapple even if it was never transferred to the inventory.
        g = self.game
        before = bool(g and g.c1_flags.get('pineapple_taken'))
        super()._mouse_game(event, ui)
        if g and not before and g.carried_object_id == 'purple_passion_pineapple':
            g.c1_flags['pineapple_taken'] = True
            self._log('TROLL', 'Frosty awakened when player picked up the pineapple')

    def _respawn(self):
        super()._respawn()
        g = self.game
        if not g:return
        # Each attempt starts with Frosty at his known home position, not where
        # he ended the preceding pursuit near the cave's exit.
        troll = g.c1_npcs.get('troll')
        original = next((n for n in self.draw_engine.world['npcs'] if n['npc_id']=='troll'), None)
        if troll and original:
            troll['x'], troll['y'] = float(original['x']), float(original['y'])
            troll['alive'] = True

    def _eat(self):
        g = self.game
        if not g or g.c1_dead:return
        obj = g.object_by_id(g.inventory_selected_id) if g.inventory_open else None
        if obj is None or obj.object_id not in g.inventory:
            obj = g.c1_have(lambda o:o.kind in C13_EDIBLE)
        if obj is None:
            self._speech('No cooked food available. Try the inn hearth and cooking pot.');return
        if obj.kind not in C13_EDIBLE:
            self._speech(f'{obj.name} is not something you can eat.');return
        g.c1_consume(obj)
        if obj.kind == 'soup':
            # One bowl is enough: no stack requirement, no hidden two-soup rule.
            g.c1_soup_stacks = 1
            g.c1_soup_seconds = float(self.soup_effect_seconds)
            self._speech(f'NOT-SO-TASTY SOUP! {self.soup_speed_multiplier:.1f}x speed '
                         f'for {self.soup_effect_seconds}s! RUN!', 6)
            self._log('SOUP', f'ate={obj.name}; multiplier={self.soup_speed_multiplier:.1f}; '
                              f'duration={self.soup_effect_seconds}; area={g.current_area_id}')
        else:
            self._speech(f'Ate {obj.name}. Delicious, but no running-speed bonus.')
            self._log('FOOD', f'ate={obj.name}; no speed effect')

    def _adjust_game_slider(self, slot, value):
        slot = max(0, min(1, int(slot)))
        key = 'soup_speed_multiplier' if slot == 0 else 'soup_effect_seconds'
        if slot == 0:
            value = round(min(4., max(1., float(value))), 1)
        else:
            value = round(min(90, max(5, int(round(value)))))
        if getattr(self, key) == value:return
        error = self.persist_preference(key, value)
        if error:
            self._speech(f'Cannot save game setting: {error}')
            return
        setattr(self, key, value)
        self._log('GAME CONFIG', f'{key}={value}')

    def _set_slider_from_pointer(self, position, ui):
        pt = ui.screen_to_game(position)
        if pt is None:return
        g = self.game
        slot = g.c13_slider_selected
        x,y,w,h = C13_SLIDER_TRACKS[slot]
        t = max(0., min(1., (pt[0]-x)/w))
        value = (1. + 3.*t) if slot == 0 else (5 + 85*t)
        self._adjust_game_slider(slot, value)

    def _dispatch_game(self, event, ui):
        g = self.game
        if not g:return super()._dispatch_game(event, ui)
        if g.c13_game_config_open:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or c12_binding_matches(event,self.c1_keys['game_config']):
                    g.c13_game_config_open = False;g.c13_slider_dragging=False;return
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    g.c13_slider_selected = 1-g.c13_slider_selected;return
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    d = 1 if event.key==pygame.K_RIGHT else -1
                    slot=g.c13_slider_selected
                    current=self.soup_speed_multiplier if slot==0 else self.soup_effect_seconds
                    self._adjust_game_slider(slot, current + d*(0.1 if slot==0 else 1));return
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button==1:
                pt=ui.screen_to_game(event.pos)
                if pt and pygame.Rect(C13_GAME_CLOSE).collidepoint(pt):
                    g.c13_game_config_open=False;g.c13_slider_dragging=False;return
                if pt:
                    for i,(x,y,w,h) in enumerate(C13_SLIDER_TRACKS):
                        if pygame.Rect(x-18,y-28,w+36,60).collidepoint(pt):
                            g.c13_slider_selected=i;g.c13_slider_dragging=True
                            self._set_slider_from_pointer(event.pos,ui);return
                return
            if event.type == pygame.MOUSEMOTION and g.c13_slider_dragging:
                self._set_slider_from_pointer(event.pos,ui);return
            if event.type == pygame.MOUSEBUTTONUP and event.button==1:
                g.c13_slider_dragging=False;return
            return
        if g.c13_cooking_open:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    g.c13_cooking_open=False;return
                if event.key in (pygame.K_UP,pygame.K_w):
                    g.c13_recipe_selected=(g.c13_recipe_selected-1)%len(C13_RECIPES);return
                if event.key in (pygame.K_DOWN,pygame.K_s):
                    g.c13_recipe_selected=(g.c13_recipe_selected+1)%len(C13_RECIPES);return
                if event.key in (pygame.K_RETURN,pygame.K_SPACE):
                    self._craft_recipe(g.c13_recipe_selected);return
                if pygame.K_1<=event.key<=pygame.K_3:
                    self._craft_recipe(event.key-pygame.K_1);return
                return
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                pt=ui.screen_to_game(event.pos)
                if pt:
                    for i,rr in enumerate(C13_COOK_ROWS):
                        if pygame.Rect(rr).collidepoint(pt):
                            g.c13_recipe_selected=i;self._craft_recipe(i);return
                    if pygame.Rect(980,155,56,37).collidepoint(pt):g.c13_cooking_open=False
                return
            return
        # C1.3's F1 game-config action is independent of F3 keyboard settings.
        if event.type == pygame.KEYDOWN and not g.c1_rebind and not g.c1_config_open:
            if c12_binding_matches(event, self.c1_keys['game_config']):
                if not g.c1_dead and not g.c1_dialogue and not g.c1_save_panel:
                    g.c13_game_config_open=True
                    g.c13_slider_selected=0
                    g.inventory_open=False
                    self._log('GAME CONFIG','Opened F1 sliders')
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pt = ui.screen_to_game(event.pos)
            if pt and g.c1_config_open:
                for i,action in enumerate(DEFAULT_KEYS):
                    if pygame.Rect(355,58+i*27,570,25).collidepoint(pt):
                        g.c1_rebind=action
                        self._speech(f'Press a key or chord for {KEY_LABELS[action]}...')
                        return
                return
            if pt and g.inventory_open and g.inventory_eat_rect().collidepoint(pt):
                self._eat();return
        return super()._dispatch_game(event, ui)

    def update(self, elapsed_seconds, ui):
        g = self.game
        # Preserve time to read menus, select dinner, or change settings.
        if g and (g.c13_game_config_open or g.c13_cooking_open or g.inventory_open or g.c1_config_open):
            return
        return super().update(elapsed_seconds, ui)


class C13Interface(C12Interface):
    def _draw_game_scene(self, surface, g):
        super()._draw_game_scene(surface, g)
        if g.inventory_open:
            eat=g.inventory_eat_rect()
            pygame.draw.rect(surface,(65,87,59),eat,border_radius=6)
            pygame.draw.rect(surface,(161,218,143),eat,2,border_radius=6)
            font=self.game_small_font
            label=font.render('EAT ITEM',True,(238,252,227))
            surface.blit(label,label.get_rect(center=eat.center))
        if g.c13_cooking_open:self._draw_c13_cooking(surface,g)
        if g.c13_game_config_open:self._draw_c13_game_config(surface,g)

    def _c1_config_dialog(self,surface,g):
        # 20 remappable actions, including F1 game settings. All fit within 640 px.
        rr=pygame.Rect(331,12,618,614)
        pygame.draw.rect(surface,(25,22,29),rr,border_radius=8)
        pygame.draw.rect(surface,(214,169,101),rr,3,border_radius=8)
        self._c1_text(surface,'CONFIGURE KEYS — ESC TO CLOSE',355,22,(254,223,169),self.game_font,560)
        for i,action in enumerate(DEFAULT_KEYS):
            row=pygame.Rect(355,58+i*27,570,25)
            bg=(107,73,69) if g.c1_rebind==action else ((51,47,58) if i%2==0 else (42,37,47))
            pygame.draw.rect(surface,bg,row,border_radius=3)
            self._c1_text(surface,KEY_LABELS[action],369,row.y+3,(239,229,202),self.game_small_font,378)
            self._c1_text(surface,self.machine.c1_keys[action].upper(),789,row.y+3,(145,244,169),self.game_small_font,126)
        self._c1_text(surface,'Click a row, then press the replacement key/chord.',355,606,(216,203,178),self.game_small_font,565)

    def _draw_c13_game_config(self,surface,g):
        shade=pygame.Surface((GAME_WIDTH,GAME_HEIGHT),pygame.SRCALPHA)
        shade.fill((0,0,0,153));surface.blit(shade,(0,0))
        rr=pygame.Rect(310,95,660,442)
        pygame.draw.rect(surface,(25,24,33),rr,border_radius=13)
        pygame.draw.rect(surface,(231,181,117),rr,3,border_radius=13)
        self._c1_text(surface,'GAME CONFIGURATION',348,119,(255,226,166),self.game_font,482)
        close=pygame.Rect(C13_GAME_CLOSE)
        pygame.draw.rect(surface,(100,58,58),close,border_radius=6)
        self._c1_text(surface,'CLOSE',close.x+6,close.y+11,(255,232,213),self.game_small_font,53)
        values=(self.machine.soup_speed_multiplier,self.machine.soup_effect_seconds)
        labels=('Soup speed multiplier','Soup effect duration')
        displays=(f'{values[0]:.1f}x normal speed',f'{values[1]} seconds')
        for i,(x,y,w,h) in enumerate(C13_SLIDER_TRACKS):
            self._c1_text(surface,labels[i],x,y-68,(248,228,191),self.game_font,370)
            self._c1_text(surface,displays[i],x,y-37,(162,244,183),self.game_small_font,390)
            pygame.draw.rect(surface,(73,67,78),(x,y,w,h),border_radius=6)
            t=((values[i]-1.)/3.) if i==0 else ((values[i]-5)/85.)
            pygame.draw.rect(surface,(148,206,132),(x,y,max(5,round(w*t)),h),border_radius=6)
            knob=pygame.Rect(round(x+w*t)-10,y-7,20,29)
            pygame.draw.rect(surface,(247,213,146),knob,border_radius=5)
            if i==g.c13_slider_selected:
                pygame.draw.rect(surface,(255,255,242),knob,2,border_radius=5)
        self._c1_text(surface,'Click or drag sliders; arrows fine-tune; ESC or F1 closes.',351,489,(225,216,204),self.game_small_font,571)

    def _draw_c13_cooking(self,surface,g):
        shade=pygame.Surface((GAME_WIDTH,GAME_HEIGHT),pygame.SRCALPHA)
        shade.fill((0,0,0,147));surface.blit(shade,(0,0))
        rr=pygame.Rect(224,135,832,391)
        pygame.draw.rect(surface,(33,25,25),rr,border_radius=12)
        pygame.draw.rect(surface,(235,180,104),rr,3,border_radius=12)
        self._c1_text(surface,'INN HEARTH — COOKING POT',262,157,(255,222,156),self.game_font,710)
        counts=self.machine._recipe_counts()
        self._c1_text(surface,f'IN YOUR PACK: {counts["tomato"]} TOMATOES  /  {counts["cabbage"]} CABBAGES',
                      263,209,(199,244,187),self.game_small_font,720)
        for i,(name,kind,needed,price) in enumerate(C13_RECIPES):
            rr=pygame.Rect(C13_COOK_ROWS[i])
            possible=all(counts.get(ingredient,0)>=amount for ingredient,amount in needed.items())
            pygame.draw.rect(surface,(76,74,49) if i==g.c13_recipe_selected else (51,45,48),rr,border_radius=7)
            pygame.draw.rect(surface,(228,185,110) if possible else (107,100,102),rr,2,border_radius=7)
            self._c1_text(surface,f'{i+1}. {name}',rr.x+15,rr.y+9,
                          (253,234,178) if possible else (173,165,164),self.game_font,520)
            desc=' + '.join(f'{count} {ingredient}' for ingredient,count in needed.items())
            self._c1_text(surface,desc+'  •  '+('READY' if possible else 'NOT ENOUGH'),rr.x+16,rr.y+41,
                          (166,244,165) if possible else (236,143,133),self.game_small_font,668)
        self._c1_text(surface,'Click recipe or press 1–3. ESC closes.',262,498,(232,222,197),self.game_small_font,630)
        pygame.draw.rect(surface,(100,58,58),(980,155,56,37),border_radius=5)
        self._c1_text(surface,'X',1001,162,(255,227,207),self.game_font,30)



# ---------------------------------------------------------------------------
# C1.3.1 — Kitty Caravan scout, discoverable workstations and configurable
#           hidden chest, repeatable alchemy. Complete standalone release.
# ---------------------------------------------------------------------------

C131_SLIDER_TRACKS = ((445, 239, 390, 15), (445, 341, 390, 15),
                      (445, 443, 390, 15))


class C131GameModel(C13GameModel):
    """Workstations are first-class interactive world objects, not decoration."""
    def __init__(self, engine):
        super().__init__(engine)
        self.c131_chest_hitbox_scale = 2.0  # configurable, not serialized in save slots

    def chest_hover_rect(self):
        chest = self.object_by_id('stable_caravan_chest')
        if chest is None or chest.area_id != self.current_area_id or chest.in_inventory:
            return None
        r = chest.rect()
        scale = max(1., min(5., float(self.c131_chest_hitbox_scale)))
        # Scale *both* dimensions around the true chest center; don't move its hitbox.
        return pygame.Rect(round(r.centerx - r.width*scale/2),
                           round(r.centery - r.height*scale/2),
                           max(1, round(r.width*scale)),
                           max(1, round(r.height*scale)))

    def hit_test(self, point):
        if point is None:return None
        # Enlarged invisible discovery zone is limited strictly to this chest.
        if self.current_area_id == 'stables':
            box = self.chest_hover_rect()
            if box is not None and box.collidepoint(point):
                return self.object_by_id('stable_caravan_chest')
        for obj in reversed(self.live_objects()):
            if obj.rect().collidepoint(point) and (obj.takeable or obj.kind in
                    ('door','path','portal','cookpot','hearth','alchemy_table','book','chest')):
                return obj
        return None

    @classmethod
    def from_snapshot(cls, engine, data):
        model = super().from_snapshot(engine, data)
        model.c131_chest_hitbox_scale = 2.0
        return model


class C131StateMachine(C13StateMachine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hidden_chest_hitbox_scale = float(self.config.get('hidden_chest_hitbox_scale', 2.0))
        self._log('GAME CONFIG', f'hidden_chest_hitbox_scale={self.hidden_chest_hitbox_scale:.2f}')

    def start_game(self):
        if self.game is None:
            self.draw_engine = LumaDrawEngine(ASSET_JSON_PATH)
            self.game = C131GameModel(self.draw_engine)
            self.game.ensure_safe_spawn('initial')
            self._log('C131 WORLD', f'{len(self.game.areas)} areas; '
                      f'{len(self.game.objects)} objects; {len(self.game.c1_npcs)} NPCs')
        self.game.c131_chest_hitbox_scale = self.hidden_chest_hitbox_scale
        super().start_game()
        self._set_status('C1.3.1: Kitty Caravan, alchemy tooltips, repeatable brewing, F1 chest slider.')

    def _read_save(self, slot):
        # Parent's slot loader uses C131GameModel (above). Keep the F1 setting
        # across a load; game saves never overwrite user-wide hitbox preferences.
        super()._read_save(slot)
        if isinstance(self.game, C131GameModel):
            self.game.c131_chest_hitbox_scale = self.hidden_chest_hitbox_scale

    def _alchemy(self):
        # A completed quest does not make the workstation cease to function.
        g = self.game
        pineapple = g.c1_have(lambda o: o.kind == 'pineapple')
        redroot = g.c1_have(lambda o: 'redroot' in o.name.lower())
        moonflower = g.c1_have(lambda o: 'moonflower' in o.name.lower())
        ingredients = [('Purple Passion Pineapple',pineapple),
                       ('Redroot',redroot),('Moonflower',moonflower)]
        missing = [name for name,item in ingredients if item is None]
        if missing:
            self._speech('ALCHEMY: missing ' + ', '.join(missing) +
                         '. Read the recipe book for ingredients.', 7)
            self._log('ALCHEMY',f'Missing ingredients: {missing}; quest_done={g.c1_flags.get("quest_done")}')
            return
        for item in (pineapple,redroot,moonflower):g.c1_consume(item)
        g.c1_make_item('Potion of Increased Physical Enhancement','potion',price=69000)
        if g.c1_flags.get('quest_done'):
            self._speech('SUCCESS! Another enhancement potion brewed! Fearmonger may be satisfied, '
                         'but BritRun alchemy has no quantity limit.',7)
        else:
            self._speech('SUCCESS! Crafted the Potion of Increased Physical Enhancement. '
                         'Take it to Fearmonger!',7)
        self._log('CRAFT','Enhancement potion: PPP + Redroot + Moonflower; '
                          f'quest_done={g.c1_flags.get("quest_done")}')

    def _c131_set_slider(self, slot, value):
        if slot < 2:
            self._adjust_game_slider(slot, value)
            return
        scale = round(min(5., max(1., float(value))), 2)
        if scale == self.hidden_chest_hitbox_scale:return
        error = self.persist_preference('hidden_chest_hitbox_scale', scale)
        if error:
            self._speech(f'Cannot save chest hitbox setting: {error}')
            return
        self.hidden_chest_hitbox_scale = scale
        if isinstance(self.game,C131GameModel):
            self.game.c131_chest_hitbox_scale = scale
        self._log('GAME CONFIG', f'hidden_chest_hitbox_scale={scale:.2f}')

    def _c131_slider_at_pointer(self, pos, ui):
        pt=ui.screen_to_game(pos)
        if pt is None:return
        g=self.game
        slot=g.c13_slider_selected
        x,y,w,h=C131_SLIDER_TRACKS[slot]
        t=max(0.,min(1.,(pt[0]-x)/w))
        value=(1.+3.*t) if slot==0 else ((5.+85.*t) if slot==1 else (1.+4.*t))
        self._c131_set_slider(slot,value)

    def _dispatch_game(self, event, ui):
        g=self.game
        if g and g.c13_game_config_open:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or c12_binding_matches(event,self.c1_keys['game_config']):
                    g.c13_game_config_open=False;g.c13_slider_dragging=False;return
                if event.key in (pygame.K_UP,pygame.K_DOWN):
                    g.c13_slider_selected=(g.c13_slider_selected +
                            (-1 if event.key==pygame.K_UP else 1))%3
                    return
                if event.key in (pygame.K_LEFT,pygame.K_RIGHT):
                    slot=g.c13_slider_selected
                    d=1 if event.key==pygame.K_RIGHT else -1
                    current=(self.soup_speed_multiplier,self.soup_effect_seconds,
                             self.hidden_chest_hitbox_scale)[slot]
                    step=(0.1,1,0.1)[slot]
                    self._c131_set_slider(slot,current+d*step)
                    return
                return
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                pt=ui.screen_to_game(event.pos)
                if pt is not None and pygame.Rect(C13_GAME_CLOSE).collidepoint(pt):
                    g.c13_game_config_open=False;g.c13_slider_dragging=False;return
                if pt is not None:
                    for i,(x,y,w,h) in enumerate(C131_SLIDER_TRACKS):
                        if pygame.Rect(x-18,y-21,w+36,53).collidepoint(pt):
                            g.c13_slider_selected=i
                            g.c13_slider_dragging=True
                            self._c131_slider_at_pointer(event.pos,ui)
                            return
                return
            if event.type==pygame.MOUSEMOTION and g.c13_slider_dragging:
                self._c131_slider_at_pointer(event.pos,ui);return
            if event.type==pygame.MOUSEBUTTONUP and event.button==1:
                g.c13_slider_dragging=False;return
            return
        return super()._dispatch_game(event,ui)


class C131Interface(C13Interface):
    """Animated JSON-painted tortoiseshell kitty patrols the exact chest site."""
    def _draw_game_scene(self, surface, g):
        super()._draw_game_scene(surface,g)
        if (g.current_area_id == 'stables' and not g.c1_dead and not g.c13_game_config_open
                and not g.inventory_open and not g.c1_config_open and not g.c1_save_panel
                and not g.c1_dialogue):
            self._draw_kitty_caravan(surface,g)
            # Kitty is painted on top of the world; restore chest hover label
            # above her silhouette so the interaction remains unambiguous.
            pointer=self.screen_to_game(pygame.mouse.get_pos())
            chest=g.object_by_id('stable_caravan_chest')
            if not getattr(self, 'd1_dedupe_tooltips', False) and chest and pointer is not None and g.hit_test(pointer) is chest and not (
                    g.c13_game_config_open or g.inventory_open or g.c1_config_open or g.c1_save_panel):
                text_surface=self.game_small_font.render('E: KITTY CARAVAN HIDDEN CHEST',True,(161,239,255))
                tx=max(8,min(GAME_WIDTH-text_surface.get_width()-12,pointer[0]+14))
                ty=max(52,min(GAME_HEIGHT-67,pointer[1]-37))
                rr=text_surface.get_rect(topleft=(tx,ty)).inflate(12,8)
                pygame.draw.rect(surface,(18,16,24),rr,border_radius=5)
                pygame.draw.rect(surface,(155,225,241),rr,1,border_radius=5)
                surface.blit(text_surface,(tx,ty))

    def _draw_kitty_caravan(self, surface, g):
        t=g.c1_elapsed%12.
        if t < 4:
            x=1096.+(128.*t/4.);facing_right=True;sitting=False
        elif t < 6:
            x=1224.;facing_right=True;sitting=True
        elif t < 10:
            x=1224.-128.*(t-6.)/4.;facing_right=False;sitting=False
        else:
            x=1096.;facing_right=False;sitting=True
        asset=('kitty_sit_blink' if int(g.c1_elapsed*3)%17==0 else 'kitty_sit') if sitting               else ('kitty_walk_a' if int(g.c1_elapsed*5)%2==0 else 'kitty_walk_b')
        # The tail, face, paws and bell are painted entirely by the Luma JSON engine.
        rect=pygame.Rect(round(x-53),347,107,94)
        engine=self.machine.draw_engine
        if facing_right:
            engine.draw_asset(surface,asset,rect)
        else:
            frame=pygame.Surface((rect.width,rect.height),pygame.SRCALPHA)
            engine.draw_asset(frame,asset,pygame.Rect(0,0,rect.width,rect.height))
            surface.blit(pygame.transform.flip(frame,True,False),rect.topleft)

    def _draw_c13_game_config(self,surface,g):
        shade=pygame.Surface((GAME_WIDTH,GAME_HEIGHT),pygame.SRCALPHA)
        shade.fill((0,0,0,153));surface.blit(shade,(0,0))
        rr=pygame.Rect(310,62,660,499)
        pygame.draw.rect(surface,(25,24,33),rr,border_radius=13)
        pygame.draw.rect(surface,(231,181,117),rr,3,border_radius=13)
        self._c1_text(surface,'GAME CONFIGURATION',348,88,(255,226,166),self.game_font,482)
        close=pygame.Rect(C13_GAME_CLOSE)
        pygame.draw.rect(surface,(100,58,58),close,border_radius=6)
        self._c1_text(surface,'CLOSE',close.x+6,close.y+11,(255,232,213),self.game_small_font,53)
        values=(self.machine.soup_speed_multiplier,self.machine.soup_effect_seconds,
                self.machine.hidden_chest_hitbox_scale)
        labels=('Soup speed multiplier','Soup effect duration','Hidden chest hitbox size ONLY')
        displays=(f'{values[0]:.1f}x normal speed',f'{values[1]} seconds',
                  f'{values[2]:.2f}x chest width and height')
        for i,(x,y,w,h) in enumerate(C131_SLIDER_TRACKS):
            self._c1_text(surface,labels[i],x,y-62,(248,228,191),self.game_font,440)
            self._c1_text(surface,displays[i],x,y-35,(162,244,183),self.game_small_font,390)
            pygame.draw.rect(surface,(73,67,78),(x,y,w,h),border_radius=6)
            ratio=((values[i]-1.)/3.) if i==0 else (((values[i]-5)/85.) if i==1
                                                    else ((values[i]-1.)/4.))
            ratio=max(0.,min(1.,ratio))
            pygame.draw.rect(surface,(148,206,132),(x,y,max(5,round(w*ratio)),h),border_radius=6)
            knob=pygame.Rect(round(x+w*ratio)-10,y-7,20,29)
            pygame.draw.rect(surface,(247,213,146),knob,border_radius=5)
            if i==g.c13_slider_selected:
                pygame.draw.rect(surface,(255,255,242),knob,2,border_radius=5)
        self._c1_text(surface,'Mouse drag or arrow keys to fine-tune; ESC / F1 closes.',345,511,
                      (225,216,204),self.game_small_font,592)

# ---------------------------------------------------------------------------
# D1.0: distribution-development presentation layer.
# World assets, movement, trade, crime, quests and saves remain C1.3.1.
# ---------------------------------------------------------------------------

D1_SLIDER_TRACKS = ((445, 203, 390, 15), (445, 307, 390, 15),
                    (445, 411, 390, 15), (445, 515, 390, 15))
D1_INVENTORY_PAGE = 12


class D1StateMachine(C131StateMachine):
    """Game-first entry, contextual speech and accessible configuration."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bubble_duration_seconds = float(self.config.get('bubble_duration_seconds', 3.0))
        self.d1_bubble_anchor = None
        self.d1_context_anchor = None
        self._log('D1 CONFIG', f'Bubble duration={self.bubble_duration_seconds:.1f}s')

    def start_game(self):
        super().start_game()
        self._set_status('SGG D1.2: direct game launch. Menu or F1 opens settings.')
        self._log('D1 UI', 'Game launched without legacy tool/notes/asset-picker screen')

    def _talk(self, npc):
        prior = self.d1_context_anchor
        self.d1_context_anchor = (float(npc['x']), float(npc['y'])-
                                  float(npc.get('height', 80))/2)
        try:
            return super()._talk(npc)
        finally:
            self.d1_context_anchor = prior

    def _talk_vendor(self, vendor):
        prior = self.d1_context_anchor
        self.d1_context_anchor = (float(vendor['x']), float(vendor['y'])-
                                  float(vendor.get('height', 77))/2)
        try:
            return super()._talk_vendor(vendor)
        finally:
            self.d1_context_anchor = prior

    def _activate(self, obj):
        prior = self.d1_context_anchor
        self.d1_context_anchor = (obj.x + obj.width / 2, obj.y)
        try:
            return super()._activate(obj)
        finally:
            self.d1_context_anchor = prior

    def _d1_anchor_for(self, message):
        g = self.game
        if not g:
            return None
        plain = str(message).lower()
        if self.d1_context_anchor is not None:
            return self.d1_context_anchor
        if plain.startswith('batguard:') and g.c1_guard and g.c1_guard.get('area_id') == g.current_area_id:
            guard = g.c1_guard
            return (float(guard['x']), float(guard['y'])-45)
        # Spoken lines belong to their actual speaker, regardless of proximity.
        for vendor in g.current_area.vendors:
            if plain.startswith(str(vendor.get('name', '')).lower() + ':'):
                return (float(vendor['x']), float(vendor['y']) - float(vendor.get('height', 77)) / 2)
        for npc in g.c1_npcs.values():
            if (npc.get('alive', True) and npc.get('area_id') == g.current_area_id
                    and plain.startswith(str(npc['name']).lower() + ':')):
                return (float(npc['x']), float(npc['y']) - float(npc.get('height', 80)) / 2)
        # Workstation and recipe messages attach to the relevant physical object.
        keywords = {
            'alchemy': ('alchemy_table', 'book'),
            'potion': ('alchemy_table', 'book'),
            'ingredient': ('alchemy_table', 'book'),
            'recipe': ('book', 'alchemy_table', 'cookpot', 'hearth'),
            'cook': ('cookpot', 'hearth'),
            'soup': ('cookpot', 'hearth'),
            'caravan': ('chest',),
            'chest': ('chest',),
        }
        kinds = next((v for k, v in keywords.items() if k in plain), ())
        if kinds:
            nearby = [o for o in g.live_objects() if o.kind in kinds]
            if nearby:
                obj = min(nearby, key=lambda o: math.hypot(g.player_x-o.x, g.player_y-o.y))
                return (obj.x + obj.width / 2, obj.y)
        selected = g.object_by_id(g.selected_object_id)
        if selected and selected.area_id == g.current_area_id and not selected.in_inventory:
            return (selected.x + selected.width / 2, selected.y)
        return (g.player_x, g.player_y - g.player_height / 2)

    def _speech(self, message, seconds=4):
        self.d1_bubble_anchor = self._d1_anchor_for(message)
        # D1 deliberately uses the player's duration preference for every
        # transient message. Dialogue CHOICES remain open until selected.
        super()._speech(message, self.bubble_duration_seconds)

    def _d1_menu(self):
        g = self.game
        if not g or g.c1_dead:
            return
        if g.c1_dialogue or g.c1_save_panel or g.c13_cooking_open or g.c1_config_open:
            return
        g.c13_game_config_open = not g.c13_game_config_open
        g.c13_slider_dragging = False
        if g.c13_game_config_open:
            g.c13_slider_selected = 0
            g.inventory_open = False
        self._log('D1 MENU', 'Game settings '+('opened' if g.c13_game_config_open else 'closed'))

    def _d1_adjust_slider(self, slot, value):
        if slot < 3:
            self._c131_set_slider(slot, value)
            return
        duration = round(max(1.0, min(10.0, float(value))), 1)
        if duration == self.bubble_duration_seconds:
            return
        error = self.persist_preference('bubble_duration_seconds', duration)
        if error:
            self._log('GAME CONFIG ERROR', f'Bubble duration: {error}')
            return
        self.bubble_duration_seconds = duration
        self._log('GAME CONFIG', f'bubble_duration_seconds={duration:.1f}')

    def _d1_slider_pointer(self, pos, ui):
        point = ui.screen_to_game(pos)
        if point is None:
            return
        g = self.game
        slot = g.c13_slider_selected
        x, y, w, h = D1_SLIDER_TRACKS[slot]
        t = max(0.0, min(1.0, (point[0] - x) / w))
        lo, hi = ((1.0, 4.0), (5.0, 90.0), (1.0, 5.0), (1.0, 10.0))[slot]
        self._d1_adjust_slider(slot, lo + t * (hi - lo))

    def _d1_inventory_scroll(self, amount):
        g = self.game
        if g is not None:
            maximum = max(0, len(g.inventory) - D1_INVENTORY_PAGE)
            g.inventory_scroll = max(0, min(maximum, getattr(g, 'inventory_scroll', 0) + amount))

    def _dispatch_game(self, event, ui):
        g = self.game
        if not g:
            return super()._dispatch_game(event, ui)
        # The top-level Menu button and F1 always lead to the same configuration.
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and ui.layout.menu_button.collidepoint(event.pos)):
            self._d1_menu()
            return
        if g.c13_game_config_open:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or c12_binding_matches(event, self.c1_keys['game_config']):
                    self._d1_menu()
                elif event.key in (pygame.K_UP, pygame.K_DOWN):
                    g.c13_slider_selected = (g.c13_slider_selected +
                                            (-1 if event.key == pygame.K_UP else 1)) % 4
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    slot = g.c13_slider_selected
                    current = (self.soup_speed_multiplier, self.soup_effect_seconds,
                               self.hidden_chest_hitbox_scale, self.bubble_duration_seconds)[slot]
                    self._d1_adjust_slider(slot, current + (1 if event.key == pygame.K_RIGHT else -1) *
                                           (1 if slot == 1 else 0.1))
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                point = ui.screen_to_game(event.pos)
                if point is not None and pygame.Rect(C13_GAME_CLOSE).collidepoint(point):
                    self._d1_menu()
                elif point is not None:
                    for i, (x, y, w, h) in enumerate(D1_SLIDER_TRACKS):
                        if pygame.Rect(x-18, y-21, w+36, 53).collidepoint(point):
                            g.c13_slider_selected = i
                            g.c13_slider_dragging = True
                            self._d1_slider_pointer(event.pos, ui)
                            break
                return
            if event.type == pygame.MOUSEMOTION and g.c13_slider_dragging:
                self._d1_slider_pointer(event.pos, ui)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                g.c13_slider_dragging = False
            return
        # Inventory wheel and scrollbar are not forwarded to gameplay clicks.
        if g.inventory_open:
            point = ui.screen_to_game(pygame.mouse.get_pos())
            over_inventory = point is not None and g.inventory_panel_rect().collidepoint(point)
            if event.type == pygame.MOUSEWHEEL and over_inventory:
                self._d1_inventory_scroll(-event.y * 3)
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5) and over_inventory:
                self._d1_inventory_scroll(-3 if event.button == 4 else 3)
                return
            if event.type == pygame.MOUSEMOTION and getattr(g, 'd1_scroll_dragging', False):
                point = ui.screen_to_game(event.pos)
                if point is not None:
                    self._d1_scroll_pointer(point)
                return
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                g.d1_scroll_dragging = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                point = ui.screen_to_game(event.pos)
                if point is not None:
                    track = pygame.Rect(1241, 91, 18, 345)
                    if track.collidepoint(point):
                        g.d1_scroll_dragging = True
                        self._d1_scroll_pointer(point)
                        return
                    for index, oid in enumerate(g.inventory[getattr(g, 'inventory_scroll', 0):
                                                             getattr(g, 'inventory_scroll', 0)+D1_INVENTORY_PAGE]):
                        if g.inventory_row_rect(index).collidepoint(point):
                            g.inventory_selected_id = oid
                            obj = g.object_by_id(oid)
                            self._speech('Selected '+obj.name if obj else 'Missing inventory item')
                            return
        # The old Escape behavior returned to a nonexistent tool screen.
        # Keep Escape as a useful menu shortcut instead (respect active modals).
        if (event.type == pygame.KEYDOWN
                and (event.key == pygame.K_ESCAPE or
                     c12_binding_matches(event, self.c1_keys['exit']))
                and not (g.c1_config_open or g.c1_rebind or g.c1_dialogue or
                         g.c1_save_panel or g.c13_cooking_open or g.c1_dead)):
            if g.inventory_open:
                g.inventory_open = False
            else:
                self._d1_menu()
            return
        return super()._dispatch_game(event, ui)

    def _d1_scroll_pointer(self, point):
        g = self.game
        maximum = max(0, len(g.inventory) - D1_INVENTORY_PAGE)
        if maximum:
            t = max(0.0, min(1.0, (point[1] - 92) / 344.0))
            g.inventory_scroll = round(t * maximum)


class D1Interface(C131Interface):
    """Compact chrome, world-anchored bubbles, external hints and inventory scroll."""
    def __init__(self, machine):
        self.d1_external_hints = True
        self.d1_speech_bubbles = True
        self.d1_dedupe_tooltips = True
        super().__init__(machine)
        # The 1280x640 world remains pixel-perfect; only the window chrome shrinks.
        self.resize(self.width, min(self.height, 780))

    def calculate_layout(self):
        from dataclasses import replace
        old = super().calculate_layout()
        return replace(old,
                       header=pygame.Rect(0, 0, self.width, 42),
                       menu_button=pygame.Rect(self.width-114, 5, 100, 32),
                       game_view_rect=pygame.Rect(9, 47, self.width-18, self.height-102),
                       game_back_button=pygame.Rect(-1000, -1000, 1, 1),
                       game_screenshot_button=pygame.Rect(-1000, -1000, 1, 1))

    def _draw_header(self):
        pygame.draw.rect(self.screen, (22, 18, 31), (0, 0, self.width, 42))
        pygame.draw.line(self.screen, (185, 143, 93), (0, 41), (self.width, 41), 1)
        path = str(self.machine.archive.directory)
        font = self.game_small_font
        available = self.width - 145
        # Preserve the terminal portion of a long path, including the run name.
        if font.size(path)[0] > available:
            while path and font.size('…'+path)[0] > available:
                path = path[1:]
            path = '…' + path
        self.screen.blit(font.render(path, True, (239, 225, 195)), (12, 12))
        button = self.layout.menu_button
        pygame.draw.rect(self.screen, (77, 59, 80), button, border_radius=5)
        pygame.draw.rect(self.screen, (210, 171, 112), button, 2, border_radius=5)
        label = self.game_small_font.render('MENU', True, (252, 230, 179))
        self.screen.blit(label, label.get_rect(center=button.center))

    def _d1_hint(self, g):
        if not g.c1_hint_visible:
            return ''
        hints = {
            'castle_hall': 'TREASURE ROOM: a platter and a suspicious wall seam might prove useful.',
            'troll_cave': 'Frosty guards the purple pineapple. Soup might help you escape!',
            'stables': f'KITTY CARAVAN: chest refreshes every two days. Today: Day {g.c1_day}.',
            'alchemy_shop': 'ALCHEMIST: B buy (69,000g), V sell, E at the table or recipe book.',
            'inn_interior': 'INN: E at the cookpot; two tomatoes + two cabbages make speed soup.',
            'mages_lab': 'E to speak to Fearmonger and deliver his enhancement potion.',
        }
        return hints.get(g.current_area_id,
                         'WASD/ARROWS move   E use/talk   I inventory   F1/Menu settings   F3 keys   F5/F9 save/load   ? hints')

    def _draw_game(self):
        game = self.machine.game
        if game is None:
            return
        view = self.layout.game_view_rect
        scale = min(view.width / GAME_WIDTH, view.height / GAME_HEIGHT)
        draw_w, draw_h = max(1, round(GAME_WIDTH * scale)), max(1, round(GAME_HEIGHT * scale))
        left = view.x + (view.width - draw_w) // 2
        self.game_blit_rect = pygame.Rect(left, view.y, draw_w, draw_h)
        canvas = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
        self._draw_game_scene(canvas, game)
        self.screen.blit(pygame.transform.scale(canvas, (draw_w, draw_h)), self.game_blit_rect)
        pygame.draw.rect(self.screen, (220, 187, 126), self.game_blit_rect, 1)
        # The hints panel is explicitly OUTSIDE the world rendering viewport.
        if game.c1_hint_visible:
            hint = self._d1_hint(game)
            rect = pygame.Rect(self.game_blit_rect.x,
                               self.game_blit_rect.bottom + 6,
                               self.game_blit_rect.width, 29)
            if rect.bottom <= self.height:
                pygame.draw.rect(self.screen, (29, 26, 35), rect, border_radius=4)
                pygame.draw.rect(self.screen, (168, 137, 96), rect, 1, border_radius=4)
                text = hint
                font = self.game_small_font
                while text and font.size(text)[0] > rect.width-16:
                    text = text[:-2]+'…'
                self.screen.blit(font.render(text, True, (240, 227, 197)), (rect.x+9, rect.y+5))

    def _d1_wrapped_lines(self, content, max_width, font, limit=None):
        words = str(content).replace('\n', ' \n ').split(' ')
        lines, line = [], ''
        for word in words:
            if word == '\n':
                lines.append(line); line = ''; continue
            candidate = word if not line else line+' '+word
            if font.size(candidate)[0] <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                    line = ''
                if font.size(word)[0] > max_width:
                    piece = ''
                    for letter in word:
                        if piece and font.size(piece+letter)[0] > max_width:
                            lines.append(piece); piece = letter
                        else: piece += letter
                    line = piece
                else:
                    line = word
        if line: lines.append(line)
        if not lines: lines = ['']
        if limit is not None and len(lines) > limit:
            lines = lines[:limit]
            last = lines[-1]
            while last and font.size(last+'…')[0] > max_width: last = last[:-1]
            lines[-1] = last+'…'
        return lines

    def _d1_speech_anchor(self, g, speaker=None):
        if speaker:
            name = str(speaker).lower()
            alias = {'inn lout':'inn_lout', 'fearmonger':'fearmonger',
                     'naz':'naz', 'alchemist':'alchemy_vendor', 'karlotta':'kart_lotta'}
            for vendor in g.current_area.vendors:
                if (name == str(vendor.get('name', '')).lower() or
                        alias.get(name) == vendor.get('vendor_id')):
                    return float(vendor['x']), float(vendor['y'])-40
            for npc in g.c1_npcs.values():
                if (npc.get('alive', True) and npc['area_id'] == g.current_area_id and
                        (name == npc['name'].lower() or alias.get(name) == npc.get('npc_id'))):
                    return float(npc['x']), float(npc['y'])-float(npc.get('height', 80))/2
        return self.machine.d1_bubble_anchor or (g.player_x, g.player_y-25)

    def _draw_d1_bubble(self, surface, message, anchor, *, max_width=540, max_lines=7):
        font = self.game_small_font
        padding = 13
        lines = self._d1_wrapped_lines(message, max_width-2*padding, font, max_lines)
        textwidth = max(font.size(line)[0] for line in lines)
        width = min(max_width, max(140, textwidth+2*padding))
        line_h = font.get_linesize()+2
        height = max(40, len(lines)*line_h+2*padding)
        ax, ay = (int(anchor[0]), int(anchor[1]))
        x = max(7, min(GAME_WIDTH-width-7, ax-width//2))
        # Prefer above the speaker. If that would cover the HUD, move below.
        above_y = ay-height-22
        y = above_y if above_y >= 48 else min(GAME_HEIGHT-height-8, ay+25)
        y = max(46, min(GAME_HEIGHT-height-8, y))
        rect = pygame.Rect(x, y, width, height)
        shadow = rect.move(3, 4)
        pygame.draw.rect(surface, (10, 9, 13), shadow, border_radius=12)
        pygame.draw.rect(surface, (248, 237, 213), rect, border_radius=12)
        pygame.draw.rect(surface, (91, 62, 79), rect, 3, border_radius=12)
        # Pointer faces toward the actual source; clamp to bubble edges.
        tipx = max(x+20, min(x+width-20, ax))
        if y < ay:
            pts = [(tipx-9, rect.bottom-1), (tipx+9, rect.bottom-1), (tipx, min(GAME_HEIGHT-2, ay-3))]
        else:
            pts = [(tipx-9, rect.top+1), (tipx+9, rect.top+1), (tipx, max(43, ay+5))]
        pygame.draw.polygon(surface, (248, 237, 213), pts)
        pygame.draw.lines(surface, (91, 62, 79), False, [pts[0], pts[2], pts[1]], 2)
        for i, line in enumerate(lines):
            surface.blit(font.render(line, True, (41, 31, 43)), (x+padding, y+padding+i*line_h))
        return rect

    def _draw_dialogue_panel(self, surface, g):
        info = g.c1_dialogue
        anchor = self._d1_speech_anchor(g, info['speaker'])
        self._draw_d1_bubble(surface, info['speaker']+': '+info['line'], anchor, max_width=610, max_lines=8)
        # Choices remain explicit controls; otherwise branching quests break.
        options = info['options']
        card_height = len(options)*43+46
        panel = pygame.Rect(245, 320, 790, max(98, 43*len(options)+72))
        pygame.draw.rect(surface, (27, 24, 34), panel, border_radius=9)
        pygame.draw.rect(surface, (218, 179, 111), panel, 2, border_radius=9)
        for index, option in enumerate(options):
            row = pygame.Rect(260, 335+index*43, 760, 37)
            # Preserve C1.2's exact click hitboxes at y=335+index*43.
            pygame.draw.rect(surface, (105, 80, 92) if index == g.c1_dialogue_selected else (47, 42, 57),
                             row, border_radius=5)
            pygame.draw.rect(surface, (232, 189, 115) if index == g.c1_dialogue_selected else (98, 87, 102),
                             row, 1, border_radius=5)
            line = f'{index+1}. {option["text"]}'
            self._c1_text(surface, line, row.x+12, row.y+7, (250, 238, 210), self.game_small_font, 725)
        self._c1_text(surface, '1-5 / arrows + Enter choose. Esc closes.', 265, panel.bottom-29,
                      (224, 213, 195), self.game_small_font, 690)

    def _draw_game_scene(self, surface, g):
        # Clamp before the inherited inventory renderer indexes its visible page.
        if g.inventory_open:
            g.inventory_scroll = max(0, min(max(0, len(g.inventory)-D1_INVENTORY_PAGE),
                                             getattr(g, 'inventory_scroll', 0)))
        # All world artwork and mechanics are delegated to the C1.3.1 renderer.
        super()._draw_game_scene(surface, g)
        # Scrollbar lives solely in the inventory panel and is shown only
        # when there are more items than the visible inventory page.
        if g.inventory_open:
            max_scroll = max(0, len(g.inventory)-D1_INVENTORY_PAGE)
            g.inventory_scroll = max(0, min(max_scroll, getattr(g, 'inventory_scroll', 0)))
            if max_scroll:
                track = pygame.Rect(1244, 92, 10, 341)
                pygame.draw.rect(surface, (79, 73, 86), track, border_radius=4)
                thumb_h = max(28, round(track.height*D1_INVENTORY_PAGE/len(g.inventory)))
                ty = track.y + round((track.height-thumb_h)*g.inventory_scroll/max_scroll)
                thumb = pygame.Rect(track.x, ty, track.width, thumb_h)
                pygame.draw.rect(surface, (233, 186, 103), thumb, border_radius=4)
                text = f'{g.inventory_scroll+1}-{min(len(g.inventory),g.inventory_scroll+D1_INVENTORY_PAGE)} / {len(g.inventory)}'
                self._c1_text(surface, text, 1090, 59, (225, 205, 164), self.game_small_font, 120)
        # Speech is a timed speech bubble above the speaker or active object.
        if (g.c1_speech_seconds > 0 and g.c1_selected_speech
                and not (g.c1_dialogue or g.c1_dead or g.c1_save_panel or
                         g.c13_cooking_open or g.c13_game_config_open or g.c1_config_open)):
            self._draw_d1_bubble(surface, g.c1_selected_speech, self._d1_speech_anchor(g))

    def _draw_c13_game_config(self, surface, g):
        shade = pygame.Surface((GAME_WIDTH, GAME_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 153))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect(305, 52, 670, 558)
        pygame.draw.rect(surface, (25, 24, 33), panel, border_radius=13)
        pygame.draw.rect(surface, (231, 181, 117), panel, 3, border_radius=13)
        self._c1_text(surface, 'GAME CONFIGURATION', 345, 71, (255, 226, 166), self.game_font, 490)
        close = pygame.Rect(C13_GAME_CLOSE)
        pygame.draw.rect(surface, (100, 58, 58), close, border_radius=6)
        self._c1_text(surface, 'CLOSE', close.x+6, close.y+11,
                      (255, 232, 213), self.game_small_font, 54)
        values = (self.machine.soup_speed_multiplier, self.machine.soup_effect_seconds,
                  self.machine.hidden_chest_hitbox_scale, self.machine.bubble_duration_seconds)
        labels = ('Soup speed multiplier', 'Soup effect duration',
                  'Hidden chest hitbox size ONLY', 'Speech bubble duration')
        displays = (f'{values[0]:.1f}x normal speed', f'{values[1]} seconds',
                    f'{values[2]:.2f}x chest width and height', f'{values[3]:.1f} seconds')
        ranges = ((1., 4.), (5., 90.), (1., 5.), (1., 10.))
        for i, (x, y, w, h) in enumerate(D1_SLIDER_TRACKS):
            self._c1_text(surface, labels[i], x, y-52, (248, 228, 191), self.game_font, 456)
            self._c1_text(surface, displays[i], x, y-25, (162, 244, 183), self.game_small_font, 400)
            pygame.draw.rect(surface, (73, 67, 78), (x, y, w, h), border_radius=6)
            t = max(0., min(1., (values[i]-ranges[i][0])/(ranges[i][1]-ranges[i][0])))
            pygame.draw.rect(surface, (148, 206, 132), (x, y, max(5, round(w*t)), h), border_radius=6)
            knob = pygame.Rect(round(x+w*t)-10, y-7, 20, 29)
            pygame.draw.rect(surface, (247, 213, 146), knob, border_radius=5)
            if g.c13_slider_selected == i:
                pygame.draw.rect(surface, (255, 255, 242), knob, 2, border_radius=5)
        self._c1_text(surface, 'Mouse drag / arrow keys adjust. ESC or F1 closes.', 345, 572,
                      (225, 216, 204), self.game_small_font, 590)




# ---------------------------------------------------------------------------
# D1.1 — preserving D1.0 mechanics while adding dynamic speech, discreet
# character-triggered cameo appearances and the magician's original tip sign.
# Cameo state lives in c1_flags, automatically serialized by the existing
# SAVE_SCHEMA (thus older D1.0/C1.3.1 save slots remain readable).
# ---------------------------------------------------------------------------

D11_TIP_URL = 'https://ko-fi.com/cozmothemagician'
D11_CAMEO_TEXT = {
    'bucket': 'Hope you liked the bucket trick (: Feel free to click the tip jar if you can help out.',
    'naz': 'I love how you got rid of Naz! Luma and I are proud of that bit of coding. Even if you don\'t tip, it\'s nice to know you discovered what we wrote. Thank you!',
}


class D11StateMachine(D1StateMachine):
    """Small additions to the authoritative D1.0 state machine."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.d11_context_ref = None

    def _d11_flags(self):
        g = self.game
        if g is None:
            return None
        f = g.c1_flags
        f.setdefault('d11_cameo_events', [])
        f.setdefault('d11_cameo_queue', [])
        f.setdefault('d11_cameo_active', None)
        return f

    def start_game(self):
        super().start_game()
        self._d11_flags()

    def _read_save(self, slot):
        super()._read_save(slot)
        self._d11_flags()
        # Existing D1.0 saves stored the old floor-door coordinates. Move ONLY
        # the unmodified legacy exit to the new back-wall doorway, leaving
        # custom player-placed objects and all quest progress intact.
        exit_obj = self.game.object_by_id('castle_exit') if self.game else None
        if exit_obj and abs(exit_obj.x-601)<1 and abs(exit_obj.y-516)<1:
            exit_obj.x, exit_obj.y, exit_obj.width, exit_obj.height = 601., 279., 88, 123
            self._log('SAVE MIGRATION', 'Moved old castle floor exit onto the hall back wall')
        self.d1_bubble_anchor = {'kind': 'player'}

    def _d11_open_tip(self):
        import webbrowser
        try:
            launched = webbrowser.open(D11_TIP_URL, new=2)
            self._log('KO-FI', f'Tip jar visited; browser request returned {launched}')
            if not launched:
                self._set_status('Ko-fi: ' + D11_TIP_URL)
        except Exception as exc:
            self._log('KO-FI ERROR', f'{type(exc).__name__}: {exc}')
            self._set_status('Open ' + D11_TIP_URL + ' in your browser.')

    def _d11_schedule(self, event):
        f = self._d11_flags()
        if f is None:
            return
        if event in f['d11_cameo_events']:
            return
        f['d11_cameo_events'].append(event)
        f['d11_cameo_queue'].append({'event': event, 'at': self.game.c1_elapsed + 5.0})
        self._log('COZMO CAMEO', f'Queued {event} at {self.game.c1_elapsed + 5.0:.2f}')

    def _take(self, obj):
        g = self.game
        # A successful unwitnessed theft performed while a bucket blinds a
        # vendor/guard, not merely putting the bucket on somebody's head.
        candidate = bool(g and obj and obj.takeable and not obj.in_inventory and
                         g.close_to_object(obj) and g.is_unauthorized(obj) and
                         (g.bucket_on_head_vendor_id or g.c1_guard_bucketed) and
                         not g.is_vendor_watching(obj) and not g.guard_sees(obj))
        previous = (obj.area_id, obj.in_inventory) if obj else None
        result = super()._take(obj)
        if candidate and obj and (obj.in_inventory or obj.area_id != previous[0]):
            self._d11_schedule('bucket')
        return result

    def _npc_tick(self, dt):
        g = self.game
        previous_naz = bool(g and g.c1_npcs.get('naz', {}).get('alive', True))
        super()._npc_tick(dt)
        if previous_naz and g and not g.c1_npcs.get('naz', {}).get('alive', True):
            self._d11_schedule('naz')

    def _area_enter(self, conn):
        # A cameo should be a discovery, not an NPC stranded on another map.
        g = self.game
        if g:
            flags = self._d11_flags()
            active = flags.get('d11_cameo_active')
            if active and conn.to_area_id != active.get('area'):
                flags['d11_cameo_active'] = None
        return super()._area_enter(conn)

    def _d11_update_cameo(self):
        g = self.game
        if not g:
            return
        f = self._d11_flags()
        active = f.get('d11_cameo_active')
        if active is not None:
            if active.get('area') != g.current_area_id:
                f['d11_cameo_active'] = None
            elif active.get('leave_at') is not None and g.c1_elapsed >= active['leave_at']:
                f['d11_cameo_active'] = None
                self._log('COZMO CAMEO', 'Departed after conversation')
            return
        if not f['d11_cameo_queue']:
            return
        next_event = f['d11_cameo_queue'][0]
        if g.c1_elapsed < next_event['at'] or g.c1_dead or g.c1_dialogue:
            return
        # Bucket congratulations can happen where the player actually used
        # the trick (including the Alchemy Shop). Naz's death cameo is in the
        # market specifically, and waits there for the player to return.
        safe_for_bucket = ('alchemy_shop', 'britrun_market', 'stables',
                           'plains', 'inn_outside', 'gold_district')
        if next_event['event'] == 'naz' and g.current_area_id != AREA_MARKET:
            return
        if next_event['event'] == 'bucket' and g.current_area_id not in safe_for_bucket:
            return
        f['d11_cameo_queue'].pop(0)
        # Stay away from the player and visible in the 1280x640 viewport.
        px, py = g.player_x, g.player_y
        x = max(120., min(1120., px + (145 if px < 880 else -145)))
        y = max(190., min(535., py + (8 if py < 420 else -16)))
        f['d11_cameo_active'] = {'event': next_event['event'], 'area': g.current_area_id,
                                'x': x, 'y': y, 'talked': False, 'leave_at': None}
        self._log('COZMO CAMEO', f'Appeared for {next_event["event"]} at {x:.0f},{y:.0f}')

    def update(self, elapsed_seconds, ui):
        result = super().update(elapsed_seconds, ui)
        if self.game and self.state is AppState.PLAY_GAME:
            self._d11_update_cameo()
        return result

    def _d11_rects(self):
        g = self.game
        info = self._d11_flags().get('d11_cameo_active') if g else None
        if not info or info['area'] != g.current_area_id:
            return None
        x, y = info['x'], info['y']
        return (pygame.Rect(round(x - 35), round(y - 54), 70, 99),
                pygame.Rect(round(x + 22), round(y + 15), 41, 42))

    def _d11_talk(self):
        info = self._d11_flags().get('d11_cameo_active')
        if not info:
            return
        if not info.get('talked'):
            info['talked'] = True
            # Leave the jar accessible for a generous 30 seconds afterwards.
            info['leave_at'] = self.game.c1_elapsed + 30.0
        self._dialogue('Cozmo', D11_CAMEO_TEXT[info['event']],
                       [{'text': 'Thank you, Cozmo!', 'action': 'close'}])

    def _d11_interact(self, ui, point=None):
        rects = self._d11_rects()
        if not rects:
            return False
        actor, jar = rects
        g = self.game
        # Hovered jar wins; otherwise choose the nearby NPC. Explicit mouse
        # proximity prevents accidental browser launches during ordinary play.
        if point and jar.inflate(10, 10).collidepoint(point):
            if g.close_to(jar.centerx, jar.centery, reach=147):
                self._d11_open_tip()
            else:
                self._speech('Walk closer to Cozmo\'s tip jar first.')
            return True
        if point and actor.inflate(12, 8).collidepoint(point):
            if g.close_to(actor.centerx, actor.centery, reach=177):
                self._d11_talk()
            else:
                self._speech('Walk closer to speak with Cozmo.')
            return True
        if g.close_to(actor.centerx, actor.centery, reach=109):
            self._d11_talk()
            return True
        return False

    def _use_nearest(self, ui):
        if self._d11_interact(ui, ui.screen_to_game(pygame.mouse.get_pos())):
            return
        return super()._use_nearest(ui)

    def _mouse_game(self, event, ui):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            point = ui.screen_to_game(event.pos)
            rects = self._d11_rects()
            if point and rects:
                actor, jar = rects
                if jar.collidepoint(point):
                    if self.game.close_to(jar.centerx, jar.centery, reach=147):
                        self._d11_open_tip()
                    else: self._speech('Walk closer to the tip jar.')
                    return
                if actor.collidepoint(point):
                    if self.game.close_to(actor.centerx, actor.centery, reach=177):
                        self._d11_talk()
                    else: self._speech('Walk closer to speak with Cozmo.')
                    return
        return super()._mouse_game(event, ui)

    def _dispatch_game(self, event, ui):
        # The thank-you sign is part of the global top chrome, even while a
        # dialogue or inventory menu is open. Never treat its click as travel.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if ui.d11_tip_button().collidepoint(event.pos):
                self._d11_open_tip()
                return
        return super()._dispatch_game(event, ui)

    def _talk(self, npc):
        previous = self.d11_context_ref
        self.d11_context_ref = {'kind': 'npc', 'id': npc.get('npc_id')}
        try:
            return C131StateMachine._talk(self, npc)
        finally:
            self.d11_context_ref = previous

    def _talk_vendor(self, vendor):
        previous = self.d11_context_ref
        self.d11_context_ref = {'kind': 'vendor', 'id': vendor.get('vendor_id')}
        try:
            return C131StateMachine._talk_vendor(self, vendor)
        finally:
            self.d11_context_ref = previous

    def _activate(self, obj):
        previous = self.d11_context_ref
        self.d11_context_ref = {'kind': 'object', 'id': obj.object_id}
        try:
            return C131StateMachine._activate(self, obj)
        finally:
            self.d11_context_ref = previous

    def _d1_anchor_for(self, message):
        g = self.game
        if not g:
            return None
        if self.d11_context_ref is not None:
            return dict(self.d11_context_ref)
        plain = str(message).lower()
        if plain.startswith(('batguard:', 'guard:')) and g.c1_guard:
            return {'kind': 'guard'}
        for v in g.current_area.vendors:
            if plain.startswith(str(v.get('name', '')).lower() + ':'):
                return {'kind': 'vendor', 'id': v.get('vendor_id')}
        for npc in g.c1_npcs.values():
            if npc.get('area_id') != g.current_area_id or not npc.get('alive', True):
                continue
            if (plain.startswith(npc['name'].lower() + ':') or
                    message in npc.get('lines', [])):
                return {'kind': 'npc', 'id': npc['npc_id']}
        names = {
            'alchemy': ('alchemy_table', 'book'), 'potion': ('alchemy_table','book'),
            'recipe': ('book', 'alchemy_table','cookpot'), 'cook': ('cookpot','hearth'),
            'soup': ('cookpot','hearth'), 'caravan': ('chest',), 'chest': ('chest',),
        }
        kinds = next((v for word, v in names.items() if word in plain), ())
        nearest = [o for o in g.live_objects() if o.kind in kinds]
        if nearest:
            o = min(nearest, key=lambda o: math.dist((g.player_x,g.player_y),(o.x,o.y)))
            return {'kind': 'object', 'id': o.object_id}
        selected = g.object_by_id(g.selected_object_id)
        if selected and not selected.in_inventory and selected.area_id == g.current_area_id:
            return {'kind': 'object', 'id': selected.object_id}
        return {'kind': 'player'}


class D11Interface(D1Interface):
    """D1 visuals retained, plus script lettered tip sign and JSON cameo art."""
    def d11_tip_button(self):
        menu = self.layout.menu_button
        return pygame.Rect(menu.x - 246, menu.y, 235, menu.height)

    def _draw_header(self):
        # Leave room for BOTH top-right controls, without erasing archive info.
        super()._draw_header()
        sign = self.d11_tip_button()
        pygame.draw.rect(self.screen, (76, 47, 80), sign, border_radius=5)
        pygame.draw.rect(self.screen, (220, 175, 106), sign, 2, border_radius=5)
        # Use a real script face when available on Windows (Segoe Script), not
        # merely the standard UI font with its italic property turned on.
        if not hasattr(self, '_d11_tip_fonts'):
            regular = pygame.font.SysFont('consolas', 16, bold=True)
            regular.set_underline(True)
            try:
                family = next((name for name in ('Segoe Script', 'Brush Script MT',
                           'Freestyle Script', 'Lucida Handwriting', 'Comic Sans MS')
                           if pygame.font.match_font(name)), 'arial')
                script = pygame.font.SysFont(family, 21 if family != 'arial' else 17, italic=True)
            except Exception:
                script = pygame.font.SysFont('arial', 17, italic=True)
            self._d11_tip_fonts = regular, script
        regular, script = self._d11_tip_fonts
        left = regular.render('Please Tip', True, (255, 229, 174))
        right = script.render('Thank You!', True, (246, 213, 174))
        gap = 9
        total = left.get_width() + gap + right.get_width()
        x = sign.centerx - total // 2
        self.screen.blit(left, (x, sign.centery - left.get_height() // 2))
        self.screen.blit(right, (x + left.get_width() + gap,
                                 sign.centery - right.get_height() // 2))
        # Redraw the archive label clipped to free header width, never under
        # the sign; preserves the useful end of the path on long Windows paths.
        pygame.draw.rect(self.screen, (22, 18, 31), (0, 0, max(0, sign.x-6), 40))
        path = str(self.machine.archive.directory)
        font = self.game_small_font
        available = max(20, sign.x - 24)
        if font.size(path)[0] > available:
            while path and font.size('…'+path)[0] > available:
                path = path[1:]
            path = '…'+path
        self.screen.blit(font.render(path, True, (239,225,195)), (12,12))

    def _d11_resolve_anchor(self, g, ref):
        if not isinstance(ref, dict):
            return ref
        kind = ref.get('kind')
        if kind == 'player':
            return (float(g.player_x), float(g.player_y)-g.player_height/2)
        if kind == 'npc':
            obj = g.c1_npcs.get(ref.get('id'))
            if obj and obj.get('alive', True) and obj.get('area_id') == g.current_area_id:
                return (float(obj['x']), float(obj['y'])-float(obj.get('height', 80))/2)
        if kind == 'vendor':
            obj = next((v for v in g.current_area.vendors if v.get('vendor_id') == ref.get('id')), None)
            if obj:
                return (float(obj['x']), float(obj['y'])-float(obj.get('height',77))/2)
        if kind == 'guard':
            obj = g.c1_guard
            if obj and obj.get('area_id') == g.current_area_id:
                return (float(obj['x']), float(obj['y'])-43)
        if kind == 'object':
            obj = g.object_by_id(ref.get('id'))
            if obj and obj.area_id == g.current_area_id and not obj.in_inventory:
                return (obj.x+obj.width/2, obj.y)
        if kind == 'cozmo':
            info = g.c1_flags.get('d11_cameo_active')
            if info and info.get('area') == g.current_area_id:
                return (float(info['x']),float(info['y'])-55)
        return (float(g.player_x),float(g.player_y)-g.player_height/2)

    def _d1_speech_anchor(self, g, speaker=None):
        if speaker and str(speaker).lower() == 'cozmo':
            return self._d11_resolve_anchor(g, {'kind':'cozmo'})
        if speaker:
            name = str(speaker).lower()
            for v in g.current_area.vendors:
                if name == str(v.get('name', '')).lower():
                    return self._d11_resolve_anchor(g, {'kind':'vendor', 'id':v.get('vendor_id')})
            for npc in g.c1_npcs.values():
                if name == npc['name'].lower() and npc.get('area_id') == g.current_area_id:
                    return self._d11_resolve_anchor(g, {'kind':'npc', 'id':npc['npc_id']})
        # Autonomous NPC banter is written directly by the old C1.2 tick,
        # bypassing _speech. Resolve it by matching that NPC's actual lines.
        if not speaker:
            for npc in g.c1_npcs.values():
                if (npc.get('area_id') == g.current_area_id and npc.get('alive', True)
                        and g.c1_selected_speech in npc.get('lines', [])):
                    return self._d11_resolve_anchor(g, {'kind':'npc','id':npc['npc_id']})
        anchor = getattr(self.machine, 'd1_bubble_anchor', None)
        if isinstance(anchor, dict):
            return self._d11_resolve_anchor(g, anchor)
        return super()._d1_speech_anchor(g, speaker)

    def _draw_game_scene(self, surface, g):
        super()._draw_game_scene(surface, g)
        info = g.c1_flags.get('d11_cameo_active')
        if not info or info.get('area') != g.current_area_id:
            return
        x, y = info['x'], info['y']
        self.machine.draw_engine.draw_asset(surface, 'cozmo_magician',
                                            pygame.Rect(round(x-35),round(y-54),70,99))
        self.machine.draw_engine.draw_asset(surface, 'cozmo_tip_jar',
                                            pygame.Rect(round(x+22),round(y+15),41,42))
        point = self.screen_to_game(pygame.mouse.get_pos())
        rects = self.machine._d11_rects()
        if (rects and point and rects[1].inflate(7,7).collidepoint(point)
                and not (g.inventory_open or g.c1_dialogue or g.c13_game_config_open)):
            label = 'E = Go to Cozmo\'s Ko-fi'
            font = self.game_small_font
            txt = font.render(label, True, (250, 221, 153))
            xx = min(GAME_WIDTH-txt.get_width()-20, max(8,point[0]+13))
            yy = min(GAME_HEIGHT-38, max(50,point[1]+15))
            rr = pygame.Rect(xx-7,yy-5,txt.get_width()+14,txt.get_height()+10)
            pygame.draw.rect(surface,(28,23,31),rr,border_radius=4)
            pygame.draw.rect(surface,(230,176,109),rr,2,border_radius=4)
            surface.blit(txt,(xx,yy))
        elif (rects and point and rects[0].collidepoint(point)
              and not (g.inventory_open or g.c1_dialogue or g.c13_game_config_open)):
            txt = self.game_small_font.render('E = Talk to Cozmo', True, (250,221,153))
            xx = min(GAME_WIDTH-txt.get_width()-15,point[0]+13)
            yy = min(GAME_HEIGHT-30,point[1]+15)
            rr = pygame.Rect(xx-5,yy-5,txt.get_width()+10,txt.get_height()+9)
            pygame.draw.rect(surface,(28,23,31),rr,border_radius=4)
            surface.blit(txt,(xx,yy))



# ---------------------------------------------------------------------------
# D1.2 — two focused presentation fixes, preserving D1.1 mechanics, artwork,
# save schema, cameo timing and event triggers. See D1.1 classes above.
# ---------------------------------------------------------------------------

class D12StateMachine(D11StateMachine):
    """Route inventory feedback to the player, not a similarly named station.

    D1.1 guessed that ANY message containing 'potion' came from the alchemy
    table / recipe book. Selecting an inventory potion consequently made its
    'Selected ...' bubble point across the shop. Explicit UI intent wins over
    keyword-based world-object inference.
    """

    def _d1_anchor_for(self, message):
        message_text = str(message).strip().lower()
        if message_text.startswith(('selected ', 'missing inventory item')):
            return {'kind': 'player'}
        return super()._d1_anchor_for(message)


class D12Interface(D11Interface):
    """Display every dialogue line *inside* its choice panel exactly once.

    The dialog option rectangles intentionally remain at their established
    D1.1 coordinates because C1.2's mouse dispatcher uses those hitboxes.
    Normal non-dialogue speech bubbles remain unchanged and still follow
    the speaking character.
    """

    def _draw_dialogue_panel(self, surface, g):
        info = g.c1_dialogue
        # This modal replaces D1.1's speech-bubble-plus-choices presentation.
        # No separate speech bubble is drawn for dialogue.
        shade = pygame.Surface((GAME_WIDTH, GAME_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 148))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect(213, 105, 853, 464)
        pygame.draw.rect(surface, (26, 22, 35), panel, border_radius=12)
        pygame.draw.rect(surface, (233, 190, 113), panel, 3, border_radius=12)
        self._c1_text(surface, str(info['speaker']).upper(), 254, 132,
                      (255, 218, 152), self.game_font, 756)
        pygame.draw.line(surface, (105, 82, 89), (252, 178), (1028, 178), 1)

        # Render the *complete* dialogue, rather than the former bubble's
        # max_lines=8 truncation or C1.2's first-three-lines-only limitation.
        # Adapt font size for longer speeches while keeping the options in
        # their original clickable rows at y=335, 378, ... .
        text = str(info['line'])
        fonts = [self.game_small_font]
        fonts.extend(pygame.font.SysFont('segoeui', pt) for pt in (17, 15, 13, 11))
        available_height = 132  # y=191 through y=323; first option y=335.
        text_font, lines, line_height = None, [], 0
        for font in fonts:
            wrapped = self._d1_wrapped_lines(text, 745, font)
            height = font.get_linesize() + 3
            if len(wrapped) * height <= available_height:
                text_font, lines, line_height = font, wrapped, height
                break
        if text_font is None:
            # Current game speeches fit above. If substantially longer prose
            # is added later, shrink one last time rather than silently
            # discard the end of a speech.
            text_font = pygame.font.SysFont('segoeui', 9)
            lines = self._d1_wrapped_lines(text, 745, text_font)
            line_height = text_font.get_linesize() + 1
        for i, line in enumerate(lines):
            surface.blit(text_font.render(line, True, (248, 235, 206)),
                         (254, 190 + i * line_height))

        for index, option in enumerate(info['options']):
            row = pygame.Rect(260, 335 + index * 43, 760, 37)
            pygame.draw.rect(surface,
                             (105, 80, 92) if index == g.c1_dialogue_selected else (47, 42, 57),
                             row, border_radius=5)
            pygame.draw.rect(surface,
                             (232, 189, 115) if index == g.c1_dialogue_selected else (98, 87, 102),
                             row, 2, border_radius=5)
            self._c1_text(surface, f'{index + 1}. {option["text"]}', row.x + 12, row.y + 7,
                          (250, 238, 210), self.game_small_font, 725)
        self._c1_text(surface, '1–5 / arrows + Enter choose. Esc closes.', 254, 546,
                      (224, 213, 195), self.game_small_font, 690)

# Keep the file executable directly, with no dependency on earlier source versions.
if __name__ == '__main__':
    raise SystemExit(main())
