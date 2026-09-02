# ================================================================
# QuackSpace Launcher
# FILE: qsl.py
# VERSION: QSL 0.3
#
# PURPOSE:
#   Prepare the Chromium/CDP environment and launch the frozen
#   QuackSink executable.
#
# IMPORTANT:
#   QSL does NOT modify qs.py.
#
# QSL 0.3:
#   - Creates a timestamped startup archive on every launch.
#   - Archives qsl.py and qsl_config.json when present.
#   - Writes a QSL startup LOG.txt into the archive.
#   - Discovers installed Chromium-family browsers through Windows
#     installed-application registry information.
#   - Falls back to common Windows install locations when needed.
#   - Presents discovered browsers in a dropdown.
#   - Selecting a browser fills the visible executable path.
#   - Keeps Browse... as a manual fallback.
#   - Remembers browser path, QuackSink directory, and human handle.
#   - Creates/updates the EXISTING qs_config.json expected by QS 1.1.
#   - Prevents QSL from intentionally launching a second QuackSink.exe.
#   - Checks whether CDP is already available on 127.0.0.1:9222.
#   - Starts the selected browser with --remote-debugging-port=9222
#     when CDP is not already available.
#   - Warns when the selected QuackSink.exe cannot be verified against
#     the configured official repository binary.
#   - Creates a launch BAT inside the active QSL archive.
#   - Launches that BAT through cmd.exe.
#   - Leaves the BAT in the archive as permanent launch provenance.
#   - Closes QSL after successful launch.
#
# There is intentionally NO qs.py process check.
# ================================================================

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winreg


# ================================================================
# CONSTANTS
# ================================================================

QSL_VERSION = "0.3"

QSL_CONFIG_FILE = "qsl_config.json"
QS_CONFIG_FILE = "qs_config.json"
QS_EXE_NAME = "QuackSink.exe"

QSL_LAUNCH_BAT_NAME = "QSL_launch_qs.bat"
QSL_ARCHIVE_PREFIX = "QSL_"
ARCHIVES_DIR_NAME = "ARCHIVES"

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

CDP_VERSION_URL = (
    f"http://{CDP_HOST}:{CDP_PORT}/json/version"
)

# IMPORTANT:
# Until the official QuackSink.exe is published at this exact
# repository location, QSL cannot verify it as official.
OFFICIAL_EXE_URL = (
    "https://raw.githubusercontent.com/magiccozmo/QuackSink/"
    "main/DIST/QuackSink.exe"
)

DEFAULT_CONFIG = {
    "browser_path": "",
    "quacksink_dir": "",
    "human_handle": "Cozmo",
    "official_exe_url": OFFICIAL_EXE_URL,
}


# ================================================================
# PATHS / ARCHIVING
# ================================================================

def launcher_dir() -> Path:
    """
    Return the directory containing the active QSL program.

    For a frozen QSL executable, use the directory containing the
    executable. For qsl.py, use the directory containing the source.
    """
    if getattr(sys, "frozen", False):
        return Path(
            sys.executable
        ).resolve().parent

    return Path(
        __file__
    ).resolve().parent


def source_file_path() -> Path:
    """
    Return qsl.py when it exists beside the launcher.

    This allows the source to be archived during normal development.
    """
    candidate = (
        launcher_dir()
        / "qsl.py"
    )

    if candidate.is_file():
        return candidate

    return Path(
        __file__
    ).resolve()


def qsl_config_path() -> Path:
    return (
        launcher_dir()
        / QSL_CONFIG_FILE
    )


def archives_dir() -> Path:
    return (
        launcher_dir()
        / ARCHIVES_DIR_NAME
    )


def timestamp_for_archive() -> str:
    return datetime.now().strftime(
        "%b %d %Y %I_%M_%S_%p"
    )


def create_unique_archive_dir() -> Path:
    """
    Create a unique timestamp-named archive directory.

    Example:
        QSL_Sep 02 2026 04_58_30_AM_v0.3

    If the generated name already exists, wait one minute and try
    again, matching the project's archive discipline.
    """
    root = archives_dir()

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    while True:

        name = (
            f"{QSL_ARCHIVE_PREFIX}"
            f"{timestamp_for_archive()}"
            f"_v{QSL_VERSION}"
        )

        candidate = (
            root
            / name
        )

        if not candidate.exists():
            candidate.mkdir(
                parents=True
            )
            return candidate

        time.sleep(60)


def archive_startup(
    active_archive: Path,
    config_path: Path,
) -> list[str]:

    actions: list[str] = []

    source = source_file_path()

    if source.is_file():

        destination = (
            active_archive
            / "qsl.py"
        )

        shutil.copy2(
            source,
            destination,
        )

        actions.append(
            f"Source archived: {destination}"
        )

    else:

        actions.append(
            "Source archive skipped: qsl.py not found."
        )

    if config_path.is_file():

        destination = (
            active_archive
            / QSL_CONFIG_FILE
        )

        shutil.copy2(
            config_path,
            destination,
        )

        actions.append(
            f"Configuration archived: {destination}"
        )

    else:

        actions.append(
            "Configuration not present at startup."
        )

    return actions


def write_startup_log(
    active_archive: Path,
    actions: list[str],
) -> Path:

    path = (
        active_archive
        / "LOG.txt"
    )

    lines = [
        "=============================================================",
        (
            f"QuackSpace Launcher QSL "
            f"{QSL_VERSION} STARTING"
        ),
        (
            "Startup timestamp: "
            + datetime.now().isoformat(
                sep=" ",
                timespec="seconds",
            )
        ),
        f"Startup directory: {launcher_dir()}",
        f"Archive root: {archives_dir()}",
        f"Active archive: {active_archive}",
        f"Python executable: {sys.executable}",
        (
            f"Frozen: "
            f"{bool(getattr(sys, 'frozen', False))}"
        ),
        "-------------------------------------------------------------",
    ]

    lines.extend(
        actions
    )

    lines.append(
        "============================================================="
    )

    lines.append(
        ""
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        handle.write(
            "\n".join(lines)
        )

    return path


def append_archive_log(
    active_archive: Path,
    message: str,
) -> None:

    path = (
        active_archive
        / "LOG.txt"
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:

        handle.write(
            f"{timestamp} [QSL] {message}\n"
        )


# ================================================================
# BASIC FILE / CONFIG HELPERS
# ================================================================

def load_qsl_config() -> dict:

    path = qsl_config_path()

    if not path.exists():
        return DEFAULT_CONFIG.copy()

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            data = json.load(
                handle
            )

        config = (
            DEFAULT_CONFIG.copy()
        )

        if isinstance(
            data,
            dict,
        ):

            config.update(
                data
            )

        return config

    except Exception:

        return DEFAULT_CONFIG.copy()


def save_json(
    path: Path,
    data: dict,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temp.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            data,
            handle,
            indent=4,
        )

        handle.write(
            "\n"
        )

    temp.replace(
        path
    )


def save_qsl_config(
    config: dict,
) -> None:

    save_json(
        qsl_config_path(),
        config,
    )


# ================================================================
# WINDOWS BROWSER DISCOVERY
# ================================================================

BROWSER_DEFINITIONS = (
    (
        "Opera GX",
        (
            "opera gx",
        ),
        (
            "opera.exe",
        ),
    ),
    (
        "Opera",
        (
            "opera",
        ),
        (
            "opera.exe",
        ),
    ),
    (
        "Google Chrome",
        (
            "google chrome",
            "chrome",
        ),
        (
            "chrome.exe",
        ),
    ),
    (
        "Microsoft Edge",
        (
            "microsoft edge",
        ),
        (
            "msedge.exe",
        ),
    ),
    (
        "Brave",
        (
            "brave",
        ),
        (
            "brave.exe",
        ),
    ),
)


def clean_registry_text(
    value: str,
) -> str:

    value = str(
        value or ""
    ).strip()

    if not value:
        return ""

    return (
        os.path.expandvars(
            value
        )
        .strip()
        .strip('"')
    )


def identify_browser(
    display_name: str,
    install_location: str,
    display_icon: str,
) -> tuple[
    str,
    tuple[str, ...],
] | None:

    haystack = " ".join(
        [
            display_name,
            install_location,
            display_icon,
        ]
    ).lower()

    for (
        label,
        markers,
        executable_names,
    ) in BROWSER_DEFINITIONS:

        if any(
            marker in haystack
            for marker in markers
        ):

            return (
                label,
                executable_names,
            )

    return None


def extract_executable_from_value(
    value: str,
) -> str:

    value = (
        clean_registry_text(
            value
        )
    )

    if not value:
        return ""

    candidate = Path(
        value
    )

    if candidate.is_file():
        return str(
            candidate
        )

    if '"' in value:

        parts = [
            part.strip()
            for part
            in value.split('"')
            if part.strip()
        ]

        for part in parts:

            path = Path(
                os.path.expandvars(
                    part
                )
            )

            if (
                path.is_file()
                and path.suffix.lower()
                == ".exe"
            ):

                return str(
                    path
                )

    lower = value.lower()

    exe_index = lower.find(
        ".exe"
    )

    if exe_index != -1:

        possible = (
            value[
                :exe_index + 4
            ]
            .strip()
            .strip('"')
        )

        path = Path(
            os.path.expandvars(
                possible
            )
        )

        if path.is_file():
            return str(
                path
            )

    return ""


def scan_uninstall_registry(
    root,
    base_key: str,
    access_flags: int = 0,
) -> list[tuple[str, str]]:

    found: list[
        tuple[str, str]
    ] = []

    try:

        with winreg.OpenKey(
            root,
            base_key,
            0,
            winreg.KEY_READ
            | access_flags,
        ) as parent:

            subkey_count = (
                winreg.QueryInfoKey(
                    parent
                )[0]
            )

            for index in range(
                subkey_count
            ):

                try:

                    child_name = (
                        winreg.EnumKey(
                            parent,
                            index,
                        )
                    )

                except OSError:

                    continue

                try:

                    with winreg.OpenKey(
                        parent,
                        child_name,
                        0,
                        winreg.KEY_READ
                        | access_flags,
                    ) as app_key:

                        def read_value(
                            name: str,
                        ) -> str:

                            try:

                                value, _ = (
                                    winreg.QueryValueEx(
                                        app_key,
                                        name,
                                    )
                                )

                                return str(
                                    value or ""
                                )

                            except OSError:

                                return ""

                        display_name = (
                            read_value(
                                "DisplayName"
                            )
                        )

                        install_location = (
                            read_value(
                                "InstallLocation"
                            )
                        )

                        display_icon = (
                            read_value(
                                "DisplayIcon"
                            )
                        )

                except OSError:

                    continue

                identified = (
                    identify_browser(
                        display_name,
                        install_location,
                        display_icon,
                    )
                )

                if not identified:
                    continue

                (
                    label,
                    executable_names,
                ) = identified

                executable_path = ""

                if display_icon:

                    executable_path = (
                        extract_executable_from_value(
                            display_icon
                        )
                    )

                if (
                    not executable_path
                    and install_location
                ):

                    install_dir = Path(
                        os.path.expandvars(
                            install_location
                        )
                    )

                    for executable_name in (
                        executable_names
                    ):

                        candidate = (
                            install_dir
                            / executable_name
                        )

                        if candidate.is_file():

                            executable_path = (
                                str(candidate)
                            )

                            break

                if executable_path:

                    found.append(
                        (
                            label,
                            executable_path,
                        )
                    )

    except OSError:

        pass

    return found


def fallback_browser_locations() -> list[
    tuple[str, str]
]:

    local_app_data = Path(
        os.environ.get(
            "LOCALAPPDATA",
            "",
        )
    )

    program_files = Path(
        os.environ.get(
            "PROGRAMFILES",
            r"C:\Program Files",
        )
    )

    program_files_x86 = Path(
        os.environ.get(
            "PROGRAMFILES(X86)",
            r"C:\Program Files (x86)",
        )
    )

    candidates = [
        (
            "Opera GX",
            local_app_data
            / "Programs"
            / "Opera GX"
            / "opera.exe",
        ),
        (
            "Opera",
            local_app_data
            / "Programs"
            / "Opera"
            / "opera.exe",
        ),
        (
            "Google Chrome",
            local_app_data
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
        ),
        (
            "Google Chrome",
            program_files
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
        ),
        (
            "Google Chrome",
            program_files_x86
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
        ),
        (
            "Microsoft Edge",
            program_files
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe",
        ),
        (
            "Microsoft Edge",
            program_files_x86
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe",
        ),
        (
            "Brave",
            local_app_data
            / "BraveSoftware"
            / "Brave-Browser"
            / "Application"
            / "brave.exe",
        ),
        (
            "Brave",
            program_files
            / "BraveSoftware"
            / "Brave-Browser"
            / "Application"
            / "brave.exe",
        ),
    ]

    return [
        (
            label,
            str(path),
        )
        for label, path
        in candidates
        if path.is_file()
    ]


def discover_installed_browsers() -> list[
    tuple[str, str]
]:

    found: list[
        tuple[str, str]
    ] = []

    registry_targets = [
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]

    for root, base_key in registry_targets:

        found.extend(
            scan_uninstall_registry(
                root,
                base_key,
            )
        )

    wow64_32 = getattr(
        winreg,
        "KEY_WOW64_32KEY",
        0,
    )

    if wow64_32:

        for root, base_key in registry_targets:

            found.extend(
                scan_uninstall_registry(
                    root,
                    base_key,
                    wow64_32,
                )
            )

    found.extend(
        fallback_browser_locations()
    )

    deduped: list[
        tuple[str, str]
    ] = []

    seen: set[str] = set()

    for label, path in found:

        normalized = os.path.normcase(
            os.path.abspath(
                path
            )
        )

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        deduped.append(
            (
                label,
                path,
            )
        )

    priority = {
        "Opera GX": 0,
        "Opera": 1,
        "Google Chrome": 2,
        "Microsoft Edge": 3,
        "Brave": 4,
    }

    deduped.sort(
        key=lambda item: (
            priority.get(
                item[0],
                99,
            ),
            item[0].lower(),
            item[1].lower(),
        )
    )

    return deduped


# ================================================================
# EXISTING QS CONFIGURATION
# ================================================================

def prepare_qs_config(
    qs_dir: Path,
    human_handle: str,
) -> Path:

    config_path = (
        qs_dir
        / QS_CONFIG_FILE
    )

    if config_path.exists():

        try:

            with config_path.open(
                "r",
                encoding="utf-8",
            ) as handle:

                data = json.load(
                    handle
                )

            if not isinstance(
                data,
                dict,
            ):

                data = {}

        except Exception:

            data = {}

    else:

        data = {}

    data[
        "human_handle"
    ] = human_handle

    data.setdefault(
        "nodes",
        [],
    )

    save_json(
        config_path,
        data,
    )

    return config_path


# ================================================================
# QUACKSINK PROCESS GUARD
# ================================================================

def quacksink_is_running() -> bool:

    try:

        completed = (
            subprocess.run(
                [
                    "tasklist",
                    "/FI",
                    f"IMAGENAME eq {QS_EXE_NAME}",
                    "/FO",
                    "CSV",
                    "/NH",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        )

        return (
            QS_EXE_NAME.lower()
            in completed.stdout.lower()
        )

    except Exception:

        return False


# ================================================================
# EXE HASH / OFFICIAL BUILD CHECK
# ================================================================

def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def fetch_official_exe_hash(
    url: str,
) -> str | None:

    if not url:
        return None

    try:

        request = (
            urllib.request.Request(
                url,
                headers={
                    "User-Agent":
                        "QuackSpace-Launcher-QSL"
                },
            )
        )

        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:

            official_data = (
                response.read()
            )

        return hashlib.sha256(
            official_data
        ).hexdigest()

    except Exception:

        return None


def verify_quacksink_exe(
    config: dict,
    exe_path: Path,
) -> bool:

    local_hash = (
        sha256_file(
            exe_path
        )
    )

    official_url = str(
        config.get(
            "official_exe_url",
            OFFICIAL_EXE_URL,
        )
    ).strip()

    official_hash = (
        fetch_official_exe_hash(
            official_url
        )
    )

    if not official_hash:

        return messagebox.askyesno(
            "Official QuackSink.exe Check Unavailable",
            (
                "QSL could not verify this "
                "QuackSink.exe against the "
                "configured official repository "
                "binary.\n\n"
                f"Local SHA-256:\n{local_hash}\n\n"
                "The executable has NOT been verified "
                "as the current official release.\n\n"
                "Continue anyway?"
            ),
        )

    if (
        local_hash.lower()
        == official_hash.lower()
    ):

        return True

    return messagebox.askyesno(
        "WARNING — QuackSink.exe Is Not Official",
        (
            "This QuackSink.exe does NOT match "
            "the current official repository "
            "executable.\n\n"
            f"Local SHA-256:\n{local_hash}\n\n"
            f"Official SHA-256:\n{official_hash}\n\n"
            "It may be an older, newer, or "
            "locally modified build.\n\n"
            "Continue anyway?"
        ),
    )


# ================================================================
# CDP / BROWSER CONTROL
# ================================================================

def cdp_is_available(
    timeout: float = 1.0,
) -> bool:

    try:

        request = (
            urllib.request.Request(
                CDP_VERSION_URL,
                headers={
                    "User-Agent":
                        "QuackSpace-Launcher-QSL"
                },
            )
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            return (
                response.status
                == 200
            )

    except Exception:

        return False


def cdp_browser_name(
    timeout: float = 1.0,
) -> str:

    try:

        request = (
            urllib.request.Request(
                CDP_VERSION_URL,
                headers={
                    "User-Agent":
                        "QuackSpace-Launcher-QSL"
                },
            )
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return str(
            data.get(
                "Browser",
                "Unknown Chromium",
            )
        )

    except Exception:

        return "Unknown"


def launch_browser(
    browser_path: Path,
) -> subprocess.Popen:

    command = [
        str(browser_path),
        (
            f"--remote-debugging-port="
            f"{CDP_PORT}"
        ),
    ]

    return subprocess.Popen(
        command,
        cwd=str(
            browser_path.parent
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def prepare_browser(
    browser_path: Path,
    active_archive: Path | None = None,
) -> bool:

    if cdp_is_available():

        if active_archive:

            append_archive_log(
                active_archive,
                (
                    "CDP already available "
                    "before browser launch."
                ),
            )

        return True

    try:

        launch_browser(
            browser_path
        )

        if active_archive:

            append_archive_log(
                active_archive,
                (
                    "Browser launch requested: "
                    f"{browser_path} "
                    f"--remote-debugging-port="
                    f"{CDP_PORT}"
                ),
            )

    except Exception as exc:

        if active_archive:

            append_archive_log(
                active_archive,
                f"Browser launch FAILED: {exc}",
            )

        messagebox.showerror(
            "Browser Launch Failed",
            (
                "QSL could not start the "
                "selected browser.\n\n"
                f"{browser_path}\n\n"
                f"Error:\n{exc}"
            ),
        )

        return False

    deadline = (
        time.monotonic()
        + 15.0
    )

    while (
        time.monotonic()
        < deadline
    ):

        if cdp_is_available():

            if active_archive:

                append_archive_log(
                    active_archive,
                    (
                        f"CDP became available "
                        f"on port {CDP_PORT}."
                    ),
                )

            return True

        time.sleep(
            0.25
        )

    if active_archive:

        append_archive_log(
            active_archive,
            (
                f"CDP did not become available "
                f"on port {CDP_PORT} within 15 seconds."
            ),
        )

    messagebox.showwarning(
        "Remote Debugging Unavailable",
        (
            "The selected browser was started, "
            "but QSL could not detect remote "
            f"debugging on port {CDP_PORT}.\n\n"
            "This commonly happens when a normal "
            "browser instance was already running "
            "and reused its existing process.\n\n"
            "Close that browser completely and "
            "try again."
        ),
    )

    return False


# ================================================================
# LAUNCH BAT
# ================================================================

def create_launch_bat(
    active_archive: Path,
    qs_exe: Path,
) -> Path:
    """
    Create the exact launch script used to hand QS to Windows.

    The BAT remains permanently inside the QSL startup archive.
    """
    bat_path = (
        active_archive
        / QSL_LAUNCH_BAT_NAME
    )

    qs_dir = qs_exe.parent

    lines = [
        "@echo off",
        f'cd /d "{qs_dir}"',
        f'"{qs_exe.name}"',
    ]

    with bat_path.open(
        "w",
        encoding="utf-8",
        newline="\r\n",
    ) as handle:

        handle.write(
            "\r\n".join(
                lines
            )
        )

        handle.write(
            "\r\n"
        )

    append_archive_log(
        active_archive,
        f"Launch BAT created: {bat_path}",
    )

    return bat_path


def launch_quacksink_via_bat(
    bat_path: Path,
    qs_exe: Path,
) -> subprocess.Popen:
    """
    Launch the preserved BAT through cmd.exe.

    The BAT itself performs:

        cd /d "<QuackSink directory>"
        "QuackSink.exe"
    """
    return subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            str(bat_path),
        ],
        cwd=str(
            qs_exe.parent
        ),
    )


# ================================================================
# GUI
# ================================================================

class QuackSpaceLauncher:

    def __init__(
        self,
    ) -> None:

        self.root = tk.Tk()

        self.root.title(
            f"QuackSpace Launcher QSL {QSL_VERSION}"
        )

        self.root.geometry(
            "920x700"
        )

        self.root.minsize(
            780,
            600,
        )

        self.root.configure(
            bg="#121212"
        )

        self.config = (
            load_qsl_config()
        )

        # --------------------------------------------------------
        # ARCHIVE FIRST
        # --------------------------------------------------------

        self.active_archive = (
            create_unique_archive_dir()
        )

        actions = archive_startup(
            self.active_archive,
            qsl_config_path(),
        )

        write_startup_log(
            self.active_archive,
            actions,
        )

        append_archive_log(
            self.active_archive,
            "QSL startup archive created.",
        )

        # --------------------------------------------------------
        # BROWSER DISCOVERY
        # --------------------------------------------------------

        self.browsers = (
            discover_installed_browsers()
        )

        self.browser_name_var = (
            tk.StringVar()
        )

        self.browser_path_var = (
            tk.StringVar(
                value=str(
                    self.config.get(
                        "browser_path",
                        "",
                    )
                )
            )
        )

        self.qs_dir_var = (
            tk.StringVar(
                value=str(
                    self.config.get(
                        "quacksink_dir",
                        "",
                    )
                )
            )
        )

        self.handle_var = (
            tk.StringVar(
                value=str(
                    self.config.get(
                        "human_handle",
                        "Cozmo",
                    )
                )
            )
        )

        self.status_var = (
            tk.StringVar(
                value="Ready."
            )
        )

        self.build_ui()

        self.populate_browser_dropdown()

        self.root.after(
            150,
            self.startup_check,
        )

        append_archive_log(
            self.active_archive,
            "QSL GUI initialized.",
        )

    # ------------------------------------------------------------

    def build_ui(
        self,
    ) -> None:

        tk.Label(
            self.root,
            text="🪶 QUACKSPACE LAUNCHER",
            font=(
                "Arial",
                24,
                "bold",
            ),
            bg="#121212",
            fg="#00FFCC",
        ).pack(
            pady=(20, 5)
        )

        tk.Label(
            self.root,
            text=(
                f"QSL {QSL_VERSION} — "
                "prepare environment and "
                "launch QuackSink"
            ),
            font=(
                "Arial",
                11,
            ),
            bg="#121212",
            fg="#CCCCCC",
        ).pack(
            pady=(0, 20)
        )

        form = tk.Frame(
            self.root,
            bg="#121212",
        )

        form.pack(
            fill=tk.X,
            padx=30,
        )

        # --------------------------------------------------------
        # Browser dropdown
        # --------------------------------------------------------

        browser_frame = tk.Frame(
            form,
            bg="#121212",
        )

        browser_frame.pack(
            fill=tk.X,
            pady=8,
        )

        tk.Label(
            browser_frame,
            text="Browser:",
            width=16,
            anchor="e",
            font=(
                "Arial",
                12,
                "bold",
            ),
            bg="#121212",
            fg="#00FFCC",
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        self.browser_combo = (
            ttk.Combobox(
                browser_frame,
                textvariable=(
                    self.browser_name_var
                ),
                state="readonly",
                font=(
                    "Arial",
                    11,
                ),
            )
        )

        self.browser_combo.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        self.browser_combo.bind(
            "<<ComboboxSelected>>",
            self.browser_selected,
        )

        tk.Button(
            browser_frame,
            text="Rescan",
            command=self.rescan_browsers,
            font=(
                "Arial",
                10,
                "bold",
            ),
            bg="#444444",
            fg="#FFFFFF",
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        # --------------------------------------------------------
        # Browser executable
        # --------------------------------------------------------

        self.add_path_row(
            form,
            "Browser EXE:",
            self.browser_path_var,
            self.choose_browser,
        )

        # --------------------------------------------------------
        # QuackSink directory
        # --------------------------------------------------------

        self.add_path_row(
            form,
            "QuackSink:",
            self.qs_dir_var,
            self.choose_qs_dir,
        )

        # --------------------------------------------------------
        # Human handle
        # --------------------------------------------------------

        handle_frame = tk.Frame(
            form,
            bg="#121212",
        )

        handle_frame.pack(
            fill=tk.X,
            pady=10,
        )

        tk.Label(
            handle_frame,
            text="Human Handle:",
            width=16,
            anchor="e",
            font=(
                "Arial",
                12,
                "bold",
            ),
            bg="#121212",
            fg="#00FFCC",
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        tk.Entry(
            handle_frame,
            textvariable=self.handle_var,
            font=(
                "Arial",
                12,
            ),
            bg="#1e1e1e",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        # --------------------------------------------------------
        # Status
        # --------------------------------------------------------

        status_frame = tk.Frame(
            self.root,
            bg="#1e1e1e",
            bd=1,
            relief=tk.SOLID,
        )

        status_frame.pack(
            fill=tk.X,
            padx=30,
            pady=25,
        )

        tk.Label(
            status_frame,
            text="STATUS",
            font=(
                "Arial",
                11,
                "bold",
            ),
            bg="#1e1e1e",
            fg="#AAAAAA",
        ).pack(
            pady=(10, 3)
        )

        tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=(
                "Arial",
                13,
                "bold",
            ),
            bg="#1e1e1e",
            fg="#FFFFFF",
            wraplength=780,
        ).pack(
            pady=(0, 12)
        )

        # --------------------------------------------------------
        # BIG LAUNCH BUTTON
        # --------------------------------------------------------

        self.launch_button = tk.Button(
            self.root,
            text="LAUNCH QUACKSINK.EXE",
            command=self.launch_quacksink,
            font=(
                "Arial",
                22,
                "bold",
            ),
            bg="#008855",
            fg="#FFFFFF",
            activebackground="#00AA66",
            activeforeground="#FFFFFF",
            height=2,
        )

        self.launch_button.pack(
            fill=tk.X,
            padx=60,
            pady=5,
        )

        # --------------------------------------------------------
        # Diagnostic
        # --------------------------------------------------------

        tk.Button(
            self.root,
            text="CHECK BROWSER / CDP",
            command=self.check_browser,
            font=(
                "Arial",
                11,
                "bold",
            ),
            bg="#444444",
            fg="#FFFFFF",
        ).pack(
            pady=15
        )

    # ------------------------------------------------------------

    def add_path_row(
        self,
        parent,
        label,
        variable,
        command,
    ) -> None:

        row = tk.Frame(
            parent,
            bg="#121212",
        )

        row.pack(
            fill=tk.X,
            pady=8,
        )

        tk.Label(
            row,
            text=label,
            width=16,
            anchor="e",
            font=(
                "Arial",
                12,
                "bold",
            ),
            bg="#121212",
            fg="#00FFCC",
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        tk.Entry(
            row,
            textvariable=variable,
            font=(
                "Arial",
                11,
            ),
            bg="#1e1e1e",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        tk.Button(
            row,
            text="Browse...",
            command=command,
            font=(
                "Arial",
                10,
                "bold",
            ),
            bg="#444444",
            fg="#FFFFFF",
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

    # ------------------------------------------------------------

    def populate_browser_dropdown(
        self,
    ) -> None:

        labels = [
            label
            for label, _path
            in self.browsers
        ]

        self.browser_combo[
            "values"
        ] = labels

        configured = (
            self.browser_path_var
            .get()
            .strip()
        )

        if configured:

            configured_normalized = (
                os.path.normcase(
                    os.path.abspath(
                        configured
                    )
                )
            )

            for (
                index,
                (_label, path),
            ) in enumerate(
                self.browsers
            ):

                found_normalized = (
                    os.path.normcase(
                        os.path.abspath(
                            path
                        )
                    )
                )

                if (
                    configured_normalized
                    == found_normalized
                ):

                    self.browser_combo.current(
                        index
                    )

                    self.browser_name_var.set(
                        self.browsers[index][0]
                    )

                    return

        if self.browsers:

            self.browser_combo.current(
                0
            )

            self.browser_name_var.set(
                self.browsers[0][0]
            )

            if not configured:

                self.browser_path_var.set(
                    self.browsers[0][1]
                )

    # ------------------------------------------------------------

    def rescan_browsers(
        self,
    ) -> None:

        self.browsers = (
            discover_installed_browsers()
        )

        self.populate_browser_dropdown()

        self.save_settings()

        count = len(
            self.browsers
        )

        self.status_var.set(
            (
                "Browser scan complete: "
                f"{count} recognized browser(s)."
            )
        )

        append_archive_log(
            self.active_archive,
            (
                "Browser rescan complete: "
                f"{count} browser(s)."
            ),
        )

    # ------------------------------------------------------------

    def browser_selected(
        self,
        _event=None,
    ) -> None:

        index = (
            self.browser_combo.current()
        )

        if not (
            0
            <= index
            < len(self.browsers)
        ):

            return

        label, path = (
            self.browsers[index]
        )

        self.browser_name_var.set(
            label
        )

        self.browser_path_var.set(
            path
        )

        self.save_settings()

        self.status_var.set(
            f"Selected {label}.\n{path}"
        )

        append_archive_log(
            self.active_archive,
            (
                f"Browser selected: "
                f"{label} -> {path}"
            ),
        )

    # ------------------------------------------------------------

    def startup_check(
        self,
    ) -> None:

        self.save_settings()

        if quacksink_is_running():

            self.status_var.set(
                "⚠ QuackSink.exe is already running."
            )

            append_archive_log(
                self.active_archive,
                (
                    "Startup check: "
                    "QuackSink.exe already running."
                ),
            )

            return

        qs_exe = (
            self.get_qs_exe()
        )

        if not qs_exe:

            self.status_var.set(
                "Choose the folder containing "
                "QuackSink.exe."
            )

            return

        browser = (
            self.get_browser_path()
        )

        if not browser:

            if self.browsers:

                count = len(
                    self.browsers
                )

                self.status_var.set(
                    (
                        f"Found {count} "
                        "recognized browser(s). "
                        "Select one."
                    )
                )

            else:

                self.status_var.set(
                    "No recognized Chromium-family "
                    "browser found. Use Browse..."
                )

            return

        if cdp_is_available():

            detected = (
                cdp_browser_name()
            )

            self.status_var.set(
                "BROWSER / CDP READY\n"
                + detected
            )

        else:

            browser_label = (
                self.browser_name_var
                .get()
                .strip()
                or browser.stem
            )

            self.status_var.set(
                f"{browser_label} selected.\n"
                "Remote debugging is not currently "
                "available on "
                f"port {CDP_PORT}."
            )

    # ------------------------------------------------------------

    def choose_browser(
        self,
    ) -> None:

        selected = (
            filedialog.askopenfilename(
                title=(
                    "Select the Chromium "
                    "browser executable"
                ),
                filetypes=[
                    (
                        "Executable files",
                        "*.exe",
                    ),
                    (
                        "All files",
                        "*.*",
                    ),
                ],
            )
        )

        if selected:

            self.browser_path_var.set(
                selected
            )

            self.browser_name_var.set(
                browser_name_from_path(
                    Path(selected)
                )
            )

            self.save_settings()

            self.startup_check()

    # ------------------------------------------------------------

    def choose_qs_dir(
        self,
    ) -> None:

        selected = (
            filedialog.askdirectory(
                title=(
                    "Select the folder containing "
                    "QuackSink.exe"
                ),
            )
        )

        if selected:

            self.qs_dir_var.set(
                selected
            )

            self.save_settings()

            self.startup_check()

    # ------------------------------------------------------------

    def get_browser_path(
        self,
    ) -> Path | None:

        value = (
            self.browser_path_var
            .get()
            .strip()
        )

        if not value:
            return None

        path = Path(
            value
        )

        if path.is_file():
            return path

        return None

    # ------------------------------------------------------------

    def get_qs_exe(
        self,
    ) -> Path | None:

        value = (
            self.qs_dir_var
            .get()
            .strip()
        )

        if not value:
            return None

        directory = Path(
            value
        )

        exe = (
            directory
            / QS_EXE_NAME
        )

        if exe.is_file():
            return exe

        return None

    # ------------------------------------------------------------

    def save_settings(
        self,
    ) -> None:

        self.config[
            "browser_path"
        ] = (
            self.browser_path_var
            .get()
            .strip()
        )

        self.config[
            "quacksink_dir"
        ] = (
            self.qs_dir_var
            .get()
            .strip()
        )

        self.config[
            "human_handle"
        ] = (
            self.handle_var
            .get()
            .strip()
            or "Cozmo"
        )

        save_qsl_config(
            self.config
        )

    # ------------------------------------------------------------

    def check_browser(
        self,
    ) -> None:

        if cdp_is_available():

            detected = (
                cdp_browser_name()
            )

            self.status_var.set(
                "BROWSER / CDP READY\n"
                + detected
            )

            append_archive_log(
                self.active_archive,
                (
                    "Manual CDP check: "
                    f"READY ({detected})."
                ),
            )

            messagebox.showinfo(
                "Browser / CDP",
                (
                    "Remote debugging is available."
                    "\n\n"
                    f"Detected browser:\n{detected}"
                    "\n\n"
                    f"Port: {CDP_PORT}"
                ),
            )

            return

        self.status_var.set(
            "No Chromium remote-debugging "
            "service detected on "
            f"port {CDP_PORT}."
        )

        append_archive_log(
            self.active_archive,
            (
                "Manual CDP check: NOT AVAILABLE "
                f"on port {CDP_PORT}."
            ),
        )

        messagebox.showwarning(
            "Browser / CDP",
            (
                "No usable Chromium "
                "remote-debugging endpoint "
                f"was detected on port {CDP_PORT}."
            ),
        )

    # ------------------------------------------------------------

    def launch_quacksink(
        self,
    ) -> None:

        self.save_settings()

        append_archive_log(
            self.active_archive,
            "Launch sequence started.",
        )

        # 1. Prevent duplicate QS.
        if quacksink_is_running():

            messagebox.showinfo(
                "QuackSink Already Running",
                (
                    "QuackSink.exe is already "
                    "running.\n\n"
                    "QSL will not start a "
                    "second instance."
                ),
            )

            append_archive_log(
                self.active_archive,
                (
                    "Launch aborted: "
                    "QuackSink.exe already running."
                ),
            )

            self.root.destroy()

            return

        # 2. Locate QS.
        qs_exe = (
            self.get_qs_exe()
        )

        if not qs_exe:

            messagebox.showerror(
                "QuackSink Not Found",
                (
                    "QSL could not find "
                    "QuackSink.exe.\n\n"
                    "Use Browse... to select "
                    "its directory."
                ),
            )

            return

        append_archive_log(
            self.active_archive,
            (
                "QuackSink executable selected: "
                f"{qs_exe}"
            ),
        )

        # 3. Human Handle.
        human_handle = (
            self.handle_var
            .get()
            .strip()
        )

        if not human_handle:

            messagebox.showerror(
                "Human Handle Required",
                (
                    "Enter a Human Handle "
                    "before launching "
                    "QuackSink."
                ),
            )

            return

        append_archive_log(
            self.active_archive,
            f"Human handle: {human_handle}",
        )

        # 4. Official EXE check.
        if not verify_quacksink_exe(
            self.config,
            qs_exe,
        ):

            append_archive_log(
                self.active_archive,
                (
                    "Launch aborted by official "
                    "executable verification decision."
                ),
            )

            return

        append_archive_log(
            self.active_archive,
            (
                "Official executable verification "
                "accepted."
            ),
        )

        # 5. Prepare existing QS config.
        try:

            qs_config = (
                prepare_qs_config(
                    qs_exe.parent,
                    human_handle,
                )
            )

            append_archive_log(
                self.active_archive,
                (
                    "QS configuration prepared: "
                    f"{qs_config}"
                ),
            )

            self.status_var.set(
                "QS configuration prepared.\n"
                + str(qs_config)
            )

        except Exception as exc:

            append_archive_log(
                self.active_archive,
                (
                    "QS configuration FAILED: "
                    f"{exc}"
                ),
            )

            messagebox.showerror(
                "QS Configuration Error",
                (
                    "QSL could not prepare "
                    "qs_config.json.\n\n"
                    f"{exc}"
                ),
            )

            return

        # 6. Prepare browser/CDP.
        if not cdp_is_available():

            browser = (
                self.get_browser_path()
            )

            if not browser:

                messagebox.showerror(
                    "Browser Not Configured",
                    (
                        "Select the Chromium "
                        "browser QSL should "
                        "launch."
                    ),
                )

                return

            browser_label = (
                self.browser_name_var
                .get()
                .strip()
                or browser.stem
            )

            self.status_var.set(
                f"Starting {browser_label} "
                "with remote debugging "
                f"on port {CDP_PORT}..."
            )

            if not prepare_browser(
                browser,
                self.active_archive,
            ):

                return

        else:

            append_archive_log(
                self.active_archive,
                (
                    f"CDP already available on "
                    f"port {CDP_PORT}; browser "
                    "launch skipped."
                ),
            )

        # 7. Create permanent launch BAT.
        try:

            launch_bat = (
                create_launch_bat(
                    self.active_archive,
                    qs_exe,
                )
            )

        except Exception as exc:

            append_archive_log(
                self.active_archive,
                (
                    "Launch BAT creation FAILED: "
                    f"{exc}"
                ),
            )

            messagebox.showerror(
                "Launch Script Error",
                (
                    "QSL could not create the "
                    "preserved QuackSink "
                    "launch BAT.\n\n"
                    f"{exc}"
                ),
            )

            return

        # 8. Final duplicate check.
        if quacksink_is_running():

            messagebox.showinfo(
                "QuackSink Already Running",
                (
                    "QuackSink.exe became "
                    "active before QSL could "
                    "launch it.\n\n"
                    "QSL will not launch a "
                    "second instance."
                ),
            )

            append_archive_log(
                self.active_archive,
                (
                    "Launch aborted: duplicate "
                    "QS detected immediately "
                    "before BAT launch."
                ),
            )

            self.root.destroy()

            return

        # 9. Launch QS through the BAT.
        try:

            process = (
                launch_quacksink_via_bat(
                    launch_bat,
                    qs_exe,
                )
            )

            append_archive_log(
                self.active_archive,
                (
                    "Launch BAT handed to "
                    f"cmd.exe. PID={process.pid}"
                ),
            )

        except Exception as exc:

            append_archive_log(
                self.active_archive,
                f"BAT launch FAILED: {exc}",
            )

            messagebox.showerror(
                "QuackSink Launch Failed",
                (
                    "QSL could not start "
                    "the QuackSink launch BAT."
                    "\n\n"
                    f"{launch_bat}\n\n"
                    f"Error:\n{exc}"
                ),
            )

            return

        # 10. QSL is finished.
        self.status_var.set(
            "QuackSink launch script handed "
            "to Windows. Closing launcher..."
        )

        append_archive_log(
            self.active_archive,
            (
                "QSL launch sequence completed; "
                "closing launcher."
            ),
        )

        self.root.after(
            150,
            self.root.destroy,
        )

    # ------------------------------------------------------------

    def run(
        self,
    ) -> None:

        self.root.mainloop()


# ================================================================
# SMALL HELPER
# ================================================================

def browser_name_from_path(
    path: Path,
) -> str:

    stem = path.stem.lower()

    names = {
        "opera": "Opera",
        "chrome": "Google Chrome",
        "msedge": "Microsoft Edge",
        "brave": "Brave",
    }

    return names.get(
        stem,
        path.stem,
    )


# ================================================================
# ENTRY POINT
# ================================================================

def main() -> None:

    launcher = (
        QuackSpaceLauncher()
    )

    launcher.run()


if __name__ == "__main__":
    main()