#!/usr/bin/env python3
"""
Purple Python — IA public-library record builder v2

Builds the curated Internet Archive staging tree from:
    D:/QuackSink/ARCHIVES 8-30-2026/
    D:/QuackSink/Purple Python/IA_INDEX.LST

OUTPUT:
    D:/QuackSink/Purple Python/ARCHIVES 8-30-2026/
        LUMA INDEX.TXT
        <one curated .txt record per approved archive>

READ-ONLY SOURCE:
    The real QuackSink archive is never modified.

IMPORTANT v2 FIX:
    The previous builder treated metadata lines embedded in IA_INDEX.LST
    (ARCHIVE:, CANONICAL REPOSITORY:, GitHub URL, separators, etc.) as part
    of the summary. That produced pages of repeated metadata in each record.

    v2 strips those manifest metadata lines before creating the summary.
    It also removes repeated copies of the same metadata block.

Record format:
    archive name
    canonical GitHub URL
    summary
    complete .CONVO

Public filename rule:
    PROGRAM_vVERSION_Mon_DD_YYYY_HH_MM_SSAM.txt

Examples:
    QS_v6.53_Sep_29_2026_12_14_13PM.txt
    MMRC_Aug_29_2026_01_22_40AM.txt
    PPR_v1.0_Oct_07_2026_02_33_17AM.txt

This program does NOT upload anything.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import quote

SOURCE_ROOT = Path(r"D:\QuackSink\ARCHIVES 8-30-2026")
PURPLE_ROOT = Path(r"D:\QuackSink\Purple Python")
MANIFEST = PURPLE_ROOT / "IA_INDEX.LST"
OUTPUT_ROOT = PURPLE_ROOT / "ARCHIVES 8-30-2026"

GITHUB_BASE = (
    "https://github.com/magiccozmo/QuackSink/tree/main/"
    "ARCHIVES%208-30-2026/"
)

SEPARATOR_RE = re.compile(r"^[-=*_]+\s*$")
TIMESTAMP_RE = re.compile(
    r"(?:^|_)(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})\s+"
    r"(?P<hour>\d{1,2})_(?P<minute>\d{2})_(?P<second>\d{2})_"
    r"(?P<ampm>AM|PM)(?=$|_)"
    , re.IGNORECASE,
)


def fail(message: str) -> None:
    print("\nERROR:\n" + message + "\n")
    raise SystemExit(1)


def is_metadata_line(line: str) -> bool:
    """Lines that are NOT summary text in the manifest."""
    s = line.strip()
    if not s:
        return False
    if SEPARATOR_RE.fullmatch(s):
        return True
    if s.upper() in {
        "SUMMARY:",
        "ARCHIVE:",
        "CANONICAL REPOSITORY:",
        "CANONICAL REPOSITORY",
    }:
        return True
    if s.upper().startswith("ARCHIVE:"):
        return True
    if s.upper().startswith("CANONICAL REPOSITORY:"):
        return True
    if s.lower().startswith("https://github.com/magiccozmo/quacksink/"):
        return True
    return False


def clean_summary(text: str, archive_name: str) -> str:
    """
    Remove manifest metadata and repeated copies of metadata blocks.

    We intentionally do NOT globally deduplicate ordinary summary sentences;
    only known metadata lines are removed. This keeps genuine summary text
    intact.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    blank = False

    for raw in lines:
        line = raw.strip()
        if not line:
            if out:
                blank = True
            continue

        # Exact archive name can occur in a malformed manifest metadata block.
        if line == archive_name:
            continue

        if is_metadata_line(line):
            continue

        if blank and out:
            out.append("")
        blank = False
        out.append(line)

    return "\n".join(out).strip()


def github_url(dirname: str) -> str:
    return GITHUB_BASE + quote(dirname, safe="")


def public_filename(dirname: str) -> str:
    """Convert exact archive directory name to public IA filename."""
    match = TIMESTAMP_RE.search(dirname)
    if not match:
        fail(f"Could not find timestamp in archive name:\n{dirname}")

    before = dirname[:match.start()].rstrip(" _")
    after = dirname[match.end():].strip(" _")

    program = before
    if program.upper().endswith("_ARC"):
        program = program[:-4]

    version = ""
    version_match = re.fullmatch(r"v(.+)", after, re.IGNORECASE)
    if version_match:
        version = version_match.group(1).strip(" _")
    elif after:
        fail(
            "Unexpected text after timestamp in archive name:\n"
            f"{dirname}\nSuffix: {after}"
        )

    month = match.group("month").title()
    day = int(match.group("day"))
    year = match.group("year")
    hour = match.group("hour")
    minute = match.group("minute")
    second = match.group("second")
    ampm = match.group("ampm").upper()

    public_date = f"{month}_{day:02d}_{year}_{hour}_{minute}_{second}{ampm}"
    if version:
        return f"{program}_v{version}_{public_date}.txt"
    return f"{program}_{public_date}.txt"


def find_direct_convos(archive_dir: Path) -> list[Path]:
    """
    Find .CONVO files belonging to this archive.

    For normal archive cards the .CONVO is directly in the archive directory.
    If there isn't one there, we allow a single nested .CONVO because a few
    older archive cards contain a captured conversation below the card root.
    """
    direct = sorted(
        p for p in archive_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".convo" and p.stat().st_size > 0
    )
    if direct:
        return direct

    nested = sorted(
        p for p in archive_dir.rglob("*.CONVO")
        if p.is_file() and p.stat().st_size > 0
    )
    return nested


def find_local_luma_summary(archive_dir: Path) -> str | None:
    candidates = sorted(
        p for p in archive_dir.rglob("*")
        if p.is_file() and p.name.lower() == "luma.summary"
    )
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cleaned = clean_summary(text, archive_dir.name)
        if not cleaned:
            continue
        if "NO MESSAGES RECORDED in the conversation artifact" in cleaned.upper():
            continue
        return cleaned
    return None


def parse_manifest(path: Path) -> list[tuple[str, str]]:
    """
    Parse IA_INDEX.LST.

    An entry starts with an EXACT top-level archive directory name.
    The next exact archive-directory name starts the next entry.
    Separators and legacy metadata are ignored wherever they appear; they
    are NOT treated as entry boundaries because older IA_INDEX files may use
    a separator between metadata and the actual summary.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        fail(f"Could not read manifest:\n{path}\n{exc}")

    source_names = {
        p.name for p in SOURCE_ROOT.iterdir() if p.is_dir()
    }

    entries: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_lines
        if current_name is None:
            current_lines = []
            return
        summary = clean_summary("\n".join(current_lines), current_name)
        entries.append((current_name, summary))
        current_name = None
        current_lines = []

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()

        if line in source_names:
            if current_name is not None:
                flush()
            current_name = line
            current_lines = []
            continue

        if current_name is None:
            continue

        current_lines.append(line)

    flush()

    # First occurrence wins; duplicate manifest entries are not emitted twice.
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for name, summary in entries:
        if name in seen:
            continue
        seen.add(name)
        deduped.append((name, summary))

    return deduped

def record_text(
    archive_name: str,
    repo_url: str,
    summary: str,
    convo_text: str,
) -> str:
    """Build exactly one clean public IA record."""
    parts = [
        "=" * 72,
        "PURPLE PYTHON ARCHIVE RECORD",
        "=" * 72,
        "",
        f"ARCHIVE: {archive_name}",
        "",
        "CANONICAL REPOSITORY:",
        repo_url,
        "",
        "=" * 72,
        "SUMMARY",
        "=" * 72,
        "",
        summary.strip(),
        "",
        "=" * 72,
        "FULL CONVERSATION",
        "=" * 72,
        "",
        convo_text.rstrip(),
        "",
        "=" * 72,
        "END RECORD",
        "=" * 72,
        "",
    ]
    return "\n".join(parts)

def main() -> int:
    print()
    print("=" * 72)
    print(" PURPLE PYTHON — IA RECORD BUILDER v2")
    print("=" * 72)
    print()

    if not SOURCE_ROOT.is_dir():
        fail(f"Source archive directory not found:\n{SOURCE_ROOT}")
    if not PURPLE_ROOT.is_dir():
        fail(f"Purple Python directory not found:\n{PURPLE_ROOT}")
    if not MANIFEST.is_file():
        fail(f"IA_INDEX.LST not found:\n{MANIFEST}")

    if OUTPUT_ROOT.exists():
        print(f"Existing output directory found:\n  {OUTPUT_ROOT}")
        print()
        print("For safety, v2 will NOT delete or overwrite it.")
        print("Delete or rename ONLY that generated output directory, then rerun.")
        print("The real D:\\QuackSink\\ARCHIVES 8-30-2026 archive is untouched.")
        print()
        return 1

    entries = parse_manifest(MANIFEST)
    if not entries:
        fail("No approved archive entries found in IA_INDEX.LST.")

    print(f"Approved entries: {len(entries):,}")
    print()
    print("Validating and building...")

    records: list[dict[str, str]] = []
    seen_filenames: set[str] = set()

    for n, (archive_name, manifest_summary) in enumerate(entries, 1):
        archive_dir = SOURCE_ROOT / archive_name
        if not archive_dir.is_dir():
            fail(f"Missing source directory for entry #{n}:\n{archive_name}")

        convos = find_direct_convos(archive_dir)
        if len(convos) != 1:
            fail(
                f"Expected exactly one non-empty .CONVO for:\n{archive_name}\n"
                f"Found {len(convos)}:\n" + "\n".join(str(p) for p in convos)
            )

        convo_path = convos[0]
        try:
            convo_text = convo_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            fail(f"Could not read conversation:\n{convo_path}\n{exc}")

        # The manifest summary is authoritative when present.
        summary = clean_summary(manifest_summary, archive_name)
        if not summary or "NO MESSAGES RECORDED in the conversation artifact" in summary.upper():
            summary = find_local_luma_summary(archive_dir) or ""

        if not summary:
            fail(
                "No meaningful summary found for approved archive:\n"
                f"{archive_name}\n"
                "Add/repair its summary in IA_INDEX.LST before building."
            )

        filename = public_filename(archive_name)
        if filename in seen_filenames:
            fail(f"Public filename collision:\n{filename}")
        seen_filenames.add(filename)

        records.append(
            {
                "archive_name": archive_name,
                "repo_url": github_url(archive_name),
                "summary": summary,
                "convo_text": convo_text,
                "filename": filename,
            }
        )

        print(f"[{n:03d}/{len(entries):03d}] OK  {archive_name}")

    print()
    print("Validation passed for all approved entries.")
    print(f"Creating: {OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)

    try:
        for record in records:
            (OUTPUT_ROOT / record["filename"]).write_text(
                record_text(
                    record["archive_name"],
                    record["repo_url"],
                    record["summary"],
                    record["convo_text"],
                ),
                encoding="utf-8",
                newline="\n",
            )

        index_lines = [
            "=" * 72,
            "PURPLE PYTHON — LUMA INDEX",
            "=" * 72,
            "",
            "Curated public conversation index for the Purple Python",
            "Internet Archive collection.",
            "",
        ]

        for record in records:
            index_lines.extend(
                [
                    f"IA FILENAME: {record['filename']}",
                    f"REPOSITORY URL: {record['repo_url']}",
                    "",
                    "SUMMARY:",
                    record["summary"],
                    "",
                    "-" * 72,
                    "",
                ]
            )

        (OUTPUT_ROOT / "LUMA INDEX.TXT").write_text(
            "\n".join(index_lines),
            encoding="utf-8",
            newline="\n",
        )

    except Exception:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        raise

    public_files = list(OUTPUT_ROOT.glob("*.txt"))
    total_bytes = sum(p.stat().st_size for p in public_files)

    print()
    print("=" * 72)
    print(" BUILD COMPLETE")
    print("=" * 72)
    print()
    print(f"Conversation records : {len(records):,}")
    print("LUMA INDEX.TXT       : 1")
    print(f"Total public files   : {len(public_files):,}")
    print(f"Total size           : {total_bytes / (1024 ** 2):,.2f} MiB")
    print()
    print(f"Output: {OUTPUT_ROOT}")
    print()
    print("SOURCE ARCHIVE WAS NOT MODIFIED.")
    print("NOTHING WAS UPLOADED TO INTERNET ARCHIVE.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
