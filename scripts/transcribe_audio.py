"""Blind audio-only transcription; no drafts or reference files enter the model."""
import argparse
import csv
import importlib.metadata
import json
import time
from pathlib import Path

from scripts.build_dataset import digest, write_json

MODEL = 'mlx-community/whisper-large-v3-turbo'
REVISION = 'a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb'


def transcribe(inputs, output, model_cache):
    import mlx_whisper
    import soundfile as sf
    from huggingface_hub import snapshot_download

    model = snapshot_download(MODEL, revision=REVISION, local_dir=model_cache)
    rows = json.loads(inputs.read_text(encoding='utf-8'))['items']
    # Select only these fields. Drafts cannot influence recognition.
    audio_rows = [(row['id'], (inputs.parent / row['audio']).resolve()) for row in rows]
    if len({ident for ident, _ in audio_rows}) != len(audio_rows):
        raise ValueError('Duplicate audio IDs.')
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / 'audio-only.json'
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {'model':MODEL,'revision':REVISION,'items':[]}
    if (state['model'], state['revision']) != (MODEL, REVISION):
        raise ValueError('Checkpoint model mismatch.')
    done = {row['id']:row for row in state['items']}
    if set(done) - {ident for ident, _ in audio_rows}:
        raise ValueError('Checkpoint IDs differ from requested inputs.')
    for index, (ident, path) in enumerate(audio_rows, 1):
        checksum = digest(path)
        if ident in done:
            if done[ident]['audio_sha256'] != checksum:
                raise ValueError('Checkpoint audio changed.')
            continue
        samples, rate = sf.read(path, dtype='float32')
        if rate != 16000 or samples.ndim != 1:
            raise ValueError('Expected 16 kHz mono audio.')
        start = time.monotonic()
        result = mlx_whisper.transcribe(samples, path_or_hf_repo=model,
            language='ko', task='transcribe', temperature=0.0,
            condition_on_previous_text=False, initial_prompt=None, verbose=None)
        row = {'id':ident, 'audio_sha256':checksum, 'prediction':result['text'].strip(),
               'elapsed_seconds':round(time.monotonic()-start, 3)}
        state['items'].append(row)
        # A stopped or interrupted long run must leave its last complete JSON
        # checkpoint readable, rather than a partly overwritten file.
        pending = checkpoint.with_suffix('.json.pending')
        write_json(pending, state)
        pending.replace(checkpoint)
        print(f'{index}/{len(audio_rows)} {ident}: {row["prediction"]}', flush=True)
    with (output / 'audio-only.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['id','prediction'])
        predictions = {row['id']:row['prediction'] for row in state['items']}
        writer.writerows((ident,predictions[ident]) for ident,_ in audio_rows)
    write_json(output / 'run.json', {'model':MODEL,'revision':REVISION,
        'inputs_sha256':digest(inputs),'prompt':None,'draft_access':False,'reference_access':False,
        'decoding':{'language':'ko','task':'transcribe','temperature':0.0,'condition_on_previous_text':False},
        'packages':{name:importlib.metadata.version(name) for name in ('mlx-whisper','mlx','soundfile','huggingface-hub')}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-cache', type=Path, required=True)
    args = parser.parse_args()
    transcribe(args.inputs, args.output, args.model_cache)


if __name__ == '__main__':
    main()
