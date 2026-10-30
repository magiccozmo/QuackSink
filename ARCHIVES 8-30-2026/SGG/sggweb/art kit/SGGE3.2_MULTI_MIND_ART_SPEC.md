# SGGE3.2 — Multi-Mind Canvas: LumaDraw Artist Contract

Source of truth: `SGGE3.1_SOURCE.zip`, files `main.py` and `luma_assets_e31.json`. This document describes the existing renderer, not hypothetical features.

## Assignments and boundaries

- Gemini: **Alchemy Shop** (`area_id`: `alchemy_shop`; background asset: `alchemy_shop_background`).
- DeepSeek / Kelp: **Castle Vault** (`area_id`: `castle_vault`; background asset: `c1_bg_castle_vault`).
- Both areas are present in the SGGE3.1 source.
- Each artist edits **only the commands of their assigned background asset**. Keep the original asset name, width and height. No edits to `world`, other assets, Python, gameplay, connections, NPCs, or navigation. This is a strict first-pass visual-only experiment; propose any geometry changes separately.
- Send Luma a JSON file with the entire replacement asset recipe in the format below. The original full JSON is supplied for visual and placement reference, but should not be returned with unrelated modifications.

## JSON payload to return

```json
{
  "asset_name": "alchemy_shop_background",
  "recipe": {
    "width": 1280,
    "height": 640,
    "commands": [
      {"op":"rect", "rect":[0,0,1280,640], "color":[70,49,35]},
      {"op":"polygon", "points":[[20,20],[80,20],[50,65]], "color":[180,145,90]},
      {"op":"line", "points":[[20,100],[100,105],[130,130]], "color":[30,20,15], "width":3},
      {"op":"circle", "center":[200,100], "radius":12, "color":[220,180,60]},
      {"op":"ellipse", "rect":[240,90,50,25], "color":[100,80,65]}
    ]
  }
}
```

Kelp must substitute `c1_bg_castle_vault` for `asset_name`. The example is a format demonstration, NOT proposed scene art. Preserve the original recipe dimensions (both assigned backgrounds use 1280 × 640; verify against source).

## Rendering rules (verified in `LumaDrawEngine.draw_asset`)

- Canvas: 1280 wide × 640 high for each assigned background; origin **top-left**, x grows right, y grows down.
- `commands` is an **ordered list**. Later commands paint **over** earlier commands. **There is no per-command z-index**. Depth is created by ordering and shape design.
- Supported operations ONLY: `rect`, `ellipse`, `polygon`, `line`, `circle`.
- `color`: `[R,G,B]` integer channels, 0–255; RGBA may be accepted by pygame drawing on alpha surfaces but use RGB for compatibility. No hex strings.
- `rect` and `ellipse`: `rect:[x,y,width,height]`; optional `border` (0 or absent = filled; positive = outline). `rect` additionally supports `radius` for rounded corners.
- `polygon`: `points:[[x,y],...]` (3 or more); optional `border` (positive = outline).
- `line`: `points:[[x,y],...]` (2 or more); optional `width` (default 1). Connected polyline, **not** a filled shape. `border` does not control line thickness.
- `circle`: `center:[x,y]`, `radius:number`; optional `border` (positive = outline).
- No native gradient, shadow, texture, randomness, transform, image embed, opacity animation, clipping path, text or shader operations in the basic recipe renderer. Approximate shadows/highlights/texture with additional ordered primitives. The market's appearance does not imply these unsupported features exist.
- When an asset is drawn into a target rectangle, the engine scales local coordinates to that rectangle and caches the rendered surface. Backgrounds use the full game canvas. The cached rendering is static; do not expect per-frame random variation.
- Every shape should have the required fields for its operation; malformed geometry can cause a runtime error. JSON must be syntactically valid (no comments or trailing commas).

## Scene and interaction safety

The original JSON has `world.areas`, `world.objects`, `world.connections`, `world.npcs` and other definitions. Area entries specify `background_asset`, `solid_rects`, `sight_blockers`, `conceal_zones`, and `navigation`. These are **gameplay** data, not just painting data. Do not modify them in this experiment. Art must respect their existing walkable regions and interaction placements. Likewise, objects, NPCs, and doors are rendered/handled by separate systems, sometimes over the background. Do not draw a fake usable door and expect it to function. Existing interaction targets must remain visually discoverable.

## Art direction

Shared setting: cozy, legible fantasy RPG, consistent with the new SGGE3.1 Britrun Market. Individual styles are encouraged; avoid radical mismatches in perspective, scale, saturation, and lighting. Build from broad composition to architectural masses, then fixtures, shadows, material variation and small accents. Use controlled variation, not random visual noise. Aim for readable gameplay at 1280 × 640, including UI overlays.

Gemini: an alchemist's interior with readable workbench, shelves, bottles, and atmospheric illumination, while respecting existing shop interactions. Kelp: a heavy, secure, opulent castle vault with substantial masonry, ironwork and gold, while respecting existing vault interactions.

## Merge and verification

Luma will validate both JSON payloads, replace ONLY `assets.alchemy_shop_background` and `assets.c1_bg_castle_vault` in a **copy** of the SGGE3.1 JSON, and produce SGGE3.2 as a **new standalone release**. The untouched SGGE3.1 release remains preserved. Validate: JSON parsing, command schema and bounds sanity, both areas render, player can navigate, doors and interactions remain accessible, and old areas are unchanged. Cozmo field-tests before publishing.

**Credit:** Gemini — Alchemy Shop art; DeepSeek/Kelp — Castle Vault art; Luma — rendering engine, specification, integration; Cozmo — experiment conception, direction and field testing.
