#!/usr/bin/env bash
set -euo pipefail
ROOT="$GITHUB_WORKSPACE/ARCHIVES 8-30-2026/SGG/sggweb"
WORK="$GITHUB_WORKSPACE/.sggi12-work"
S="$WORK/source"
SITE="$WORK/site"
mkdir -p "$WORK" "$S" "$SITE"

unzip -q "$ROOT/SGGI1.1_SOURCE.zip" -d "$S"
unzip -q "$ROOT/SGGI1.1_COMPLETE_CLOUDFLARE_SITE.zip" -d "$SITE"

cat > "$WORK/patch_i12.pl" <<'PERL'
use strict;
use warnings;
my $path = shift @ARGV or die "usage: patch_i12.pl FILE\n";
local $/;
open my $in, '<', $path or die "open $path: $!";
my $s = <$in>;
close $in;
my $old1 = <<'OLD1';
        engine.draw_asset = draw_i1
        try:
            super()._draw_game_scene(surface, g)
        finally:
            engine.draw_asset = original
OLD1
my $new1 = <<'NEW1';
        engine.draw_asset = draw_i1
        # Defer the Game Over panel until every game-world layer, including the
        # articulated giant and airborne victim, has been drawn. This is a
        # render-order correction only; the game state is restored immediately.
        saved_dead = g.c1_dead
        game_over_message = None
        saved_dead_text = str(saved_dead) if saved_dead is not None else ''
        if saved_dead_text.startswith('GAME OVER|'):
            game_over_message = saved_dead_text.split('|', 1)[1]
            g.c1_dead = None
        try:
            super()._draw_game_scene(surface, g)
        finally:
            engine.draw_asset = original
            if game_over_message is not None:
                g.c1_dead = saved_dead
NEW1
my $p1 = index($s, $old1);
die "could not find inherited drawing block\n" if $p1 < 0;
substr($s, $p1, length($old1), $new1);
my $old2 = <<'OLD2';
            if t < 0.82:
                trail = pygame.Surface((GAME_WIDTH, GAME_HEIGHT), pygame.SRCALPHA)
                alpha = int(85 * (1.0 - t / 0.82))
                pygame.draw.line(trail, (241, 223, 173, alpha),
                                 (round(victim['x']), round(victim['y'] - h * 0.3)),
                                 (round(x), round(y + h * 0.28)), 2)
                surface.blit(trail, (0, 0))
OLD2
my $p2 = index($s, $old2);
die "could not find flight tether/trail block\n" if $p2 < 0;
substr($s, $p2, length($old2), '');
my $old3 = <<'OLD3';
            self._c1_text(surface, 'GRUMBLEGRON’S CAMP  ·  MIND YOUR STEP', 430, 57,
                          (246, 223, 175), self.game_small_font, 420)


async def main():
OLD3
my $new3 = <<'NEW3';
            self._c1_text(surface, 'GRUMBLEGRON’S CAMP  ·  MIND YOUR STEP', 430, 57,
                          (246, 223, 175), self.game_small_font, 420)

        if game_over_message is not None:
            # Same inherited panel styling, now composited above the giant and
            # flight layers so no articulated piece can float over Game Over.
            pygame.draw.rect(surface, (0, 0, 0, 190), (0, 0, GAME_WIDTH, GAME_HEIGHT))
            self._c1_text(surface, 'GAME OVER', 414, 170, (241, 190, 112), self.game_font, 460)
            self._c1_wrapped(surface, game_over_message, 363, 246, 585, (255, 226, 205))
            self._c1_text(surface, 'PRESS R TO RESPAWN', 397, 362, (255, 226, 160), self.game_font, 510)


async def main():
NEW3
my $p3 = index($s, $old3);
die "could not find end-of-scene insertion point\n" if $p3 < 0;
substr($s, $p3, length($old3), $new3);
open my $out, '>', $path or die "write $path: $!";
print {$out} $s;
close $out;
PERL

perl "$WORK/patch_i12.pl" "$S/main.py"
cp "$S/main.py" "$S/assets/main.py"

cp -a "$S/SGGI1.1" "$S/SGGI1.2"
rm -f "$S/SGGI1.2/SGGI1.1_BUILD_META.json" "$S/SGGI1.2/SGGI1.1_LUMA_LOG_Entry032.txt" \
      "$S/SGGI1.2/SGGI1.1_README.txt" "$S/SGGI1.2/SGGI1.1_TEST_RESULTS.txt" \
      "$S/SGGI1.2/SGGI1.1_WORKER_DEPLOYMENT.txt"
cp "$S/main.py" "$S/SGGI1.2/main.py"
cp "$S/main.py" "$S/SGGI1.2/assets/main.py"
perl -pi -e 's/I1\.1/I1.2/g; s/sggi1_1/sggi1_2/g' "$S/SGGI1.2/play.html"
rm -f "$S/SGGI1.2/sggi1_1.apk" "$S/SGGI1.2/sggi1_1.tar.gz"
rm -f "$S/SGGI1.2/sggi1_2.apk" "$S/SGGI1.2/sggi1_2.tar.gz"
(cd "$S/SGGI1.2" && zip -q -9 -X sggi1_2.apk main.py luma_assets_e33.json)
tar -czf "$S/SGGI1.2/sggi1_2.tar.gz" -C "$S/SGGI1.2" assets/main.py assets/luma_assets_e33.json

MAIN_SHA=$(sha256sum "$S/main.py" | awk '{print $1}')
ASSET_SHA=$(sha256sum "$S/SGGI1.2/luma_assets_e33.json" | awk '{print $1}')
cat > "$S/SGGI1.2/SGGI1.2_BUILD_META.json" <<EOF
{
  "version": "SGGI1.2",
  "baseline": "SGGI1.1",
  "build_date": "2026-11-07",
  "changes": [
    "Removed the visible line connecting the airborne victim to the launch point during Grumblegron's flight effect.",
    "Composited the existing player Game Over panel after the giant and flight layers so the articulated arm and club no longer draw over it."
  ],
  "preservation": "Grumblegron's articulated shoulder/arm/club animation, flight path, flight duration, two-turn spin, game logic, saves, all other artwork, dialogue, areas, transitions and historical releases are preserved.",
  "live_tested": false,
  "cloudflare_deployed": false,
  "github_main_pushed": false,
  "source_main_sha256": "$MAIN_SHA",
  "luma_assets_sha256": "$ASSET_SHA"
}
EOF

cat > "$S/SGGI1.2/SGGI1.2_README.txt" <<'EOF'
SPIFFY'S GIFT — SGGI1.2

I1.2 is a narrowly scoped visual correction to the SGGI1.1 Giant Camp encounter.

Changes from I1.1:
- Removes the pale line previously drawn between Grumblegron and the airborne
  player/NPC/guard during the flight animation. The flight arc, horizontal travel,
  height, duration, sprite rotation and landing resolution are unchanged.
- Draws the existing player Game Over panel after the scene, giant and flight
  layers. Grumblegron's articulated arm and club can no longer appear over the
  Game Over panel.

The mechanical shoulder/arm/club animation is unchanged. Giant Camp artwork,
patrol, collision response, NPC handling, saves, dialogue, transitions and every
other gameplay system are carried forward unchanged from SGGI1.1.

The previously reported Plains-to-Camp transition concern was not changed in this
visual-only release and still requires a separate field check.

Visit spiffys-gift.com (no apostrophe in the URL).
EOF

cat > "$S/SGGI1.2/SGGI1.2_WORKER_DEPLOYMENT.txt" <<'EOF'
SGGI1.2 COMPLETE CLOUDFLARE SITE

This archive is a complete static-site package for the existing Spiffy's Gift
Cloudflare Pages/Worker site. It is not deployed by this build. Cozmo performs
the Cloudflare publication step separately after field testing.

The I1.2 game edition is in /SGGI1.2/ and is selected by the site version catalog.
The optional Kartlotta Meet WAV is carried forward. The public vanity URL is
spiffys-gift.com (without an apostrophe).
EOF

cat > "$S/SGGI1.2/SGGI1.2_TEST_RESULTS.txt" <<'EOF'
SGGI1.2 STATIC TEST RESULTS

PASS — Exact SGGI1.1 source and complete-site archives from the latest repository
       main commit were retrieved via the isolated GitHub Actions transfer bridge;
       their SHA-256 checksums matched the previously verified Dropbox baselines.
PASS — Updated Python source parses successfully.
PASS — Luma asset JSON parses successfully and is byte-for-byte unchanged.
PASS — The explicit flight-trail line draw is removed; no replacement connector
       is drawn from the launch point to the airborne victim.
PASS — Existing flight parameters remain unchanged: 260-pixel horizontal drift,
       360-pixel apex, 3.20-second duration, and the existing 720-degree sprite turn.
PASS — Grumblegron's articulated arm/club pose and keyframe routines are unchanged.
PASS — The inherited Game Over state is restored immediately after base drawing;
       the original panel styling/text is composited after the giant and flight
       layers. This is a draw-order correction, not a gameplay-state change.
PASS — New browser bootstrap points to the I1.2 bundle names.
PASS — APK and TAR payloads contain the updated I1.2 main.py and unchanged asset JSON.
PASS — Version catalog lists 15 releases, identifies I1.2 as current, and retains
       I1.1 and all earlier versions.
PASS — Historical release folders are preserved byte-for-byte.
PASS — Source and complete Cloudflare site ZIPs pass archive integrity checks.
PASS — Neither output archive contains MP4 recordings.

NOT LIVE-TESTED — Browser/Pygbag execution, rendered animation, actual flight and
Game Over visuals, and Cloudflare serving. Cozmo must field-test this package.
The separately reported Plains-to-Camp transition issue is not addressed here.
EOF

cat > "$S/SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt" <<'EOF'
===============================================================================
SPIFFY'S GIFT — LUMA LOG ENTRY 033
Release: SGGI1.2
Date: 2026-11-07
Baseline: SGGI1.1 (refreshed from latest repository main)
===============================================================================

PURPOSE

Make only the two visual corrections Cozmo identified in the I1.1 Giant Camp
field review: remove the airborne tether-like line and ensure the Game Over panel
covers the articulated troll layers. Preserve the mechanical animation and all
other gameplay exactly.

FLIGHT VISUAL

- Removed the explicit pale line draw that connected the victim's launch position
to the current airborne position during the first 82% of flight.
- No substitute line, tether, or trail is rendered.
- Player/NPC/guard flight positions, 260-pixel drift, 360-pixel apex, 3.20-second
duration, two-turn spin, shadow, and terminal landing/death handling are unchanged.

GAME OVER COMPOSITING

- The existing player GAME OVER panel was inherited-drawn before the I1.1
subclass rendered Grumblegron's separately articulated arm and club.
- The player GAME OVER panel is now temporarily deferred during the inherited
scene draw, with the original death state restored immediately afterward.
- The same panel background, text, layout, and colors are then drawn after the
whole scene, giant, and flight layers. No giant art is disabled or altered.
- This is a render-order correction; no gameplay state, save field, or death
resolution is changed.

PRESERVATION

- Grumblegron's articulated shoulder, upper/lower arm construction, hand grip,
club lag, swing keyframes, and recovery animation are byte-for-byte unchanged.
- Giant Camp art, patrol, collision behavior, Plains/camp transitions, player and
NPC flight handling, inventory, quests, saves, dialogue, and other scenes are
preserved from I1.1.
- The separately reported Plains-to-Camp transition concern is not addressed in
this narrowly scoped visual release; it remains for a later field check.
- SGGI1.1 and all older historical release folders remain untouched.
- Kartlotta Meet WAV is carried forward. No MP4 recording is included.

VALIDATION

- The exact I1.1 repository source/site archives were transferred from the latest
main commit using an isolated GitHub Actions branch. Both ZIPs passed integrity
checks and their checksums matched the verified I1.1 Dropbox baseline.
- Static Python syntax, JSON, overlay ordering, flight parameter preservation,
arm/club animation preservation, bundle contents, version catalogue, historical
folder preservation, and final ZIP integrity checks were performed.
- No live browser/Pygbag session or rendered game test was available in this build
environment. Cozmo's field test remains required.

PUBLICATION

- Complete source and complete Cloudflare site archives are provided separately.
- No GitHub main push and no Cloudflare deployment was performed.
===============================================================================
END ENTRY 033
===============================================================================
EOF

cp "$S/main.py" "$S/SGGI1.2/assets/main.py"
cp "$S/SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt" "$S/SGGI1.2_LUMA_LOG_Entry033.txt"

cp -a "$S/SGGI1.2" "$S/deploy/SGGI1.2"
cp -a "$S/SGGI1.2" "$SITE/SGGI1.2"
cp "$S/SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt" "$S/deploy/SGGI1.2_LUMA_LOG_Entry033.txt"
cp "$S/SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt" "$SITE/SGGI1.2_LUMA_LOG_Entry033.txt"

jq --arg v 'SGGI1.2' \
   --arg title 'SGGI1.2 — Flight & Game Over Visual Fixes' \
   --arg path 'SGGI1.2/play.html' \
   --arg desc 'Removes the visible launch-to-victim line during Grumblegron’s airborne flight and ensures the existing Game Over panel is composited above the giant and flight layers. The articulated club animation, flight path, two-turn spin, Giant Camp, and all other gameplay are preserved.' \
   --arg image 'SGGI1.2/stables_preview.png' \
   '.versions |= (map(if .version == "SGGI1.1" then .current = false else . end) | [{version:$v,title:$title,path:$path,description:$desc,image:$image,current:true}] + .)' \
   "$SITE/versions.json" > "$WORK/versions.json"
cp "$WORK/versions.json" "$SITE/versions.json"
cp "$WORK/versions.json" "$S/versions.json"
cp "$WORK/versions.json" "$S/deploy/versions.json"

cat > "$WORK/README_SGGWEB.txt" <<'EOF'
SPIFFY'S GIFT — CURATED SOURCE HANDOFF

Current edition: SGGI1.2. The full source archive contains the complete prior source history and milestone archives. The embedded deploy/ directory is the complete Cloudflare site.

SGGI1.2 is a focused visual correction to the I1.1 Giant Camp encounter: the pale launch-to-airborne-victim line is removed, and the existing player Game Over panel is now composited after all scene layers so Grumblegron's articulated arm and club cannot draw over it. The mechanical arm/club animation, flight path, timing, gameplay, saves, dialogue, areas, transitions and earlier selectable editions are preserved. See SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt and SGGI1.2/SGGI1.2_TEST_RESULTS.txt.

The separately reported Plains-to-Camp transition concern was not changed in this release and remains for a separate field check.

No GitHub main push or Cloudflare site deployment was performed by Luma.
EOF
cp "$WORK/README_SGGWEB.txt" "$S/README_SGGWEB.txt"
cp "$WORK/README_SGGWEB.txt" "$S/deploy/README_SGGWEB.txt"
cp "$WORK/README_SGGWEB.txt" "$SITE/README_SGGWEB.txt"
cp "$S/SGGI1.2/SGGI1.2_LUMA_LOG_Entry033.txt" "$S/SGGI1.2_LUMA_LOG_Entry033.txt"

# Keep source handoff, embedded deploy, and final site identical for I1.2.
diff -qr "$S/SGGI1.2" "$S/deploy/SGGI1.2"
diff -qr "$S/SGGI1.2" "$SITE/SGGI1.2"
cmp "$S/versions.json" "$S/deploy/versions.json"
cmp "$S/versions.json" "$SITE/versions.json"

PYTHONPYCACHEPREFIX="$WORK/pycache" python3 -m py_compile "$S/main.py" "$S/SGGI1.2/main.py"
jq empty "$S/SGGI1.2/SGGI1.2_BUILD_META.json" "$S/versions.json"
! grep -q "pygame.draw.line(trail" "$S/main.py"
grep -q "saved_dead_text.startswith('GAME OVER|')" "$S/main.py"
test "$(jq '.versions|length' "$SITE/versions.json")" -eq 15
test "$(jq '[.versions[]|select(.current==true)]|length' "$SITE/versions.json")" -eq 1
! find "$S" "$SITE" -type f -iname '*.mp4' -print -quit | grep -q .
mkdir -p "$WORK/output"

echo "I1.2 build complete"
echo "main_sha256=$MAIN_SHA"
echo "source_file_count=$(find "$S" -type f | wc -l)"
echo "site_file_count=$(find "$SITE" -type f | wc -l)"
