"""Project Qtip v0.3
Privacy-safe browser ownership/persistence probe.

Qtip v0.2 intentionally does NOT inspect or modify the user's existing
browser profile. It creates/uses a dedicated Qtip Chromium profile and
keeps potentially sensitive browser state outside the archive.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

VERSION = "0.3"
PROJECT = "QTIP"
APP_NAME = "Project Qtip"
PROFILE_DIRNAME = "QTIP_BROWSER_PROFILE"
ARCHIVE_DIRNAME = "ARCHIVES"
LOG_NAME = "log.txt"

HOME = Path.home()
WORK_DIR = Path(__file__).resolve().parent
ARCHIVE_ROOT = WORK_DIR / ARCHIVE_DIRNAME
PROFILE_DIR = WORK_DIR / PROFILE_DIRNAME

# Privacy: these are deliberately coarse. Qtip never logs raw secrets/state.
SECRET_QUERY_KEYS = {
    "code", "token", "auth", "authorization", "access_token", "refresh_token",
    "id_token", "session", "session_id", "sid", "key", "secret", "password",
    "passwd", "credential", "credentials", "challenge", "cf_chl_tk", "__cf_chl_rt_tk",
    "sig", "signature", "jwt", "assertion", "saml", "state", "nonce",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
WIN_USER_PATH_RE = re.compile(r"([A-Za-z]:\\Users\\)[^\\\s'\"]+", re.I)
MAC_USER_PATH_RE = re.compile(r"(/Users/)[^/\s'\"]+", re.I)
TOKENISH_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|AIza[0-9A-Za-z_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,})\b")


@dataclass
class Archive:
    path: Path
    log_path: Path


def now_stamp() -> str:
    return datetime.now().strftime("%b %d %Y %I_%M_%S_%p")


def make_unique_archive(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    while True:
        stamp = now_stamp()
        candidate = root / f"{PROJECT}_{stamp}_v{VERSION}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            # Timestamp collision: sleep briefly then retry.
            import time
            time.sleep(1)


def privacy_url(url: str) -> str:
    """Return a URL safe enough for diagnostics: origin/path only; query removed."""
    if not url:
        return "<empty-url>"
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url)
        if not p.scheme or not p.netloc:
            return redact_text(url)
        path = p.path or "/"
        # Fragment can also contain state/token data; omit it.
        return f"{p.scheme}://{p.netloc}{path}"
    except Exception:
        return "<unparseable-url>"


def redact_text(text: object) -> str:
    """Conservative privacy scrub for anything that reaches the log."""
    s = str(text)
    s = WIN_USER_PATH_RE.sub(r"\1<USER>", s)
    s = MAC_USER_PATH_RE.sub(r"\1<USER>", s)
    s = EMAIL_RE.sub("<EMAIL>", s)
    s = TOKENISH_RE.sub("<REDACTED_TOKEN>", s)
    # Strip obvious key=value secret material from arbitrary diagnostics.
    pattern = re.compile(
        r"(?i)(?:" + "|".join(re.escape(k) for k in sorted(SECRET_QUERY_KEYS, key=len, reverse=True)) +
        r")=([^&\s,'\"]+)"
    )
    s = pattern.sub(lambda m: f"{m.group(0).split('=')[0]}=<REDACTED>", s)
    return s


def redact_path(path: Path) -> str:
    try:
        p = path.resolve()
    except Exception:
        return "<PATH>"
    s = str(p)
    s = WIN_USER_PATH_RE.sub(r"\1<USER>", s)
    s = MAC_USER_PATH_RE.sub(r"\1<USER>", s)
    return s


def log_line(archive: Archive, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe = redact_text(message)
    line = f"{stamp} [{PROJECT}] {safe}\n"
    with archive.log_path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def write_source_snapshot(archive: Archive) -> None:
    """Archive the exact qtip.py that produced the run."""
    src = Path(__file__).resolve()
    dst = archive.path / src.name
    if src != dst:
        shutil.copy2(src, dst)


def browser_process_survey(archive: Archive) -> None:
    log_line(archive, "BROWSER SURVEY: starting process survey (diagnostic only; no browser modification).")
    if platform.system() != "Windows":
        log_line(archive, f"BROWSER SURVEY: platform={platform.system()} (Windows process survey skipped).")
        return
    try:
        # Avoid dumping command lines, which may contain sensitive arguments.
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Where-Object { $_.ProcessName -match '^(opera|chrome|msedge|brave|firefox)$' } | Select-Object ProcessName,Id,SessionId,WorkingSet64 | Format-Table -HideTableHeaders"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        count = 0
        for raw in ps.stdout.splitlines():
            bits = raw.split()
            if len(bits) >= 4:
                count += 1
                log_line(archive, f"BROWSER PROCESS: name={bits[0]} pid={bits[1]} session={bits[2]} memory={bits[3]}")
        log_line(archive, f"BROWSER SURVEY: {count} supported browser process entries logged.")
    except Exception as exc:
        log_line(archive, f"BROWSER SURVEY ERROR: {type(exc).__name__}")


async def persistent_profile_probe(archive: Archive) -> None:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        log_line(archive, f"PLAYWRIGHT IMPORT: FAILED ({type(exc).__name__})")
        return

    log_line(archive, "PLAYWRIGHT IMPORT: OK")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    log_line(archive, f"QTIP PROFILE: {redact_path(PROFILE_DIR)}")
    log_line(archive, "QTIP PROFILE: dedicated profile only; existing Human browser profile is never opened or modified.")

    test_url = "https://chatgpt.com/"
    async with async_playwright() as p:
        context = None
        try:
            log_line(archive, f"VISIBLE SETUP: launching Qtip-owned Chromium at {test_url}")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1200, "height": 800},
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(test_url, wait_until="domcontentloaded", timeout=45_000)
            log_line(archive, f"VISIBLE SETUP NAVIGATED: url={privacy_url(page.url)}")
            log_line(archive, "VISIBLE SETUP: Leave the Qtip window open for this test; close it yourself when ready to continue.")
            # Wait for explicit human confirmation in terminal, without scraping page content.
            await asyncio.to_thread(input, "\nQtip v0.3 setup: browser is open. Complete any desired login/setup, then press ENTER here to continue... ")
        except Exception as exc:
            log_line(archive, f"VISIBLE SETUP ERROR: {type(exc).__name__}")
        finally:
            if context is not None:
                try:
                    await context.close()
                    log_line(archive, "VISIBLE SETUP: browser closed cleanly.")
                except Exception as exc:
                    log_line(archive, f"VISIBLE SETUP CLOSE ERROR: {type(exc).__name__}")

        # Headless restart probe.
        try:
            log_line(archive, "HEADLESS PROBE: reopening the same Qtip-owned persistent profile.")
            context2 = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=True,
            )
            try:
                page2 = context2.pages[0] if context2.pages else await context2.new_page()
                await page2.goto(test_url, wait_until="domcontentloaded", timeout=45_000)
                # Only safe, coarse telemetry.
                cookies = await context2.cookies()
                local_storage_count = await page2.evaluate("() => { try { return window.localStorage.length } catch(e) { return -1 } }")
                session_storage_count = await page2.evaluate("() => { try { return window.sessionStorage.length } catch(e) { return -1 } }")
                safe_url = privacy_url(page2.url)
                title_present = False
                try:
                    title_present = bool(await page2.title())
                except Exception:
                    title_present = False

                # Coarse ChatGPT auth heuristic. Never log page text or matched values.
                login_marker_count = -1
                app_marker_count = -1
                try:
                    login_marker_count = await page2.locator(
                        "a[href*='/auth/login'], button:has-text('Log in'), button:has-text('Sign in')"
                    ).count()
                except Exception:
                    pass
                try:
                    app_marker_count = await page2.locator(
                        "textarea, [contenteditable='true'], button[aria-label*='Send']"
                    ).count()
                except Exception:
                    pass

                if login_marker_count > 0:
                    auth_state = "NOT_AUTHENTICATED_LIKELY"
                elif login_marker_count == 0 and app_marker_count > 0:
                    auth_state = "AUTHENTICATED_LIKELY"
                elif "challenge" in safe_url.lower():
                    auth_state = "CHALLENGE_OR_BLOCKED"
                else:
                    auth_state = "UNKNOWN"

                log_line(archive, f"HEADLESS PROBE: final_url={safe_url}")
                log_line(archive, f"HEADLESS PROBE: title_present={title_present}")
                log_line(archive, f"HEADLESS PROBE: cookies_count={len(cookies)} localStorageEntries={local_storage_count} sessionStorageEntries={session_storage_count}")
                log_line(archive, f"CHATGPT AUTH STATE: {auth_state}")
                log_line(archive, "HEADLESS PROBE: completed successfully.")
                if auth_state == "AUTHENTICATED_LIKELY":
                    log_line(archive, "QTIP RESULT: authentication state appears to have survived restart inside the Qtip-owned persistent profile.")
                elif auth_state == "NOT_AUTHENTICATED_LIKELY":
                    log_line(archive, "QTIP RESULT: profile reopened, but authentication does not appear to have persisted.")
                elif auth_state == "CHALLENGE_OR_BLOCKED":
                    log_line(archive, "QTIP RESULT: browser reopened, but the site presented a challenge/block state.")
                else:
                    log_line(archive, "QTIP RESULT: browser reopened, but authentication state could not be determined safely.")
            finally:
                await context2.close()
        except Exception as exc:
            log_line(archive, f"HEADLESS PROBE ERROR: {type(exc).__name__}")


def main() -> int:
    archive_path = make_unique_archive(ARCHIVE_ROOT)
    archive = Archive(archive_path, archive_path / LOG_NAME)
    write_source_snapshot(archive)
    log_line(archive, "=============================================================")
    log_line(archive, f"{APP_NAME} {VERSION} STARTING")
    log_line(archive, f"Startup timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_line(archive, f"Startup directory: {redact_path(WORK_DIR)}")
    log_line(archive, f"Archive root: {redact_path(ARCHIVE_ROOT)}")
    log_line(archive, f"Active archive: {redact_path(archive_path)}")
    log_line(archive, f"Python executable: {redact_path(Path(sys.executable))}")
    log_line(archive, f"Frozen: {getattr(sys, 'frozen', False)}")
    log_line(archive, f"Platform: {platform.platform()}".replace(str(HOME), "<USER_HOME>"))
    log_line(archive, f"Python: {platform.python_version()} ({platform.python_implementation()})")
    log_line(archive, f"Machine: {platform.machine()}")
    log_line(archive, f"Source archived: {redact_path(archive_path / Path(__file__).name)}")
    log_line(archive, "PRIVACY POLICY: no cookie values, storage values, response text, DOM text, account identifiers, command lines, or credential-bearing URLs are written to log.txt.")
    log_line(archive, "=============================================================")

    browser_process_survey(archive)
    try:
        asyncio.run(persistent_profile_probe(archive))
    except KeyboardInterrupt:
        log_line(archive, "QTIP STOPPED: keyboard interrupt.")
        return 130
    except Exception as exc:
        log_line(archive, f"QTIP FATAL ERROR: {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
