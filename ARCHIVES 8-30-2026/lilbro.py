#!/usr/bin/env python3
"""
lilbro.py 1.2

Select a QuackSink archive root directory and create/rebuild one .CARD file
inside each direct child directory that represents an archive.

Rules:
- A Windows folder-selection dialog chooses the root directory.
- Only directories directly under the selected root are examined.
- No recursive traversal into subdirectories.
- Every direct child directory gets a <dirname>.CARD file rebuilt/overwritten.
- The card lists all files directly inside that archive directory.
- If LOG.txt exists, its first valid timestamped record is used to determine
  the conversation/event date and that date is recorded in the CARD.
- If no valid LOG.txt timestamp can be found, the CARD records UNKNOWN and
  lilbro issues a warning.
- If <dirname>.CONVO exists, its complete CONVO header block is copied exactly.
- If luma.summary exists, its complete contents are copied into the CARD under
  a LUMA SUMMARY section.
- LOG.txt contents are otherwise not copied into the CARD.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

HEADER_START = "<CONVO HEADER START>"
HEADER_END = "<CONVO HEADER END>"

LOG_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s+\[[^\]]+\]"
)


LUMA_SUMMARY_NAME = "luma.summary"


def choose_root() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="LilBro 1.2 - Select QuackSink archive root"
        )
    finally:
        root.destroy()

    if not selected:
        return None
    return Path(selected)


def read_convo_header(convo_path: Path) -> list[str] | None:
    """Return the complete header block, without inventing/reformatting it."""
    try:
        lines = convo_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines(keepends=True)
    except OSError as exc:
        print(f"  WARNING: could not read {convo_path.name}: {exc}")
        return None

    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == HEADER_START:
            start = i
            break

    if start is None:
        print(f"  WARNING: no {HEADER_START} found in {convo_path.name}")
        return None

    for j in range(start + 1, len(lines)):
        if lines[j].rstrip("\r\n") == HEADER_END:
            return lines[start : j + 1]

    print(f"  WARNING: no {HEADER_END} found in {convo_path.name}")
    return None


def extract_conversation_date(log_path: Path) -> str | None:
    """
    Return the YYYY-MM-DD date from the first valid timestamped LOG record.

    The LOG itself is authoritative for the event/session date. Filesystem
    timestamps and archive-directory names are deliberately not consulted.
    """
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = LOG_TIMESTAMP_RE.match(line.rstrip("\r\n"))
                if match:
                    return match.group(1)
    except OSError as exc:
        print(f"  WARNING: could not read {log_path.name}: {exc}")
        return None

    return None


def read_luma_summary(summary_path: Path) -> list[str] | None:
    """Return the complete luma.summary contents without reformatting it."""
    try:
        return summary_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines(keepends=True)
    except OSError as exc:
        print(f"  WARNING: could not read {summary_path.name}: {exc}")
        return None


def build_card(archive_dir: Path) -> Path:
    card_path = archive_dir / f"{archive_dir.name}.CARD"
    convo_path = archive_dir / f"{archive_dir.name}.CONVO"
    log_path = archive_dir / "LOG.txt"
    summary_path = archive_dir / LUMA_SUMMARY_NAME

    files = sorted(
        (p for p in archive_dir.iterdir() if p.is_file()),
        key=lambda p: p.name.lower(),
    )

    conversation_date = None
    if log_path.is_file():
        conversation_date = extract_conversation_date(log_path)
        if conversation_date is None:
            print(
                f"  WARNING: {archive_dir.name}: LOG.txt contains no valid "
                "timestamped record; conversation date set to UNKNOWN."
            )
    else:
        print(
            f"  WARNING: {archive_dir.name}: LOG.txt not found; "
            "conversation date set to UNKNOWN."
        )

    lines: list[str] = [
        "<CARD HEADER START>\n",
        "QuackSink Archive Index Card\n",
        f"Archive: {archive_dir.name}\n",
        "Format: 1\n",
        f"Conversation date: {conversation_date or 'UNKNOWN'}\n",
        "<CARD HEADER END>\n",
        "\n",
        "FILES:\n",
    ]

    for path in files:
        lines.append(f"{path.name}\n")

    if convo_path.is_file():
        convo_header = read_convo_header(convo_path)
        if convo_header is not None:
            lines.append("\nCONVO HEADER:\n")
            lines.extend(convo_header)
            if not convo_header[-1].endswith(("\n", "\r")):
                lines.append("\n")

    if summary_path.is_file():
        luma_summary = read_luma_summary(summary_path)
        if luma_summary is not None:
            lines.append("\nLUMA SUMMARY:\n")
            lines.extend(luma_summary)
            if luma_summary and not luma_summary[-1].endswith(("\n", "\r")):
                lines.append("\n")

    try:
        card_path.write_text("".join(lines), encoding="utf-8", newline="")
    except OSError as exc:
        raise OSError(f"could not write {card_path}: {exc}") from exc

    return card_path


def main() -> int:
    root = choose_root()
    if root is None:
        print("No directory selected. Nothing done.")
        return 0

    if not root.is_dir():
        print(f"ERROR: selected path is not a directory: {root}", file=sys.stderr)
        return 1

    archive_dirs = sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.name.lower(),
    )

    print("LilBro 1.2")
    print(f"Root: {root}")
    print(f"Direct child directories found: {len(archive_dirs)}")
    print()

    processed = 0
    errors = 0
    unknown_dates = 0
    missing_summaries = 0

    for archive_dir in archive_dirs:
        try:
            card_path = build_card(archive_dir)
            processed += 1
            print(f"[OK] {archive_dir.name} -> {card_path.name}")

            log_path = archive_dir / "LOG.txt"
            if not log_path.is_file() or extract_conversation_date(log_path) is None:
                unknown_dates += 1

            summary_path = archive_dir / LUMA_SUMMARY_NAME
            if not summary_path.is_file():
                missing_summaries += 1
                print(f"  WARNING: {archive_dir.name}: {LUMA_SUMMARY_NAME} not found.")
        except OSError as exc:
            errors += 1
            print(f"[ERROR] {archive_dir.name}: {exc}", file=sys.stderr)

    print()
    print(f"Processed:          {processed}")
    print(f"Unknown dates:      {unknown_dates}")
    print(f"Missing luma.summary:{missing_summaries}")
    print(f"Errors:             {errors}")
    print("Done.")

    try:
        if errors:
            messagebox.showwarning(
                "LilBro 1.2 complete",
                f"Processed {processed} archive directories with {errors} error(s).\n\n"
                f"Unknown conversation dates: {unknown_dates}\n"
                f"Missing luma.summary files: {missing_summaries}\n\n"
                f"Root:\n{root}",
            )
        else:
            messagebox.showinfo(
                "LilBro 1.2 complete",
                f"Processed {processed} archive directories.\n\n"
                f"Unknown conversation dates: {unknown_dates}\n"
                f"Missing luma.summary files: {missing_summaries}\n\nRoot:\n{root}",
            )
    except tk.TclError:
        pass

    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
