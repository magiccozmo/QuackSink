"""Package and validate SGGF1.5 while preserving every deployed prior release."""
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
BASE_DEPLOY = ROOT / 'SGGF1.4_CLOUDFLARE_DEPLOY.zip'
MAIN = WORK / 'main.py'
ASSETS = WORK / 'luma_assets_e33.json'
PLAY = WORK / 'F1_play.html'
README = WORK / 'README_SGGF15.txt'
PREVIEW = WORK / 'F1.5_CASTLE_HALL_PREVIEW.png'
DEPLOY = ROOT / 'SGGF1.5_CLOUDFLARE_DEPLOY.zip'
SOURCE = ROOT / 'SGGF1.5_SOURCE.zip'
META_PATH = WORK / 'F1.5_BUILD_META.json'

assert BASE_DEPLOY.exists(), BASE_DEPLOY
assert README.exists() and PREVIEW.exists()
code = MAIN.read_bytes()
assets_bytes = ASSETS.read_bytes()
assets_doc = json.loads(assets_bytes)
page = PLAY.read_text(encoding='utf-8')
assert assets_doc['version'] == 'SGGF1.5'
assert b'VERSION = "F1.5"' in code
assert all(x in page for x in ('SGGF1.5', 'sggf15.apk', 'sggf15.tar.gz', 'archive:"sggf15"'))
assert 'castle hall redesign' in README.read_text(encoding='utf-8').lower()

# Repeatable build checks.
ast.parse(code.decode('utf-8'))
subprocess.run([sys.executable, '-m', 'py_compile', str(MAIN)], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'test_f15.py')], cwd=WORK, check=True)

base_assets = json.loads((WORK / 'F1.4_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = copy.deepcopy(base_assets)
expected['version'] = assets_doc['version']
expected['notes'] = assets_doc['notes']
expected['assets']['c1_bg_castle_hall'] = assets_doc['assets']['c1_bg_castle_hall']
expected['assets']['locked_door'] = assets_doc['assets']['locked_door']
base_vault = next(o for o in expected['world']['objects'] if o['object_id'] == 'vault_locked_door')
new_vault = next(o for o in assets_doc['world']['objects'] if o['object_id'] == 'vault_locked_door')
base_vault.update({k: new_vault[k] for k in ('name', 'x', 'y', 'width', 'height', 'activity')})
assert assets_doc == expected, 'F1.5 world/art JSON changed outside the approved Castle Hall/vault scope.'

# Ensure all existing F1.4 baseline files remain available to reproduce the build.
for filename in ('F1.4_BASE_MAIN.py', 'F1.4_BASE_LUMA_ASSETS.json', 'F1.4_BASE_F1_play.html'):
    assert (WORK / filename).exists(), f'Missing reproducible F1.4 baseline: {filename}'

# Build exact runtime archive bytes from F1.5 code and world JSON.
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

# Extend the complete F1.4 deploy package, keeping every old member byte-for-byte
# except versions.json, and append the five F1.5 browser runtime files.
with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
    assert old.testzip() is None
    old_names = old.namelist()
    assert len(old_names) == 160
    assert all(x in old_names for x in (
        'index.html', 'versions.html', 'versions.json', '_headers',
        'SGGF1.4/play.html', 'SGGF1.4/favicon.png',
        'SGGF1.4/sggf14.apk', 'SGGF1.4/sggf14.tar.gz', 'SGGF1.4/README_SGGF14.txt'))
    favicon = old.read('SGGF1.4/favicon.png')
    manifest = json.loads(old.read('versions.json'))
    assert manifest['versions'][0]['version'] == 'SGGF1.4'
    assert manifest['versions'][0]['current'] is True
    for entry in manifest['versions']:
        entry['current'] = False
    manifest['versions'].insert(0, {
        'version': 'SGGF1.5',
        'title': 'SGGF 1.5',
        'path': 'SGGF1.5/play.html',
        'description': 'Castle Hall is rebuilt to match the F1.4 fortress. The left door leads to the Mage Room; the middle door returns outside unchanged; the right door is an interactable, permanently locked bank vault with item-specific Zork-style dialogue. The existing off-centre platter seam remains, with a persistent Special Hard Hitbox slider controlling target precision. Previous world transitions, movement mesh, gameplay, and saves are retained.',
        'current': True,
    })
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (WORK / 'deploy' / 'versions.json').write_bytes(manifest_bytes)
    additions = [
        ('SGGF1.5/play.html', page.encode('utf-8')),
        ('SGGF1.5/favicon.png', favicon),
        ('SGGF1.5/sggf15.apk', apkb.getvalue()),
        ('SGGF1.5/sggf15.tar.gz', tarb.getvalue()),
        ('SGGF1.5/README_SGGF15.txt', README.read_bytes()),
    ]
    with zipfile.ZipFile(DEPLOY, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as out:
        for member in old.infolist():
            payload = manifest_bytes if member.filename == 'versions.json' else old.read(member.filename)
            out.writestr(copy.copy(member), payload)
        for name, payload in additions:
            out.writestr(name, payload)

# Validate deployment archive and all runtime payloads.
with zipfile.ZipFile(DEPLOY, 'r') as z:
    assert z.testzip() is None
    names = z.namelist()
    assert len(names) == len(old_names) + len(additions) == 165
    assert len(set(names)) == len(names)
    with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
        for name in old_names:
            if name == 'versions.json':
                continue
            assert z.read(name) == old.read(name), f'Historic deployed file changed: {name}'
    final_doc = json.loads(z.read('versions.json'))
    assert len(final_doc['versions']) == 32
    assert final_doc['versions'][0]['version'] == 'SGGF1.5' and final_doc['versions'][0]['current'] is True
    assert final_doc['versions'][1]['version'] == 'SGGF1.4' and final_doc['versions'][1]['current'] is False
    assert sum(1 for v in final_doc['versions'] if v.get('current')) == 1
    for v in final_doc['versions']:
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', v['version'])
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*\/(?:play|index)\.html', v['path'])
    with zipfile.ZipFile(io.BytesIO(z.read('SGGF1.5/sggf15.apk'))) as runtime:
        assert runtime.testzip() is None
        assert runtime.namelist() == ['assets/main.py', 'assets/luma_assets_e33.json']
        assert runtime.read('assets/main.py') == code
        assert runtime.read('assets/luma_assets_e33.json') == assets_bytes
    with tarfile.open(fileobj=io.BytesIO(z.read('SGGF1.5/sggf15.tar.gz')), mode='r:gz') as runtime:
        assert runtime.extractfile('assets/main.py').read() == code
        assert runtime.extractfile('assets/luma_assets_e33.json').read() == assets_bytes
    final_page = z.read('SGGF1.5/play.html').decode('utf-8')
    assert 'archive:"sggf15"' in final_page and 'sggf15.apk' in final_page and 'sggf15.tar.gz' in final_page
    for name in ('index.html', 'versions.html'):
        html = z.read(name).decode('utf-8')
        assert 'isPhoneOrTablet' in html and 'navigator.userAgentData?.mobile' in html
print(f'PASS deploy: {len(old_names)} previous/historical site entries preserved except versions.json; {len(additions)} F1.5 entries added.')

# Source archive: everything required to reproduce the new release and inspect
# previous baselines, excluding caches and nested/release ZIPs.
source_files = []
for path in sorted(WORK.iterdir()):
    if not path.is_file():
        continue
    if path.suffix.lower() in ('.zip', '.pyc') or path.name.startswith('.'):
        continue
    if path.name in ('F1.5_BUILD_META.json',):
        continue  # written below after final package hashes are known
    source_files.append((path.name, path))
for name in ('index.html', 'versions.html', 'versions.json', '_headers'):
    p = WORK / 'deploy' / name
    assert p.exists()
    source_files.append((f'deploy/{name}', p))
assert len({name for name, _ in source_files}) == len(source_files)

meta = {
    'version': 'SGGF1.5',
    'based_on': 'SGGF1.4',
    'repository': 'magiccozmo/QuackSink',
    'source_folder': 'ARCHIVES 8-30-2026/SGG/sggweb',
    'scope': 'Castle Hall art redesign, permanently locked interactive Bank Vault Door dialogue, and configurable off-centre platter clip hitbox. Existing Mage Room and Castle Exterior transitions, original seam connection and all other F1.4 gameplay/world data are preserved.',
    'art': {
        'castle_hall_commands': len(assets_doc['assets']['c1_bg_castle_hall']['commands']),
        'vault_door_commands': len(assets_doc['assets']['locked_door']['commands']),
        'preview': 'F1.5_CASTLE_HALL_PREVIEW.png',
    },
    'preserved': [
        'F1.4 Castle Exterior and Castle Path artwork, all other art assets and scenes.',
        'All F1.4 world geometry, navigation regions, collision definitions, left Mage Room door/trigger/connection/arrival, middle Castle Exterior door/trigger/connection/arrival, existing vault seam object, and vault clip connection.',
        'All F1.4 gameplay/save/quest/inventory/Kitty/Stables/carriage/comments/Part One code apart from the explicitly listed F1.5 additions and release/hint labels.',
        'Every previously deployed site member byte-for-byte except versions.json; five F1.5 versioned browser files are appended.',
    ],
    'vault': {
        'object_id': 'vault_locked_door',
        'dialogue': 'Pick lock; Force open; Leave the vault alone',
        'pick_lock_response': "Are you kidding? Even the Skeleton Key ain't gonna pick this.",
        'plate_response': 'Oddly the plate ALMOST squeezes in a gap.',
        'can_open': False,
        'inventory_items_consumed': False,
    },
    'special_hard_hitbox': {
        'config_key': 'special_hard_hitbox',
        'label': 'Special Hard Hitbox',
        'range': [1.0, 5.0],
        'default': 3.0,
        '1.0': 'larger and more forgiving',
        '5.0': 'smaller and more precise',
        'target_center': [1046, 333],
        'relative_to_vault_center_px': [63, 0],
    },
    'tests': [
        'PASS Python AST and py_compile.',
        'PASS F1.5 regression checks: JSON scope lock, all Luma commands supported, F1.4 door/connection preservation, walkmesh approach reachability, vault hit-test, plate-only directional clip, off-centre scaling, held-plate inventory selection, pick-lock and item-specific force dialogue, vault remains closed, config persistence, and F1.5 browser page identifiers.',
        'PASS runtime APK/TAR content equality to the exact F1.5 source files.',
        'PASS deploy ZIP CRC, no duplicate paths, 32-entry version manifest, and byte-for-byte preservation of 160 prior deployment entries other than versions.json.',
        'PASS rendered Castle Hall preview from the F1.5 Luma JSON recipe.',
    ],
    'runtime_note': 'The build and static regressions passed. The game was not launched in a live browser during this build; Cozmo must field-test pointer/E interaction, movement, inventory UI and saved settings before runtime behavior is considered confirmed.',
    'hashes': {
        'main_sha256': hashlib.sha256(code).hexdigest(),
        'assets_sha256': hashlib.sha256(assets_bytes).hexdigest(),
        'base_deploy_sha256': hashlib.sha256(BASE_DEPLOY.read_bytes()).hexdigest(),
        'deploy_sha256': hashlib.sha256(DEPLOY.read_bytes()).hexdigest(),
    },
    'bytes': {
        'deploy': DEPLOY.stat().st_size,
    },
    'source_archive_digest_note': 'Not embedded: the source archive contains this metadata file, so embedding the archive SHA-256 would be self-referential. Calculate the source ZIP SHA-256 externally after packaging.',
    'deploy_entries': {
        'previous_entries_preserved': len(old_names),
        'catalog_versions': 32,
        'new_files': [name for name, _ in additions],
    },
}
META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source_files.append((META_PATH.name, META_PATH))

with zipfile.ZipFile(SOURCE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
    for arcname, path in source_files:
        assert path.exists(), f'Missing source component: {path}'
        out.write(path, arcname)
with zipfile.ZipFile(SOURCE, 'r') as z:
    assert z.testzip() is None
    assert z.read('main.py') == code
    assert z.read('luma_assets_e33.json') == assets_bytes
    assert z.read('F1_play.html') == page.encode('utf-8')
    assert z.read('README_SGGF15.txt') == README.read_bytes()
    assert z.read('F1.5_BUILD_META.json') == META_PATH.read_bytes()
    assert len(z.namelist()) == len(source_files)
    assert len(set(z.namelist())) == len(z.namelist())

with zipfile.ZipFile(SOURCE, 'r') as z:
    assert z.testzip() is None
    assert z.read('F1.5_BUILD_META.json') == META_PATH.read_bytes()
    assert z.read('main.py') == code and z.read('luma_assets_e33.json') == assets_bytes

print('DEPLOY:', DEPLOY, DEPLOY.stat().st_size, 'bytes')
print('DEPLOY SHA256:', hashlib.sha256(DEPLOY.read_bytes()).hexdigest())
print('SOURCE:', SOURCE, SOURCE.stat().st_size, 'bytes')
print('SOURCE SHA256:', hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print('MAIN SHA256:', meta['hashes']['main_sha256'])
print('ASSETS SHA256:', meta['hashes']['assets_sha256'])
print('SOURCE COMPONENTS:', len(source_files))
