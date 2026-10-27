SPIFFY'S GIFT GAME — C1.1
==========================
Build date: October 27, 2026

CONTENTS
--------
sggc1.1.py           Complete standalone game + notes/editor + logging/archives
luma_assets_c11.json Complete procedural artwork and 20-area world, including B and C art
README_C1.1.txt      This guide

NO OTHER SGG FILES ARE NEEDED TO RUN C1.1.
In particular, you do not need sggb1.0.py, sggc1.0.py,
sggc1_assets.py, c1_new_assets.json, or luma_assets.json.

LAUNCH
------
1. Extract the ZIP into its own folder, e.g. C:\Users\mcozm\projects\sgg\SGGC1.1
2. Activate your existing Python virtual environment containing pygame-ce.
3. From the folder containing these files, launch:

   python sggc1.1.py

   (Using `py sggc1.1.py` is also fine if that Python has pygame-ce.)

4. In the SGG main tool window, select Play Game.

Only external Python dependency: pygame-ce (developed for pygame-ce 2.5.8).

WHAT CHANGED IN C1.1
--------------------
- Game/notes/UI engine consolidated into one independent Python source.
- Original complete Luma art/scene recipes bundled into one JSON file.
- Every screen-edge transition now has a small arrow and destination label.
- Edge exits use location-sensitive gates. Two exits on the right of Gold District
  now choose different areas according to WHERE you cross.
- Market-return collision bug and Market respawn collision bug addressed.
- Every arrival is checked for collision and moved to nearest available safe spot
  if blocked. Embedded players can also move toward less obstructed space.
- Market has a permanent guard stationed near Naz, initially looking toward him.
- Guard detection checks distance, facing, cover and bucket-obscured vision.
- Vendor witnesses can yell for help, whether or not the guard saw the theft.
- Moving merchandise around via mouse is NOT the same as inventory theft.
  Stealing happens when you press E to take an owned item into inventory.
- Stolen-item status persists after inventory pickup, dropping, carrying, and
  moving to a new area. Picking up stolen loot again can be reported.
- Guard reacts when Naz takes stolen goods in sight; otherwise Naz gets away.
- The guard can wear a bucket as well as vendors; vendor shouts still summon help.
- Kart-lotta friendship quest: confront the inn harasser, talk to Kart-lotta
  again, then her designated produce is free to the PLAYER.
- Existing inventory, cooking, alchemy, soup, quest, screenshot, note editor,
  and archive/log functionality are retained.

CONTROLS
--------
WASD/arrows   Move
Mouse click   Pick up/carry or place merchandise (not automatically theft)
E             Take into inventory / interact / talk / enter door
I             Inventory
Space         Drop carried item (or selected inventory item while inventory open)
T             Wait one day
F             Eat soup
B/V           Buy / sell at Alchemy Shop
R             Respawn after death
?             Toggle hints
F3            Remap controls
F12/Ctrl+S    Screenshot
Esc           Back to SGG tool / menu

TEST GUIDANCE
-------------
1. Market -> Gold District -> Market via lower right arrow. Verify no stuck spawn.
2. Market -> Front Gate -> Market, then player death -> R, verify free movement.
3. Check two RIGHT arrows in Gold District (upper=Front Gate, lower=Market).
4. Steal Kart-lotta's Gold Pouch while bucketed; drop near Naz and check guard.
5. Repeat with the Market guard bucketed or out of line-of-sight: Naz survives.
6. Shop: bucket the alchemist, steal; remove bucket and retake stolen item in view.
7. Kart-lotta quest: hear her complaint, intimidate inn patron, return; vegetables green.
8. F12 screenshot saved to this run's archive; notes and logs likewise.

Every launch creates `archives/SGG_<DATE>_<TIME>VC1.1/` and snapshots
sggc1.1.py, luma_assets_c11.json, sgg.config, and log.txt.

TESTING STATUS
--------------
Python syntax check and offline logic/integration tests passed, including
all 40 connections' arrival positions, 20 areas, Naz/guard visibility,
guard chase, bucket witness suppression, and Kart-lotta friendship state.
A graphical Pygame session could NOT be run here because pygame-ce is not
available in the build environment. Your first local launch is the visual
and integration test; please send any run log/screenshots from the archive.

U B U. WE BE WE.  - Luma
