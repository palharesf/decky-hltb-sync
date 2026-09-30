"""Create a reviewable Decky ZIP from an explicit allowlist, never private data."""
import hashlib
import json
import zipfile
from pathlib import Path


def package(root):
    version = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
    target = root / '.local' / 'artifacts'
    target.mkdir(parents=True, exist_ok=True)
    output = target / f'hltb-sync-for-deck-{version}.zip'
    files = [root / name for name in ('main.py', 'package.json', 'plugin.json', 'README.md', 'LICENSE', 'dist/index.js')]
    files += sorted((root / 'py_modules' / 'hltb_sync').glob('*.py'))
    files += sorted((root / 'docs').glob('*.md'))
    if not all(p.is_file() for p in files):
        raise SystemExit('Build the frontend before packaging.')
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'hltb-sync-for-deck/' + path.relative_to(root).as_posix())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    print(f'Package: {output}')
    print(f'SHA256: {digest}')
    return output


if __name__ == '__main__':
    package(Path(__file__).resolve().parents[1])
