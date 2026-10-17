"""Paired public-Eval audio stress probe; no private Test is opened."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from server.scoring import normalize
from server.scoring_v2 import validate_manifest

ROOT = Path(__file__).resolve().parent.parent
NAME = 'tye-public-eval-stress-v1'
CONDITIONS = ('original', 'gaussian_5db', 'packet_loss_20')


def generator(base_id, condition):
    seed = int.from_bytes(hashlib.sha256(f'{NAME}:{condition}:{base_id}'.encode()).digest()[:8], 'big')
    return np.random.Generator(np.random.PCG64(seed))


def degrade(samples, base_id, condition, sample_rate=16000):
    """Audio-only transform: neither transcripts nor scores are arguments."""
    if samples.dtype != np.int16 or samples.ndim != 1 or not len(samples) or sample_rate != 16000:
        raise ValueError('Expected nonempty original mono PCM16 at 16 kHz.')
    rng = generator(base_id, condition)
    x = samples.astype(np.float64) / 32768
    if condition == 'gaussian_5db':
        rms = float(np.sqrt(np.mean(x*x)))
        if rms <= 1e-12:
            raise ValueError('Silent source cannot define SNR; inspect instead of silently dropping it.')
        noise = rng.standard_normal(len(x))
        noise -= noise.mean()
        noise *= rms / (10**(5/20) * np.sqrt(np.mean(noise*noise)))
        mixed = x + noise
        gain = min(1.0, 0.98 / float(np.max(np.abs(mixed))))
        y = np.rint(mixed * gain * 32768).astype(np.int16)
        quantized = y.astype(np.float64) / 32768
        effective_noise = quantized - x*gain
        snr = float(10*np.log10(np.mean((x*gain)**2)/np.mean(effective_noise**2)))
        return y, {'target_snr_db':5.0, 'effective_snr_db':snr, 'gain':gain,
                   'clipped_samples':0}
    if condition == 'packet_loss_20':
        packet = sample_rate // 50
        packets = math.ceil(len(x)/packet)
        count = math.floor(0.2 * packets + 0.5)
        dropped = np.sort(rng.choice(packets, size=count, replace=False))
        y = samples.copy()
        lost = 0
        for index in dropped:
            start, stop = int(index)*packet, min((int(index)+1)*packet,len(y))
            y[start:stop] = 0
            lost += stop-start
        return y, {'packet_samples':packet, 'packets':packets, 'lost_packets':count,
                   'lost_samples':lost, 'lost_sample_fraction':lost/len(y),
                   'dropped_packet_indices':dropped.tolist()}
    raise ValueError('Unsupported degradation condition.')


def build(public, output, expected_rows=409):
    inputs_path, refs_path = public/'eval/inputs.json', public/'eval/references.json'
    rows = load_inputs(inputs_path)
    references = validate_manifest(json.loads(refs_path.read_text()))
    refs = {r['id']:r for r in references}
    if (len(rows)!=expected_rows or len(refs)!=expected_rows or
        {r['id'] for r in rows} != set(refs) or
        any(r['draft']!=refs[r['id']]['draft'] for r in rows)):
        raise ValueError('Expected complete aligned public Eval inputs/references.')
    if output.exists():
        raise ValueError('Use a new output folder; never overwrite a probe.')
    spec=ROOT/'docs/public-eval-stress-probe.md'
    plan={'name':NAME, 'scope':'public_eval_only', 'unique_recordings':len(rows),
        'source_inputs_sha256':digest(inputs_path), 'source_references_sha256':digest(refs_path),
        'source_metadata_sha256':digest(public/'metadata.json'), 'conditions':list(CONDITIONS),
        'protocol':'ko-correction-v2', 'primary_metric':'micro_cer',
        'noise_snr_db':5.0, 'packet_milliseconds':20, 'packet_loss_fraction':0.2,
        'seed_rule':'SHA256(tye-public-eval-stress-v1:condition:base_id) first 8 bytes big endian; NumPy PCG64',
        'specification_sha256':digest(spec), 'builder_sha256':digest(Path(__file__)),
        'numpy':importlib.metadata.version('numpy'), 'soundfile':importlib.metadata.version('soundfile'),
        'selection_used_model_scores':False, 'private_test_used':False,
        'prior_original_v2_aggregate_scores_seen':True}
    output.mkdir(parents=True)
    write_json(output/'plan.json',plan)
    shutil.copyfile(spec,output/'frozen-specification.md')
    (output/'eval/audio').mkdir(parents=True)
    items, gold, pairs = [], [], []
    for row in rows:
        audio=(public/'eval'/row['audio']).resolve()
        # Paths must stay within the public Eval folder.
        if not audio.is_relative_to((public/'eval').resolve()):
            raise ValueError('Input audio escapes public Eval.')
        info=sf.info(audio)
        if info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16':
            raise ValueError('Expected unchanged public PCM16 source.')
        samples,sr=sf.read(audio,dtype='int16')
        for cond in CONDITIONS:
            ident=row['id']+'--'+cond
            target=output/'eval/audio'/(ident+'.wav')
            diagnostics={}
            if cond=='original':shutil.copyfile(audio,target)
            else:
                degraded,diagnostics=degrade(samples,row['id'],cond,sr)
                sf.write(target,degraded,sr,subtype='PCM_16')
            items.append({'id':ident,'audio':'audio/'+target.name,'draft':row['draft']})
            gold.append({**refs[row['id']],'id':ident})
            pairs.append({'id':ident,'base_id':row['id'],'condition':cond,
                'original_audio_sha256':digest(audio),'audio_sha256':digest(target),
                'frames':len(samples),'sample_rate':sr,
                'draft_correct':normalize(row['draft'])==normalize(refs[row['id']]['reference']),
                **diagnostics})
    def manifest(values):return {'name':NAME+'-eval','protocol':'ko-correction-v2','items':values}
    write_json(output/'eval/inputs.json',manifest(items))
    write_json(output/'eval/references.json',manifest(gold))
    write_json(output/'pairs.json',{'name':NAME,'items':pairs})
    # New-audio-only inference subset avoids rerunning unchanged originals.
    subset=[{**r,'audio':'../../eval/'+r['audio']} for r in items if not r['id'].endswith('--original')]
    (output/'inference/eval').mkdir(parents=True)
    write_json(output/'inference/eval/inputs.json',manifest(subset))
    duration=sum(p['frames']/p['sample_rate'] for p in pairs if p['condition']=='original')
    clean=sum(p['draft_correct'] for p in pairs if p['condition']=='original')
    metadata={**plan,'state':'constructed_not_model_evaluated_not_listening_reviewed',
        'plan_sha256':digest(output/'plan.json'), 'unique_duration_seconds':duration,
        'derived_audio_rows':len(items), 'new_audio_rows':len(subset),
        'draft_correct_per_condition':clean,'draft_error_per_condition':len(rows)-clean,
        'human_listening_review':'not_performed', 'model_evaluation':'not_started',
        'inputs_sha256':digest(output/'eval/inputs.json'),
        'references_sha256':digest(output/'eval/references.json'),
        'pairs_sha256':digest(output/'pairs.json'),
        'inference_inputs_sha256':digest(output/'inference/eval/inputs.json')}
    write_json(output/'metadata.json',metadata)
    attribution=(public/'NOTICE').read_text().split('Changes:',1)[0]
    (output/'NOTICE').write_text(attribution+
        'Changes in this public stress derivative: original-view WAV bytes are copied unchanged from actual-ASR v2; '
        'gaussian_5db adds synthetic white Gaussian noise and joint peak gain; packet_loss_20 replaces selected 20 ms packets with zeros. '
        'All views retain v2 actual-ASR drafts and NFC source references.\n'
        'Upstream authors do not endorse this derivative. Independent listening has not been performed.\n')
    (output/'README.md').write_text(
        '# Trust Your Ears public Eval stress probe\n\n'
        'Public development candidate; no private Test is included.\n'
        f'{len(rows)} distinct recordings form {len(items)} paired views: original, synthetic Gaussian noise at 5 dB, and 20% packet erasure at 20 ms.\n'
        'The same real-ASR draft and reference are retained across all three views. '
        'This is one hour of distinct source recordings, not three independent hours.\n\n'
        'eval/inputs.json contains only id, audio and draft. eval/references.json contains public references. '
        'pairs.json records correspondence and measured corruption; plan.json and frozen-specification.md define the probe.\n'
        'Run Copy and evaluation with the project scripts.baseline and scripts.evaluate commands. '
        'Report each audio condition separately; do not mix with the v2 official Test ranking.\n\n'
        'Automated signal checks do not certify acoustic recoverability or source transcript accuracy. '
        'Model difficulty and independent listening are not yet verified.\n')
    return metadata


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.public,args.output),ensure_ascii=False))
