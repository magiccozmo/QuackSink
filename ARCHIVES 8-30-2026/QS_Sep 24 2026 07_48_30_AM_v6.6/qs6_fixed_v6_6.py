# QuackSink - Multi-Mind Relay Core
# VERSION: QS 6.3
# QS 6.3 DEVELOPMENT:
#   - Claude native Read Aloud gating follows the actual Claude UI state:
#     Read Aloud -> Pause while speaking -> Read Aloud when finished.
#   - Native speech remains a blocking relay step; Kokoro remains blocking via
#     sounddevice.wait().
#   - Idle 'Read Aloud' labels are no longer treated as active playback.
# QS 5.11 DEVELOPMENT:
#   - Keeps the QS 5.10 Aisha extracted-style voice integration.
#   - Fixes the message-submit fallback: use a real CDP key event for Enter
#     before the older synthetic DOM KeyboardEvent fallback.
#   - This preserves the known-good QS relay/state-machine behavior while making
#     the browser receive an Enter event much closer to a real human Enter.
# QS 5.10 DEVELOPMENT:
#   - Adds the extracted Aisha1 Kokoro style as a selectable local Kokoro voice.
#   - Uses the saved 1000-step Aisha checkpoint from kokoro.embed.
#   - Keeps Aisha NATIVE UI available and unchanged; the extracted voice is an additional choice.
#   - Loads the custom 256-dimension style from a local voice asset without editing QS 5.9.
#   - Custom-style synthesis uses the same differentiable Kokoro forward path used by the working Aisha test.

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
#   - Treats node introduction as an explicit state-machine phase.
#   - Sends the embedded QuackSink preamble as the node introduction/channel-opening event.
#   - The preamble includes the DRS paper, Duckspace axioms, and Library index.
#   - The Library doorway is also available to the human operator in the UI.
#   - Adds a public-facing "WHAT CAN THIS DO?" button linking to The Shakedown Blues.
#   - The preamble itself is the handshake; no second handshake prompt or token framing is used.
#   - Allows first-run bootstrap when no QS 2.2 archive exists remotely; the local
#     archive is created after verification so it can become the first public archive.
#   - Keeps the implementation organized around explicit states and transitions;
#     Python implements the model rather than becoming the model.
#   - Uses Puppeteer target IDs as stable page identity so mutable chat URLs do not
#     make a live node appear offline after navigation.
#   - Reworks element access to use Puppeteer element handles rather than the
#     Playwright-style Locator.nth() API.
#   - Serializes node introductions so introduction traffic cannot overlap
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
# QS 5.4: Kokoro is lazy-loaded on first Kokoro voice activation and remains resident;
# QS 5.5: bootstraps a Chromium-family browser with QS-owned profile/CDP on startup when needed;
#           local speech blocks until playback ends once the engine is ready.
# Voice-state changes are logged locally. They are NOT broadcast into Mind conversation traffic.
# QS 6.4: native GPT playback wait no longer treats idle "Read aloud" as active speech;
#          dismisses the More Actions menu after launching Read aloud.
# QS 6.6: native voice targeting is bound to the exact response text being spoken;
#          playback completion is response-scoped, and unknown playback state never
#          releases the relay turn.
# QS 6.5: GPT native playback state is bound to the latest response; generic page-wide
#          Stop/Pause/scroll controls can no longer keep the relay waiting forever.



VERSION = "6.6"
VERSION_TAG = f"v{VERSION}"
PROGRAM_NAME = "QuackSink"
RUNTIME_FILE = "qs6_fixed_v6_6.py"
CONFIG_FILE = "qs_config.json"

STARTUP_DIR = os.path.dirname(os.path.abspath(__file__))

CUSTOM_KOKORO_VOICE_FILES = {
    "aisha1": [
        os.path.join(STARTUP_DIR, "voices", "aisha1_001000.json"),
        os.path.join(STARTUP_DIR, "aisha1_001000.json"),
        r"C:\Users\mcozm\projects\drsgem\QuackSink\kokoro_embed_lab\logs\aisha1\aisha1_001000.json",
    ],
}

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

VOICE_NATIVE_NODES = {"GPT", "Gemini", "DeepSeek", "Aisha", "Claude"}
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

KOKORO_CUSTOM_VOICE_IDS = [
    "aisha1",
]

KOKORO_CUSTOM_VOICE_LABELS = {
    "aisha1": "Kokoro - Aisha (extracted 1000-step style)",
}

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

VOICE_SELECTION_OPTIONS = (
    [VOICE_NATIVE_UI]
    + [f"kokoro_{voice_id}" for voice_id in KOKORO_VOICE_IDS]
    + [f"kokoro_{voice_id}" for voice_id in KOKORO_CUSTOM_VOICE_IDS]
)
VOICE_DISPLAY_OPTIONS = (
    ["NATIVE UI"]
    + [f"Kokoro: {v}" for v in KOKORO_VOICE_IDS]
    + [KOKORO_CUSTOM_VOICE_LABELS[v] for v in KOKORO_CUSTOM_VOICE_IDS]
)
VOICE_DISPLAY_TO_SELECTION = {"NATIVE UI": VOICE_NATIVE_UI}
VOICE_SELECTION_TO_DISPLAY = {VOICE_NATIVE_UI: "NATIVE UI"}
for _voice_id in KOKORO_VOICE_IDS:
    _selection = f"kokoro_{_voice_id}"
    _label = f"Kokoro: {_voice_id}"
    VOICE_DISPLAY_TO_SELECTION[_label] = _selection
    VOICE_SELECTION_TO_DISPLAY[_selection] = _label
for _voice_id in KOKORO_CUSTOM_VOICE_IDS:
    _selection = f"kokoro_{_voice_id}"
    _label = KOKORO_CUSTOM_VOICE_LABELS[_voice_id]
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


# -----------------------------------------------------------------------------
# QS 5.6 BROWSER PREFLIGHT / SELF-LAUNCH
# -----------------------------------------------------------------------------
#
# QS owns the browser transport bootstrap now:
#   1. Probe the configured CDP endpoint.
#   2. If a live browser is already there, attach without launching anything.
#   3. Otherwise enumerate installed Chromium-family browsers and their real
#      user-data directories.
#   4. Let the operator choose a browser and profile mode.
#   5. Existing Profile mode launches the browser against its REAL user-data
#      directory so existing login/session state is preserved.
#   6. Fresh QS Profile mode remains available when a browser refuses CDP on
#      its normal profile (a modern Chromium security restriction).
#   7. Verify the CDP endpoint before the normal QS window is created.
#
# The full relay/state-machine/UI machinery below remains unchanged from QS 5.4.
# This layer exists only to ensure that the browser transport exists before the
# main QS UI starts.
# -----------------------------------------------------------------------------

BROWSER_CDP_HOST = "127.0.0.1"
BROWSER_CDP_PORT = 9222
BROWSER_CDP_URL = f"http://{BROWSER_CDP_HOST}:{BROWSER_CDP_PORT}/json/version"
BROWSER_PROFILE_ROOT = os.path.join(STARTUP_DIR, "QS_BROWSER_PROFILES")
BROWSER_BOOTSTRAP_TIMEOUT = 30.0
BROWSER_PROBE_TIMEOUT = 1.25


class BrowserBootstrapCancelled(Exception):
    pass


class BrowserBootstrapError(RuntimeError):
    pass


def _windows_registry_values(root, path):
    """Return string values from a Windows registry key; empty elsewhere."""
    if os.name != "nt":
        return {}
    try:
        import winreg
    except Exception:
        return {}

    values = {}
    try:
        with winreg.OpenKey(root, path) as key:
            index = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                values[str(name)] = str(value)
                index += 1
    except OSError:
        pass
    return values


def _existing_file(path):
    if not path:
        return None
    try:
        candidate = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    except Exception:
        return None
    return os.path.abspath(candidate) if os.path.isfile(candidate) else None


def _browser_slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-") or "Browser"


def _candidate_paths():
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

    paths = []

    def add(name, *items):
        for item in items:
            if item:
                paths.append((name, item))

    add(
        "Google Chrome",
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
    )
    add(
        "Microsoft Edge",
        os.path.join(local, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
    )
    add(
        "Brave",
        os.path.join(local, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(program_files_x86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
    )
    add(
        "Vivaldi",
        os.path.join(local, "Vivaldi", "Application", "vivaldi.exe"),
        os.path.join(program_files, "Vivaldi", "Application", "vivaldi.exe"),
        os.path.join(program_files_x86, "Vivaldi", "Application", "vivaldi.exe"),
    )
    add(
        "Opera",
        os.path.join(local, "Programs", "Opera", "launcher.exe"),
        os.path.join(local, "Programs", "Opera", "opera.exe"),
        os.path.join(roaming, "Opera Software", "Opera Stable", "launcher.exe"),
        os.path.join(program_files, "Opera", "opera.exe"),
        os.path.join(program_files_x86, "Opera", "opera.exe"),
    )
    add(
        "Opera GX",
        os.path.join(local, "Programs", "Opera GX", "launcher.exe"),
        os.path.join(local, "Programs", "Opera GX", "opera.exe"),
        os.path.join(program_files, "Opera GX", "opera.exe"),
        os.path.join(program_files_x86, "Opera GX", "opera.exe"),
    )
    add(
        "Chromium",
        os.path.join(local, "Chromium", "Application", "chrome.exe"),
        os.path.join(program_files, "Chromium", "Application", "chrome.exe"),
        os.path.join(program_files_x86, "Chromium", "Application", "chrome.exe"),
    )

    return paths


def _default_user_data_dir(browser_name):
    """Return the normal Windows user-data root for a Chromium-family browser."""
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")

    roots = {
        "Google Chrome": os.path.join(local, "Google", "Chrome", "User Data"),
        "Microsoft Edge": os.path.join(local, "Microsoft", "Edge", "User Data"),
        "Brave": os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
        "Vivaldi": os.path.join(local, "Vivaldi", "User Data"),
        "Opera": os.path.join(roaming, "Opera Software", "Opera Stable"),
        "Opera GX": os.path.join(roaming, "Opera Software", "Opera GX Stable"),
        "Chromium": os.path.join(local, "Chromium", "User Data"),
    }
    root = roots.get(browser_name)
    if root and os.path.isdir(root):
        return os.path.abspath(root)
    return None


def detect_installed_browsers():
    """Find common Chromium-family browsers and their existing profiles."""
    found = {}

    if os.name == "nt":
        try:
            import winreg
            app_keys = [
                ("Google Chrome", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                ("Google Chrome", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                ("Google Chrome", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                ("Microsoft Edge", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
                ("Microsoft Edge", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
                ("Brave", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"),
                ("Brave", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"),
                ("Vivaldi", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\vivaldi.exe"),
                ("Vivaldi", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\vivaldi.exe"),
            ]
            for name, root, key_path in app_keys:
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        exe = winreg.QueryValue(key, None)
                    exe = _existing_file(exe)
                    if exe:
                        found.setdefault(name, exe)
                except OSError:
                    pass
        except Exception:
            pass

    for name, raw_path in _candidate_paths():
        exe = _existing_file(raw_path)
        if exe:
            found.setdefault(name, exe)

    path_names = {
        "Google Chrome": "chrome.exe",
        "Microsoft Edge": "msedge.exe",
        "Brave": "brave.exe",
        "Vivaldi": "vivaldi.exe",
        "Chromium": "chromium.exe",
    }
    for name, executable in path_names.items():
        if name not in found:
            exe = shutil.which(executable)
            if exe:
                found[name] = os.path.abspath(exe)

    deduped = {}
    seen = set()
    for name, exe in sorted(found.items(), key=lambda item: item[0].lower()):
        norm = os.path.normcase(os.path.abspath(exe))
        if norm in seen:
            continue
        seen.add(norm)
        profile = _default_user_data_dir(name)
        deduped[name] = {
            "executable": exe,
            "user_data_dir": profile,
            "has_existing_profile": bool(profile),
        }

    return deduped


def probe_cdp_endpoint():
    """Return browser version JSON when 9222 is a live Chrome-family CDP endpoint."""
    try:
        with urllib.request.urlopen(BROWSER_CDP_URL, timeout=BROWSER_PROBE_TIMEOUT) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if payload.get("webSocketDebuggerUrl"):
                return payload
    except Exception:
        return None
    return None


def _show_browser_chooser(browsers):
    """Return (name, info, mode) where mode is existing or fresh."""
    if not browsers:
        raise BrowserBootstrapError(
            "No supported Chromium-family browser was found. "
            "Install Chrome, Edge, Brave, Vivaldi, Opera, Opera GX, or Chromium and try again."
        )

    result = {"name": None, "mode": "existing", "cancelled": False}
    chooser = tk.Tk()
    chooser.title(f"QuackSink QS {VERSION} — Browser Setup")
    chooser.geometry("760x455")
    chooser.minsize(760, 455)
    chooser.resizable(False, False)

    frame = ttk.Frame(chooser, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="QuackSink needs a Chrome-based browser for CDP.",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        frame,
        text=(
            "No usable debug endpoint was found on port 9222.\n"
            "Choose a browser. Existing Profile preserves your logged-in browser session."
        ),
        justify="left",
    ).pack(anchor="w", pady=(6, 12))

    browser_names = list(browsers.keys())
    selected = tk.StringVar(value=browser_names[0])
    mode = tk.StringVar(value="existing")
    detail_var = tk.StringVar()

    list_frame = ttk.LabelFrame(frame, text="Browser")
    list_frame.pack(fill="x", expand=False)

    browser_box = tk.Listbox(list_frame, height=min(8, len(browser_names)), exportselection=False)
    browser_box.pack(fill="x", padx=8, pady=8)
    for name in browser_names:
        info = browsers[name]
        suffix = " — existing profile found" if info["has_existing_profile"] else " — no profile detected"
        browser_box.insert(tk.END, name + suffix)
    browser_box.selection_set(0)

    def selected_name():
        idxs = browser_box.curselection()
        return browser_names[idxs[0]] if idxs else browser_names[0]

    def update_detail(*_args):
        name = selected_name()
        selected.set(name)
        info = browsers[name]
        profile = info["user_data_dir"] or "<no existing profile found>"
        detail_var.set(f"Executable: {info['executable']}\nUser-data directory: {profile}")
        if info["has_existing_profile"]:
            existing_radio.config(state="normal")
            if mode.get() not in ("existing", "fresh"):
                mode.set("existing")
        else:
            mode.set("fresh")
            existing_radio.config(state="disabled")

    ttk.Label(frame, textvariable=detail_var, justify="left").pack(anchor="w", pady=(10, 10))

    mode_frame = ttk.LabelFrame(frame, text="Profile")
    mode_frame.pack(fill="x", expand=False, pady=(0, 10))
    existing_radio = ttk.Radiobutton(
        mode_frame,
        text="Use EXISTING browser profile (keep my logins, cookies, tabs, settings, etc.)",
        variable=mode,
        value="existing",
    )
    existing_radio.pack(anchor="w", padx=8, pady=(8, 4))
    ttk.Radiobutton(
        mode_frame,
        text="Use a fresh QS-owned profile (clean browser session)",
        variable=mode,
        value="fresh",
    ).pack(anchor="w", padx=8, pady=(4, 8))

    # Create the widgets referenced by update_detail() before the first call.
    browser_box.bind("<<ListboxSelect>>", update_detail)
    update_detail()

    # Keep the action row immediately beneath the profile choice so it cannot
    # disappear below the visible client area on Windows display scaling.
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill="x", pady=(4, 8))

    def _cancel():
        result["cancelled"] = True
        chooser.destroy()

    def _launch():
        name = selected_name()
        result["name"] = name
        result["mode"] = mode.get() if browsers[name]["has_existing_profile"] else "fresh"
        chooser.destroy()

    ttk.Button(button_frame, text="Launch Browser", command=_launch).pack(side="right", padx=(8, 0))
    ttk.Button(button_frame, text="Cancel", command=_cancel).pack(side="right")

    ttk.Label(
        frame,
        text=(
            "Security note: CDP gives QS full control of the selected browser profile. "
            "Use EXISTING only when you trust this QS instance. Modern Chrome/Edge may reject "
            "CDP on their default profile; QS will report that rather than silently replacing it."
        ),
        justify="left",
        wraplength=700,
    ).pack(anchor="w", pady=(0, 4))

    chooser.protocol("WM_DELETE_WINDOW", _cancel)
    chooser.bind("<Return>", lambda _event: _launch())
    chooser.bind("<Escape>", lambda _event: _cancel())
    chooser.update_idletasks()
    chooser.eval('tk::PlaceWindow . center')
    chooser.lift()
    chooser.focus_force()
    chooser.mainloop()

    if result["cancelled"] or not result["name"]:
        return None
    return result["name"], browsers[result["name"]], result["mode"]


def _launch_browser(browser_name, browser_info, mode):
    """Launch with either the real profile or a clean QS-owned profile."""
    executable = browser_info["executable"]

    if mode == "existing":
        user_data_dir = browser_info["user_data_dir"]
        if not user_data_dir:
            raise BrowserBootstrapError(
                f"No existing user-data directory was found for {browser_name}."
            )
        logger.info("[BROWSER] Using EXISTING profile for %s: %s", browser_name, user_data_dir)
    else:
        os.makedirs(BROWSER_PROFILE_ROOT, exist_ok=True)
        user_data_dir = os.path.join(BROWSER_PROFILE_ROOT, _browser_slug(browser_name))
        os.makedirs(user_data_dir, exist_ok=True)
        logger.info("[BROWSER] Using fresh QS-owned profile for %s: %s", browser_name, user_data_dir)

    args = [
        executable,
        f"--remote-debugging-port={BROWSER_CDP_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
    ]

    logger.info("[BROWSER] Launching %s: %s", browser_name, executable)
    logger.info("[BROWSER] User-data directory: %s", user_data_dir)
    logger.info("[BROWSER] Remote debugging port: %s", BROWSER_CDP_PORT)

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)

    try:
        process = subprocess.Popen(
            args,
            cwd=os.path.dirname(executable) or STARTUP_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception as exc:
        raise BrowserBootstrapError(f"Could not launch {browser_name}: {exc}") from exc

    logger.info("[BROWSER] %s launched (PID %s). Waiting for CDP...", browser_name, process.pid)
    return process, user_data_dir


def ensure_browser_transport():
    """Ensure 9222 is a usable CDP endpoint before the main QS UI is created."""
    existing = probe_cdp_endpoint()
    if existing:
        browser_name = existing.get("Browser", "existing browser")
        logger.info(
            "[BROWSER] Existing CDP browser detected on %s:%s (%s). Attaching without launch.",
            BROWSER_CDP_HOST,
            BROWSER_CDP_PORT,
            browser_name,
        )
        return existing

    logger.info(
        "[BROWSER] No usable CDP endpoint found on %s:%s.",
        BROWSER_CDP_HOST,
        BROWSER_CDP_PORT,
    )
    browsers = detect_installed_browsers()
    logger.info("[BROWSER] Chromium-family browsers detected: %s", ", ".join(browsers) or "none")

    selection = _show_browser_chooser(browsers)
    if not selection:
        raise BrowserBootstrapCancelled("Browser selection cancelled by operator.")

    browser_name, browser_info, mode = selection
    _process, user_data_dir = _launch_browser(browser_name, browser_info, mode)

    deadline = time.time() + BROWSER_BOOTSTRAP_TIMEOUT
    while time.time() < deadline:
        info = probe_cdp_endpoint()
        if info:
            logger.info(
                "[BROWSER] CDP ready on %s:%s (%s).",
                BROWSER_CDP_HOST,
                BROWSER_CDP_PORT,
                info.get("Browser", browser_name),
            )
            logger.info("[BROWSER] Active user-data directory: %s", user_data_dir)
            return info
        time.sleep(0.25)

    if mode == "existing":
        raise BrowserBootstrapError(
            f"{browser_name} launched with its existing profile, but CDP did not become "
            f"available on 127.0.0.1:{BROWSER_CDP_PORT} within {BROWSER_BOOTSTRAP_TIMEOUT:.0f} seconds.\n\n"
            "This can happen with modern Chromium-family browsers that intentionally refuse "
            "remote debugging on their normal/default profile. QS did NOT replace or clone your profile.\n\n"
            "For a browser that enforces that restriction, select a dedicated QS profile or "
            "use a browser build that permits the existing-profile route."
        )

    raise BrowserBootstrapError(
        f"{browser_name} launched with the QS-owned profile, but CDP did not become available "
        f"on 127.0.0.1:{BROWSER_CDP_PORT} within {BROWSER_BOOTSTRAP_TIMEOUT:.0f} seconds."
    )


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




# Retired: the QS preamble is the handshake/channel-opening event.
def _kokoro_custom_voice_id(selection):
    if isinstance(selection, str) and selection.startswith("kokoro_"):
        voice_id = selection[len("kokoro_"):]
        if voice_id in KOKORO_CUSTOM_VOICE_IDS:
            return voice_id
    return None


def _kokoro_load_custom_style(path, torch_module, device):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    style = torch_module.tensor(data["style"], dtype=torch_module.float32, device=device)
    if style.dim() == 1:
        style = style.unsqueeze(0)
    if tuple(style.shape) != (1, 256):
        raise ValueError(
            f"Custom Kokoro style at {path} has shape {tuple(style.shape)}; expected (1, 256)."
        )
    return style


def _kokoro_clean_speech_text(text):
    """Remove emoji/icon glyphs from text before sending it to Kokoro.

    QS keeps the original relay/archive text untouched; this is speech-only
    sanitization. Ordinary punctuation and line breaks are preserved.
    """
    value = str(text or "")
    out = []
    for ch in value:
        cp = ord(ch)
        # Emoji / pictographs / dingbats / misc symbols commonly used as
        # emotes or UI icons. Strip variation selectors, ZWJ, and keycaps.
        if (0x1F000 <= cp <= 0x1FAFF or
            0x1FC00 <= cp <= 0x1FFFF or
            0x2600 <= cp <= 0x27FF or
            0xFE0E <= cp <= 0xFE0F or
            cp in {0x200D, 0x20E3}):
            continue
        out.append(ch)
    cleaned = "".join(out)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


def _kokoro_get_phonemes(pipeline, text):
    """Return ALL Kokoro phoneme chunks for the supplied text."""
    cleaned = _kokoro_clean_speech_text(text)
    phonemes = []
    for result in pipeline(cleaned, voice="af_bella", speed=1.0):
        chunk = getattr(result, "phonemes", None)
        if chunk:
            phonemes.append(chunk)
    return phonemes


def _kokoro_custom_forward(model, phonemes_str, ref_s, speed=1.0):
    """Same differentiable Kokoro forward path used by the working Aisha test."""
    import torch
    import torch.nn.functional as F

    input_ids = list(filter(lambda i: i is not None,
                            map(lambda p: model.vocab.get(p), phonemes_str)))
    input_ids = torch.LongTensor([[0, *input_ids, 0]]).to(model.device)
    n = input_ids.shape[1]
    input_lengths = torch.full((1,), n, device=model.device, dtype=torch.long)
    text_mask = torch.arange(n, device=model.device).unsqueeze(0)
    text_mask = torch.gt(text_mask + 1, input_lengths.unsqueeze(1))

    bert_dur = model.bert(input_ids, attention_mask=(~text_mask).int())
    d_en = model.bert_encoder(bert_dur).transpose(-1, -2)

    s = ref_s[:, 128:]
    d = model.predictor.text_encoder(d_en, s, input_lengths, text_mask)
    x, _ = model.predictor.lstm(d)
    dur = model.predictor.duration_proj(x)
    dur = torch.sigmoid(dur).sum(axis=-1) / speed
    pred_dur = torch.round(dur).clamp(min=1).long().squeeze()

    indices = torch.repeat_interleave(
        torch.arange(n, device=model.device), pred_dur
    )
    pred_aln = torch.zeros((n, indices.shape[0]), device=model.device)
    pred_aln[indices, torch.arange(indices.shape[0], device=model.device)] = 1
    pred_aln = pred_aln.unsqueeze(0)

    en = d.transpose(-1, -2) @ pred_aln
    F0_pred, N_pred = model.predictor.F0Ntrain(en, s)

    t_en = model.text_encoder(input_ids, input_lengths, text_mask)
    asr = t_en @ pred_aln
    audio = model.decoder(asr, F0_pred, N_pred, ref_s[:, :128]).squeeze()
    return audio


class KokoroVoiceEngine:
    """Lazy local Kokoro voice engine for QS 5.4.

    QS startup does not import or initialize Kokoro. The engine is initialized
    when a node first activates a Kokoro voice, and then remains resident for
    the rest of the session. Pipeline objects are cached per language code.
    """

    def __init__(self, preload_voice_selections=None):
        # ``preload_voice_selections`` is retained for API compatibility with
        # the QS 5.0-5.3 controller, but lazy loading deliberately ignores it
        # until a Kokoro voice is actually activated.
        self.available = False
        self.device = "cpu"
        self._pipelines = {}
        self._pipeline_lock = threading.RLock()
        self._init_lock = threading.Lock()
        self._init_event = threading.Event()
        self._initializing = False
        self._init_error = None
        self._torch = None
        self._np = None
        self._sd = None
        self._KPipeline = None
        self._custom_styles = {}
        self._custom_voice_paths = {}

        logger.info("[VOICE] Kokoro engine lazy-load armed; waiting for first Kokoro voice activation.")

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

    def _initialize(self, selection=None):
        logger.info("[VOICE] First Kokoro voice activation: loading local Kokoro engine...")
        try:
            import numpy as np
            import sounddevice as sd
            import torch
            from kokoro import KPipeline

            self._np = np
            self._sd = sd
            self._torch = torch
            self._KPipeline = KPipeline
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            # Load the language needed by the first requested Kokoro voice.
            # English is currently the only exposed language family, but this
            # remains selection-aware for future multilingual voice lists.
            lang = self._lang_for_selection(selection) or "a"
            self._get_pipeline(lang)
            self.available = True
            self._init_error = None
            logger.info(
                "[VOICE] Kokoro ready. Device=%s | pipelines=%s",
                self.device,
                sorted(self._pipelines.keys())
            )
        except Exception as exc:
            self.available = False
            self._init_error = exc
            logger.exception("[VOICE] Kokoro initialization failed: %s", exc)

    def start_async(self, selection=None):
        """Begin Kokoro initialization without blocking the Tkinter UI."""
        with self._init_lock:
            if self.available or self._initializing:
                return
            self._initializing = True
            self._init_event.clear()

        def worker():
            try:
                self._initialize(selection)
            finally:
                with self._init_lock:
                    self._initializing = False
                    self._init_event.set()

        threading.Thread(target=worker, daemon=True, name="QS-Kokoro-Init").start()

    def ensure_started(self, selection=None):
        """Ensure Kokoro is ready, waiting if a background startup is underway."""
        with self._init_lock:
            if self.available:
                return True
            initializing = self._initializing

        if not initializing:
            self.start_async(selection)

        self._init_event.wait()
        if not self.available:
            reason = self._init_error or RuntimeError("Unknown Kokoro initialization failure.")
            raise RuntimeError(f"Kokoro engine is not available: {reason}")
        return True

    def _get_pipeline(self, lang):
        with self._pipeline_lock:
            if lang in self._pipelines:
                return self._pipelines[lang]
            logger.info("[VOICE] Kokoro loading language pipeline '%s' on %s...", lang, self.device)
            pipeline = self._KPipeline(lang_code=lang, device=self.device)
            self._pipelines[lang] = pipeline
            logger.info("[VOICE] Kokoro language pipeline '%s' ready.", lang)
            return pipeline

    def _resolve_custom_voice_path(self, voice_id):
        candidates = CUSTOM_KOKORO_VOICE_FILES.get(voice_id, [])
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        raise FileNotFoundError(
            f"Custom Kokoro voice asset for '{voice_id}' was not found. "
            f"Expected one of: {candidates}"
        )

    def _load_custom_style(self, voice_id):
        if voice_id in self._custom_styles:
            return self._custom_styles[voice_id]
        path = self._resolve_custom_voice_path(voice_id)
        style = _kokoro_load_custom_style(path, self._torch, self._get_pipeline("a").model.device)
        self._custom_styles[voice_id] = style
        self._custom_voice_paths[voice_id] = path
        logger.info("[VOICE] Loaded custom Kokoro style '%s' from %s", voice_id, path)
        return style

    def _prepare_custom_inference(self):
        pipeline = self._get_pipeline("a")
        model = pipeline.model
        for _name_mod, module in model.named_modules():
            if isinstance(module, (self._torch.nn.LSTM, self._torch.nn.GRU, self._torch.nn.RNN)):
                module.train()
        return pipeline, model

    def _speak_custom(self, text, voice_id):
        self.ensure_started(f"kokoro_{voice_id}")
        import time as _time
        t0 = _time.perf_counter()
        pipeline, model = self._prepare_custom_inference()
        style = self._load_custom_style(voice_id)
        t1 = _time.perf_counter()

        phoneme_chunks = _kokoro_get_phonemes(pipeline, str(text).strip())
        if not phoneme_chunks:
            raise RuntimeError("Kokoro produced no phonemes for custom voice synthesis.")

        audio_chunks = []
        with self._torch.no_grad():
            for phonemes in phoneme_chunks:
                audio = _kokoro_custom_forward(model, phonemes, style, 1.0)
                audio_chunks.append(audio.detach().float().cpu().numpy())

        audio_data = self._np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]
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
            "chunks": len(phoneme_chunks),
            "custom_style_path": self._custom_voice_paths.get(voice_id, ""),
        }

    def speak(self, text, selection):
        """Synthesize and block until the requested audio has finished playing."""
        voice_id = self._voice_id(selection)
        if not voice_id:
            raise ValueError(f"Invalid Kokoro voice selection: {selection!r}")
        if not str(text).strip():
            raise ValueError("Cannot speak empty response text.")

        custom_voice_id = _kokoro_custom_voice_id(selection)
        if custom_voice_id:
            return self._speak_custom(text, custom_voice_id)

        if voice_id not in KOKORO_VOICE_IDS:
            raise ValueError(f"Unknown Kokoro voice: {voice_id}")

        # A direct SPEAK/title audition is also a legitimate first activation.
        self.ensure_started(selection)

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
            "Claude": ("textarea, [contenteditable='true']", ".font-claude-response, [data-testid='assistant-message'], [data-testid='ai-message'], .font-claude-message, [data-testid='message-assistant'], .assistant-message, .font-claude-response-body"),
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
        """Classify by the actual URL host, never by arbitrary URL substrings.

        This is important because query strings can contain another site's domain,
        e.g. a GitHub URL with ``?utm_source=chatgpt.com``. The old substring
        matcher therefore misclassified GitHub as GPT.
        """
        mappings = [
            ("chat.mistral.ai", "Mistral"),
            ("chat.z.ai", "GLM"),
            ("qwenlm.ai", "Qwen"),
            ("perplexity.ai", "Perplexity"),
            ("kimi.com", "Kimi"),
            ("gemini.google.com", "Gemini"),
            ("chat.deepseek.com", "DeepSeek"),
            ("deepseek.com", "DeepSeek"),
            ("aisha.ai", "Aisha"),
            ("claude.ai", "Claude"),
            ("chatgpt.com", "GPT"),
            ("grok.com", "Grok"),
        ]

        try:
            parsed = urllib.parse.urlparse(url)
            hostname = (parsed.hostname or "").rstrip(".").lower()
            port = parsed.port
            host_with_port = f"{hostname}:{port}" if port else hostname

            if host_with_port == "localhost:8080":
                return "Chron"

            for domain, name in mappings:
                if hostname == domain or hostname.endswith("." + domain):
                    return name

            if hostname:
                parts = hostname.split(".")
                if len(parts) >= 2:
                    return parts[0].capitalize()
                return hostname.capitalize()
        except Exception:
            pass

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
        """QS 6.0 two-pane UI.

        Control pane: everything that used to live above BROADCAST MESSAGE.
        Comms pane: BROADCAST MESSAGE and everything below it.
        """
        self.pane = tk.PanedWindow(
            self.root,
            orient=tk.VERTICAL,
            bg="#121212",
            sashwidth=8,
            sashrelief=tk.RAISED,
            bd=0,
            relief=tk.FLAT
        )
        self.pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.control_frame = tk.Frame(self.pane, bg="#121212")
        self.comms_frame = tk.Frame(self.pane, bg="#121212")

        self.pane.add(self.control_frame, minsize=340, stretch="never")
        self.pane.add(self.comms_frame, minsize=300, stretch="always")

        # ------------------------------------------------------------------
        # CONTROL PANE
        # ------------------------------------------------------------------
        tk.Label(
            self.control_frame,
            text=f"CONTROL PANE  -  QUACKSINK MULTI-MIND RELAY CORE - QS {VERSION}",
            font=("Arial", 15, "bold"), bg="#121212", fg="#00FFCC"
        ).pack(pady=(4, 0))

        title_frame = tk.Frame(self.control_frame, bg="#121212")
        title_frame.pack(pady=(3, 2), fill=tk.X, padx=12)

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

        title_voice_frame = tk.Frame(self.control_frame, bg="#121212")
        title_voice_frame.pack(pady=(0, 3), fill=tk.X, padx=12)

        tk.Label(
            title_voice_frame, text="VOICE TEST:", font=("Arial", 11, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.title_voice_var = tk.StringVar(value="kokoro_af_heart")
        self.title_voice_combo = ttk.Combobox(
            title_voice_frame,
            textvariable=self.title_voice_var,
            values=[
                selection
                for selection in VOICE_SELECTION_OPTIONS
                if selection != VOICE_NATIVE_UI
            ],
            state="readonly",
            width=28,
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
            self.control_frame,
            text="ACTIVE NODES: (discovered from open tabs)",
            font=("Arial", 13, "bold"), bg="#121212", fg="#ffffff"
        ).pack(pady=(5, 3))

        self.nodes_frame = tk.Frame(self.control_frame, bg="#121212")
        self.nodes_frame.pack(pady=5)
        self._render_nodes()

        order_frame = tk.Frame(self.control_frame, bg="#121212")
        order_frame.pack(fill=tk.X, padx=12, pady=(2, 3))

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
        self._render_send_order()

        ctrl_bar = tk.Frame(self.control_frame, bg="#121212")
        ctrl_bar.pack(pady=(10, 0))

        tk.Label(
            ctrl_bar, text="Human Handle:", font=("Arial", 14, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.handle_entry = tk.Entry(
            ctrl_bar, font=("Arial", 14, "bold"),
            bg="#1e1e1e", fg="#ffffff", width=15,
            insertbackground="white"
        )
        self.handle_entry.insert(0, self.human_handle)
        self.handle_entry.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            ctrl_bar, text="Save Handle", command=self._save_handle,
            bg="#00AA55", fg="white", font=("Arial", 11, "bold"),
            height=1, padx=8
        ).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(
            ctrl_bar, text="Font:", font=("Arial", 14, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 5))

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

        tk.Button(
            ctrl_bar, text="REFRESH", command=self.controller.scan,
            bg="#FF8800", fg="black", font=("Arial", 11, "bold"),
            height=1, padx=8
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            ctrl_bar, text="ADD NODE (disabled)", command=self._manual_add,
            bg="#444444", fg="#666666", font=("Arial", 11, "bold"),
            height=1, padx=8, state=tk.DISABLED
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            ctrl_bar, text="CLEAR", command=self.controller.clear_all,
            bg="#FF4444", fg="white", font=("Arial", 11, "bold"),
            height=1, padx=8
        ).pack(side=tk.LEFT, padx=5)

        archive_frame = tk.Frame(self.control_frame, bg="#121212")
        archive_frame.pack(pady=(12, 3), fill=tk.X, padx=12)

        archive_label_row = tk.Frame(archive_frame, bg="#121212")
        archive_label_row.pack(fill=tk.X)
        tk.Label(
            archive_label_row, text="ARCHIVE:", font=("Arial", 12, "bold"),
            bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT, padx=(0, 8))

        archive_style = ttk.Style(self.root)
        try:
            archive_style.configure("QSArchive.TCombobox", font=("Arial", 18, "bold"))
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

        # ------------------------------------------------------------------
        # COMMS PANE
        # ------------------------------------------------------------------
        comms_header = tk.Frame(self.comms_frame, bg="#121212")
        comms_header.pack(fill=tk.X, padx=12, pady=(4, 0))

        tk.Label(
            comms_header, text="COMMS PANE",
            font=("Arial", 14, "bold"), bg="#121212", fg="#00FFCC"
        ).pack(side=tk.LEFT)
        tk.Label(
            comms_header, text="broadcast + relay display",
            font=("Arial", 10), bg="#121212", fg="#777777"
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.comms_max_btn = tk.Button(
            comms_header, text="MAX COMMS", command=self._toggle_comms_maximize,
            bg="#555555", fg="white", font=("Arial", 10, "bold"),
            height=1, padx=10
        )
        self.comms_max_btn.pack(side=tk.RIGHT)

        tk.Label(
            self.comms_frame, text="BROADCAST MESSAGE:",
            font=("Arial", 14, "bold"), bg="#121212", fg="#ffffff"
        ).pack(pady=(6, 5))

        self.text_input = tk.Text(
            self.comms_frame, height=3, width=85,
            font=("Consolas", 18), bg="#1e1e1e", fg="#ffffff",
            insertbackground="white", wrap=tk.WORD
        )
        self.text_input.pack(fill=tk.X, padx=20, pady=5)
        self.text_input.bind("<Return>", self._on_input_enter)
        self.text_input.bind("<KP_Enter>", self._on_input_enter)

        btn_frame = tk.Frame(self.comms_frame, bg="#121212")
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

        tk.Label(
            self.comms_frame, text="RELAY DISPLAY:",
            font=("Arial", 14, "bold"), bg="#121212", fg="#ffffff"
        ).pack(pady=(5, 3))

        log_frame = tk.Frame(self.comms_frame, bg="#121212")
        log_frame.pack(pady=5, fill=tk.BOTH, expand=True, padx=20)

        self.log_box = tk.Text(
            log_frame, height=28, font=("Consolas", 16),
            bg="#1e1e1e", fg="#ffffff", insertbackground="white",
            wrap=tk.WORD
        )
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.root.update_idletasks()
        try:
            self.pane.sash_place(0, 0, 520)
        except Exception:
            pass
        self._comms_maximized = False

    def _toggle_comms_maximize(self):
        if not getattr(self, "_comms_maximized", False):
            try:
                self.pane.forget(self.control_frame)
                self._comms_maximized = True
                self.comms_max_btn.config(text="RESTORE CONTROL")
                self.log("[UI] COMMS pane maximized.", is_system=True)
            except Exception as exc:
                self.log(f"[UI] Could not maximize COMMS pane: {exc}", is_system=True)
            return

        try:
            self.pane.add(self.control_frame, minsize=340, stretch="never", before=self.comms_frame)
            self._comms_maximized = False
            self.comms_max_btn.config(text="MAX COMMS")
            self.root.update_idletasks()
            try:
                self.pane.sash_place(0, 0, 520)
            except Exception:
                pass
            self.log("[UI] Control pane restored.", is_system=True)
        except Exception as exc:
            self.log(f"[UI] Could not restore CONTROL pane: {exc}", is_system=True)

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

        self.kokoro = KokoroVoiceEngine()

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

                # Discovery identity is host-based. Never let query-string text
                # or tracking parameters manufacture an LLM identity.
                if name == "GPT":
                    try:
                        host = (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
                    except Exception:
                        host = ""
                    if host != "chatgpt.com" and not host.endswith(".chatgpt.com"):
                        self.ui.log(
                            f"[DISCOVERY] Rejecting GPT classification for non-ChatGPT host: {host or url}",
                            is_system=True
                        )
                        name = SelectorDetector.generate_name(url)

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
        if enabled and isinstance(node.voice_selection, str) and node.voice_selection.startswith("kokoro_"):
            self.ui.log(
                f"[VOICE] {node.name}: first Kokoro activation; starting voice engine in background.",
                is_system=True
            )
            self.kokoro.start_async(node.voice_selection)
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
            if isinstance(selection, str) and selection.startswith("kokoro_"):
                self.ui.log(
                    f"[VOICE] {node.name}: Kokoro selected while voice is ON; starting voice engine in background.",
                    is_system=True
                )
                self.kokoro.start_async(selection)
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
        if enabled:
            for name, node in self.nodes.items():
                if node.voice_enabled and isinstance(node.voice_selection, str) and node.voice_selection.startswith("kokoro_"):
                    self.ui.log(
                        f"[VOICE] Global activation: starting shared Kokoro engine for {name} in background.",
                        is_system=True
                    )
                    self.kokoro.start_async(node.voice_selection)
                    break
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
        """Compatibility shim: voice-state notices are local QS logs only.

        Voice configuration is control-plane state. Never inject it into Mind
        conversation traffic or wait for an acknowledgement from a node.
        """
        return None

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


    async def _clear_handshake_turn(self, page, node, handshake_prompt, handshake_frame):
        """Remove only the just-completed handshake exchange from the visible node UI.

        This is a UI cleanup operation only. It does not alter archive/log state and
        does not delete ordinary conversation history. We identify the exact user
        handshake prompt and the exact assistant 🟩...🔚 response, then remove the
        smallest matching message nodes from the live DOM.
        """
        try:
            safe_prompt = json.dumps(str(handshake_prompt).strip())
            safe_frame = json.dumps(str(handshake_frame).strip())
            result = await page.evaluate(rf"""
                (() => {{
                    const norm = (v) => String(v || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\r\n?/g, '\n')
                        .replace(/\s+/g, ' ')
                        .trim();
                    const prompt = norm({safe_prompt});
                    const frame = norm({safe_frame});
                    const removed = [];

                    const visible = (el) => {{
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden' &&
                               r.width > 0 && r.height > 0;
                    }};

                    const candidates = Array.from(document.querySelectorAll(
                        '[data-message-author-role], article, [data-message-id], ' +
                        'div[class*=\"message\" i], div[class*=\"chat-message\" i]'
                    )).filter(visible);

                    const exactOrContained = (el, needle) => {{
                        if (!needle) return false;
                        const text = norm(el.innerText || el.textContent || '');
                        return text === needle || text.includes(needle);
                    }};

                    // Remove exact assistant handshake response first.
                    for (const el of candidates.slice().reverse()) {{
                        if (exactOrContained(el, frame) && frame.includes('🟩') && frame.includes('🔚')) {{
                            el.remove();
                            removed.push('assistant-handshake');
                            break;
                        }}
                    }}

                    // Remove the corresponding user handshake prompt if present.
                    for (const el of candidates.slice().reverse()) {{
                        if (exactOrContained(el, prompt) && prompt.includes('QuackSink HANDSHAKE')) {{
                            el.remove();
                            removed.push('user-handshake');
                            break;
                        }}
                    }}

                    return removed;
                }})()
            """)
            if result:
                self.ui.log(
                    f"[HANDSHAKE] {node.name}: removed handshake turn from node UI ({', '.join(result)}).",
                    is_system=True
                )
            else:
                self.ui.log(
                    f"[HANDSHAKE] {node.name}: handshake succeeded; no matching UI turn found to remove.",
                    is_system=True
                )
            return True
        except Exception as exc:
            self.ui.log(
                f"[HANDSHAKE] {node.name}: UI cleanup failed: {type(exc).__name__}: {exc}",
                is_system=True
            )
            return False


    async def _do_handshake(self, node):
        """Open a node by sending the Library preamble and accepting its reply.

        QS6 protocol simplification: the preamble itself is the introduction/handshake.
        If the node accepts the preamble and produces a fresh assistant response,
        communications are proven. That first response becomes the node's first
        conversational message; no second handshake prompt or token framing is required.
        """
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
                f"[INTRO] {node.name}: preamble sent; waiting for the first fresh response.",
                is_system=True
            )

            responded = await self._wait_for_response(
                page, node, timeout=90, is_handshake=False
            )
            if not responded:
                node.introduction_failed()
                self.ui.log(
                    f"[INTRO] {node.name}: no fresh response to Library preamble.",
                    is_system=True
                )
                return

            raw = await self._get_response(page, node, is_handshake=False)
            clean, dropped = self._parse_response(raw, is_handshake=False)
            if dropped:
                node.introduction_failed()
                self.ui.log(
                    f"[INTRO] {node.name}: preamble response requested dropout.",
                    is_system=True
                )
                return
            if not clean:
                node.introduction_failed()
                self.ui.log(
                    f"[INTRO] {node.name}: fresh response was empty.",
                    is_system=True
                )
                return

            # The first response is the proof-of-life / channel-open event.
            # Preserve the existing lifecycle so the rest of QS6 remains unchanged.
            node.introduction_success()
            node.handshake_start()
            node.handshake_success()

            self.ui.log(
                f"[INTRO] {node.name}: preamble answered; communications confirmed.",
                is_system=True
            )

            announcement = f"{node.icon} {node.name} - {clean}"
            self.ui.log(f"\n[ANNOUNCE] {announcement}\n", is_system=False)

            # The first response enters the ordinary relay flow immediately.
            # Existing active nodes receive it just like any later relay response.
            for target in self.nodes.values():
                if target.is_active() and target != node:
                    target.stack.append(announcement)

            return

        except Exception as exc:
            node.handshake_failed()
            self.ui.log(
                f"[ERROR] Introduction with {node.name}: {exc}",
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

    async def _dismiss_gpt_more_actions_menu(self, page):
        """Dismiss ChatGPT's More Actions menu after Read aloud is launched.

        The native Read aloud action can start successfully while the originating
        More Actions menu remains visually open when triggered through DOM click.
        Escape is the least invasive menu-dismissal path and does not change the
        selected voice or conversation content.
        """
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.10)
            self.ui.log("[VOICE] GPT More Actions menu dismissed after Read aloud launch.", is_system=True)
        except Exception as exc:
            self.ui.log(f"[VOICE] GPT More Actions menu dismiss failed: {exc}", is_system=True)

    async def _click_gpt_read_aloud(self, page, response_text=None):
        """GPT: click Read aloud on the exact response QS just captured."""
        try:
            safe_response = json.dumps(self._canonical_message_text(response_text or ""))
            result = await page.evaluate(rf"""
                (() => {{
                    const targetText = {safe_response};
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const visible = (el) => {{
                        if (!el) return false;
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    }};
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);
                    const isMore = (el) => {{
                        if (!visible(el)) return false;
                        const aria = clean(el.getAttribute('aria-label') || '');
                        const title = clean(el.getAttribute('title') || '');
                        const text = clean(el.textContent || '');
                        const testid = clean(el.getAttribute('data-testid') || '');
                        return /more\\s+actions?/i.test(aria) ||
                               /more\\s+actions?/i.test(title) ||
                               /^(?:\\.\\.\\.|…|⋯)$/.test(text) ||
                               /more[-_\\s]+actions?/i.test(testid);
                    }};

                    const assistants = Array.from(
                        document.querySelectorAll('[data-message-author-role="assistant"], article')
                    ).filter(visible);

                    const wanted = canonical(targetText);
                    let exact = wanted
                        ? assistants.filter((el) => canonical(el.innerText || el.textContent || '') === wanted)
                        : [];
                    if (!exact.length && wanted) {{
                        exact = assistants.filter((el) => canonical(el.innerText || el.textContent || '').includes(wanted));
                    }}

                    let latest = exact.length ? exact[exact.length - 1] : null;
                    if (!latest) latest = assistants.length ? assistants[assistants.length - 1] : null;
                    if (!latest) return {{ok:false, stage:'latest_response', reason:'GPT response container not found.'}};

                    let responseScope = latest.closest('[data-message-author-role="assistant"]');
                    if (!responseScope) responseScope = latest.closest('article');
                    if (!responseScope) responseScope = latest;

                    let scope = responseScope;
                    let moreTarget = null;
                    for (let depth = 0; depth <= 8 && scope; depth += 1) {{
                        const candidates = Array.from(
                            scope.querySelectorAll('button,[role="button"],[data-testid]')
                        ).filter(isMore);
                        if (candidates.length) {{
                            moreTarget = candidates[candidates.length - 1];
                            break;
                        }}
                        scope = scope.parentElement;
                    }}

                    if (!moreTarget) {{
                        return {{ok:false, stage:'more_actions', reason:'GPT More Actions control not found for captured response.'}};
                    }}

                    moreTarget.click();
                    return {{ok:true, responseMatched:Boolean(exact.length)}};
                }})()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] GPT More Actions probe failed: {exc}", is_system=True)
            return False

        if not result or not result.get('ok'):
            self.ui.log(
                f"[VOICE] GPT More Actions unavailable: "
                f"{result.get('reason', 'unknown') if result else 'no result'}",
                is_system=True
            )
            return False

        self.ui.log(
            "[VOICE] GPT More Actions opened "
            f"({'exact response' if result.get('responseMatched') else 'latest-response fallback'}).",
            is_system=True
        )

        deadline = asyncio.get_event_loop().time() + 3.0
        while asyncio.get_event_loop().time() < deadline:
            try:
                menu_item = await page.evaluate(r"""
                    (() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const style = getComputedStyle(el);
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
                        const menus = Array.from(document.querySelectorAll(
                            '[role="menu"], [data-radix-menu-content], [data-state="open"]'
                        )).filter(visible);
                        for (const menu of menus.reverse()) {
                            const match = Array.from(menu.querySelectorAll(
                                '[role="menuitem"],button,[role="button"],[data-testid]'
                            )).find(exact);
                            if (match) {
                                match.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                """)
            except Exception as exc:
                self.ui.log(f"[VOICE] GPT Read aloud menu probe failed: {exc}", is_system=True)
                return False

            if menu_item:
                self.ui.log("[VOICE] GPT Read aloud menu item clicked.", is_system=True)
                await self._dismiss_gpt_more_actions_menu(page)
                return True
            await asyncio.sleep(0.15)

        await self._dismiss_gpt_more_actions_menu(page)
        self.ui.log("[VOICE] GPT Read aloud menu item unavailable after render wait.", is_system=True)
        return False


    async def _click_claude_read_aloud(self, page, node, response_text=None):
        """Claude: click Read Aloud on the exact response QS just captured."""
        try:
            target_text = self._canonical_message_text(response_text or "")
            safe_response = json.dumps(target_text)
            safe_selector = json.dumps(
                node.output_selector or
                ".font-claude-response, [data-testid='assistant-message'], "
                "[data-testid='ai-message'], .font-claude-message, "
                "[data-testid='message-assistant'], .assistant-message, "
                ".font-claude-response-body"
            )
            result = await page.evaluate(rf"""
                (() => {{
                    const targetText = {safe_response};
                    const configured = {safe_selector};
                    const visible = (el) => {{
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                    }};
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const canonical = (value) => clean(value).normalize('NFKC').toLocaleLowerCase();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);
                    const isReadAloud = (el) => visible(el) && labels(el).some((value) =>
                        /^read\\s+aloud$/i.test(value) ||
                        /^read[-_\\s]+aloud(?:[-_\\s]+button)?$/i.test(value)
                    );

                    const messages = [];
                    const seen = new Set();
                    const addMessage = (el, priority) => {{
                        if (!el || seen.has(el) || !visible(el)) return;
                        const t = clean(el.innerText || el.textContent || '');
                        if (!t) return;
                        seen.add(el);
                        messages.push({{el, text:t, priority}});
                    }};

                    try {{ document.querySelectorAll(configured).forEach((el) => addMessage(el, 100)); }} catch (_) {{}}
                    for (const sel of [
                        '[data-testid*="assistant-message"]',
                        '[data-testid*="message-assistant"]',
                        '[data-testid*="response"]',
                        '.font-claude-response',
                        '.font-claude-response-body',
                        '.font-claude-message',
                        '.assistant-message',
                        '[role="article"]',
                        'article'
                    ]) {{
                        try {{ document.querySelectorAll(sel).forEach((el) => addMessage(el, 50)); }} catch (_) {{}}
                    }}

                    const wanted = canonical(targetText);
                    let candidates = wanted
                        ? messages.filter((item) => canonical(item.text) === wanted)
                        : [];
                    if (!candidates.length && wanted) {{
                        candidates = messages.filter((item) => canonical(item.text).includes(wanted));
                    }}
                    if (!candidates.length) candidates = messages;
                    if (!candidates.length) {{
                        return {{ok:false, stage:'latest_response', reason:'No visible Claude response-like nodes found.'}};
                    }}

                    candidates.sort((a, b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return b.priority - a.priority;
                    }});
                    const latest = candidates[candidates.length - 1].el;

                    let scope = latest;
                    let target = null;
                    for (let depth = 0; depth <= 8 && scope; depth += 1) {{
                        const matches = Array.from(scope.querySelectorAll(
                            'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip]'
                        )).filter(isReadAloud);
                        if (matches.length) {{
                            target = matches[matches.length - 1];
                            break;
                        }}
                        scope = scope.parentElement;
                    }}

                    if (!target) {{
                        return {{ok:false, stage:'read_aloud', reason:'Exact Claude Read Aloud control not found for captured response.'}};
                    }}

                    target.click();
                    return {{
                        ok:true,
                        responseMatched:Boolean(
                            wanted && candidates.some((item) => canonical(item.text) === wanted)
                        ),
                        label:labels(target).join(' | ')
                    }};
                }})()
            """)
        except Exception as exc:
            self.ui.log(f"[VOICE] Claude Read Aloud probe failed: {exc}", is_system=True)
            return False

        if not result or not result.get('ok'):
            self.ui.log(
                f"[VOICE] Claude Read Aloud unavailable: "
                f"{result.get('reason', 'unknown') if result else 'no result'}",
                is_system=True
            )
            return False

        self.ui.log(
            f"[VOICE] Claude Read Aloud clicked "
            f"(response={'exact' if result.get('responseMatched') else 'fallback'}, "
            f"label={result.get('label')!r}).",
            is_system=True
        )
        return True


    async def _gpt_voice_state(self, page, response_text=None):
        """Return GPT native Read Aloud state for the exact response being spoken."""
        try:
            safe_response = json.dumps(self._canonical_message_text(response_text or ""))
            result = await page.evaluate(rf"""
                (() => {{
                    const targetText = {safe_response};
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\\u00a0/g, ' ')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const visible = (el) => {{
                        if (!el) return false;
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               style.opacity !== '0' && rect.width > 0 && rect.height > 0;
                    }};
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);

                    const assistants = Array.from(
                        document.querySelectorAll('[data-message-author-role="assistant"], article')
                    ).filter(visible);

                    const wanted = canonical(targetText);
                    let matches = wanted
                        ? assistants.filter((el) => canonical(el.innerText || el.textContent || '') === wanted)
                        : [];
                    if (!matches.length && wanted) {{
                        matches = assistants.filter((el) => canonical(el.innerText || el.textContent || '').includes(wanted));
                    }}

                    let latest = matches.length ? matches[matches.length - 1] : null;
                    if (!latest) latest = assistants.length ? assistants[assistants.length - 1] : null;
                    if (!latest) return {{state:'unknown', reason:'GPT response container not found'}};

                    let responseScope = latest.closest('[data-message-author-role="assistant"]');
                    if (!responseScope) responseScope = latest.closest('article');
                    if (!responseScope) responseScope = latest;

                    const controls = [];
                    let scope = responseScope;
                    for (let i = 0; i < 8 && scope; i += 1) {{
                        for (const el of scope.querySelectorAll(
                            'button,[role="button"],[data-testid],[aria-label],[title]'
                        )) {{
                            if (!visible(el)) continue;
                            if (el.closest('[role="menu"],[role="menuitem"],nav,header')) continue;
                            if (!controls.includes(el)) controls.push(el);
                        }}
                        scope = scope.parentElement;
                    }}

                    const active = controls.find((el) => labels(el).some((value) =>
                        /^(?:pause|stop)(?:\\s+(?:reading|reading\\s+aloud|speech|speaking|playback))?$/i.test(value) ||
                        /^(?:reading\\s+aloud|speaking)$/i.test(value)
                    ));
                    if (active) return {{
                        state:'active',
                        label:labels(active).join(' | '),
                        responseMatched:Boolean(matches.length)
                    }};

                    const idle = controls.find((el) => labels(el).some((value) =>
                        /^read\\s+aloud$/i.test(value) ||
                        /^read[-_\\s]+aloud(?:[-_\\s]+button)?$/i.test(value)
                    ));
                    if (idle) return {{
                        state:'idle',
                        label:labels(idle).join(' | '),
                        responseMatched:Boolean(matches.length)
                    }};

                    return {{
                        state:'unknown',
                        reason:'No response-scoped GPT Read Aloud state detected',
                        responseMatched:Boolean(matches.length)
                    }};
                }})()
            """)
            return result or {'state':'unknown'}
        except Exception as exc:
            return {'state':'unknown', 'reason':f'{type(exc).__name__}: {exc}'}



    async def _claude_voice_state(self, page, node, response_text=None):
        """Return Claude native Read Aloud state for the exact response being spoken."""
        try:
            target_text = self._canonical_message_text(response_text or "")
            safe_response = json.dumps(target_text)
            safe_selector = json.dumps(
                node.output_selector or
                ".font-claude-response, [data-testid='assistant-message'], "
                "[data-testid='ai-message'], .font-claude-message, "
                "[data-testid='message-assistant'], .assistant-message, "
                ".font-claude-response-body"
            )
            result = await page.evaluate(rf"""
                (() => {{
                    const targetText = {safe_response};
                    const configured = {safe_selector};
                    const visible = (el) => {{
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                    }};
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const canonical = (value) => clean(value).normalize('NFKC').toLocaleLowerCase();
                    const labels = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-tooltip') || '',
                        el.getAttribute('data-tip') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].map(clean).filter(Boolean);
                    const isRead = (el) => visible(el) && labels(el).some((v) =>
                        /^read\\s+aloud$/i.test(v) || /^read[-_\\s]+aloud(?:[-_\\s]+button)?$/i.test(v)
                    );
                    const isActive = (el) => visible(el) && labels(el).some((v) =>
                        /^(?:pause|stop)(?:\\s+(?:reading|reading\\s+aloud|speech|speaking|playback))?$/i.test(v) ||
                        /^(?:reading\\s+aloud|speaking)$/i.test(v)
                    );

                    const messages = [];
                    const seen = new Set();
                    const add = (el, priority) => {{
                        if (!el || seen.has(el) || !visible(el)) return;
                        const t = clean(el.innerText || el.textContent || '');
                        if (!t) return;
                        seen.add(el);
                        messages.push({{el,text:t,priority}});
                    }};
                    try {{ document.querySelectorAll(configured).forEach((el) => add(el,100)); }} catch (_) {{}}
                    for (const sel of [
                        '[data-testid*="assistant-message"]',
                        '[data-testid*="message-assistant"]',
                        '[data-testid*="response"]',
                        '.font-claude-response',
                        '.font-claude-response-body',
                        '.font-claude-message',
                        '.assistant-message',
                        '[role="article"]',
                        'article'
                    ]) {{
                        try {{ document.querySelectorAll(sel).forEach((el) => add(el,50)); }} catch (_) {{}}
                    }}

                    const wanted = canonical(targetText);
                    let candidates = wanted
                        ? messages.filter((m) => canonical(m.text) === wanted)
                        : [];
                    if (!candidates.length && wanted) {{
                        candidates = messages.filter((m) => canonical(m.text).includes(wanted));
                    }}
                    if (!candidates.length) candidates = messages;
                    if (!candidates.length) return {{state:'unknown', reason:'Claude response container not found'}};

                    candidates.sort((a,b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return b.priority - a.priority;
                    }});
                    const latest = candidates[candidates.length - 1].el;

                    const controls = [];
                    let scope = latest;
                    for (let i = 0; i < 8 && scope; i += 1) {{
                        for (const el of scope.querySelectorAll(
                            'button,[role="button"],[data-testid],[aria-label],[title],[data-tooltip],[data-tip]'
                        )) {{
                            if (!visible(el)) continue;
                            if (el.closest('[role="menu"],nav,header')) continue;
                            if (!controls.includes(el)) controls.push(el);
                        }}
                        scope = scope.parentElement;
                    }}

                    const active = controls.find(isActive);
                    if (active) return {{state:'active',label:labels(active).join(' | ')}};
                    const idle = controls.find(isRead);
                    if (idle) return {{state:'idle',label:labels(idle).join(' | ')}};
                    return {{state:'unknown', reason:'No Claude response-scoped Read Aloud state detected'}};
                }})()
            """)
            return result or {'state':'unknown'}
        except Exception as exc:
            return {'state':'unknown', 'reason':f'{type(exc).__name__}: {exc}'}

    async def _native_voice_activity_visible(self, page):
        """Detect active browser-native speech/audio anywhere on the bound page."""
        try:
            return bool(await page.evaluate(r"""
                (() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                    };
                    const label = (el) => [
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('data-testid') || '',
                        el.textContent || ''
                    ].join(' ').replace(/\\s+/g, ' ').trim();
                    const activeAudio = Array.from(document.querySelectorAll('audio,video')).some((el) => {
                        try { return !el.paused && el.readyState >= 2; } catch (_) { return false; }
                    });
                    if (activeAudio) return true;
                    try {
                        if (window.speechSynthesis && window.speechSynthesis.speaking) return true;
                    } catch (_) {}
                    const speakingLabels = Array.from(document.querySelectorAll(
                        'button,[role="button"],[data-testid],[aria-label],[title]'
                    )).filter(visible).some((el) => /(?:stop|pause|speaking|playback)/i.test(label(el)));
                    return speakingLabels;
                })()
            """))
        except Exception:
            return False

    async def _claude_voice_stop_visible(self, page, node, response_text=None):
        state = await self._claude_voice_state(
            page, node, response_text=response_text
        )
        return state.get('state') == 'active'

    async def _wait_for_voice_playback(self, page, node, response_text=None):
        """Wait for native playback on the exact captured response and release only on completion."""
        start = asyncio.get_event_loop().time()
        saw_playback = False
        idle_streak = 0

        def elapsed():
            return asyncio.get_event_loop().time() - start

        # Observe startup without allowing an unknown state to release the relay.
        while elapsed() < 30.0:
            if node.name == 'GPT':
                state = await self._gpt_voice_state(page, response_text=response_text)
            elif node.name == 'Claude':
                state = await self._claude_voice_state(page, node, response_text=response_text)
            else:
                state = {'state': 'unknown'}

            current = state.get('state')
            if current == 'active':
                saw_playback = True
                self.ui.log(
                    f"[VOICE] {node.name} playback started; "
                    f"state={state.get('label', 'active')!r}; waiting for native playback to finish.",
                    is_system=True
                )
                break

            await asyncio.sleep(0.20)

        if not saw_playback:
            self.ui.log(
                f"[VOICE] {node.name} native playback state still unknown after 30s; "
                "relay remains blocked until response-scoped playback completion is proven.",
                is_system=True
            )

        # Never interpret failure to observe the state as completion.
        while elapsed() < 1800.0:
            if node.name == 'GPT':
                state = await self._gpt_voice_state(page, response_text=response_text)
            elif node.name == 'Claude':
                state = await self._claude_voice_state(page, node, response_text=response_text)
            else:
                state = {'state': 'unknown'}

            current = state.get('state')
            if current == 'active':
                saw_playback = True
                idle_streak = 0
            elif current == 'idle':
                if saw_playback:
                    idle_streak += 1
                    if idle_streak >= 2:
                        self.ui.log(
                            f"[VOICE] {node.name} playback complete; "
                            "exact response voice control returned to idle.",
                            is_system=True
                        )
                        return True
                else:
                    idle_streak = 0
            else:
                idle_streak = 0

            await asyncio.sleep(0.20)

        self.ui.log(
            f"[VOICE] {node.name} native playback safety timeout reached; "
            "relay remains blocked.",
            is_system=True
        )
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
            started = await self._click_gpt_read_aloud(page, response_text)
        elif node.name == 'Gemini':
            started = await self._click_gemini_listen(page)
        elif node.name == 'DeepSeek':
            started = await self._click_deepseek_read_aloud(page, node)
        elif node.name == 'Aisha':
            started = await self._click_aisha_read_aloud(page, node)
        elif node.name == 'Claude':
            started = await self._click_claude_read_aloud(page, node, response_text)
        else:
            started = False

        if not started:
            return

        completed = await self._wait_for_voice_playback(page, node, response_text=response_text)
        while not completed:
            self.ui.log(
                f"[VOICE] {node.name} native completion still unproven; "
                "holding relay turn and retrying response-scoped state.",
                is_system=True
            )
            await asyncio.sleep(0.5)
            completed = await self._wait_for_voice_playback(
                page, node, response_text=response_text
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
            submit_success = await self._submit(page, node, input_element, selector, is_handshake=is_handshake)
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

    async def _refocus_live_input(self, page, selector):
        """Reacquire and focus the current composer after a framework re-render."""
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                await element.focus()
                return element
        except Exception as exc:
            self.ui.log(
                f"[SEND] REFRESH INPUT FOCUS failed for selector {selector!r}: {exc}",
                is_system=True
            )
        return None

    async def _submit_verified(self, page, node, input_element, selector, method, is_handshake=False):
        """Verify the INPUT -> SUBMITTED transition, not the later response."""
        timeout = 5.0 if method in ("Enter", "Enter/CDP") else 3.0
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            await asyncio.sleep(0.20)

            try:
                live_input = await page.query_selector(selector)
                check_element = live_input or input_element
                still_has_text = await self._input_has_text(page, check_element, selector)
            except Exception:
                still_has_text = True

            try:
                busy_state = await self._browser_generation_state(page)
                busy = bool(busy_state.get("busyControl"))
            except Exception:
                busy = False

            try:
                current = await self._capture_output_snapshot(page, node)
                response_candidates = self._response_candidates(current, node)
                new_output = bool(response_candidates)
            except Exception:
                new_output = False

            if method in ("Enter", "Enter/CDP"):
                if is_handshake:
                    # Handshake submission is its own state transition. Once the
                    # exact composer clears after a focused Enter, the message
                    # has left INPUT. Response recognition happens afterward.
                    submitted = (not still_has_text) or new_output
                else:
                    # Preserve the existing protection for ordinary relay sends.
                    submitted = new_output or ((not still_has_text) and busy)

                if submitted:
                    reason = "new_output" if new_output else "composer_clear"
                    self.ui.log(
                        f"[SEND] SUBMIT CONFIRMED ({method}): {node.name} | "
                        f"input_clear={not still_has_text} busy={busy} "
                        f"new_output={new_output} handshake={is_handshake} evidence={reason}",
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
                f"input_clear={not still_has_text} busy={busy} new_output={new_output} "
                f"handshake={is_handshake}",
                is_system=True
            )

        self.ui.log(
            f"[SEND] SUBMIT NOT CONFIRMED ({method}): {node.name} | "
            f"input still contains message or no submission evidence.",
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

    async def _submit(self, page, node, input_element, selector, is_handshake=False):
        await self._prepare_background_page(node)

        # Handshake is a state-machine boundary. Make INPUT -> SUBMIT use the
        # same focused-composer path as a human Enter, then fall back through
        # other real submission mechanisms. Do not wait for response extraction
        # to decide whether the message actually left the composer.
        if is_handshake:
            live_input = await self._refocus_live_input(page, selector)
            if live_input is not None:
                self.ui.log(
                    f"[SEND] HANDSHAKE FOCUS REFRESH: {node.name}",
                    is_system=True
                )
                try:
                    self.ui.log(
                        f"[SEND] HANDSHAKE SUBMIT ATTEMPT (focused Enter): {node.name}",
                        is_system=True
                    )
                    await page.keyboard.press("Enter")
                    if await self._submit_verified(
                        page, node, live_input, selector, "Enter", is_handshake=True
                    ):
                        return True
                except Exception as exc:
                    self.ui.log(
                        f"[SEND] focused handshake Enter failed for {node.name}: {exc}",
                        is_system=True
                    )

            # Native target-level key event, but ALWAYS refocus the current
            # composer immediately before firing it.
            for enter_attempt in range(2):
                try:
                    live_input = await self._refocus_live_input(page, selector)
                    if live_input is None:
                        raise RuntimeError("current composer could not be focused")
                    self.ui.log(
                        f"[SEND] HANDSHAKE SUBMIT ATTEMPT (CDP Enter): {node.name} "
                        f"attempt={enter_attempt + 1}/2",
                        is_system=True
                    )
                    await asyncio.to_thread(
                        self.browser.bridge.request,
                        {
                            "op": "target_key_press",
                            "pageId": node.page_id,
                            "url": node.url,
                            "key": "Enter",
                        }
                    )
                    if await self._submit_verified(
                        page, node, live_input, selector, "Enter/CDP", is_handshake=True
                    ):
                        return True
                    if enter_attempt == 0:
                        await asyncio.sleep(0.35)
                except Exception as exc:
                    self.ui.log(
                        f"[SEND] handshake CDP Enter failed for {node.name}: {exc}",
                        is_system=True
                    )

            # Actual enabled Send control fallback.
            for send_selector in [
                'button[aria-label*="Send"]', 'button[type="submit"]',
                '[data-testid="send-button"]'
            ]:
                try:
                    buttons = await page.query_selector_all(send_selector)
                    for button in buttons:
                        if not await button.is_visible() or await button.is_disabled():
                            continue
                        aria = (await button.get_attribute("aria-label") or "").lower()
                        text = (await button.inner_text() or "").lower()
                        if "stop" in aria or "cancel" in aria or "stop" in text or "cancel" in text:
                            continue
                        self.ui.log(
                            f"[SEND] HANDSHAKE SUBMIT ATTEMPT (button): {node.name} "
                            f"using '{send_selector}'",
                            is_system=True
                        )
                        await button.click()
                        if await self._submit_verified(
                            page, node, input_element, selector, "button", is_handshake=True
                        ):
                            return True
                except Exception as exc:
                    self.ui.log(
                        f"[SEND] handshake button submit attempt failed for {node.name}: {exc}",
                        is_system=True
                    )

            # Existing synthetic fallback, again with fresh focus.
            try:
                live_input = await self._refocus_live_input(page, selector)
                if live_input is None:
                    raise RuntimeError("current composer could not be focused")
                self.ui.log(
                    f"[SEND] HANDSHAKE SUBMIT ATTEMPT (DOM Enter fallback): {node.name}",
                    is_system=True
                )
                await asyncio.to_thread(
                    self.browser.bridge.request,
                    {
                        "op": "element_dispatch_enter",
                        "pageId": node.page_id,
                        "url": node.url,
                        "selector": selector,
                        "index": getattr(live_input, 'index', 0),
                    }
                )
                if await self._submit_verified(
                    page, node, live_input, selector, "Enter/CDP", is_handshake=True
                ):
                    return True
            except Exception as exc:
                self.ui.log(
                    f"[SEND] handshake DOM Enter fallback failed for {node.name}: {exc}",
                    is_system=True
                )

            return False

        # Ordinary relay sends retain the existing button-first route, but any
        # Enter fallback now refocuses the live composer before pressing Enter.
        send_selectors = [
            'button[aria-label*="Send"]', 'button[type="submit"]',
            '[data-testid="send-button"]'
        ]

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
                        if await self._submit_verified(
                            page, node, input_element, selector, "button", is_handshake=False
                        ):
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

        for enter_attempt in range(2):
            try:
                live_input = await self._refocus_live_input(page, selector)
                if live_input is None:
                    raise RuntimeError("current composer could not be focused")
                self.ui.log(
                    f"[SEND] SUBMIT ATTEMPT (focused Enter): {node.name} attempt={enter_attempt + 1}/2",
                    is_system=True
                )
                await page.keyboard.press("Enter")
                if await self._submit_verified(
                    page, node, live_input, selector, "Enter", is_handshake=False
                ):
                    return True
                if enter_attempt == 0:
                    await asyncio.sleep(0.35)
            except Exception as exc:
                self.ui.log(
                    f"[SEND] focused Enter submit attempt failed for {node.name}: {exc}",
                    is_system=True
                )

        for enter_attempt in range(2):
            try:
                live_input = await self._refocus_live_input(page, selector)
                if live_input is None:
                    raise RuntimeError("current composer could not be focused")
                self.ui.log(
                    f"[SEND] SUBMIT ATTEMPT (CDP Enter): {node.name} attempt={enter_attempt + 1}/2",
                    is_system=True
                )
                await asyncio.to_thread(
                    self.browser.bridge.request,
                    {
                        "op": "target_key_press",
                        "pageId": node.page_id,
                        "url": node.url,
                        "key": "Enter",
                    }
                )
                if await self._submit_verified(
                    page, node, live_input, selector, "Enter/CDP", is_handshake=False
                ):
                    return True
                if enter_attempt == 0:
                    await asyncio.sleep(0.35)
            except Exception as exc:
                self.ui.log(
                    f"[SEND] CDP Enter submit attempt failed for {node.name}: {exc}",
                    is_system=True
                )

        try:
            live_input = await self._refocus_live_input(page, selector)
            if live_input is None:
                raise RuntimeError("current composer could not be focused")
            self.ui.log(
                f"[SEND] SUBMIT ATTEMPT (Enter/DOM fallback): {node.name}",
                is_system=True
            )
            await asyncio.to_thread(
                self.browser.bridge.request,
                {
                    "op": "element_dispatch_enter",
                    "pageId": node.page_id,
                    "url": node.url,
                    "selector": selector,
                    "index": getattr(live_input, 'index', 0),
                }
            )
            if await self._submit_verified(
                page, node, live_input, selector, "Enter/CDP", is_handshake=False
            ):
                return True
        except Exception as exc:
            self.ui.log(
                f"[SEND] Enter DOM fallback failed for {node.name}: {exc}",
                is_system=True
            )

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

    async def _capture_claude_latest(self, page, node):
        """Capture Claude's newest assistant response as a DOM-node delta.

        Claude's current UI uses several assistant-response structures and the
        old QS fallback (``article, div.assistant``) no longer reliably maps
        to the actual response nodes. Keep Claude-specific extraction local
        to the transport boundary: find visible assistant-like nodes, reduce
        nested matches to leaves, and return the last leaf in DOM order.
        This preserves the normal QS baseline/candidate state machine while
        avoiding dependence on one brittle Claude selector.
        """
        try:
            submitted = self._canonical_message_text(node.last_submitted_text)
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
                        .split('\\n')
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .join('\\n')
                        .trim();
                    const canonical = (value) => String(value || '')
                        .normalize('NFKC')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\s+/g, ' ')
                        .trim()
                        .toLocaleLowerCase();
                    const submittedText = {safe_submitted};
                    const selectors = [
                        '.font-claude-response',
                        '[data-testid="assistant-message"]',
                        '[data-testid="ai-message"]',
                        '.font-claude-message',
                        '[data-testid="message-assistant"]',
                        '.assistant-message',
                        '.font-claude-response-body',
                        '.standard-markdown',
                        '.progressive-markdown'
                    ];
                    const candidates = [];
                    const seen = new Set();
                    const add = (el, source) => {{
                        if (!el || seen.has(el) || !visible(el)) return;
                        const text = clean(el.innerText || el.textContent || '');
                        if (!text) return;
                        seen.add(el);
                        candidates.push({{el, source, text}});
                    }};
                    for (const selector of selectors) {{
                        try {{
                            document.querySelectorAll(selector).forEach((el) => add(el, selector));
                        }} catch (_) {{}}
                    }}
                    if (!candidates.length) {{
                        return {{ok:false, reason:'No visible Claude assistant-response nodes matched current selectors.'}};
                    }}
                    const leaves = candidates.filter((item) => !candidates.some((other) =>
                        other.el !== item.el && item.el.contains(other.el)
                    ));
                    const pool = leaves.length ? leaves : candidates;
                    let nonSubmitted = pool.filter((item) =>
                        !submittedText || canonical(item.text) !== submittedText
                    );
                    if (submittedText && !nonSubmitted.length) {{
                        return {{ok:false, reason:'Claude candidates currently contain only the submitted user turn.'}};
                    }}
                    if (!nonSubmitted.length) nonSubmitted = pool;
                    nonSubmitted.sort((a, b) => {{
                        const pos = a.el.compareDocumentPosition(b.el);
                        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
                        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
                        return 0;
                    }});
                    const chosen = nonSubmitted[nonSubmitted.length - 1];
                    return {{ok:true, text:chosen.text, source:chosen.source,
                            candidateCount:candidates.length, leafCount:leaves.length}};
                }})()
            """)
            if not result or not result.get('ok'):
                reason = result.get('reason', 'unknown') if result else 'no result'
                self.ui.log(
                    f"[CLAUDE-CAPTURE] No fresh latest response: {reason}",
                    is_system=True
                )
                return []
            text = str(result.get('text') or '').strip()
            if not text:
                return []
            self.ui.log(
                f"[CLAUDE-CAPTURE] Latest response locked to one DOM node "
                f"(source={result.get('source')}, candidates={result.get('candidateCount')}, "
                f"leaves={result.get('leafCount')}, chars={len(text)}).",
                is_system=True
            )
            return [text]
        except Exception as exc:
            self.ui.log(
                f"[CLAUDE-CAPTURE] Latest-node extraction failed: {type(exc).__name__}: {exc}",
                is_system=True
            )
            return []

    async def _capture_output_snapshot(self, page, node):
        if node.name == "Aisha":
            return await self._capture_aisha_latest(page, node)
        if node.name == "Claude":
            return await self._capture_claude_latest(page, node)

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

    async def _capture_latest_handshake_frame(self, page, node):
        """Read the latest assistant turn directly for the handshake contract.

        Handshake detection is deliberately independent of the generic relay
        response-candidate machinery. The generic path can mix parent/child
        message selectors (notably GPT's article + assistant-role selectors),
        which can make a fresh assistant turn look like an old/stale candidate.
        For HANDSHAKING, the state contract is simple: the latest assistant turn
        itself must contain one complete 🟩...🔚 frame.
        """
        try:
            output_selector = node.output_selector or ''
            safe_output_selector = json.dumps(output_selector)
            safe_node_name = json.dumps(node.name)
            result = await page.evaluate(rf"""
                (() => {{
                    const nodeName = {safe_node_name};
                    const outputSelector = {safe_output_selector};
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
                        .trim();

                    let elements = [];
                    const pushUnique = (el) => {{
                        if (el && !elements.includes(el) && visible(el)) elements.push(el);
                    }};

                    // GPT has a precise assistant-message selector. Prefer it
                    // so parent <article> nodes cannot confuse the handshake
                    // detector with historical content.
                    try {{
                        if (document.querySelector('[data-message-author-role="assistant"]')) {{
                            document.querySelectorAll('[data-message-author-role="assistant"]').forEach(pushUnique);
                        }}
                    }} catch (_) {{}}

                    // Other nodes may expose only their discovered output selector.
                    if (!elements.length && outputSelector) {{
                        try {{
                            document.querySelectorAll(outputSelector).forEach(pushUnique);
                        }} catch (_) {{}}
                    }}

                    // Final generic fallbacks.
                    if (!elements.length) {{
                        for (const sel of [
                            '[data-message-id]', '[data-testid*="message"]',
                            '[role="article"]', 'article',
                            'div[class*="message" i]'
                        ]) {{
                            try {{ document.querySelectorAll(sel).forEach(pushUnique); }} catch (_) {{}}
                        }}
                    }}

                    if (!elements.length) return {{ok:false, reason:'no visible assistant/message nodes'}};

                    const latest = elements[elements.length - 1];
                    const text = clean(latest.innerText || latest.textContent || '');
                    const matches = Array.from(text.matchAll(/🟩[\s\S]*?🔚/g));
                    if (!matches.length) {{
                        return {{ok:false, reason:'latest assistant turn contains no complete handshake frame'}};
                    }}

                    const frame = matches[matches.length - 1][0].trim();
                    return {{ok:true, frame, chars:text.length, nodeName}};
                }})()
            """)
            if not result or not result.get('ok'):
                return None
            return str(result.get('frame') or '').strip() or None
        except Exception as exc:
            self.ui.log(
                f"[WAIT-DIAG] {node.name}: direct handshake capture failed: "
                f"{type(exc).__name__}: {exc}",
                is_system=True
            )
            return None

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
            direct_frame = await self._capture_latest_handshake_frame(page, node)
            if direct_frame:
                start = direct_frame.find("🟩")
                end = direct_frame.find("🔚", start)
                if start != -1 and end != -1:
                    frame_content = direct_frame[start + 1:end].strip()
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
        # Browser transport must exist before the full QS UI/controller starts.
        ensure_browser_transport()
        controller = QSController()
        controller.ui.run()
    except BrowserBootstrapCancelled:
        logger.info("[BROWSER] Startup cancelled by operator. QS exiting cleanly.")
        print("QuackSink startup cancelled.")
    except BrowserBootstrapError as exc:
        logger.error("[BROWSER] Startup failed: %s", exc)
        message = f"QuackSink browser startup failed:\n\n{exc}"
        try:
            messagebox.showerror(f"QuackSink QS {VERSION}", message)
        except Exception:
            pass
        print(message)
    except Exception as exc:
        logger.error("Fatal QS %s startup error: %s", VERSION, exc)
        print(f"FATAL QS {VERSION} ERROR: {exc}")
        input("Press ENTER to exit...")
