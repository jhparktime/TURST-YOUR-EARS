"""Queue public stress inference after the verified main v2 process finishes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from scripts.run_omni_baselines import atomic_json

ROOT=Path(__file__).resolve().parent.parent


def utc():return datetime.now(timezone.utc).isoformat()


def process_args(pid):
    p=subprocess.run(['ps','-p',str(pid),'-o','args='],capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['public','base_results','probe','work','qwen_model_cache','whisper_model_cache']:
        parser.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    parser.add_argument('--wait-pid',type=int,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();work=args.work
    work.mkdir(parents=True,exist_ok=True)
    status_path=work/'suite-status.json'
    validation=json.loads((args.probe/'validation.json').read_text())
    assert validation['metadata_sha256']==digest(args.probe/'metadata.json')
    assert validation['unique_recordings']==409 and validation['derived_audio_rows']==1227
    inputs=args.probe/'inference/eval/inputs.json'
    contract={'probe_metadata_sha256':digest(args.probe/'metadata.json'),
        'probe_validation_sha256':digest(args.probe/'validation.json'),
        'new_inputs_sha256':digest(inputs),'public_inputs_sha256':digest(args.public/'eval/inputs.json'),
        'qwen_model_cache':str(args.qwen_model_cache.resolve()),
        'whisper_model_cache':str(args.whisper_model_cache.resolve()),
        'modes':['audio-only','audio-draft'],'splits':['eval'],'max_new_tokens':512,
        'private_test_used':False,'auto_publish':False}
    if status_path.exists():
        status=json.loads(status_path.read_text())
        assert args.resume,'Inspect the existing suite before requesting --resume.'
        assert status['contract']==contract,'Probe/settings changed; do not mix outputs.'
        previous=status.get('pid')
        assert not previous or previous==os.getpid() or process_args(previous) is None,'Existing supervisor is alive.'
        assert status['state']!='complete_ready_for_review','Already complete; review results.'
    else:
        assert not args.resume,'No existing suite to resume.'
        status={'started_at':utc(),'contract':contract,'completed_phases':[],'executions':[]}
    previous_failure={key:status[key] for key in ('error_type','error','failed_at') if key in status}
    for key in previous_failure:status.pop(key,None)
    status['pid']=os.getpid()
    status['executions'].append({'started_at':utc(),'pid':os.getpid(),
        'runner_sha256':digest(Path(__file__)),'resume':args.resume,
        'previous_failure':previous_failure})
    caffeinate=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())])
    try:
        while True:
            primary=json.loads((args.base_results/'suite-status.json').read_text())
            if primary['state']=='complete_ready_for_review':break
            command=process_args(args.wait_pid)
            if not command or 'resume-tye-asr-v2-suite.py' not in command:
                raise RuntimeError('Main v2 process is absent before completion; inspect it instead of starting another model.')
            if primary['state']=='failed':raise RuntimeError('Main v2 suite failed; inspect its log first.')
            status.update(state='queued_waiting_for_main_v2',phase='wait_main',
                verified_live_primary_pid=args.wait_pid,verified_live_at=utc())
            atomic_json(status_path,status)
            time.sleep(30)
        processes=subprocess.check_output(['ps','-ax','-o','args='],text=True).splitlines()
        if any(' -m scripts.run_omni_baselines ' in p or ' -m scripts.transcribe_audio ' in p for p in processes):
            raise RuntimeError('Another model process is live; do not load a second GPU model.')
        main_result=json.loads((args.base_results/'comparison.json').read_text())
        assert main_result['dataset']=='tye-ko-asr-v2' and len(main_result['entries'])==10 and not main_result['pending']
        assert main_result['public_eval_reuse']['inputs_sha256']==contract['public_inputs_sha256']
        blind={'name':'tye-public-eval-stress-v1-new-audio-only','items':[
            {'id':r['id'],'audio':str((inputs.parent/r['audio']).resolve())} for r in load_inputs(inputs)]}
        blind_path=work/'blind-audio-inputs.json'
        if blind_path.exists():assert json.loads(blind_path.read_text())==blind
        else:write_json(blind_path,blind)
        phases=[('whisper','scripts.transcribe_audio',['--inputs',str(blind_path),
            '--output',str(work/'whisper'),'--model-cache',str(args.whisper_model_cache)]),
            ('qwen','scripts.run_omni_baselines',['--public',str(args.probe/'inference'),
            '--private',str(work/'unused-private'),'--model-cache',str(args.qwen_model_cache),
            '--work',str(work/'omni'),'--modes','audio-only','audio-draft','--splits','eval','--max-new-tokens','512']),
            ('score','scripts.score_public_eval_stress',['--public',str(args.public),
            '--base-results',str(args.base_results),'--probe',str(args.probe),'--work',str(work)])]
        for phase,module,options in phases:
            if phase in status['completed_phases']:continue
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            log=work/(phase+'-'+stamp+'.log')
            with log.open('w') as stream:
                child=subprocess.Popen([sys.executable,'-m',module,*options],cwd=ROOT,
                    stdout=stream,stderr=subprocess.STDOUT)
                status.update(state='running',phase=phase,child_pid=child.pid,log=str(log),updated_at=utc())
                atomic_json(status_path,status)
                code=child.wait()
                if code:raise RuntimeError(f'{phase} exited {code}; inspect {log}')
            status['completed_phases'].append(phase);atomic_json(status_path,status)
        status.update(state='complete_ready_for_review',finished_at=utc());atomic_json(status_path,status)
    except BaseException as exc:
        status.update(state='failed',failed_at=utc(),error_type=type(exc).__name__,error=str(exc))
        atomic_json(status_path,status)
        raise
    finally:
        if caffeinate.poll() is None:caffeinate.terminate()


if __name__=='__main__':main()
