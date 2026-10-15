"""Pinned Zeroth source access; audio is decoded from data, never executed."""
import argparse
import concurrent.futures
import io
import json
import unicodedata
import urllib.request
from pathlib import Path

from scripts.build_dataset import digest, write_json

DATASET = 'kresnik/zeroth_korean'
REVISION = '1fe937899f828af822293d05e086200946088bdf'
FILES = [
    ('test-00000-of-00001.parquet', 59847930, '2f6382b902622ede1bf35e5a167a9b06b0f1b8c896e1947324b8b5180fca7502'),
    ('train-00000-of-00006.parquet', 499070876, '6801a64e3f5c9b49bedfffc41733dfceffbf822237ac9cd70c9687944a685943'),
    ('train-00001-of-00006.parquet', 470691683, '5f189248aed0befdecea9fb3cd843d18819419acfbe2be32fcc61af94360b64b'),
    ('train-00002-of-00006.parquet', 444033028, 'b7f7b4cdd57af262313485bd41c454f575509ef4eba17240f2078033693b2069'),
    ('train-00003-of-00006.parquet', 481254881, '7b1cc68d924b52d9f7ea938fa3d65ba3d8e7bb81d0149b10f06f89e8d39261a5'),
    ('train-00004-of-00006.parquet', 459642792, 'f679e7f963e6cf4911c45ac68c4e67be12df73b63d889ebd9373d4af18fcbe91'),
    ('train-00005-of-00006.parquet', 462471629, '7c31d0628a6bd0d6624d4bd1505052579a72eec99842e9e526fe1b1c89f6c1ec'),
]


def source_files(names=None):
    if names is not None and (not names or not set(names) <= {r[0] for r in FILES}):
        raise ValueError('Unknown or empty source-file selection.')
    return [r for r in FILES if names is None or r[0] in names]


def verify(cache, names=None):
    for name, size, checksum in source_files(names):
        path = cache / 'data' / name
        if path.stat().st_size != size or digest(path) != checksum:
            raise ValueError(f'Upstream file size/hash mismatch: {name}')


def fetch(cache, names=None):
    def one(entry):
        name, size, checksum = entry
        path = cache / 'data' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size == size and digest(path) == checksum:
            print('Verified cached ' + name, flush=True)
            return
        temporary = path.with_suffix('.partial')
        while not temporary.exists() or temporary.stat().st_size < size:
            start = temporary.stat().st_size if temporary.exists() else 0
            end = min(start + 16 * 1024 * 1024, size) - 1
            url = f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/data/{name}?download=true&start={start}&end={end}'
            for attempt in range(4):
                try:
                    request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
                    with urllib.request.urlopen(request, timeout=90) as response:
                        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                            raise ValueError('Unexpected source byte range.')
                        payload = response.read(end - start + 2)
                    if len(payload) != end - start + 1:
                        raise ValueError('Truncated source byte range.')
                    with temporary.open('ab') as stream: stream.write(payload)
                    break
                except (OSError, ValueError):
                    if attempt == 3: raise
            print(f'{name}: {end + 1}/{size} bytes', flush=True)
        if temporary.stat().st_size != size or digest(temporary) != checksum:
            raise ValueError(f'Upstream file size/hash mismatch: {name}')
        temporary.replace(path)
        if path.stat().st_size != size or digest(path) != checksum:
            raise ValueError(f'Upstream file size/hash mismatch: {name}')
        print('Verified ' + name, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(one, source_files(names)))


def batches(cache, columns=None, names=None):
    import pyarrow.parquet as pq
    for name, _, _ in source_files(names):
        offset = 0
        for batch in pq.ParquetFile(cache / 'data' / name).iter_batches(batch_size=32, columns=columns):
            for i, row in enumerate(batch.to_pylist()):
                yield name, offset + i, row
            offset += len(batch)


def index(cache, output, names=None):
    import hashlib
    import numpy as np
    import soundfile as sf
    verify(cache, names)
    rows, ids = [], set()
    for filename, offset, row in batches(cache, names=names):
        if row['id'] in ids:
            raise ValueError('Duplicate upstream recording ID.')
        ids.add(row['id'])
        payload = row['audio']['bytes']
        info = sf.info(io.BytesIO(payload))
        if info.samplerate != 16000 or info.channels != 1 or info.subtype != 'PCM_16':
            raise ValueError('Unexpected upstream audio encoding.')
        samples, rate = sf.read(io.BytesIO(payload), dtype='float32')
        if not np.all(np.isfinite(samples)) or not np.any(samples):
            raise ValueError('Upstream contains nonfinite or silent audio.')
        frame = 320
        padded = np.pad(samples, (0, (-len(samples)) % frame)).reshape(-1, frame)
        rms = np.sqrt(np.mean(padded * padded, axis=1))
        active = np.flatnonzero(rms > max(.0001, float(np.max(np.abs(samples))) * .01))
        if not len(active): raise ValueError('No active audio frames.')
        rows.append({'source_id': row['id'], 'speaker_id': str(row['speaker_id']),
            'session_id': f"{row['speaker_id']}:{row['chapter_id']}",
            'source_file': filename, 'source_row': offset, 'source_path': row['path'],
            'source_split': filename.split('-')[0],
            'reference': unicodedata.normalize('NFC', row['text']),
            'samples': info.frames, 'duration_seconds': info.frames / info.samplerate,
            'active_fraction': len(active) / len(rms), 'leading_silence': float(active[0] * .02),
            'trailing_silence': float((len(rms) - active[-1] - 1) * .02),
            'source_audio_sha256': hashlib.sha256(payload).hexdigest()})
        if len(rows) % 3000 == 0:
            print(f'Indexed {len(rows)} recordings', flush=True)
    write_json(output, {'dataset': DATASET, 'revision': REVISION,
        'source_files': [r[0] for r in source_files(names)], 'items': rows})
    print(json.dumps({'recordings': len(rows), 'hours': sum(r['duration_seconds'] for r in rows) / 3600}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'index'])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--files', nargs='+', help='Pinned shard filenames; default is all seven source files.')
    args = parser.parse_args()
    if args.action == 'fetch': fetch(args.cache, args.files)
    elif not args.output: parser.error('--output is required for index')
    else: index(args.cache, args.output, args.files)


if __name__ == '__main__': main()
