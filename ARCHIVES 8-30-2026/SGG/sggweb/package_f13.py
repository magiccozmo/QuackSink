"""Build and validate the narrowly scoped SGGF1.3 release from F1.2."""
from pathlib import Path
import ast
import copy
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path('/mnt/data')
WORK = Path(__file__).resolve().parent
BASE_DEPLOY = ROOT / 'SGGF1.2_CLOUDFLARE_DEPLOY.zip'
MAIN = WORK / 'main.py'
ASSETS = WORK / 'luma_assets_e33.json'
PLAY = WORK / 'F1_play.html'
README = WORK / 'README_SGGF13.txt'
DEPLOY = ROOT / 'SGGF1.3_CLOUDFLARE_DEPLOY.zip'
SOURCE = ROOT / 'SGGF1.3_SOURCE.zip'

code = MAIN.read_bytes()
assets_bytes = ASSETS.read_bytes()
assets_doc = json.loads(assets_bytes)
page = PLAY.read_text(encoding='utf-8')
assert assets_doc['version'] == 'SGGF1.3'
assert 'VERSION = "F1.3"' in code.decode('utf-8')
assert all(x in page for x in ('SGGF1.3', 'sggf13.apk', 'sggf13.tar.gz', 'archive:"sggf13"'))
assert 'Castle Path transition-marker' in README.read_text(encoding='utf-8')

# Syntax and complete current-release regressions.
ast.parse(code.decode('utf-8'))
subprocess.run([sys.executable, '-m', 'py_compile', str(MAIN)], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'test_f13.py')], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'render_f13_preview.py')], cwd=WORK, check=True)

# The full old art/world JSON must differ only in the explicitly authorized F1.3 items.
base_assets = json.loads((WORK / 'F1.2_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = copy.deepcopy(base_assets)
expected['version'] = 'SGGF1.3'
old_commands = expected['assets']['c1_bg_castle_path']['commands']
expected['assets']['c1_bg_castle_path']['commands'] = [
    c for c in old_commands
    if not (c.get('op') == 'line' and c.get('points') == [[748,435],[834,307]])
]
assert sum(1 for c in old_commands if c.get('op') == 'line'
           and c.get('points') == [[748,435],[834,307]]) == 3
next(c for c in expected['world']['connections']
     if c['connection_id'] == 'castle_exterior_bottom_castle_path').update(
         arrival_x=834, arrival_y=400)
expected['notes'] = (expected.get('notes', '').rstrip() +
    '\nSGGF1.3: removed the temporary Castle Path threshold guide stroke, added a visible Castle Exterior direction arrow beyond the unchanged invisible crossing threshold, and moved the Castle Exterior return landing safely onto the Castle Path approach. All other F1.2 assets, areas, gameplay, and transition logic are retained.')
assert assets_doc == expected, 'F1.3 assets contain an out-of-scope change.'

# Build the runtime APK ZIP and the Cloudflare/pygbag TAR.GZ from the exact
# source JSON and Python payloads. No existing gameplay files are rewritten.
apkb = io.BytesIO()
with zipfile.ZipFile(apkb, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as apk:
    apk.writestr('assets/main.py', code)
    apk.writestr('assets/luma_assets_e33.json', assets_bytes)

tarb = io.BytesIO()
with gzip.GzipFile(fileobj=tarb, mode='wb', compresslevel=9, mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode='w') as tf:
        for name, payload in (('assets/main.py', code), ('assets/luma_assets_e33.json', assets_bytes)):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            tf.addfile(info, io.BytesIO(payload))

# Extend the exact F1.2 site package. Preserve every F1.2/historical file byte
# for byte except the dynamic versions.json catalog, then append F1.3's 5 files.
assert BASE_DEPLOY.exists(), BASE_DEPLOY
with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
    assert old.testzip() is None
    old_names = old.namelist()
    assert len(old_names) == 155 - 5
    assert all(x in old_names for x in (
        'index.html', 'versions.html', 'versions.json', '_headers',
        'SGGF1.2/play.html', 'SGGF1.2/favicon.png',
        'SGGF1.2/sggf12.apk', 'SGGF1.2/sggf12.tar.gz', 'SGGF1.2/README_SGGF12.txt'))
    favicon = old.read('SGGF1.2/favicon.png')
    manifest = json.loads(old.read('versions.json'))
    assert manifest['versions'][0]['version'] == 'SGGF1.2'
    assert manifest['versions'][0]['current'] is True
    for entry in manifest['versions']:
        entry['current'] = False
    manifest['versions'].insert(0, {
        'version': 'SGGF1.3',
        'title': 'SGGF 1.3',
        'path': 'SGGF1.3/play.html',
        'description': 'Castle Path navigation clarity: the temporary threshold guide line is removed; a Castle Exterior arrow and label sit just beyond the unchanged invisible crossing boundary; returning from Castle Exterior places Spiffy safely on the lower approach. All F1.2 gameplay and other art are retained.',
        'current': True,
    })
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (WORK / 'deploy' / 'versions.json').write_bytes(manifest_bytes)
    additions = [
        ('SGGF1.3/play.html', page.encode('utf-8')),
        ('SGGF1.3/favicon.png', favicon),
        ('SGGF1.3/sggf13.apk', apkb.getvalue()),
        ('SGGF1.3/sggf13.tar.gz', tarb.getvalue()),
        ('SGGF1.3/README_SGGF13.txt', README.read_bytes()),
    ]
    with zipfile.ZipFile(DEPLOY, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as out:
        for member in old.infolist():
            payload = manifest_bytes if member.filename == 'versions.json' else old.read(member.filename)
            out.writestr(copy.copy(member), payload)
        for name, payload in additions:
            out.writestr(name, payload)

# Validate full site preservation, version manifest, runtime contents, and loader refs.
with zipfile.ZipFile(DEPLOY, 'r') as z:
    assert z.testzip() is None
    names = z.namelist()
    assert len(names) == len(old_names) + len(additions) == 155
    assert len(set(names)) == len(names)
    with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
        for name in old_names:
            if name == 'versions.json':
                continue
            assert z.read(name) == old.read(name), f'Historical/site file changed unexpectedly: {name}'
    final_doc = json.loads(z.read('versions.json'))
    assert len(final_doc['versions']) == 30
    assert final_doc['versions'][0]['version'] == 'SGGF1.3' and final_doc['versions'][0]['current'] is True
    assert final_doc['versions'][1]['version'] == 'SGGF1.2' and final_doc['versions'][1]['current'] is False
    assert sum(1 for v in final_doc['versions'] if v.get('current')) == 1
    for v in final_doc['versions']:
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', v['version'])
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*\/(?:play|index)\.html', v['path'])
    with zipfile.ZipFile(io.BytesIO(z.read('SGGF1.3/sggf13.apk'))) as runtime:
        assert runtime.testzip() is None
        assert runtime.namelist() == ['assets/main.py', 'assets/luma_assets_e33.json']
        assert runtime.read('assets/main.py') == code
        assert runtime.read('assets/luma_assets_e33.json') == assets_bytes
    with tarfile.open(fileobj=io.BytesIO(z.read('SGGF1.3/sggf13.tar.gz')), mode='r:gz') as runtime:
        assert runtime.extractfile('assets/main.py').read() == code
        assert runtime.extractfile('assets/luma_assets_e33.json').read() == assets_bytes
    final_page = z.read('SGGF1.3/play.html').decode('utf-8')
    assert 'archive:"sggf13"' in final_page and 'sggf13.apk' in final_page and 'sggf13.tar.gz' in final_page
    for name in ('index.html', 'versions.html'):
        html = z.read(name).decode('utf-8')
        assert 'isPhoneOrTablet' in html and 'navigator.userAgentData?.mobile' in html
    print(f'PASS deploy: {len(old_names)} F1.2/historical site entries preserved except versions.json; {len(additions)} F1.3 entries added.')

# Reproducible build ledger with source/base hashes and tested scope.
meta = {
    'version': 'SGGF1.3',
    'based_on': 'SGGF1.2',
    'repository': 'magiccozmo/QuackSink',
    'source_folder': 'ARCHIVES 8-30-2026/SGG/sggweb',
    'base_source_blob_sha': '7cd25fd875ee2b7102888488992f6e9ffadf1836',
    'base_deploy_blob_sha': 'a51abb9aeb5d4cbab6ffd535635859b4b4ed19a5',
    'scope': 'Remove the temporary Castle Path threshold guide stroke; add a castle-ward directional Castle Exterior arrow/label; move the reverse landing to (834, 400). No other art, world, gameplay or threshold logic changes.',
    'preserved': [
        'E5.6 crossing threshold coordinates, vectors, crossing direction and lateral tolerance (byte-for-byte class preservation)',
        'All F1.2 asset recipes except the three-pass Castle Path marker line',
        'All F1.2 world definitions except reverse arrival_x/arrival_y (834, 400)',
        'Stables horse, carriage, fence, background, Kitty art/behavior and Stables geometry',
        'F1.2 save behavior, inventory, driver/sammich handoff, Fearmonger quest, comments, Cozmo finale and Part One gameplay',
        'All F1.2 and earlier deployment files; only versions.json advances and five F1.3 files are added',
    ],
    'main_sha256': hashlib.sha256(code).hexdigest(),
    'assets_sha256': hashlib.sha256(assets_bytes).hexdigest(),
    'previous_deploy_sha256': hashlib.sha256(BASE_DEPLOY.read_bytes()).hexdigest(),
    'deploy_sha256': hashlib.sha256(DEPLOY.read_bytes()).hexdigest(),
    'deploy_bytes': DEPLOY.stat().st_size,
    'historical_site_entries_preserved': len(old_names),
    'release_catalog_versions': 30,
    'new_deployment_files': [name for name, _ in additions],
    'static_regression': 'PASS: Python AST/py_compile; full adapted F1.2 tests; strict full-JSON F1.2-to-F1.3 diff; exact E5.6 state-machine/model preservation; Castle Exterior arrow orientation; real F1.3 model return to (834,400); authored navigation corridor; threshold-lookup tolerance; deployment CRC and byte-for-byte historical file preservation.',
    'runtime_note': 'Build-time tests and renderer-generated preview passed. The game was not launched in a live browser during this build; please field-test deployed F1.3 before treating browser runtime behavior as verified.',
}
meta_path = WORK / 'F1.3_BUILD_META.json'
meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')

# Source handoff: current F1.3 implementation, tests and package scripts, exact
# F1.2 baseline, retained F1.1/F1.0 baselines, and versioned site-front-door files.
source_files = [
    ('main.py', MAIN),
    ('luma_assets_e33.json', ASSETS),
    ('README_SGGF13.txt', README),
    ('F1_play.html', PLAY),
    ('test_f13.py', WORK / 'test_f13.py'),
    ('make_f13_changes.py', WORK / 'make_f13_changes.py'),
    ('render_f13_preview.py', WORK / 'render_f13_preview.py'),
    ('package_f13.py', WORK / 'package_f13.py'),
    ('F1.3_BUILD_META.json', meta_path),
    ('F1.3_CASTLE_PATH_PREVIEW.png', WORK / 'F1.3_CASTLE_PATH_PREVIEW.png'),
    ('F1.3_MARKER_DETAIL.png', WORK / 'F1.3_MARKER_DETAIL.png'),
    ('F1.2_BASE_MAIN.py', WORK / 'F1.2_BASE_MAIN.py'),
    ('F1.2_BASE_LUMA_ASSETS.json', WORK / 'F1.2_BASE_LUMA_ASSETS.json'),
    ('F1.2_BUILD_META.json', WORK / 'F1.2_BUILD_META.json'),
    ('F1.2_STABLES_PREVIEW.png', WORK / 'F1.2_STABLES_PREVIEW.png'),
    ('F1.2_HORSE_ASSET_PREVIEW.png', WORK / 'F1.2_HORSE_ASSET_PREVIEW.png'),
    ('F1.2_HORSE_ASSET_PREVIEW_LIGHT.png', WORK / 'F1.2_HORSE_ASSET_PREVIEW_LIGHT.png'),
    ('test_f12.py', WORK / 'test_f12.py'),
    ('make_f12_changes.py', WORK / 'make_f12_changes.py'),
    ('package_f12.py', WORK / 'package_f12.py'),
    ('render_preview.py', WORK / 'render_preview.py'),
    ('test_f11_baseline.py', WORK / 'test_f11_baseline.py'),
    ('F1.1_MAIN_BASE.py', WORK / 'F1.1_MAIN_BASE.py'),
    ('F1.1_BASE_LUMA_ASSETS.json', WORK / 'F1.1_BASE_LUMA_ASSETS.json'),
    ('F1.1_BUILD_META.json', WORK / 'F1.1_BUILD_META.json'),
    ('F1.1_HORSE_ASSET_PREVIEW.png', WORK / 'F1.1_HORSE_ASSET_PREVIEW.png'),
    ('F1.1_STABLES_PREVIEW.png', WORK / 'F1.1_STABLES_PREVIEW.png'),
    ('F1.0_MAIN_BASE.py', WORK / 'F1.0_MAIN_BASE.py'),
    ('F1.0_BASE_LUMA_ASSETS.json', WORK / 'F1.0_BASE_LUMA_ASSETS.json'),
    ('F1.0_BUILD_META.json', WORK / 'F1.0_BUILD_META.json'),
    ('F1.0_STABLES_BACKGROUND_PREVIEW.png', WORK / 'F1.0_STABLES_BACKGROUND_PREVIEW.png'),
    ('deploy/index.html', WORK / 'deploy' / 'index.html'),
    ('deploy/versions.html', WORK / 'deploy' / 'versions.html'),
    ('deploy/versions.json', WORK / 'deploy' / 'versions.json'),
    ('deploy/_headers', WORK / 'deploy' / '_headers'),
]
with zipfile.ZipFile(SOURCE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
    for arcname, path in source_files:
        assert path.exists(), f'Missing source component: {path}'
        out.write(path, arcname)
with zipfile.ZipFile(SOURCE, 'r') as z:
    assert z.testzip() is None
    assert z.read('main.py') == code
    assert z.read('luma_assets_e33.json') == assets_bytes
    assert z.read('F1_play.html') == page.encode('utf-8')
    assert z.read('F1.2_BASE_MAIN.py') == (WORK/'F1.2_BASE_MAIN.py').read_bytes()
    assert set(name for name, _ in source_files) == set(z.namelist())

print('DEPLOY:', DEPLOY, DEPLOY.stat().st_size, 'bytes')
print('DEPLOY SHA256:', hashlib.sha256(DEPLOY.read_bytes()).hexdigest())
print('SOURCE:', SOURCE, SOURCE.stat().st_size, 'bytes')
print('SOURCE SHA256:', hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print('MAIN SHA256:', meta['main_sha256'])
print('ASSETS SHA256:', meta['assets_sha256'])
