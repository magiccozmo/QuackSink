SPIFFY'S GIFT GAME — C1.0 (October 27, 2026)
==============================================

THIS IS A PLAYABLE DEVELOPMENT BUILD, NOT A PROMISE OF A BUG-FREE FINAL GAME.
KOKORO / VOICE IS INTENTIONALLY NOT INCLUDED.

What is included
----------------
  sggc1.0.py         — new game code, inherits B1.0 core state/UI/art engine
  sggc1_assets.py    — new level design, JSON generator, NPC/art recipes
  c1_new_assets.json — 38 new editable procedural art assets
  SETUP_C1.ps1       — optional PowerShell preparation (see below)

To preserve the exact look and feel of B1.0, C1.0 REQUIRES THE UNMODIFIED:
  sggb1.0.py         — original B1.0 code (not overwritten)
  luma_assets.json   — original B1.0 asset pack (not overwritten)
  sgg.config         — original settings file, optional; generated if missing

Put the 3 included files and the original B1.0 files into the SAME directory.
A fresh subfolder (such as C:\Users\mcozm\projects\sgg\SGGC1.0) is safest.
If the original two files are missing, SETUP_C1.ps1 can copy them from the
parent folder or download the October 23, 2026 B1.0 archival originals
from the QuackSink GitHub repository. It does NOT alter the originals.

In your EXISTING pygame-ce venv, run:

    python sggc1.0.py

No pip changes should be needed IF sggb1.0.py already runs in that venv.
C1.0 uses pygame-ce and Python's standard library only.

At startup, the art builder reads original luma_assets.json and generates:
  luma_assets_c1.json  — complete original + new artwork/world (auto-generated)
  c1_additions.json   — world/art additions snapshot (auto-generated)

Original luma_assets.json is untouched. Edit c1_new_assets.json to change
C1 art recipes; the combined file is regenerated each time the game starts.

The existing PPR-style run archive is preserved:
  archives/SGG_<DATE>_<TIME>VC1.0/
It snapshots C1 code, B1 code, the art builder, combined assets, overlay,
sgg.config and a timestamped log. The original code is left intact.

Controls
--------
  WASD / arrow keys = walk
  Mouse LEFT click = carry or drop an object (NEVER takes it into inventory)
  Point at a nearby object / person + E = take, activate, enter, read, talk
  E while carrying = move the carried item into inventory
  I = inventory; select any row by clicking it
  Space = drop carried object; if inventory open, drop selected item
  T = wait one day (vegetable stock and caravan chest can respawn)
  F = eat a bowl of vegetable soup (two bowls stack into a faster dash)
  B = buy enhancement potion from alchemy shopkeeper (69,000 gold)
  V = sell selected inventory item near alchemy shopkeeper
  ? = show/hide the bottom in-game hint bar
  F3 = key configuration screen; click an action, press new key
  R = respawn after death
  F12 or Ctrl+S = screenshot
  Esc = back / exit game to tool

All the PRIMARY in-game bindings above can be changed in F3; arrow keys
remain as emergency movement fallbacks. Config is saved in sgg.config.

Walkthrough / quest routes (SPOILERS)
------------------------------------
MISSION: Visit Fearmonger in the castle Mages Lab. Bring him a
Potion of Increased Physical Enhancement and receive 5,000 gold.

1) TRADING: Market south -> Front Gate (E on the city gate) -> Outside Gate -> Stables.
   E on the kitty caravan hidden chest gives 2,000 gold + tradable goods.
   It restocks after 2 days (T). Sell goods near alchemy shopkeeper (V).
   Repeat to buy the 69,000-gold potion (B) in the shop.

2) ALCHEMY / SOUP: Talk to Kart-lotta, then confront the Inn Lout in
   the inn, return to Kart-lotta for free access to her vegetables.
   The inn cooking pot (E) makes a soup from one cabbage + tomato.
   Two soups eaten with F grant escape speed. Market south -> Front Gate (E on gate)
   -> Outside -> Stables -> Plains -> LEFT Mountain Path -> Peak
   -> Frost Cave. Take Purple Passion Pineapple, avoid Frosty the troll,
   dash to the cave exit. Craft potion at Alchemy Table using Purple
   Passion Pineapple + Redroot + Moonflower. Recipe books in lab/shop.

3) TREASURE ROOM: Market LEFT -> Gold District -> Castle Path (north)
   -> Castle Exterior -> Castle Hall. The locked treasure gate cannot
   be opened normally. Find a serving platter in the inn, CARRY it
   with the mouse, and push into the castle hall's suspicious east wall
   seam (x~1000, y 210..405), or E the seam while holding the platter.
   Loot the treasure, then buy the potion.

The routes are combinable. Item ownership is independent from whether
someone witnessed the take. Bucket-over-head suppresses that vendor's
sight but does not remove an item's ownership. Witnessed theft causes a
shouting vendor and a guard chase. Drop stolen valuables near Naz the
Jerk and watch what happens if he decides they belong to him!

Wilderness giant, mudcrab and southern wilds encounters are intentionally
lethal in this build. Other ways to kill Naz and full shops/interiors are
future-design opportunities, not implemented here.

LIMITATIONS / TEST STATUS
-------------------------
* Source code compiled and generated recipes/world-data passed static checks.
* This environment does not have pygame-ce or the B1.0 art/source files mounted;
  an actual window launch and graphical regression test on your machine are
  still required. Please report the resulting archive log and screenshot.
* C1 code is an extension of the archival B1.0 core (two original files needed).
  It is NOT a completely standalone copy of 125KB B1.0.
* NPC pathing/physics are prototype-level state machines, not final AI.
* Kokoro has NOT been added; characters have readable dialogue text only.
