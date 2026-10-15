"""Resumable, reference-blind matched Qwen2.5-Omni input ablations.

Only input manifests are read here. Score the completed CSVs separately. The
Thinker retains the audio encoder; no speech-generation weights are needed.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.baseline import PROMPTS, SYSTEM, load_inputs, messages_for

MODEL = 'Qwen/Qwen2.5-Omni-3B'
REVISION = 'f75b40e3da2003cdd6e1829b1f420ca70797c34e'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_jobs(public, private, splits, limit):
    jobs = []
    manifests = {}
    for split in splits:
        path = (public if split == 'eval' else private) / split / 'inputs.json'
        rows = load_inputs(path)
        manifests[split] = sha(path)
        for row in rows[:limit] if limit else rows:
            jobs.append({'split': split, 'row': row, 'root': path.parent})
    return jobs, manifests


def validate_checkpoint(checkpoint, contract):
    if checkpoint.get('contract') != contract:
        raise ValueError('Checkpoint inputs/model/settings differ; use a separate work folder.')
    records = checkpoint.get('items')
    if not isinstance(records, list) or len({(r['split'], r['id']) for r in records}) != len(records):
        raise ValueError('Invalid or duplicate checkpoint rows.')
    return {(r['split'], r['id']): r for r in records}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public', type=Path, required=True)
    p.add_argument('--private', type=Path, required=True)
    p.add_argument('--model-cache', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--modes', nargs='+', choices=tuple(PROMPTS), default=list(PROMPTS))
    p.add_argument('--splits', nargs='+', choices=('eval', 'test'), default=['eval', 'test'])
    p.add_argument('--device', choices=('mps', 'cpu'), default='mps')
    p.add_argument('--max-new-tokens', type=int, default=512)
    p.add_argument('--limit', type=int, help='Technical smoke test only; never an official full score.')
    args = p.parse_args()
    if args.max_new_tokens < 1 or (args.limit is not None and args.limit < 1):
        p.error('Token limit and optional row limit must be positive.')
    if len(set(args.modes)) != len(args.modes) or len(set(args.splits)) != len(args.splits):
        p.error('Duplicate modes or splits.')
    jobs, manifests = load_jobs(args.public, args.private, args.splits, args.limit)
    args.work.mkdir(parents=True, exist_ok=True)
    # Hash every local model artifact used, not only its directory name.
    files = sorted(x for x in args.model_cache.iterdir() if x.is_file()
                   and (x.suffix in ('.json', '.safetensors') or x.name == 'merges.txt'))
    if not any(x.suffix == '.safetensors' for x in files):
        raise ValueError('Complete the fixed model snapshot download first.')
    print('Hashing fixed model snapshot', flush=True)
    model_hashes = {x.name: sha(x) for x in files}

    import torch
    import soundfile as sf
    from transformers import Qwen2_5OmniProcessor, Qwen2_5OmniThinkerForConditionalGeneration

    if args.device == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS requested but unavailable.')
    torch.manual_seed(0)
    torch.set_num_threads(4)
    dtype = torch.float16 if args.device == 'mps' else torch.float32
    common = {'model': MODEL, 'revision': REVISION, 'model_files_sha256': model_hashes,
              'input_manifests_sha256': manifests, 'splits': args.splits,
              'row_limit': args.limit, 'system': SYSTEM, 'seed': 0,
              'max_new_tokens': args.max_new_tokens, 'do_sample': False,
              'device': args.device, 'dtype': str(dtype), 'attention': 'sdpa',
              'reference_access': False, 'output_postprocessing': 'strip_only',
              'packages': {x: importlib.metadata.version(x) for x in
                           ('torch', 'torchvision', 'transformers', 'accelerate', 'soundfile', 'safetensors')}}
    status = {'state': 'loading', 'started_at': utc(), 'hardware': platform.platform(),
              'jobs_per_mode': len(jobs), 'modes': args.modes, 'contract': common}
    atomic_json(args.work / 'status.json', status)
    try:
        model, info = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
            args.model_cache, local_files_only=True, dtype=dtype,
            device_map=args.device, attn_implementation='sdpa', output_loading_info=True)
        missing = info.get('missing_keys', [])
        mismatched = info.get('mismatched_keys', [])
        if missing or mismatched:
            raise ValueError(f'Missing/mismatched Thinker weights: {missing}, {mismatched}')
        model.eval()
        processor = Qwen2_5OmniProcessor.from_pretrained(args.model_cache, local_files_only=True)
        atomic_json(args.work / 'loading.json', {'missing_keys': missing,
            'mismatched_keys': mismatched, 'unexpected_keys_count': len(info.get('unexpected_keys', [])),
            'parameters': sum(x.numel() for x in model.parameters()),
            'device': str(model.device), 'dtype': str(model.dtype)})
        for mode in args.modes:
            contract = common | {'mode': mode, 'prompt': PROMPTS[mode]}
            path = args.work / mode / 'checkpoint.json'
            prior = json.loads(path.read_text()) if path.exists() else {'contract': contract, 'items': []}
            done = validate_checkpoint(prior, contract)
            expected = {(j['split'], j['row']['id']) for j in jobs}
            if not set(done) <= expected:
                raise ValueError('Checkpoint contains unexpected IDs.')
            for job in jobs:
                row, split, root = job['row'], job['split'], job['root']
                key = (split, row['id'])
                audio_hash = sha((root / row['audio']).resolve()) if mode != 'text-only' else None
                draft_hash = hashlib.sha256(row['draft'].encode()).hexdigest() if mode != 'audio-only' else None
                if key in done:
                    if (done[key]['audio_sha256'], done[key]['draft_sha256']) != (audio_hash, draft_hash):
                        raise ValueError('Previously processed input changed.')
                    continue
                started = time.monotonic()
                messages = messages_for(row, mode, root)
                prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
                audio = None
                if mode != 'text-only':
                    waveform, sr = sf.read(root / row['audio'], dtype='float32')
                    if sr != 16000 or waveform.ndim != 1:
                        raise ValueError('Expected original 16 kHz mono audio; no implicit conversion.')
                    audio = [waveform]
                batch = processor(text=prompt, audio=audio, return_tensors='pt', padding=True,
                                  use_audio_in_video=False)
                batch = batch.to(device=model.device, dtype=model.dtype)
                with torch.inference_mode():
                    generated = model.generate(**batch, do_sample=False,
                        max_new_tokens=args.max_new_tokens, use_audio_in_video=False)
                tokens = generated[:, batch['input_ids'].shape[1]:]
                if tokens.shape[1] >= args.max_new_tokens:
                    raise ValueError(f'Token limit reached: {split}/{row["id"]}')
                prediction = processor.batch_decode(tokens, skip_special_tokens=True,
                    clean_up_tokenization_spaces=False)[0].strip()
                if not prediction or len(prediction) > 4000:
                    raise ValueError(f'Empty/oversized prediction: {split}/{row["id"]}')
                record = {'split': split, 'id': row['id'], 'prediction': prediction,
                          'audio_sha256': audio_hash, 'draft_sha256': draft_hash,
                          'elapsed_seconds': time.monotonic() - started,
                          'new_tokens': tokens.shape[1]}
                prior['items'].append(record)
                done[key] = record
                atomic_json(path, prior)
                status.update(state='running', mode=mode, processed=len(done), updated_at=utc())
                atomic_json(args.work / 'status.json', status)
                print(f'{mode} {len(done)}/{len(jobs)} {record["elapsed_seconds"]:.2f}s', flush=True)
                del batch, generated, tokens
            for split in args.splits:
                target = args.work / split / f'{mode}.csv'
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'prediction'])
                    writer.writerows((j['row']['id'], done[(split, j['row']['id'])]['prediction'])
                                     for j in jobs if j['split'] == split)
            atomic_json(args.work / mode / 'run.json', contract | {'rows': len(done), 'finished_at': utc()})
        status.update(state='completed', finished_at=utc())
        atomic_json(args.work / 'status.json', status)
    except Exception as exc:
        status.update(state='failed', error_type=type(exc).__name__, error=str(exc), updated_at=utc())
        atomic_json(args.work / 'status.json', status)
        raise


if __name__ == '__main__':
    main()
