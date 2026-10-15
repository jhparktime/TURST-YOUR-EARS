"""Package only validated public eval and aggregate baseline scores for the site.

Individual test inputs, predictions, references and source IDs are never copied.
"""
import argparse
import json
from pathlib import Path

from scripts.build_dataset import digest, write_json
from scripts.run_omni_baselines import MODEL, REVISION
from scripts.baseline import PROMPTS, SYSTEM
from server.scoring import parse_submission, score, validate_manifest

ROOT = Path(__file__).resolve().parent.parent
DATASET = 'tye-ko-merged-v1'


def public_eval_snapshot(omni, mode, public, refs):
    """Accept a completed public split while private inference is still running.

    The active runner files are never changed. Partial ID coverage, changed
    inputs and mismatched inference settings must fail before publication.
    """
    folder = omni.parent / 'completed-public-eval'
    score_path = folder / f'{mode}.scores.json'
    if not score_path.exists():
        return None
    csv_path = folder / f'{mode}.csv'
    proof = json.loads((folder / f'{mode}.receipt.json').read_text())
    contract = proof['contract']
    expected = {'model': MODEL, 'revision': REVISION, 'mode': mode,
                'prompt': PROMPTS[mode], 'system': SYSTEM, 'row_limit': None,
                'reference_access': False, 'seed': 0, 'max_new_tokens': 512,
                'do_sample': False, 'output_postprocessing': 'strip_only'}
    if any(key not in contract or contract[key] != value for key, value in expected.items()):
        raise ValueError('Public snapshot model/settings differ from the fixed run.')
    active = json.loads((omni / 'status.json').read_text())
    if mode not in active['modes'] or contract != active['contract'] | {'mode': mode, 'prompt': PROMPTS[mode]}:
        raise ValueError('Public snapshot does not match the inference run contract.')
    if (proof.get('state') != 'full_public_eval_completed'
            or proof.get('private_predictions_exported') is not False
            or proof.get('rows') != len(refs)
            or proof.get('predictions_sha256') != digest(csv_path)
            or proof.get('reference_sha256') != digest(public / 'eval/references.json')
            or contract['input_manifests_sha256']['eval'] != digest(public / 'eval/inputs.json')):
        raise ValueError('Public snapshot coverage/provenance mismatch.')
    metrics = json.loads(score_path.read_text())
    if score(parse_submission(csv_path.read_bytes()), refs) != metrics:
        raise ValueError('Public snapshot scores differ from current evaluator.')
    return score_path, csv_path


def build(results, public, output):
    manifest_path = public / 'eval/references.json'
    manifest = json.loads(manifest_path.read_text())
    refs = validate_manifest(manifest)
    metadata = json.loads((public / 'metadata.json').read_text())
    if metadata['name'] != DATASET or digest(manifest_path) != metadata['splits']['eval']['references_sha256']:
        raise ValueError('Wrong or changed public dataset.')
    receipt = json.loads((results / 'status.json').read_text())
    if receipt['status'] != 'completed' or receipt['metadata_sha256'] != digest(public / 'metadata.json'):
        raise ValueError('Whisper run is incomplete or belongs to another dataset.')
    inputs = json.loads((public / 'eval/inputs.json').read_text())
    if [r['id'] for r in inputs['items']] != [r['id'] for r in refs]:
        raise ValueError('Public input/reference ID order mismatch.')
    entries = []
    # Recalculate public eval from CSV; private-test scores are aggregate receipts.
    candidates = [('Copy draft', results, 'copy'), ('Whisper large-v3-turbo · Audio only', results, 'audio-only')]
    omni = results / 'omni/full'
    for mode in ('text-only', 'audio-draft', 'audio-only'):
        candidates.append((f'Qwen2.5-Omni-3B · {mode}', omni, mode))
    pending = []
    for label, folder, mode in candidates:
        for split in ('eval', 'test'):
            score_path = folder / split / f'{mode}.scores.json'
            csv_path = folder / split / f'{mode}.csv'
            if not score_path.exists() and folder == omni and split == 'eval':
                snapshot = public_eval_snapshot(omni, mode, public, refs)
                if snapshot is not None:
                    score_path, csv_path = snapshot
            if not score_path.exists():
                pending.append({'baseline': label, 'split': split, 'state': 'not_completed'})
                continue
            metrics = json.loads(score_path.read_text())
            if split == 'eval':
                fresh = score(parse_submission(csv_path.read_bytes()), refs)
                if fresh != metrics:
                    raise ValueError('Saved scores differ from current evaluator.')
            if metrics['scorer'] != metadata['protocol'] or metrics['utterances'] != metadata['splits'][split]['utterances']:
                raise ValueError('Score version/coverage mismatch.')
            entries.append({'baseline': label, 'split': split, 'metrics': metrics,
                            'score_file_sha256': digest(score_path)})
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'eval.json', manifest)
    write_json(output / 'baselines.json', {'dataset': DATASET, 'protocol': metadata['protocol'],
        'primary_metric': 'macro_cer', 'entries': entries, 'pending': pending,
        'limitations': metadata['limitations']})
    (output / 'eval-copy.csv').write_bytes((results / 'eval/copy.csv').read_bytes())
    write_json(output / 'receipt.json', {'dataset': DATASET, 'public_eval_reference_sha256': digest(manifest_path),
        'public_eval_inputs_sha256': digest(public / 'eval/inputs.json'),
        'files': {name: digest(output / name) for name in ('eval.json', 'baselines.json', 'eval-copy.csv')},
        'private_row_export': False})
    lines = ['# Baseline measurements · tye-ko-merged-v1', '',
        '동일한 고정 eval/test에서 측정한 결과입니다. 모든 값은 %이며 개선폭은 %p입니다.',
        '개별 test 예측·정답은 포함하지 않았습니다. 미완료 실험은 점수 0으로 대체하지 않습니다.', '',
        '| Baseline | Split | Macro CER ↓ | Micro CER ↓ | WER ↓ | 개선폭 ↑ | 복원률 ↑ | 훼손률 ↓ | Clean 변경률 ↓ | 최악 조건 CER ↓ |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    keys = ['macro_cer','micro_cer','micro_wer','cer_improvement_pp','restoration_rate',
            'harmful_edit_rate','clean_change_rate','worst_cer']
    for entry in entries:
        values = ['N/A' if entry['metrics'][k] is None else f'{entry["metrics"][k]:.4f}' for k in keys]
        lines.append('| ' + ' | '.join([entry['baseline'], entry['split']] + values) + ' |')
    lines.extend(['', 'Copy는 초안을 그대로 유지합니다. Whisper는 초안 없이 음성만 입력합니다.',
        'Whisper: `mlx-community/whisper-large-v3-turbo@a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`.',
        'ko, temperature 0, task transcribe, initial prompt 없음, 이전 발화 문맥 재사용 없음.',
        'Qwen 실험은 고정 `Qwen/Qwen2.5-Omni-3B@f75b40e3da2003cdd6e1829b1f420ca70797c34e`에서 입력만 비교합니다.',
        'Whisper와 Qwen의 성능 차이를 입력 효과만으로 해석하지 않습니다.', '',
        f'미완료 split별 측정: {len(pending)}건. 조건별 CER/WER와 분자·분모는 [전체 JSON](../web/data/baselines.json)을 확인하세요.', '',
        '현재 오류는 실제 ASR 오인식이 아닌 합성 명사 치환입니다. 독립 청취 검수는 아직이며,',
        '높은 주입 구간 복원률을 전체 문장 정확도 또는 음성 활용의 증거로 해석하지 않습니다.', ''])
    (ROOT / 'docs/baseline-results.md').write_text('\n'.join(lines))
    return entries, pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'web/data')
    args = parser.parse_args()
    entries, pending = build(args.results, args.public, args.output)
    print(json.dumps({'completed_scores': len(entries), 'pending_scores': len(pending)}))


if __name__ == '__main__':
    main()
