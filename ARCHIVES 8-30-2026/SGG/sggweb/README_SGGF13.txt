SPIFFY'S GIFT — SGGF1.3
Castle Path transition-marker clarity and safe return placement

WHAT CHANGED
- Removed the complete temporary three-pass yellow/gold guide stroke from the Castle Path background. It is no longer visible in the finished scene.
- Added a normal gold-outlined directional transition arrow, pointed up the road toward the castle, with the destination label “Castle Exterior”. The arrow sits just beyond the threshold on the castle side.
- Kept the actual transition boundary invisible and at the exact F1.2 location. The player must physically cross the existing threshold to enter Castle Exterior. The arrow is a visual target only; it does not trigger travel.
- Moved the Castle Exterior return landing to (834, 400), safely on the player side of the threshold and centered on the Castle Path approach corridor. This avoids an immediate re-trigger after returning.

WHAT DID NOT CHANGE
- The E5.6 crossing-state-machine code, threshold point, forward/lateral vectors, crossing direction, and lateral tolerance are unchanged from F1.2.
- All other F1.2 JSON art, area geometry, objects, Stables assets, Kitty art/behavior, quests, driver/sammich handoff, saves, inventory, comments, and Part One finale are retained.
- Other transition arrows and labels are unchanged.
- The Cloudflare comments Worker and D1 database are unchanged.

FILES
- main.py: F1.3 release labels and the Castle Exterior visual arrow only; original crossing logic retained.
- luma_assets_e33.json: temporary Castle Path guide line removed, return arrival updated, release version/notes advanced.
- F1_play.html: F1.3 browser-loader names and bundle references.
- F1.3_CASTLE_PATH_PREVIEW.png: rendered Castle Path preview with Spiffy and the new marker.
- F1.2_BASE_MAIN.py and F1.2_BASE_LUMA_ASSETS.json: exact F1.2 comparison baselines.
- test_f13.py: F1.2 gameplay/art regression checks plus strict F1.3 scope and return-transition checks.

DEPLOYMENT
Upload the contents of SGGF1.3_CLOUDFLARE_DEPLOY.zip to the existing Cloudflare static-assets site, preserving the archive folder structure. F1.2 and all earlier releases remain in the package. The comments API Worker and D1 database do not need changes.

TESTING
Static/model regressions and package-integrity tests pass, including a real model-level return transition to (834, 400), verification that the return point is inside the authored walkable corridor, and forward-connection lookup across the full lateral tolerance. The E5.6 crossing state machine is byte-for-byte unchanged from F1.2. A live browser session was not launched during this build; browser field testing remains the final runtime check.
