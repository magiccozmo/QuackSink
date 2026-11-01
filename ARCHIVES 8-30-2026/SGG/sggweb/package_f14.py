"""Build and validate SGGF1.4 from the tested F1.3 source and deploy bundle."""
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
BASE_DEPLOY = ROOT / 'SGGF1.3_CLOUDFLARE_DEPLOY.zip'
MAIN = WORK / 'main.py'
ASSETS = WORK / 'luma_assets_e33.json'
PLAY = WORK / 'F1_play.html'
README = WORK / 'README_SGGF14.txt'
DEPLOY = ROOT / 'SGGF1.4_CLOUDFLARE_DEPLOY.zip'
SOURCE = ROOT / 'SGGF1.4_SOURCE.zip'

code = MAIN.read_bytes()
assets_bytes = ASSETS.read_bytes()
assets_doc = json.loads(assets_bytes)
page = PLAY.read_text(encoding='utf-8')
assert assets_doc['version'] == 'SGGF1.4'
assert 'VERSION = "F1.4"' in code.decode('utf-8')
assert all(x in page for x in ('SGGF1.4', 'sggf14.apk', 'sggf14.tar.gz', 'archive:"sggf14"'))
assert 'Castle Exterior' in README.read_text(encoding='utf-8')

# Syntax, full regression suite, and deterministic art preview.
ast.parse(code.decode('utf-8'))
subprocess.run([sys.executable, '-m', 'py_compile', str(MAIN)], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'test_f14.py')], cwd=WORK, check=True)
subprocess.run([sys.executable, str(WORK / 'render_f14_exterior_preview.py')], cwd=WORK, check=True)

# Extra explicit scope proof: F1.4 art/world JSON must be exactly F1.3 except
# the Castle Exterior recipe, version marker, and one F1.4 release note.
f13_assets = json.loads((WORK / 'F1.3_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = copy.deepcopy(f13_assets)
expected['version'] = 'SGGF1.4'
expected['assets']['c1_bg_castle_exterior'] = assets_doc['assets']['c1_bg_castle_exterior']
expected['notes'] = (expected.get('notes', '').rstrip() +
    '\nSGGF1.4: rebuilt only the Castle Exterior background to match the F1.3 Castle Path castle: round pale-stone arch, deep vaulted opening, raised portcullis detail, open wooden gate leaves, square battlement towers, and a centered cobbled approach. Castle Path art, transitions, walkable corridor, entrance trigger, other scenes, gameplay, and save data are retained.')
assert assets_doc == expected, 'F1.4 JSON changed outside its approved Castle Exterior art/version/note scope.'

# Runtime payloads are the exact same source files as in the source handoff.
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

# Extend exact F1.3 site package: preserve every historic file byte-for-byte
# except the dynamic versions.json catalog, then append the five F1.4 files.
assert BASE_DEPLOY.exists(), BASE_DEPLOY
with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
    assert old.testzip() is None
    old_names = old.namelist()
    assert len(old_names) == 155
    assert all(x in old_names for x in (
        'index.html', 'versions.html', 'versions.json', '_headers',
        'SGGF1.3/play.html', 'SGGF1.3/favicon.png',
        'SGGF1.3/sggf13.apk', 'SGGF1.3/sggf13.tar.gz', 'SGGF1.3/README_SGGF13.txt'))
    favicon = old.read('SGGF1.3/favicon.png')
    manifest = json.loads(old.read('versions.json'))
    assert manifest['versions'][0]['version'] == 'SGGF1.3'
    assert manifest['versions'][0]['current'] is True
    for entry in manifest['versions']:
        entry['current'] = False
    manifest['versions'].insert(0, {
        'version': 'SGGF1.4',
        'title': 'SGGF 1.4',
        'path': 'SGGF1.4/play.html',
        'description': 'Castle Exterior rebuilt to match the F1.3 Castle Path fortress: pale round stone arch, deep vaulted opening, raised portcullis, open timber gate leaves, square crenellated towers and a centered cobbled approach. Castle Path, transitions, movement, collision, gameplay and save data remain unchanged.',
        'current': True,
    })
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (WORK / 'deploy' / 'versions.json').write_bytes(manifest_bytes)
    additions = [
        ('SGGF1.4/play.html', page.encode('utf-8')),
        ('SGGF1.4/favicon.png', favicon),
        ('SGGF1.4/sggf14.apk', apkb.getvalue()),
        ('SGGF1.4/sggf14.tar.gz', tarb.getvalue()),
        ('SGGF1.4/README_SGGF14.txt', README.read_bytes()),
    ]
    with zipfile.ZipFile(DEPLOY, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as out:
        for member in old.infolist():
            payload = manifest_bytes if member.filename == 'versions.json' else old.read(member.filename)
            out.writestr(copy.copy(member), payload)
        for name, payload in additions:
            out.writestr(name, payload)

# Validate full deployment structure, manifest, exact old files, and payloads.
with zipfile.ZipFile(DEPLOY, 'r') as z:
    assert z.testzip() is None
    names = z.namelist()
    assert len(names) == len(old_names) + len(additions) == 160
    assert len(set(names)) == len(names)
    with zipfile.ZipFile(BASE_DEPLOY, 'r') as old:
        for name in old_names:
            if name == 'versions.json':
                continue
            assert z.read(name) == old.read(name), f'Historical/site file changed unexpectedly: {name}'
    final_doc = json.loads(z.read('versions.json'))
    assert len(final_doc['versions']) == 31
    assert final_doc['versions'][0]['version'] == 'SGGF1.4' and final_doc['versions'][0]['current'] is True
    assert final_doc['versions'][1]['version'] == 'SGGF1.3' and final_doc['versions'][1]['current'] is False
    assert sum(1 for v in final_doc['versions'] if v.get('current')) == 1
    for v in final_doc['versions']:
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', v['version'])
        assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*\/(?:play|index)\.html', v['path'])
    with zipfile.ZipFile(io.BytesIO(z.read('SGGF1.4/sggf14.apk'))) as runtime:
        assert runtime.testzip() is None
        assert runtime.namelist() == ['assets/main.py', 'assets/luma_assets_e33.json']
        assert runtime.read('assets/main.py') == code
        assert runtime.read('assets/luma_assets_e33.json') == assets_bytes
    with tarfile.open(fileobj=io.BytesIO(z.read('SGGF1.4/sggf14.tar.gz')), mode='r:gz') as runtime:
        assert runtime.extractfile('assets/main.py').read() == code
        assert runtime.extractfile('assets/luma_assets_e33.json').read() == assets_bytes
    final_page = z.read('SGGF1.4/play.html').decode('utf-8')
    assert 'archive:"sggf14"' in final_page and 'sggf14.apk' in final_page and 'sggf14.tar.gz' in final_page
    for name in ('index.html', 'versions.html'):
        html = z.read(name).decode('utf-8')
        assert 'isPhoneOrTablet' in html and 'navigator.userAgentData?.mobile' in html
    print(f'PASS deploy: {len(old_names)} F1.3/historical site entries preserved except versions.json; {len(additions)} F1.4 entries added.')

# Build metadata records all inputs/results and the verification boundary.
meta = {
    'version': 'SGGF1.4',
    'based_on': 'SGGF1.3',
    'repository': 'magiccozmo/QuackSink',
    'source_folder': 'ARCHIVES 8-30-2026/SGG/sggweb',
    'scope': 'Rebuild only the Castle Exterior background to visually match the F1.3 Castle Path fortress. Preserve the Castle Path artwork, all world/transition/collision/navigation definitions, door trigger, all other scene recipes, gameplay and save behavior.',
    'castle_exterior_recipe': '903 Luma primitive commands; 1280x640.',
    'preserved': [
        'F1.3 Castle Path background recipe and all other background/character/object recipes, except only the Castle Exterior background recipe is replaced.',
        'All F1.3 world definitions byte-for-byte: area geometry, solid rectangles, sight blockers, navigation regions, objects, door location/walk trigger, and connection arrival positions.',
        'F1.3 model/state-machine classes and gameplay logic; only VERSION/status/header release text changes.',
        'Stables, Kitty, horse, carriage, fence, inventory, quest, save migration, dialogue and Part One gameplay.',
        'All F1.3 and earlier deployed site files byte-for-byte; only versions.json advances and five new F1.4 version files are appended.',
    ],
    'main_sha256': hashlib.sha256(code).hexdigest(),
    'assets_sha256': hashlib.sha256(assets_bytes).hexdigest(),
    'base_deploy_sha256': hashlib.sha256(BASE_DEPLOY.read_bytes()).hexdigest(),
    'deploy_sha256': hashlib.sha256(DEPLOY.read_bytes()).hexdigest(),
    'deploy_bytes': DEPLOY.stat().st_size,
    'historical_site_entries_preserved': len(old_names),
    'release_catalog_versions': 31,
    'new_deployment_files': [name for name, _ in additions],
    'static_regression': 'PASS: Python AST/py_compile; F1.4 regression suite; exact F1.3-to-F1.4 JSON diff scope lock; Castle Path exact preservation; exact world/door/collision/navigation/transition preservation; old class logic preservation apart from release status string; runtime APK/TAR payload hashes; deployment ZIP CRC and byte-for-byte preservation of all previous site files except versions.json.',
    'runtime_note': 'Build-time tests and renderer-generated preview passed. The game was not launched in a live browser during this build; field-test F1.4 in the browser before treating browser runtime behavior as verified.',
}
meta_path = WORK / 'F1.4_BUILD_META.json'
meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')

# Source package includes complete F1.4 working sources, reproducible art/build
# scripts, F1.3 baselines, F1.0-F1.2 baselines, preview, tests, and site front door.
source_files = []
for path in sorted(WORK.iterdir()):
    if path.is_file() and path.name != '__pycache__':
        if path.name == 'test_f13.py':
            source_files.append(('F1.3_BASE_test_f13.py', path))
        elif path.name in ('SGGF1.4_SOURCE.zip', 'SGGF1.4_CLOUDFLARE_DEPLOY.zip'):
            continue
        else:
            source_files.append((path.name, path))
for name in ('index.html', 'versions.html', 'versions.json', '_headers'):
    p = WORK / 'deploy' / name
    assert p.exists()
    source_files.append((f'deploy/{name}', p))

# Reject accidental nested archives, cache files, or paths outside this source handoff.
assert len({name for name, _ in source_files}) == len(source_files)
with zipfile.ZipFile(SOURCE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
    for arcname, path in source_files:
        assert path.exists(), f'Missing source component: {path}'
        out.write(path, arcname)
with zipfile.ZipFile(SOURCE, 'r') as z:
    assert z.testzip() is None
    assert z.read('main.py') == code
    assert z.read('luma_assets_e33.json') == assets_bytes
    assert z.read('F1_play.html') == page.encode('utf-8')
    assert z.read('README_SGGF14.txt') == README.read_bytes()
    assert 'F1.3_BASE_test_f13.py' in z.namelist()
    assert len(z.namelist()) == len(source_files)

print('DEPLOY:', DEPLOY, DEPLOY.stat().st_size, 'bytes')
print('DEPLOY SHA256:', hashlib.sha256(DEPLOY.read_bytes()).hexdigest())
print('SOURCE:', SOURCE, SOURCE.stat().st_size, 'bytes')
print('SOURCE SHA256:', hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print('MAIN SHA256:', meta['main_sha256'])
print('ASSETS SHA256:', meta['assets_sha256'])
print('SOURCE COMPONENTS:', len(source_files))
