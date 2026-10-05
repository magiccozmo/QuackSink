#!/usr/bin/env python3
"""BigBro 2.4

Build QuackSink conversation artifacts from LOG.txt files.

Compatibility target:
- Historical QS records where the timestamped [INFO] record is followed by
  the conversation payload on the next nonblank line.
- Newer QS records where the conversation payload begins on the same
  timestamped [INFO] line.

For each archive containing LOG.txt, BigBro creates/overwrites:
    <archive>.CONVO
    <archive>.CONVO.JSON

LOG.txt is never modified.

Safety retained from BigBro 2.2:
- Generic 🎩 / 🔮 speaker recognition.
- Generic speaker-prefix removal.
- [ANNOUNCE] support.
- Zero-message extraction never destroys existing transcript artifacts.
- Atomic output writes.
- Diagnostics are printed for auditability.
"""


import json
import re
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

TIMESTAMP_LOG_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>[^\]]+)\](?:\s(?P<body>.*))?$"
)
GENERIC_SPEAKER_RE = re.compile(
    r"^(?P<icon>[🎩🔮])\s*(?P<label>.+?)\s*-\s*"
)
ANNOUNCE_RE = re.compile(r"^\[ANNOUNCE\](?:\s|$)")


def parse_record(line: str):
    m = TIMESTAMP_LOG_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    raw_timestamp = f"{m.group('date')} {m.group('time')}"
    return raw_timestamp, m.group("level"), m.group("body")


def friendly_timestamp(raw: str) -> str:
    date_part, time_part = raw.split(" ", 1)
    year, month, day = map(int, date_part.split("-"))
    hour, minute, _second = map(int, time_part.split(":"))
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return f"{month}-{day}-{year % 100:02d} {display_hour}:{minute:02d}{suffix}"


def speaker_from_payload(first_line: str) -> str | None:
    """Return BigBro's historical speaker value for a payload header."""
    line = first_line.rstrip("\r\n")

    # Preserve BigBro 2.2 behavior for announcement records.
    if ANNOUNCE_RE.match(line):
        return "[ANNOUNCE]"

    m = GENERIC_SPEAKER_RE.match(line)
    if not m:
        return None

    icon = m.group("icon")
    label = m.group("label").strip()
    if not label:
        return None
    return f"{icon} {label}"


def clean_first_payload_line(line: str, speaker: str) -> str:
    """Remove only the structural prefix represented by the speaker header."""
    text = line.rstrip("\r\n")
    if speaker == "[ANNOUNCE]":
        return ANNOUNCE_RE.sub("", text, count=1).lstrip()

    m = GENERIC_SPEAKER_RE.match(text)
    return text[m.end():] if m else text


def extract_messages(lines: list[str]):
    results = []
    diagnostics = []
    n = len(lines)
    i = 0

    while i < n:
        record = parse_record(lines[i])
        if record is None:
            i += 1
            continue

        raw_timestamp, level, body = record

        # Only INFO records can contain conversation material. Other levels
        # remain diagnostics and are ignored.
        if level != "INFO":
            i += 1
            continue

        # ---------------------------------------------------------------
        # Format B: newer QS same-line conversation record.
        # Example:
        # 2026-10-02 10:46:08 [INFO] 🎩 Cozmo - message
        # 2026-10-02 10:17:49 [INFO] [ANNOUNCE] 🔮 Gemini - message
        # ---------------------------------------------------------------
        if body is not None and body.strip():
            speaker = speaker_from_payload(body)
            if speaker is not None:
                k = i + 1
                while k < n and parse_record(lines[k]) is None:
                    k += 1

                payload = [body] + lines[i + 1:k]
                while payload and payload[-1].strip() == "":
                    payload.pop()

                payload[0] = clean_first_payload_line(payload[0], speaker)
                if payload:
                    results.append((raw_timestamp, speaker, payload))

                i = k
                continue

        # ---------------------------------------------------------------
        # Format A: historical QS two-line conversation record.
        # Example:
        # 2026-10-02 07:24:45 [INFO]
        # [ANNOUNCE] 🔮 GPT - message
        # ---------------------------------------------------------------
        if body is None or not body.strip():
            j = i + 1
            while j < n and lines[j].strip() == "":
                j += 1

            if j >= n:
                diagnostics.append(
                    f"line {i + 1}: trailing bare [INFO] record with no payload"
                )
                break

            # If the next line is another timestamped record, this bare INFO
            # had no payload at all.
            if parse_record(lines[j]) is not None:
                diagnostics.append(
                    f"line {i + 1}: bare [INFO] record followed by another log record"
                )
                i += 1
                continue

            first_payload = lines[j].rstrip("\r\n")
            speaker = speaker_from_payload(first_payload)
            if speaker is None:
                diagnostics.append(
                    f"line {i + 1}: skipped bare [INFO] record; "
                    f"unknown/non-conversation payload: {first_payload[:160]!r}"
                )
                i += 1
                continue

            k = j + 1
            while k < n and parse_record(lines[k]) is None:
                k += 1

            payload = lines[j:k].copy()
            while payload and payload[-1].strip() == "":
                payload.pop()

            if payload:
                payload[0] = clean_first_payload_line(payload[0], speaker)
                results.append((raw_timestamp, speaker, payload))

            i = k
            continue

        # INFO record with same-line non-conversation content.
        # Keep it out of the transcript without treating it as an error.
        i += 1

    return results, diagnostics


def make_transcript(archive_dir: Path, messages) -> str:
    out = [
        "<CONVO HEADER START>\n",
        "QuackSink Conversation Transcript\n",
        f"Archive: {archive_dir.name}\n",
        "Source: LOG.txt\n",
        "Format: 1\n",
        "<CONVO HEADER END>\n",
        "\n",
    ]

    for raw_timestamp, speaker, payload in messages:
        out.append(f"{friendly_timestamp(raw_timestamp)}  {speaker}\n")
        for line in payload:
            out.append(line)
            if not line.endswith(("\n", "\r")):
                out.append("\n")
        out.append("\n")

    return "".join(out)


def make_convo_json(archive_dir: Path, messages) -> str:
    records = []
    for sequence, (raw_timestamp, speaker, payload) in enumerate(messages, start=1):
        text = "".join(
            line if line.endswith(("\n", "\r")) else line + "\n"
            for line in payload
        ).rstrip("\r\n")
        records.append(
            {
                "sequence": sequence,
                "timestamp": raw_timestamp,
                "display_timestamp": friendly_timestamp(raw_timestamp),
                "speaker": speaker,
                "text": text,
            }
        )

    document = {
        "format": 1,
        "type": "QuackSink Conversation JSON",
        "archive": archive_dir.name,
        "source": "LOG.txt",
        "message_count": len(records),
        "messages": records,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="")
        temp.replace(path)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass


def process_archive(archive_dir: Path):
    log_path = archive_dir / "LOG.txt"
    if not log_path.is_file():
        return "skipped", 0, [], None

    try:
        lines = log_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines(keepends=True)
        messages, diagnostics = extract_messages(lines)

        if not messages:
            return "zero", 0, diagnostics, None

        convo_path = archive_dir / f"{archive_dir.name}.CONVO"
        json_path = archive_dir / f"{archive_dir.name}.CONVO.JSON"

        atomic_write(convo_path, make_transcript(archive_dir, messages))
        atomic_write(json_path, make_convo_json(archive_dir, messages))

        return "processed", len(messages), diagnostics, None
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        return "error", 0, [], str(exc)


def choose_root() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    root.update()
    selected = filedialog.askdirectory(title="Select the QuackSink archive root")
    root.destroy()
    if not selected:
        return None
    return Path(selected)


def main() -> int:
    root = choose_root()
    if root is None:
        print("No directory selected. BigBro 2.4 cancelled.")
        return 0
    if not root.is_dir():
        print(f"ERROR: selected path is not a directory: {root}", file=sys.stderr)
        return 1

    processed = skipped = errors = zero = messages = 0
    total_diagnostics = 0
    details = []

    try:
        children = sorted(
            (p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()
        )
    except OSError as exc:
        print(f"ERROR: cannot read selected directory: {exc}", file=sys.stderr)
        return 1

    for child in children:
        status, count, diagnostics, error = process_archive(child)
        details.append((child.name, status, count, diagnostics, error))
        total_diagnostics += len(diagnostics)

        if status == "processed":
            processed += 1
            messages += count
        elif status == "skipped":
            skipped += 1
        elif status == "zero":
            zero += 1
        else:
            errors += 1

    print("\nBigBro 2.4")
    print(f"Root: {root}")
    print(f"Direct child directories examined: {len(children)}")
    print(f"Processed (LOG.txt found): {processed}")
    print(f"Skipped (no LOG.txt): {skipped}")
    print(f"Zero-message / NOT OVERWRITTEN: {zero}")
    print(f"Errors: {errors}")
    print(f"Total message blocks extracted: {messages}")
    print(f"Diagnostics emitted: {total_diagnostics}")

    for name, status, count, diagnostics, error in details:
        if diagnostics:
            print(f"\n[{name}] {len(diagnostics)} diagnostic(s):")
            for item in diagnostics:
                print(f"  - {item}")
        if error:
            print(f"\n[{name}] ERROR: {error}")

    try:
        message = (
            f"BigBro 2.4 finished.\n\n"
            f"Processed: {processed}\n"
            f"Skipped: {skipped}\n"
            f"Zero-message / not overwritten: {zero}\n"
            f"Errors: {errors}\n"
            f"Message blocks: {messages}\n"
            f"Diagnostics: {total_diagnostics}"
        )
        app = tk.Tk()
        app.withdraw()
        if errors or zero:
            messagebox.showwarning("BigBro 2.4", message)
        else:
            messagebox.showinfo("BigBro 2.4", message)
        app.destroy()
    except tk.TclError:
        pass

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
