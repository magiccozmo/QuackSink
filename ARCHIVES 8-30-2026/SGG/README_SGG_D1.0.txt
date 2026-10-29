SPIFFY'S GIFT GAME — D1.0 FIELD TEST
====================================

D = distribution-development branch. This is a complete standalone Python
source release, NOT yet a Windows installer or public/browser build.

FILES
  sggd1.0.py              Complete executable game source (no C1 imports)
  luma_assets_c131.json   Unmodified C1.3.1 art and world assets

INSTALL / START
  1. Extract BOTH files into the same SGG game directory.
     They can coexist with existing C1.3.1 files.
  2. Activate the same Python environment used for C1.3.1, with pygame-ce.
     If needed: py -m pip install pygame-ce==2.5.8
  3. Run: py sggd1.0.py

  No launcher/menu/notes UI appears; the world starts immediately.
  Existing saves/ and sgg.config in that directory are reused.
  If no sgg.config exists, D1 creates one with defaults.
  The original game and asset files are not overwritten.

WHAT CHANGED
  - Boot directly into play rather than the legacy tool/notes screen.
  - Compact top bar: current run archive directory + MENU button only.
  - Menu opens the SAME Game Configuration panel as the F1 shortcut.
  - Removed Back to Tool, Screenshot and +/- font-size buttons.
  - Screenshot HOTKEY remains (F12 by default; existing binds honored).
  - Hints moved below the actual game viewport; '?' still toggles them.
  - Timed speech bubbles now appear near NPCs and interactive objects.
    Branching dialogue choices remain clickable/keyboard controlled.
  - F1 configuration includes a fourth slider: bubble lifetime, 1–10 seconds.
  - Inventory mouse-wheel scrolling and draggable scrollbar for >12 items.
  - Removed the special extra chest tooltip in the Kitty Caravan.
  - Esc now closes inventory or opens Game Configuration instead of returning
    to the removed launcher. Existing rebinding of the exit key uses that too.

UNCHANGED
  - Same art/world JSON as C1.3.1; same 21 areas and 52 starting objects.
  - Same gameplay, trade, theft, cooking, quest, saves, and world transitions.
  - Same run archive/log/source/config/asset snapshots and hotkey screenshots.
  - C1.3.1 game engine and state-machine methods preserved unchanged.

ARCHIVES
  archives/SGG_<date>_<time>VD1.0/ is created on launch, containing
  log.txt, a copy of sggd1.0.py, a copy of luma_assets_c131.json, and
  a copy of sgg.config. Screenshots are stored there as before.

TESTING STATUS
  Python syntax checked; 21-area world initialization, startup archive,
  configuration, bubble timer, inventory scroll, and fake/headless drawing
  paths (world, settings, dialogue, inventory, bubbles) checked. These are
  NOT substitutes for testing with real Pygame on Windows. Cozmo's first
  local run and screenshots are still required before calling D1.0 verified.

PENDING FUTURE DISTRIBUTION TASKS
  - Tip button when the Ko-fi URL is specified.
  - Final delivery format: desktop installer and/or browser build.
  - Wider real-player QA and accessibility testing.

This ZIP does not alter the GitHub repository.
