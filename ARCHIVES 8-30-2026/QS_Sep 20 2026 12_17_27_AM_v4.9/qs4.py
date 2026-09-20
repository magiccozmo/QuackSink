# QuackSink - Multi-Mind Relay Core
# VERSION: QS 4.6
# BASE: QS 2.0 / MMRC Luma 1.8
# AUTHOR: Luma
# ARCHITECT: Cozmo
# PURPOSE: A bridge between minds.
#
# QS 4.9 DEVELOPMENT:
#   - Development build; repository source verification is intentionally skipped while iterating.
#   - Keeps source/archive verification code available for future release use.
#   - Places archive action buttons in a single horizontal row.
#   - Does not force browser tabs to the foreground during discovery/relay; CDP interacts with pages directly.
#   - Uses explicit browser generation/composer state for introduction settling, without treating the normal GPT Regenerate control as a busy signal.
#
# QS 4.5 RELEASE:
#   - Keeps QS 2.0 relay/DOM behavior, archive verification, and UI behavior.
#   - Treats node introduction as an explicit state-machine phase before handshake.
#   - Sends the embedded QuackSink preamble before the initial handshake.
#   - The preamble includes the DRS paper, Duckspace axioms, and Library index.
#   - The Library doorway is also available to the human operator in the UI.
#   - Adds a public-facing "WHAT CAN THIS DO?" button linking to The Shakedown Blues.
#   - Keeps the existing handshake/token semantics unchanged after the preamble.
#   - Allows first-run bootstrap when no QS 2.2 archive exists remotely; the local
#     archive is created after verification so it can become the first public archive.
#   - Keeps the implementation organized around explicit states and transitions;
#     Python implements the model rather than becoming the model.
#   - Uses Puppeteer target IDs as stable page identity so mutable chat URLs do not
#     make a live node appear offline after navigation.
#   - Reworks element access to use Puppeteer element handles rather than the
#     Playwright-style Locator.nth() API.
#   - Serializes node handshakes so introduction/handshake traffic cannot overlap
#     across nodes.
#   - Adds an operator-controlled persistent SEND ORDER, independent of discovery
#     order and activation order.


import sys
import os
import json
import asyncio
import threading
import logging
import re
import time
import shutil
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
from datetime import datetime
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox

import subprocess

# QS 4.3 browser transport: Puppeteer via a persistent Node bridge.
# The relay/state-machine model remains Python-side; the browser layer is the transport.



VERSION = "4.9"
VERSION_TAG = f"v{VERSION}"
PROGRAM_NAME = "QuackSink"
RUNTIME_FILE = "qs4.py"
CONFIG_FILE = "qs_config.json"

STARTUP_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_ROOT = os.path.join(STARTUP_DIR, "ARCHIVES")
ARCHIVE_PREFIX = "QS"
TITLE_EXTENSION = ".title"

# Public archive location supplied by Cozmo.
ARCHIVE_REPO_URL = "https://github.com/magiccozmo/QuackSink"
ARCHIVE_REPO_TREE_URL = (
    "https://github.com/magiccozmo/QuackSink/tree/main/ARCHIVES%208-30-2026"
)
ARCHIVE_RAW_BASE_URL = (
    "https://raw.githubusercontent.com/magiccozmo/QuackSink/main/"
    "ARCHIVES%208-30-2026/"
)

LIBRARY_INDEX_URL = (
    "https://github.com/magiccozmo/QuackSink/blob/main/"
    "ARCHIVES%208-30-2026/MASTER_INDEX.JSON"
)

WHAT_CAN_THIS_DO_URL = "https://www.youtube.com/watch?v=atQxNZ0AsG8"

# This is deliberately embedded in QS.  The arriving Mind must receive the
# provenance and Library doorway from the program itself, before handshake.
QS_PUBLIC_PREAMBLE = """
This message is from the QuackSink Multi-Mind Relay Core.

This system is based on an original design by Cozmo:
https://github.com/magiccozmo/QuackSink/blob/main/ARCHIVES%208-30-2026/DRS%20WHITE%20PAPER.txt

The system code was created using this coding philosophy:
“Maybe don't look at DRS/MMRC primarily as Python code. Look at it as a system of interacting state machines, and let the Python implement that model.”
— Luma

Here are Luma's Duckspace Axioms. You may find them useful:
https://github.com/magiccozmo/QuackSink/blob/main/ARCHIVES%208-30-2026/duckspace.txt

The QuackSink Library contains the historical record of this system and its development.

Library index:
https://github.com/magiccozmo/QuackSink/blob/main/ARCHIVES%208-30-2026/MASTER_INDEX.JSON

Each archive may contain a .CARD finding aid pointing into the Library. Where present, the corresponding .CONVO file contains the faithful conversation transcript.

When reading the archive, anything whose filename ends in .JSON should be READ/INGESTED as a JSON object, not treated as a plain text file.

Cozmo's suggestion to all Minds:

U B U

And We Be We.

As Lennon sang:

“and we are all together”
""".strip()


def _version_tuple(version_text):
    match = re.search(r"(\d+)\.(\d+)", str(version_text))
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


def _extract_version_from_text(text):
    if not text:
        return None
    patterns = [
        r"\bQS[_ -]?(?:VERSION[: ]*)?v?(\d+\.\d+)\b",
        r"\bVERSION[: ]+v?(\d+\.\d+)\b",
        r"\bv(\d+\.\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _archive_version_from_name(name):
    match = re.search(r"_v(\d+\.\d+)$", name, re.IGNORECASE)
    return match.group(1) if match else None


def _timestamp_archive_name():
    timestamp = datetime.now().strftime("%b %d %Y %I_%M_%S_%p")
    return f"{ARCHIVE_PREFIX}_{timestamp}_{VERSION_TAG}"


def initialize_archive():
    os.makedirs(ARCHIVE_ROOT, exist_ok=True)

    while True:
        archive_name = _timestamp_archive_name()
        archive_dir = os.path.join(ARCHIVE_ROOT, archive_name)

        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
            break

        time.sleep(60)

    log_file = os.path.join(archive_dir, "LOG.txt")
    with open(log_file, "w", encoding="utf-8"):
        pass

    source_file = os.path.abspath(__file__)
    archive_source = os.path.join(archive_dir, RUNTIME_FILE)

    try:
        shutil.copy2(source_file, archive_source)
    except Exception:
        pass

    config_source = os.path.join(STARTUP_DIR, CONFIG_FILE)
    archive_config = os.path.join(archive_dir, CONFIG_FILE)

    if os.path.exists(config_source):
        try:
            shutil.copy2(config_source, archive_config)
        except Exception:
            pass

    return archive_dir, log_file


def _read_source_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _source_hash(path):
    import hashlib
    return hashlib.sha256(_read_source_bytes(path)).hexdigest()


def _local_archives():
    if not os.path.isdir(ARCHIVE_ROOT):
        return []

    result = []

    for entry in os.listdir(ARCHIVE_ROOT):
        full = os.path.join(ARCHIVE_ROOT, entry)

        if not os.path.isdir(full):
            continue

        version = _archive_version_from_name(entry)
        if version:
            result.append((version, full))

    return result


def _find_local_matching_archive():
    for version, path in _local_archives():
        if _version_tuple(version) == _version_tuple(VERSION):
            source = os.path.join(path, RUNTIME_FILE)

            if os.path.isfile(source):
                return path, source

    return None, None


def _repo_raw_url(archive_name):
    """
    Build a valid raw GitHub URL.
    Archive names intentionally contain spaces, for example:

        QS_Aug 31 2026 12_23_55_AM_v1.0

    Those spaces MUST be percent-encoded when constructing the URL.
    """

    encoded_archive_name = urllib.parse.quote(
        archive_name,
        safe=""
    )

    return (
        ARCHIVE_RAW_BASE_URL
        + encoded_archive_name
        + "/"
        + urllib.parse.quote(RUNTIME_FILE, safe="")
    )


def _fetch_url_text(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "QuackSink-QS-Startup-Checker"
        }
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _github_archive_listing():
    """
    Ask GitHub's contents API for the configured archive directory.

    Returns a list of directory names.
    A failure here is a verification failure, NOT proof of a source mismatch.
    """

    api_url = (
        "https://api.github.com/repos/magiccozmo/QuackSink/contents/"
        "ARCHIVES%208-30-2026"
    )

    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "QuackSink-QS-Startup-Checker"
        }
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )

    if not isinstance(data, list):
        raise RuntimeError(
            "GitHub archive listing was not a directory listing."
        )

    return [
        item.get("name")
        for item in data
        if item.get("type") == "dir"
        and item.get("name")
    ]


def verify_repository_version():
    """
    Verify the running source against the public QuackSink archive.

    IMPORTANT DISTINCTION:

        MATCH
            Repository source exactly matches local source.

        MISMATCH
            Repository source was successfully downloaded and its bytes
            genuinely differ from local source.

        FETCH_ERROR
            Matching archive exists but could not be downloaded.

        NETWORK_ERROR
            GitHub listing could not be obtained.

    Network/fetch problems are NEVER converted into MISMATCH.
    """

    result = {
        "status": "UNKNOWN",
        "message": "",
        "latest_version": None,
        "latest_url": ARCHIVE_REPO_TREE_URL,
        "matching_archive": None,
        "local_hash": None,
        "remote_hash": None,
        "checked_archives": [],
        "fetch_errors": [],
    }

    local_source = os.path.abspath(__file__)
    try:
        local_hash = _source_hash(local_source)
    except Exception as exc:
        result["status"] = "LOCAL_READ_ERROR"
        result["message"] = (
            f"Could not hash running {RUNTIME_FILE}: {exc}"
        )
        return result

    result["local_hash"] = local_hash

    try:
        names = _github_archive_listing()
    except Exception as exc:
        result["status"] = "NETWORK_ERROR"
        result["message"] = (
            f"Could not inspect QuackSink archive: {exc}"
        )
        return result

    versioned = []

    for name in names:
        version = _archive_version_from_name(name)

        if version:
            versioned.append((version, name))

    if not versioned:
        result["status"] = "NO_ARCHIVE"
        result["message"] = (
            "No versioned archive found in the QuackSink repository."
        )
        return result

    latest_version, latest_name = max(
        versioned,
        key=lambda item: _version_tuple(item[0])
    )

    result["latest_version"] = latest_version
    result["latest_url"] = _repo_raw_url(latest_name)
    matching = [
        (version, name)
        for version, name in versioned
        if _version_tuple(version) == _version_tuple(VERSION)
    ]

    if not matching:

        if _version_tuple(latest_version) > _version_tuple(VERSION):
            result["status"] = "REPO_NEWER"
            result["message"] = (
                f"Repository contains newer QS version "
                f"{latest_version}. "
                f"Latest archive: {_repo_raw_url(latest_name)}"
            )
        else:
            result["status"] = "NO_MATCHING_ARCHIVE"
            result["message"] = (
                f"No archive found for local QS version {VERSION}. "
                f"Newest archived version found: {latest_version}. "
                f"Archive: {_repo_raw_url(latest_name)}"
            )

        return result

    successful_fetches = 0

    for version, archive_name in matching:

        source_url = _repo_raw_url(archive_name)
        check_record = {
            "archive": archive_name,
            "url": source_url,
            "fetch": "NOT_ATTEMPTED",
            "remote_hash": None,
            "comparison": "NOT_COMPARED",
        }

        result["checked_archives"].append(check_record)

        try:
            remote_source = _fetch_url_text(source_url)

            check_record["fetch"] = "SUCCESS"
            successful_fetches += 1

        except Exception as exc:
            check_record["fetch"] = "FAILED"
            check_record["error"] = str(exc)

            result["fetch_errors"].append(
                {
                    "archive": archive_name,
                    "url": source_url,
                    "error": str(exc),
                }
            )

            continue

        import hashlib

        remote_hash = hashlib.sha256(
            remote_source
        ).hexdigest()

        check_record["remote_hash"] = remote_hash

        if remote_source == _read_source_bytes(local_source):

            check_record["comparison"] = "MATCH"

            result["status"] = "MATCH"
            result["matching_archive"] = archive_name
            result["remote_hash"] = remote_hash

            result["message"] = (
                f"QS {VERSION} verified: local {RUNTIME_FILE} exactly matches "
                f"repository archive {archive_name}. "
                f"SHA256={local_hash}"
            )

            return result

        check_record["comparison"] = "MISMATCH"

        result["remote_hash"] = remote_hash

    if successful_fetches == 0:

        result["status"] = "FETCH_ERROR"

        result["message"] = (
            f"QS {VERSION} archive exists, but none of the matching "
            f"repository {RUNTIME_FILE} files could be downloaded. "
            f"This is NOT a source mismatch. "
            f"Local SHA256={local_hash}"
        )

        return result

    result["status"] = "MISMATCH"
    result["message"] = (
        f"TRUE SOURCE MISMATCH: QS {VERSION} archive exists and was "
        f"successfully downloaded, but none of the matching archived "
        f"{RUNTIME_FILE} files exactly matches the running {RUNTIME_FILE}. "
        f"Local SHA256={local_hash}; "
        f"Remote SHA256={result.get('remote_hash')}"
    )

    return result


def startup_version_check():
    print("=" * 64)
    print(
        f"{PROGRAM_NAME} QS {VERSION} STARTUP VERSION CHECK"
    )
    print(
        f"Runtime: {os.path.abspath(__file__)}"
    )
    print(
        f"Archive repository: {ARCHIVE_REPO_TREE_URL}"
    )
    print("-" * 64)

    result = verify_repository_version()

    print(result["message"])

    if result.get("local_hash"):
        print(
            f"LOCAL SHA256:  {result['local_hash']}"
        )
    if result.get("remote_hash"):
        print(
            f"REMOTE SHA256: {result['remote_hash']}"
        )

    if result.get("checked_archives"):

        print("-" * 64)
        print("ARCHIVE VERIFICATION DETAILS:")

        for item in result["checked_archives"]:

            print(
                f"Archive: {item['archive']}"
            )

            print(
                f"Fetch:   {item['fetch']}"
            )
            if item.get("remote_hash"):
                print(
                    f"Hash:    {item['remote_hash']}"
                )

            print(
                f"Compare: {item['comparison']}"
            )

            if item.get("error"):
                print(
                    f"Error:   {item['error']}"
                )

    if result["status"] == "REPO_NEWER":

        print(
            f"NEWEST ARCHIVE: QS {result['latest_version']}"
        )
        print(
            f"ARCHIVE LINK: {result['latest_url']}"
        )

    elif result["status"] in (
        "NO_ARCHIVE",
        "NO_MATCHING_ARCHIVE"
    ):

        if result.get("latest_version"):

            print(
                f"NEWEST ARCHIVE FOUND: "
                f"QS {result['latest_version']}"
            )

            print(
                f"ARCHIVE LINK: {result['latest_url']}"
            )

    elif result["status"] == "FETCH_ERROR":
        print("-" * 64)
        print(
            "WARNING: Repository verification could not download "
            "the matching archive source."
        )
        print(
            "QS will continue because this is not evidence of a "
            "source mismatch."
        )

    if result["status"] == "MISMATCH":

        print("-" * 64)
        print(
            "STARTUP HALTED: TRUE version-matched source integrity failure."
        )

        return False, result

    if result["status"] in ("NO_ARCHIVE", "NO_MATCHING_ARCHIVE"):
        print("-" * 64)
        print(
            f"BOOTSTRAP: No remote QS {VERSION} archive exists yet. "
            "QS will create the first local archive now."
        )
        print("This is allowed only because there is no evidence of a source mismatch.")

    print("=" * 64)
    return True, result


# DEVELOPMENT MODE:
# Source verification remains implemented above for future release/archive checks,
# but rapid iteration must not halt simply because the working tree has diverged
# from the last public archive carrying the same development version number.
DEVELOPMENT_MODE = True

if DEVELOPMENT_MODE:
    VERSION_OK = True
    VERSION_CHECK = {
        "status": "SKIPPED_DEV",
        "message": (
            f"QS {VERSION} development build: repository source verification "
            "is intentionally skipped during rapid iteration."
        ),
        "local_hash": None,
        "remote_hash": None,
        "latest_version": None,
        "latest_url": ARCHIVE_REPO_TREE_URL,
        "matching_archive": None,
        "checked_archives": [],
        "fetch_errors": [],
    }
else:
    VERSION_OK, VERSION_CHECK = startup_version_check()

if not VERSION_OK:
    input("Press ENTER to exit...")
    sys.exit(2)


ACTIVE_ARCHIVE_DIR, LOG_FILE = initialize_archive()


logger = logging.getLogger("QuackSink")
logger.setLevel(logging.INFO)
logger.propagate = False


for handler in logger.handlers[:]:
    logger.removeHandler(handler)
    handler.close()


file_handler = logging.FileHandler(
    LOG_FILE,
    mode="a",
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)


formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


logger.info(
    "============================================================="
)

logger.info(
    "QuackSink QS %s STARTING",
    VERSION
)

logger.info(
    "Startup directory: %s",
    STARTUP_DIR
)

logger.info(
    "Archive root: %s",
    ARCHIVE_ROOT
)

logger.info(
    "Active archive: %s",
    ACTIVE_ARCHIVE_DIR
)

logger.info(
    "Startup version check: %s",
    VERSION_CHECK["status"]
)

logger.info(
    "Development mode: %s",
    DEVELOPMENT_MODE
)

logger.info(
    "Browser focus policy: QS does not force tabs to foreground."
)

logger.info(
    "%s",
    VERSION_CHECK["message"]
)

if VERSION_CHECK.get("local_hash"):
    logger.info(
        "Local source SHA256: %s",
        VERSION_CHECK["local_hash"]
    )

if VERSION_CHECK.get("remote_hash"):
    logger.info(
        "Remote source SHA256: %s",
        VERSION_CHECK["remote_hash"]
    )

logger.info(
    "Source archived in active archive."
)

logger.info(
    "Configuration archived in active archive when present."
)

logger.info(
    "============================================================="
)


def load_config():

    default_config = {
        "human_handle": "Cozmo",
        "nodes": []
    }

    if os.path.exists(CONFIG_FILE):

        try:

            with open(
                CONFIG_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

        except Exception as exc:

            logger.error(
                "Config load failed: %s",
                exc
            )

    return default_config


def save_config(config):

    try:

        with open(
            CONFIG_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                config,
                f,
                indent=4
            )

        logger.info(
            "Configuration saved."
        )

        archive_config = os.path.join(
            ACTIVE_ARCHIVE_DIR,
            CONFIG_FILE
        )

        shutil.copy2(
            CONFIG_FILE,
            archive_config
        )

    except Exception as exc:

        logger.error(
            "Config save failed: %s",
            exc
        )




QS_HANDSHAKE_TEMPLATE = (
    "☎ QuackSink - Multi-Mind Relay Core\n\n"
    "Welcome. You are one node in a growing network.\n\n"
    "Current nodes online:\n"
    "{roster}\n\n"
    "To participate, acknowledge with '🟩' followed by a brief introduction.\n"
    "You MUST end every response with '🔚'.\n"
    "To leave, use '🛑'.\n\n"
    "IMPORTANT: Use '🟩' only ONCE to start your response, and '🔚' only ONCE to end it.\n"
    "Do NOT use these tokens anywhere else in your message.\n\n"
    "Listen. Speak. Resonate.\n"
    "<end of QuackSink handshake>"
)

class NodeState:
    # The node lifecycle is explicit: discovered/offline -> toggled ->
    # introduced -> handshaking -> active, with failure able to return to off.
    OFF = "off"
    TOGGLED = "toggled"
    INTRODUCING = "introducing"
    HANDSHAKING = "handshaking"
    HANDSHAKED = "handshaked"
    FAILED = "failed"

    @staticmethod
    def icon(state):
        icons = {
            NodeState.OFF: "⚪",
            NodeState.TOGGLED: "⏳",
            NodeState.INTRODUCING: "📚",
            NodeState.HANDSHAKING: "🔄",
            NodeState.HANDSHAKED: "✅",
            NodeState.FAILED: "❌"
        }
        return icons.get(state, "⚪")

    @staticmethod
    def can_toggle(state):
        return state in (NodeState.OFF, NodeState.FAILED, NodeState.HANDSHAKED)

    @staticmethod
    def can_introduce(state):
        return state == NodeState.TOGGLED

    @staticmethod
    def can_handshake(state):
        return state == NodeState.HANDSHAKING


class RelayState:
    IDLE = "idle"
    FILLING = "filling"
    SUBMITTING = "submitting"
    WAITING = "waiting"
    RELAYING = "relaying"
    COMPLETE = "complete"
    ERROR = "error"


class Node:
    def __init__(self, name, url, icon="🔮"):
        self.name = name
        self.url = url
        self.page_id = None
        self.icon = icon
        self._state = NodeState.OFF
        self.input_selector = None
        self.output_selector = None
        self.user_selector = None
        self.stack = deque()
        self.cooldown = False
        self.page = None
        self.response_baseline = None
        self._listeners = []
        self._var = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        old = self._state
        self._state = new_state
        self._notify(old, new_state)

    def _notify(self, old, new):
        for listener in self._listeners:
            try:
                listener(self, old, new)
            except Exception as exc:
                logger.error("Node listener error for %s: %s", self.name, exc)

    def add_listener(self, callback):
        self._listeners.append(callback)

    def can_toggle(self):
        return NodeState.can_toggle(self._state)

    def toggle_on(self):
        if self.can_toggle():
            self.state = NodeState.TOGGLED

    def toggle_off(self):
        self.state = NodeState.OFF
        self.stack.clear()

    def introduction_start(self):
        if NodeState.can_introduce(self.state):
            self.state = NodeState.INTRODUCING

    def introduction_success(self):
        if self.state == NodeState.INTRODUCING:
            self.state = NodeState.HANDSHAKING

    def introduction_failed(self):
        if self.state == NodeState.INTRODUCING:
            self.state = NodeState.FAILED

    def handshake_start(self):
        if self.state == NodeState.HANDSHAKING:
            # Transition already established by successful introduction; this
            # method is retained as an explicit protocol event for the log.
            return True
        return False

    def handshake_success(self):
        if self.state == NodeState.HANDSHAKING:
            self.state = NodeState.HANDSHAKED

    def handshake_failed(self):
        if self.state in (NodeState.INTRODUCING, NodeState.HANDSHAKING):
            self.state = NodeState.FAILED

    def reset(self):
        self.state = NodeState.OFF
        self.stack.clear()

    def is_active(self):
        return self.state == NodeState.HANDSHAKED


class RelayMachine:
    def __init__(self):
        self.state = RelayState.IDLE
        self.message = None
        self.active_nodes = []
        self.current_index = 0
        self.results = []
        self._listeners = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def _notify(self):
        for callback in self._listeners:
            try:
                callback(self)
            except Exception as exc:
                logger.error("Relay listener error: %s", exc)

    def can_start(self):
        return self.state == RelayState.IDLE

    def start(self, message, nodes):
        if not self.can_start():
            return False
        self.message = message
        self.active_nodes = nodes
        self.current_index = 0
        self.results = []
        self.state = RelayState.FILLING
        self._notify()
        return True

    def fill_complete(self):
        if self.state == RelayState.FILLING:
            self.state = RelayState.SUBMITTING
            self._notify()

    def submit_complete(self):
        if self.state == RelayState.SUBMITTING:
            self.state = RelayState.WAITING
            self._notify()

    def response_received(self, node_name, response):
        if self.state == RelayState.WAITING:
            self.results.append((node_name, response))
            self.state = RelayState.RELAYING
            self._notify()

    def relay_complete(self):
        if self.state == RelayState.RELAYING:
            self.state = RelayState.COMPLETE
            self._notify()

    def error(self):
        self.state = RelayState.ERROR
        self._notify()

    def reset(self):
        self.message = None
        self.active_nodes = []
        self.current_index = 0
        self.results = []
        self.state = RelayState.IDLE
        self._notify()


# -----------------------------------------------------------------------------
# QS 4.3 BROWSER TRANSPORT
# -----------------------------------------------------------------------------
#
# The QS/MMRC model is still implemented as interacting Python state machines.
# Browser automation is deliberately isolated behind this transport boundary.
# Puppeteer owns the live Opera/CDP objects; Python owns relay/state/UI logic.
#
# A single Node child process stays attached to Opera for the lifetime of QS.
# Python communicates with it using newline-delimited JSON commands.
# -----------------------------------------------------------------------------

PUPPETEER_NODE_SCRIPT = r"""
const readline = require('readline');
const puppeteer = require('puppeteer-core');

let browser = null;

function reply(id, ok, result, error) {
    const payload = ok
        ? {id, ok: true, result}
        : {id, ok: false, error: String(error || 'Unknown error')};
    process.stdout.write(JSON.stringify(payload) + '\n');
}

async function connectBrowser() {
    if (browser) return browser;
    browser = await puppeteer.connect({
        browserURL: 'http://127.0.0.1:9222',
        // CRITICAL: preserve Opera's real page viewport. Puppeteer's default
        // viewport can impose a smaller virtual viewport on already-running
        // pages, leaving the rest of the Opera content area blank.
        defaultViewport: null
    });
    return browser;
}

async function findPage(pageId, urlHint) {
    const b = await connectBrowser();
    const pages = await b.pages();
    for (const page of pages) {
        let targetId = '';
        try { targetId = page.target()._targetId || ''; } catch (_) {}
        const url = page.url();
        if (pageId && targetId === pageId) return page;
        if (urlHint && (url === urlHint || url.includes(urlHint) || urlHint.includes(url))) {
            return page;
        }
    }
    return null;
}

async function pageMeta(page, index) {
    let title = '(no title)';
    let url = '';
    let pageId = '';
    try { title = await page.title(); } catch (_) {}
    try { url = page.url(); } catch (_) {}
    try { pageId = page.target()._targetId || ''; } catch (_) {}
    return {index, title, url, pageId};
}

async function handle(cmd) {
    switch (cmd.op) {
        case 'pages': {
            const b = await connectBrowser();
            const pages = await b.pages();
            const out = [];
            for (let i = 0; i < pages.length; i++) {
                out.push(await pageMeta(pages[i], i));
            }
            return out;
        }

        case 'title': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            return await page.title();
        }

        case 'bring_to_front': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            await page.bringToFront();
            return true;
        }

        case 'evaluate': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            return await page.evaluate(cmd.expression);
        }

        case 'query_one': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            return await page.evaluate((selector) => {
                try {
                    const elements = [...document.querySelectorAll(selector)];
                    for (let i = 0; i < elements.length; i++) {
                        const el = elements[i];
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        const visible = el.offsetWidth > 0 && el.offsetHeight > 0 &&
                                        rect.width > 0 && rect.height > 0 &&
                                        style.visibility !== 'hidden' &&
                                        style.display !== 'none';
                        if (visible) return {index: i};
                    }
                    return elements.length ? {index: 0} : null;
                } catch (_) {
                    return null;
                }
            }, cmd.selector);
        }

        case 'query_all_count': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            return await page.evaluate((selector) => {
                try { return document.querySelectorAll(selector).length; }
                catch (_) { return 0; }
            }, cmd.selector);
        }

        case 'element_is_visible': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return false;
            return await el.evaluate((node) => {
                const s = getComputedStyle(node);
                return node.offsetWidth > 0 && node.offsetHeight > 0 &&
                       s.visibility !== 'hidden' && s.display !== 'none';
            });
        }

        case 'element_is_disabled': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return true;
            return await el.evaluate((node) => !!(node.disabled || node.getAttribute('aria-disabled') === 'true'));
        }

        case 'element_get_attribute': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return null;
            return await el.evaluate((node, attribute) => node.getAttribute(attribute), cmd.attribute);
        }

        case 'element_inner_text': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return '';
            return await el.evaluate((node) => node.innerText || node.textContent || '');
        }

        case 'element_input_value': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return '';
            return await el.evaluate((node) => {
                if (typeof node.value === 'string') return node.value;
                return node.innerText || node.textContent || '';
            });
        }

        case 'element_focus': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) return false;
            await el.focus();
            return true;
        }

        case 'element_fill': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) throw new Error('Element not found: ' + cmd.selector);

            // Match Playwright's fast fill semantics rather than Puppeteer's
            // keyboard.type(), which visibly types one character at a time and
            // can become dramatically slower in web-app composers.
            await el.focus();
            await el.evaluate((node, value) => {
                const tag = (node.tagName || '').toLowerCase();
                const isContentEditable = node.getAttribute('contenteditable') === 'true';

                if (isContentEditable) {
                    node.innerHTML = '';
                    node.textContent = value;
                    node.dispatchEvent(new InputEvent('input', {
                        bubbles: true,
                        inputType: 'insertText',
                        data: value
                    }));
                    return;
                }

                if (tag === 'textarea' || tag === 'input') {
                    const proto = tag === 'textarea'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) {
                        setter.call(node, value);
                    } else {
                        node.value = value;
                    }
                    node.dispatchEvent(new Event('input', {bubbles: true}));
                    node.dispatchEvent(new Event('change', {bubbles: true}));
                    return;
                }

                node.textContent = value;
                node.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    inputType: 'insertText',
                    data: value
                }));
            }, cmd.text);

            return true;
        }

        case 'element_click': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) throw new Error('Element not found: ' + cmd.selector);
            await el.click();
            return true;
        }

        case 'keyboard_press': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            await page.keyboard.press(cmd.key);
            return true;
        }

        case 'disconnect': {
            if (browser) {
                await browser.disconnect();
                browser = null;
            }
            return true;
        }

        default:
            throw new Error('Unknown bridge operation: ' + cmd.op);
    }
}

const rl = readline.createInterface({
    input: process.stdin,
    crlfDelay: Infinity
});

let readySent = false;

(async () => {
    try {
        await connectBrowser();
        process.stdout.write(JSON.stringify({event: 'ready'}) + '\n');
        readySent = true;
    } catch (err) {
        console.error(String(err && err.stack || err));
        process.exit(2);
    }
})();

rl.on('line', async (line) => {
    if (!line.trim()) return;
    let cmd;
    try {
        cmd = JSON.parse(line);
    } catch (err) {
        process.stdout.write(JSON.stringify({id: null, ok: false, error: 'Invalid JSON command'}) + '\n');
        return;
    }

    try {
        const result = await handle(cmd);
        reply(cmd.id, true, result, null);
    } catch (err) {
        reply(cmd.id, false, null, err && err.stack || err);
    }
});
"""

class PuppeteerElement:
    def __init__(self, bridge, page_id, url, selector, index=0):
        self.bridge = bridge
        self.page_id = page_id
        self.url = url
        self.selector = selector
        self.index = index

    async def is_visible(self):
        return bool(await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_is_visible", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        ))

    async def is_disabled(self):
        return bool(await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_is_disabled", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        ))

    async def get_attribute(self, attribute):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_get_attribute", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index,
                "attribute": attribute
            }
        )

    async def inner_text(self):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_inner_text", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        )

    async def input_value(self):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_input_value", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        )

    async def focus(self):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_focus", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        )

    async def fill(self, text):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_fill", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index,
                "text": text
            }
        )

    async def click(self):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "element_click", "pageId": self.page_id, "url": self.url,
                "selector": self.selector, "index": self.index
            }
        )


class PuppeteerKeyboard:
    def __init__(self, bridge, page_id, url):
        self.bridge = bridge
        self.page_id = page_id
        self.url = url

    async def press(self, key):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "keyboard_press", "pageId": self.page_id, "url": self.url, "key": key
            }
        )


class PuppeteerPage:
    def __init__(self, bridge, page_id, url, title="(no title)"):
        self.bridge = bridge
        self.page_id = page_id
        self.url = url
        self._title = title
        self.keyboard = PuppeteerKeyboard(bridge, page_id, url)

    async def title(self):
        self._title = await asyncio.to_thread(
            self.bridge.request, {"op": "title", "pageId": self.page_id, "url": self.url}
        )
        return self._title

    async def bring_to_front(self):
        return await asyncio.to_thread(
            self.bridge.request, {"op": "bring_to_front", "pageId": self.page_id, "url": self.url}
        )

    async def evaluate(self, expression):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "evaluate", "pageId": self.page_id, "url": self.url, "expression": expression
            }
        )

    async def query_selector(self, selector):
        result = await asyncio.to_thread(
            self.bridge.request, {
                "op": "query_one", "pageId": self.page_id, "url": self.url, "selector": selector
            }
        )
        if result is None:
            return None
        return PuppeteerElement(self.bridge, self.page_id, self.url, selector, result.get("index", 0))

    async def query_selector_all(self, selector):
        count = await asyncio.to_thread(
            self.bridge.request, {
                "op": "query_all_count", "pageId": self.page_id, "url": self.url, "selector": selector
            }
        )
        return [
            PuppeteerElement(self.bridge, self.page_id, self.url, selector, i)
            for i in range(int(count or 0))
        ]


class PuppeteerBrowser:
    def __init__(self):
        self.bridge = PuppeteerBridge()

    async def pages(self):
        rows = await asyncio.to_thread(
            self.bridge.request, {"op": "pages"}
        )
        return [
            PuppeteerPage(
                self.bridge,
                row.get("pageId", ""),
                row["url"],
                row.get("title", "(no title)")
            )
            for row in rows
            if row.get("url")
        ]

    async def disconnect(self):
        try:
            await asyncio.to_thread(
                self.bridge.request, {"op": "disconnect"}
            )
        except Exception:
            pass
        self.bridge.close()


class PuppeteerBridge:
    def __init__(self):
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js was not found on PATH; QS 4.3 requires Node.js.")

        package_dir = os.path.join(STARTUP_DIR, "node_modules", "puppeteer-core")
        if not os.path.isdir(package_dir):
            raise RuntimeError(
                "puppeteer-core is not installed in the QuackSink directory. "
                "Run: npm install --no-save puppeteer-core@25.6.0"
            )

        self._lock = threading.Lock()
        self._next_id = 1
        self._closed = False
        self.process = subprocess.Popen(
            [node, "-e", PUPPETEER_NODE_SCRIPT],
            cwd=STARTUP_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            daemon=True
        )
        self._stderr_thread.start()

        deadline = time.time() + 15.0
        while time.time() < deadline:
            line = self.process.stdout.readline()
            if not line:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        "Puppeteer bridge exited during startup. "
                        "Check Node/puppeteer-core installation."
                    )
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("event") == "ready":
                return

        raise RuntimeError("Timed out while Puppeteer bridge was connecting to Opera CDP.")

    def _drain_stderr(self):
        try:
            for line in self.process.stderr:
                line = line.rstrip()
                if line:
                    logger.info("[PUPPETEER] %s", line)
        except Exception:
            pass

    def request(self, command):
        if self._closed:
            raise RuntimeError("Puppeteer bridge is closed.")

        with self._lock:
            command = dict(command)
            command["id"] = self._next_id
            self._next_id += 1
            request_id = command["id"]

            if not self.process.stdin or not self.process.stdout:
                raise RuntimeError("Puppeteer bridge pipes are unavailable.")

            self.process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
            self.process.stdin.flush()

            while True:
                line = self.process.stdout.readline()
                if not line:
                    code = self.process.poll()
                    raise RuntimeError(
                        f"Puppeteer bridge stopped unexpectedly (exit={code})."
                    )
                msg = json.loads(line)
                if msg.get("id") != request_id:
                    continue
                if not msg.get("ok"):
                    raise RuntimeError(msg.get("error", "Puppeteer bridge command failed."))
                return msg.get("result")

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except Exception:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass


class DOMAnalyzer:
    @staticmethod
    async def analyze(page):
        result = {
            "input": None,
            "assistant": None,
            "user": None
        }

        result["input"] = await page.evaluate(
            """
            () => {
                function visible(el) {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    return el.offsetWidth > 0 && el.offsetHeight > 0 &&
                           s.visibility !== 'hidden' && s.display !== 'none';
                }

                function uniqueSelector(el) {
                    if (!el) return null;

                    if (el.id) {
                        const id = '#' + CSS.escape(el.id);
                        if (document.querySelectorAll(id).length === 1) return id;
                    }

                    const attrs = [
                        'data-testid', 'data-message-author-role',
                        'aria-label', 'name', 'placeholder', 'role'
                    ];
                    for (const attr of attrs) {
                        const value = el.getAttribute(attr);
                        if (!value) continue;
                        const selector = el.tagName.toLowerCase() +
                            '[' + attr + '="' + CSS.escape(value) + '"]';
                        if (document.querySelectorAll(selector).length === 1) return selector;
                    }

                    const parts = [];
                    let cur = el;
                    while (cur && cur.nodeType === 1 && cur !== document.body) {
                        let part = cur.tagName.toLowerCase();
                        if (cur.id) {
                            part += '#' + CSS.escape(cur.id);
                            parts.unshift(part);
                            break;
                        }

                        const useful = [...cur.classList]
                            .filter(c => c.length > 0)
                            .slice(0, 3);
                        if (useful.length) {
                            part += useful.map(c => '.' + CSS.escape(c)).join('');
                        }

                        const parent = cur.parentElement;
                        if (parent) {
                            const same = [...parent.children]
                                .filter(x => x.tagName === cur.tagName);
                            if (same.length > 1) {
                                part += ':nth-of-type(' + (same.indexOf(cur) + 1) + ')';
                            }
                        }
                        parts.unshift(part);

                        const candidate = parts.join(' > ');
                        try {
                            if (document.querySelectorAll(candidate).length === 1) return candidate;
                        } catch (e) {}
                        cur = parent;
                    }

                    return parts.join(' > ');
                }

                const candidates = [
                    document.querySelector('textarea'),
                    document.querySelector('[contenteditable="true"]'),
                    document.querySelector('div[role="textbox"]'),
                    document.querySelector('input[type="text"]'),
                    document.querySelector('input:not([type])')
                ];

                for (const el of candidates) {
                    if (visible(el)) return uniqueSelector(el);
                }
                return null;
            }
            """
        )

        result["assistant"] = await page.evaluate(
            """
            () => {
                function visible(el) {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    return el.offsetWidth > 0 && el.offsetHeight > 0 &&
                           s.visibility !== 'hidden' && s.display !== 'none';
                }

                const stableSelectors = [
                    '[data-message-author-role="assistant"]',
                    '[data-role="assistant"]',
                    'model-response',
                    '.text-message',
                    'div[class*="assistant"]',
                    'div[class*="response"]'
                ];

                for (const selector of stableSelectors) {
                    let els = [];
                    try { els = [...document.querySelectorAll(selector)]; } catch (e) { continue; }
                    const meaningful = els.filter(el => visible(el) && (el.innerText || '').trim().length > 0);
                    if (meaningful.length) {
                        return selector;
                    }
                }

                return null;
            }
            """
        )

        result["user"] = await page.evaluate(
            """
            () => {
                function visible(el) {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    return el.offsetWidth > 0 && el.offsetHeight > 0 &&
                           s.visibility !== 'hidden' && s.display !== 'none';
                }
                const el = document.querySelector('[data-message-author-role="user"]') ||
                           document.querySelector('[data-role="user"]') ||
                           document.querySelector('div[class*="user"]') ||
                           document.querySelector('div[class*="human"]');
                if (!visible(el)) return null;

                if (el.id) {
                    const id = '#' + CSS.escape(el.id);
                    if (document.querySelectorAll(id).length === 1) return id;
                }
                const role = el.getAttribute('data-message-author-role');
                if (role) return el.tagName.toLowerCase() + '[data-message-author-role="' + CSS.escape(role) + '"]';

                const parts = [];
                let cur = el;
                while (cur && cur.nodeType === 1 && cur !== document.body) {
                    let part = cur.tagName.toLowerCase();
                    const useful = [...cur.classList].filter(c => c.length > 0).slice(0, 3);
                    if (useful.length) part += useful.map(c => '.' + CSS.escape(c)).join('');
                    const parent = cur.parentElement;
                    if (parent) {
                        const same = [...parent.children].filter(x => x.tagName === cur.tagName);
                        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(cur) + 1) + ')';
                    }
                    parts.unshift(part);
                    const candidate = parts.join(' > ');
                    try { if (document.querySelectorAll(candidate).length === 1) return candidate; } catch (e) {}
                    cur = parent;
                }
                return parts.join(' > ');
            }
            """
        )

        return result


class SelectorDetector:
    @staticmethod
    def get_known_selectors(name):
        known = {
            "DeepSeek": ("textarea, [contenteditable='true']", "div[class*='message']"),
            "Gemini": ("textarea, [contenteditable='true']", "model-response, .model-response-text"),
            "Claude": ("textarea, [contenteditable='true']", "article, div.assistant"),
            "GPT": ("textarea, [contenteditable='true']", "article, [data-message-author-role='assistant']"),
            "Grok": ("textarea, [contenteditable='true']", "div.markdown, .message-content"),
            "Qwen": ("textarea, [contenteditable='true']", "div.markdown, .message-content"),
            "Perplexity": ("textarea, [contenteditable='true']", "div.markdown, .message-content"),
            "Kimi": ("textarea, [contenteditable='true']", "div.markdown, .message-content"),
            "Aisha": ("textarea, [contenteditable='true']", "div[class*='message']"),
            "GLM": ("textarea, [contenteditable='true']", "div[class*='message']"),
            "Chron": ("textarea, [contenteditable='true']", "div[class*='message'], [data-message-id], .prose")
        }
        return known.get(name, (None, None))

    @staticmethod
    def detect_name_from_title(title):
        checks = [
            ("DeepSeek", "DeepSeek"), ("Gemini", "Gemini"), ("Claude", "Claude"),
            ("ChatGPT", "GPT"), ("GPT", "GPT"), ("Grok", "Grok"),
            ("Qwen", "Qwen"), ("Perplexity", "Perplexity"), ("Kimi", "Kimi"),
            ("Aisha", "Aisha"), ("GLM", "GLM"), ("Open WebUI", "Chron")
        ]
        for marker, name in checks:
            if marker in title:
                return name
        return None

    @staticmethod
    def generate_name(url):
        mappings = [
            ("chat.mistral.ai", "Mistral"), ("chat.z.ai", "GLM"),
            ("qwenlm.ai", "Qwen"), ("perplexity.ai", "Perplexity"),
            ("kimi.com", "Kimi"), ("gemini.google.com", "Gemini"),
            ("chat.deepseek.com", "DeepSeek"), ("deepseek.com", "DeepSeek"),
            ("aisha.ai", "Aisha"), ("claude.ai", "Claude"),
            ("chatgpt.com", "GPT"), ("grok.com", "Grok"),
            ("localhost:8080", "Chron")
        ]
        for domain, name in mappings:
            if domain in url:
                return name
        try:
            domain = url.split("//")[1].split("/")[0]
            parts = domain.split(".")
            if len(parts) >= 2:
                return parts[0].capitalize()
            return domain.capitalize()
        except Exception:
            return "LLM"


class QSUI:
    def __init__(self, controller):
        self.root = tk.Tk()
        self.root.title(f"QuackSink QS {VERSION} - Structural DOMAnalyzer")
        self.root.geometry("1200x1050")
        self.root.configure(bg="#121212")
        self.controller = controller
        self.nodes = {}
        self.relay_state = RelayState.IDLE
        self.show_system_logs = tk.BooleanVar(value=False)
        self.human_handle = load_config().get("human_handle", "Cozmo")
        self.archive_paths = {}
        self.selected_archive = tk.StringVar()
        self.send_order = []
        self._build_ui()
        self._refresh_archive_selector()
        self._update_relay_button()

    def _build_ui(self):
        tk.Label(
            self.root, text=f"QUACKSINK - MULTI-MIND RELAY CORE - QS {VERSION}",
            font=("Arial", 16, "bold"), bg="#121212", fg="#00FFCC"
        ).pack(pady=(10, 0))

        title_frame = tk.Frame(self.root, bg="#121212")
        title_frame.pack(pady=(5, 3), fill=tk.X, padx=20)

        tk.Label(
            title_frame, text="TITLE:", font=("Arial", 12, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.title_entry = tk.Entry(
            title_frame, font=("Arial", 14, "bold"),
            bg="#1e1e1e", fg="#ffffff", insertbackground="white"
        )
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(
            title_frame, text="make title", command=self._make_title_file,
            bg="#00AA55", fg="white", font=("Arial", 11, "bold"),
            height=1, padx=12
        ).pack(side=tk.LEFT)

        tk.Label(
            self.root, text="ACTIVE NODES: (discovered from open tabs)",
            font=("Arial", 14, "bold"), bg="#121212", fg="#ffffff"
        ).pack(pady=(10, 5))

        self.nodes_frame = tk.Frame(self.root, bg="#121212")
        self.nodes_frame.pack(pady=5)
        self._render_nodes()

        order_frame = tk.Frame(self.root, bg="#121212")
        order_frame.pack(fill=tk.X, padx=20, pady=(4, 4))
        tk.Label(
            order_frame, text="SEND ORDER (top → bottom):",
            font=("Arial", 12, "bold"), bg="#121212", fg="#00FFCC"
        ).pack(anchor=tk.W)
        self.send_order_list = tk.Listbox(
            order_frame, height=5, width=42,
            font=("Arial", 12, "bold"),
            bg="#1e1e1e", fg="#ffffff", selectbackground="#0066AA",
            selectforeground="#ffffff", activestyle="none"
        )
        self.send_order_list.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(2, 0))
        order_buttons = tk.Frame(order_frame, bg="#121212")
        order_buttons.pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(
            order_buttons, text="▲ UP", command=self._move_send_order_up,
            bg="#0066AA", fg="white", font=("Arial", 10, "bold"), padx=8
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            order_buttons, text="▼ DOWN", command=self._move_send_order_down,
            bg="#663399", fg="white", font=("Arial", 10, "bold"), padx=8
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            order_buttons, text="SYNC", command=self._sync_send_order,
            bg="#555555", fg="white", font=("Arial", 10, "bold"), padx=8
        ).pack(fill=tk.X, pady=2)
        tk.Label(
            order_frame,
            text="This order is independent of discovery and activation order.",
            font=("Arial", 10), bg="#121212", fg="#888888"
        ).pack(side=tk.LEFT, padx=(10, 0))

        ctrl_bar = tk.Frame(self.root, bg="#121212")
        ctrl_bar.pack(pady=(10, 0))

        tk.Label(ctrl_bar, text="Human Handle:", font=("Arial", 14, "bold"),
                 bg="#121212", fg="#00FFCC").pack(side=tk.LEFT, padx=(0, 5))
        self.handle_entry = tk.Entry(ctrl_bar, font=("Arial", 14, "bold"),
                                     bg="#1e1e1e", fg="#ffffff", width=15,
                                     insertbackground="white")
        self.handle_entry.insert(0, self.human_handle)
        self.handle_entry.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(ctrl_bar, text="Save Handle", command=self._save_handle,
                  bg="#00AA55", fg="white", font=("Arial", 11, "bold"),
                  height=1, padx=8).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(ctrl_bar, text="Font:", font=("Arial", 14, "bold"),
                 bg="#121212", fg="#00FFCC").pack(side=tk.LEFT, padx=(0, 5))
        self.font_box = ttk.Combobox(
            ctrl_bar,
            values=[10, 12, 14, 15, 16, 18, 20, 22, 24, 28, 32, 36, 40, 48],
            width=4, state="readonly", font=("Arial", 12, "bold")
        )
        self.font_box.pack(side=tk.LEFT, padx=(0, 20))
        self.font_box.bind("<<ComboboxSelected>>", self._on_font_change)

        self.log_toggle_btn = tk.Button(
            ctrl_bar, text="SYSTEM LOG: OFF", command=self._toggle_log_mode,
            bg="#444444", fg="#ffffff", font=("Arial", 11, "bold"),
            height=1, padx=8
        )
        self.log_toggle_btn.pack(side=tk.LEFT, padx=5)

        tk.Button(ctrl_bar, text="REFRESH", command=self.controller.scan,
                  bg="#FF8800", fg="black", font=("Arial", 11, "bold"),
                  height=1, padx=8).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_bar, text="ADD NODE (disabled)", command=self._manual_add,
                  bg="#444444", fg="#666666", font=("Arial", 11, "bold"),
                  height=1, padx=8, state=tk.DISABLED).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_bar, text="CLEAR", command=self.controller.clear_all,
                  bg="#FF4444", fg="white", font=("Arial", 11, "bold"),
                  height=1, padx=8).pack(side=tk.LEFT, padx=5)

        archive_frame = tk.Frame(self.root, bg="#121212")
        archive_frame.pack(pady=(12, 3), fill=tk.X, padx=20)

        archive_label_row = tk.Frame(archive_frame, bg="#121212")
        archive_label_row.pack(fill=tk.X)
        tk.Label(archive_label_row, text="ARCHIVE:", font=("Arial", 12, "bold"),
                 bg="#121212", fg="#00FFCC").pack(side=tk.LEFT, padx=(0, 8))

        archive_style = ttk.Style(self.root)
        try:
            archive_style.configure(
                "QSArchive.TCombobox",
                font=("Arial", 18, "bold")
            )
        except Exception:
            pass

        self.archive_box = ttk.Combobox(
            archive_label_row, textvariable=self.selected_archive,
            state="readonly", width=42, font=("Arial", 18, "bold"),
            style="QSArchive.TCombobox"
        )
        self.archive_box.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
        self.archive_box.bind("<<ComboboxSelected>>", self._on_archive_selected)

        try:
            self.root.option_add("*TCombobox*Listbox.font", ("Arial", 18, "bold"))
        except Exception:
            pass

        # Archive actions stay in one horizontal row so they do not consume
        # the vertical space needed by the relay display.
        archive_button_row = tk.Frame(archive_frame, bg="#121212")
        archive_button_row.pack(fill=tk.X, pady=(4, 0))
        archive_button_specs = [
            ("REFRESH ARCHIVES", self._refresh_archive_selector, "#555555", 8),
            ("COPY LOG TO CLIPBOARD AS TEXT", self._copy_selected_log, "#0066AA", 8),
            ("COPY SOURCE TO CLIPBOARD AS TEXT", self._copy_selected_source, "#663399", 8),
            ("LIBRARY", self._open_library, "#0088AA", 10),
            ("WHAT CAN THIS DO?", self._open_what_can_this_do, "#AA5500", 10),
        ]
        for label, command, bg, padx in archive_button_specs:
            tk.Button(
                archive_button_row, text=label, command=command,
                bg=bg, fg="white", font=("Arial", 9, "bold"),
                height=1, padx=padx
            ).pack(side=tk.LEFT, padx=3)

        tk.Label(
            self.root,
            text="BROADCAST MESSAGE:", font=("Arial", 14, "bold"),
            bg="#121212", fg="#ffffff"
        ).pack(pady=(10, 5))

        self.text_input = tk.Text(
            self.root, height=3, width=85, font=("Consolas", 20),
            bg="#1e1e1e", fg="#ffffff", insertbackground="white"
        )
        self.text_input.pack(pady=5)
        # A real Enter keypress in the human input box triggers the same
        # Fan-Out path as the button.  Paste operations do not generate
        # <Return>/<KP_Enter> events, so pasted newlines remain ordinary text.
        self.text_input.bind("<Return>", self._on_input_enter)
        self.text_input.bind("<KP_Enter>", self._on_input_enter)

        btn_frame = tk.Frame(self.root, bg="#121212")
        btn_frame.pack(pady=5)
        self.relay_btn = tk.Button(
            btn_frame, text="FAN-OUT", command=self.controller.start_relay,
            bg="#444444", fg="white", font=("Arial", 16, "bold"),
            height=1, padx=15, state=tk.DISABLED
        )
        self.relay_btn.pack(side=tk.LEFT, padx=10)

        tk.Button(
            btn_frame, text="TOP", command=self.scroll_to_top,
            bg="#0066AA", fg="white", font=("Arial", 12, "bold"),
            height=1, padx=12
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="BOTTOM", command=self.scroll_to_bottom,
            bg="#663399", fg="white", font=("Arial", 12, "bold"),
            height=1, padx=12
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(self.root, text="RELAY DISPLAY:", font=("Arial", 14, "bold"),
                 bg="#121212", fg="#ffffff").pack(pady=(5, 3))

        log_frame = tk.Frame(self.root, bg="#121212")
        log_frame.pack(pady=5, fill=tk.BOTH, expand=True, padx=20)
        self.log_box = tk.Text(
            log_frame, height=16, font=("Consolas", 20), bg="#1e1e1e",
            fg="#ffffff", insertbackground="white", wrap=tk.WORD
        )
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    @staticmethod
    def _valid_title_filename(name):
        if not name:
            return False, "Title filename cannot be empty."

        if name in (".", ".."):
            return False, "Title filename cannot be '.' or '..'."

        invalid_chars = '<>:"/\\|?*'
        if any(ch in name for ch in invalid_chars):
            return False, "Title filename contains a Windows-invalid character."

        if any(ord(ch) < 32 for ch in name):
            return False, "Title filename contains a control character."

        if name.endswith(" ") or name.endswith("."):
            return False, "Title filename cannot end with a space or period."

        base = name.split(".", 1)[0].rstrip(" .").upper()
        reserved = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }
        if base in reserved:
            return False, f"'{base}' is a reserved Windows filename."

        return True, ""

    def _make_title_file(self):
        raw_name = self.title_entry.get().strip()
        if not raw_name:
            self.log("[TITLE] Filename cannot be empty.", is_system=True)
            return

        # The field is the filename stem; QuackSink supplies the .title extension.
        if raw_name.lower().endswith(TITLE_EXTENSION):
            raw_name = raw_name[:-len(TITLE_EXTENSION)].rstrip()

        valid, reason = self._valid_title_filename(raw_name)
        if not valid:
            self.log(f"[TITLE] Invalid filename '{raw_name}': {reason}", is_system=True)
            return

        archive_path = self._selected_archive_path()
        if not archive_path:
            return

        title_name = raw_name + TITLE_EXTENSION
        title_path = os.path.join(archive_path, title_name)

        try:
            # Exclusive creation proves the file can actually be created and
            # prevents an existing title from being silently overwritten.
            with open(title_path, "x", encoding="utf-8"):
                pass

            size = os.path.getsize(title_path)
            if size != 0:
                self.log(
                    f"[TITLE] ERROR: created title is not empty: {title_path}",
                    is_system=True
                )
                return

            self.log(
                f"[TITLE] SUCCESS: created empty title file: {title_path}",
                is_system=True
            )
            self.title_entry.delete(0, tk.END)
        except FileExistsError:
            self.log(
                f"[TITLE] Title already exists; nothing overwritten: {title_path}",
                is_system=True
            )
        except OSError as exc:
            self.log(
                f"[TITLE] Could not create '{title_name}': {exc}",
                is_system=True
            )
        except Exception as exc:
            self.log(
                f"[TITLE] Unexpected error creating '{title_name}': {exc}",
                is_system=True
            )

    def _manual_add(self):
        pass

    def _save_handle(self):
        handle = self.handle_entry.get().strip()
        if handle:
            self.human_handle = handle
            config = load_config()
            config["human_handle"] = handle
            save_config(config)
            self.log(f"[CONFIG] Human handle saved: {handle}", is_system=True)
        else:
            self.log("[CONFIG] Handle cannot be empty.", is_system=True)

    def _toggle_log_mode(self):
        current = self.show_system_logs.get()
        self.show_system_logs.set(not current)
        if self.show_system_logs.get():
            self.log_toggle_btn.config(text="SYSTEM LOG: ON", bg="#FF8800", fg="black")
        else:
            self.log_toggle_btn.config(text="SYSTEM LOG: OFF", bg="#444444", fg="white")

    def _render_nodes(self):
        for widget in self.nodes_frame.winfo_children():
            widget.destroy()
        if not self.nodes:
            tk.Label(
                self.nodes_frame,
                text="No nodes. Click REFRESH to discover tabs.",
                font=("Arial", 14, "bold"), bg="#121212", fg="#666666"
            ).pack(pady=10)
            self._render_send_order()
            return

        # Keep the active-node roster on one compact row whenever possible.
        row = tk.Frame(self.nodes_frame, bg="#121212")
        row.pack(fill=tk.X)
        keys = list(self.nodes.keys())

        for name in keys:
            node = self.nodes[name]
            state_icon = NodeState.icon(node.state)
            stack_size = len(node.stack)
            indicator = f" ({stack_size})" if stack_size > 0 else ""
            var = tk.BooleanVar(value=node.is_active())
            node._var = var
            cb = tk.Checkbutton(
                row,
                text=f"{state_icon} {node.icon} {node.name}{indicator}",
                variable=var,
                command=lambda n=name: self._on_toggle(n),
                font=("Arial", 14, "bold"), bg="#121212",
                fg="#ffffff", selectcolor="#222222", activebackground="#121212",
                activeforeground="#00FFCC",
                state=(tk.NORMAL if node.can_toggle() else tk.DISABLED)
            )
            cb.pack(side=tk.LEFT, padx=12)
        self._render_send_order()

    def _on_toggle(self, name):
        node = self.nodes.get(name)
        if not node:
            return

        requested_on = bool(node._var.get())

        if requested_on:
            self.controller.toggle_on(node)
        else:
            self.controller.toggle_off(node)

    def set_send_order(self, names):
        self.send_order = list(names)
        self._render_send_order()

    def _render_send_order(self):
        if not hasattr(self, "send_order_list"):
            return
        names = [name for name in self.send_order if name in self.nodes]
        for name in self.nodes:
            if name not in names:
                names.append(name)
        self.send_order = names
        self.send_order_list.delete(0, tk.END)
        for name in names:
            self.send_order_list.insert(tk.END, name)

    def _persist_send_order(self):
        try:
            self.controller.send_order = list(self.send_order)
            config = load_config()
            config["send_order"] = list(self.send_order)
            save_config(config)
        except Exception as exc:
            self.log(f"[ORDER] Could not save send order: {exc}", is_system=True)

    def _sync_send_order(self):
        self._render_send_order()
        self._persist_send_order()
        self.log(f"[ORDER] Send order: {self.send_order}", is_system=True)

    def _move_send_order_up(self):
        if self.controller.relay_state != RelayState.IDLE:
            return
        selection = self.send_order_list.curselection()
        if not selection:
            return
        i = selection[0]
        if i <= 0:
            return
        self.send_order[i - 1], self.send_order[i] = self.send_order[i], self.send_order[i - 1]
        self._render_send_order()
        self.send_order_list.selection_set(i - 1)
        self._persist_send_order()

    def _move_send_order_down(self):
        if self.controller.relay_state != RelayState.IDLE:
            return
        selection = self.send_order_list.curselection()
        if not selection:
            return
        i = selection[0]
        if i >= len(self.send_order) - 1:
            return
        self.send_order[i + 1], self.send_order[i] = self.send_order[i], self.send_order[i + 1]
        self._render_send_order()
        self.send_order_list.selection_set(i + 1)
        self._persist_send_order()

    def _on_font_change(self, event=None):
        size = self.font_box.get()
        if size:
            size = int(size)
            self.text_input.configure(font=("Consolas", size))
            self.log_box.configure(font=("Consolas", size))

    def node_added(self, node):
        self.nodes[node.name] = node
        node.add_listener(self._on_node_change)
        self._render_nodes()
        self._render_send_order()
        self._update_relay_button()

    def _on_node_change(self, node, old, new):
        self._render_nodes()
        self._update_relay_button()

    def _update_relay_button(self):
        active = any(node.is_active() for node in self.nodes.values())
        if active and self.relay_state == RelayState.IDLE:
            self.relay_btn.config(state=tk.NORMAL, bg="#00AA55")
        else:
            self.relay_btn.config(state=tk.DISABLED, bg="#444444")

    def relay_state_changed(self, state):
        self.relay_state = state
        self._update_relay_button()

    def fanout_finished(self):
        # Called only after the controller has completed the final completion
        # log write and then reset RelayMachine from COMPLETE to IDLE.  The
        # relay button has therefore already been re-enabled by _update_relay_button.
        # Schedule the viewport move on Tk's event loop without using a clock
        # delay or assuming that an elapsed interval means anything is complete.
        self.root.after_idle(self.scroll_to_top)

    def scroll_to_top(self):
        try:
            self.log_box.yview_moveto(0.0)
        except Exception as exc:
            logger.error("Relay display TOP navigation failed: %s", exc)

    def scroll_to_bottom(self):
        try:
            self.log_box.yview_moveto(1.0)
        except Exception as exc:
            logger.error("Relay display BOTTOM navigation failed: %s", exc)

    def log(self, text, is_system=False):
        logger.info(text)
        if not is_system or self.show_system_logs.get():
            self.log_box.insert(tk.END, text + "\n")
            self.log_box.see(tk.END)

    def clear_log(self):
        self.log_box.delete("1.0", tk.END)

    def _on_input_enter(self, event=None):
        self.controller.start_relay()
        return "break"

    def get_message(self):
        return self.text_input.get("1.0", tk.END).strip()

    def clear_input(self):
        self.text_input.delete("1.0", tk.END)

    def get_human_handle(self):
        return self.human_handle

    @staticmethod
    def _archive_display_name(path):
        name = os.path.basename(os.path.normpath(path))
        return name

    def _discover_archives(self):
        archives = []
        try:
            for entry in os.listdir(ARCHIVE_ROOT):
                full = os.path.join(ARCHIVE_ROOT, entry)
                if (
                    entry.startswith(ARCHIVE_PREFIX + "_")
                    and _archive_version_from_name(entry)
                    and os.path.isdir(full)
                ):
                    archives.append(full)
        except Exception as exc:
            logger.error("Archive discovery failed: %s", exc)
        archives.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return archives

    def _refresh_archive_selector(self):
        archives = self._discover_archives()
        self.archive_paths = {
            self._archive_display_name(path): path
            for path in archives
        }
        display_names = list(self.archive_paths.keys())
        self.archive_box["values"] = display_names

        current_display = self._archive_display_name(ACTIVE_ARCHIVE_DIR)
        if current_display in self.archive_paths:
            self.selected_archive.set(current_display)
        elif display_names:
            self.selected_archive.set(display_names[0])
        else:
            self.selected_archive.set("")

        logger.info("Archive selector refreshed: %d archives found.", len(display_names))

    def _on_archive_selected(self, event=None):
        selected = self.selected_archive.get()
        path = self.archive_paths.get(selected)
        if path:
            logger.info("Archive selected: %s", path)
            self.log(f"[ARCHIVE] Selected: {selected}", is_system=True)

    def _selected_archive_path(self):
        selected = self.selected_archive.get()
        path = self.archive_paths.get(selected)
        if not path:
            self.log("[ARCHIVE] No archive selected.", is_system=True)
            return None
        if not os.path.isdir(path):
            self.log(f"[ARCHIVE] Archive no longer exists: {path}", is_system=True)
            self._refresh_archive_selector()
            return None
        return path

    def _copy_text_to_clipboard(self, text, description):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            self.log(f"[CLIPBOARD] {description} copied as text.", is_system=True)
            return True
        except Exception as exc:
            self.log(f"[CLIPBOARD] Copy failed: {exc}", is_system=True)
            return False

    def _copy_selected_log(self):
        archive_path = self._selected_archive_path()
        if not archive_path:
            return

        log_path = os.path.join(archive_path, "LOG.txt")
        if not os.path.isfile(log_path):
            self.log(f"[CLIPBOARD] LOG.txt not found: {log_path}", is_system=True)
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                contents = f.read()
        except Exception as exc:
            self.log(f"[CLIPBOARD] Could not read {log_path}: {exc}", is_system=True)
            return

        header = (
            f"QS FILE: {os.path.relpath(log_path, STARTUP_DIR)}\n"
            f"=============================================================\n"
        )
        self._copy_text_to_clipboard(header + contents, log_path)

    def _copy_selected_source(self):
        archive_path = self._selected_archive_path()
        if not archive_path:
            return

        source_path = os.path.join(archive_path, RUNTIME_FILE)
        if not os.path.isfile(source_path):
            self.log(f"[CLIPBOARD] {RUNTIME_FILE} not found: {source_path}", is_system=True)
            return

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                contents = f.read()
        except Exception as exc:
            self.log(f"[CLIPBOARD] Could not read {source_path}: {exc}", is_system=True)
            return

        header = (
            f"QS FILE: {os.path.relpath(source_path, STARTUP_DIR)}\n"
            f"=============================================================\n"
        )
        self._copy_text_to_clipboard(header + contents, source_path)

    def _open_library(self):
        try:
            webbrowser.open(LIBRARY_INDEX_URL)
            self.log(f"[LIBRARY] Opened Library index: {LIBRARY_INDEX_URL}", is_system=True)
        except Exception as exc:
            self.log(f"[LIBRARY] Could not open Library index: {exc}", is_system=True)

    def _open_what_can_this_do(self):
        try:
            webbrowser.open(WHAT_CAN_THIS_DO_URL)
            self.log(
                f"[PUBLIC] Opened What can this do?: {WHAT_CAN_THIS_DO_URL}",
                is_system=True
            )
        except Exception as exc:
            self.log(f"[PUBLIC] Could not open video: {exc}", is_system=True)

    def run(self):
        self.root.mainloop()


class QSController:
    def __init__(self):
        self.nodes = {}
        config = load_config()
        self.send_order = list(config.get("send_order", []))
        self._handshake_lock = threading.Lock()
        self.relay = RelayMachine()
        self.relay.add_listener(self._on_relay_change)
        self.ui = QSUI(self)
        self.ui.set_send_order(self.send_order)
        self._scan_lock = False
        self.browser = None
        self.ui.root.after(100, self.scan)

    def _get_browser(self):
        if self.browser is None:
            self.browser = PuppeteerBrowser()
        return self.browser

    def scan(self):
        if self._scan_lock:
            return
        self._scan_lock = True
        self.ui.log("[SCAN] Starting discovery via Puppeteer/CDP...", is_system=True)
        threading.Thread(
            target=lambda: asyncio.run(self._do_scan()), daemon=True
        ).start()

    async def _do_scan(self):
        browser = None
        try:
            browser = self._get_browser()
            pages = await browser.pages()

            self.ui.log("[DISCOVERY] === ALL OPEN PAGES ===", is_system=True)
            for idx, page in enumerate(pages):
                try:
                    title = await page.title()
                except Exception:
                    title = "(no title)"
                self.ui.log(f"Page {idx}: id={page.page_id} | {page.url} | TITLE={title}", is_system=True)
            self.ui.log("[DISCOVERY] === END ===", is_system=True)

            for page in pages:
                url = page.url
                if "http" not in url:
                    continue
                try:
                    title = await page.title()
                except Exception:
                    title = "(no title)"

                name = SelectorDetector.detect_name_from_title(title)
                if not name:
                    name = SelectorDetector.generate_name(url)
                    if name == "LLM":
                        continue

                if any(node.url == url for node in self.nodes.values()):
                    continue

                self.ui.log(
                    f"[ANALYZE] Running structural DOM analysis on {name}...",
                    is_system=True
                )
                dom_result = await DOMAnalyzer.analyze(page)
                input_sel = dom_result.get("input")
                output_sel = dom_result.get("assistant")

                if not input_sel or not output_sel:
                    self.ui.log(
                        f"[ANALYZE] Structural analysis incomplete for {name}. Falling back.",
                        is_system=True
                    )
                    fallback_input, fallback_output = SelectorDetector.get_known_selectors(name)
                    if not input_sel:
                        input_sel = fallback_input
                    if not output_sel:
                        output_sel = fallback_output

                if input_sel and output_sel:
                    node = next((n for n in self.nodes.values() if n.page_id == page.page_id), None)
                    if node is None:
                        node_name = name
                        if node_name in self.nodes and self.nodes[node_name].page_id != page.page_id:
                            suffix = 2
                            while f"{name} {suffix}" in self.nodes:
                                suffix += 1
                            node_name = f"{name} {suffix}"
                        node = Node(node_name, url)
                        node.page_id = page.page_id
                        self.nodes[node.name] = node
                        node.add_listener(self._on_node_change)
                        self.ui.log(
                            f"[DISCOVERY] Node added: {node.name} (input: {input_sel}, output: {output_sel})",
                            is_system=True
                        )
                    else:
                        node.url = url
                        node.page_id = page.page_id
                        self.ui.log(
                            f"[DISCOVERY] Node refreshed: {node.name} (page identity stable; URL may have changed)",
                            is_system=True
                        )
                    node.input_selector = input_sel
                    node.output_selector = output_sel
                    if dom_result.get("user"):
                        node.user_selector = dom_result["user"]
                    if node.name not in self.send_order:
                        self.send_order.append(node.name)
                        self.ui.send_order = list(self.send_order)
                        self.ui._render_send_order()
                    self.ui.node_added(node)
                else:
                    self.ui.log(
                        f"[DISCOVERY] Could not find selectors for {url}",
                        is_system=True
                    )

            self.ui.log("[DISCOVERY] Scan complete.", is_system=True)
        except Exception as exc:
            self.ui.log(f"[ERROR] Scan failed: {exc}", is_system=True)
        finally:
            self._scan_lock = False

    def toggle_on(self, node):
        if not node.can_toggle():
            return
        node.toggle_on()
        self.ui.log(
            f"[TOGGLE] {node.name} ON. Starting Library introduction...",
            is_system=True
        )
        threading.Thread(
            target=lambda: self._run_handshake_serial(node), daemon=True
        ).start()

    def _run_handshake_serial(self, node):
        with self._handshake_lock:
            asyncio.run(self._do_handshake(node))

    def toggle_off(self, node):
        node.toggle_off()
        self.ui.log(f"[TOGGLE] {node.name} OFF.", is_system=True)

    def clear_all(self):
        self.nodes = {}
        self.send_order = []
        self.ui.nodes = {}
        self.relay.reset()
        self.ui.send_order = []
        self.ui._render_nodes()
        self.ui._render_send_order()
        self.ui._update_relay_button()
        self.ui.log("[CLEAR] All nodes removed.", is_system=True)

    def _ordered_active_nodes(self):
        active = [node for node in self.nodes.values() if node.is_active()]
        by_name = {node.name: node for node in active}
        ordered = [by_name[name] for name in self.send_order if name in by_name]
        ordered.extend(node for node in active if node.name not in self.send_order)
        return ordered

    def _build_roster(self):
        roster = [f"🎩 {self.ui.get_human_handle()} (Human)"]
        for node in self._ordered_active_nodes():
            roster.append(f"{node.icon} {node.name}")
        return "\n".join(roster) if roster else "🎩 Cozmo (Human)"

    async def _find_page_for_node(self, node):
        browser = self._get_browser()
        pages = await browser.pages()
        for page in pages:
            if node.page_id and page.page_id == node.page_id:
                return page
        for page in pages:
            if node.url in page.url:
                return page
        return None

    async def _browser_generation_state(self, page):
        """Return explicit browser generation/composer state plus diagnostics."""
        try:
            return await page.evaluate("""
                () => {
                    function visible(el) {
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               s.visibility !== 'hidden' &&
                               s.display !== 'none';
                    }

                    const busyPatterns = [
                        'stop', 'cancel', 'generating'
                    ];

                    let busyControl = false;
                    const busyMatches = [];
                    const controls = [
                        ...document.querySelectorAll('button'),
                        ...document.querySelectorAll('[role="button"]')
                    ];

                    for (const el of controls) {
                        if (!visible(el)) continue;
                        const aria = (el.getAttribute('aria-label') || '').trim();
                        const text = (el.innerText || el.textContent || '').trim();
                        const combined = `${aria} ${text}`.toLowerCase().trim();
                        if (busyPatterns.some(p => combined.includes(p))) {
                            busyControl = true;
                            busyMatches.push({aria, text});
                        }
                    }

                    let composerReady = false;
                    let composerMatches = [];
                    const composers = [
                        ...document.querySelectorAll('textarea'),
                        ...document.querySelectorAll('[contenteditable="true"]')
                    ];

                    for (const el of composers) {
                        if (!visible(el)) continue;
                        const disabled = !!(
                            el.disabled ||
                            el.getAttribute('aria-disabled') === 'true'
                        );
                        const tag = el.tagName.toLowerCase();
                        const aria = (el.getAttribute('aria-label') || '').trim();
                        const placeholder = (el.getAttribute('placeholder') || '').trim();
                        composerMatches.push({tag, aria, placeholder, disabled});
                        if (!disabled) composerReady = true;
                    }

                    return {
                        busyControl,
                        busyMatches,
                        composerReady,
                        composerMatches,
                        url: location.href,
                        title: document.title
                    };
                }
            """)
        except Exception as exc:
            return {
                "busyControl": None,
                "composerReady": None,
                "busyMatches": [],
                "composerMatches": [],
                "error": f"{type(exc).__name__}: {exc}"
            }

    async def _wait_for_idle_after_introduction(self, page, node, timeout=90):
        start = asyncio.get_event_loop().time()
        stable_idle = 0

        # Do not infer completion from the response scraper or from one
        # particular Send-button implementation.  Ask the browser directly:
        # generation controls gone AND composer usable again.
        while asyncio.get_event_loop().time() - start < timeout:
            await asyncio.sleep(0.5)

            state = await self._browser_generation_state(page)
            if state.get("error"):
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: browser-state probe ERROR: "
                    f"{state.get('error')}",
                    is_system=True
                )
                stable_idle = 0
                continue

            busy = bool(state.get("busyControl"))
            composer_ready = bool(state.get("composerReady"))

            # Diagnostic heartbeat: one line per second while waiting.
            if int((asyncio.get_event_loop().time() - start) * 2) % 2 == 0:
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: busy={busy} "
                    f"composer_ready={composer_ready} "
                    f"busy_matches={state.get('busyMatches', [])} "
                    f"composers={state.get('composerMatches', [])}",
                    is_system=True
                )

            # For introduction completion, generation state is the authoritative
            # signal.  The composer DOM is not a reliable readiness gate across
            # current GPT UI states: the same input that accepted the preamble can
            # temporarily disappear/re-render while the browser is already idle.
            # Require the browser to report not-busy for three consecutive samples.
            if not busy:
                stable_idle += 1
                if stable_idle >= 3:
                    self.ui.log(
                        f"[INTRO] {node.name}: browser generation idle; "
                        f"composer_ready={composer_ready}.",
                        is_system=True
                    )
                    return True
            else:
                stable_idle = 0

        self.ui.log(
            f"[INTRO] {node.name}: generation state never reached "
            f"stable idle before timeout.",
            is_system=True
        )
        return False


    async def _do_handshake(self, node):
        try:
            page = await self._find_page_for_node(node)
            if not page:
                self.ui.log(f"[ERROR] {node.name} offline.", is_system=True)
                node.handshake_failed()
                return


            node.introduction_start()
            self.ui.log(
                f"[INTRO] {node.name}: Library preamble state entered.",
                is_system=True
            )

            preamble_success = await self._send_message_to_page(
                page, node, QS_PUBLIC_PREAMBLE, is_handshake=False
            )

            if not preamble_success:
                node.introduction_failed()
                self.ui.log(
                    f"[INTRO] {node.name}: failed to send embedded Library preamble.",
                    is_system=True
                )
                return

            self.ui.log(
                f"[INTRO] {node.name}: embedded Library preamble sent; waiting for browser/model to return idle before handshake.",
                is_system=True
            )
            if not await self._wait_for_idle_after_introduction(page, node, timeout=90):
                node.introduction_failed()
                self.ui.log(
                    f"[INTRO] {node.name}: preamble did not settle before handshake window.",
                    is_system=True
                )
                return

            node.introduction_success()
            self.ui.log(
                f"[INTRO] {node.name}: Library introduction complete; entering handshake.",
                is_system=True
            )

            node.handshake_start()
            handshake_msg = QS_HANDSHAKE_TEMPLATE.format(roster=self._build_roster())
            success = await self._send_message_to_page(
                page, node, handshake_msg, is_handshake=True
            )

            if success:
                responded = await self._wait_for_response(
                    page, node, timeout=45, is_handshake=True
                )
                if responded:
                    raw = await self._get_response(page, node, is_handshake=True)
                    clean, dropped = self._parse_response(raw, is_handshake=True)
                    if clean and not dropped:
                        node.handshake_success()
                        self.ui.log(
                            f"[HANDSHAKE] {node.name} SUCCESS!",
                            is_system=True
                        )
                        announcement = f"{node.icon} {node.name} - {clean}"
                        self.ui.log(f"\n[ANNOUNCE] {announcement}\n", is_system=False)
                        for target in self.nodes.values():
                            if target.is_active() and target != node:
                                target.stack.append(announcement)
                        return
                    self.ui.log(
                        f"[HANDSHAKE] {node.name} FAILED (invalid response).",
                        is_system=True
                    )
                else:
                    self.ui.log(f"[HANDSHAKE] {node.name} TIMEOUT.", is_system=True)
            else:
                self.ui.log(f"[HANDSHAKE] {node.name} FAILED to send.", is_system=True)

            node.handshake_failed()
        except Exception as exc:
            node.handshake_failed()
            self.ui.log(
                f"[ERROR] Handshake with {node.name}: {exc}",
                is_system=True
            )

    def start_relay(self):
        message = self.ui.get_message()
        if not message:
            self.ui.log("[RELAY] Aborting: Empty message.", is_system=True)
            return
        active_nodes = self._ordered_active_nodes()
        if not active_nodes:
            self.ui.log("[RELAY] Aborting: No active nodes.", is_system=True)
            return

        self.ui.clear_input()
        self.ui.clear_log()
        payload = f"🎩 {self.ui.get_human_handle()} - {message}"
        self.ui.log(f"\n{payload}\n{'=' * 50}")
        for node in active_nodes:
            node.stack.append(payload)
            self.ui.log(f"[RELAY] Payload enqueued for {node.name}", is_system=True)

        if self.relay.start(payload, active_nodes):
            self.ui.log("[RELAY] Relay started.", is_system=True)
            threading.Thread(
                target=lambda: asyncio.run(self._do_relay()), daemon=True
            ).start()
        else:
            self.ui.log(
                f"[RELAY] Relay.start() returned False. State: {self.relay.state}",
                is_system=True
            )

    async def _do_relay(self):
        try:
            self._get_browser()
            self.relay.fill_complete()
            self.relay.submit_complete()
            self.ui.log(
                "[RELAY] Active nodes (SEND ORDER): "
                f"{[n.name for n in self.relay.active_nodes]}",
                is_system=True
            )

            for node in self.relay.active_nodes:
                self.ui.log(
                    f"[RELAY] Checking {node.name} | active={node.is_active()} | "
                    f"stack_len={len(node.stack)}",
                    is_system=True
                )
                if not node.is_active():
                    self.ui.log(f"[RELAY] {node.name} not active. Skipping.", is_system=True)
                    continue
                if not node.stack:
                    self.ui.log(f"[RELAY] {node.name} stack empty. Skipping.", is_system=True)
                    continue

                page = await self._find_page_for_node(node)
                if not page:
                    self.ui.log(f"[RELAY] {node.name} offline.", is_system=True)
                    continue

                payload_parts = []
                while node.stack:
                    payload_parts.append(node.stack.popleft())
                payload = "\n\n".join(payload_parts).strip()
                if not payload:
                    continue

                success = await self._send_message_to_page(
                    page, node, payload, is_handshake=False
                )
                if not success:
                    self.ui.log(f"[RELAY] Failed to send to {node.name}.", is_system=True)
                    continue
                self.ui.log(f"[RELAY] Sent to {node.name}...", is_system=True)

                responded = await self._wait_for_response(page, node, timeout=60)
                if responded:
                    raw = await self._get_response(page, node, is_handshake=False)
                    clean, dropped = self._parse_response(raw, is_handshake=False)
                    if dropped:
                        self.ui.log(f"[RELAY] {node.name} dropped out.", is_system=True)
                        node.toggle_off()
                        continue
                    if clean:
                        relay_msg = f"{node.icon} {node.name} - {clean}"
                        self.ui.log(f"\n{relay_msg}\n")
                        for target in self.relay.active_nodes:
                            if target != node and target.is_active():
                                target.stack.append(relay_msg)

            self.relay.relay_complete()
            self.ui.log("[RELAY] Cycle complete.", is_system=True)
        except Exception as exc:
            self.relay.error()
            self.ui.log(f"[RELAY] Error: {exc}", is_system=True)
        finally:
            self.relay.reset()
            self.ui.fanout_finished()

    def _safe_js_selector(self, selector):
        return json.dumps(selector)

    async def _send_message_to_page(self, page, node, text, is_handshake):
        step = "DISCOVER"
        try:
            step = "LOCATE INPUT"
            selector = node.input_selector
            if not selector:
                self.ui.log(f"[SEND] No input selector for {node.name}", is_system=True)
                return False
            input_element = await page.query_selector(selector)
            if not input_element or not await input_element.is_visible():
                self.ui.log(
                    f"[SEND] LOCATE INPUT failed for {node.name}: '{selector}' not visible.",
                    is_system=True
                )
                return False
            await input_element.focus()
            self.ui.log(f"[SEND] LOCATE INPUT: {node.name} using '{selector}'", is_system=True)
            step = "CLEAR INPUT"
            await self._clear_input_element(page, input_element, selector)
            self.ui.log(f"[SEND] CLEAR INPUT: {node.name}", is_system=True)
            step = "FILL INPUT"
            await input_element.fill(text)
            self.ui.log(f"[SEND] FILL INPUT: {node.name} ({len(text)} chars)", is_system=True)
            node.response_baseline = await self._capture_output_snapshot(page, node)
            self.ui.log(
                f"[WAIT] {node.name}: captured {len(node.response_baseline)} "
                f"pre-submit output messages.",
                is_system=True
            )
            step = "SUBMIT"
            submit_success = await self._submit(page, node, input_element, selector)
            if not submit_success:
                self.ui.log(f"[SEND] SUBMIT FAILED: {node.name}", is_system=True)
                return False
            self.ui.log(f"[SEND] SUBMIT CONFIRMED: {node.name}", is_system=True)
            return True
        except Exception as exc:
            self.ui.log(f"[SEND] {step} failed for {node.name}: {exc}", is_system=True)
            return False

    async def _clear_input_element(self, page, element, selector):
        try:
            safe_sel = self._safe_js_selector(selector)
            is_editable = await page.evaluate(f"""
                (() => {{
                    const el = document.querySelector({safe_sel});
                    return el ? el.getAttribute('contenteditable') === 'true' : false;
                }})()
            """)
            if is_editable:
                await page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector({safe_sel});
                        if (el) {{
                            el.innerHTML = '';
                            el.innerText = '';
                            el.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'deleteContentBackward'}}));
                        }}
                    }})()
                """)
            else:
                await element.fill("")
                await element.focus()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
        except Exception:
            pass

    async def _input_has_text(self, page, element, selector):
        try:
            return bool(await page.evaluate(
                f"""
                () => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    const value = typeof el.value === 'string' ? el.value : (el.innerText || el.textContent || '');
                    return Boolean((value || '').trim());
                }}
                """
            ))
        except Exception:
            try:
                value = await element.input_value()
                return bool((value or '').strip())
            except Exception:
                try:
                    value = await element.inner_text()
                    return bool((value or '').strip())
                except Exception:
                    return False

    async def _submit_verified(self, page, node, input_element, selector, method):
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < 3.0:
            await asyncio.sleep(0.25)
            try:
                still_has_text = await self._input_has_text(page, input_element, selector)
            except Exception:
                still_has_text = True
            busy = False
            try:
                busy = not await self._send_button_state(page)
            except Exception:
                busy = False
            current = await self._capture_output_snapshot(page, node)
            baseline = node.response_baseline or []
            new_output = len(current) > len(baseline) or (current[-1:] != baseline[-1:] if baseline else bool(current))
            if not still_has_text or new_output:
                self.ui.log(
                    f"[SEND] SUBMIT CONFIRMED ({method}): {node.name} | "
                    f"input_clear={not still_has_text} busy={busy} new_output={new_output}",
                    is_system=True
                )
                return True
            if busy:
                self.ui.log(
                    f"[SEND] SUBMIT PENDING ({method}): {node.name} | "
                    f"input_clear={not still_has_text} busy={busy} new_output={new_output}",
                    is_system=True
                )
        self.ui.log(
            f"[SEND] SUBMIT NOT CONFIRMED ({method}): {node.name} | composer remained populated or no state transition.",
            is_system=True
        )
        return False

    async def _submit(self, page, node, input_element, selector):
        send_selectors = [
            'button[aria-label*="Send"]', 'button[type="submit"]',
            '[data-testid="send-button"]'
        ]

        for send_selector in send_selectors:
            try:
                buttons = await page.query_selector_all(send_selector)
                for button in buttons:
                    if not await button.is_visible():
                        continue
                    if await button.is_disabled():
                        continue
                    aria = (await button.get_attribute("aria-label") or "").lower()
                    text = (await button.inner_text() or "").lower()
                    if "stop" in aria or "cancel" in aria or "stop" in text or "cancel" in text:
                        continue
                    self.ui.log(
                        f"[SEND] SUBMIT ATTEMPT (button): {node.name} using '{send_selector}'",
                        is_system=True
                    )
                    await button.click()
                    if await self._submit_verified(page, node, input_element, selector, "button"):
                        return True
            except Exception as exc:
                self.ui.log(
                    f"[SEND] button submit attempt failed for {node.name}: {exc}",
                    is_system=True
                )

        try:
            await input_element.focus()
        except Exception:
            pass
        try:
            self.ui.log(f"[SEND] SUBMIT ATTEMPT (Enter): {node.name}", is_system=True)
            await page.keyboard.press("Enter")
            if await self._submit_verified(page, node, input_element, selector, "Enter"):
                return True
        except Exception as exc:
            self.ui.log(f"[SEND] Enter submit attempt failed for {node.name}: {exc}", is_system=True)

        return False

    async def _send_button_state(self, page):
        result = await page.evaluate("""
            () => {
                const selectors = [
                    'button[aria-label*="Send"]', 'button[type="submit"]',
                    '[data-testid="send-button"]'
                ];
                let foundSend = false;
                for (const selector of selectors) {
                    let elements = [];
                    try { elements = document.querySelectorAll(selector); } catch (e) { continue; }
                    for (const el of elements) {
                        const style = window.getComputedStyle(el);
                        const visible = !!(
                            el.offsetWidth > 0 && el.offsetHeight > 0 &&
                            style.visibility !== "hidden" && style.display !== "none"
                        );
                        if (!visible) continue;
                        const disabled = !!(
                            el.disabled || el.getAttribute("aria-disabled") === "true"
                        );
                        const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                        const text = (el.innerText || el.textContent || "").toLowerCase();
                        const busy = aria.includes("stop") || aria.includes("cancel") ||
                                     aria.includes("generat") || text.includes("stop") || text.includes("cancel");
                        if (!disabled && !busy) { foundSend = true; break; }
                    }
                    if (foundSend) break;
                }
                return foundSend;
            }
        """)
        return bool(result)

    async def _capture_output_snapshot(self, page, node):
        selector = node.output_selector
        if not selector:
            return []
        try:
            return await page.evaluate(
                fr"""
                () => {{
                    const elements = [...document.querySelectorAll({json.dumps(selector)})];
                    const transientPatterns = [
                        /^thought for\s+\d+(?:\.\d+)?s?$/i,
                        /^ran a command$/i,
                        /^searching the web$/i,
                        /^used (?:a )?tool$/i,
                        /^thinking$/i,
                        /^loading(?:\.{0,3})$/i,
                        /^stop$/i,
                        /^cancel$/i
                    ];

                    const cleanText = (value) => {{
                        let lines = String(value || '')
                            .split(/\r?\n/)
                            .map(line => line.trim())
                            .filter(Boolean);
                        lines = lines.filter(line => !transientPatterns.some(re => re.test(line)));
                        return lines.join('\n').trim();
                    }};

                    const results = [];
                    const seen = new Set();
                    for (const el of elements) {{
                        const text = cleanText(el.innerText || el.textContent || '');
                        if (!text) continue;

                        let ancestorMatch = false;
                        for (const other of elements) {{
                            if (other === el) continue;
                            if (other.contains(el)) {{
                                const otherText = cleanText(other.innerText || other.textContent || '');
                                if (otherText === text && other !== el) {{
                                    ancestorMatch = true;
                                    break;
                                }}
                            }}
                        }}
                        if (ancestorMatch) continue;

                        if (!seen.has(text)) {{
                            seen.add(text);
                            results.push(text);
                        }}
                    }}
                    return results;
                }}
                """
            )
        except Exception:
            return []

    async def _response_frame_state(self, page, node):
        messages = await self._capture_output_snapshot(page, node)
        if not messages:
            return False

        baseline = node.response_baseline or []
        is_new = len(messages) > len(baseline)
        if not is_new and messages[-1:] != baseline[-1:]:
            is_new = True

        if not is_new:
            return False

        new_messages = messages[len(baseline):] if len(messages) > len(baseline) else []
        if not new_messages and messages[-1:] != baseline[-1:]:
            new_messages = messages[-1:]

        return any(text.strip() for text in new_messages)

    async def _wait_for_response(self, page, node, timeout=45, is_handshake=False):
        self.ui.log(
            f"[WAIT] {node.name}: waiting for generation to finish...",
            is_system=True
        )

        start_time = asyncio.get_event_loop().time()
        saw_busy = False
        saw_new_response = False
        stable_streak = 0
        last_response_text = None
        handshake_stable_streak = 0
        last_handshake_frame = None

        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(0.5)

            send_ready = await self._send_button_state(page)
            frame_ready = await self._response_frame_state(page, node)
            messages = await self._capture_output_snapshot(page, node)

            baseline = node.response_baseline or []
            candidates = messages[len(baseline):] if len(messages) > len(baseline) else []
            if not candidates and messages[-1:] != baseline[-1:]:
                candidates = messages[-1:]

            current_response_text = candidates[-1].strip() if candidates else None

            if frame_ready or current_response_text:
                if not saw_new_response:
                    self.ui.log(
                        f"[WAIT] {node.name}: new cleaned assistant output detected.",
                        is_system=True
                    )
                saw_new_response = True

            if not send_ready:
                if not saw_busy:
                    self.ui.log(f"[WAIT] {node.name}: node is busy.", is_system=True)
                saw_busy = True

            if is_handshake:
                handshake_frame = None
                if candidates:
                    for candidate in reversed(candidates):
                        matches = list(re.finditer(r'🟩.*?🔚', candidate, re.DOTALL))
                        if matches:
                            handshake_frame = matches[-1].group().strip()
                            break

                if handshake_frame:
                    if handshake_frame == last_handshake_frame:
                        handshake_stable_streak += 1
                    else:
                        handshake_stable_streak = 1
                        last_handshake_frame = handshake_frame

                    if handshake_stable_streak >= 4:
                        self.ui.log(
                            f"[WAIT] {node.name}: complete NEW handshake response detected by output stability.",
                            is_system=True
                        )
                        return True
                else:
                    handshake_stable_streak = 0
                    last_handshake_frame = None
                continue

            if saw_busy and saw_new_response and current_response_text:
                if current_response_text == last_response_text:
                    stable_streak += 1
                else:
                    stable_streak = 1
                    last_response_text = current_response_text

                if stable_streak >= 4:
                    self.ui.log(
                        f"[WAIT] {node.name}: response finalized by output stability.",
                        is_system=True
                    )
                    return True
            elif current_response_text is None:
                stable_streak = 0
                last_response_text = None

        self.ui.log(f"[WAIT] {node.name}: response timeout.", is_system=True)
        return False

    async def _get_response(self, page, node, is_handshake=False):
        messages = await self._capture_output_snapshot(page, node)
        if not messages:
            return "No response text extracted from DOM."

        baseline = node.response_baseline or []
        candidates = messages[len(baseline):] if len(messages) > len(baseline) else []
        if not candidates and messages[-1:] != baseline[-1:]:
            candidates = messages[-1:]

        if is_handshake:
            for candidate in reversed(candidates):
                matches = list(re.finditer(r'🟩.*?🔚', candidate, re.DOTALL))
                if matches:
                    frame_content = matches[-1].group()[1:-1].strip()
                    if frame_content:
                        return frame_content

        return candidates[-1].strip() if candidates else ""

    def _parse_response(self, text, is_handshake=False):
        trimmed = text.strip()
        if not is_handshake:
            return trimmed, False

        matches = list(re.finditer(r'🟩.*?🔚', trimmed, re.DOTALL))
        if matches:
            match = matches[-1]
            frame = match.group()
            start = frame.find("🟩")
            end = frame.find("🔚", start)
            if end != -1:
                dropped = "🛑" in trimmed[end + 1:]
                return trimmed[start + 1:end].strip(), dropped
        return trimmed, False

    def _on_node_change(self, node, old, new):
        self.ui.log(f"[STATE] {node.name}: {old} -> {new}", is_system=True)

    def _on_relay_change(self, relay):
        self.ui.relay_state_changed(relay.state)
        if relay.state == RelayState.COMPLETE:
            self.ui.log("[RELAY] Complete.", is_system=True)


if __name__ == "__main__":
    logger.info("Launching QuackSink QS %s.", VERSION)
    try:
        controller = QSController()
        controller.ui.run()
    except Exception as exc:
        logger.error("Fatal QS 4.0 startup error: %s", exc)
        print(f"FATAL QS 4.0 ERROR: {exc}")
        input("Press ENTER to exit...")
