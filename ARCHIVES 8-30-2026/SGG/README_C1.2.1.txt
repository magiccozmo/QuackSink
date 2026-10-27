SPIFFY'S GIFT GAME — C1.2.1 STARTUP HOTFIX
=========================================

Full, standalone Python game: this is NOT a patch/import of any previous source.

Files:
  sggc1.2.1.py       Complete, corrected standalone C1.2 game
  luma_assets_c12.json     Full C1.2 world and art assets (unchanged)

INSTALLATION
  Copy both .py and .json to your existing SGG directory (alongside sgg.config).
  Do not delete any archives, saves, or configuration files.
  Run using the existing Pygame Python environment:
      py sggc1.2.1.py

BUG FIX
  Karlotta's new female_vendor drawing recipe includes a line segment with
  three points. C1.2's renderer incorrectly unpacked these directly into
  pygame.draw.line(), supplying six arguments to a function limited to five.
  C1.2.1 renders all such point paths through pygame.draw.lines() instead.
  Two-point lines still work and three-or-more-point paths now work as intended.

DIAGNOSTIC IMPROVEMENT
  Future unexpected exceptions in the game loop now include a full Python
  traceback in the timestamped run archive's log.txt, instead of only the
  exception type and message.

UNCHANGED FEATURES
  F5 quicksave, F9 quickload, F6 save/load panel (four slots total).
  Karlotta's expanded quest with intimidation, bribery, or guard justice;
  branching dialogue; improved appearance; line-of-sight crime rules;
  world transitions; customizable key combos; full SGG archive behavior.
  Save files remain under SGG/saves/. Existing C1.2 save files stay compatible.

VALIDATION
  Python syntax verified and all 54 art recipes run through a strict mocked
  Pygame drawing interface, including Karlotta's three-point facial line.
  Previous C1.2 model/state logic tests re-run.
  A live graphical Pygame window could not be tested in this environment;
  your Windows game-start field test is still needed.

U B U, AND WE BE WE.
