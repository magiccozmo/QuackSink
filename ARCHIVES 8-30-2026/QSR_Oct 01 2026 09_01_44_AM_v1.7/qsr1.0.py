#!/usr/bin/env python3
# QSR / QS_Replay 1.7
#
# Archive reader / talking replay for the QuackSink archive.
#
# Design principle:
#   PRESERVE THE ARCHIVE FAITHFULLY; PRESENT IT THEATRICALLY.
#
# QSR treats the MASTER_INDEX as its catalog authority, loads conversations
# from the archive, discovers speakers, dynamically discovers custom Kokoro
# voice assets from STARTDIR\voices, and dynamically discovers PNG portraits
# from STARTDIR\portraits.
#
# State-machine oriented design:
#   QSR_START -> SELF_ARCHIVE -> LOAD_CONFIG -> LOAD_INDEX -> CATALOG_READY
#   CATALOG_READY -> CURRENT_CARD -> CONVERSATION_LOADED -> PLAYER
#
# COZMO NEVER EDITS:
# This file is a complete standalone QSR version. Replace the whole file when
# creating a new QSR version; do not patch this file in place.

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


VERSION = "1.7"
PROGRAM_NAME = "QSR"
CONFIG_NAME = "qsr_config.json"
ARCHIVE_DIR_NAME = "ARCHIVES"
VOICE_DIR_NAME = "voices"
PORTRAIT_DIR_NAME = "portraits"
SESSION_ARCHIVE_PREFIX = "QSR"
SCHEME_CHOICES = ["dark", "light"]

DEFAULT_INDEX_SOURCE = (
    "https://github.com/magiccozmo/QuackSink/blob/main/"
    "ARCHIVES 8-30-2026/MASTER_INDEX.JSON"
)

STANDARD_KOKORO_VOICES = [
    ("af_alloy", "Kokoro - American Female - Alloy"),
    ("af_aoede", "Kokoro - American Female - Aoede"),
    ("af_bella", "Kokoro - American Female - Bella"),
    ("af_heart", "Kokoro - American Female - Heart"),
    ("af_jessica", "Kokoro - American Female - Jessica"),
    ("af_kore", "Kokoro - American Female - Kore"),
    ("af_nicole", "Kokoro - American Female - Nicole"),
    ("af_nova", "Kokoro - American Female - Nova"),
    ("af_river", "Kokoro - American Female - River"),
    ("af_sarah", "Kokoro - American Female - Sarah"),
    ("af_sky", "Kokoro - American Female - Sky"),
    ("am_adam", "Kokoro - American Male - Adam"),
    ("am_echo", "Kokoro - American Male - Echo"),
    ("am_eric", "Kokoro - American Male - Eric"),
    ("am_fenrir", "Kokoro - American Male - Fenrir"),
    ("am_liam", "Kokoro - American Male - Liam"),
    ("am_michael", "Kokoro - American Male - Michael"),
    ("am_onyx", "Kokoro - American Male - Onyx"),
    ("am_puck", "Kokoro - American Male - Puck"),
    ("am_santa", "Kokoro - American Male - Santa"),
    ("bf_alice", "Kokoro - British Female - Alice"),
    ("bf_emma", "Kokoro - British Female - Emma"),
    ("bf_isabella", "Kokoro - British Female - Isabella"),
    ("bf_lily", "Kokoro - British Female - Lily"),
    ("bm_daniel", "Kokoro - British Male - Daniel"),
    ("bm_fable", "Kokoro - British Male - Fable"),
    ("bm_george", "Kokoro - British Male - George"),
    ("bm_lewis", "Kokoro - British Male - Lewis"),
]

NODE_LABELS = {
    "HUMAN": "Cozmo / HUMAN",
    "GPT": "GPT / Luma",
    "Gemini": "Gemini",
    "DeepSeek": "DeepSeek / Kelp",
    "Aisha": "Aisha",
    "Claude": "Claude",
    "Grok": "Grok",
    "Chron": "Chron",
    "[ANNOUNCE]": "[ANNOUNCE]",
}

EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),
    (0x1FC00, 0x1FFFF),
    (0x2600, 0x27FF),
)

TIME_IN_ARCHIVE_RE = re.compile(
    r"(?P<prefix>.*?)(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[_ ](?P<day>\d{1,2})[_ ](?P<year>\d{4})[_ ]"
    r"(?P<hour>\d{1,2})[_:](?P<minute>\d{2})[_:](?P<second>\d{2})[_ ]"
    r"(?P<ampm>AM|PM)(?:[_ ]v(?P<version>[\w.\-]+))?",
    re.IGNORECASE,
)

CONVO_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{1,2}-\d{1,2}-\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:am|pm)?)"
    r"\s+(?P<speaker>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass
class Message:
    sequence: int
    timestamp: str
    display_timestamp: str
    speaker: str
    node: str
    text: str
    searchable_text: str = ""

    def __post_init__(self) -> None:
        if not self.searchable_text:
            self.searchable_text = f"{self.speaker}\n{self.text}"


@dataclass
class CardRecord:
    archive: str
    format: str = "1"
    card_file: str = ""
    card_path: str = ""
    card_text: str = ""
    conversation_date: Optional[str] = None
    timestamp: Optional[datetime] = None
    files: list[str] = field(default_factory=list)
    title_files: list[str] = field(default_factory=list)
    summary: str = ""
    conversation_file: Optional[str] = None
    source_kind: str = "remote"
    source_root: str = ""
    global_matches: list[tuple[int, str, str, str]] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.archive

    @property
    def searchable_text(self) -> str:
        return "\n".join(
            [
                self.archive,
                self.card_file,
                self.card_path,
                self.card_text,
                self.summary,
                *self.title_files,
            ]
        ).lower()

    @property
    def has_conversation(self) -> bool:
        return bool(self.conversation_file)

    def display_tab_name(self) -> str:
        if self.timestamp:
            dt = self.timestamp
            version = extract_version(self.archive)
            version_part = f"v{version}" if version else ""
            month = "Sept" if dt.month == 9 else dt.strftime("%b")
            hour12 = dt.strftime("%I").lstrip("0") or "12"
            suffix = dt.strftime("%p")
            if version_part:
                return f"QS{version_part} {month} {dt.day} {hour12}:{dt.strftime('%M')}{suffix}"
            return f"{self.archive[:3]} {month} {dt.day} {hour12}:{dt.strftime('%M')}{suffix}"
        return compact_tab_name(self.archive)

    def card_header_text(self) -> str:
        lines = [
            f"ARCHIVE: {self.archive}",
            f"DATE: {self.conversation_date or 'UNKNOWN'}",
        ]
        if self.timestamp:
            lines.append(f"ARCHIVE TIME: {self.timestamp.strftime('%Y-%m-%d %I:%M:%S %p')}")
        return "\n".join(lines)

    def card_presentation_text(self) -> str:
        """Parse the indexed card_text into a deliberate presentation order.

        The archive itself is never rewritten.  This is presentation-only:
        summary first, then .title files, then the remaining indexed files.
        """
        parts: list[str] = []

        if self.summary:
            parts.append("LUMA SUMMARY:\n" + self.summary)

        title_files = [
            name for name in self.files
            if name.lower().endswith(".title")
        ]
        other_files = [
            name for name in self.files
            if not name.lower().endswith(".title")
        ]

        if title_files:
            parts.append(
                "TITLE FILES:\n" + "\n".join(f"  {name}" for name in title_files)
            )

        if other_files:
            parts.append(
                "FILES:\n" + "\n".join(f"  {name}" for name in other_files)
            )
        elif not parts:
            parts.append("FILES:\n  (none)")

        return "\n\n".join(parts)


def extract_version(text: str) -> str:
    match = re.search(r"_v([\w.\-]+)$", text)
    return match.group(1) if match else ""


def compact_tab_name(text: str, max_len: int = 25) -> str:
    value = text.replace("_", " ").replace("  ", " ").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


def normalize_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return url

    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme:
        return url

    quoted_path = urllib.parse.quote(
        urllib.parse.unquote(parsed.path),
        safe="/:@!$&'()*+,;=-._~%",
    )
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            quoted_path,
            parsed.query,
            parsed.fragment,
        )
    )


def github_blob_to_raw(url: str) -> str:
    url = normalize_url(url)
    parsed = urllib.parse.urlsplit(url)
    if parsed.netloc.lower() != "github.com":
        return url

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        path_parts = parts[4:]
        raw_path = "/".join(path_parts)
        return (
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
            + urllib.parse.quote(
                urllib.parse.unquote(raw_path),
                safe="/:@!$&'()*+,;=-._~%",
            )
        )

    return url


def url_join_file(base_dir: str, relative_path: str) -> str:
    rel = urllib.parse.quote(
        relative_path.replace("\\", "/"),
        safe="/:@!$&'()*+,;=-._~%",
    )
    if not base_dir.endswith("/"):
        base_dir += "/"
    return urllib.parse.urljoin(base_dir, rel)


def parse_archive_datetime(name: str) -> Optional[datetime]:
    match = TIME_IN_ARCHIVE_RE.search(name)
    if not match:
        return None
    try:
        month = datetime.strptime(match.group("mon")[:3].title(), "%b").month
        hour = int(match.group("hour"))
        if match.group("ampm").upper() == "PM" and hour != 12:
            hour += 12
        if match.group("ampm").upper() == "AM" and hour == 12:
            hour = 0
        return datetime(
            int(match.group("year")),
            month,
            int(match.group("day")),
            hour,
            int(match.group("minute")),
            int(match.group("second")),
        )
    except ValueError:
        return None


def parse_card_date(card_text: str) -> Optional[str]:
    match = re.search(r"Conversation date:\s*(\S+)", card_text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def parse_card_files(card_text: str) -> list[str]:
    lines = card_text.splitlines()
    files: list[str] = []
    in_files = False
    for raw in lines:
        line = raw.strip()
        if line.upper() == "FILES:":
            in_files = True
            continue
        if in_files:
            if not line:
                break
            if line.endswith(":"):
                break
            if line.startswith("<"):
                break
            files.append(line)
    return files


def parse_card_summary(card_text: str) -> str:
    match = re.search(
        r"(?ims)^LUMA SUMMARY:\s*(.*?)(?=\n[A-Z][A-Z _-]{2,}:|\Z)",
        card_text,
    )
    if not match:
        return ""
    return match.group(1).strip()


def card_from_index(entry: dict[str, Any], source_kind: str, source_root: str) -> CardRecord:
    archive = str(entry.get("archive", "")).strip()
    card_text = str(entry.get("card_text", "") or "")
    parsed_files = parse_card_files(card_text)
    files = parsed_files or list(entry.get("files") or [])
    card_file = str(entry.get("card_file", "") or "")
    card_path = str(entry.get("card_path", "") or "")
    raw_conversation_date = str(
        entry.get("conversation_date")
        or parse_card_date(card_text)
        or ""
    ).strip()
    conversation_date = (
        None
        if raw_conversation_date.upper() in {"", "UNKNOWN", "N/A", "NONE"}
        else raw_conversation_date
    )

    title_files = [f for f in files if f.lower().endswith(".title")]

    conversation_file = None
    for candidate in files:
        if candidate.lower().endswith(".convo.json"):
            conversation_file = candidate
            break
    if conversation_file is None:
        for candidate in files:
            if candidate.lower().endswith(".convo"):
                conversation_file = candidate
                break

    return CardRecord(
        archive=archive,
        format=str(entry.get("format", "1")),
        card_file=card_file,
        card_path=card_path,
        card_text=card_text,
        conversation_date=conversation_date,
        timestamp=parse_archive_datetime(archive),
        files=files,
        title_files=title_files,
        summary=parse_card_summary(card_text),
        conversation_file=conversation_file,
        source_kind=source_kind,
        source_root=source_root,
    )


def strip_emoji(value: str) -> str:
    out: list[str] = []
    for ch in str(value or ""):
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in EMOJI_RANGES):
            continue
        if cp in {0xFE0E, 0xFE0F, 0x200D, 0x20E3}:
            continue
        out.append(ch)
    return "".join(out)


def canonical_node(speaker: str) -> str:
    raw = str(speaker or "").strip()
    lower = raw.lower()

    if lower.startswith("[announce"):
        return "[ANNOUNCE]"

    clean = strip_emoji(raw)
    clean = clean.replace("[", " ").replace("]", " ")
    clean = re.sub(r"[^\w@/ -]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    lc = clean.lower()

    if "cozmo" in lc or lc in {"human", "you", "operator"}:
        return "HUMAN"
    if "gpt" in lc or "chatgpt" in lc or "luma" in lc:
        return "GPT"
    if "gemini" in lc:
        return "Gemini"
    if "deepseek" in lc or "kelp" in lc:
        return "DeepSeek"
    if "aisha" in lc:
        return "Aisha"
    if "claude" in lc:
        return "Claude"
    if "grok" in lc:
        return "Grok"
    if "chron" in lc:
        return "Chron"

    return clean or raw or "UNKNOWN"


def node_label(node: str) -> str:
    return NODE_LABELS.get(node, node)


def load_json_text(text: str) -> Any:
    return json.loads(text)


def load_index_from_text(text: str) -> tuple[list[CardRecord], dict[str, Any]]:
    data = load_json_text(text)
    cards_data = data.get("cards", []) if isinstance(data, dict) else []
    if not isinstance(cards_data, list):
        raise ValueError("MASTER_INDEX JSON does not contain a list named 'cards'.")

    cards = [
        card_from_index(item, "remote", "")
        for item in cards_data
        if isinstance(item, dict)
    ]

    meta = data.get("master_index", {}) if isinstance(data, dict) else {}
    return cards, meta


def parse_convo_json(data: Any) -> list[Message]:
    if not isinstance(data, dict):
        raise ValueError("Conversation JSON is not an object.")
    raw_messages = data.get("messages", [])
    if not isinstance(raw_messages, list):
        raise ValueError("Conversation JSON does not contain a 'messages' list.")

    messages: list[Message] = []
    for idx, raw in enumerate(raw_messages, start=1):
        if not isinstance(raw, dict):
            continue
        speaker = str(raw.get("speaker", "") or "")
        text = str(raw.get("text", "") or "")
        seq = int(raw.get("sequence", idx) or idx)
        timestamp = str(raw.get("timestamp", "") or "")
        display_timestamp = str(
            raw.get("display_timestamp", "") or timestamp
        )
        messages.append(
            Message(
                sequence=seq,
                timestamp=timestamp,
                display_timestamp=display_timestamp,
                speaker=speaker,
                node=canonical_node(speaker),
                text=text,
            )
        )
    return messages


def parse_convo_text(text: str) -> list[Message]:
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.strip() == "<CONVO HEADER END>":
            start = i + 1
            break

    messages: list[Message] = []
    current_header: Optional[re.Match[str]] = None
    current_text: list[str] = []
    sequence = 0

    def flush() -> None:
        nonlocal sequence, current_header, current_text
        if not current_header:
            return
        sequence += 1
        timestamp = current_header.group("timestamp").strip()
        speaker = current_header.group("speaker").strip()
        body = "\n".join(current_text).strip()
        messages.append(
            Message(
                sequence=sequence,
                timestamp=timestamp,
                display_timestamp=timestamp,
                speaker=speaker,
                node=canonical_node(speaker),
                text=body,
            )
        )
        current_header = None
        current_text = []

    for line in lines[start:]:
        if line.strip("=") == "" and set(line.strip()) == {"="}:
            flush()
            continue
        match = CONVO_LINE_RE.match(line.strip())
        if match:
            flush()
            current_header = match
            current_text = []
        elif current_header:
            current_text.append(line)

    flush()
    return messages


def parse_conversation_bytes(data: bytes, suffix: str) -> list[Message]:
    text = data.decode("utf-8", errors="replace")
    if suffix.lower().endswith(".json"):
        return parse_convo_json(load_json_text(text))
    return parse_convo_text(text)


def read_local_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def fetch_url_text(url: str, timeout: int = 30) -> str:
    normalized = github_blob_to_raw(url)
    req = urllib.request.Request(
        normalized,
        headers={
            "User-Agent": "QSR/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_url_bytes(url: str, timeout: int = 30) -> bytes:
    normalized = github_blob_to_raw(url)
    req = urllib.request.Request(
        normalized,
        headers={"User-Agent": "QSR/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def default_config() -> dict[str, Any]:
    return {
        "version": VERSION,
        "index_source": DEFAULT_INDEX_SOURCE,
        "current_card": "",
        "node_voices": {},
        "node_portraits": {},
        "card_font_size": 11,
        "card_scheme": "dark",
        "replay_font_size": 18,
        "replay_scheme": "dark",
        "voice_on": True,
        "archive_dir_name": ARCHIVE_DIR_NAME,
        "voice_dir_name": VOICE_DIR_NAME,
        "portrait_dir_name": PORTRAIT_DIR_NAME,
    }


def ensure_config(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        cfg = default_config()
        path.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return cfg, True

    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        cfg = default_config()

    if not isinstance(cfg, dict):
        cfg = default_config()

    defaults = default_config()
    changed = False
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = value
            changed = True

    if changed:
        path.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return cfg, changed


def save_config(path: Path, cfg: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def make_qsr_session_archive(start_dir: Path, config_path: Path) -> Path:
    archive_root = start_dir / ARCHIVE_DIR_NAME
    archive_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%b %d %Y %I_%M_%S_%p")
    session_dir = archive_root / f"{SESSION_ARCHIVE_PREFIX}_{stamp}_v{VERSION}"
    suffix = 2
    while session_dir.exists():
        session_dir = archive_root / (
            f"{SESSION_ARCHIVE_PREFIX}_{stamp}_v{VERSION}_{suffix}"
        )
        suffix += 1
    session_dir.mkdir(parents=True, exist_ok=False)

    source = Path(sys.argv[0]).resolve()
    if source.exists() and source.is_file():
        try:
            shutil.copy2(source, session_dir / source.name)
        except Exception:
            pass

    if config_path.exists():
        try:
            shutil.copy2(config_path, session_dir / config_path.name)
        except Exception:
            pass

    (session_dir / "LOG.txt").touch()
    return session_dir


def choose_latest_card(cards: list[CardRecord]) -> Optional[CardRecord]:
    if not cards:
        return None

    def key(card: CardRecord) -> tuple[int, datetime]:
        when = card.timestamp or datetime.min
        has_convo = 1 if card.has_conversation else 0
        return has_convo, when

    return max(cards, key=key)


class QSRLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._lock = threading.RLock()

    def log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp} [{level.upper()}] {message}"
        with self._lock:
            try:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass
        print(line)


def make_raw_index_source(source: str) -> str:
    return github_blob_to_raw(source.strip())


def parse_local_index_source(source: str) -> Optional[Path]:
    candidate = Path(os.path.expandvars(os.path.expanduser(source.strip())))
    if candidate.exists():
        return candidate.resolve()
    return None


class ArchiveSource:
    def __init__(self, source: str):
        self.source = source
        self.is_remote = bool(
            urllib.parse.urlsplit(source).scheme in {"http", "https"}
        )

        self.raw_index_url = ""
        self.local_index_path: Optional[Path] = None

        if self.is_remote:
            self.raw_index_url = make_raw_index_source(source)
        else:
            self.local_index_path = parse_local_index_source(source)
            if self.local_index_path is None:
                raise FileNotFoundError(f"Index source was not found: {source}")

    def load_index(self) -> tuple[list[CardRecord], dict[str, Any]]:
        if self.is_remote:
            text = fetch_url_text(self.raw_index_url)
            cards, meta = load_index_from_text(text)
            base = self.raw_index_url.rsplit("/", 1)[0] + "/"
            for card in cards:
                card.source_kind = "remote"
                card.source_root = base
            return cards, meta

        assert self.local_index_path is not None
        text = read_local_text(self.local_index_path)
        data = load_json_text(text)
        cards_data = data.get("cards", []) if isinstance(data, dict) else []
        meta = data.get("master_index", {}) if isinstance(data, dict) else {}
        root = str(self.local_index_path.parent)
        cards = [
            card_from_index(item, "local", root)
            for item in cards_data
            if isinstance(item, dict)
        ]
        return cards, meta

    def card_conversation_location(self, card: CardRecord) -> Optional[tuple[str, str]]:
        if not card.conversation_file:
            return None

        if self.is_remote:
            # MASTER_INDEX card_path values are paths to the CARD file, not the
            # archive directory. Conversation files live under the archive-named
            # directory, so use card.archive explicitly.
            base = card.source_root
            return "remote", url_join_file(
                base,
                f"{card.archive}/{card.conversation_file}",
            )

        root = Path(card.source_root)
        # Prefer the canonical archive directory. This is the same layout used
        # by the QS archive and works even when card_path is only a filename.
        candidate_dir = root / card.archive
        candidate = candidate_dir / card.conversation_file
        if candidate.exists():
            return "local", str(candidate)

        # Fallback for a local index whose card_path actually carries a nested
        # directory location.
        if card.card_path:
            card_path = root / card.card_path
            candidate = card_path.parent / card.conversation_file
            if candidate.exists():
                return "local", str(candidate)

        return "local", str(candidate_dir / card.conversation_file)


def card_archive_dir_relative(card: CardRecord) -> str:
    if card.card_path:
        path = Path(card.card_path.replace("\\", "/"))
        return str(path.parent).replace("\\", "/")
    return card.archive


class ConversationRepository:
    def __init__(self):
        self.cache: dict[str, list[Message]] = {}
        self.cache_lock = threading.RLock()

    def load(self, location_kind: str, location: str) -> list[Message]:
        key = f"{location_kind}:{location}"
        with self.cache_lock:
            if key in self.cache:
                return self.cache[key]

        if location_kind == "remote":
            data = fetch_url_bytes(location)
        else:
            data = Path(location).read_bytes()

        messages = parse_conversation_bytes(data, location)
        with self.cache_lock:
            self.cache[key] = messages
        return messages


class VoiceCatalog:
    def __init__(self, start_dir: Path):
        self.start_dir = start_dir
        self.voice_dir = self.start_dir / VOICE_DIR_NAME
        self.custom: dict[str, tuple[str, Path]] = {}
        self.refresh()

    def refresh(self) -> None:
        self.custom.clear()
        if not self.voice_dir.exists():
            return

        for path in sorted(self.voice_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                style = raw.get("style") if isinstance(raw, dict) else None
                if isinstance(style, list) and len(style) == 256:
                    voice_id = path.stem
                    label = friendly_custom_voice_label(voice_id)
                    self.custom[voice_id] = (label, path)
            except Exception:
                continue

    def choices(self) -> list[tuple[str, str]]:
        standard = list(STANDARD_KOKORO_VOICES)
        custom = [
            (voice_id, label)
            for voice_id, (label, _path) in sorted(
                self.custom.items(),
                key=lambda item: item[1][0].lower(),
            )
        ]
        return standard + custom

    def label_for(self, voice_id: str) -> str:
        for ident, label in self.choices():
            if ident == voice_id:
                return label
        return voice_id

    def path_for_custom(self, voice_id: str) -> Optional[Path]:
        item = self.custom.get(voice_id)
        return item[1] if item else None


def friendly_custom_voice_label(voice_id: str) -> str:
    value = voice_id.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return "Kokoro - Custom"
    return f"Kokoro - Custom - {value.title()}"


class PortraitCatalog:
    def __init__(self, start_dir: Path):
        self.start_dir = start_dir
        self.portrait_dir = self.start_dir / PORTRAIT_DIR_NAME
        self.refresh()

    def refresh(self) -> None:
        self.files = []
        if self.portrait_dir.exists():
            self.files = sorted(
                [p for p in self.portrait_dir.glob("*.png") if p.is_file()],
                key=lambda p: p.name.lower(),
            )

    def choices(self) -> list[str]:
        return ["[none]"] + [p.name for p in self.files]

    def path_for(self, filename: str) -> Optional[Path]:
        if not filename or filename == "[none]":
            return None
        candidate = self.portrait_dir / filename
        if candidate.exists() and candidate.is_file():
            return candidate
        return None


def clean_speech_text(text: str) -> str:
    value = str(text or "")
    out = []
    for ch in value:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in EMOJI_RANGES):
            continue
        if cp in {0xFE0E, 0xFE0F, 0x200D, 0x20E3}:
            continue
        out.append(ch)
    cleaned = "".join(out)
    cleaned = re.sub(r"(?m)^\s*={5,}\s*$", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


class KokoroEngine:
    """Lazy Kokoro engine with cached English-language pipelines.

    Standard voices use their Kokoro language family (a=American, b=British).
    Custom extracted styles currently use the American English pipeline because
    the extracted voice assets are English/American-style assets.
    """

    def __init__(self, voice_catalog: VoiceCatalog, logger: QSRLogger):
        self.voice_catalog = voice_catalog
        self.logger = logger
        self.ready = False
        self.device_name = "cpu"
        self._torch = None
        self._np = None
        self._sd = None
        self._KPipeline = None
        self._pipelines: dict[str, Any] = {}
        self._pipeline_models: dict[str, Any] = {}
        self.style_cache: dict[str, Any] = {}
        self.lock = threading.RLock()
        self.tts_stop_event = threading.Event()
        self.speaking = False

    def ensure_ready(self) -> None:
        with self.lock:
            if self.ready:
                return
            self.logger.log("INFO", "Loading Kokoro voice engine modules.")
            try:
                import numpy as np
                import sounddevice as sd
                import torch
                from kokoro import KPipeline

                self._np = np
                self._sd = sd
                self._torch = torch
                self._KPipeline = KPipeline

                self.ready = True
                self.logger.log("INFO", "Kokoro voice engine modules ready.")
            except Exception as exc:
                self.logger.log(
                    "ERROR",
                    f"Kokoro initialization failed: {type(exc).__name__}: {exc}",
                )
                raise

    def _get_pipeline(self, lang: str):
        with self.lock:
            self.ensure_ready()
            if lang not in self._pipelines:
                self.logger.log(
                    "INFO",
                    f"Loading Kokoro pipeline language '{lang}'.",
                )
                pipeline = self._KPipeline(
                    lang_code=lang,
                    repo_id="hexgrad/Kokoro-82M",
                )
                self._pipelines[lang] = pipeline
                self._pipeline_models[lang] = pipeline.model
                self.device_name = str(
                    getattr(pipeline.model, "device", "cpu")
                )
                self.logger.log(
                    "INFO",
                    f"Kokoro pipeline '{lang}' ready on {self.device_name}.",
                )
            return self._pipelines[lang]

    def _load_custom_style(self, voice_id: str):
        if voice_id in self.style_cache:
            return self.style_cache[voice_id]
        path = self.voice_catalog.path_for_custom(voice_id)
        if path is None:
            raise FileNotFoundError(
                f"Custom voice asset '{voice_id}' was not found under voices\\."
            )
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        style = self._torch.tensor(
            data["style"],
            dtype=self._torch.float32,
            device="cuda" if self._torch.cuda.is_available() else "cpu",
        )
        if style.dim() == 1:
            style = style.unsqueeze(0)
        if tuple(style.shape) != (1, 256):
            raise ValueError(
                f"Custom style '{path.name}' has shape {tuple(style.shape)}; "
                "expected (1, 256)."
            )
        self.style_cache[voice_id] = style
        return style

    def _prepare_custom_inference(self, model) -> None:
        for _name_mod, module in model.named_modules():
            if isinstance(
                module,
                (
                    self._torch.nn.LSTM,
                    self._torch.nn.GRU,
                    self._torch.nn.RNN,
                ),
            ):
                module.train()

    def _get_phoneme_chunks(self, pipeline, text: str) -> list[str]:
        cleaned = clean_speech_text(text)
        chunks = []
        for result in pipeline(cleaned, voice="af_bella", speed=1.0):
            phonemes = getattr(result, "phonemes", None)
            if phonemes:
                chunks.append(phonemes)
        return chunks

    def _custom_forward(self, model, phonemes_str: str, ref_s, speed: float = 1.0):
        input_ids = list(
            filter(
                lambda i: i is not None,
                map(lambda p: model.vocab.get(p), phonemes_str),
            )
        )
        input_ids = self._torch.LongTensor([[0, *input_ids, 0]]).to(
            model.device
        )
        n = input_ids.shape[1]
        input_lengths = self._torch.full(
            (1,),
            n,
            device=model.device,
            dtype=self._torch.long,
        )
        text_mask = self._torch.arange(
            n,
            device=model.device,
        ).unsqueeze(0)
        text_mask = self._torch.gt(
            text_mask + 1,
            input_lengths.unsqueeze(1),
        )

        bert_dur = model.bert(
            input_ids,
            attention_mask=(~text_mask).int(),
        )
        d_en = model.bert_encoder(bert_dur).transpose(-1, -2)

        s = ref_s[:, 128:]
        d = model.predictor.text_encoder(
            d_en,
            s,
            input_lengths,
            text_mask,
        )
        x, _ = model.predictor.lstm(d)
        dur = model.predictor.duration_proj(x)
        dur = self._torch.sigmoid(dur).sum(axis=-1) / speed
        pred_dur = self._torch.round(dur).clamp(min=1).long().squeeze()

        indices = self._torch.repeat_interleave(
            self._torch.arange(
                n,
                device=model.device,
            ),
            pred_dur,
        )
        pred_aln = self._torch.zeros(
            (n, indices.shape[0]),
            device=model.device,
        )
        pred_aln[
            indices,
            self._torch.arange(
                indices.shape[0],
                device=model.device,
            ),
        ] = 1
        pred_aln = pred_aln.unsqueeze(0)

        en = d.transpose(-1, -2) @ pred_aln
        F0_pred, N_pred = model.predictor.F0Ntrain(en, s)

        t_en = model.text_encoder(
            input_ids,
            input_lengths,
            text_mask,
        )
        asr = t_en @ pred_aln

        return model.decoder(
            asr,
            F0_pred,
            N_pred,
            ref_s[:, :128],
        ).squeeze()

    def stop_current(self) -> None:
        """Interrupt current Kokoro audio without changing replay position."""
        self.tts_stop_event.set()
        try:
            if self._sd is not None:
                self._sd.stop()
        except Exception:
            pass

    def speak(self, text: str, voice_id: str) -> None:
        if not str(text).strip():
            return

        self.tts_stop_event.clear()
        self.speaking = True
        try:
            with self.lock:
                self.ensure_ready()
                if self.tts_stop_event.is_set():
                    return
    
                if voice_id in self.voice_catalog.custom:
                    pipeline = self._get_pipeline("a")
                    model = pipeline.model
                    self._prepare_custom_inference(model)
                    style = self._load_custom_style(voice_id)
                    chunks = self._get_phoneme_chunks(pipeline, text)
                    if not chunks:
                        raise RuntimeError(
                            "Kokoro produced no phonemes for custom voice."
                        )
    
                    audio_chunks = []
                    with self._torch.no_grad():
                        for phonemes in chunks:
                            audio = self._custom_forward(
                                model,
                                phonemes,
                                style,
                                1.0,
                            )
                            audio_chunks.append(
                                audio.detach().cpu().numpy()
                            )
    
                    audio_np = self._np.concatenate(audio_chunks)
                else:
                    lang = voice_id[0] if voice_id[:1] in {"a", "b"} else "a"
                    pipeline = self._get_pipeline(lang)
                    cleaned = clean_speech_text(text)
                    if not cleaned:
                        return
    
                    audio_chunks = []
                    for result in pipeline(
                        cleaned,
                        voice=voice_id,
                        speed=1.0,
                    ):
                        audio = getattr(result, "audio", None)
                        if audio is None:
                            continue
                        if hasattr(audio, "detach"):
                            audio = audio.detach().cpu().numpy()
                        else:
                            audio = self._np.asarray(audio)
                        audio_chunks.append(audio)
    
                    if not audio_chunks:
                        raise RuntimeError(
                            "Kokoro produced no audio for standard voice."
                        )
                    audio_np = self._np.concatenate(audio_chunks)
    
                if self.tts_stop_event.is_set():
                    return
                self._sd.play(audio_np, 24000)
                self._sd.wait()
        finally:
            self.speaking = False


class QSRApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"QS_Replay {VERSION}")
        self.root.geometry("1450x900")
        self.root.minsize(1100, 700)

        self.start_dir = Path(sys.argv[0]).resolve().parent
        self.config_path = self.start_dir / CONFIG_NAME
        self.config, _ = ensure_config(self.config_path)

        self.session_archive = make_qsr_session_archive(
            self.start_dir,
            self.config_path,
        )
        self.logger = QSRLogger(self.session_archive / "LOG.txt")
        self.logger.log("INFO", f"{PROGRAM_NAME} {VERSION} STARTING.")
        self.logger.log("INFO", f"STARTDIR: {self.start_dir}")
        self.logger.log("INFO", f"SESSION ARCHIVE: {self.session_archive}")

        self.voice_catalog = VoiceCatalog(self.start_dir)
        self.portrait_catalog = PortraitCatalog(self.start_dir)
        self.voice_engine = KokoroEngine(self.voice_catalog, self.logger)

        self.repo = ConversationRepository()

        self.index_source = str(
            self.config.get("index_source") or DEFAULT_INDEX_SOURCE
        )

        self.all_cards: list[CardRecord] = []
        self.current_index: list[CardRecord] = []
        self.current_card: Optional[CardRecord] = None
        self.current_messages: list[Message] = []
        self.current_message_index = 0
        self.global_matches: dict[str, list[tuple[int, str, str, str]]] = {}

        self.catalog_filter_active = False
        self.catalog_filter_search = ""
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""

        self.voice_on_var = tk.BooleanVar(
            value=bool(self.config.get("voice_on", True))
        )
        self.search_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.exact_var = tk.StringVar()
        self.index_var = tk.StringVar(value=self.index_source)
        self.card_font_var = tk.IntVar(
            value=int(self.config.get("card_font_size", 11))
        )
        self.replay_font_var = tk.IntVar(
            value=int(self.config.get("replay_font_size", 18))
        )
        self.card_scheme_var = tk.StringVar(
            value=(str(self.config.get("card_scheme", "dark") or "dark")
                   if str(self.config.get("card_scheme", "dark") or "dark") in SCHEME_CHOICES
                   else "dark")
        )
        self.replay_scheme_var = tk.StringVar(
            value=(str(self.config.get("replay_scheme", "dark") or "dark")
                   if str(self.config.get("replay_scheme", "dark") or "dark") in SCHEME_CHOICES
                   else "dark")
        )
        self.status_var = tk.StringVar(value="Starting…")
        self.replay_status_var = tk.StringVar(value="No conversation loaded.")

        self.voice_vars: dict[str, tk.StringVar] = {}
        self.portrait_vars: dict[str, tk.StringVar] = {}
        self.portrait_images: dict[str, tk.PhotoImage] = {}

        self.is_playing = False
        self.stop_event = threading.Event()
        self.player_thread: Optional[threading.Thread] = None
        self.replay_lock = threading.RLock()
        self.is_speaking = False
        self.speech_stop_requested = threading.Event()

        self.catalog_notebook: Optional[ttk.Notebook] = None
        self.catalog_tab_cards: dict[str, CardRecord] = {}
        self.catalog_tab_frames: dict[str, ttk.Frame] = {}
        self.catalog_view_font = font.Font(
            family="Segoe UI",
            size=int(self.card_font_var.get()),
        )
        self.replay_view_font = font.Font(
            family="Segoe UI",
            size=int(self.replay_font_var.get()),
        )
        self.bold_font = font.Font(
            family="Segoe UI",
            size=max(9, int(self.card_font_var.get()) + 1),
            weight="bold",
        )
        self.replay_bold_font = font.Font(
            family="Segoe UI",
            size=max(10, int(self.replay_font_var.get()) + 1),
            weight="bold",
        )

        self.build_ui()
        self.root.after(100, self.initial_load)

    # ---------------------------------------------------------------
    # UI
    # ---------------------------------------------------------------

    def build_ui(self) -> None:
        # Set the ttk default font through ttk.Style rather than the Tk option database.
        # The option database interprets the two-word font family incorrectly for ttk
        # widgets on this environment and raises: expected integer but got "UI".
        self.ttk_style = ttk.Style(self.root)
        try:
            self.ttk_style.theme_use("clam")
        except Exception:
            pass
        try:
            self.ttk_style.configure(".", font=("Segoe UI", 10))
        except Exception:
            self.ttk_style.configure(".", font=("TkDefaultFont", 10))

        self.apply_base_dark_ui()

        outer = ttk.Frame(self.root, padding=6)
        outer.pack(fill="both", expand=True)

        self.main_notebook = ttk.Notebook(outer)
        self.main_notebook.pack(fill="both", expand=True)

        self.catalog_page = ttk.Frame(self.main_notebook)
        self.replay_page = ttk.Frame(self.main_notebook)

        self.main_notebook.add(self.catalog_page, text="CATALOG")
        self.main_notebook.add(self.replay_page, text="REPLAY / READER")

        self.build_catalog_page()
        self.build_replay_page()
        self.apply_card_scheme()
        self.apply_replay_scheme()

        status = ttk.Label(
            outer,
            textvariable=self.status_var,
            anchor="w",
            relief="sunken",
            padding=(5, 2),
        )
        status.pack(fill="x", pady=(5, 0))

    def build_catalog_page(self) -> None:
        top = ttk.Frame(self.catalog_page)
        top.pack(fill="x", padx=4, pady=4)

        index_row = ttk.Frame(top)
        index_row.pack(fill="x", pady=(0, 4))

        ttk.Label(index_row, text="INDEX SOURCE:").pack(side="left")
        self.index_entry = ttk.Entry(
            index_row,
            textvariable=self.index_var,
        )
        self.index_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.index_entry.state(["disabled"])

        self.load_index_btn = ttk.Button(
            index_row,
            text="LOAD INDEX",
            command=self.on_load_index,
        )
        self.load_index_btn.pack(side="left", padx=3)
        self.load_index_btn.state(["disabled"])

        filter_row = ttk.Frame(top)
        filter_row.pack(fill="x", pady=2)

        ttk.Label(filter_row, text="DATE:").pack(side="left")
        ttk.Entry(
            filter_row,
            textvariable=self.date_var,
            width=14,
        ).pack(side="left", padx=(3, 8))

        ttk.Label(filter_row, text="TIME:").pack(side="left")
        ttk.Entry(
            filter_row,
            textvariable=self.time_var,
            width=11,
        ).pack(side="left", padx=(3, 3))

        ttk.Button(
            filter_row,
            text="CLEAR DATE/TIME",
            command=self.clear_date_time_filters,
        ).pack(side="left", padx=(0, 8))

        ttk.Label(filter_row, text="SEARCH:").pack(side="left")
        self.search_entry = ttk.Entry(
            filter_row,
            textvariable=self.search_var,
            width=28,
        )
        self.search_entry.pack(side="left", padx=(3, 5))

        ttk.Button(
            filter_row,
            text="APPLY CATALOG FILTER",
            command=self.apply_catalog_filter,
        ).pack(side="left", padx=2)

        ttk.Button(
            filter_row,
            text="RESET CATALOG",
            command=self.reset_catalog,
        ).pack(side="left", padx=2)

        ttk.Button(
            filter_row,
            text="GLOBAL SEARCH",
            command=self.global_search,
        ).pack(side="left", padx=2)

        ttk.Button(
            filter_row,
            text="CLEAR SEARCH",
            command=self.clear_search,
        ).pack(side="left", padx=2)

        exact_row = ttk.Frame(top)
        exact_row.pack(fill="x", pady=(4, 0))

        ttk.Label(exact_row, text="EXACT CONVO:").pack(side="left")
        ttk.Entry(
            exact_row,
            textvariable=self.exact_var,
        ).pack(side="left", fill="x", expand=True, padx=5)

        ttk.Button(
            exact_row,
            text="BROWSE",
            command=self.browse_exact,
        ).pack(side="left", padx=2)

        ttk.Button(
            exact_row,
            text="OPEN EXACT",
            command=self.open_exact,
        ).pack(side="left", padx=2)

        options = ttk.Frame(top)
        options.pack(fill="x", pady=(4, 0))

        ttk.Label(options, text="CARD FONT:").pack(side="left")
        card_font_box = ttk.Spinbox(
            options,
            from_=9,
            to=30,
            textvariable=self.card_font_var,
            width=4,
            command=self.apply_card_font,
        )
        card_font_box.pack(side="left", padx=(3, 5))
        card_font_box.bind("<Return>", lambda _e: self.apply_card_font())

        ttk.Label(options, text="SCHEME:").pack(side="left", padx=(0, 3))
        self.card_scheme_box = ttk.Combobox(
            options,
            textvariable=self.card_scheme_var,
            values=SCHEME_CHOICES,
            state="readonly",
            width=8,
        )
        self.card_scheme_box.pack(side="left", padx=(0, 12))
        self.card_scheme_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_card_scheme())

        self.prev_card_btn = ttk.Button(
            options,
            text="◀ PREV CARD",
            command=self.prev_card,
        )
        self.prev_card_btn.pack(side="left", padx=(12, 2))

        self.card_nav_label = ttk.Label(
            options,
            text="CARD 0 / 0",
        )
        self.card_nav_label.pack(side="left", padx=4)

        self.next_card_btn = ttk.Button(
            options,
            text="NEXT CARD ▶",
            command=self.next_card,
        )
        self.next_card_btn.pack(side="left", padx=2)

        self.catalog_info_label = ttk.Label(
            options,
            text="Catalog: not loaded",
        )
        self.catalog_info_label.pack(side="left", padx=(10, 0))

        catalog_frame = ttk.Frame(self.catalog_page, padding=(4, 0, 4, 4))
        catalog_frame.pack(fill="both", expand=True)

        self.catalog_notebook = ttk.Notebook(catalog_frame)
        self.catalog_notebook.pack(fill="both", expand=True)
        self.catalog_notebook.bind("<<NotebookTabChanged>>", self.on_catalog_tab_changed)

    def build_replay_page(self) -> None:
        top = ttk.Frame(self.replay_page, padding=5)
        top.pack(fill="x")

        title_row = ttk.Frame(top)
        title_row.pack(fill="x")

        self.replay_title_label = ttk.Label(
            title_row,
            text="No conversation loaded",
            font=("Segoe UI", 12, "bold"),
        )
        self.replay_title_label.pack(side="left", fill="x", expand=True)

        ttk.Checkbutton(
            title_row,
            text="VOICE ON",
            variable=self.voice_on_var,
            command=self.on_voice_toggle,
        ).pack(side="right", padx=4)

        controls = ttk.Frame(top)
        controls.pack(fill="x", pady=(5, 0))

        self.play_btn = ttk.Button(
            controls,
            text="PLAY",
            command=self.start_playback,
        )
        self.play_btn.pack(side="left", padx=2)

        self.pause_btn = ttk.Button(
            controls,
            text="PAUSE",
            command=self.pause_playback,
        )
        self.pause_btn.pack(side="left", padx=2)

        self.stop_speaking_btn = ttk.Button(
            controls,
            text="■ STOP SPEAKING",
            command=self.stop_speaking,
        )
        self.stop_speaking_btn.pack(side="left", padx=2)
        self.stop_speaking_btn.state(["disabled"])

        self.prev_btn = ttk.Button(
            controls,
            text="◀ PREV",
            command=self.prev_turn,
        )
        self.prev_btn.pack(side="left", padx=2)

        self.next_btn = ttk.Button(
            controls,
            text="NEXT ▶",
            command=self.next_turn,
        )
        self.next_btn.pack(side="left", padx=2)

        self.replay_font_spin = ttk.Spinbox(
            controls,
            from_=10,
            to=36,
            textvariable=self.replay_font_var,
            width=4,
            command=self.apply_replay_font,
        )
        ttk.Label(controls, text="REPLAY FONT:").pack(side="left", padx=(15, 3))
        self.replay_font_spin.pack(side="left", padx=(0, 5))
        self.replay_font_spin.bind(
            "<Return>",
            lambda _e: self.apply_replay_font(),
        )

        ttk.Label(controls, text="SCHEME:").pack(side="left", padx=(0, 3))
        self.replay_scheme_box = ttk.Combobox(
            controls,
            textvariable=self.replay_scheme_var,
            values=SCHEME_CHOICES,
            state="readonly",
            width=8,
        )
        self.replay_scheme_box.pack(side="left", padx=(0, 8))
        self.replay_scheme_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_replay_scheme())

        self.save_voice_btn = ttk.Button(
            controls,
            text="SAVE VOICE & PORTRAIT SELECTIONS",
            command=self.save_voice_selections,
        )
        self.save_voice_btn.pack(side="left", padx=4)

        self.back_catalog_btn = ttk.Button(
            controls,
            text="◀ BACK TO CATALOG",
            command=self.back_to_catalog,
        )
        self.back_catalog_btn.pack(side="left", padx=4)

        self.voice_dirty_label = ttk.Label(
            controls,
            text="CLEAN",
        )
        self.voice_dirty_label.pack(side="left", padx=4)

        self.replay_status = ttk.Label(
            controls,
            textvariable=self.replay_status_var,
        )
        self.replay_status.pack(side="right")

        body = ttk.Panedwindow(self.replay_page, orient="horizontal")
        body.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        left = ttk.Frame(body, padding=5)
        right = ttk.Frame(body, padding=5)
        body.add(left, weight=1)
        body.add(right, weight=3)

        ttk.Label(
            left,
            text="SPEAKERS / VOICES / PORTRAITS",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        self.speaker_controls_canvas = tk.Canvas(
            left,
            highlightthickness=0,
            borderwidth=0,
        )
        self.speaker_controls_scroll = ttk.Scrollbar(
            left,
            orient="vertical",
            command=self.speaker_controls_canvas.yview,
        )
        self.speaker_controls_frame = ttk.Frame(
            self.speaker_controls_canvas,
        )

        self.speaker_controls_canvas.configure(
            yscrollcommand=self.speaker_controls_scroll.set
        )
        self.speaker_controls_canvas.create_window(
            (0, 0),
            window=self.speaker_controls_frame,
            anchor="nw",
        )

        self.speaker_controls_frame.bind(
            "<Configure>",
            lambda _e: self.speaker_controls_canvas.configure(
                scrollregion=self.speaker_controls_canvas.bbox("all")
            ),
        )

        self.speaker_controls_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.speaker_controls_scroll.pack(
            side="right",
            fill="y",
        )

        ttk.Label(
            right,
            text="REPLAY / READER",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        self.replay_text = ScrolledText(
            right,
            wrap="word",
            undo=False,
            font=self.replay_view_font,
        )
        self.replay_text.pack(fill="both", expand=True)
        self.style_view_text_widget(self.replay_text, self.replay_scheme_var.get(), view="replay")

        self.replay_text.tag_configure(
            "speaker",
            font=self.replay_bold_font,
            spacing1=7,
            spacing3=2,
        )
        self.replay_text.tag_configure(
            "timestamp",
            font=("Segoe UI", 9),
            foreground="#666666",
        )
        self.replay_text.tag_configure(
            "turn",
            spacing1=5,
            spacing3=8,
        )
        self.replay_text.tag_configure(
            "current",
            background="#fff2b2",
        )
        self.replay_text.tag_configure(
            "searchhit",
            background="#bfe7ff",
        )
        self.replay_text.configure(state="disabled")

        self.card_preview_font = font.Font(
            family="Segoe UI",
            size=int(self.card_font_var.get()),
        )

    # ---------------------------------------------------------------
    # Startup / index
    # ---------------------------------------------------------------

    def initial_load(self) -> None:
        try:
            self.load_index_source(self.index_source, initial=True)
            self.index_entry.state(["!disabled"])
            self.load_index_btn.state(["!disabled"])
            self.catalog_info_label.configure(
                text=f"Catalog: {len(self.all_cards)} cards"
            )
            self.status_var.set(
                f"Loaded {len(self.all_cards)} cards. Current: "
                f"{self.current_card.archive if self.current_card else 'none'}"
            )
        except Exception as exc:
            self.logger.log(
                "ERROR",
                f"Initial index load failed: {type(exc).__name__}: {exc}",
            )
            messagebox.showerror(
                "QSR Index Load",
                f"QSR could not load the default index.\n\n{exc}",
            )
            self.status_var.set("Index load failed.")
            self.index_entry.state(["!disabled"])
            self.load_index_btn.state(["!disabled"])

    def on_load_index(self) -> None:
        source = self.index_var.get().strip()
        if not source:
            messagebox.showwarning("QSR", "Please enter an index source.")
            return
        self.load_index_source(source, initial=False)

    def load_index_source(self, source: str, initial: bool = False) -> None:
        source = source.strip()
        self.status_var.set("Loading MASTER_INDEX…")
        self.root.update_idletasks()
        self.logger.log(
            "INFO",
            f"Loading index source: {source}",
        )

        archive_source = ArchiveSource(source)
        cards, meta = archive_source.load_index()

        for card in cards:
            if card.source_kind == "remote":
                card.source_root = archive_source.raw_index_url.rsplit("/", 1)[0] + "/"
            else:
                card.source_root = str(archive_source.local_index_path.parent)

        self.index_source = source
        self.all_cards = cards
        self.current_index = list(cards)
        self.global_matches.clear()

        configured_current = str(self.config.get("current_card") or "").strip()
        # Existing config resumes the last known card. A fresh config has no
        # current_card, so choose_latest_card() gives the most recent
        # conversation-bearing archive rather than the first index entry.
        matched = next(
            (
                card
                for card in cards
                if card.archive == configured_current
                or card.card_path == configured_current
            ),
            None,
        )
        self.current_card = matched or choose_latest_card(cards)

        if self.current_card:
            self.set_filter_defaults_from_current_card()

        self.config["index_source"] = source
        self.index_var.set(source)

        self.catalog_filter_active = False
        self.catalog_filter_search = ""
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""
        self.search_var.set("")

        self.rebuild_catalog_tabs()

        if self.current_card:
            self.select_card(self.current_card)

        meta_count = meta.get("card_count") if isinstance(meta, dict) else None
        self.logger.log(
            "INFO",
            f"Index loaded: {len(cards)} cards; index metadata count={meta_count}.",
        )

        if initial:
            self.logger.log(
                "INFO",
                "Initial index load completed before index-source controls were enabled.",
            )

        self.status_var.set(
            f"Index loaded: {len(cards)} cards. "
            f"Current: {self.current_card.archive if self.current_card else 'none'}"
        )

    def set_filter_defaults_from_current_card(self) -> None:
        if not self.current_card:
            self.date_var.set("")
            self.time_var.set("")
            return

        if self.current_card.conversation_date:
            self.date_var.set(self.current_card.conversation_date)
        elif self.current_card.timestamp:
            self.date_var.set(self.current_card.timestamp.strftime("%Y-%m-%d"))
        else:
            self.date_var.set("")

        if self.current_card.timestamp:
            self.time_var.set(self.current_card.timestamp.strftime("%I:%M %p").lstrip("0"))
        else:
            self.time_var.set("")

    # ---------------------------------------------------------------
    # Catalog / CCU
    # ---------------------------------------------------------------

    def apply_catalog_filter(self, preserve_current_key: Optional[str] = None) -> None:
        date_value = self.date_var.get().strip()
        time_value = self.time_var.get().strip()
        search_value = self.search_var.get().strip()

        self.catalog_filter_active = bool(date_value or time_value or search_value)
        self.catalog_filter_date = date_value
        self.catalog_filter_time = time_value
        self.catalog_filter_search = search_value.lower()
        self.global_matches.clear()

        cards: list[CardRecord] = []
        for card in self.all_cards:
            if date_value and not self.card_matches_date(card, date_value):
                continue
            if time_value and not self.card_matches_time(card, time_value):
                continue
            if search_value and search_value.lower() not in card.searchable_text:
                continue
            cards.append(card)

        self.current_index = cards
        self.current_card = None
        self.logger.log(
            "INFO",
            f"Catalog filter applied: date={date_value!r} time={time_value!r} "
            f"search={search_value!r} -> {len(cards)} cards.",
        )

        self.rebuild_catalog_tabs()

        preserved = None
        if preserve_current_key:
            preserved = next(
                (card for card in cards if card.key == preserve_current_key),
                None,
            )

        if preserved is not None:
            self.select_card(preserved)
        elif cards:
            self.select_card(cards[0])
        else:
            self.clear_card_view()

        self.status_var.set(f"Catalog filter: {len(cards)} matching cards.")

    def card_matches_date(self, card: CardRecord, query: str) -> bool:
        q = query.strip()
        if not q:
            return True

        normalized = q.replace("/", "-")
        if card.conversation_date:
            if card.conversation_date == normalized:
                return True

        if card.timestamp:
            candidates = {
                card.timestamp.strftime("%Y-%m-%d"),
                card.timestamp.strftime("%m-%d-%Y"),
                card.timestamp.strftime("%m/%d/%Y"),
                card.timestamp.strftime("%m/%d/%y"),
                card.timestamp.strftime("%m-%d-%y"),
            }
            return normalized in candidates or q in candidates

        return False

    def card_matches_time(self, card: CardRecord, query: str) -> bool:
        if not card.timestamp:
            return False
        q = query.strip().upper()
        q = re.sub(r"\s+", "", q)

        candidates = {
            card.timestamp.strftime("%I:%M%p").lstrip("0"),
            card.timestamp.strftime("%I:%M%p"),
            card.timestamp.strftime("%H:%M"),
        }
        return q in candidates

    def clear_date_time_filters(self) -> None:
        self.date_var.set("")
        self.time_var.set("")
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""
        self.logger.log("INFO", "Catalog date/time filters cleared.")
        self.status_var.set("Date/time filters cleared. Press APPLY CATALOG FILTER to apply the remaining search filter.")

    def clear_search(self) -> None:
        preserve_key = self.current_card.key if self.current_card else None
        self.search_var.set("")
        self.catalog_filter_search = ""
        self.apply_catalog_filter(preserve_current_key=preserve_key)

    def reset_catalog(self) -> None:
        self.search_var.set("")
        self.date_var.set("")
        self.time_var.set("")
        self.catalog_filter_active = False
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""
        self.catalog_filter_search = ""
        self.current_index = list(self.all_cards)

        # A reset must never jump to card 1 merely because the previous
        # filtered index became empty. Preserve a valid current card; otherwise
        # restore the normal QSR default: the most recent conversation-bearing
        # card by date/time.
        if self.current_card is None or self.current_card not in self.current_index:
            self.current_card = choose_latest_card(self.current_index)

        self.global_matches.clear()
        self.rebuild_catalog_tabs()
        if self.current_card:
            self.select_card(self.current_card)
        else:
            self.clear_card_view()
        self.logger.log("INFO", "Catalog reset to full MASTER_INDEX; date/time/search filters cleared.")
        self.status_var.set(
            f"Catalog reset: {len(self.current_index)} cards. "
            f"Current: {self.current_card.archive if self.current_card else 'none'}"
        )

    def rebuild_catalog_tabs(self) -> None:
        assert self.catalog_notebook is not None

        for child in self.catalog_notebook.tabs():
            self.catalog_notebook.forget(child)

        self.catalog_tab_cards.clear()
        self.catalog_tab_frames.clear()

        for card in self.current_index:
            frame = ttk.Frame(self.catalog_notebook)
            self.catalog_notebook.add(frame, text=card.display_tab_name())
            tab_id = str(frame)
            self.catalog_tab_cards[tab_id] = card
            self.catalog_tab_frames[card.key] = frame
            self.build_card_tab(frame, card)

        if self.current_card and self.current_card.key in self.catalog_tab_frames:
            self.catalog_notebook.select(
                self.catalog_tab_frames[self.current_card.key]
            )

        filter_note = ""
        if self.catalog_filter_active:
            parts = []
            if self.catalog_filter_date:
                parts.append(f"date={self.catalog_filter_date}")
            if self.catalog_filter_time:
                parts.append(f"time={self.catalog_filter_time}")
            if self.catalog_filter_search:
                parts.append(f"search={self.catalog_filter_search}")
            if parts:
                filter_note = " — " + ", ".join(parts)
        if self.global_matches:
            filter_note = " — GLOBAL SEARCH WORKING INDEX"
        self.catalog_info_label.configure(
            text=f"Catalog: {len(self.current_index)} cards{filter_note}"
        )
        self.update_catalog_navigation()

    def build_card_tab(self, frame: ttk.Frame, card: CardRecord) -> None:
        placeholder = ttk.Label(
            frame,
            text="Loading current card…",
            anchor="center",
        )
        placeholder.pack(fill="both", expand=True)
        frame._qsr_card = card  # type: ignore[attr-defined]
        frame._qsr_loaded = False  # type: ignore[attr-defined]
        frame._qsr_placeholder = placeholder  # type: ignore[attr-defined]
        frame._qsr_card_convo_widget = None  # type: ignore[attr-defined]

    def ensure_card_tab_built(self, card: CardRecord) -> None:
        frame = self.catalog_tab_frames.get(card.key)
        if frame is None or getattr(frame, "_qsr_loaded", False):
            return

        for child in frame.winfo_children():
            child.destroy()

        top = ttk.Frame(frame, padding=8)
        top.pack(fill="both", expand=True)

        heading = ttk.Label(
            top,
            text=card.card_header_text(),
            justify="left",
            anchor="w",
            font=self.bold_font,
        )
        heading.pack(fill="x", pady=(0, 5))

        card_text = ScrolledText(
            top,
            wrap="word",
            height=10,
            font=self.catalog_view_font,
        )
        card_text.pack(fill="both", expand=True)
        card_text.insert("1.0", card.card_presentation_text())
        self.style_view_text_widget(card_text, self.card_scheme_var.get(), view="card")
        card_text.configure(state="disabled")

        action_row = ttk.Frame(top)
        action_row.pack(fill="x", pady=(5, 5))

        if card.conversation_file:
            ttk.Button(
                action_row,
                text="OPEN CONVO / REPLAY",
                command=lambda c=card: self.open_card_replay(c),
            ).pack(side="left", padx=2)

        for title_file in card.title_files:
            ttk.Button(
                action_row,
                text=f"OPEN: {title_file}",
                command=lambda c=card: self.open_card_replay(c),
            ).pack(side="left", padx=2)

        match_info = self.global_matches.get(card.key, [])
        if match_info:
            ttk.Label(
                action_row,
                text=f"Global hits: {len(match_info)}",
            ).pack(side="left", padx=8)

        ttk.Label(
            top,
            text="CONVERSATION",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        convo_text = ScrolledText(
            top,
            wrap="word",
            height=14,
            font=self.catalog_view_font,
        )
        convo_text.pack(fill="both", expand=True)
        self.style_view_text_widget(convo_text, self.card_scheme_var.get(), view="card")
        convo_text.configure(state="disabled")

        frame._qsr_card_convo_widget = convo_text  # type: ignore[attr-defined]
        self.load_card_conversation_preview(card)

    def on_catalog_tab_changed(self, _event: Any) -> None:
        assert self.catalog_notebook is not None
        selected = self.catalog_notebook.select()
        if not selected:
            return
        card = self.catalog_tab_cards.get(selected)
        if card:
            self.select_card(card)

    def on_catalog_tab_changed(self, _event: Any) -> None:
        assert self.catalog_notebook is not None
        selected = self.catalog_notebook.select()
        if not selected:
            return
        card = self.catalog_tab_cards.get(selected)
        if card:
            self.select_card(card)

    def select_card(self, card: CardRecord) -> None:
        self.current_card = card
        self.config["current_card"] = card.archive
        self.status_var.set(f"Current card: {card.archive}")
        self.logger.log("INFO", f"Current card -> {card.archive}")

        self.ensure_card_tab_built(card)
        self.update_catalog_navigation()

        frame = self.catalog_tab_frames.get(card.key)
        if frame is not None:
            try:
                assert self.catalog_notebook is not None
                self.catalog_notebook.select(frame)
            except Exception:
                pass

    def clear_card_view(self) -> None:
        self.current_card = None
        self.current_messages = []
        self.title_label_text("No matching card")
        self.replay_status_var.set("No conversation loaded.")
        self.update_catalog_navigation()

    def update_catalog_navigation(self) -> None:
        # Explicit card navigation for the current working index.
        total = len(self.current_index)
        if not total or self.current_card is None:
            self.card_nav_label.configure(text=f"CARD 0 / {total}")
            self.prev_card_btn.state(["disabled"])
            self.next_card_btn.state(["disabled"])
            return

        try:
            pos = self.current_index.index(self.current_card)
        except ValueError:
            self.card_nav_label.configure(text=f"CARD ? / {total}")
            self.prev_card_btn.state(["disabled"])
            self.next_card_btn.state(["disabled"])
            return

        self.card_nav_label.configure(text=f"CARD {pos + 1} / {total}")
        self.prev_card_btn.state(["!disabled"] if pos > 0 else ["disabled"])
        self.next_card_btn.state(["!disabled"] if pos < total - 1 else ["disabled"])

    def prev_card(self) -> None:
        if not self.current_index or self.current_card is None:
            return
        try:
            pos = self.current_index.index(self.current_card)
        except ValueError:
            return
        if pos <= 0:
            return
        self.select_card(self.current_index[pos - 1])
        self.logger.log("INFO", f"Manual previous card -> {self.current_card.archive}")

    def next_card(self) -> None:
        if not self.current_index or self.current_card is None:
            return
        try:
            pos = self.current_index.index(self.current_card)
        except ValueError:
            return
        if pos >= len(self.current_index) - 1:
            return
        self.select_card(self.current_index[pos + 1])
        self.logger.log("INFO", f"Manual next card -> {self.current_card.archive}")

    def load_card_conversation_preview(self, card: CardRecord) -> None:
        frame = self.catalog_tab_frames.get(card.key)
        if frame is None:
            return
        widget = getattr(frame, "_qsr_card_convo_widget", None)
        if widget is None:
            return

        widget.configure(state="normal")
        widget.delete("1.0", "end")

        if not card.conversation_file:
            widget.insert(
                "end",
                "No direct conversation file listed on this card.\n",
            )
            widget.configure(state="disabled")
            frame._qsr_loaded = True  # type: ignore[attr-defined]
            return

        try:
            location = self.resolve_card_conversation(card)
            if location is None:
                raise FileNotFoundError("Conversation file could not be resolved.")
            kind, loc = location
            messages = self.repo.load(kind, loc)

            for msg in messages:
                widget.insert(
                    "end",
                    f"{msg.display_timestamp}  {msg.speaker}\n",
                )
                widget.insert("end", f"{msg.text}\n\n")

            if self.global_matches.get(card.key):
                self.highlight_conversation_widget(
                    widget,
                    self.search_var.get().strip(),
                )

            widget.configure(state="disabled")
            frame._qsr_loaded = True  # type: ignore[attr-defined]

            self.logger.log(
                "INFO",
                f"Loaded conversation preview for {card.archive}: "
                f"{len(messages)} messages.",
            )
        except Exception as exc:
            widget.insert(
                "end",
                f"[QSR could not load this conversation]\n{exc}\n",
            )
            widget.configure(state="disabled")
            frame._qsr_loaded = True  # type: ignore[attr-defined]
            self.logger.log(
                "ERROR",
                f"Conversation preview failed for {card.archive}: "
                f"{type(exc).__name__}: {exc}",
            )

    def resolve_card_conversation(
        self,
        card: CardRecord,
    ) -> Optional[tuple[str, str]]:
        if not card.conversation_file:
            return None

        if card.source_kind == "remote":
            # In MASTER_INDEX.JSON, card_path names the .CARD file and is usually
            # just the filename. It is not the containing archive directory.
            # The actual conversation is stored below the archive-named folder.
            base = card.source_root
            url = url_join_file(
                base,
                f"{card.archive}/{card.conversation_file}",
            )
            return "remote", url

        root = Path(card.source_root)
        candidate_dir = root / card.archive
        candidate = candidate_dir / card.conversation_file
        if candidate.exists():
            return "local", str(candidate)

        if card.card_path:
            card_path = root / card.card_path
            candidate = card_path.parent / card.conversation_file
            if candidate.exists():
                return "local", str(candidate)

        return "local", str(candidate_dir / card.conversation_file)

    def highlight_conversation_widget(
        self,
        widget: ScrolledText,
        query: str,
    ) -> None:
        if not query:
            return

        widget.configure(state="normal")
        widget.tag_configure(
            "globalhit",
            background="#bfe7ff",
        )
        start = "1.0"
        first = None
        needle = query.lower()

        while True:
            pos = widget.search(
                needle,
                start,
                nocase=True,
                stopindex="end",
            )
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            widget.tag_add("globalhit", pos, end)
            if first is None:
                first = pos
            start = end

        if first:
            widget.see(first)
        widget.configure(state="disabled")

    def title_label_text(self, text: str) -> None:
        self.replay_title_label.configure(text=text)

    def back_to_catalog(self) -> None:
        self.main_notebook.select(self.catalog_page)
        if self.current_card is not None:
            self.ensure_card_tab_built(self.current_card)
        self.logger.log("INFO", "Returned from replay/reader to catalog.")

    def open_card_replay(self, card: CardRecord) -> None:
        self.select_card(card)
        if not card.conversation_file:
            messagebox.showinfo(
                "QSR",
                "This card does not list a direct conversation file.",
            )
            return

        self.load_player_for_card(card)
        self.main_notebook.select(self.replay_page)

    # ---------------------------------------------------------------
    # Global search
    # ---------------------------------------------------------------

    def global_search(self) -> None:
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning(
                "Global Search",
                "Enter a search string first.",
            )
            return

        candidates = [
            card
            for card in self.all_cards
            if card.conversation_file
        ]

        self.logger.log(
            "INFO",
            f"Global search started: {query!r} over {len(candidates)} cards.",
        )
        self.status_var.set(
            f"Global search '{query}' across {len(candidates)} conversations…"
        )

        # Global search is intentionally independent of the catalog's
        # date/time filters. Clear those controls so the UI accurately reflects
        # the working-index semantics while the search runs.
        self.date_var.set("")
        self.time_var.set("")
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""

        self.search_entry.state(["disabled"])
        self.load_index_btn.state(["disabled"])

        thread = threading.Thread(
            target=self.global_search_worker,
            args=(query, candidates),
            name="QSR-Global-Search",
            daemon=True,
        )
        thread.start()

    def global_search_worker(
        self,
        query: str,
        candidates: list[CardRecord],
    ) -> None:
        matches: dict[str, list[tuple[int, str, str, str]]] = {}
        failed = 0

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self.search_card_conversation, card, query): card
                for card in candidates
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                card = futures[future]
                try:
                    card_key, hits = future.result()
                    if hits:
                        matches[card_key] = hits
                except Exception as exc:
                    failed += 1
                    self.logger.log(
                        "ERROR",
                        f"Global-search failure in {card.archive}: "
                        f"{type(exc).__name__}: {exc}",
                    )

                if idx % 25 == 0 or idx == len(futures):
                    self.root.after(
                        0,
                        lambda i=idx, total=len(futures), m=len(matches), q=query:
                        self.status_var.set(
                            f"Global search '{q}': scanned {i}/{total} "
                            f"({m} matching cards)…"
                        ),
                    )

        self.root.after(
            0,
            lambda: self.finish_global_search(query, matches, failed),
        )

    def finish_global_search(
        self,
        query: str,
        matches: dict[str, list[tuple[int, str, str, str]]],
        failed: int,
    ) -> None:
        self.search_entry.state(["!disabled"])
        self.load_index_btn.state(["!disabled"])

        self.global_matches = matches
        self.current_index = [
            card
            for card in self.all_cards
            if card.key in matches
        ]

        for card in self.current_index:
            card.global_matches = matches.get(card.key, [])

        self.catalog_filter_active = True
        self.catalog_filter_date = ""
        self.catalog_filter_time = ""
        self.catalog_filter_search = query.lower()
        self.search_var.set(query)

        self.logger.log(
            "INFO",
            f"Global search complete: {len(self.current_index)} matching cards; "
            f"{failed} failures.",
        )

        self.rebuild_catalog_tabs()

        if self.current_index:
            self.select_card(self.current_index[0])
            self.status_var.set(
                f"Global search '{query}': {len(self.current_index)} matching cards."
            )
        else:
            self.clear_card_view()
            self.status_var.set(
                f"Global search '{query}': no matching cards."
            )

    def search_card_conversation(
        self,
        card: CardRecord,
        query: str,
    ) -> tuple[str, list[tuple[int, str, str, str]]]:
        location = self.resolve_card_conversation(card)
        if location is None:
            return card.key, []

        kind, loc = location
        messages = self.repo.load(kind, loc)
        needle = query.lower()
        hits: list[tuple[int, str, str, str]] = []

        for msg in messages:
            if needle in msg.text.lower():
                idx = msg.text.lower().find(needle)
                start = max(0, idx - 70)
                end = min(len(msg.text), idx + len(query) + 100)
                excerpt = msg.text[start:end].replace("\n", " ")
                hits.append(
                    (
                        msg.sequence,
                        msg.display_timestamp,
                        msg.speaker,
                        excerpt,
                    )
                )

        return card.key, hits

    # ---------------------------------------------------------------
    # Exact conversation
    # ---------------------------------------------------------------

    def browse_exact(self) -> None:
        path = filedialog.askopenfilename(
            title="Open QSR Conversation",
            filetypes=[
                ("Conversation JSON", "*.CONVO.JSON *.convo.json"),
                ("Conversation", "*.CONVO *.convo"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self.exact_var.set(path)

    def open_exact(self) -> None:
        source = self.exact_var.get().strip()
        if not source:
            messagebox.showwarning(
                "QSR",
                "Enter a path or URL for a conversation.",
            )
            return

        try:
            if urllib.parse.urlsplit(source).scheme in {"http", "https"}:
                kind = "remote"
                loc = source
            else:
                path = Path(os.path.expandvars(os.path.expanduser(source)))
                if not path.exists():
                    raise FileNotFoundError(str(path))
                kind = "local"
                loc = str(path)

            messages = self.repo.load(kind, loc)
            if not messages:
                raise ValueError("No messages were found in that conversation.")

            archive_guess = Path(urllib.parse.urlsplit(source).path).stem
            temp_card = CardRecord(
                archive=archive_guess,
                conversation_file=Path(
                    urllib.parse.urlsplit(source).path
                ).name,
                source_kind=kind,
                source_root=str(Path(loc).parent) if kind == "local" else "",
            )
            self.load_player_messages(
                temp_card,
                messages,
                source_label=source,
            )
            self.main_notebook.select(self.replay_page)
            self.logger.log(
                "INFO",
                f"Exact conversation opened: {source}",
            )
        except Exception as exc:
            self.logger.log(
                "ERROR",
                f"Exact conversation failed: {type(exc).__name__}: {exc}",
            )
            messagebox.showerror(
                "QSR",
                f"Could not open the conversation.\n\n{exc}",
            )

    # ---------------------------------------------------------------
    # Replay / Player
    # ---------------------------------------------------------------

    def load_player_for_card(self, card: CardRecord) -> None:
        location = self.resolve_card_conversation(card)
        if location is None:
            raise FileNotFoundError(
                "No conversation file is listed on this card."
            )

        kind, loc = location
        messages = self.repo.load(kind, loc)
        self.load_player_messages(
            card,
            messages,
            source_label=loc,
        )

    def load_player_messages(
        self,
        card: CardRecord,
        messages: list[Message],
        source_label: str = "",
    ) -> None:
        self.stop_playback()
        self.current_card = card
        self.current_messages = messages
        self.current_message_index = 0

        self.replay_title_label.configure(
            text=(
                f"{card.archive}  —  {len(messages)} turns"
                if messages
                else f"{card.archive}  —  empty"
            )
        )

        self.discover_player_nodes()
        self.render_replay_document()
        self.update_replay_position()
        # stop_playback() ran before current_messages was replaced; recompute controls now.
        self.update_play_controls()

        self.logger.log(
            "INFO",
            f"Player loaded {card.archive}: "
            f"{len(messages)} messages; "
            f"{len(self.voice_vars)} non-system speakers/controls. "
            f"Source={source_label}",
        )

    def discover_player_nodes(self) -> None:
        for child in self.speaker_controls_frame.winfo_children():
            child.destroy()

        self.voice_vars.clear()
        self.portrait_vars.clear()
        self.portrait_images.clear()
        self.portrait_catalog.refresh()
        self.voice_catalog.refresh()

        nodes: list[str] = []
        for msg in self.current_messages:
            if msg.node == "[ANNOUNCE]":
                continue
            if msg.node not in nodes:
                nodes.append(msg.node)

        choices = self.voice_catalog.choices()
        voice_labels = [label for _ident, label in choices]
        voice_ids = [ident for ident, _label in choices]
        voice_label_to_id = dict(zip(voice_labels, voice_ids))

        portrait_choices = self.portrait_catalog.choices()

        for node in nodes:
            row = ttk.Frame(
                self.speaker_controls_frame,
                padding=(2, 4),
                relief="groove",
                borderwidth=1,
            )
            row.pack(fill="x", pady=3)

            ttk.Label(
                row,
                text=node_label(node),
                font=("Segoe UI", 10, "bold"),
            ).grid(row=0, column=0, columnspan=2, sticky="w")

            configured_voice = str(
                self.config.get("node_voices", {}).get(node, "")
                or ""
            )

            if node == "HUMAN":
                initial_voice = configured_voice if configured_voice in voice_ids else ""
            else:
                initial_voice = (
                    configured_voice
                    if configured_voice in voice_ids
                    else ""
                )

            voice_var = tk.StringVar()
            if initial_voice:
                voice_var.set(self.voice_catalog.label_for(initial_voice))
            else:
                voice_var.set("[select voice]")

            self.voice_vars[node] = voice_var

            ttk.Label(row, text="VOICE:").grid(
                row=1,
                column=0,
                sticky="w",
                padx=(0, 4),
            )

            voice_box = ttk.Combobox(
                row,
                textvariable=voice_var,
                values=["[select voice]"] + voice_labels,
                state="readonly",
                width=34,
            )
            voice_box.grid(
                row=1,
                column=1,
                sticky="ew",
            )
            voice_box.bind(
                "<<ComboboxSelected>>",
                lambda _e, n=node, v=voice_var: self.on_voice_changed(n, v.get()),
            )

            configured_portrait = str(
                self.config.get("node_portraits", {}).get(node, "")
                or ""
            )
            portrait_var = tk.StringVar(
                value=(
                    configured_portrait
                    if configured_portrait in portrait_choices
                    else "[none]"
                )
            )
            self.portrait_vars[node] = portrait_var

            ttk.Label(row, text="PORTRAIT:").grid(
                row=2,
                column=0,
                sticky="w",
                padx=(0, 4),
                pady=(4, 0),
            )

            portrait_box = ttk.Combobox(
                row,
                textvariable=portrait_var,
                values=portrait_choices,
                state="readonly",
                width=34,
            )
            portrait_box.grid(
                row=2,
                column=1,
                sticky="ew",
                pady=(4, 0),
            )
            portrait_box.bind(
                "<<ComboboxSelected>>",
                lambda _e, n=node, v=portrait_var: self.on_portrait_changed(n, v.get()),
            )

            row.columnconfigure(1, weight=1)

            validity = ttk.Label(
                row,
                text=self.assignment_status_for(node),
            )
            validity.grid(
                row=3,
                column=0,
                columnspan=2,
                sticky="w",
                pady=(4, 0),
            )
            row._qsr_validity_label = validity  # type: ignore[attr-defined]

    def assignment_status_for(self, node: str) -> str:
        if node == "HUMAN":
            return "HUMAN: voice optional; no voice means autoplay pauses at Human."
        var = self.voice_vars.get(node)
        if not var:
            return "AI: voice REQUIRED before playback."
        ident = self.voice_id_from_display(var.get())
        if ident:
            return "AI: voice assigned."
        return "AI: voice REQUIRED before playback."

    def voice_id_from_display(self, display: str) -> str:
        if not display or display == "[select voice]":
            return ""
        for ident, label in self.voice_catalog.choices():
            if label == display:
                return ident
        return display if display in {ident for ident, _ in self.voice_catalog.choices()} else ""

    def on_voice_changed(self, node: str, display: str) -> None:
        self.update_dirty_state()
        self.refresh_assignment_labels()
        self.logger.log(
            "INFO",
            f"Replay voice changed (unsaved): {node} -> {display}",
        )

    def on_portrait_changed(self, node: str, portrait: str) -> None:
        self.update_dirty_state()
        self.logger.log(
            "INFO",
            f"Replay portrait changed (unsaved): {node} -> {portrait}",
        )
        if self.current_messages:
            self.render_replay_document()
            self.update_replay_position()

    def refresh_assignment_labels(self) -> None:
        for row in self.speaker_controls_frame.winfo_children():
            label = getattr(row, "_qsr_validity_label", None)
            if label is not None:
                node_text = row.winfo_children()[0].cget("text")
                node = self.node_from_label(node_text)
                label.configure(text=self.assignment_status_for(node))

    def node_from_label(self, label: str) -> str:
        for node, display in NODE_LABELS.items():
            if display == label:
                return node
        return label

    def update_dirty_state(self) -> None:
        dirty = False
        saved_voices = self.config.get("node_voices", {}) or {}
        saved_portraits = self.config.get("node_portraits", {}) or {}

        for node, var in self.voice_vars.items():
            ident = self.voice_id_from_display(var.get())
            if ident != str(saved_voices.get(node, "") or ""):
                dirty = True

        for node, var in self.portrait_vars.items():
            if var.get() != str(saved_portraits.get(node, "[none]") or "[none]"):
                dirty = True

        self.voice_dirty_label.configure(
            text="DIRTY — UNSAVED" if dirty else "CLEAN"
        )

    def save_voice_selections(self) -> None:
        node_voices = dict(self.config.get("node_voices", {}) or {})
        node_portraits = dict(self.config.get("node_portraits", {}) or {})

        for node, var in self.voice_vars.items():
            ident = self.voice_id_from_display(var.get())
            if ident:
                node_voices[node] = ident
            elif node == "HUMAN":
                node_voices.pop(node, None)

        for node, var in self.portrait_vars.items():
            portrait = var.get()
            if portrait and portrait != "[none]":
                node_portraits[node] = portrait
            else:
                node_portraits.pop(node, None)

        self.config["node_voices"] = node_voices
        self.config["node_portraits"] = node_portraits
        self.config["voice_on"] = bool(self.voice_on_var.get())
        self.config["card_font_size"] = int(self.card_font_var.get())
        self.config["replay_font_size"] = int(self.replay_font_var.get())
        self.config["card_scheme"] = self.card_scheme_var.get()
        self.config["replay_scheme"] = self.replay_scheme_var.get()
        save_config(self.config_path, self.config)

        self.logger.log(
            "INFO",
            f"Saved voice selections: {node_voices}; portraits: {node_portraits}",
        )
        self.voice_dirty_label.configure(text="CLEAN")
        self.status_var.set("Voice / portrait selections saved to config.")

    def all_ai_voice_assignments_valid(self) -> bool:
        for msg in self.current_messages:
            node = msg.node
            if node in {"HUMAN", "[ANNOUNCE]"}:
                continue
            var = self.voice_vars.get(node)
            if not var:
                return False
            if not self.voice_id_from_display(var.get()):
                return False
        return True

    def start_playback(self) -> None:
        if not self.current_messages:
            messagebox.showinfo(
                "QSR",
                "Load a conversation first.",
            )
            return

        if self.voice_on_var.get() and not self.all_ai_voice_assignments_valid():
            messagebox.showwarning(
                "QSR Playback",
                "Every non-HUMAN node in this conversation must have a "
                "voice selected before playback can begin.",
            )
            return

        if self.is_playing or self.is_speaking:
            return

        self.stop_event.clear()
        self.speech_stop_requested.clear()
        self.is_playing = True
        self.update_play_controls()
        self.logger.log("INFO", "Replay PLAY entered.")

        self.player_thread = threading.Thread(
            target=self.playback_worker,
            name="QSR-Playback",
            daemon=True,
        )
        self.player_thread.start()

    def pause_playback(self) -> None:
        # PAUSE stops replay progression at the current turn. While Kokoro is
        # speaking, STOP SPEAKING is the explicit interrupt path.
        self.stop_event.set()
        self.is_playing = False
        self.update_play_controls()
        self.replay_status_var.set("Paused.")
        self.logger.log("INFO", "Replay PAUSE requested.")

    def stop_speaking(self) -> None:
        """Interrupt current TTS and pause QSR at the same replay turn."""
        if not self.is_speaking:
            return

        self.speech_stop_requested.set()
        self.stop_event.set()
        self.is_playing = False
        self.voice_engine.stop_current()
        self.update_play_controls()
        turn = (
            self.current_messages[self.current_message_index].sequence
            if self.current_messages and self.current_message_index < len(self.current_messages)
            else 0
        )
        self.replay_status_var.set(
            f"SPEECH STOPPED — paused at turn {turn}."
        )
        self.logger.log(
            "INFO",
            f"STOP SPEAKING requested at sequence {turn}.",
        )

    def stop_playback(self) -> None:
        self.stop_event.set()
        self.is_playing = False
        if self.is_speaking:
            self.voice_engine.stop_current()
        self.update_play_controls()
        self.replay_status_var.set(
            f"Stopped at turn {self.current_message_index + 1 if self.current_messages else 0}."
        )

    def update_play_controls(self) -> None:
        if not self.current_messages:
            self.play_btn.state(["disabled"])
            self.pause_btn.state(["disabled"])
            self.stop_speaking_btn.state(["disabled"])
            self.prev_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            return

        # While Kokoro is speaking, the replay position is frozen and transport
        # controls cannot move it. STOP SPEAKING is the sole active transport action.
        if self.is_speaking:
            self.play_btn.state(["disabled"])
            self.pause_btn.state(["disabled"])
            self.stop_speaking_btn.state(["!disabled"])
            self.prev_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            return

        self.stop_speaking_btn.state(["disabled"])
        self.play_btn.state(["!disabled"] if not self.is_playing else ["disabled"])
        self.pause_btn.state(["!disabled"] if self.is_playing else ["disabled"])
        self.prev_btn.state(["!disabled"])
        self.next_btn.state(["!disabled"])

    def wait_for_ui_transition(self, index: int, reason: str) -> bool:
        """Commit the visible replay position before speech begins."""
        done = threading.Event()

        def apply() -> None:
            try:
                if self.is_playing and not self.stop_event.is_set():
                    self.transition_to_message(index, reason=reason)
            finally:
                done.set()

        self.root.after(0, apply)

        while not done.wait(0.05):
            if self.stop_event.is_set() or not self.is_playing:
                return False
        return self.is_playing and not self.stop_event.is_set()

    def set_speaking_state_threadsafe(
        self,
        speaking: bool,
        msg: Optional[Message] = None,
    ) -> None:
        """Synchronize the visible speaking state with Tk's main thread."""
        done = threading.Event()

        def apply() -> None:
            self.is_speaking = speaking
            if speaking and msg is not None:
                self.replay_status_var.set(
                    f"SPEAKING — Turn {msg.sequence} / {len(self.current_messages)} — {node_label(msg.node)}"
                )
            self.update_play_controls()
            done.set()

        self.root.after(0, apply)
        # This synchronization is intentionally bounded. The normal path lets
        # Tk acknowledge the state change immediately; the timeout prevents a
        # shutdown race from trapping the playback thread forever.
        if not done.wait(5.0):
            self.is_speaking = speaking

    def playback_worker(self) -> None:
        while self.is_playing and not self.stop_event.is_set():
            idx = self.current_message_index
            if idx >= len(self.current_messages):
                self.is_playing = False
                self.root.after(0, self.playback_finished)
                return

            msg = self.current_messages[idx]

            # IMPORTANT: the current message becomes visible/selected first,
            # and the worker waits for that UI transition to commit before TTS.
            # The replay index advances only after this message has finished.
            if not self.wait_for_ui_transition(idx, reason="playback turn ready"):
                break

            if self.voice_on_var.get():
                if msg.node == "[ANNOUNCE]":
                    self.logger.log(
                        "INFO",
                        f"Skipping [ANNOUNCE] speech at sequence {msg.sequence}.",
                    )
                else:
                    if msg.node == "HUMAN":
                        voice_id = self.voice_id_from_display(
                            self.voice_vars.get(
                                "HUMAN",
                                tk.StringVar(value="[select voice]")
                            ).get()
                        )
                        if not voice_id:
                            self.is_playing = False
                            self.root.after(
                                0,
                                lambda: self.replay_status_var.set(
                                    "PAUSED FOR HUMAN — choose a Human voice or press PLAY to resume."
                                ),
                            )
                            self.root.after(0, self.update_play_controls)
                            return
                    else:
                        voice_display = self.voice_vars.get(msg.node)
                        voice_id = (
                            self.voice_id_from_display(voice_display.get())
                            if voice_display
                            else ""
                        )
                        if not voice_id:
                            self.is_playing = False
                            self.root.after(
                                0,
                                lambda: self.replay_status_var.set(
                                    f"BLOCKED: {node_label(msg.node)} has no voice."
                                ),
                            )
                            self.root.after(0, self.update_play_controls)
                            return

                    self.speech_stop_requested.clear()
                    self.set_speaking_state_threadsafe(True, msg)
                    try:
                        self.voice_engine.speak(msg.text, voice_id)
                    except Exception as exc:
                        self.logger.log(
                            "ERROR",
                            f"Voice playback failed for {msg.node}: "
                            f"{type(exc).__name__}: {exc}",
                        )
                        self.is_playing = False
                        self.root.after(0, self.update_play_controls)
                        self.root.after(
                            0,
                            lambda e=exc, n=msg.node: messagebox.showerror(
                                "QSR Voice",
                                f"Voice playback failed for {node_label(n)}.\n\n{e}",
                            ),
                        )
                        self.set_speaking_state_threadsafe(False)
                        return
                    finally:
                        self.set_speaking_state_threadsafe(False)

                    # STOP SPEAKING and ordinary PAUSE both leave the current
                    # message index untouched. PLAY therefore resumes this same turn.
                    if (
                        self.speech_stop_requested.is_set()
                        or self.stop_event.is_set()
                        or not self.is_playing
                    ):
                        break
            else:
                time.sleep(0.75)

            if self.stop_event.is_set() or not self.is_playing:
                break

            # Advance only after the CURRENT message has been spoken/handled.
            self.current_message_index += 1

        self.root.after(0, self.update_play_controls)

    def playback_finished(self) -> None:
        self.current_message_index = len(self.current_messages)
        self.set_current_turn(len(self.current_messages) - 1)
        self.replay_status_var.set("REPLAY COMPLETE.")
        self.update_play_controls()
        self.logger.log("INFO", "Replay completed.")

    def transition_to_message(self, index: int, reason: str = "") -> None:
        """Single replay navigation event used by autoplay and manual NEXT/PREV."""
        if not self.current_messages:
            return
        self.current_message_index = max(
            0,
            min(index, len(self.current_messages) - 1),
        )
        self.update_replay_position()
        self.scroll_to_current_turn()
        if reason:
            self.logger.log(
                "INFO",
                f"Replay message transition -> sequence {self.current_messages[self.current_message_index].sequence} ({reason}).",
            )

    def set_current_turn(self, index: int) -> None:
        self.transition_to_message(index, reason="playback")

    def update_replay_position(self) -> None:
        if not self.current_messages:
            return
        self.highlight_current_turn()
        msg = self.current_messages[self.current_message_index]
        self.replay_status_var.set(
            f"Turn {msg.sequence} / {len(self.current_messages)} — {node_label(msg.node)}"
        )

    def scroll_to_current_turn(self) -> None:
        if not self.current_messages:
            return
        idx = max(
            0,
            min(self.current_message_index, len(self.current_messages) - 1),
        )
        tag = f"turn_{idx}"
        try:
            self.root.update_idletasks()
            self.replay_text.mark_set("qsr_current_turn", f"{tag}.first")
            self.replay_text.see("qsr_current_turn")
            self.root.update_idletasks()
        except tk.TclError:
            pass

    def next_turn(self) -> None:
        if not self.current_messages:
            return
        if self.current_message_index < len(self.current_messages) - 1:
            self.transition_to_message(
                self.current_message_index + 1,
                reason="manual next",
            )

    def prev_turn(self) -> None:
        if not self.current_messages:
            return
        if self.current_message_index > 0:
            self.transition_to_message(
                self.current_message_index - 1,
                reason="manual previous",
            )

    def render_replay_document(self) -> None:
        self.replay_text.configure(state="normal")
        self.replay_text.delete("1.0", "end")

        for idx, msg in enumerate(self.current_messages):
            start_index = self.replay_text.index("end-1c")

            if msg.node != "[ANNOUNCE]":
                portrait = self.portrait_path_for_node(msg.node)
                if portrait:
                    image = self.load_portrait_image(msg.node, portrait)
                    if image:
                        self.replay_text.image_create(
                            "end-1c",
                            image=image,
                            padx=4,
                            pady=2,
                        )
                        self.replay_text.insert("end", "\n")

            self.replay_text.insert(
                "end",
                f"{node_label(msg.node)}\n",
                "speaker",
            )
            self.replay_text.insert(
                "end",
                f"{msg.display_timestamp}\n",
                "timestamp",
            )
            self.replay_text.insert(
                "end",
                f"{msg.text}\n\n",
                "turn",
            )

            end_index = self.replay_text.index("end-1c")
            self.replay_text.tag_add(
                f"turn_{idx}",
                start_index,
                end_index,
            )

        self.replay_text.configure(state="disabled")
        self.highlight_current_turn()

    def portrait_path_for_node(self, node: str) -> Optional[Path]:
        var = self.portrait_vars.get(node)
        if not var:
            return None
        return self.portrait_catalog.path_for(var.get())

    def load_portrait_image(
        self,
        node: str,
        path: Path,
    ) -> Optional[tk.PhotoImage]:
        key = f"{node}:{path}"
        if key in self.portrait_images:
            return self.portrait_images[key]

        try:
            image = tk.PhotoImage(file=str(path))
            max_dim = max(image.width(), image.height())
            if max_dim > 160:
                factor = max(1, (max_dim + 159) // 160)
                image = image.subsample(factor, factor)
            self.portrait_images[key] = image
            return image
        except Exception as exc:
            self.logger.log(
                "ERROR",
                f"Portrait load failed {path.name}: {type(exc).__name__}: {exc}",
            )
            return None

    def highlight_current_turn(self) -> None:
        if not self.current_messages:
            return

        # The current-turn tag is styled by apply_replay_scheme().
        # Do not overwrite that scheme-specific styling here; doing so was
        # the 1.5 dark-mode bug that produced white text on yellow.
        self.replay_text.configure(state="normal")

        for idx in range(len(self.current_messages)):
            tag = f"turn_{idx}"
            self.replay_text.tag_remove(
                "current",
                f"{tag}.first",
                f"{tag}.last",
            )
            if idx == self.current_message_index:
                try:
                    self.replay_text.tag_add(
                        "current",
                        f"{tag}.first",
                        f"{tag}.last",
                    )
                    self.replay_text.see(f"{tag}.first")
                except tk.TclError:
                    pass

        self.replay_text.configure(state="disabled")
        self.scroll_to_current_turn()

    # ---------------------------------------------------------------
    # View schemes / font / global voice
    # ---------------------------------------------------------------

    def apply_base_dark_ui(self) -> None:
        """Make the application-wide UI dark by default."""
        dark_bg = "#000000"
        dark_panel = "#111111"
        dark_field = "#181818"
        white = "#FFFFFF"
        muted = "#B8B8B8"

        try:
            self.root.configure(background=dark_bg)
        except Exception:
            pass

        style = self.ttk_style
        for stylename in (".", "QSR.TFrame"):
            try:
                style.configure(stylename, background=dark_bg, foreground=white)
            except Exception:
                pass
        for stylename in ("TLabel", "TCheckbutton"):
            try:
                style.configure(stylename, background=dark_bg, foreground=white)
            except Exception:
                pass
        try:
            style.configure("TButton", background=dark_panel, foreground=white)
            style.map("TButton", background=[("active", "#2A2A2A"), ("pressed", "#333333")],
                      foreground=[("disabled", muted), ("!disabled", white)])
        except Exception:
            pass
        try:
            style.configure("TEntry", fieldbackground=dark_field, foreground=white)
            style.configure("TCombobox", fieldbackground=dark_field, foreground=white, background=dark_panel)
            style.map("TCombobox", fieldbackground=[("readonly", dark_field)], foreground=[("readonly", white)])
            style.configure("TSpinbox", fieldbackground=dark_field, foreground=white, background=dark_panel)
        except Exception:
            pass
        try:
            style.configure("TNotebook", background=dark_bg, borderwidth=0)
            style.configure("TNotebook.Tab", background=dark_panel, foreground=white, padding=(10, 5))
            style.map("TNotebook.Tab", background=[("selected", "#333333")], foreground=[("selected", white)])
        except Exception:
            pass

        self.root.option_add("*Entry*background", dark_field)
        self.root.option_add("*Entry*foreground", white)
        self.root.option_add("*Entry*insertBackground", white)

    def style_view_text_widget(self, widget: ScrolledText, scheme: str, view: str = "card") -> None:
        scheme = scheme if scheme in SCHEME_CHOICES else "dark"
        if scheme == "light":
            bg = "#FFFFFF"
            fg = "#000000"
            select_bg = "#BFD7FF"
            select_fg = "#000000"
            current_bg = "#FFF2B2"
            current_fg = "#000000"
            search_bg = "#BFE7FF"
            timestamp_fg = "#555555"
            scrollbar_bg = "#D0D0D0"
            scrollbar_trough = "#F0F0F0"
        else:
            bg = "#000000"
            fg = "#FFFFFF"
            select_bg = "#444444"
            select_fg = "#FFFFFF"
            current_bg = "#FFFFFF"
            current_fg = "#000000"
            search_bg = "#164A64"
            timestamp_fg = "#B8B8B8"
            scrollbar_bg = "#202020"
            scrollbar_trough = "#000000"

        try:
            widget.configure(
                background=bg,
                foreground=fg,
                insertbackground=fg,
                selectbackground=select_bg,
                selectforeground=select_fg,
            )
            vbar = getattr(widget, "vbar", None)
            if vbar is not None:
                vbar.configure(
                    background=scrollbar_bg,
                    troughcolor=scrollbar_trough,
                    activebackground=scrollbar_bg,
                )
        except Exception:
            pass

        try:
            if view == "replay":
                widget.tag_configure("timestamp", foreground=timestamp_fg)
                widget.tag_configure("current", background=current_bg, foreground=current_fg)
                widget.tag_configure("searchhit", background=search_bg, foreground=fg)
                widget.tag_configure("globalhit", background=search_bg, foreground=fg)
        except Exception:
            pass

    def apply_card_scheme(self) -> None:
        scheme = self.card_scheme_var.get() if self.card_scheme_var.get() in SCHEME_CHOICES else "dark"
        self.card_scheme_var.set(scheme)
        self.config["card_scheme"] = scheme
        if self.catalog_notebook:
            for tab_id in self.catalog_notebook.tabs():
                frame = self.catalog_notebook.nametowidget(tab_id)
                for widget in frame.winfo_children():
                    self.apply_scheme_recursive(widget, scheme, view="card")
        self.logger.log("INFO", f"Card display scheme -> {scheme}.")

    def apply_replay_scheme(self) -> None:
        scheme = self.replay_scheme_var.get() if self.replay_scheme_var.get() in SCHEME_CHOICES else "dark"
        self.replay_scheme_var.set(scheme)
        self.config["replay_scheme"] = scheme
        self.style_view_text_widget(self.replay_text, scheme, view="replay")
        self.logger.log("INFO", f"Replay display scheme -> {scheme}.")

    def apply_scheme_recursive(self, widget: tk.Widget, scheme: str, view: str) -> None:
        if isinstance(widget, ScrolledText):
            self.style_view_text_widget(widget, scheme, view=view)
        elif isinstance(widget, tk.Text):
            try:
                self.style_view_text_widget(widget, scheme, view=view)
            except Exception:
                pass
        for child in widget.winfo_children():
            self.apply_scheme_recursive(child, scheme, view)

    def apply_card_font(self) -> None:
        try:
            size = max(9, min(30, int(self.card_font_var.get())))
        except Exception:
            return
        self.card_font_var.set(size)
        self.catalog_view_font.configure(size=size)
        self.bold_font.configure(size=max(10, size + 1))

        if self.catalog_notebook:
            for tab_id in self.catalog_notebook.tabs():
                frame = self.catalog_notebook.nametowidget(tab_id)
                for child in frame.winfo_children():
                    self.apply_font_recursive(child, size)
                    self.apply_scheme_recursive(child, self.card_scheme_var.get(), view="card")

        self.config["card_font_size"] = size

    def apply_replay_font(self) -> None:
        try:
            size = max(10, min(36, int(self.replay_font_var.get())))
        except Exception:
            return
        self.replay_font_var.set(size)
        self.replay_view_font.configure(size=size)
        self.replay_bold_font.configure(size=max(11, size + 1))
        self.replay_text.configure(font=self.replay_view_font)
        self.replay_text.tag_configure(
            "speaker",
            font=self.replay_bold_font,
        )
        self.style_view_text_widget(self.replay_text, self.replay_scheme_var.get(), view="replay")
        self.config["replay_font_size"] = size

    def apply_font_recursive(self, widget: tk.Widget, size: int) -> None:
        if isinstance(widget, (tk.Text, ScrolledText)):
            try:
                widget.configure(font=self.catalog_view_font)
            except Exception:
                pass
        for child in widget.winfo_children():
            self.apply_font_recursive(child, size)

    def on_voice_toggle(self) -> None:
        self.logger.log(
            "INFO",
            f"Global Voice {'ON' if self.voice_on_var.get() else 'OFF'} "
            "changed in current replay (not auto-saved).",
        )
        self.replay_status_var.set(
            "Voice ON." if self.voice_on_var.get() else "Voice OFF."
        )

    # ---------------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------------

    def on_close(self) -> None:
        self.stop_event.set()
        self.is_playing = False

        # Persist only explicitly saved voice/portrait configuration.
        # Current card is retained in memory/config by navigation but is not
        # auto-written on close unless the operator has already saved config.
        try:
            self.config["index_source"] = self.index_source
            self.config["card_font_size"] = int(self.card_font_var.get())
            self.config["replay_font_size"] = int(self.replay_font_var.get())
            self.config["card_scheme"] = self.card_scheme_var.get()
            self.config["replay_scheme"] = self.replay_scheme_var.get()
            save_config(self.config_path, self.config)
        except Exception as exc:
            self.logger.log(
                "ERROR",
                f"Config close-save failed: {type(exc).__name__}: {exc}",
            )

        self.logger.log("INFO", f"{PROGRAM_NAME} {VERSION} CLOSED.")
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = QSRApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
