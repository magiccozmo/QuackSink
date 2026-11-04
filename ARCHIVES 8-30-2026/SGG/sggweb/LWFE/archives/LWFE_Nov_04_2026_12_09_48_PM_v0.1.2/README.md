# Luma-Winslow Folio Engine (LWFE) — 0.1.2

LWFE is a standalone sound-painting workstation for SGG and other projects. It turns JSON instructions into finished WAV files. The JSON does not merely specify a waveform: it describes layers of sound material, vocal gestures, pressure, pitch movement, resonance, breath, texture and impacts.

## First sound folios

- **Dog Bark** — two short, rough throat bursts with noisy muzzle edges.
- **Chicken Cluck** — three hollow clucks with separate beak ticks.
- **Kitty Meow** — a rising/falling voiced cry with nasal resonance and a breathy tail.

These are first-pass procedural sketches. Their character is intentionally distinct; listening and adjusting the folios is part of the creative process.

## Start the workstation

Use a normal Windows Command Prompt (CMD). No PowerShell window or PPR virtual-environment activation is required for the standard Python installation, provided it includes Tk support.

```bat
cd /d "D:\QuackSink\ARCHIVES 8-30-2026\SGG\sggweb\LWFE"
py -3 lwfe_app.py
```

LWFE uses only Python's standard library: Tkinter for the UI, `wave`/`struct` for WAV writing, and Windows `winsound` for PLAY. The renderer itself can write WAVs on non-Windows systems too; this first UI's PLAY button is Windows-specific.

The `run_lwfe.bat` launcher is also retained, but the normal development workflow is to launch from CMD so startup messages and errors remain visible.

## UI

The list is read from `lwfe.json`.

- Select a sound.
- **PLAY** is enabled only when its WAV already exists.
- **RENDER** creates or replaces that selected sound's generated WAV.
- Escape stops playback.
- Project → Reload lwfe.json reloads the folio list.
- Project → Create snapshot now makes an additional directory snapshot of the current state.

Generated masters are written under `sounds/` with the requested naming pattern, for example `dog_bark_LWFE.WAV`. They are mono, 48 kHz, 16-bit PCM WAV files.

## The sound-painting model

Each sound in `lwfe.json` has a `canvas` and a list of `strokes`.

A stroke can use these brushes:

- `voice`: a pitched vocal/body material shaped by harmonic partials and formant resonances.
- `air`: breath, hiss or a filtered noise cloud.
- `impact`: a short resonant click/thump with a decaying ring.

The other instruction groups describe the gesture:

- `start` and `duration` place a stroke in time.
- `pressure` is a time/gain contour (the equivalent of how hard a brush presses).
- `contour` is the pitch path for voiced material.
- `tone` describes partial balance and formant resonances.
- `grain` describes noisy texture, color and small pitch irregularities.
- `motion` adds slow vibrato or other motion.

The engine mixes the strokes, applies gentle saturation, and paints a WAV. No sampled dog, chicken or cat recordings are bundled or required.

## Runtime directory archives

**Every application launch creates a new snapshot directory under `archives/` before the user can render or change anything in that session.** The directory name follows the PPR-style timestamp convention, with underscores in place of spaces:

`LWFE_Nov_04_2026_11_03_08_AM_v0.1.2`

Each snapshot contains copies of the current top-level project files (including Python source, `lwfe.json`, launcher, README and version marker) and copies of every `.wav` file already present under `sounds/`. The snapshot also contains `ARCHIVE_MANIFEST.txt` describing what was captured.

The snapshot is a directory, not a ZIP. Later RENDER operations write to the live `sounds/` folder and do not modify the startup snapshot. On the next launch, a new timestamped directory captures the updated JSON/source and all WAVs that exist at that time.

`archives/` itself is excluded from snapshots, so old snapshots are never copied recursively. Existing archive directories are never overwritten. If two snapshots are requested within the same second, a numeric suffix makes the new directory unique.

The structure is:

```text
LWFE/
  lwfe.json
  lwfe_app.py
  lwfe_engine.py
  lwfe_archive.py
  run_lwfe.bat
  README.md
  LWFE_VERSION.txt
  sounds/
    *.WAV
  archives/
    LWFE_<timestamp>_v<version>/
      current project files
      sounds/*.WAV (only those existing at snapshot time)
      ARCHIVE_MANIFEST.txt
```

## Editing and extending the folio

Add another entry to the `sounds` array in `lwfe.json`. Give it a unique `id`, a display `name`, an output path, a `canvas`, and one or more `strokes`. Reload the JSON from the Project menu. The UI will list the new sound automatically.

The renderer deliberately stays separate from SGG. SGG only needs the finished sound file; LWFE does not need to be packaged into the game. WAV is the master output. A later delivery step can convert selected masters to OGG Vorbis for Pygbag/browser distribution without changing their JSON recipes.
