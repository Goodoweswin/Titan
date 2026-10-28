"""Collect installed dependency metadata and license texts for a release.

Inventory includes build/test and inactive platform dependencies. It is not a
statement that every inventoried package is shipped in the application.
"""
import importlib.metadata as metadata
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'release' / 'third-party'
OUT.mkdir(parents=True, exist_ok=True)
records = []


def add(ecosystem, name, version, license_id, sources):
    safe = name.replace('/', '_').replace('@', '') + '-' + version
    dest = OUT / ecosystem / safe
    texts = []
    for index, source in enumerate(dict.fromkeys(sources)):
        if not source.is_file():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / (str(index) + '-' + source.name)
        shutil.copy2(source, target)
        texts.append(str(target.relative_to(OUT)))
    records.append(dict(ecosystem=ecosystem, name=name, version=version,
                        license=license_id or 'See included metadata/source', texts=texts))


for dist in metadata.distributions():
    m = dist.metadata
    sources = [Path(dist.locate_file(f)) for f in (dist.files or [])
               if any(x in str(f).lower() for x in ('license', 'licence', 'copying', 'notice', 'authors'))]
    add('python', m['Name'], m['Version'], m.get('License-Expression') or m.get('License'), sources)
python_license = Path(sys.base_prefix) / 'Resources' / 'English.lproj' / 'Documentation' / 'LICENSE.txt'
for candidate in [python_license, Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'lib/python3.11/LICENSE.txt']:
    if candidate.is_file():
        add('python', 'CPython', sys.version.split()[0], 'Python-2.0', [candidate])
        break
for package in (ROOT / 'node_modules').glob('**/package.json'):
    try:
        m = json.loads(package.read_text(encoding='utf-8'))
        if not m.get('name') or not m.get('version'):
            continue
        sources = [p for p in package.parent.iterdir() if p.is_file() and p.name.lower().startswith(('license', 'licence', 'copying', 'notice', 'authors'))]
        add('npm', m['name'], m['version'], m.get('license'), sources)
    except (OSError, ValueError):
        continue
cargo = json.loads((ROOT / 'artifacts/cargo-metadata.json').read_text(encoding='utf-8-sig'))
for m in cargo['packages']:
    if m.get('source') is None:
        continue
    folder = Path(m['manifest_path']).parent
    sources = [p for p in folder.iterdir() if p.is_file() and p.name.lower().startswith(('license', 'licence', 'copying', 'notice', 'authors'))]
    if m.get('license_file'):
        sources.append(folder / m['license_file'])
    add('cargo', m['name'], m['version'], m.get('license'), sources)
(OUT / 'inventory.json').write_text(json.dumps(records, ensure_ascii=False, indent=2),encoding='utf-8')
(OUT / 'README.txt').write_text('Titan WB 0.1 dependency notices\nInventory includes development/test/inactive platform packages. See inventory.json for package versions, declared licenses and copied license text paths. Dependencies are locked in requirements.lock, package-lock.json and Cargo.lock. This collection does not replace distribution license review.\n',encoding='utf-8')
print(f'{len(records)} dependency records; notices: {OUT}')
