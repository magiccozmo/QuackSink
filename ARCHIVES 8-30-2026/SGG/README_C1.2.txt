SPIFFY'S GIFT GAME — C1.2
=========================

COMPLETE, STANDALONE C1.2 (NOT AN IMPORT OR PATCH TO AN OLDER VERSION)

CONTENTS
  sggc1.2.py              Complete source code, including base game and C1.2 extensions
  luma_assets_c12.json    Full combined Luma procedural-art/world pack (20 areas)
  README_C1.2.txt         This document

INSTALLATION
  Place BOTH .py and .json files together in your existing SGG project directory,
  beside your current sgg.config and archives/ folder. You do NOT need to copy
  any previous C1.1/B1.0 .py or JSON file to run C1.2.

  In the existing SGG Python 3.12 environment with pygame-ce installed:
      python sggc1.2.py
  or:
      py sggc1.2.py

  Dependency: pygame-ce==2.5.8 (or compatible version).

SAVE / LOAD — NEW IN C1.2
  F5: quicksave         F9: quickload         F6: save/load menu
  F6 shows Quick + 3 manual slots with clickable Save and Load buttons.
  Existing lives, deaths, current position/area, held objects, full inventory,
  money, day, generated items, respawn schedule, NPC state (including dead Naz),
  vendor permission, bucket placement, stolen-item flags, quest progress, guard
  pursuit and game timers are serialized.
  Save files are stored under SGG/saves/ and persist between runs.
  Files are written atomically. Malformed or incompatible saves are rejected
  without replacing the running game state.
  C1.1 sessions did not have saves, so C1.2 starts a new world initially.

CONVERSATIONS AND KARLOTTA'S QUEST — NEW IN C1.2
  Talk with E while pointing at or standing next to someone.
  In dialogue: click a response, press 1-5, or use Up/Down + Enter.
  Escape closes a conversation without choosing.

  1. Karlotta: "This twit in the inn keeps bothering me. I have no idea why!"
  2. Confront the Boorish Inn Patron in the inn. You may:
     A. Threaten him: "Leave Karlotta alone, or else."
        He answers "Step outside and say that!" and follows you OUTSIDE.
        Talk outside again to intimidate him, OR tempt him with stolen gold.
        Like Naz, he picks up dropped valuables. If a guard or vendor
        actually witnesses the theft, existing crime/pursuit systems apply.
        An unwitnessed theft does not magically trigger punishment.
     B. Negotiate: "What will it take to make you leave Karlotta alone?"
        He requests Black-Briar Mead. One bottle can be found in the inn.
        Return with the bottle (or pay immediately if you're carrying it).
  3. Return to Karlotta once the lout is intimidated, bribed or eliminated.
     "Oh, my hero! I could not charge YOU for my lovely veggies!"
     Her tomatoes and cabbages become green/free to take. Her gold pouch
     and other non-produce possessions NEVER become free automatically.

KARLOTTA ART
  The full Luma JSON includes a new silhouette, hairstyle, dress and apron.
  Kokoro voice assignment for future integration: af_nicole (not active in C1.2).

CONTROLS / MOVEMENT
  F3: configure control bindings (click a row, press a new key or chord)
  Ctrl+S can now be assigned to Screenshot using the binding screen.
  Default screenshot remains F12; use Esc to cancel a binding.
  Arrow keys / WASD: move, E: take/use/talk, mouse: point or carry/place,
  I: inventory, F: eat soup, T: wait, B: buy, V: sell, R: respawn.
  Vertical transition activation bands have been widened so movement cannot
  routinely skip over a one-pixel exit strip. Edge-arrow locations and the
  established world connections remain unchanged.

DIAGNOSTICS AND ARCHIVES
  Every launch still creates a dated C1.2 archive with source, assets,
  config snapshot, log and any screenshots/notes. Save files are NOT placed
  in individual run archives; they persist in the stable saves/ directory.
  Logs capture meaningful events, including guard distance, concealment,
  facing direction, line-of-sight blockers and crime decisions, not frames.

FIELD TEST PLAN
  - Start C1.2 and confirm it opens. Enter/exit shop and the inn.
  - F5 while carrying a stolen item; move; press F9 and verify exact return.
  - Kill Naz in view of the guard; F5; restart; F9; verify Naz stays dead.
  - F6: save slot1, change world, load slot1.
  - Try Karlotta's quest via bribery, then restart and try outside intimidation.
  - Try outside stolen-gold trick; compare guard witnessed vs not witnessed.
  - Check Ctrl+S binding through F3, and vertical castle/stables exits.

VALIDATION PERFORMED HERE
  Python syntax compilation passed. JSON parsed and world/art asset presence
  validated. Simulated non-graphical logic checks passed for state persistence,
  atomic saves, corrupted-save rollback, mead resolution, intimidation, NPC
  following across areas, legal produce permissions, and guard-witness gating.
  The actual Pygame graphical loop could not be run here (pygame-ce is not
  installed in this build environment). Your live field test remains essential.

U B U — AND WE BE WE.
