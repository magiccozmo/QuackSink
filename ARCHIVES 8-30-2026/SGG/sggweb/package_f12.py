"""Build and deeply validate SGGF1.2 source and Cloudflare deployment ZIPs."""
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
BASE_DEPLOY = ROOT / 'SGGF1.1_CLOUDFLARE_DEPLOY.zip'
MAIN = WORK / 'main.py'
ASSETS = WORK / 'luma_assets_e33.json'
PLAY = WORK / 'F1_play.html'
README = WORK / 'README_SGGF12.txt'
DEPLOY = ROOT / 'SGGF1.2_CLOUDFLARE_DEPLOY.zip'
SOURCE = ROOT / 'SGGF1.2_SOURCE.zip'

code = MAIN.read_bytes()
assets_bytes = ASSETS.read_bytes()
assets_doc = json.loads(assets_bytes)
page = PLAY.read_text(encoding='utf-8')
assert assets_doc['version'] == 'SGGF1.2'
assert 'VERSION = "F1.2"' in code.decode('utf-8')
assert 'for oid in (\'stable_carriage\', \'stables_foreground_fence\', \'stable_draft_horse\'):' in code.decode('utf-8')
assert all(x in page for x in ('SGGF1.2', 'sggf12.apk', 'sggf12.tar.gz', 'archive:"sggf12"'))

# Syntax and complete model regressions.
ast.parse(code.decode('utf-8'))
subprocess.run([sys.executable, '-m', 'py_compile', str(MAIN)], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'test_f12.py')], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'make_f12_changes.py')], cwd=WORK, check=True)

# Runtime payloads use the exact source code and JSON asset pack.
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

# Build on the exact F1.1 deploy package; preserve every existing file except
# the dynamic version catalog, then append the five F1.2 release files.
assert BASE_DEPLOY.exists(), BASE_DEPLOY
with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
    assert old.testzip() is None
    old_names = old.namelist()
    assert len(old_names) == 145
    assert all(x in old_names for x in (
        'index.html', 'versions.html', 'versions.json', '_headers',
        'SGGF1.1/play.html', 'SGGF1.1/favicon.png',
        'SGGF1.1/sggf11.apk', 'SGGF1.1/sggf11.tar.gz', 'SGGF1.1/README_SGGF11.txt'))
    favicon = old.read('SGGF1.1/favicon.png')
    manifest = json.loads(old.read('versions.json'))
    assert manifest['versions'][0]['version'] == 'SGGF1.1'
    assert manifest['versions'][0]['current'] is True
    for entry in manifest['versions']:
        entry['current'] = False
    manifest['versions'].insert(0, {
        'version': 'SGGF1.2',
        'title': 'SGGF 1.2',
        'path': 'SGGF1.2/play.html',
        'description': 'Horse rendering polish: all horse polygons now render both their solid fill and outline, and the Stables foreground fence is correctly drawn behind the horse. The F1.1 horse design, carriage, Kitty, stable geometry and Part One gameplay are preserved.',
        'current': True,
    })
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (WORK / 'deploy' / 'versions.json').write_bytes(manifest_bytes)
    additions = [
        ('SGGF1.2/play.html', page.encode('utf-8')),
        ('SGGF1.2/favicon.png', favicon),
        ('SGGF1.2/sggf12.apk', apkb.getvalue()),
        ('SGGF1.2/sggf12.tar.gz', tarb.getvalue()),
        ('SGGF1.2/README_SGGF12.txt', README.read_bytes()),
    ]
    with zipfile.ZipFile(DEPLOY, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as out:
        for member in old.infolist():
            payload = manifest_bytes if member.filename == 'versions.json' else old.read(member.filename)
            out.writestr(copy.copy(member), payload)
        for name, payload in additions:
            out.writestr(name, payload)

# Re-open and validate preservation, catalog, runtime ZIP and tar payload equality.
with zipfile.ZipFile(DEPLOY, 'r') as z:
    assert z.testzip() is None
    names = z.namelist()
    assert len(names) == len(old_names) + len(additions) == 150
    assert len(set(names)) == len(names)
    with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
        for name in old_names:
            if name == 'versions.json':
                continue
            assert z.read(name) == old.read(name), f'Historical/site file changed unexpectedly: {name}'
    final_doc = json.loads(z.read('versions.json'))
    assert len(final_doc['versions']) == 29
    assert final_doc['versions'][0]['version'] == 'SGGF1.2' and final_doc['versions'][0]['current'] is True
    assert final_doc['versions'][1]['version'] == 'SGGF1.1' and final_doc['versions'][1]['current'] is False
    assert sum(1 for v in final_doc['versions'] if v.get('current')) == 1
    for v in final_doc['versions']:
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', v['version'])
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*\/(?:play|index)\.html', v['path'])
    with zipfile.ZipFile(io.BytesIO(z.read('SGGF1.2/sggf12.apk'))) as runtime:
        assert runtime.testzip() is None
        assert runtime.namelist() == ['assets/main.py', 'assets/luma_assets_e33.json']
        assert runtime.read('assets/main.py') == code
        assert runtime.read('assets/luma_assets_e33.json') == assets_bytes
    with tarfile.open(fileobj=io.BytesIO(z.read('SGGF1.2/sggf12.tar.gz')), mode='r:gz') as runtime:
        assert runtime.extractfile('assets/main.py').read() == code
        assert runtime.extractfile('assets/luma_assets_e33.json').read() == assets_bytes
    final_page = z.read('SGGF1.2/play.html').decode('utf-8')
    assert 'archive:"sggf12"' in final_page and 'sggf12.apk' in final_page and 'sggf12.tar.gz' in final_page
    for name in ('index.html', 'versions.html'):
        html = z.read(name).decode('utf-8')
        assert 'isPhoneOrTablet' in html and 'navigator.userAgentData?.mobile' in html
    print(f'PASS deployment: all {len(old_names)} F1.1 site entries preserved (only version catalog advanced); {len(additions)} F1.2 entries added.')

# Build metadata with reproducible fingerprints.
horse_base = json.loads((WORK / 'F1.1_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))['assets']['stable_draft_horse']['commands']
horse_new = assets_doc['assets']['stable_draft_horse']['commands']
fill_pairs = sum(1 for c in horse_base if c.get('op') == 'polygon' and int(c.get('border', 0) or 0) > 0)
meta = {
    'version': 'SGGF1.2',
    'based_on': 'SGGF1.1',
    'repository_source_blob_sha': 'ebc6bd188beda50f96ddfd1d7a84fef22ab46e26',
    'scope': 'Corrected horse render fill semantics and Stables painter order only. Explicit filled polygons are now drawn before their retained outline strokes; fence is drawn before horse.',
    'preserved': [
        'F1.1 horse silhouette, size, colors, mane, head, harness and composition',
        'F1.1 carriage and foreground fence JSON artwork, sizes and world positions',
        'Stable background artwork, world geometry, collision and navigation',
        'Kitty art, patrol and NPC behavior',
        'F1.1 game logic, save schema, inventory, quests, driver handoff and Part One finale',
        'all 145 entries from the F1.1 Cloudflare package except the version catalog, plus all historical releases',
    ],
    'main_sha256': hashlib.sha256(code).hexdigest(),
    'assets_sha256': hashlib.sha256(assets_bytes).hexdigest(),
    'previous_deploy_sha256': hashlib.sha256(BASE_DEPLOY.read_bytes()).hexdigest(),
    'deploy_sha256': hashlib.sha256(DEPLOY.read_bytes()).hexdigest(),
    'deploy_bytes': DEPLOY.stat().st_size,
    'horse_polygon_fill_passes_added': fill_pairs,
    'horse_polygon_commands_before': len(horse_base),
    'horse_polygon_commands_after': len(horse_new),
    'stable_prop_draw_order': ['stable_carriage', 'stables_foreground_fence', 'stable_draft_horse', 'vendors', 'player'],
    'historical_site_entries_preserved': len(old_names),
    'release_catalog_versions': 29,
    'new_deployment_files': [name for name, _ in additions],
    'static_regression': 'PASS: Python AST/py_compile, Luma engine asset/world load, supported drawing ops, explicit horse fill/outline pairs, unchanged carriage/fence JSON, corrected prop painter order, unchanged Kitty recipes and Stable geometry/background, F1.0 save migration, driver breakfast handoff, Fearmonger quest reward, four-page finale, front-door mobile gate, deployment CRC and all F1.1 deployment files preserved.',
    'runtime_note': 'Build-time tests are static/model regressions. The game was not launched in a live browser during this build; please field-test deployed F1.2 before treating browser runtime behavior as verified.',
}
(WORK / 'F1.2_BUILD_META.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')

# Include current source, reproducible scripts/tests, preview art and both prior baselines.
source_files = [
    ('main.py', MAIN),
    ('luma_assets_e33.json', ASSETS),
    ('README_SGGF12.txt', README),
    ('F1_play.html', PLAY),
    ('test_f12.py', WORK / 'test_f12.py'),
    ('test_f11_baseline.py', WORK / 'test_f11.py'),
    ('make_f12_changes.py', WORK / 'make_f12_changes.py'),
    ('render_preview.py', WORK / 'render_preview.py'),
    ('package_f12.py', WORK / 'package_f12.py'),
    ('F1.2_BUILD_META.json', WORK / 'F1.2_BUILD_META.json'),
    ('F1.2_STABLES_PREVIEW.png', WORK / 'F1.2_STABLES_PREVIEW.png'),
    ('F1.2_HORSE_ASSET_PREVIEW.png', WORK / 'F1.2_HORSE_ASSET_PREVIEW.png'),
    ('F1.2_HORSE_ASSET_PREVIEW_LIGHT.png', WORK / 'F1.2_HORSE_ASSET_PREVIEW_LIGHT.png'),
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
    assert set(name for name, _ in source_files) == set(z.namelist())

print('DEPLOY:', DEPLOY, DEPLOY.stat().st_size, 'bytes')
print('DEPLOY SHA256:', hashlib.sha256(DEPLOY.read_bytes()).hexdigest())
print('SOURCE:', SOURCE, SOURCE.stat().st_size, 'bytes')
print('SOURCE SHA256:', hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print('MAIN SHA256:', meta['main_sha256'])
print('ASSETS SHA256:', meta['assets_sha256'])
