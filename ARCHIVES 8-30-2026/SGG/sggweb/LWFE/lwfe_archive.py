"""Create a no-overwrite, directory-based LWFE startup snapshot."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

APP_VERSION = "0.1.3"
EXCLUDED_ROOT_NAMES = {"archives", "__pycache__", ".git", ".venv", "venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak"}


def _include_root_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() not in EXCLUDED_SUFFIXES


def create_archive(project_root: Path, version: str = APP_VERSION) -> Path:
    """Create and return a new immutable session workspace under archives/.

    The desktop app uses the returned directory as the active output root for
    every render and playback during that application run. The archive itself
    is never copied recursively, and existing archives are never overwritten.
    """
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(f"LWFE project directory does not exist: {project_root}")

    archives_root = project_root / "archives"
    archives_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    timestamp = now.strftime("%b_%d_%Y_%I_%M_%S_%p")
    base_name = f"LWFE_{timestamp}_v{version}"
    destination = archives_root / base_name
    collision = 2
    while destination.exists():
        destination = archives_root / f"{base_name}_{collision:02d}"
        collision += 1

    # mkdir(exist_ok=False) is the final no-overwrite guard.
    destination.mkdir(parents=False, exist_ok=False)
    copied: list[str] = []

    try:
        (destination / "sounds").mkdir(exist_ok=True)

        # Copy the current source, folio JSON and project-side documentation.
        for source in sorted(project_root.iterdir(), key=lambda item: item.name.casefold()):
            if source.name.casefold() in EXCLUDED_ROOT_NAMES:
                continue
            if _include_root_file(source):
                target = destination / source.name
                shutil.copy2(source, target)
                copied.append(target.relative_to(destination).as_posix())

        # Carry forward any WAV masters that were already in the legacy/live
        # sounds folder when this session started.
        sounds_root = project_root / "sounds"
        if sounds_root.is_dir():
            for source in sorted(sounds_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
                if not source.is_file() or source.suffix.lower() != ".wav":
                    continue
                relative = source.relative_to(sounds_root)
                target = destination / "sounds" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(target.relative_to(destination).as_posix())

        manifest = [
            "Luma-Winslow Folio Engine (LWFE) — Session Workspace",
            f"Version: {version}",
            f"Created: {now.isoformat(timespec='seconds')}",
            "Snapshot timing: application startup (or explicit additional snapshot).",
            "Contents: current project files and lwfe.json, plus WAV files present in the legacy sounds/ folder at startup.",
            "SESSION OUTPUT: new RENDER operations in this application run write to this directory's sounds/ folder.",
            "PLAYBACK: the application checks this directory's sounds/ folder for WAV files.",
            "Archive policy: this directory is a session workspace and immutable history after the application closes; archives/ is never copied recursively.",
            "",
            "Files copied:",
        ]
        manifest.extend(f"- {name}" for name in copied)
        (destination / "ARCHIVE_MANIFEST.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return destination
