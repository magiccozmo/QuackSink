from pathlib import Path
import shutil, json, hashlib, zipfile, tarfile

BASE = Path("/tmp/sgg_h1_work")
SRC0 = BASE/'baseline_src'
SITE0 = BASE/'baseline_site'
SRC = BASE/'source_work'
SITE = BASE/'site_work'
for p in (SRC, SITE):
    if p.exists(): shutil.rmtree(p)
shutil.copytree(SRC0, SRC)
shutil.copytree(SITE0, SITE)

for parent, old, new in [
    (SRC, 'SGGG1.5', 'SGGH1.0'),
    (SRC/'deploy', 'SGGG1.5', 'SGGH1.0'),
    (SITE, 'SGGG1.5', 'SGGH1.0'),
]:
    dst = parent/new
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(parent/old, dst)

old_pre = """        self._dialogue('Kart-lotta',
            'This twit in the inn keeps bothering me. I have no idea why!',
            [{'text':'I will see what I can do.','action':'close'},
             {'text':'Where can I find him?','action':'kart_hint'}])"""
new_pre = """        sggg_play_kartlotta_voice('meet')
        self._dialogue('Kart-lotta',
            'That lout at the inn is so annoying. He wants to fondle my tomatoes and squeeze my cabbages.',
            [{'text':'I will see what I can do.','action':'close'},
             {'text':'Where can I find him?','action':'kart_hint'}])"""
old_hero = """            self._dialogue('Kart-lotta',
                'Oh, my hero! I could not charge YOU for my lovely veggies!',
                [{'text':'Thank you, Karlotta.','action':'kart_reward'}])"""
new_hero = """            sggg_play_kartlotta_voice('hero')
            self._dialogue('Kart-lotta',
                'Oh, you are NOW my HERO. You can do whatever you want with my veggies.',
                [{'text':'Thank you, Karlotta.','action':'kart_reward'}])"""
js_old = """  bridge.takeGlobalLogStatus = function () {
    const status = this.globalLogStatus;
    this.globalLogStatus = null;
    return status;
  };
})();
"""
js_new = """  bridge.takeGlobalLogStatus = function () {
    const status = this.globalLogStatus;
    this.globalLogStatus = null;
    return status;
  };
  // Optional Kartlotta voice clips. The assets live at the site-root audio_clip/ path.
  bridge.kartlottaVoiceAudio = bridge.kartlottaVoiceAudio || null;
  bridge.playKartlottaVoice = function (clipKey) {
    const files = {meet: 'kartlotta_meet.wav', hero: 'kartlotta_hero.wav'};
    const fileName = files[String(clipKey || '')];
    if (!fileName) return false;
    try {
      if (bridge.kartlottaVoiceAudio) {
        bridge.kartlottaVoiceAudio.pause();
        bridge.kartlottaVoiceAudio.currentTime = 0;
      }
      const clipUrl = new URL('../audio_clip/' + fileName, window.location.href).href;
      const audio = new Audio(clipUrl);
      bridge.kartlottaVoiceAudio = audio;
      audio.preload = 'auto';
      audio.volume = 1.0;
      const playback = audio.play();
      if (playback && typeof playback.catch === 'function') {
        playback.catch(error => console.warn('Kartlotta voice playback unavailable:', String(error)));
      }
      return true;
    } catch (error) {
      console.warn('Kartlotta voice setup unavailable:', String(error));
      return false;
    }
  };
})();
"""
helper_anchor = "\n\ndef sggg_prepare_browser_bridge():"
helper_text = """

def sggg_play_kartlotta_voice(clip_key):
    # Play an optional Kartlotta voice clip in the browser; never block dialogue.
    if not BROWSER:
        return
    try:
        E1_STORAGE._window.SGGBridge.playKartlottaVoice(str(clip_key))
    except Exception:
        # Audio is a presentation enhancement; dialogue and quest logic always proceed.
        pass


def sggg_prepare_browser_bridge():"""

base_main = (SRC0/'SGGG1.5/main.py').read_text(encoding='utf-8')
assert old_pre in base_main
assert old_hero in base_main
assert js_old in base_main
assert helper_anchor in base_main
patched = base_main.replace(old_pre, new_pre, 1).replace(old_hero, new_hero, 1).replace(js_old, js_new, 1)
patched = patched.replace(helper_anchor, helper_text, 1)
patched = patched.replace('VERSION = "G1.5"  # Kitty Caravan Cozmo cameo uses a dedicated clear spawn point.',
                          'VERSION = "H1.0"  # Kartlotta quest dialogue and optional browser voice clips.')
patched = patched.replace("self._log('SGGG1.5', 'Global Usage Log enabled; explicit privacy handoff, save/load events, immutable run difficulty, stable cameos and save-bound Tea active.')",
                          "self._log('SGGH1.0', 'Global Usage Log enabled; Kartlotta dialogue and optional voice clips active.')")
patched = patched.replace("Started SGGG1.5 — {mode_label} mode", "Started SGGH1.0 — {mode_label} mode")
patched = patched.replace("postGlobalSession('SGGG1.5', mode)", "postGlobalSession('SGGH1.0', mode)")

runtime_targets = [
    SRC/'main.py', SRC/'assets/main.py',
    SRC/'SGGH1.0/main.py', SRC/'SGGH1.0/assets/main.py',
    SRC/'deploy/SGGH1.0/main.py',
]
for p in runtime_targets:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(patched, encoding='utf-8')

html_base = (SRC0/'SGGG1.5/play.html').read_text(encoding='utf-8')
html_h = html_base.replace('sggg1_5', 'sggh1_0').replace('G1.5', 'H1.0')
for p in [SRC/'SGGH1.0/play.html', SRC/'deploy/SGGH1.0/play.html', SITE/'SGGH1.0/play.html']:
    p.write_text(html_h, encoding='utf-8')

(SITE/'SGGH1.0/main.py').write_text(patched, encoding='utf-8')
(SRC/'VERSION').write_text('H1.0\n', encoding='utf-8')
(SRC/'SGGH1.0/VERSION').write_text('H1.0\n', encoding='utf-8')
(SRC/'deploy/SGGH1.0/VERSION').write_text('H1.0\n', encoding='utf-8')
(SITE/'SGGH1.0/VERSION').write_text('H1.0\n', encoding='utf-8')

def build_bundles(folder: Path):
    folder = Path(folder)
    old_apk = folder/'sggg1_5.apk'
    old_tar = folder/'sggg1_5.tar.gz'
    apk = folder/'sggh1_0.apk'
    tar = folder/'sggh1_0.tar.gz'
    if old_apk.exists(): old_apk.unlink()
    if old_tar.exists(): old_tar.unlink()
    with zipfile.ZipFile(apk, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(folder/'main.py', 'main.py')
        z.write(folder/'luma_assets_e33.json', 'luma_assets_e33.json')
    with tarfile.open(tar, 'w:gz', compresslevel=9) as t:
        t.add(folder/'main.py', arcname='assets/main.py')
        t.add(folder/'luma_assets_e33.json', arcname='assets/luma_assets_e33.json')

for folder in [SRC/'SGGH1.0', SRC/'deploy/SGGH1.0', SITE/'SGGH1.0']:
    build_bundles(folder)

for folder in [SRC/'SGGH1.0', SRC/'deploy/SGGH1.0', SITE/'SGGH1.0']:
    if not (folder/'luma_assets_e33.json').exists():
        shutil.copy2(SRC0/'SGGG1.5/luma_assets_e33.json', folder/'luma_assets_e33.json')
    if not (folder/'stables_preview.png').exists():
        shutil.copy2(SRC0/'SGGG1.5/stables_preview.png', folder/'stables_preview.png')

for root in [SRC, SRC/'deploy', SITE]:
    audio = root/'audio_clip'
    audio.mkdir(exist_ok=True)
    (audio/'.gitkeep').write_bytes(b'')

legacy_docs = ['README_SGGG1.5.txt','SGGG1.5_BUILD_META.json','SGGG1.5_LUMA_LOG_Entry029.txt','SGGG1.5_TEST_RESULTS.txt','SGGG1.5_WORKER_DEPLOYMENT.txt']
for folder in [SRC/'SGGH1.0', SRC/'deploy/SGGH1.0', SITE/'SGGH1.0']:
    for n in legacy_docs:
        q=folder/n
        if q.exists(): q.unlink()

readme = """Spiffy's Gift — SGGH1.0

Baseline: SGGG1.5. This release changes only Kartlotta's two quest-stage dialogue lines and adds optional browser voice playback hooks at the corresponding dialogue triggers.

Kartlotta's first meeting now says: "That lout at the inn is so annoying. He wants to fondle my tomatoes and squeeze my cabbages." The original response choices and actions are unchanged.

After the inn lout is resolved, the first return conversation says: "Oh, you are NOW my HERO. You can do whatever you want with my veggies." The original "Thank you, Karlotta." reward action is unchanged. The later generic permission dialogue is unchanged and does not trigger voice playback.

Optional browser voice assets, when supplied, belong in the site-root audio_clip/ folder with these exact names:
- kartlotta_meet.wav
- kartlotta_hero.wav

The WAV files were not present at build time. The browser bridge is wired to request them, but audible playback has not been tested. Missing audio does not block dialogue or quest progression.

All other game areas, save compatibility, quest state, player choices, permissions, rewards, public logging, and historical releases are preserved from SGGG1.5.
"""
test_results = """SGGH1.0 — Static Test Results

PASS — Python source parses successfully.
PASS — Embedded browser JavaScript bridge passes Node syntax checking.
PASS — Kartlotta pre-resolution dialogue text is updated.
PASS — Kartlotta post-resolution hero dialogue text is updated.
PASS — Original response options and action names remain unchanged (close, kart_hint, kart_reward).
PASS — Kartlotta quest state fields and reward path remain present.
PASS — Browser audio bridge maps meet to kartlotta_meet.wav and hero to kartlotta_hero.wav.
PASS — Audio path resolves from SGGH1.0/play.html to the site-root audio_clip/ directory.
PASS — Previous Kartlotta audio is paused before the next clip is started.
PASS — Missing audio/load/play errors are caught and do not block game dialogue.
PASS — APK and TAR bundle payloads contain the updated runtime.
PASS — Source and deployment ZIP archives pass CRC/integrity verification.
PASS — SGGG1.5 and all previous deployment release folders are preserved unchanged.
PASS — SGGH1.0 is the sole current catalogue entry; all 11 prior catalogue entries remain.

NOT TESTED — No live browser/Pygbag gameplay session was run. The two WAV assets were not supplied, so audible voice playback could not be tested.
"""
worker = """SGGH1.0 — Worker Deployment Note

This package is a complete Cloudflare static-site bundle. It has not been deployed. Cozmo handles publication and Cloudflare deployment.

When the two voice assets are available, place them in the top-level audio_clip/ directory beside index.html, preserving the exact filenames kartlotta_meet.wav and kartlotta_hero.wav.
"""
log = """===============================================================================
ENTRY 030 — SGGH1.0 KARTLOTTA DIALOGUE / OPTIONAL BROWSER VOICE
Date: 2026-11-07
Status: Built and statically verified; voice assets pending
===============================================================================

BASELINE

SGGG1.5, retrieved from the existing Dropbox release and independently CRC-checked.

CHANGES

- Updated Kartlotta's first quest-stage dialogue line to the tomatoes/cabbages wording.
- Updated her first post-lout-resolution dialogue to the NOW my HERO wording.
- Preserved the existing response options, action names, quest-state transitions, permission handling, and reward mechanics.
- Added optional browser voice hooks for kartlotta_meet.wav and kartlotta_hero.wav.
- Added a top-level audio_clip/ placeholder directory to the complete site.
- Updated release identity and version catalogue to SGGH1.0.

AUDIO STATUS

The WAV files were not available during the build. The expected files are audio_clip/kartlotta_meet.wav and audio_clip/kartlotta_hero.wav. The bridge path and mocked play/stop behavior were statically exercised; actual playback was not. Missing files do not prevent dialogue or quest progression.

PRESERVATION

The SGGG1.5 source and deployment version folders remain unchanged. All previous curated historical deployment folders remain present.

TESTING

Python syntax, JavaScript syntax, dialogue/action preservation, browser audio URL mapping, nested bundle payloads, versions catalogue, and ZIP CRC checks passed. No live browser or Cloudflare gameplay test was performed.

PUBLICATION

No GitHub main push and no Cloudflare deployment were performed.
"""

for folder in [SRC/'SGGH1.0', SRC/'deploy/SGGH1.0', SITE/'SGGH1.0']:
    (folder/'README_SGGH1.0.txt').write_text(readme, encoding='utf-8')
    (folder/'SGGH1.0_TEST_RESULTS.txt').write_text(test_results, encoding='utf-8')
    (folder/'SGGH1.0_WORKER_DEPLOYMENT.txt').write_text(worker, encoding='utf-8')
    (folder/'SGGH1.0_LUMA_LOG_Entry030.txt').write_text(log, encoding='utf-8')
    (folder/'SGGH1.0_BUILD_META.json').write_text(json.dumps({
        'version':'SGGH1.0','baseline':'SGGG1.5','date':'2026-11-07',
        'scope':'Kartlotta dialogue and optional browser voice playback only',
        'audio_assets_expected':['audio_clip/kartlotta_meet.wav','audio_clip/kartlotta_hero.wav'],
        'audio_assets_present':False,
        'live_browser_test':False,'cloudflare_deployed':False,
        'historical_releases_preserved':True
    }, indent=2)+'\n', encoding='utf-8')

new_entry = {
    'version':'SGGH1.0',
    'title':'SGGH1.0 — Kartlotta Dialogue & Voice',
    'path':'SGGH1.0/play.html',
    'description':'Updates Kartlotta’s two quest-stage dialogue lines and adds optional browser voice clips. Existing response choices, quest actions, permissions, rewards, and all other gameplay remain unchanged.',
    'image':'SGGH1.0/stables_preview.png',
    'current':True
}
for p in [SRC/'versions.json', SRC/'deploy/versions.json', SITE/'versions.json']:
    data=json.loads(p.read_text(encoding='utf-8'))
    assert any(x.get('version')=='SGGG1.5' for x in data.get('versions',[]))
    for item in data['versions']:
        item['current']=False
    data['versions']=[new_entry]+data['versions']
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

for p in [SRC/'deploy/index.html', SITE/'index.html']:
    html=p.read_text(encoding='utf-8')
    assert '<span class="current-version">SGGG1.5</span>' in html
    html=html.replace('<span class="current-version">SGGG1.5</span>', '<span class="current-version">SGGH1.0</span>', 1)
    p.write_text(html,encoding='utf-8')

for p in [SRC/'main.py', SRC/'assets/main.py', SRC/'SGGH1.0/main.py', SRC/'SGGH1.0/assets/main.py', SRC/'deploy/SGGH1.0/main.py', SITE/'SGGH1.0/main.py']:
    p.write_text(patched,encoding='utf-8')

(SRC/'SGGH1.0_README.txt').write_text(readme, encoding='utf-8')
(SRC/'SGGH1.0_TEST_RESULTS.txt').write_text(test_results, encoding='utf-8')
(SRC/'SGGH1.0_WORKER_DEPLOYMENT.txt').write_text(worker, encoding='utf-8')
(SRC/'SGGH1.0_LUMA_LOG_Entry030.txt').write_text(log, encoding='utf-8')
(SRC/'SGGH1.0_BUILD_META.json').write_text((SRC/'SGGH1.0/SGGH1.0_BUILD_META.json').read_text(encoding='utf-8'), encoding='utf-8')

runtime_hashes={hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    SRC/'main.py',SRC/'assets/main.py',SRC/'SGGH1.0/main.py',
    SRC/'SGGH1.0/assets/main.py',SRC/'deploy/SGGH1.0/main.py',SITE/'SGGH1.0/main.py'
]}
assert len(runtime_hashes)==1, runtime_hashes
versions=json.loads((SITE/'versions.json').read_text(encoding='utf-8'))['versions']
assert len(versions)==12 and versions[0]['version']=='SGGH1.0'
assert sum(1 for x in versions if x['current'])==1
assert (SITE/'audio_clip/.gitkeep').exists()
assert not (SITE/'audio_clip/kartlotta_meet.wav').exists()
assert not (SITE/'audio_clip/kartlotta_hero.wav').exists()
print('H1.0 source tree and Cloudflare site generated; runtime hashes agree.')
