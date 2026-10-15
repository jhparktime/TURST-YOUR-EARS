"""Package participant, private organizer, and answer-free test inputs separately."""
import argparse
import json
import zipfile
from pathlib import Path

from scripts.build_dataset import digest, write_json


def archive(root, output, prefix, selected=None, private=False):
    if output.exists():
        raise ValueError(f'Refusing to overwrite {output}')
    pending = output.with_suffix('.zip.pending')
    files = [p for p in sorted(root.rglob('*')) if p.is_file() and
             (selected is None or selected(p.relative_to(root)))]
    with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for path in files:
            if path.is_symlink():
                raise ValueError('Archive inputs must be regular files.')
            z.write(path, f'{prefix}/{path.relative_to(root)}')
    with zipfile.ZipFile(pending) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC verification failed.')
    pending.replace(output)
    checksum = digest(output)
    sidecar = output.with_suffix('.zip.sha256')
    sidecar.write_text(f'{checksum}  {output.name}\n')
    if private:
        output.chmod(0o600)
        sidecar.chmod(0o600)
    return {'file': output.name, 'sha256': checksum, 'bytes': output.stat().st_size,
            'files': len(files), 'private': private, 'crc_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'private', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((args.public / 'metadata.json').read_text())
    if metadata != json.loads((args.private / 'metadata.json').read_text()):
        raise ValueError('Public/private metadata mismatch.')
    for root in (args.public, args.private):
        expected = json.loads((root / 'release-lock.json').read_text())['sha256']
        actual = {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
                  if p.is_file() and p.name != 'release-lock.json'}
        if expected != actual:
            raise ValueError('Unsealed or changed delivery.')
    receipts = []
    for role, root, private, selected in [
        ('participant', args.public, False, None),
        ('test-inputs', args.private / 'test', True,
         lambda p: p.parts[0] == 'audio' or p.name in {'inputs.json', 'audio-checksums.json'}),
        ('organizer', args.private, True, None)]:
        filename = args.output / f'{metadata["name"]}-{role}.zip'
        receipts.append(archive(root, filename, f'{metadata["name"]}-{role}', selected, private))
        print(f'Packaged {role}', flush=True)
    write_json(args.output / 'packaging-receipt.json', {'name': metadata['name'], 'archives': receipts})


if __name__ == '__main__':
    main()
