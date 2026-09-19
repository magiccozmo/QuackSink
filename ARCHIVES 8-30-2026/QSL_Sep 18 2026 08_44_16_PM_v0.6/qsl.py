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


QSL_VERSION = "0.6"

QSL_CONFIG_FILE = "qsl_config.json"
QS_CONFIG_FILE = "qs_config.json"
QS_EXE_NAME = "QuackSink.exe"

QSL_LAUNCH_BAT_NAME = "QSL_launch_qs.bat"
BROWSER_LAUNCH_BAT_NAME = "openbrowser.bat"

ARCHIVES_DIR_NAME = "ARCHIVES"
QSL_ARCHIVE_PREFIX = "QSL_"

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

CDP_VERSION_URL = f"http://{CDP_HOST}:{CDP_PORT}/json/version"
CDP_LIST_URL = f"http://{CDP_HOST}:{CDP_PORT}/json/list"

BROWSER_READY_TIMEOUT = 30.0
BROWSER_POLL_INTERVAL = 0.50
BROWSER_STABLE_POLLS_REQUIRED = 4
BROWSER_FINAL_SETTLE_SECONDS = 2.0

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


BROWSER_DEFINITIONS = (
    ("Opera GX", ("opera gx",), ("opera.exe",)),
    ("Opera", ("opera",), ("opera.exe",)),
    ("Google Chrome", ("google chrome", "chrome"), ("chrome.exe",)),
    ("Microsoft Edge", ("microsoft edge",), ("msedge.exe",)),
    ("Brave", ("brave",), ("brave.exe",)),
)


def launcher_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def qsl_config_path() -> Path:
    return launcher_dir() / QSL_CONFIG_FILE


def archives_dir() -> Path:
    return launcher_dir() / ARCHIVES_DIR_NAME


def source_file_path() -> Path:
    return launcher_dir() / "qsl.py"


def timestamp_for_archive() -> str:
    return datetime.now().strftime("%b %d %Y %I_%M_%S_%p")


def create_unique_archive_dir() -> Path:
    root = archives_dir()
    root.mkdir(parents=True, exist_ok=True)

    while True:
        path = root / f"{QSL_ARCHIVE_PREFIX}{timestamp_for_archive()}_v{QSL_VERSION}"

        if not path.exists():
            path.mkdir(parents=True)
            return path

        time.sleep(60)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        f.write("\n")

    tmp.replace(path)


def load_qsl_config() -> dict:
    path = qsl_config_path()

    if not path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        cfg = DEFAULT_CONFIG.copy()

        if isinstance(data, dict):
            cfg.update(data)

        return cfg

    except Exception:
        return DEFAULT_CONFIG.copy()


def save_qsl_config(config: dict) -> None:
    save_json(qsl_config_path(), config)


def append_log(archive: Path, message: str) -> None:
    path = archive / "LOG.txt"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with path.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} [QSL] {message}\n")


def archive_startup(archive: Path) -> None:
    log = archive / "LOG.txt"

    lines = [
        "=============================================================",
        f"QuackSpace Launcher QSL {QSL_VERSION} STARTING",
        f"Startup timestamp: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
        f"Startup directory: {launcher_dir()}",
        f"Archive root: {archives_dir()}",
        f"Active archive: {archive}",
        f"Python executable: {sys.executable}",
        f"Frozen: {bool(getattr(sys, 'frozen', False))}",
        "-------------------------------------------------------------",
    ]

    src = source_file_path()

    if src.is_file():
        shutil.copy2(src, archive / "qsl.py")
        lines.append(f"Source archived: {archive / 'qsl.py'}")
    else:
        lines.append("Source archive skipped: qsl.py not found beside launcher.")

    cfg = qsl_config_path()

    if cfg.is_file():
        shutil.copy2(cfg, archive / QSL_CONFIG_FILE)
        lines.append(f"Configuration archived: {archive / QSL_CONFIG_FILE}")
    else:
        lines.append("Configuration not present at startup.")

    lines += [
        "=============================================================",
        "",
    ]

    log.write_text("\n".join(lines), encoding="utf-8")


def clean_registry_text(value: str) -> str:
    return os.path.expandvars(str(value or "").strip()).strip().strip('"')


def identify_browser(display_name: str, install_location: str, display_icon: str):
    text = " ".join(
        (display_name, install_location, display_icon)
    ).lower()

    for label, markers, exes in BROWSER_DEFINITIONS:
        if any(m in text for m in markers):
            return label, exes

    return None


def extract_executable(value: str) -> str:
    value = clean_registry_text(value)

    if not value:
        return ""

    p = Path(value)

    if p.is_file():
        return str(p)

    if '"' in value:
        for part in (x.strip() for x in value.split('"') if x.strip()):
            p = Path(os.path.expandvars(part))

            if p.is_file() and p.suffix.lower() == ".exe":
                return str(p)

    idx = value.lower().find(".exe")

    if idx >= 0:
        p = Path(
            os.path.expandvars(
                value[:idx + 4].strip().strip('"')
            )
        )

        if p.is_file():
            return str(p)

    return ""


def scan_uninstall_registry(root, base_key: str, access_flags: int = 0):
    found = []

    try:
        with winreg.OpenKey(
            root,
            base_key,
            0,
            winreg.KEY_READ | access_flags
        ) as parent:

            count = winreg.QueryInfoKey(parent)[0]

            for i in range(count):
                try:
                    child = winreg.EnumKey(parent, i)

                    with winreg.OpenKey(
                        parent,
                        child,
                        0,
                        winreg.KEY_READ | access_flags
                    ) as key:

                        def rv(name):
                            try:
                                v, _ = winreg.QueryValueEx(key, name)
                                return str(v or "")
                            except OSError:
                                return ""

                        dn = rv("DisplayName")
                        loc = rv("InstallLocation")
                        icon = rv("DisplayIcon")

                except OSError:
                    continue

                ident = identify_browser(dn, loc, icon)

                if not ident:
                    continue

                label, exes = ident

                exe = extract_executable(icon) if icon else ""

                if not exe and loc:
                    d = Path(os.path.expandvars(loc))

                    for name in exes:
                        candidate = d / name

                        if candidate.is_file():
                            exe = str(candidate)
                            break

                if exe:
                    found.append((label, exe))

    except OSError:
        pass

    return found


def fallback_browser_locations():
    local = Path(os.environ.get("LOCALAPPDATA", ""))

    pf = Path(
        os.environ.get(
            "PROGRAMFILES",
            r"C:\Program Files"
        )
    )

    pfx86 = Path(
        os.environ.get(
            "PROGRAMFILES(X86)",
            r"C:\Program Files (x86)"
        )
    )

    candidates = [
        (
            "Opera GX",
            local / "Programs" / "Opera GX" / "opera.exe"
        ),
        (
            "Opera",
            local / "Programs" / "Opera" / "opera.exe"
        ),
        (
            "Google Chrome",
            local / "Google" / "Chrome" / "Application" / "chrome.exe"
        ),
        (
            "Google Chrome",
            pf / "Google" / "Chrome" / "Application" / "chrome.exe"
        ),
        (
            "Google Chrome",
            pfx86 / "Google" / "Chrome" / "Application" / "chrome.exe"
        ),
        (
            "Microsoft Edge",
            pf / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        ),
        (
            "Microsoft Edge",
            pfx86 / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        ),
        (
            "Brave",
            local / "BraveSoftware" / "Brave-Browser"
            / "Application" / "brave.exe"
        ),
        (
            "Brave",
            pf / "BraveSoftware" / "Brave-Browser"
            / "Application" / "brave.exe"
        ),
    ]

    return [
        (label, str(path))
        for label, path in candidates
        if path.is_file()
    ]


def discover_installed_browsers():
    found = []

    targets = [
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        ),
    ]

    for root, key in targets:
        found.extend(
            scan_uninstall_registry(root, key)
        )

    wow = getattr(winreg, "KEY_WOW64_32KEY", 0)

    if wow:
        for root, key in targets:
            found.extend(
                scan_uninstall_registry(root, key, wow)
            )

    found.extend(fallback_browser_locations())

    seen = set()
    result = []

    priority = {
        "Opera GX": 0,
        "Opera": 1,
        "Google Chrome": 2,
        "Microsoft Edge": 3,
        "Brave": 4,
    }

    for label, path in found:
        norm = os.path.normcase(
            os.path.abspath(path)
        )

        if norm not in seen:
            seen.add(norm)
            result.append((label, path))

    result.sort(
        key=lambda x: (
            priority.get(x[0], 99),
            x[0].lower(),
            x[1].lower()
        )
    )

    return result


def prepare_qs_config(
    qs_dir: Path,
    human_handle: str
) -> Path:

    path = qs_dir / QS_CONFIG_FILE

    if path.exists():
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(data, dict):
                data = {}

        except Exception:
            data = {}

    else:
        data = {}

    data["human_handle"] = human_handle
    data.setdefault("nodes", [])

    save_json(
        path,
        data
    )

    return path


def quacksink_is_running() -> bool:

    try:

        p = subprocess.run(
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

        return (
            QS_EXE_NAME.lower()
            in p.stdout.lower()
        )

    except Exception:
        return False


def sha256_file(path: Path) -> str:

    h = hashlib.sha256()

    with path.open("rb") as f:

        while True:

            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def fetch_official_exe_hash(url: str):

    if not url:
        return None

    try:

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    "QuackSpace-Launcher-QSL"
            },
        )

        with urllib.request.urlopen(
            req,
            timeout=20
        ) as response:

            return hashlib.sha256(
                response.read()
            ).hexdigest()

    except Exception:
        return None


def verify_quacksink_exe(
    config: dict,
    exe_path: Path
) -> bool:

    local_hash = sha256_file(
        exe_path
    )

    url = str(
        config.get(
            "official_exe_url",
            OFFICIAL_EXE_URL
        )
    ).strip()

    official_hash = fetch_official_exe_hash(
        url
    )

    if not official_hash:

        return messagebox.askyesno(
            "Official QuackSink.exe Check Unavailable",
            "QSL could not verify this QuackSink.exe "
            "against the configured official repository binary.\n\n"
            f"Local SHA-256:\n{local_hash}\n\n"
            "The executable has NOT been verified as the "
            "current official release.\n\n"
            "Continue anyway?"
        )

    if (
        local_hash.lower()
        == official_hash.lower()
    ):
        return True

    return messagebox.askyesno(
        "WARNING — QuackSink.exe Is Not Official",
        "This QuackSink.exe does NOT match the current "
        "official repository executable.\n\n"
        f"Local SHA-256:\n{local_hash}\n\n"
        f"Official SHA-256:\n{official_hash}\n\n"
        "It may be an older, newer, or locally modified build.\n\n"
        "Continue anyway?"
    )


def cdp_is_available(timeout=1.0):

    try:

        req = urllib.request.Request(
            CDP_VERSION_URL,
            headers={
                "User-Agent":
                    "QuackSpace-Launcher-QSL"
            },
        )

        with urllib.request.urlopen(
            req,
            timeout=timeout
        ) as r:

            return r.status == 200

    except Exception:
        return False


def cdp_browser_name(timeout=1.0):

    try:

        req = urllib.request.Request(
            CDP_VERSION_URL,
            headers={
                "User-Agent":
                    "QuackSpace-Launcher-QSL"
            },
        )

        with urllib.request.urlopen(
            req,
            timeout=timeout
        ) as r:

            data = json.loads(
                r.read().decode(
                    "utf-8"
                )
            )

        return str(
            data.get(
                "Browser",
                "Unknown"
            )
        )

    except Exception:
        return "Unknown"


def get_cdp_pages(timeout=1.0):

    try:

        req = urllib.request.Request(
            CDP_LIST_URL,
            headers={
                "User-Agent":
                    "QuackSpace-Launcher-QSL"
            },
        )

        with urllib.request.urlopen(
            req,
            timeout=timeout
        ) as r:

            data = json.loads(
                r.read().decode(
                    "utf-8"
                )
            )

        return (
            data
            if isinstance(data, list)
            else []
        )

    except Exception:
        return []


def page_signature(pages):

    items = []

    for page in pages:

        if page.get("type") != "page":
            continue

        items.append(
            (
                str(
                    page.get(
                        "id",
                        ""
                    )
                ),
                str(
                    page.get(
                        "url",
                        ""
                    )
                ),
                str(
                    page.get(
                        "title",
                        ""
                    )
                ),
            )
        )

    items.sort()

    return tuple(items)


def wait_for_browser_ready(
    archive: Path
) -> bool:

    append_log(
        archive,
        "Browser readiness wait started."
    )

    deadline = (
        time.monotonic()
        + BROWSER_READY_TIMEOUT
    )

    last = None
    stable = 0
    max_pages = 0

    while time.monotonic() < deadline:

        if not cdp_is_available():

            append_log(
                archive,
                "Readiness failed: "
                "CDP endpoint disappeared."
            )

            return False

        sig = page_signature(
            get_cdp_pages()
        )

        page_count = len(sig)

        max_pages = max(
            max_pages,
            page_count
        )

        if page_count == 0:

            stable = 0
            last = None

        elif sig == last:

            stable += 1

        else:

            stable = 1
            last = sig

        append_log(
            archive,
            f"Readiness poll: pages={page_count}, "
            f"stable={stable}/"
            f"{BROWSER_STABLE_POLLS_REQUIRED}."
        )

        if stable >= BROWSER_STABLE_POLLS_REQUIRED:

            append_log(
                archive,
                "Page state reached required stability; "
                "final settle started."
            )

            settle_end = (
                time.monotonic()
                + BROWSER_FINAL_SETTLE_SECONDS
            )

            while time.monotonic() < settle_end:

                if not cdp_is_available():

                    append_log(
                        archive,
                        "Readiness failed during final settle: "
                        "CDP disappeared."
                    )

                    return False

                time.sleep(
                    0.25
                )

            final_sig = page_signature(
                get_cdp_pages()
            )

            if final_sig == sig:

                append_log(
                    archive,
                    "Browser READY for QuackSink launch. "
                    f"Stable page targets={page_count}; "
                    f"maximum observed={max_pages}."
                )

                return True

            append_log(
                archive,
                "Page state changed during final settle; "
                "resuming readiness polling."
            )

            stable = 0
            last = final_sig

        time.sleep(
            BROWSER_POLL_INTERVAL
        )

    append_log(
        archive,
        f"Browser readiness TIMEOUT after "
        f"{BROWSER_READY_TIMEOUT:.1f}s; "
        f"maximum observed page targets={max_pages}."
    )

    return False


# ----------------------------------------------------------------------
# BROWSER BAT CREATION
#
# QSL DOES NOT EXECUTE THIS BAT.
#
# It creates it, copies its full path to the clipboard, tells the
# human what to run, and stops the launch sequence.
# ----------------------------------------------------------------------

def create_browser_launch_bat(
    archive: Path,
    browser_path: Path
) -> Path:

    path = (
        archive
        / BROWSER_LAUNCH_BAT_NAME
    )

    contents = (
        "@echo off\r\n"
        f'cd /d "{browser_path.parent}"\r\n'
        f'"{browser_path}" '
        f'--remote-debugging-port={CDP_PORT}\r\n'
    )

    path.write_text(
        contents,
        encoding="utf-8"
    )

    append_log(
        archive,
        f"Browser launch BAT created: {path}"
    )

    append_log(
        archive,
        f"Browser BAT target: {browser_path}"
    )

    append_log(
        archive,
        f"Browser BAT CDP argument: "
        f"--remote-debugging-port={CDP_PORT}"
    )

    return path


def copy_to_clipboard(
    root,
    text: str
) -> bool:

    try:

        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()

        return True

    except Exception:
        return False


def prepare_browser(
    browser_path: Path,
    archive: Path,
    root
) -> bool:

    # Existing CDP means browser is already available.
    if cdp_is_available():

        append_log(
            archive,
            "CDP already available; "
            "browser launch BAT not required."
        )

        return True

    try:

        bat = create_browser_launch_bat(
            archive,
            browser_path
        )

    except Exception as exc:

        append_log(
            archive,
            f"Browser BAT creation FAILED: {exc}"
        )

        messagebox.showerror(
            "Browser Launch Script Failed",
            "QSL could not create the browser launch BAT.\n\n"
            f"{archive / BROWSER_LAUNCH_BAT_NAME}\n\n"
            f"Error:\n{exc}"
        )

        return False

    bat_path = str(
        bat.resolve()
    )

    copied = copy_to_clipboard(
        root,
        bat_path
    )

    if copied:

        append_log(
            archive,
            f"Full browser BAT path copied to clipboard: "
            f"{bat_path}"
        )

    else:

        append_log(
            archive,
            "WARNING: QSL could not copy browser BAT "
            "path to clipboard."
        )

    messagebox.showinfo(
        "Browser Launch Required",
        "QSL created the browser launch BAT.\n\n"
        "Run this batch file to start the browser:\n\n"
        f"{bat_path}\n\n"
        "The full path has been copied to your clipboard."
        if copied
        else
        "QSL created the browser launch BAT.\n\n"
        "Run this batch file to start the browser:\n\n"
        f"{bat_path}\n\n"
        "QSL could not copy the path to the clipboard."
    )

    append_log(
        archive,
        "Browser launch handed to human operator. "
        "QSL launch sequence paused."
    )

    return False


# ----------------------------------------------------------------------
# QUACKSINK BAT LAUNCH — UNCHANGED
# ----------------------------------------------------------------------

def create_launch_bat(
    archive: Path,
    qs_exe: Path
) -> Path:

    path = (
        archive
        / QSL_LAUNCH_BAT_NAME
    )

    path.write_text(
        f'@echo off\r\n'
        f'cd /d "{qs_exe.parent}"\r\n'
        f'"{qs_exe.name}"\r\n',
        encoding="utf-8"
    )

    append_log(
        archive,
        f"Launch BAT created: {path}"
    )

    return path


def launch_quacksink_via_bat(
    bat: Path,
    qs_exe: Path
):

    return subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            str(bat)
        ],
        cwd=str(qs_exe.parent)
    )


class QuackSpaceLauncher:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            f"QuackSpace Launcher QSL {QSL_VERSION}"
        )

        self.root.geometry(
            "920x700"
        )

        self.root.minsize(
            780,
            600
        )

        self.root.configure(
            bg="#121212"
        )

        self.config = load_qsl_config()

        self.active_archive = (
            create_unique_archive_dir()
        )

        archive_startup(
            self.active_archive
        )

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
                        ""
                    )
                )
            )
        )

        self.qs_dir_var = (
            tk.StringVar(
                value=str(
                    self.config.get(
                        "quacksink_dir",
                        ""
                    )
                )
            )
        )

        self.handle_var = (
            tk.StringVar(
                value=str(
                    self.config.get(
                        "human_handle",
                        "Cozmo"
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
            self.startup_check
        )

        append_log(
            self.active_archive,
            "QSL GUI initialized."
        )

    def build_ui(self):

        tk.Label(
            self.root,
            text="🪶 QUACKSPACE LAUNCHER",
            font=("Arial", 24, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            pady=(20, 5)
        )

        tk.Label(
            self.root,
            text=(
                f"QSL {QSL_VERSION} — "
                "prepare environment and launch QuackSink"
            ),
            font=("Arial", 11),
            bg="#121212",
            fg="#CCCCCC"
        ).pack(
            pady=(0, 20)
        )

        form = tk.Frame(
            self.root,
            bg="#121212"
        )

        form.pack(
            fill=tk.X,
            padx=30
        )

        bf = tk.Frame(
            form,
            bg="#121212"
        )

        bf.pack(
            fill=tk.X,
            pady=8
        )

        tk.Label(
            bf,
            text="Browser:",
            width=16,
            anchor="e",
            font=("Arial", 12, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        self.browser_combo = ttk.Combobox(
            bf,
            textvariable=self.browser_name_var,
            state="readonly",
            font=("Arial", 11)
        )

        self.browser_combo.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True
        )

        self.browser_combo.bind(
            "<<ComboboxSelected>>",
            self.browser_selected
        )

        tk.Button(
            bf,
            text="Rescan",
            command=self.rescan_browsers,
            font=("Arial", 10, "bold"),
            bg="#444444",
            fg="#FFFFFF"
        ).pack(
            side=tk.LEFT,
            padx=(8, 0)
        )

        self.add_path_row(
            form,
            "Browser EXE:",
            self.browser_path_var,
            self.choose_browser
        )

        self.add_path_row(
            form,
            "QuackSink:",
            self.qs_dir_var,
            self.choose_qs_dir
        )

        hf = tk.Frame(
            form,
            bg="#121212"
        )

        hf.pack(
            fill=tk.X,
            pady=10
        )

        tk.Label(
            hf,
            text="Human Handle:",
            width=16,
            anchor="e",
            font=("Arial", 12, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        tk.Entry(
            hf,
            textvariable=self.handle_var,
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#FFFFFF",
            insertbackground="#FFFFFF"
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True
        )

        sf = tk.Frame(
            self.root,
            bg="#1e1e1e",
            bd=1,
            relief=tk.SOLID
        )

        sf.pack(
            fill=tk.X,
            padx=30,
            pady=25
        )

        tk.Label(
            sf,
            text="STATUS",
            font=("Arial", 11, "bold"),
            bg="#1e1e1e",
            fg="#AAAAAA"
        ).pack(
            pady=(10, 3)
        )

        tk.Label(
            sf,
            textvariable=self.status_var,
            font=("Arial", 13, "bold"),
            bg="#1e1e1e",
            fg="#FFFFFF",
            wraplength=780
        ).pack(
            pady=(0, 12)
        )

        tk.Button(
            self.root,
            text="LAUNCH QUACKSINK.EXE",
            command=self.launch_quacksink,
            font=("Arial", 22, "bold"),
            bg="#008855",
            fg="#FFFFFF",
            activebackground="#00AA66",
            activeforeground="#FFFFFF",
            height=2
        ).pack(
            fill=tk.X,
            padx=60,
            pady=5
        )

        tk.Button(
            self.root,
            text="CHECK BROWSER / CDP",
            command=self.check_browser,
            font=("Arial", 11, "bold"),
            bg="#444444",
            fg="#FFFFFF"
        ).pack(
            pady=15
        )

    def add_path_row(
        self,
        parent,
        label,
        variable,
        command
    ):

        row = tk.Frame(
            parent,
            bg="#121212"
        )

        row.pack(
            fill=tk.X,
            pady=8
        )

        tk.Label(
            row,
            text=label,
            width=16,
            anchor="e",
            font=("Arial", 12, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        tk.Entry(
            row,
            textvariable=variable,
            font=("Arial", 11),
            bg="#1e1e1e",
            fg="#FFFFFF",
            insertbackground="#FFFFFF"
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True
        )

        tk.Button(
            row,
            text="Browse...",
            command=command,
            font=("Arial", 10, "bold"),
            bg="#444444",
            fg="#FFFFFF"
        ).pack(
            side=tk.LEFT,
            padx=(8, 0)
        )

    def populate_browser_dropdown(self):

        self.browser_combo["values"] = [
            label
            for label, _ in self.browsers
        ]

        configured = (
            self.browser_path_var.get().strip()
        )

        if configured:

            target = os.path.normcase(
                os.path.abspath(
                    configured
                )
            )

            for i, (_, path) in enumerate(
                self.browsers
            ):

                if target == os.path.normcase(
                    os.path.abspath(path)
                ):

                    self.browser_combo.current(i)

                    self.browser_name_var.set(
                        self.browsers[i][0]
                    )

                    return

        if self.browsers:

            self.browser_combo.current(0)

            self.browser_name_var.set(
                self.browsers[0][0]
            )

            if not configured:

                self.browser_path_var.set(
                    self.browsers[0][1]
                )

    def rescan_browsers(self):

        self.browsers = (
            discover_installed_browsers()
        )

        self.populate_browser_dropdown()
        self.save_settings()

        self.status_var.set(
            f"Browser scan complete: "
            f"{len(self.browsers)} recognized browser(s)."
        )

        append_log(
            self.active_archive,
            f"Browser rescan complete: "
            f"{len(self.browsers)} browser(s)."
        )

    def browser_selected(
        self,
        _event=None
    ):

        i = self.browser_combo.current()

        if 0 <= i < len(self.browsers):

            label, path = self.browsers[i]

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

            append_log(
                self.active_archive,
                f"Browser selected: "
                f"{label} -> {path}"
            )

    def startup_check(self):

        self.save_settings()

        if quacksink_is_running():

            self.status_var.set(
                "⚠ QuackSink.exe is already running."
            )

            return

        qs = self.get_qs_exe()

        if not qs:

            self.status_var.set(
                "Choose the folder containing QuackSink.exe."
            )

            return

        browser = self.get_browser_path()

        if not browser:

            self.status_var.set(
                f"Found {len(self.browsers)} "
                "recognized browser(s). Select one."
                if self.browsers
                else
                "No recognized Chromium-family "
                "browser found. Use Browse..."
            )

            return

        if cdp_is_available():

            self.status_var.set(
                "BROWSER / CDP READY\n"
                + cdp_browser_name()
            )

        else:

            name = (
                self.browser_name_var.get().strip()
                or browser.stem
            )

            self.status_var.set(
                f"{name} selected.\n"
                f"Remote debugging is not currently "
                f"available on port {CDP_PORT}."
            )

    def choose_browser(self):

        selected = filedialog.askopenfilename(
            title=(
                "Select the Chromium browser executable"
            ),
            filetypes=[
                (
                    "Executable files",
                    "*.exe"
                ),
                (
                    "All files",
                    "*.*"
                ),
            ]
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

    def choose_qs_dir(self):

        selected = filedialog.askdirectory(
            title=(
                "Select the folder containing "
                "QuackSink.exe"
            )
        )

        if selected:

            self.qs_dir_var.set(
                selected
            )

            self.save_settings()
            self.startup_check()

    def get_browser_path(self):

        p = Path(
            self.browser_path_var.get().strip()
        )

        return (
            p
            if p.is_file()
            else None
        )

    def get_qs_exe(self):

        d = Path(
            self.qs_dir_var.get().strip()
        )

        p = d / QS_EXE_NAME

        return (
            p
            if p.is_file()
            else None
        )

    def save_settings(self):

        self.config["browser_path"] = (
            self.browser_path_var.get().strip()
        )

        self.config["quacksink_dir"] = (
            self.qs_dir_var.get().strip()
        )

        self.config["human_handle"] = (
            self.handle_var.get().strip()
            or "Cozmo"
        )

        save_qsl_config(
            self.config
        )

    def check_browser(self):

        if cdp_is_available():

            name = cdp_browser_name()

            pages = len(
                page_signature(
                    get_cdp_pages()
                )
            )

            self.status_var.set(
                "BROWSER / CDP READY\n"
                + name
            )

            messagebox.showinfo(
                "Browser / CDP",
                "Remote debugging is available.\n\n"
                f"Detected browser:\n{name}\n\n"
                f"Page targets: {pages}\n\n"
                f"Port: {CDP_PORT}"
            )

        else:

            self.status_var.set(
                "No Chromium remote-debugging service "
                f"detected on port {CDP_PORT}."
            )

            messagebox.showwarning(
                "Browser / CDP",
                "No usable Chromium remote-debugging "
                f"endpoint was detected on port {CDP_PORT}."
            )

    def launch_quacksink(self):

        self.save_settings()

        append_log(
            self.active_archive,
            "Launch sequence started."
        )

        if quacksink_is_running():

            messagebox.showinfo(
                "QuackSink Already Running",
                "QuackSink.exe is already running.\n\n"
                "QSL will not start a second instance."
            )

            self.root.destroy()
            return

        qs = self.get_qs_exe()

        if not qs:

            messagebox.showerror(
                "QuackSink Not Found",
                "QSL could not find QuackSink.exe.\n\n"
                "Use Browse... to select its directory."
            )

            return

        handle = (
            self.handle_var.get().strip()
        )

        if not handle:

            messagebox.showerror(
                "Human Handle Required",
                "Enter a Human Handle before launching QuackSink."
            )

            return

        if not verify_quacksink_exe(
            self.config,
            qs
        ):

            append_log(
                self.active_archive,
                "Launch aborted by executable "
                "verification decision."
            )

            return

        try:

            cfg = prepare_qs_config(
                qs.parent,
                handle
            )

            append_log(
                self.active_archive,
                f"QS configuration prepared: {cfg}"
            )

        except Exception as exc:

            messagebox.showerror(
                "QS Configuration Error",
                "QSL could not prepare qs_config.json.\n\n"
                f"{exc}"
            )

            return

        # ----------------------------------------------------------
        # BROWSER PREPARATION
        #
        # If CDP is already alive, continue.
        #
        # If CDP is NOT alive:
        #   create openbrowser.bat
        #   copy its path
        #   tell human to run it
        #   STOP THIS QSL RUN
        #
        # The human then runs the BAT and starts QSL again.
        # ----------------------------------------------------------

        if not cdp_is_available():

            browser = self.get_browser_path()

            if not browser:

                messagebox.showerror(
                    "Browser Not Configured",
                    "Select the Chromium browser QSL should launch."
                )

                return

            name = (
                self.browser_name_var.get().strip()
                or browser.stem
            )

            self.status_var.set(
                f"{name} is not running with remote "
                f"debugging on port {CDP_PORT}.\n"
                "Preparing browser launch BAT..."
            )

            if not prepare_browser(
                browser,
                self.active_archive,
                self.root
            ):

                self.status_var.set(
                    "Browser launch BAT prepared.\n"
                    "Run the BAT, then run QSL again."
                )

                return

        # ----------------------------------------------------------
        # EXISTING POST-BROWSER READINESS CHECKS
        #
        # If this point is reached, CDP exists.
        # Confirm the browser/page targets are stable before QS.
        # ----------------------------------------------------------

        if not wait_for_browser_ready(
            self.active_archive
        ):

            messagebox.showwarning(
                "Browser Not Ready",
                "The browser is reachable through CDP, "
                "but its page targets did not reach the "
                "required stable state.\n\n"
                "QuackSink will not be launched."
            )

            return

        # ----------------------------------------------------------
        # EXISTING QUACKSINK LAUNCH PATH
        # ----------------------------------------------------------

        try:

            bat = create_launch_bat(
                self.active_archive,
                qs
            )

        except Exception as exc:

            messagebox.showerror(
                "Launch Script Error",
                "QSL could not create the preserved "
                "QuackSink launch BAT.\n\n"
                f"{exc}"
            )

            return

        if quacksink_is_running():

            messagebox.showinfo(
                "QuackSink Already Running",
                "QuackSink.exe became active before QSL "
                "could launch it.\n\n"
                "QSL will not launch a second instance."
            )

            self.root.destroy()
            return

        try:

            proc = launch_quacksink_via_bat(
                bat,
                qs
            )

            append_log(
                self.active_archive,
                f"Launch BAT handed to cmd.exe. "
                f"PID={proc.pid}"
            )

        except Exception as exc:

            messagebox.showerror(
                "QuackSink Launch Failed",
                "QSL could not start the QuackSink launch BAT.\n\n"
                f"{bat}\n\n"
                f"Error:\n{exc}"
            )

            return

        self.status_var.set(
            "QuackSink launch script handed to Windows. "
            "Closing launcher..."
        )

        append_log(
            self.active_archive,
            "QSL launch sequence completed; "
            "closing launcher."
        )

        self.root.after(
            150,
            self.root.destroy
        )

    def run(self):
        self.root.mainloop()


def browser_name_from_path(
    path: Path
) -> str:

    return {
        "opera": "Opera",
        "chrome": "Google Chrome",
        "msedge": "Microsoft Edge",
        "brave": "Brave",
    }.get(
        path.stem.lower(),
        path.stem
    )


def main():

    QuackSpaceLauncher().run()


if __name__ == "__main__":
    main()