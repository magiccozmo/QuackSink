SPIFFY'S GIFT — SGGF1.5
Castle Hall redesign, bank-vault interaction, and configurable platter hitbox

WHAT CHANGED
- Rebuilt the Castle Hall scene in the same pale grey-green masonry, rounded stone arch, deep dark recesses, blue arched windows, and gold/iron detailing established by the F1.4 Castle Exterior.
- Replaced the right-hand doorway's corridor-like appearance with a classic bank vault door: heavy steel frame, thick slab, perimeter bolts, central multi-spoke wheel, and a locking lever. The artwork is drawn with supported Luma Draw Engine primitives.
- Made the right-hand Bank Vault Door an interactable world object. Point at it and press E (while close enough) to open the vault dialogue.
- Added the deliberately impossible vault choices. “Pick lock” returns: “Are you kidding? Even the Skeleton Key ain't gonna pick this.” “Force open” offers items from the player's inventory, including a currently carried item, with item-specific humorous responses. No item is consumed and the vault can never open.
- Added the plate response: “Oddly the plate ALMOST squeezes in a gap.” The hidden passage remains a separate platter-only clip route; the response to trying the plate on the visible vault door does not open it.
- Added the persistent Game Configuration slider “Special Hard Hitbox”. Its range is 1.0–5.0: 1.0 is the larger, forgiving target; 5.0 is the smaller, precise target. The default is provisionally 3.0. The target remains offset toward the vault's right-hand seam, rather than being centered on the door.

DOOR AND MOVEMENT BEHAVIOR
- Left-hand door: Mage Room / Mage's Lab. Its existing object, walk trigger, connection, and arrival point are preserved.
- Middle door: returns outside to the Castle Exterior. Its existing object, walk trigger, connection, and arrival point are preserved. The amusing enter-while-moving-and-immediately-exit loop is intentionally retained.
- Right-hand door: visible Bank Vault Door. It is point-and-E interactive, but it is not a normal walk-through door and has no open transition.
- The existing vault wall seam and the hidden platter clip connection are retained. The clip hitbox is a separate off-centre target controlled only by “Special Hard Hitbox”.
- Existing Castle Hall navigation/walkmesh data is unchanged. Static checks verify that the left, middle, and off-centre plate approach coordinates remain in the walkable region.

WHAT DID NOT CHANGE
- The F1.4 Castle Exterior and Castle Path scenes, their transitions, arrival coordinates, and the new Castle Exterior artwork are preserved.
- All other area art, asset recipes, world objects, collision/navigation definitions, save formats, inventory behavior, quests, Kitty, Stables, carriage, comments, Part One finale, and prior gameplay are retained.
- The left Mage Room transition and middle Castle Exterior transition are unchanged.
- The old vault seam object and the existing hidden clip connection are unchanged; only the plate clip test is delegated to a configurable, offset target.
- All previously deployed site releases are kept byte-for-byte, except for the release catalog (versions.json), which now lists SGGF1.5 as current.

IMPLEMENTATION
- Runtime code: main.py
- World and Luma artwork: luma_assets_e33.json
- Browser entry page: F1_play.html (archive identifier sggf15)
- The source archive includes the F1.4 baseline, prior development baselines, hall artwork generator, reproducible F1.5 builder, packaging script, test suite, preview, and versioned-site front-door files.

DEPLOYMENT
Upload the contents of SGGF1.5_CLOUDFLARE_DEPLOY.zip to the existing Cloudflare static-assets site, preserving the archive folder structure. The package contains all earlier releases plus the new SGGF1.5 browser bundle. The comments API Worker and D1 database do not need changes.

TESTING AND VERIFICATION
- Python AST parsing and py_compile pass.
- The F1.5 regression suite verifies every Luma command, exact F1.4-to-F1.5 JSON scope, preserved door objects and connections, reachable walkmesh approach coordinates, clickable vault-object hit test, off-centre hitbox scaling, carried-plate inventory selection, lock/force dialogue responses, item-specific responses, permanently closed vault state, and persistence of the new configuration value.
- Runtime APK and TAR payloads are checked against the exact F1.5 source bytes.
- Both ZIP archives are checked for CRC integrity and duplicate paths. The Cloudflare deployment archive is checked for byte-for-byte preservation of all prior deployment files except versions.json.
- The hall preview is rendered from the F1.5 Luma JSON recipe.
- This build was not launched in a live browser. Please field-test F1.5 in the browser before treating pointer interaction, keyboard movement, or live save/config behavior as runtime-verified.
