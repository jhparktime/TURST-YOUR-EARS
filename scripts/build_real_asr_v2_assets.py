"""Publish only public v2 references and verified aggregate baseline results."""
import argparse
import json
import shutil
from pathlib import Path

from scripts.build_dataset import digest,write_json
from scripts.score_real_asr_v2_baselines import complete_mode
from server.scoring import parse_submission
from server.scoring_v2 import score,validate_manifest

ROOT = Path(__file__).resolve().parent.parent


def build(public,private,results,output):
    metadata = json.loads((public/'metadata.json').read_text())
    validation_path = results/'dataset-validation.json'
    validation = json.loads(validation_path.read_text())
    if validation['metadata_sha256'] != digest(public/'metadata.json') or validation['active_recordings'] != 2631:
        raise ValueError('V2 dataset has no matching full integrity validation.')
    entries,pending,proof = [],[],{}
    refsets = {}
    for split,root in [('eval',public),('test',private)]:
        path = private/'test-references.json' if split=='test' else public/'eval/references.json'
        if digest(path) != metadata['splits'][split]['references_sha256']:
            raise ValueError('V2 reference bytes changed.')
        refs = validate_manifest(json.loads(path.read_text()))
        refsets[split] = refs
        for label,file in [('Copy draft','copy-draft.csv'),('Whisper audio-only','whisper-audio-only.csv'),
                           ('Qwen audio-only','qwen-audio-only.csv')]:
            metrics = score(parse_submission((root/split/file).read_bytes()),refs)
            entries.append({'baseline':label,'split':split,'metrics':metrics})
    for mode,label in [('text-only','Qwen text-only'),('audio-draft','Qwen audio+draft')]:
        if not (results/'omni'/mode/'run.json').exists():
            pending.extend({'baseline':label,'split':split,'state':'not_completed'} for split in ('eval','test'))
            continue
        predictions,receipt = complete_mode(results/'omni',public,private,mode)
        proof[mode] = receipt
        entries.extend({'baseline':label,'split':split,'metrics':score(predictions[split],refsets[split])}
                       for split in ('eval','test'))
    baseline = {'dataset':metadata['name'],'protocol':metadata['protocol'],'primary_metric':'micro_cer',
        'status':metadata['status'],'reference_verification':metadata.get('reference_verification',{}),'entries':entries,'pending':pending,'private_row_export':False,
        'limitations':metadata['limitations']}
    # A recursive privacy check is stronger than checking top-level names alone.
    def aggregates_only(value):
        if isinstance(value,dict):
            if {'id','reference','draft','prediction','audio','source_id'} & set(value):
                raise ValueError('Individual data in baseline aggregate export.')
            for item in value.values(): aggregates_only(item)
        elif isinstance(value,list):
            for item in value: aggregates_only(item)
    aggregates_only(baseline)
    output.mkdir(parents=True,exist_ok=True)
    for origin,name in [(public/'eval/references.json','eval.json'),(public/'eval/copy-draft.csv','eval-copy.csv'),
                        (public/'metadata.json','metadata.json')]:
        shutil.copyfile(origin,output/name)
    write_json(output/'baselines.json',baseline)
    write_json(output/'receipt.json',{'dataset':metadata['name'],'private_row_export':False,
        'validation_sha256':digest(validation_path),'files':{name:digest(output/name)
            for name in ('eval.json','eval-copy.csv','metadata.json','baselines.json')}})
    canonical = ROOT/'datasets/tye-ko-asr-v2'
    canonical.mkdir(parents=True,exist_ok=True)
    for name in ('metadata.json','README.md','NOTICE'):
        shutil.copyfile(public/name,canonical/name)
    for split in ('train','eval'):
        target=canonical/split
        target.mkdir(exist_ok=True)
        for name in ('inputs.json','references.json','audio-checksums.json','copy-draft.csv','copy-draft.scores.json'):
            shutil.copyfile(public/split/name,target/name)
    measurement=ROOT/'docs/measurements'
    shutil.copyfile(validation_path,measurement/'real-asr-v2-validation.json')
    if proof:
        write_json(measurement/'real-asr-v2-completed-models.json',{
            'dataset':metadata['name'],'private_row_export':False,'models':proof})
    lines=['# Actual-ASR v2 baseline measurements','',
        '주 지표는 Micro CER이며 v1 점수와 비교하지 않습니다.',
        '초안 생성기와 같은 Audio-only 기준점은 해당 생성기 부분집합에서 Copy와 같습니다.',
        '전체·생성기별 결과를 함께 해석하고 미완료 실험은 점수로 채우지 않습니다.','',
        '| Baseline | Split | Micro CER ↓ | Utterance Macro CER ↓ | WER ↓ | 개선폭 ↑ | 슬롯 복원률 ↑ | 정상 문자 훼손률 ↓ | 불필요 삽입률 ↓ |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for entry in entries:
        values=[entry['metrics'][key] for key in ('micro_cer','macro_cer','micro_wer','cer_improvement_pp',
            'slot_restoration_rate','harmful_edit_rate','unwanted_insertion_rate')]
        lines.append('| '+' | '.join([entry['baseline'],entry['split']]+[
            'N/A' if v is None else f'{v:.4f}' for v in values])+' |')
    lines.extend(['',f'완료 {len(entries)}건 / 미완료 {len(pending)}건.',
        '정의와 한계: [v2 규격](real-asr-v2.md). 전체 생성기별·조건별 분자와 분모는 '
        '[집계 JSON](../web/data-v2/baselines.json)에 있습니다.',''])
    (ROOT/'docs/real-asr-v2-results.md').write_text('\n'.join(lines))
    print(json.dumps({'dataset':metadata['name'],'complete':len(entries),'pending':len(pending),
                      'private_row_export':False}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('public','private','results'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'web/data-v2')
    args=parser.parse_args()
    build(args.public,args.private,args.results,args.output)
