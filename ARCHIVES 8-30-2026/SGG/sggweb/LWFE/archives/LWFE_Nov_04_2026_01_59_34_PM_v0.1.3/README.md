# Luma-Winslow Folio Engine (LWFE) — 0.1.3

LWFE is a standalone sound-painting workstation for SGG and other projects. It turns JSON instructions into finished WAV files. The JSON describes layers of sound material, vocal gestures, pressure, pitch movement, resonance, breath, texture and impacts.

## First sound folios

The current folio library includes Dog Bark, Chicken Cluck, Kitty Meow, a moo-box-inspired Kitty Meow experiment, and a Cow Moo control experiment. These are procedural sketches; listening and adjusting the folios is part of the creative process.

## Start the workstation

Use a normal Windows Command Prompt (CMD). No PowerShell window or PPR virtual-environment activation is required for the standard Python installation, provided it includes Tk support.

```bat
cd /d "D:\QuackSink\ARCHIVES 8-30-2026\SGG\sggweb\LWFE"
py -3 lwfe_app.py
```

LWFE uses only Python's standard library: Tkinter for the UI, wave/struct for WAV writing, and Windows winsound for PLAY. The renderer can write WAVs on non-Windows systems too; this first UI's PLAY button is Windows-specific.

The run_lwfe.bat launcher is also retained, but the normal development workflow is to launch from CMD so startup messages and errors remain visible.

## UI

The list is read from lwfe.json.

- Select a sound.
- PLAY checks for the WAV inside the current run's archive workspace.
- RENDER paints a new WAV into that same archive workspace.
- Escape stops playback.
- Project → Reload lwfe.json reloads the folio list.
- Project → Create additional snapshot makes another snapshot but does not change the active workspace for the current run.

## Session workspace and archive behavior

**Every application launch creates a new, uniquely named directory under archives/. That new directory becomes the active working directory for the entire application run.**

For example:

`archives/LWFE_Nov_04_2026_01_10_00_PM_v0.1.3/`

At startup, LWFE copies the current top-level project files (including Python source, lwfe.json, launcher, README and version marker) into the new directory. WAV files already present in the legacy/main sounds/ folder are copied into the archive's sounds/ subfolder too. An ARCHIVE_MANIFEST.txt records what was captured.

**All new renders go into the active archive's sounds/ folder.** PLAY looks in that same folder. The main project sounds/ folder is no longer used as the output destination by the desktop app.

The archive path is held by the running app as its session workspace. Selecting another folio, reloading lwfe.json, or rendering another sound does not change that workspace. When LWFE is closed, that archive remains on disk with the source snapshot and all WAVs rendered during that run.

The menu command "Create additional snapshot" is deliberately separate: it creates another historical snapshot but leaves the current session's render destination unchanged.

Existing archive directories are never overwritten. If a timestamp collides, a numeric suffix is added. The archives/ directory is excluded from snapshots, so snapshots are never copied recursively.

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
  sounds/                         legacy WAVs copied at startup only
    *.WAV
  archives/
    LWFE_<timestamp>_v0.1.3/       active workspace for one app run
      current project files
      sounds/
        copied WAVs plus new renders from this run
      ARCHIVE_MANIFEST.txt
```

## The sound-painting model

Each sound in lwfe.json has a canvas and a list of strokes.

A stroke can use these brushes:

- voice: a pitched vocal/body material shaped by harmonic partials and formant resonances.
- air: breath, hiss or a filtered noise cloud.
- impact: a short resonant click/thump with a decaying ring.

The other instruction groups describe the gesture:

- start and duration place a stroke in time.
- pressure is a time/gain contour.
- contour is the pitch path for voiced material.
- tone describes partial balance and formant resonances.
- grain describes noisy texture, color and small pitch irregularities.
- motion adds slow vibrato or other motion.

The engine mixes the strokes, applies gentle saturation, and paints a WAV. No sampled animal recordings are bundled or required.

## Editing and extending the folio

Add another entry to the sounds array in lwfe.json. Give it a unique id, a display name, an output path, a canvas, and one or more strokes. Reload the JSON from the Project menu. The UI will list the new sound automatically.

For the desktop app, each output path is resolved relative to the active session archive, not the main project directory. Keep output paths such as sounds/example_LWFE.WAV so the output is placed in the archive's sounds folder.

The renderer deliberately stays separate from SGG. SGG only needs the finished sound file; LWFE does not need to be packaged into the game. WAV is the master output. A later delivery step can convert selected masters to OGG Vorbis for Pygbag/browser distribution without changing their JSON recipes.
