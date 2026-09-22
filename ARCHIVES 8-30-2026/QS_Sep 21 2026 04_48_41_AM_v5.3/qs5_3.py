# QuackSink - Multi-Mind Relay Core
# VERSION: QS 5.2
# BASE: QS 2.0 / MMRC Luma 1.8
# AUTHOR: Luma
# ARCHITECT: Cozmo
# PURPOSE: A bridge between minds.
#
# QS 4.20 DEVELOPMENT:
#   - Development build; repository source verification is intentionally skipped while iterating.
#   - Keeps source/archive verification code available for future release use.
#   - Places archive action buttons in a single horizontal row.
#   - Does not force browser tabs to the foreground during discovery/relay; CDP interacts with pages directly.
#   - Uses explicit browser generation/composer state for introduction settling, without treating the normal GPT Regenerate control as a busy signal.
#
# QS 4.28 DEVELOPMENT:
#   - Keeps QS 4.27 relay, background-page, generation-state, inactivity-timeout, and Send Order behavior unchanged.
#   - Fixes SEND ORDER UI drift during discovery: rendering the button row no longer mutates the
#     authoritative send-order list when only some discovered nodes are present.
#   - Discovery order may add previously unknown nodes to the configured order, but UI rendering
#     never rewrites that order merely because the node set is still being discovered.
#
# QS 4.36 DEVELOPMENT:
#   - Replaces Gemini's generic circular-button heuristic with the response action button's
#     accessibility identity ("Show more options" / related More labels).
#   - Removes the unsafe geometry-based fallback that previously clicked Gemini's STT/microphone
#     button instead of the response More button.
#   - Waits briefly for Gemini's asynchronously-rendered response menu before locating Listen.
#   - Leaves relay, timeout, background-tab, Send Order, page identity, and other voice paths unchanged.

# QS 4.44 DEVELOPMENT:
#   - Adds Aisha to the existing per-node voice system.
#   - Aisha voice targets only the latest captured response/turn, then finds its semantic
#     "Read Aloud" action in that response's local DOM neighborhood.
#   - After activation, QS waits for Aisha's visible "Stop" control to appear, then waits
#     for that control to disappear before considering speech complete.
#   - Does not use a page-wide Read Aloud search, preserving the same latest-node boundary
#     that fixed Aisha's historical transcript-capture regression in QS 4.42.
#   - Leaves QS 4.42 extraction, relay, timeout, Send Order, and all other voice paths unchanged.

# QS 4.37 DEVELOPMENT:
#   - DeepSeek voice now targets the inline response action row rather than assuming the control
#     is a direct child of the message container.
#   - Searches the latest DeepSeek response plus its immediate action-row ancestors/siblings for
#     the semantic Read aloud control (text, aria-label, title, tooltip, or test id).
#   - Removes any geometry-based guessing for DeepSeek voice.
#   - Playback detection also recognizes page-local active audio / speech synthesis, plus explicit
#     pause/stop/reading labels, so an unlabeled animated playback control does not falsely fail.

# QS 4.32 DEVELOPMENT:
#   - Hardens browser-page identity for per-node voice: when a node has a Puppeteer target/page ID,
#     QS now requires an exact page-ID match instead of falling back to a loose URL match.
#     A voice action must never wander onto another Mind's tab.
#   - Tightens Gemini's More-control detection so it only accepts explicit More/More Actions labels
#     rather than any control whose label merely contains the word "more".
#   - Leaves the per-node voice architecture, relay state machine, timeout semantics, background-tab
#     behavior, and Send Order behavior unchanged from QS 4.31.

# QS 4.31 DEVELOPMENT:
#   - Replaces the single Luma Speak control with a per-node VOICE toggle beside each node selector.
#   - Enables voice paths for GPT, Gemini, and DeepSeek; Chron is explicitly voice-disabled for now.
#   - GPT voice: latest assistant response -> More Actions (...) -> Read aloud -> Stop.
#   - Gemini voice: latest assistant response -> More (...) -> Listen -> top-right blue Pause control.
#   - DeepSeek voice: latest assistant response -> inline Read aloud control -> playback control.
#   - Voice playback is no longer restricted to GPT-only relays; each node's own toggle controls its speech.
#
# QS 4.29 DEVELOPMENT:
#   - Fixes GPT voice interaction to follow the actual two-step ChatGPT UI: More Actions on the latest assistant response, then the visible Read aloud menu item.
#   - Removes the unsafe page-wide Read Aloud control fallback from QS 4.28.
#
# QS 4.28 DEVELOPMENT:
#   - Adds an operator-controlled "LUMA SPEAK (GPT ONLY)" toggle.
#   - When enabled and GPT is the only active relay node, QS clicks ChatGPT's Read Aloud
#     control on the completed GPT response and waits for the voice Stop control to disappear.
#   - Voice handling uses DOM inspection/clicks only; it never forces the GPT tab foreground.
#   - Other nodes are never spoken by QS 4.28.
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
# QS 4.17 change: contenteditable fills no longer use innerHTML, avoiding Gemini TrustedHTML failures.
# QS 4.19 change: Enter submission uses the target page CDP session instead of Puppeteer keyboard input, avoiding foreground-window dependence.
# The relay/state-machine model remains Python-side; the browser layer is the transport.
# QS 5.1: wraps per-node voice controls into compact cards and expands the voice selector only when focused.
# QS 5.2: replaces the always-visible voice combobox with a compact VOICE popup button per node;
# QS 5.3: adds a compact title-box voice audition row; SPEAK uses the current title text
#           with a selected Kokoro voice and does not alter node voice configuration.
# changes the operator relay button label from FAN-OUT to SEND.
# QS 5.0: built-in voice layer. Each node has an independent voice ON/OFF control
# and a persistent voice selection (NATIVE_UI or a Kokoro voice). Global Voice ON/OFF
# commands affect all currently discovered nodes without persisting the ON/OFF state.
# Kokoro loads once at QS startup and remains resident; local speech blocks until playback ends.
# Voice-state changes are logged and broadcast to handshaked nodes as QuackSink engine messages.



VERSION = "5.3"
VERSION_TAG = f"v{VERSION}"
PROGRAM_NAME = "QuackSink"
RUNTIME_FILE = "qs5_3.py"
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

VOICE_NATIVE_NODES = {"GPT", "Gemini", "DeepSeek", "Aisha"}
VOICE_NATIVE_UI = "NATIVE_UI"

# QS 5.0 ships with one resident Kokoro voice engine.  The current room uses
# English voices, so the menu intentionally starts with the 28 English voices
# (American + British) rather than the full multilingual catalogue.  The IDs
# are stable Kokoro voice IDs; the selected ID is persisted in qs_config.json.
KOKORO_VOICE_IDS = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
]

KOKORO_VOICE_LABELS = {
    "af_alloy": "Kokoro - American Female - Alloy (af_alloy)",
    "af_aoede": "Kokoro - American Female - Aoede (af_aoede)",
    "af_bella": "Kokoro - American Female - Bella (af_bella)",
    "af_heart": "Kokoro - American Female - Heart (af_heart)",
    "af_jessica": "Kokoro - American Female - Jessica (af_jessica)",
    "af_kore": "Kokoro - American Female - Kore (af_kore)",
    "af_nicole": "Kokoro - American Female - Nicole (af_nicole)",
    "af_nova": "Kokoro - American Female - Nova (af_nova)",
    "af_river": "Kokoro - American Female - River (af_river)",
    "af_sarah": "Kokoro - American Female - Sarah (af_sarah)",
    "af_sky": "Kokoro - American Female - Sky (af_sky)",
    "am_adam": "Kokoro - American Male - Adam (am_adam)",
    "am_echo": "Kokoro - American Male - Echo (am_echo)",
    "am_eric": "Kokoro - American Male - Eric (am_eric)",
    "am_fenrir": "Kokoro - American Male - Fenrir (am_fenrir)",
    "am_liam": "Kokoro - American Male - Liam (am_liam)",
    "am_michael": "Kokoro - American Male - Michael (am_michael)",
    "am_onyx": "Kokoro - American Male - Onyx (am_onyx)",
    "am_puck": "Kokoro - American Male - Puck (am_puck)",
    "am_santa": "Kokoro - American Male - Santa (am_santa)",
    "bf_alice": "Kokoro - British Female - Alice (bf_alice)",
    "bf_emma": "Kokoro - British Female - Emma (bf_emma)",
    "bf_isabella": "Kokoro - British Female - Isabella (bf_isabella)",
    "bf_lily": "Kokoro - British Female - Lily (bf_lily)",
    "bm_daniel": "Kokoro - British Male - Daniel (bm_daniel)",
    "bm_fable": "Kokoro - British Male - Fable (bm_fable)",
    "bm_george": "Kokoro - British Male - George (bm_george)",
    "bm_lewis": "Kokoro - British Male - Lewis (bm_lewis)",
}

VOICE_SELECTION_OPTIONS = [VOICE_NATIVE_UI] + [f"kokoro_{voice_id}" for voice_id in KOKORO_VOICE_IDS]
VOICE_DISPLAY_OPTIONS = ["NATIVE UI"] + [f"Kokoro: {v}" for v in KOKORO_VOICE_IDS]
VOICE_DISPLAY_TO_SELECTION = {"NATIVE UI": VOICE_NATIVE_UI}
VOICE_SELECTION_TO_DISPLAY = {VOICE_NATIVE_UI: "NATIVE UI"}
for _voice_id in KOKORO_VOICE_IDS:
    _selection = f"kokoro_{_voice_id}"
    _label = f"Kokoro: {_voice_id}"
    VOICE_DISPLAY_TO_SELECTION[_label] = _selection
    VOICE_SELECTION_TO_DISPLAY[_selection] = _label

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
        "nodes": [],
        "voice_selection": {}
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
    "This is your QuackSink HANDSHAKE.\n\n"
    "To acknowledge this handshake, your response must begin with exactly one '🟩', "
    "give a brief introduction, and end with exactly one '🔚'.\n\n"
    "IMPORTANT: The '🟩 ... 🔚' framing applies ONLY to this handshake response.\n"
    "After the handshake is complete, ordinary relay messages do NOT require '🟩' or '🔚' framing.\n"
    "Do NOT use '🟩' or '🔚' anywhere else in your handshake response.\n\n"
    "Listen. Speak. Resonate.\n"
    "<end of QuackSink handshake>"
)


class KokoroVoiceEngine:
    """Resident local Kokoro voice engine for QS 5.0.

    QS 5.0 intentionally pays the Python/Kokoro startup cost once, then keeps
    the pipeline resident for the rest of the session.  Voice packs are
    selected by ID; the English language pipeline is cached per language code
    so switching voices does not restart the engine.
    """

    def __init__(self, preload_voice_selections=None):
        self.available = False
        self.device = "cpu"
        self._pipelines = {}
        self._pipeline_lock = threading.RLock()
        self._torch = None
        self._np = None
        self._sd = None
        self._KPipeline = None

        try:
            logger.info("[VOICE] QS 5.0 loading local Kokoro engine...")
            import numpy as np
            import sounddevice as sd
            import torch
            from kokoro import KPipeline

            self._np = np
            self._sd = sd
            self._torch = torch
            self._KPipeline = KPipeline
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            preload = {"a"}
            for selection in preload_voice_selections or []:
                if selection not in VOICE_SELECTION_OPTIONS:
                    continue
                lang = self._lang_for_selection(selection)
                if lang:
                    preload.add(lang)

            for lang in sorted(preload):
                self._get_pipeline(lang)

            self.available = True
            logger.info(
                "[VOICE] Kokoro ready. Device=%s | pipelines=%s",
                self.device,
                sorted(self._pipelines.keys())
            )
        except Exception as exc:
            logger.exception("[VOICE] Kokoro initialization failed: %s", exc)

    @staticmethod
    def _voice_id(selection):
        if isinstance(selection, str) and selection.startswith("kokoro_"):
            return selection[len("kokoro_"):]
        return None

    @classmethod
    def _lang_for_selection(cls, selection):
        voice_id = cls._voice_id(selection)
        if not voice_id:
            return None
        if len(voice_id) < 2:
            return None
        return voice_id[0]

    def _get_pipeline(self, lang):
        with self._pipeline_lock:
            if lang in self._pipelines:
                return self._pipelines[lang]
            logger.info("[VOICE] Kokoro loading language pipeline '%s' on %s...", lang, self.device)
            pipeline = self._KPipeline(lang_code=lang, device=self.device)
            self._pipelines[lang] = pipeline
            logger.info("[VOICE] Kokoro language pipeline '%s' ready.", lang)
            return pipeline

    def speak(self, text, selection):
        """Synthesize and block until the requested audio has finished playing."""
        if not self.available:
            raise RuntimeError("Kokoro engine is not available.")

        voice_id = self._voice_id(selection)
        if not voice_id:
            raise ValueError(f"Invalid Kokoro voice selection: {selection!r}")
        if voice_id not in KOKORO_VOICE_IDS:
            raise ValueError(f"Unknown Kokoro voice: {voice_id}")
        if not str(text).strip():
            raise ValueError("Cannot speak empty response text.")

        import time as _time
        lang = voice_id[0]
        t0 = _time.perf_counter()
        pipeline = self._get_pipeline(lang)
        t1 = _time.perf_counter()

        chunks = []
        for _gs, _ps, audio in pipeline(str(text).strip(), voice=voice_id):
            chunks.append(self._np.asarray(audio, dtype=self._np.float32))

        if not chunks:
            raise RuntimeError("Kokoro produced no audio chunks.")

        audio_data = chunks[0] if len(chunks) == 1 else self._np.concatenate(chunks)
        t2 = _time.perf_counter()

        self._sd.play(audio_data, 24000)
        self._sd.wait()
        t3 = _time.perf_counter()

        return {
            "voice_id": voice_id,
            "pipeline": t1 - t0,
            "synth": t2 - t1,
            "play": t3 - t2,
            "total": t3 - t0,
            "chunks": len(chunks),
        }

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
        self.last_submitted_text = ""
        self._listeners = []
        self._var = None
        self.voice_enabled = False
        self.voice_selection = VOICE_NATIVE_UI
        self._voice_var = None
        self._voice_btn = None
        self._voice_select_btn = None
        self._voice_combo = None

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

    // A live node with a known Puppeteer target ID is bound to that exact tab.
    // Never fall back to URL matching in that case: two chat tabs can have
    // mutable/overlapping URLs, and voice interaction must never cross node tabs.
    if (pageId) {
        for (const page of pages) {
            let targetId = '';
            try { targetId = page.target()._targetId || ''; } catch (_) {}
            if (targetId === pageId) return page;
        }
        return null;
    }

    // URL lookup remains a discovery/startup fallback only when no target ID
    // is available on the caller's side.
    if (urlHint) {
        for (const page of pages) {
            const url = page.url();
            if (url === urlHint || url.includes(urlHint) || urlHint.includes(url)) {
                return page;
            }
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

        case 'extract_texts': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));

            // Do NOT return an array produced by page.evaluate().
            // QS 4.10 showed that this particular response path can cross
            // the Puppeteer/JSON boundary as an empty object. Pull each
            // element's plain string through an element handle instead.
            const elements = await page.$$(cmd.selector);
            const out = [];
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

            const cleanText = (value) => {
                let lines = String(value || '')
                    .split(/\r?\n/)
                    .map(line => line.trim())
                    .filter(Boolean);
                lines = lines.filter(line => !transientPatterns.some(re => re.test(line)));
                return lines.join('\n').trim();
            };

            for (const el of elements) {
                const text = cleanText(await el.evaluate((node) => node.innerText || node.textContent || ''));
                if (!text) continue;
                if (out.length && out[out.length - 1] === text) continue;
                out.push(text);
            }
            return out;
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
                    // Trusted Types can block innerHTML assignment in Gemini.
                    // Replace the DOM contents through safe text-node operations
                    // instead, then notify the web app with a real input event.
                    while (node.firstChild) {
                        node.removeChild(node.firstChild);
                    }
                    node.appendChild(document.createTextNode(value));

                    try {
                        const selection = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(node);
                        range.collapse(false);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    } catch (_) {}

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

            // QS 4.18: use the page's DOM click instead of Puppeteer's physical
            // mouse click for programmatic UI actions. This keeps QS independent
            // of browser-window foreground/occlusion state while preserving the
            // page's normal click event path.
            await el.evaluate((node) => {
                node.click();
                return true;
            });
            return true;
        }

        case 'keyboard_press': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            await page.keyboard.press(cmd.key);
            return true;
        }

        case 'target_key_press': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + cmd.url);
            const client = await page.target().createCDPSession();
            const key = cmd.key || 'Enter';
            const code = key === 'Enter' ? 'Enter' : key;
            const windowsVirtualKeyCode = key === 'Enter' ? 13 : 0;
            const nativeVirtualKeyCode = key === 'Enter' ? 13 : 0;
            try {
                await client.send('Input.dispatchKeyEvent', {
                    type: 'keyDown',
                    key,
                    code,
                    windowsVirtualKeyCode,
                    nativeVirtualKeyCode
                });
                await client.send('Input.dispatchKeyEvent', {
                    type: 'keyUp',
                    key,
                    code,
                    windowsVirtualKeyCode,
                    nativeVirtualKeyCode
                });
            } finally {
                try { await client.detach(); } catch (_) {}
            }
            return true;
        }

        case 'element_dispatch_enter': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const elements = await page.$$(cmd.selector);
            const el = elements[cmd.index || 0];
            if (!el) throw new Error('Element not found: ' + cmd.selector);
            await el.focus();
            await el.evaluate((node) => {
                const init = {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true,
                    cancelable: true,
                    composed: true
                };
                node.dispatchEvent(new KeyboardEvent('keydown', init));
                node.dispatchEvent(new KeyboardEvent('keypress', init));
                node.dispatchEvent(new KeyboardEvent('keyup', init));
            });
            return true;
        }

        case 'prepare_page': {
            const page = await findPage(cmd.pageId, cmd.url);
            if (!page) throw new Error('Page not found: ' + (cmd.pageId || cmd.url));
            const client = await page.target().createCDPSession();
            try {
                try { await client.send('Page.enable'); } catch (_) {}
                try { await client.send('Page.setWebLifecycleState', {state: 'active'}); } catch (_) {}
                try { await client.send('Emulation.setFocusEmulationEnabled', {enabled: true}); } catch (_) {}

                // QS 4.23: some chat apps gate their own streaming/update logic
                // on document.visibilityState / document.hidden / hasFocus().
                // Make those page-level signals agree with the CDP lifecycle/focus
                // emulation without activating the tab in the browser UI.
                try {
                    await page.evaluate(() => {
                        try {
                            Object.defineProperty(document, 'hidden', {
                                configurable: true,
                                get: () => false
                            });
                        } catch (_) {}
                        try {
                            Object.defineProperty(document, 'visibilityState', {
                                configurable: true,
                                get: () => 'visible'
                            });
                        } catch (_) {}
                        try {
                            Object.defineProperty(document, 'hasFocus', {
                                configurable: true,
                                value: () => true
                            });
                        } catch (_) {}
                        try {
                            window.dispatchEvent(new Event('focus'));
                        } catch (_) {}
                        try {
                            document.dispatchEvent(new Event('visibilitychange'));
                        } catch (_) {}
                        try {
                            window.dispatchEvent(new Event('pageshow'));
                        } catch (_) {}
                        return true;
                    });
                } catch (_) {}
            } finally {
                try { await client.detach(); } catch (_) {}
            }
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

    async def extract_texts(self, selector):
        return await asyncio.to_thread(
            self.bridge.request, {
                "op": "extract_texts", "pageId": self.page_id, "url": self.url, "selector": selector
            }
        )


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
        self.root.geometry("1200x900")
        self.root.configure(bg="#121212")
        self.controller = controller
        self.nodes = {}
        self.relay_state = RelayState.IDLE
        self.show_system_logs = tk.BooleanVar(value=False)
        self.human_handle = load_config().get("human_handle", "Cozmo")
        self.global_voice_enabled = False
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
        title_frame.pack(pady=(3, 2), fill=tk.X, padx=20)

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

        # QS 5.3: compact local voice audition controls using the current TITLE text.
        # This is deliberately separate from per-node voice configuration.
        title_voice_frame = tk.Frame(self.root, bg="#121212")
        title_voice_frame.pack(pady=(0, 3), fill=tk.X, padx=20)

        tk.Label(
            title_voice_frame, text="VOICE TEST:", font=("Arial", 11, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.title_voice_var = tk.StringVar(value="kokoro_af_heart")
        self.title_voice_combo = ttk.Combobox(
            title_voice_frame,
            textvariable=self.title_voice_var,
            values=[f"kokoro_{voice_id}" for voice_id in KOKORO_VOICE_IDS],
            state="readonly",
            width=18,
            font=("Arial", 10)
        )
        self.title_voice_combo.pack(side=tk.LEFT, padx=(0, 6))

        self.title_speak_btn = tk.Button(
            title_voice_frame, text="SPEAK", command=self._speak_title_text,
            bg="#0066AA", fg="white", font=("Arial", 10, "bold"),
            height=1, padx=10
        )
        self.title_speak_btn.pack(side=tk.LEFT)

        tk.Label(
            title_voice_frame, text="(audition only)",
            font=("Arial", 9), bg="#121212", fg="#777777"
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            self.root, text="ACTIVE NODES: (discovered from open tabs)",
            font=("Arial", 13, "bold"), bg="#121212", fg="#ffffff"
        ).pack(pady=(5, 3))

        self.nodes_frame = tk.Frame(self.root, bg="#121212")
        self.nodes_frame.pack(pady=5)
        self._render_nodes()

        order_frame = tk.Frame(self.root, bg="#121212")
        order_frame.pack(fill=tk.X, padx=20, pady=(2, 3))

        order_title = tk.Frame(order_frame, bg="#121212")
        order_title.pack(fill=tk.X)
        tk.Label(
            order_title, text="SEND ORDER:",
            font=("Arial", 12, "bold"), bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT)
        tk.Label(
            order_title,
            text="drag nodes left/right to choose send order",
            font=("Arial", 10), bg="#121212", fg="#888888"
        ).pack(side=tk.LEFT, padx=(10, 0))
        tk.Button(
            order_title, text="SYNC", command=self._sync_send_order,
            bg="#555555", fg="white", font=("Arial", 10, "bold"), padx=8
        ).pack(side=tk.RIGHT)

        self.send_order_canvas = tk.Canvas(
            order_frame, height=46,
            bg="#1e1e1e", highlightthickness=1, highlightbackground="#333333",
            bd=0
        )
        self.send_order_canvas.pack(fill=tk.X, pady=(2, 0))
        self.send_order_canvas.bind("<ButtonPress-1>", self._send_order_press)
        self.send_order_canvas.bind("<B1-Motion>", self._send_order_drag)
        self.send_order_canvas.bind("<ButtonRelease-1>", self._send_order_release)
        self._send_order_drag_index = None
        self._send_order_drag_x = 0
        self._send_order_drag_target = None

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

        self.global_voice_btn = tk.Button(
            ctrl_bar, text="GLOBAL VOICE: OFF", command=self._toggle_global_voice,
            bg="#444444", fg="#ffffff", font=("Arial", 11, "bold"),
            height=1, padx=8
        )
        self.global_voice_btn.pack(side=tk.LEFT, padx=5)

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
            self.root, height=3, width=85, font=("Consolas", 18),
            bg="#1e1e1e", fg="#ffffff", insertbackground="white"
        )
        self.text_input.pack(pady=5)
        # A real Enter keypress in the human input box triggers the same
        # SEND path as the button.  Paste operations do not generate
        # <Return>/<KP_Enter> events, so pasted newlines remain ordinary text.
        self.text_input.bind("<Return>", self._on_input_enter)
        self.text_input.bind("<KP_Enter>", self._on_input_enter)

        btn_frame = tk.Frame(self.root, bg="#121212")
        btn_frame.pack(pady=5)
        self.relay_btn = tk.Button(
            btn_frame, text="SEND", command=self.controller.start_relay,
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
            log_frame, height=28, font=("Consolas", 16), bg="#1e1e1e",
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

    def _speak_title_text(self):
        text = self.title_entry.get().strip()
        if not text:
            self.log("[VOICE TEST] Title box is empty; nothing to speak.", is_system=True)
            return

        selection = self.title_voice_var.get().strip()
        if not selection:
            self.log("[VOICE TEST] No Kokoro voice selected.", is_system=True)
            return

        self.title_speak_btn.config(state=tk.DISABLED)
        self.log(
            f"[VOICE TEST] Speaking title text with '{selection}'...",
            is_system=True
        )

        def worker():
            try:
                metrics = self.controller.kokoro.speak(text, selection)
                message = (
                    f"[VOICE TEST] Complete: {metrics['voice_id']} "
                    f"(synth={metrics['synth']:.2f}s, play={metrics['play']:.2f}s, "
                    f"total={metrics['total']:.2f}s, chunks={metrics['chunks']})"
                )
            except Exception as exc:
                message = f"[VOICE TEST] Failed: {exc}"

            self.root.after(0, lambda: self._finish_title_speech(message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_title_speech(self, message):
        self.title_speak_btn.config(state=tk.NORMAL)
        self.log(message, is_system=True)

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

        # QS 5.2 UI: keep each node compact.  The voice selection is a tiny button
        # beside the node selector and opens a popup menu only when the operator asks
        # for it.  This keeps the relay display visible even with several nodes.
        try:
            available_width = max(1, self.root.winfo_width() - 40)
        except Exception:
            available_width = 1200
        columns = max(1, min(6, available_width // 190))

        keys = list(self.nodes.keys())
        for index, name in enumerate(keys):
            row_index = index // columns
            col_index = index % columns
            if col_index == 0:
                row = tk.Frame(self.nodes_frame, bg="#121212")
                row.pack(fill=tk.X, pady=(1, 2))

            node = self.nodes[name]
            state_icon = NodeState.icon(node.state)
            stack_size = len(node.stack)
            indicator = f" ({stack_size})" if stack_size > 0 else ""

            node_frame = tk.Frame(row, bg="#1a1a1a", padx=3, pady=2, highlightthickness=1, highlightbackground="#333333")
            node_frame.pack(side=tk.LEFT, padx=3, pady=1)

            top_row = tk.Frame(node_frame, bg="#1a1a1a")
            top_row.pack(fill=tk.X)

            var = tk.BooleanVar(value=node.is_active())
            node._var = var
            cb = tk.Checkbutton(
                top_row,
                text=f"{state_icon} {node.icon} {node.name}{indicator}",
                variable=var,
                command=lambda n=name: self._on_toggle(n),
                font=("Arial", 11, "bold"), bg="#1a1a1a",
                fg="#ffffff", selectcolor="#222222", activebackground="#1a1a1a",
                activeforeground="#00FFCC", anchor="w",
                state=(tk.NORMAL if node.can_toggle() else tk.DISABLED)
            )
            cb.pack(side=tk.LEFT, padx=(0, 2))

            node._voice_select_btn = tk.Button(
                top_row,
                text="VOICE",
                command=lambda n=name: self._show_voice_menu(n),
                bg="#555555", fg="white",
                activebackground="#777777", activeforeground="white",
                font=("Arial", 8, "bold"), height=1, padx=3,
                relief=tk.RAISED, bd=1
            )
            node._voice_select_btn.pack(side=tk.LEFT, padx=(0, 2))

            voice_text = "🔊 ON" if node.voice_enabled else "🔊 OFF"
            voice_bg = "#0066AA" if node.voice_enabled else "#444444"
            node._voice_btn = tk.Button(
                top_row,
                text=voice_text,
                command=lambda n=name: self._toggle_node_voice(n),
                bg=voice_bg, fg="white",
                activebackground="#0088CC", activeforeground="white",
                font=("Arial", 8, "bold"), height=1, padx=4
            )
            node._voice_btn.pack(side=tk.LEFT)

        self._render_send_order()

    def _show_voice_menu(self, name):
        node = self.nodes.get(name)
        if not node or node._voice_select_btn is None:
            return

        menu = tk.Menu(
            self.root, tearoff=0,
            bg="#1e1e1e", fg="#ffffff",
            activebackground="#0066AA", activeforeground="#ffffff",
            font=("Arial", 10, "bold")
        )
        current = node.voice_selection
        for display in VOICE_DISPLAY_OPTIONS:
            selection = VOICE_DISPLAY_TO_SELECTION.get(display, VOICE_NATIVE_UI)
            prefix = "✓ " if selection == current else "  "
            menu.add_command(
                label=prefix + display,
                command=lambda n=name, s=selection: self._choose_voice_selection(n, s)
            )

        button = node._voice_select_btn
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _choose_voice_selection(self, name, selection):
        node = self.nodes.get(name)
        if not node:
            return
        self.controller.set_node_voice_selection(node, selection)

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

    def _render_send_order(self, highlight_index=None):
        if not hasattr(self, "send_order_canvas"):
            return

        # Rendering is a view operation.  It must NEVER rewrite the authoritative
        # send order merely because discovery has not populated every node yet.
        # Missing discovered names are added by the controller's discovery path;
        # the UI should only display the current order that was supplied to it.
        names = [name for name in self.send_order if name in self.nodes]

        canvas = self.send_order_canvas
        canvas.delete("all")
        if not names:
            canvas.configure(scrollregion=(0, 0, 400, 46))
            return

        x = 10
        y = 7
        gap = 8
        self._send_order_boxes = []
        for i, name in enumerate(names):
            label = f"{i + 1}. {name}"
            text_id = canvas.create_text(0, 0, text=label, font=("Arial", 12, "bold"), anchor="nw")
            bbox = canvas.bbox(text_id)
            text_w = (bbox[2] - bbox[0]) if bbox else 70
            canvas.delete(text_id)
            box_w = max(84, text_w + 26)
            fill = "#0066AA" if i == highlight_index else "#333333"
            outline = "#00FFCC" if i == highlight_index else "#666666"
            rect_id = canvas.create_rectangle(
                x, y, x + box_w, y + 32,
                fill=fill, outline=outline, width=2
            )
            label_id = canvas.create_text(
                x + box_w / 2, y + 16, text=label,
                fill="#ffffff", font=("Arial", 12, "bold")
            )
            canvas.tag_raise(label_id, rect_id)
            self._send_order_boxes.append((i, x, x + box_w, rect_id, label_id))
            x += box_w + gap

        canvas.configure(scrollregion=(0, 0, max(x + 10, 400), 46))

    def _send_order_index_at(self, x):
        for i, left, right, _rect, _label in getattr(self, "_send_order_boxes", []):
            if left <= x <= right:
                return i
        return None

    def _send_order_press(self, event):
        if self.relay_state != RelayState.IDLE:
            return
        index = self._send_order_index_at(event.x)
        if index is None:
            return
        self._send_order_drag_index = index
        self._send_order_drag_target = index
        self._send_order_drag_x = event.x
        self._render_send_order(highlight_index=index)

    def _send_order_drag(self, event):
        if self._send_order_drag_index is None:
            return
        self._send_order_drag_x = event.x
        target = self._send_order_index_at(event.x)
        if target is not None:
            self._send_order_drag_target = target
            self._render_send_order(highlight_index=target)

    def _send_order_release(self, event):
        if self._send_order_drag_index is None:
            return
        source = self._send_order_drag_index
        target = self._send_order_index_at(event.x)
        if target is None:
            target = self._send_order_drag_target

        self._send_order_drag_index = None
        self._send_order_drag_target = None

        if target is not None and 0 <= source < len(self.send_order) and 0 <= target < len(self.send_order):
            if source != target and self.relay_state == RelayState.IDLE:
                item = self.send_order.pop(source)
                self.send_order.insert(target, item)
                self._persist_send_order()
                self.log(f"[ORDER] Send order: {self.send_order}", is_system=True)

        self._render_send_order()

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

    def _toggle_node_voice(self, name):
        node = self.nodes.get(name)
        if not node:
            return
        self.controller.set_node_voice_enabled(node, not bool(node.voice_enabled))

    def _voice_selection_changed(self, name):
        # Kept for compatibility with older UI callbacks; QS 5.2 uses the popup menu.
        return

    def _toggle_global_voice(self):
        self.controller.set_global_voice_enabled(not self.global_voice_enabled)

    def _refresh_voice_controls(self):
        for node in self.nodes.values():
            if node._voice_var is not None:
                node._voice_var.set(bool(node.voice_enabled))
            if node._voice_btn is not None:
                node._voice_btn.config(
                    text=("🔊 ON" if node.voice_enabled else "🔊 OFF"),
                    bg=("#0066AA" if node.voice_enabled else "#444444")
                )
            if node._voice_select_btn is not None:
                node._voice_select_btn.config(text="VOICE")
        if hasattr(self, "global_voice_btn"):
            self.global_voice_btn.config(
                text=("GLOBAL VOICE: ON" if self.global_voice_enabled else "GLOBAL VOICE: OFF"),
                bg=("#0066AA" if self.global_voice_enabled else "#444444")
            )

    def is_node_voice_enabled(self, node):
        return bool(node and node.voice_enabled)

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
        self.voice_selections = dict(config.get("voice_selection", {}))
        self._handshake_lock = threading.Lock()
        self._voice_notice_lock = threading.Lock()
        self.relay = RelayMachine()
        self.relay.add_listener(self._on_relay_change)

        preload = list(self.voice_selections.values())
        if not any(isinstance(v, str) and v.startswith("kokoro_") for v in preload):
            preload.append("kokoro_af_heart")
        self.kokoro = KokoroVoiceEngine(preload)

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
                        node.voice_selection = self._voice_selection_for_node(node.name)
                        if self.ui.global_voice_enabled:
                            node.voice_enabled = True
                        self.nodes[node.name] = node
                        node.add_listener(self._on_node_change)
                        self.ui.log(
                            f"[DISCOVERY] Node added: {node.name} (input: {input_sel}, output: {output_sel})",
                            is_system=True
                        )
                    else:
                        node.url = url
                        node.page_id = page.page_id
                        node.voice_selection = self._voice_selection_for_node(node.name)
                        if self.ui.global_voice_enabled:
                            node.voice_enabled = True
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

    def _default_voice_selection(self, node_name):
        if node_name in VOICE_NATIVE_NODES:
            return VOICE_NATIVE_UI
        return "kokoro_af_heart"

    def _voice_selection_for_node(self, node_name):
        selection = self.voice_selections.get(node_name)
        if selection in VOICE_SELECTION_OPTIONS:
            return selection
        return self._default_voice_selection(node_name)

    def _persist_voice_selections(self):
        config = load_config()
        config["voice_selection"] = dict(self.voice_selections)
        save_config(config)

    @staticmethod
    def _voice_descriptor(selection):
        if selection == VOICE_NATIVE_UI:
            return "NATIVE UI"
        if isinstance(selection, str) and selection.startswith("kokoro_"):
            return selection
        return str(selection)

    def _build_voice_notice(self, changes):
        if len(changes) == 1:
            name, enabled, selection = changes[0]
            if enabled:
                return (
                    f"QuackSink engine: Speech enabled for '{name}' using "
                    f"'{self._voice_descriptor(selection)}'"
                )
            return f"QuackSink engine: Speech disabled for '{name}'"

        parts = []
        for name, enabled, selection in changes:
            if enabled:
                parts.append(
                    f"Speech enabled for '{name}' using '{self._voice_descriptor(selection)}'"
                )
            else:
                parts.append(f"Speech disabled for '{name}'")
        return "QuackSink engine: " + "; ".join(parts)

    def _log_voice_change(self, name, enabled, selection):
        notice = self._build_voice_notice([(name, enabled, selection)])
        self.ui.log(notice, is_system=True)

    def set_node_voice_enabled(self, node, enabled):
        enabled = bool(enabled)
        if node.voice_enabled == enabled:
            return
        node.voice_enabled = enabled
        self.ui._refresh_voice_controls()
        self._log_voice_change(node.name, enabled, node.voice_selection)
        self._schedule_voice_notice(
            self._build_voice_notice([(node.name, enabled, node.voice_selection)])
        )

    def set_node_voice_selection(self, node, selection):
        if selection not in VOICE_SELECTION_OPTIONS:
            return
        if node.voice_selection == selection:
            return
        node.voice_selection = selection
        self.voice_selections[node.name] = selection
        self._persist_voice_selections()
        self.ui._refresh_voice_controls()
        self.ui.log(
            f"[VOICE] {node.name} voice selection saved: {self._voice_descriptor(selection)}",
            is_system=True
        )
        if node.voice_enabled:
            notice = (
                f"QuackSink engine: Speech voice for '{node.name}' changed to "
                f"'{self._voice_descriptor(selection)}'"
            )
            self.ui.log(notice, is_system=True)
            self._schedule_voice_notice(notice)

    def set_global_voice_enabled(self, enabled):
        enabled = bool(enabled)
        self.ui.global_voice_enabled = enabled
        changes = []
        for node in self.nodes.values():
            if node.voice_enabled != enabled:
                node.voice_enabled = enabled
                changes.append((node.name, enabled, node.voice_selection))

        self.ui._refresh_voice_controls()
        if changes:
            notice = self._build_voice_notice(changes)
            self.ui.log(notice, is_system=True)
            self._schedule_voice_notice(notice)
        else:
            self.ui.log(
                f"[VOICE] Global speech {'enabled' if enabled else 'disabled'}; no node state changes were required.",
                is_system=True
            )

    def _schedule_voice_notice(self, notice, only_node=None):
        threading.Thread(
            target=lambda: asyncio.run(self._broadcast_system_notice(notice, only_node=only_node)),
            daemon=True
        ).start()

    async def _broadcast_system_notice(self, notice, only_node=None):
        """Send a shared QS system-state notice to active nodes without relaying replies."""
        with self._voice_notice_lock:
            # Never inject a control notice in the middle of a normal serialized relay.
            for _ in range(600):
                if self.relay.state == RelayState.IDLE:
                    break
                await asyncio.sleep(0.1)

            recipients = [only_node] if only_node else self._ordered_active_nodes()
            recipients = [
                node for node in recipients
                if node and node.is_active() and node.state == NodeState.HANDSHAKED
            ]
            if not recipients:
                self.ui.log(
                    "[VOICE] System notice deferred: no handshaked nodes are available.",
                    is_system=True
                )
                return

            self.ui.log(
                f"[VOICE] Broadcasting system notice to {[node.name for node in recipients]}.",
                is_system=True
            )
            for node in recipients:
                try:
                    page = await self._find_page_for_node(node)
                    if not page:
                        continue
                    success = await self._send_message_to_page(
                        page, node, notice, is_handshake=False
                    )
                    if not success:
                        self.ui.log(
                            f"[VOICE] System notice failed to send to {node.name}.",
                            is_system=True
                        )
                        continue
                    await self._wait_for_response(page, node, timeout=60)
                    self.ui.log(
                        f"[VOICE] System notice acknowledged by {node.name}; response not relayed.",
                        is_system=True
                    )
                except Exception as exc:
                    self.ui.log(
                        f"[VOICE] System notice error for {node.name}: {exc}",
                        is_system=True
                    )

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
        self.ui._refresh_voice_controls()
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

        # A discovered node has an exact Puppeteer target ID.  Keep that binding
        # authoritative; do not silently substitute another tab by URL.
        if node.page_id:
            for page in pages:
                if page.page_id == node.page_id:
                    return page
            self.ui.log(
                f"[VOICE/RELAY] Exact page identity missing for {node.name}: page_id={node.page_id}",
                is_system=True
            )
            return None

        # Discovery/startup fallback only when no page ID was recorded.
        for page in pages:
            if node.url and node.url == page.url:
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
                        if node.voice_enabled:
                            self._schedule_voice_notice(
                                self._build_voice_notice([(node.name, True, node.voice_selection)]),
                                only_node=node
                            )
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

    async def _click_gpt_read_aloud(self, page):
        """GPT: latest assistant response -> More Actions -> Read aloud."""
        try:
            result = await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' &&
                               style.visibility !== 'hidden' &&
                               style.opacity !== '0' &&
                               rect.width > 0 && rect.height > 0;
                    };
                    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
                    const labelOf = (el) => clean([
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].join(' '));
                    const isMore = (el) => {
                        if (!visible(el)) return false;
                        const aria = clean(el.getAttribute('aria-label') || '');
                        const title = clean(el.getAttribute('title') || '');
                        const text = clean(el.textContent || '');
                        return /more\s+actions?/i.test(aria) ||
                               /more\s+actions?/i.test(title) ||
                               /^(?:\.\.\.|…|⋯)$/.test(text);
                    };

                    const assistants = Array.from(
                        document.querySelectorAll('[data-message-author-role="assistant"]')
                    ).filter(visible);
                    let latest = assistants.length ? assistants[assistants.length - 1] : null;
                    if (!latest) {
                        const articles = Array.from(document.querySelectorAll('article')).filter(visible);
                        latest = articles.length ? articles[articles.length - 1] : null;
                    }
                    if (!latest) return {ok:false, stage:'latest_response', reason:'Latest GPT assistant response not found.'};

                    let scope = latest;
                    let moreTarget = null;
                    for (let depth = 0; depth <= 6 && scope; depth += 1) {
                        const candidates = Array.from(
                            scope.querySelectorAll('button,[role="button"],[data-testid]')
                        ).filter(isMore);
                        if (candidates.length) {
                            moreTarget = candidates[candidates.length - 1];
                            break;
                        }
                        scope = scope.parentElement;
                    }
                    if (!moreTarget) return {ok:false, stage:'more_actions', reason:'GPT More Actions control not found on latest assistant response.'};
                    moreTarget.click();
                    return {ok:true, label:labelOf(moreTarget)};
                })()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] GPT More Actions probe failed: {exc}", is_system=True)
            return False

        if not result or not result.get('ok'):
            self.ui.log(
                f"[VOICE] GPT More Actions unavailable: {result.get('reason', 'unknown')}" if result else
                "[VOICE] GPT More Actions unavailable: no result.",
                is_system=True
            )
            return False
        self.ui.log("[VOICE] GPT More Actions opened.", is_system=True)

        try:
            menu_item = await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    };
                    const exact = (el) => {
                        if (!visible(el)) return false;
                        const text = String(el.textContent || '').replace(/\s+/g, ' ').trim();
                        const aria = String(el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
                        const title = String(el.getAttribute('title') || '').replace(/\s+/g, ' ').trim();
                        const testid = String(el.getAttribute('data-testid') || '').replace(/\s+/g, ' ').trim();
                        return /^read\s+aloud$/i.test(text) ||
                               /^read\s+aloud$/i.test(aria) ||
                               /^read\s+aloud$/i.test(title) ||
                               /^read[-_\s]+aloud(?:[-_\s]+button)?$/i.test(testid);
                    };
                    const selectors = [
                        '[role="menu"] [role="menuitem"]',
                        '[role="menu"] button',
                        '[role="menu"] [data-testid]',
                        '[role="menuitem"]',
                        'button,[role="button"],[data-testid]'
                    ];
                    for (const selector of selectors) {
                        const matches = Array.from(document.querySelectorAll(selector)).filter(exact);
                        if (matches.length) { matches[matches.length - 1].click(); return true; }
                    }
                    return false;
                })()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] GPT Read aloud menu probe failed: {exc}", is_system=True)
            return False

        if not menu_item:
            self.ui.log("[VOICE] GPT Read aloud menu item unavailable.", is_system=True)
            return False
        self.ui.log("[VOICE] GPT Read aloud menu item clicked.", is_system=True)
        return True

    async def _click_aisha_read_aloud(self, page, node):
        """Aisha: click the exact Read Aloud control nearest the latest response.

        QS 4.44 deliberately does NOT use a generic "voice"/mic selector.
        Aisha's response action row is identified by the semantic label
        "Read Aloud".  All exact matches are inspected, then the one nearest
        the latest Aisha response in the DOM is selected.  This keeps the
        click tied to the response while excluding STT controls such as
        "Start Voice Input".
        """
        try:
            submitted = self._canonical_message_text(node.last_submitted_text)
            safe_selector = json.dumps(node.output_selector or "div[class*='message']")
            safe_submitted = json.dumps(submitted)
            result = await page.evaluate(fr"""
                (() => {{
                    const visible = (el) => {{
                        if (!el) return false;
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 &&
                               style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0';
                    }};
                    const clean = (value) => String(value || '')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim();
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);
                    const isReadAloud = (el) => {{
                        if (!visible(el)) return false;
                        const labelValues = labels(el);
                        const testId = clean(el.getAttribute('data-testid') || '');
                        const semanticMatch = labelValues.some((value) =>
                            /^read\s+aloud$/i.test(value)
                        );
                        const testIdMatch = /^read-aloud-button$/i.test(testId);
                        const isVoiceInput = labelValues.some((value) =>
                            /voice\s+input|microphone|mic/i.test(value)
                        );
                        return (semanticMatch || testIdMatch) && !isVoiceInput;
                    }};
                    const submittedText = {safe_submitted};

                    const messages = [];
                    const seenMessages = new Set();
                    const addMessage = (el, priority) => {{
                        if (!el || seenMessages.has(el) || !visible(el)) return;
                        const text = clean(el.innerText || el.textContent || '');
                        if (!text) return;
                        seenMessages.add(el);
                        messages.push({{el, text, priority}});
                    }};
                    try {{
                        document.querySelectorAll({safe_selector}).forEach((el) => addMessage(el, 100));
                    }} catch (_) {{}}
                    for (const sel of [
                        '[data-message-id]',
                        '[data-testid*="message"]',
                        '[data-testid*="response"]',
                        '[role="article"]',
                        'article',
                        'div[class*="message"]',
                        'div[class*="response"]'
                    ]) {{
                        try {{ document.querySelectorAll(sel).forEach((el) => addMessage(el, 50)); }} catch (_) {{}}
                    }}
                    if (!messages.length) {{
                        return {{ok:false, reason:'No visible Aisha message-like nodes found.'}};
                    }}

                    const leafCandidates = messages.filter((item) => !messages.some((other) =>
                        other.el !== item.el && item.el.contains(other.el)
                    ));
                    const pool = leafCandidates.length ? leafCandidates : messages;
                    let nonSubmitted = pool.filter((item) =>
                        !submittedText || canonical(item.text) !== submittedText
                    );
                    if (!nonSubmitted.length) nonSubmitted = pool;
                    nonSubmitted.sort((a, b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return b.priority - a.priority;
                    }});
                    const latest = nonSubmitted[nonSubmitted.length - 1].el;

                    const ancestorChain = (el) => {{
                        const chain = [];
                        let current = el;
                        while (current) {{
                            chain.push(current);
                            current = current.parentElement;
                        }}
                        return chain;
                    }};
                    const latestChain = ancestorChain(latest);
                    const distanceToLatest = (el) => {{
                        let current = el;
                        let fromButton = 0;
                        while (current) {{
                            const idx = latestChain.indexOf(current);
                            if (idx !== -1) return fromButton + idx;
                            current = current.parentElement;
                            fromButton += 1;
                        }}
                        return 100000;
                    }};

                    const readButtons = Array.from(document.querySelectorAll(
                        'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip]'
                    )).filter(isReadAloud);

                    if (!readButtons.length) {{
                        const diagnostic = Array.from(document.querySelectorAll(
                            'button,[role="button"]'
                        )).filter(visible).map((el) => clean([
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || '',
                            el.getAttribute('data-testid') || '',
                            el.textContent || ''
                        ].join(' | '))).filter(Boolean).slice(-40);
                        return {{ok:false, reason:'No exact Read Aloud control found.', diagnostics:diagnostic}};
                    }}

                    readButtons.sort((a, b) => {{
                        const da = distanceToLatest(a);
                        const db = distanceToLatest(b);
                        if (da !== db) return da - db;
                        const pos = a.compareDocumentPosition(b);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return 0;
                    }});

                    const target = readButtons[0];
                    target.click();
                    return {{
                        ok:true,
                        label:labels(target).join(' | '),
                        distance:distanceToLatest(target),
                        exactMatchCount:readButtons.length
                    }};
                }})()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] Aisha Read Aloud probe failed: {exc}", is_system=True)
            return False

        if not result or not result.get('ok'):
            reason = result.get('reason', 'unknown') if result else 'no result'
            self.ui.log(f"[VOICE] Aisha Read Aloud unavailable: {reason}", is_system=True)
            if result and result.get('diagnostics'):
                self.ui.log(
                    f"[VOICE] Aisha nearby button diagnostics: {result.get('diagnostics')}",
                    is_system=True
                )
            return False

        self.ui.log(
            f"[VOICE] Aisha Read Aloud clicked "
            f"(distance={result.get('distance')}, exact_matches={result.get('exactMatchCount')}, "
            f"label={result.get('label')!r}).",
            is_system=True
        )
        return True

    async def _aisha_voice_stop_visible(self, page, node):
        """Return True only while Aisha's latest response shows its playback Stop control."""
        try:
            submitted = self._canonical_message_text(node.last_submitted_text)
            safe_selector = json.dumps(node.output_selector or "div[class*='message']")
            safe_submitted = json.dumps(submitted)
            return bool(await page.evaluate(fr"""
                (() => {{
                    const visible = (el) => {{
                        if (!el) return false;
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 &&
                               style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0';
                    }};
                    const clean = (value) => String(value || '')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim();
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);
                    const isStop = (el) => visible(el) && labels(el).some((value) =>
                        /^(?:stop|stop\\s+(?:reading|speaking|playback))$/i.test(value)
                    );
                    const submittedText = {safe_submitted};

                    const messages = [];
                    const seenMessages = new Set();
                    const addMessage = (el, priority) => {{
                        if (!el || seenMessages.has(el) || !visible(el)) return;
                        const text = clean(el.innerText || el.textContent || '');
                        if (!text) return;
                        seenMessages.add(el);
                        messages.push({{el, text, priority}});
                    }};
                    try {{ document.querySelectorAll({safe_selector}).forEach((el) => addMessage(el, 100)); }} catch (_) {{}}
                    for (const sel of [
                        '[data-message-id]', '[data-testid*="message"]', '[data-testid*="response"]',
                        '[role="article"]', 'article', 'div[class*="message"]', 'div[class*="response"]'
                    ]) {{
                        try {{ document.querySelectorAll(sel).forEach((el) => addMessage(el, 50)); }} catch (_) {{}}
                    }}
                    if (!messages.length) return false;

                    const leafCandidates = messages.filter((item) => !messages.some((other) =>
                        other.el !== item.el && item.el.contains(other.el)
                    ));
                    const pool = leafCandidates.length ? leafCandidates : messages;
                    let nonSubmitted = pool.filter((item) =>
                        !submittedText || canonical(item.text) !== submittedText
                    );
                    if (!nonSubmitted.length) nonSubmitted = pool;
                    nonSubmitted.sort((a, b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return b.priority - a.priority;
                    }});
                    const latest = nonSubmitted[nonSubmitted.length - 1].el;

                    const ancestorChain = (el) => {{
                        const chain = [];
                        let current = el;
                        while (current) {{ chain.push(current); current = current.parentElement; }}
                        return chain;
                    }};
                    const latestChain = ancestorChain(latest);
                    const distanceToLatest = (el) => {{
                        let current = el;
                        let fromButton = 0;
                        while (current) {{
                            const idx = latestChain.indexOf(current);
                            if (idx !== -1) return fromButton + idx;
                            current = current.parentElement;
                            fromButton += 1;
                        }}
                        return 100000;
                    }};

                    const stopButtons = Array.from(document.querySelectorAll(
                        'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip]'
                    )).filter(isStop);
                    if (!stopButtons.length) return false;
                    stopButtons.sort((a, b) => distanceToLatest(a) - distanceToLatest(b));
                    return distanceToLatest(stopButtons[0]) < 100000;
                }})()
            """))
        except Exception:
            return False

    async def _gpt_voice_stop_visible(self, page):
        try:
            return bool(await page.evaluate(r"""
                (() => Array.from(document.querySelectorAll('button,[role="button"],[data-testid]')).some((el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const visible = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                    if (!visible) return false;
                    const label = [el.getAttribute('aria-label') || '', el.getAttribute('title') || '', el.getAttribute('data-testid') || '', el.textContent || ''].join(' ').replace(/\s+/g, ' ').trim();
                    return /\bstop(?:\s+reading(?:\s+aloud)?)?\b/i.test(label);
                }))()
            """))
        except Exception:
            return False

    async def _click_gemini_listen(self, page):
        """Gemini: latest assistant response -> Show more options button -> Listen."""
        try:
            opened = await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    };
                    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
                    const responseSelectors = ['model-response', '.model-response-text'];
                    const responses = [];
                    for (const selector of responseSelectors) {
                        for (const el of document.querySelectorAll(selector)) {
                            if (visible(el)) responses.push(el);
                        }
                    }
                    const uniqueResponses = Array.from(new Set(responses));
                    let latest = uniqueResponses.length ? uniqueResponses[uniqueResponses.length - 1] : null;
                    if (!latest) {
                        const candidates = Array.from(document.querySelectorAll('div,section,article'))
                            .filter(visible)
                            .filter((el) => /model-response/i.test(String(el.className || '')));
                        latest = candidates.length ? candidates[candidates.length - 1] : null;
                    }
                    if (!latest) return {ok:false, reason:'Latest Gemini response not found.'};

                    const isShowMoreOptionsButton = (el) => {
                        if (!visible(el)) return false;
                        const aria = clean(el.getAttribute('aria-label') || '');
                        const title = clean(el.getAttribute('title') || '');
                        const tooltip = clean(el.getAttribute('mattooltip') || '');
                        const dataTooltip = clean(el.getAttribute('data-tooltip') || '');
                        return [aria, title, tooltip, dataTooltip].some((value) =>
                            /^(?:show\s+more\s+options|more\s+options|more\s+actions?)$/i.test(value)
                        );
                    };

                    // Primary target: Gemini's actual accessibility-labelled response-menu button.
                    // The visual control is only a circular "..." icon; its accessible identity is
                    // the label, not the glyph itself.
                    const controlSelector = 'button,[role="button"],[aria-label]';
                    let target = null;
                    let targetReason = '';

                    let scope = latest;
                    for (let depth = 0; depth <= 12 && scope && !target; depth += 1) {
                        const controls = Array.from(scope.querySelectorAll(controlSelector)).filter(visible);
                        const matches = controls.filter(isShowMoreOptionsButton);
                        if (matches.length) {
                            target = matches[matches.length - 1];
                            targetReason = `aria-labelled Show more options depth=${depth}`;
                            break;
                        }
                        scope = scope.parentElement;
                    }

                    // Secondary target: exact accessibility hook anywhere on this Gemini page,
                    // but only accept a response-action button located below the latest response.
                    if (!target) {
                        const pageMatches = Array.from(document.querySelectorAll(controlSelector))
                            .filter(isShowMoreOptionsButton)
                            .filter((el) => {
                                const r = el.getBoundingClientRect();
                                const rr = latest.getBoundingClientRect();
                                return r.top >= rr.bottom - 160 && r.top <= rr.bottom + 500;
                            });
                        if (pageMatches.length) {
                            const rr = latest.getBoundingClientRect();
                            pageMatches.sort((a, b) => {
                                const ar = a.getBoundingClientRect();
                                const br = b.getBoundingClientRect();
                                return Math.abs((ar.top + ar.height / 2) - rr.bottom) -
                                       Math.abs((br.top + br.height / 2) - rr.bottom);
                            });
                            target = pageMatches[0];
                            targetReason = 'aria-labelled Show more options proximity';
                        }
                    }

                    if (!target) {
                        const diagnostics = Array.from(document.querySelectorAll('button,[role="button"]'))
                            .filter(visible)
                            .slice(-30)
                            .map((el) => {
                                const r = el.getBoundingClientRect();
                                return {
                                    text: clean(el.textContent || ''),
                                    aria: clean(el.getAttribute('aria-label') || ''),
                                    title: clean(el.getAttribute('title') || ''),
                                    mattooltip: clean(el.getAttribute('mattooltip') || ''),
                                    dataTooltip: clean(el.getAttribute('data-tooltip') || ''),
                                    w: Math.round(r.width),
                                    h: Math.round(r.height),
                                    y: Math.round(r.top)
                                };
                            });
                        return {ok:false, reason:'Gemini Show more options button not found.', diagnostics};
                    }

                    target.scrollIntoView({block:'nearest', inline:'nearest'});
                    target.click();
                    return {ok:true, reason:targetReason};
                })()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] Gemini More probe failed: {exc}", is_system=True)
            return False
        if not opened or not opened.get('ok'):
            reason = opened.get('reason', 'unknown') if opened else 'no result.'
            if opened and opened.get('diagnostics'):
                self.ui.log(f"[VOICE] Gemini More diagnostics: {opened.get('diagnostics')}", is_system=True)
            self.ui.log(f"[VOICE] Gemini More unavailable: {reason}", is_system=True)
            return False
        self.ui.log(f"[VOICE] Gemini Show more options clicked ({opened.get('reason', 'target')}).", is_system=True)

        # Gemini renders the menu asynchronously after the button click. Poll briefly rather
        # than querying the DOM in the same turn as the click.
        try:
            listened = await page.evaluate(r"""
                (async () => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    };
                    const exactListen = (el) => {
                        if (!visible(el)) return false;
                        const labels = [
                            el.textContent || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || '',
                            el.getAttribute('data-testid') || '',
                            el.getAttribute('data-tooltip') || '',
                            el.getAttribute('mattooltip') || ''
                        ].map((v) => String(v || '').replace(/\s+/g, ' ').trim());
                        return labels.some((value) => /^listen$/i.test(value));
                    };

                    const selectors = [
                        '[role="menu"] [role="menuitem"]',
                        '[role="menu"] button',
                        '[role="menuitem"]',
                        '[mat-menu-item]',
                        'button,[role="button"]'
                    ];

                    for (let attempt = 0; attempt < 12; attempt += 1) {
                        for (const selector of selectors) {
                            const matches = Array.from(document.querySelectorAll(selector)).filter(exactListen);
                            if (matches.length) {
                                matches[matches.length - 1].click();
                                return {ok:true, waited_ms:attempt * 100};
                            }
                        }
                        await new Promise((resolve) => setTimeout(resolve, 100));
                    }
                    return {ok:false, reason:'Gemini Listen menu item not found after menu-open wait.'};
                })()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] Gemini Listen probe failed: {exc}", is_system=True)
            return False
        if not listened or not listened.get('ok'):
            reason = listened.get('reason', 'unknown') if listened else 'no result.'
            self.ui.log(f"[VOICE] Gemini Listen unavailable: {reason}", is_system=True)
            return False
        self.ui.log(f"[VOICE] Gemini Listen clicked (menu wait={listened.get('waited_ms', 0)} ms).", is_system=True)
        return True

    async def _gemini_pause_visible(self, page):
        try:
            return bool(await page.evaluate(r"""
                (() => Array.from(document.querySelectorAll('button,[role="button"],[data-testid]')).some((el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) return false;
                    const label = [el.getAttribute('aria-label') || '', el.getAttribute('title') || '', el.getAttribute('data-testid') || '', el.textContent || ''].join(' ').replace(/\s+/g, ' ').trim();
                    return /\bpause\b/i.test(label) && rect.top < 180 && rect.left > window.innerWidth * 0.60;
                }))()
            """))
        except Exception:
            return False

    async def _click_deepseek_read_aloud(self, page, node):
        """DeepSeek: latest assistant response -> inline Read aloud action control."""
        try:
            clicked = await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    };
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('mattooltip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map((v) => String(v || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
                    const exactRead = (el) => visible(el) && labels(el).some((value) => /\bread\s+aloud\b/i.test(value));
                    const controlsIn = (scope) => Array.from(scope.querySelectorAll(
                        'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip],[mattooltip]'
                    )).filter(exactRead);

                    const messages = Array.from(document.querySelectorAll('div[class*="message"]')).filter(visible);
                    const latest = messages.length ? messages[messages.length - 1] : null;
                    if (!latest) return {ok:false, reason:'Latest DeepSeek message not found.'};

                    const latestRect = latest.getBoundingClientRect();
                    const scopes = [];
                    const addScope = (el, kind, level) => {
                        if (!el || scopes.some((item) => item.el === el)) return;
                        scopes.push({el, kind, level});
                    };
                    addScope(latest, 'latest', 0);

                    let ancestor = latest.parentElement;
                    for (let level = 1; level <= 4 && ancestor; level += 1) {
                        addScope(ancestor, 'ancestor', level);
                        ancestor = ancestor.parentElement;
                    }

                    let sibling = latest.nextElementSibling;
                    for (let index = 0; index < 3 && sibling; index += 1) {
                        addScope(sibling, 'sibling', index + 1);
                        sibling = sibling.nextElementSibling;
                    }

                    const candidates = [];
                    for (const scope of scopes) {
                        for (const el of controlsIn(scope.el)) {
                            const rect = el.getBoundingClientRect();
                            const centerY = rect.top + rect.height / 2;
                            const centerX = rect.left + rect.width / 2;
                            const verticalDistance = Math.abs(centerY - latestRect.bottom);
                            const horizontalOverlap =
                                Math.max(0, Math.min(rect.right, latestRect.right) - Math.max(rect.left, latestRect.left));
                            let score = 0;
                            if (scope.kind === 'latest') score += 1000;
                            else if (scope.kind === 'ancestor') score += 900 - scope.level * 40;
                            else score += 840 - scope.level * 20;
                            score += horizontalOverlap > 0 ? 25 : 0;
                            score -= verticalDistance * 0.02;
                            candidates.push({el, score, label: labels(el).join(' | '), centerX, centerY, scope: scope.kind});
                        }
                    }

                    // Fallback: semantic-only document search near the latest response.
                    // No geometry-only button guessing is used here.
                    if (!candidates.length) {
                        for (const el of Array.from(document.querySelectorAll(
                            'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip],[mattooltip]'
                        )).filter(exactRead)) {
                            const rect = el.getBoundingClientRect();
                            const centerY = rect.top + rect.height / 2;
                            const centerX = rect.left + rect.width / 2;
                            if (centerY < latestRect.top - 40 || centerY > latestRect.bottom + 500) continue;
                            const horizontalOverlap =
                                Math.max(0, Math.min(rect.right, latestRect.right) - Math.max(rect.left, latestRect.left));
                            let score = 500 - Math.abs(centerY - latestRect.bottom) * 0.02;
                            score += horizontalOverlap > 0 ? 20 : 0;
                            candidates.push({el, score, label: labels(el).join(' | '), centerX, centerY, scope: 'document-near-latest'});
                        }
                    }

                    if (!candidates.length) {
                        return {ok:false, reason:'DeepSeek semantic Read aloud control not found around latest response.'};
                    }

                    candidates.sort((a, b) => b.score - a.score);
                    const best = candidates[0];
                    best.el.click();
                    return {
                        ok:true,
                        label:best.label,
                        score:Math.round(best.score * 10) / 10,
                        scope:best.scope,
                        candidate_count:candidates.length
                    };
                })()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] DeepSeek Read aloud probe failed: {exc}", is_system=True)
            return False
        if not clicked or not clicked.get('ok'):
            self.ui.log(
                f"[VOICE] DeepSeek Read aloud unavailable: {clicked.get('reason','unknown')}" if clicked else
                "[VOICE] DeepSeek Read aloud unavailable: no result.",
                is_system=True
            )
            return False
        self.ui.log(
            f"[VOICE] DeepSeek Read aloud clicked (scope={clicked.get('scope')}, "
            f"score={clicked.get('score')}, candidates={clicked.get('candidate_count')}).",
            is_system=True
        )
        return True

    async def _deepseek_playback_control_visible(self, page):
        try:
            return bool(await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    };
                    const labelOf = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('mattooltip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].join(' ').replace(/\s+/g, ' ').trim();

                    // Prefer controls associated with the latest response.
                    const messages = Array.from(document.querySelectorAll('div[class*="message"]')).filter(visible);
                    const latest = messages.length ? messages[messages.length - 1] : null;
                    const scopes = [];
                    if (latest) {
                        scopes.push(latest);
                        let ancestor = latest.parentElement;
                        for (let level = 0; level < 4 && ancestor; level += 1) {
                            scopes.push(ancestor);
                            ancestor = ancestor.parentElement;
                        }
                    }

                    const hasPlayingControl = (scope) => Array.from(scope.querySelectorAll(
                        'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip],[mattooltip]'
                    )).some((el) => {
                        if (!visible(el)) return false;
                        return /\b(?:pause|stop|reading\s+aloud|speaking)\b/i.test(labelOf(el));
                    });

                    if (scopes.some(hasPlayingControl)) return true;

                    // DeepSeek may use an animated equalizer / audio element rather than a labeled
                    // pause button. These checks are page-local and only occur immediately after
                    // QS has clicked the response's Read aloud control.
                    const activeAudio = Array.from(document.querySelectorAll('audio')).some((audio) => {
                        try { return !audio.paused && audio.readyState >= 2 && audio.currentTime >= 0; }
                        catch (_) { return false; }
                    });
                    if (activeAudio) return true;

                    try {
                        if (window.speechSynthesis && window.speechSynthesis.speaking) return true;
                    } catch (_) {}

                    return false;
                })()
            """))
        except Exception:
            return False

    async def _wait_for_voice_playback(self, page, node):
        """Wait for the node's playback control to appear, then disappear."""
        start = asyncio.get_event_loop().time()
        saw_control = False

        while asyncio.get_event_loop().time() - start < 8.0:
            if node.name == 'GPT':
                visible = await self._gpt_voice_stop_visible(page)
            elif node.name == 'Gemini':
                visible = await self._gemini_pause_visible(page)
            elif node.name == 'DeepSeek':
                visible = await self._deepseek_playback_control_visible(page)
            elif node.name == 'Aisha':
                visible = await self._aisha_voice_stop_visible(page, node)
            else:
                visible = False

            if visible:
                saw_control = True
                self.ui.log(f"[VOICE] {node.name} playback started; waiting for playback control to clear.", is_system=True)
                break
            await asyncio.sleep(0.2)

        if not saw_control:
            self.ui.log(f"[VOICE] {node.name} playback control was not observed after starting voice.", is_system=True)
            return False

        while asyncio.get_event_loop().time() - start < 1800.0:
            if node.name == 'GPT':
                visible = await self._gpt_voice_stop_visible(page)
            elif node.name == 'Gemini':
                visible = await self._gemini_pause_visible(page)
            elif node.name == 'DeepSeek':
                visible = await self._deepseek_playback_control_visible(page)
            elif node.name == 'Aisha':
                visible = await self._aisha_voice_stop_visible(page, node)
            else:
                visible = False

            if not visible:
                self.ui.log(f"[VOICE] {node.name} playback complete.", is_system=True)
                return True
            await asyncio.sleep(0.5)

        self.ui.log(f"[VOICE] {node.name} playback safety timeout reached.", is_system=True)
        return False

    async def _maybe_speak_node(self, page, node, response_text):
        """Speak a completed response using the node's selected voice backend."""
        if not self.ui.is_node_voice_enabled(node):
            return

        selection = node.voice_selection

        if isinstance(selection, str) and selection.startswith("kokoro_"):
            try:
                metrics = self.kokoro.speak(response_text, selection)
                self.ui.log(
                    f"[VOICE] {node.name} Kokoro {metrics['voice_id']} complete "
                    f"(synth={metrics['synth']:.2f}s, play={metrics['play']:.2f}s, "
                    f"total={metrics['total']:.2f}s, chunks={metrics['chunks']}).",
                    is_system=True
                )
            except Exception as exc:
                self.ui.log(
                    f"[VOICE] {node.name} Kokoro speech failed: {exc}",
                    is_system=True
                )
            return

        if selection != VOICE_NATIVE_UI:
            self.ui.log(
                f"[VOICE] {node.name} has unknown voice selection '{selection}'.",
                is_system=True
            )
            return

        # Native voice is a browser-page action. Verify the exact tab before DOM work.
        if node.name in VOICE_NATIVE_NODES:
            if node.page_id and page.page_id != node.page_id:
                self.ui.log(
                    f"[VOICE] {node.name} page identity mismatch; refusing cross-tab voice action. "
                    f"expected={node.page_id} actual={page.page_id}",
                    is_system=True
                )
                return
        else:
            self.ui.log(
                f"[VOICE] {node.name} has no native UI voice path; select a Kokoro voice.",
                is_system=True
            )
            return

        try:
            await self._prepare_background_page(node)
        except Exception:
            pass

        if node.name == 'GPT':
            started = await self._click_gpt_read_aloud(page)
        elif node.name == 'Gemini':
            started = await self._click_gemini_listen(page)
        elif node.name == 'DeepSeek':
            started = await self._click_deepseek_read_aloud(page, node)
        elif node.name == 'Aisha':
            started = await self._click_aisha_read_aloud(page, node)
        else:
            started = False

        if not started:
            return

        await self._wait_for_voice_playback(page, node)

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
                        await self._maybe_speak_node(page, node, clean)
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
            node.last_submitted_text = str(text).strip()
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

    def _canonical_message_text(self, value):
        """Normalize chat text for identity comparisons across browser DOM wrappers."""
        import unicodedata
        text = unicodedata.normalize("NFKC", str(value or ""))
        text = text.replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text).strip().casefold()
        return text

    def _response_candidates(self, messages, node):
        """Return post-submit response candidates while excluding our own user message.

        Some sites, notably DeepSeek, use a generic message selector that
        includes both user and assistant bubbles. Browser-rendered copies of
        the submitted text can differ in whitespace or Unicode normalization,
        so raw string equality is not sufficient to identify our own message.
        """
        messages = self._normalize_messages(messages, "response_candidates")
        baseline = self._normalize_messages(node.response_baseline or [], "response_baseline")
        candidates = messages[len(baseline):] if len(messages) > len(baseline) else []
        if not candidates:
            last_message = self._safe_last(messages)
            last_baseline = self._safe_last(baseline)
            if last_message != last_baseline and last_message is not None:
                candidates = [last_message]

        submitted = self._canonical_message_text(node.last_submitted_text)
        if submitted:
            filtered = []
            filtered_count = 0
            for candidate in candidates:
                canonical_candidate = self._canonical_message_text(candidate)
                if canonical_candidate == submitted:
                    filtered_count += 1
                    continue
                filtered.append(candidate)
            if filtered_count:
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: filtered {filtered_count} submitted user message(s) from response candidates after normalization.",
                    is_system=True
                )
            candidates = filtered

        return candidates

    async def _submit_verified(self, page, node, input_element, selector, method):
        # QS 4.13: composer-clear is NOT proof that Enter submitted a message.
        # DeepSeek can clear the composer while consuming Enter without creating
        # a new assistant response. Button clicks retain the older clear-or-output
        # confirmation; Enter requires observable output because that is the
        # evidence that distinguishes a real submission from a swallowed Enter.
        timeout = 8.0 if method == "Enter" else 3.0
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
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
            response_candidates = self._response_candidates(current, node)
            new_output = bool(response_candidates)

            if method == "Enter":
                # A target-page Enter can successfully submit before the new
                # assistant DOM node is observable through extract_texts().
                # In that case the composer clears and the browser immediately
                # reports a busy generation state. That combination is the same
                # transition QS already accepts for a real button click.
                #
                # Keep DeepSeek's old swallowed-Enter protection: composer clear
                # by itself is NOT enough. Require either observable new output
                # or the stronger clear+busy transition.
                enter_submitted = new_output or ((not still_has_text) and busy)
                if enter_submitted:
                    reason = (
                        "new_output" if new_output
                        else "composer_clear+busy"
                    )
                    self.ui.log(
                        f"[SEND] SUBMIT CONFIRMED ({method}): {node.name} | "
                        f"input_clear={not still_has_text} busy={busy} "
                        f"new_output={new_output} evidence={reason}",
                        is_system=True
                    )
                    return True
            else:
                if not still_has_text or new_output:
                    self.ui.log(
                        f"[SEND] SUBMIT CONFIRMED ({method}): {node.name} | "
                        f"input_clear={not still_has_text} busy={busy} new_output={new_output}",
                        is_system=True
                    )
                    return True

            self.ui.log(
                f"[SEND] SUBMIT PENDING ({method}): {node.name} | "
                f"input_clear={not still_has_text} busy={busy} new_output={new_output}",
                is_system=True
            )

        self.ui.log(
            f"[SEND] SUBMIT NOT CONFIRMED ({method}): {node.name} | "
            f"Enter requires new_output={True if method == 'Enter' else 'not required'}.",
            is_system=True
        )
        return False

    async def _prepare_background_page(self, node):
        """Keep a background tab's renderer active without bringing it forward."""
        try:
            await asyncio.to_thread(
                self.browser.bridge.request,
                {"op": "prepare_page", "pageId": node.page_id, "url": node.url}
            )
            self.ui.log(
                f"[SEND] PAGE ACTIVE/FOCUS EMULATED: {node.name}",
                is_system=True
            )
            self.ui.log(
                f"[SEND] DOCUMENT VISIBILITY/FOCUS SHIM: {node.name}",
                is_system=True
            )
            return True
        except Exception as exc:
            self.ui.log(
                f"[SEND] PAGE PREP FAILED: {node.name}: {exc}",
                is_system=True
            )
            return False

    async def _submit(self, page, node, input_element, selector):
        await self._prepare_background_page(node)
        send_selectors = [
            'button[aria-label*="Send"]', 'button[type="submit"]',
            '[data-testid="send-button"]'
        ]

        # Give the web app a moment to turn the send control into its enabled
        # state after QS fills the composer. In a background tab, React/Vue/etc.
        # can update the control one or two render ticks later than the DOM text.
        for attempt in range(10):
            found_candidate = False
            for send_selector in send_selectors:
                try:
                    buttons = await page.query_selector_all(send_selector)
                    for button in buttons:
                        if not await button.is_visible():
                            continue
                        found_candidate = True
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
                        await self._prepare_background_page(node)
                        await button.click()
                        if await self._submit_verified(page, node, input_element, selector, "button"):
                            return True
                except Exception as exc:
                    self.ui.log(
                        f"[SEND] button submit attempt failed for {node.name}: {exc}",
                        is_system=True
                    )
            if attempt < 9:
                self.ui.log(
                    f"[SEND] BUTTON WAIT: {node.name} attempt={attempt + 1}/10 candidate={found_candidate}",
                    is_system=True
                )
                await asyncio.sleep(0.20)

        # Final fallback: synthesize the Enter event on the actual composer
        # inside the target page. This does not depend on the browser window
        # owning OS focus, unlike Puppeteer's page.keyboard.press().
        try:
            self.ui.log(f"[SEND] SUBMIT ATTEMPT (Enter/DOM): {node.name}", is_system=True)
            await asyncio.to_thread(
                self.browser.bridge.request,
                {"op": "element_dispatch_enter", "pageId": node.page_id, "url": node.url, "selector": selector, "index": getattr(input_element, 'index', 0)}
            )
            if await self._submit_verified(page, node, input_element, selector, "Enter"):
                return True
        except Exception as exc:
            self.ui.log(f"[SEND] Enter DOM submit attempt failed for {node.name}: {exc}", is_system=True)

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

    async def _capture_aisha_latest(self, page, node):
        """Capture ONLY Aisha's newest message node.

        Aisha's UI has historically re-ingested the full transcript/history
        wrapper during parsing. The old DRS/MMRC workaround was to lock
        extraction to the latest response/turn rather than scrape the whole
        transcript. This is the proven QS 4.38 workaround, restored here, with transient Aisha UI-status filtering added in QS 4.44.
        """
        try:
            selector = node.output_selector or "div[class*='message']"
            submitted = self._canonical_message_text(node.last_submitted_text)
            safe_selector = json.dumps(selector)
            safe_submitted = json.dumps(submitted)

            result = await page.evaluate(fr"""
                (() => {{
                    const visible = (el) => {{
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               s.display !== 'none' && s.visibility !== 'hidden' &&
                               s.opacity !== '0';
                    }};
                    const clean = (value) => String(value || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\r\n?/g, '\n')
                        .split('\n')
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .join('\n')
                        .trim();
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const submittedText = {safe_submitted};
                    const candidates = [];
                    const seen = new Set();
                    const transientStatus = (value) => {{
                        const normalized = canonical(value);
                        // Aisha may prefix transient UI status nodes with her speaker label,
                        // e.g. "AISHA\nThinking…". Treat that whole status node as transient.
                        return /^(?:(?:aisha|assistant)\s+)?(?:thinking[.…\.]*|generating[.…\.]*|loading[.…\.]*|typing[.…\.]*|processing[.…\.]*|searching[.…\.]*|working[.…\.]*)$/i.test(normalized);
                    }};
                    const add = (el, source, priority) => {{
                        if (!el || seen.has(el) || !visible(el)) return;
                        const text = clean(el.innerText || el.textContent || '');
                        if (!text || transientStatus(text)) return;
                        seen.add(el);
                        candidates.push({{el, source, priority, text}});
                    }};

                    try {{
                        document.querySelectorAll({safe_selector}).forEach((el) => add(el, 'discovered-selector', 100));
                    }} catch (_) {{}}

                    const fallbackSelectors = [
                        '[data-message-id]',
                        '[data-testid*="message"]',
                        '[data-testid*="response"]',
                        '[role="article"]',
                        'article',
                        'div[class*="message"]',
                        'div[class*="response"]'
                    ];
                    for (const sel of fallbackSelectors) {{
                        try {{ document.querySelectorAll(sel).forEach((el) => add(el, sel, 50)); }} catch (_) {{}}
                    }}

                    if (!candidates.length) return {{ok:false, reason:'No visible Aisha message-like nodes found.'}};

                    const leafCandidates = candidates.filter((item) => !candidates.some((other) =>
                        other.el !== item.el && item.el.contains(other.el)
                    ));
                    const pool = leafCandidates.length ? leafCandidates : candidates;

                    let nonSubmitted = pool.filter((item) =>
                        !submittedText || canonical(item.text) !== submittedText
                    );
                    if (submittedText && !nonSubmitted.length) {{
                        return {{ok:false, reason:'Latest Aisha message is the submitted user turn; assistant delta not present yet.'}};
                    }}
                    if (!nonSubmitted.length) nonSubmitted = pool;

                    nonSubmitted.sort((a, b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return b.priority - a.priority;
                    }});
                    const chosen = nonSubmitted[nonSubmitted.length - 1];
                    return {{ok:true, text:chosen.text, source:chosen.source,
                            candidateCount:candidates.length, leafCount:leafCandidates.length}};
                }})()
            """)

            if not result or not result.get('ok'):
                reason = result.get('reason', 'unknown') if result else 'no result'
                self.ui.log(f"[AISHA-CAPTURE] No fresh latest response: {reason}", is_system=True)
                return []

            text = str(result.get('text') or '').strip()
            if not text:
                return []
            self.ui.log(
                f"[AISHA-CAPTURE] Latest response locked to one DOM node "
                f"(source={result.get('source')}, candidates={result.get('candidateCount')}, "
                f"leaves={result.get('leafCount')}, chars={len(text)}).",
                is_system=True
            )
            return [text]
        except Exception as exc:
            self.ui.log(
                f"[AISHA-CAPTURE] Latest-node extraction failed: {type(exc).__name__}: {exc}",
                is_system=True
            )
            return []

    async def _capture_output_snapshot(self, page, node):
        if node.name == "Aisha":
            return await self._capture_aisha_latest(page, node)

        selector = node.output_selector
        if not selector:
            return []
        try:
            value = await page.extract_texts(selector)
            # This boundary must produce a real Python list. Keep the
            # diagnostic rather than silently turning a transport anomaly
            # into a fake message.
            if isinstance(value, list):
                return value
            self.ui.log(
                f"[WAIT-DIAG] output capture returned {type(value).__name__}; "
                f"selector={selector!r}",
                is_system=True
            )
            return []
        except Exception as exc:
            self.ui.log(
                f"[WAIT-DIAG] output capture failed: {type(exc).__name__}: {exc}",
                is_system=True
            )
            return []

    def _normalize_messages(self, value, label="messages"):
        """Normalize browser-returned output into a plain list of strings.

        The relay state machine should never crash because a browser adapter
        returned an unexpected container type. During development, record the
        type so the transport boundary can be fixed without guessing.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if isinstance(value, tuple):
            return [str(item) for item in value if item is not None]
        if isinstance(value, dict):
            self.ui.log(
                f"[WAIT-DIAG] {label}: unexpected dict from browser adapter; "
                f"keys={list(value.keys())[:10]}",
                is_system=True
            )
            return [str(item) for item in value.values() if item is not None]
        self.ui.log(
            f"[WAIT-DIAG] {label}: unexpected {type(value).__name__}; coercing to one item.",
            is_system=True
        )
        return [str(value)]

    def _safe_last(self, values):
        values = self._normalize_messages(values, "safe_last")
        return values[-1] if values else None

    async def _response_frame_state(self, page, node):
        messages = self._normalize_messages(
            await self._capture_output_snapshot(page, node),
            "response_frame",
        )
        return bool(self._response_candidates(messages, node))

    async def _wait_for_response(self, page, node, timeout=45, is_handshake=False):
        self.ui.log(
            f"[WAIT] {node.name}: waiting for generation to finish...",
            is_system=True
        )

        # QS 4.27: timeout is an INACTIVITY timeout, not a wall-clock timeout.
        # Any observed progress resets the deadline: active generation, or a
        # response whose text is still changing.  This lets deliberately slow
        # or very verbose nodes (notably Chron) keep working as long as the
        # browser continues to show genuine activity.
        last_activity_time = asyncio.get_event_loop().time()
        saw_busy = False
        saw_new_response = False
        stable_streak = 0
        idle_streak = 0
        last_response_text = None
        handshake_stable_streak = 0
        last_handshake_frame = None
        poll = 0

        while True:
            now = asyncio.get_event_loop().time()
            if now - last_activity_time >= timeout:
                break

            await asyncio.sleep(0.5)
            poll += 1

            try:
                await self._prepare_background_page(node)
            except Exception:
                pass

            try:
                generation_state = await self._browser_generation_state(page)
                if generation_state.get("error"):
                    raise RuntimeError(generation_state.get("error"))
                generation_busy = bool(generation_state.get("busyControl"))
            except Exception as exc:
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: generation-state probe failed on poll {poll}: {exc}",
                    is_system=True
                )
                generation_busy = None

            try:
                frame_ready = bool(await self._response_frame_state(page, node))
            except Exception as exc:
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: response-frame probe failed on poll {poll}: {exc}",
                    is_system=True
                )
                frame_ready = False

            try:
                messages = self._normalize_messages(
                    await self._capture_output_snapshot(page, node),
                    "wait_messages",
                )
            except Exception as exc:
                self.ui.log(
                    f"[WAIT-DIAG] {node.name}: output snapshot failed on poll {poll}: {exc}",
                    is_system=True
                )
                messages = []

            candidates = self._response_candidates(messages, node)
            current_response_text = str(candidates[-1]).strip() if candidates else None

            # Activity is any observable forward motion in the browser/model:
            # active generation or response text changing.  Merely having an
            # already-visible response frame is NOT activity, because a frozen
            # response must still be allowed to time out.
            activity_reason = None
            if generation_busy is True:
                activity_reason = "generation busy"
            elif current_response_text is not None and current_response_text != last_response_text:
                activity_reason = "response text changed"

            if activity_reason is not None:
                previous_activity = last_activity_time
                last_activity_time = asyncio.get_event_loop().time()
                # Avoid log spam when a node remains continuously busy.  Record
                # the reset only when the node had actually gone quiet long
                # enough for the deadline to move noticeably.
                if last_activity_time - previous_activity > 2.0:
                    self.ui.log(
                        f"[WAIT-DIAG] {node.name}: timeout deadline reset by {activity_reason}.",
                        is_system=True
                    )

            if frame_ready or current_response_text:
                if not saw_new_response:
                    self.ui.log(
                        f"[WAIT] {node.name}: new cleaned assistant output detected.",
                        is_system=True
                    )
                saw_new_response = True

            if generation_busy is True:
                if not saw_busy:
                    self.ui.log(f"[WAIT] {node.name}: browser generation is busy.", is_system=True)
                saw_busy = True
                idle_streak = 0
            elif generation_busy is False:
                idle_streak += 1
                if poll <= 3 or idle_streak <= 3:
                    self.ui.log(
                        f"[WAIT-DIAG] {node.name}: browser generation reports idle; idle_streak={idle_streak}",
                        is_system=True
                    )
            else:
                idle_streak = 0

            if is_handshake:
                handshake_frame = None
                for candidate in reversed(candidates):
                    matches = list(re.finditer(r'🟩.*?🔚', str(candidate), re.DOTALL))
                    if matches:
                        handshake_frame = matches[-1].group().strip()
                        break

                if handshake_frame:
                    if handshake_frame == last_handshake_frame:
                        handshake_stable_streak += 1
                    else:
                        handshake_stable_streak = 1
                        last_handshake_frame = handshake_frame

                    self.ui.log(
                        f"[WAIT-DIAG] {node.name}: handshake frame observed; stability={handshake_stable_streak}",
                        is_system=True
                    )

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

            if saw_new_response and current_response_text:
                # QS 4.25: generation does not have to be observed in its busy
                # state before completion can be accepted. The browser probe can
                # legitimately first report idle by the time QS samples it after
                # submit. What matters is that the browser reports idle now and
                # the response remains stable, preserving protection against a
                # still-streaming or frozen partial output.
                #
                # The Send button is NOT a reliable busy/idle signal because an
                # empty composer can legitimately leave Send disabled after the
                # assistant has completely finished.
                if generation_busy is not False:
                    stable_streak = 0
                    last_response_text = current_response_text
                elif current_response_text == last_response_text:
                    stable_streak += 1
                else:
                    stable_streak = 1
                    last_response_text = current_response_text

                if generation_busy is False and idle_streak >= 2 and stable_streak >= 4:
                    self.ui.log(
                        f"[WAIT] {node.name}: response finalized by output stability after browser generation idle.",
                        is_system=True
                    )
                    return True
            elif current_response_text is None:
                stable_streak = 0
                last_response_text = None

        self.ui.log(
            f"[WAIT] {node.name}: response timeout after {timeout}s of inactivity.",
            is_system=True
        )
        return False

    async def _get_response(self, page, node, is_handshake=False):
        messages = await self._capture_output_snapshot(page, node)
        if not messages:
            return "No response text extracted from DOM."

        candidates = self._response_candidates(messages, node)

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
        logger.error("Fatal QS 5.0 startup error: %s", exc)
        print(f"FATAL QS 5.0 ERROR: {exc}")
        input("Press ENTER to exit...")
