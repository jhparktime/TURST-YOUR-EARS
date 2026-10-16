"""Construct, validate and evaluate real-ASR v2 without publishing private files.

The config supplies local paths, never credentials. Start only after both
training drafters finish successfully. Existing dataset folders are not reused
or overwritten by this fresh construction entrypoint. Inference itself resumes
using scripts.run_omni_baselines once a dataset has been built.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

from scripts.build_dataset import digest
from scripts.run_omni_baselines import atomic_json

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    work = Path(config['work'])
    work.mkdir(parents=True,exist_ok=True,mode=0o700)
    status_path = work / 'suite-status.json'
    if status_path.exists():
        raise ValueError('A suite already exists. Inspect its exact stage before any explicit recovery.')
    status = {'state':'starting','started_at':datetime.now(timezone.utc).isoformat(),
        'config_sha256':digest(args.config),'design_sha256':digest(ROOT / 'docs/real-asr-v2.md'),
        'assignment_plan_sha256':digest(Path(config['plan']) / 'plan.json'),
        'auto_publish':False,'private_outputs_must_stay_local':True,'completed_phases':[]}
    (work / 'frozen-design.md').write_bytes((ROOT / 'docs/real-asr-v2.md').read_bytes())
    atomic_json(status_path,status)

    def run(phase,module,keys,extra=()):
        status.update(state='running',phase=phase,updated_at=datetime.now(timezone.utc).isoformat())
        atomic_json(status_path,status)
        command = [sys.executable,'-m',module]
        for key in keys:
            command.extend(['--'+key.replace('_','-'),str(config[key])])
        command.extend(extra)
        with (work / f'{phase}.log').open('w') as stream:
            subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        status['completed_phases'].append(phase)
        atomic_json(status_path,status)

    try:
        # Completed drafter receipts are required before any new folder is built.
        if json.loads((Path(config['qwen_train']) / 'status.json').read_text())['state'] != 'completed':
            raise ValueError('Training Qwen drafter is not complete; do not launch concurrently.')
        run('build_dataset','scripts.build_real_asr_v2',('plan','source_public','source_private',
            'qwen_existing','qwen_train','whisper_existing','whisper_train','public','private'))
        run('validate_dataset','scripts.validate_real_asr_v2',('public','private','source_public',
            'source_private','whisper_existing','whisper_train','qwen_existing','qwen_train'),
            ['--output',str(work/'dataset-validation.json')])
        for split in ('train','eval','test'):
            run('review_'+split,'scripts.build_listening_review',('public','private'),['--split',split])
        run('matched_inference','scripts.run_omni_baselines',('public','private'),
            ['--model-cache',config['qwen_model_cache'],'--work',str(work/'omni'),
             '--modes','text-only','audio-draft','--splits','eval','test','--max-new-tokens','512'])
        run('score_all_baselines','scripts.score_real_asr_v2_baselines',('public','private','work'))
        status.update(state='complete_ready_for_review',finished_at=datetime.now(timezone.utc).isoformat())
        atomic_json(status_path,status)
    except Exception as exc:
        status.update(state='failed',error_type=type(exc).__name__,error=str(exc),
                      failed_at=datetime.now(timezone.utc).isoformat())
        atomic_json(status_path,status)
        raise


if __name__ == '__main__':
    main()
