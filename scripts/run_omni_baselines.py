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


def generated_prediction(decoded, token_ids, max_new_tokens, eos_token_id):
    """Keep actual bounded model output, including empty/length-limited text.

    A model's generation behavior is an evaluation outcome. It must not cause
    a row to be dropped, replaced with its draft, or retried with a larger cap.
    """
    prediction = decoded.strip()
    if len(prediction) > 4000:
        raise ValueError('Oversized prediction: exceeds the submission format.')
    eos_ids = {eos_token_id} if isinstance(eos_token_id, int) else set(eos_token_id or [])
    ended = bool(token_ids) and token_ids[-1] in eos_ids
    capped = len(token_ids) >= max_new_tokens
    return prediction, {'finish_reason': 'eos' if ended else 'length' if capped else 'other',
                        'at_token_limit': capped, 'empty_output': not prediction}


def release_mps_cache(torch, device):
    """Release unused allocator buffers after output tensors are discarded.

    This changes memory housekeeping only, after the prediction is saved.
    It does not change weights, inputs, decoding or the resume contract.
    """
    if device != 'mps':
        return None
    torch.mps.synchronize()
    torch.mps.empty_cache()
    return {'tensor_bytes': torch.mps.current_allocated_memory(),
            'driver_bytes': torch.mps.driver_allocated_memory(),
            'recommended_bytes': torch.mps.recommended_max_memory()}


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
    from transformers import GenerationConfig, Qwen2_5OmniProcessor, Qwen2_5OmniThinkerConfig, Qwen2_5OmniThinkerForConditionalGeneration

    if args.device == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS requested but unavailable.')
    torch.manual_seed(0)
    torch.set_num_threads(4)
    dtype = torch.bfloat16 if args.device == 'mps' else torch.float32
    common = {'model': MODEL, 'revision': REVISION, 'model_files_sha256': model_hashes,
              'input_manifests_sha256': manifests, 'splits': args.splits,
              'row_limit': args.limit, 'system': SYSTEM, 'seed': 0,
              'max_new_tokens': args.max_new_tokens, 'do_sample': False,
              'device': args.device, 'dtype': str(dtype), 'attention': 'sdpa',
              'reference_access': False, 'output_postprocessing': 'strip_only',
              'packages': {x: importlib.metadata.version(x) for x in
                           ('torch', 'torchvision', 'transformers', 'accelerate', 'soundfile', 'safetensors')}}
    execution = {'runner_source_sha256': sha(Path(__file__)),
                 'output_policy': 'score_actual_output_including_empty_and_fixed_token_limit',
                 'memory_policy': 'release_unused_mps_cache_after_each_saved_prediction'}
    status = {'state': 'loading', 'started_at': utc(), 'hardware': platform.platform(),
              'execution': execution,
              'jobs_per_mode': len(jobs), 'modes': args.modes, 'contract': common}
    atomic_json(args.work / 'status.json', status)
    try:
        full_config = json.loads((args.model_cache / 'config.json').read_text())
        thinker_config = Qwen2_5OmniThinkerConfig.from_dict(full_config['thinker_config'])
        model, info = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
            args.model_cache, config=thinker_config, local_files_only=True, dtype=dtype,
            device_map=args.device, attn_implementation='sdpa', output_loading_info=True)
        missing = info.get('missing_keys', [])
        mismatched = info.get('mismatched_keys', [])
        if missing or mismatched:
            raise ValueError(f'Missing/mismatched Thinker weights: {missing}, {mismatched}')
        # The upstream generation_config.json has no token IDs. Derive these
        # from the actual Thinker subconfig, rather than the parent Omni config.
        model.generation_config = GenerationConfig.from_model_config(thinker_config)
        model.eval()
        processor = Qwen2_5OmniProcessor.from_pretrained(args.model_cache, local_files_only=True)
        atomic_json(args.work / 'loading.json', {'missing_keys': missing,
            'mismatched_keys': mismatched, 'unexpected_keys_count': len(info.get('unexpected_keys', [])),
            'parameters': sum(x.numel() for x in model.parameters()),
            'device': str(model.device), 'dtype': str(model.dtype),
            'generation_eos_token_id': model.generation_config.eos_token_id,
            'generation_pad_token_id': model.generation_config.pad_token_id})
        for mode in args.modes:
            contract = common | {'mode': mode, 'prompt': PROMPTS[mode]}
            path = args.work / mode / 'checkpoint.json'
            prior = json.loads(path.read_text()) if path.exists() else {'contract': contract, 'items': []}
            done = validate_checkpoint(prior, contract)
            resumed_rows = len(done)
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
                decoded = processor.batch_decode(tokens, skip_special_tokens=True,
                    clean_up_tokenization_spaces=False)[0]
                prediction, flags = generated_prediction(decoded, tokens[0].tolist(),
                    args.max_new_tokens, model.generation_config.eos_token_id)
                record = {'split': split, 'id': row['id'], 'prediction': prediction,
                          'audio_sha256': audio_hash, 'draft_sha256': draft_hash,
                          'elapsed_seconds': time.monotonic() - started,
                          'new_tokens': tokens.shape[1], **flags}
                prior['items'].append(record)
                done[key] = record
                atomic_json(path, prior)
                del batch, generated, tokens
                memory = release_mps_cache(torch, args.device)
                if memory is not None:
                    status['mps_memory_after_cleanup'] = memory
                status.update(state='running', mode=mode, processed=len(done), updated_at=utc())
                atomic_json(args.work / 'status.json', status)
                print(f'{mode} {len(done)}/{len(jobs)} {record["elapsed_seconds"]:.2f}s', flush=True)
            for split in args.splits:
                target = args.work / split / f'{mode}.csv'
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'prediction'])
                    writer.writerows((j['row']['id'], done[(split, j['row']['id'])]['prediction'])
                                     for j in jobs if j['split'] == split)
            diagnostics = {}
            for split in args.splits:
                rows = [r for (s, _), r in done.items() if s == split]
                diagnostics[split] = {'utterances': len(rows),
                    'at_token_limit': sum(r['new_tokens'] >= args.max_new_tokens for r in rows),
                    'empty_outputs': sum(not r['prediction'] for r in rows)}
            atomic_json(args.work / mode / 'run.json', contract | {'rows': len(done),
                'finished_at': utc(), 'execution': execution, 'resumed_rows': resumed_rows,
                'output_diagnostics_by_split': diagnostics})
        status.update(state='completed', finished_at=utc())
        atomic_json(args.work / 'status.json', status)
    except Exception as exc:
        status.update(state='failed', error_type=type(exc).__name__, error=str(exc), updated_at=utc())
        atomic_json(args.work / 'status.json', status)
        raise


if __name__ == '__main__':
    main()
