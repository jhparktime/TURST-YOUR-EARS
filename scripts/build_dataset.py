"""Build a reproducible Korean correction pilot from pinned, licensed FLEURS audio.

Audio/reference are external corpus data; only transcript drafts are synthesized.
Evaluation references and per-item provenance are written outside the public set.
"""
import argparse
import csv
import difflib
import hashlib
import io
import itertools
import json
import random
import re
import tarfile
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

from server.scoring import VERSION, normalize, score, validate_manifest

REVISION = '70bb2e84b976b7e960aa89f1c648e09c59f894dd'
BASE = f'https://huggingface.co/datasets/google/fleurs/resolve/{REVISION}/data/ko_kr'
ARCHIVE_HASHES = {
    'dev': '496edcb5323e75b4a2830f5b5623684a0baf86d3728101853fd4fe503372157c',
    'test': '3489e529f2aad18d3357b746c5f955941d258b79dc60d8a102d5bced2a223184',
}
TSV_HASHES = {
    'dev': '6b236de107c6a1672233f6d710d26adfdb55570a3e6e35aca9dc4ff2be01cea4',
    'test': 'cf2f7c8765f6203e3c46ef620d5e936d3f331b6e8865455557777dd1347517f5',
}
PARTICLES = {'', '은', '는', '이', '가', '을', '를', '에', '의', '와', '과', '도', '만', '에서',
             '에게', '에는', '에도', '으로', '로', '보다', '처럼', '부터', '까지', '마다', '이며',
             '이고', '이라', '이다', '입니다', '이었다', '이었습니다', '이지만', '들이', '들은',
             '들을', '들의', '들', '라고', '라는', '적', '적인', '적으로', '에서는', '에서의', '로서', '으로서'}

PARTICLES |= {'들' + suffix for suffix in tuple(PARTICLES) if not suffix.startswith('들')}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fetch(cache, split, audio=False):
    name = f'{split}.tar.gz' if audio else f'{split}.tsv'
    path = cache / name
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.part')
        url = f'{BASE}/audio/{name}' if audio else f'{BASE}/{name}'
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        temporary.replace(path)
    if digest(path) != (ARCHIVE_HASHES if audio else TSV_HASHES)[split]:
        raise ValueError(f'Archive checksum mismatch: {path}')
    return path


def has_batchim(text):
    last = ord(text[-1])
    return 0xAC00 <= last <= 0xD7A3 and (last - 0xAC00) % 28 != 0


def load_pairs(path):
    pairs = json.loads(path.read_text(encoding='utf-8'))['pairs']
    mapping = {}
    for original, replacement in pairs:
        if original == replacement or has_batchim(original) != has_batchim(replacement):
            continue
        if len(original) != len(replacement):
            continue  # Initial version avoids particle changes and alignment ambiguity.
        mapping[original] = replacement
    return mapping


def candidates(text, mapping):
    found = []
    # Match entire noun stems plus a conservative list of particles, not substrings
    # inside unknown compounds or verbs. Numbers change value, never notation only.
    for token in re.finditer(r'[가-힣]+|\d+', text):
        word = token.group()
        if word.isdigit():
            if token.start() and text[token.start()-1] in '.-+':
                continue
            if token.end() < len(text) and text[token.end()] == '.':
                continue
            replacement = str(int(word) + (1 if int(word) % 2 == 0 else -1))
            if len(replacement) != len(word):
                continue
            found.append({'start':token.start(), 'end':token.end(), 'replacement':replacement, 'type':'number_value'})
            continue
        for original, replacement in mapping.items():
            if word.startswith(original) and word[len(original):] in PARTICLES:
                found.append({'start':token.start(), 'end':token.start()+len(original), 'replacement':replacement, 'type':'noun_substitution'})
                break
    return found


def valid_edits(reference, options, count, rng):
    combinations = list(itertools.combinations(options, count))
    rng.shuffle(combinations)
    for chosen in combinations[:300]:
        edits = [{k:edit[k] for k in ('start','end','replacement')} for edit in sorted(chosen, key=lambda e:e['start'])]
        draft = reference
        for edit in reversed(edits):
            draft = draft[:edit['start']] + edit['replacement'] + draft[edit['end']:]
        row = {'id':'check','condition':'single' if count == 1 else 'multiple', 'reference':reference, 'draft':draft,'edits':edits}
        try:
            result = score({'check':draft}, [row])
        except ValueError:
            continue
        if result['restoration_rate'] != 0 or result['harmful_edit_rate'] != 0:
            continue
        return edits, draft, [edit['type'] for edit in chosen]
    return None


def source_rows(tsv, mapping, seed):
    selected, seen_ids, seen_text = [], set(), set()
    rows = [line.split('\t') for line in tsv.read_text(encoding='utf-8').splitlines()]
    random.Random(seed).shuffle(rows)
    rejected = Counter()
    for row in rows:
        if len(row) != 7:
            rejected['malformed_tsv'] += 1; continue
        ident, filename, raw, text, _, samples, gender = row
        text = unicodedata.normalize('NFC', text)
        key = normalize(text)
        if ident in seen_ids or key in seen_text:
            rejected['repeated_sentence'] += 1; continue
        if not re.fullmatch(r'[가-힣0-9 .,!?%\-]+', text) or not 35 <= len(key) <= 180:
            rejected['text_filter'] += 1; continue
        if not 4 <= int(samples) / 16000 <= 20:
            rejected['duration_filter'] += 1; continue
        options = candidates(text, mapping)
        # All three conditions come from the same two-error-eligible population.
        one = valid_edits(text, options, 1, random.Random(f'{seed}:{filename}:1'))
        two = valid_edits(text, options, 2, random.Random(f'{seed}:{filename}:2'))
        if not one or not two:
            rejected['no_two_valid_spans'] += 1; continue
        seen_ids.add(ident); seen_text.add(key)
        selected.append(dict(source_id=ident, source_filename=filename, reference=text,
                             raw_transcription=raw, samples=int(samples), gender=gender,
                             variants={1:one, 2:two}))
    return selected, dict(rejected)


def choose(rows, count, rng):
    if count <= 0 or count % 3 or count > len(rows):
        raise ValueError(f'Requested {count} balanced rows but only {len(rows)} eligible; use a multiple of 3.')
    rng.shuffle(rows)
    rows = sorted(rows[:count], key=lambda row:row['samples'])
    result = []
    for start in range(0, count, 3):
        labels = ['clean','single','multiple']; rng.shuffle(labels)
        result.extend((row, label) for row, label in zip(rows[start:start+3], labels))
    rng.shuffle(result)
    return result


def extract_audio(archive, chosen, destination):
    import numpy as np
    import soundfile as sf
    wanted = {row['source_filename']:row for row, _ in chosen}
    found = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            filename = Path(member.name).name
            if filename not in wanted:
                continue
            if not member.isfile() or filename in found or member.size > 10_000_000:
                raise ValueError(f'Invalid or duplicate audio archive member: {member.name}')
            stream = tar.extractfile(member)
            payload = stream.read()
            if sf.info(io.BytesIO(payload)).subtype not in {'PCM_16', 'FLOAT'}:
                raise ValueError(f'Unsupported original WAV subtype: {filename}')
            samples, rate = sf.read(io.BytesIO(payload), dtype='float64', always_2d=True)
            row = wanted[filename]
            if rate != 16000 or samples.shape != (row['samples'], 1) or not np.any(samples):
                raise ValueError(f'Invalid audio format/length/silence: {filename}')
            out = destination / 'audio' / f'{row["id"]}.wav'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(payload)
            decoded, _ = sf.read(out, dtype='float64', always_2d=True)
            if not np.array_equal(decoded, samples):
                raise ValueError('Copying original WAV changed audio samples.')
            row.update(audio_sha256=digest(out), source_audio_sha256=hashlib.sha256(payload).hexdigest(), pcm_sha256=hashlib.sha256(samples.astype('<f8').tobytes()).hexdigest(), bytes=out.stat().st_size)
            found.add(filename)
    if found != set(wanted):
        raise ValueError(f'Missing {len(set(wanted)-found)} selected audio files.')


def write_review_materials(output, private, provenance):
    for split in ('dev','eval'):
        rows=[row for row in provenance if row['split']==split]
        write_json(private/f'{split}-review.json', {'status':'pending','items':[{'id':row['id'],'reference_audio_match':None,'audible_substitutions':None,'reviewer':None,'notes':''} for row in rows]})
    references={}
    for path in (output/'dev/references.json',private/'eval-references.json'):
        references.update({row['id']:row for row in json.loads(path.read_text(encoding='utf-8'))['items']})
    with (private/'review-template.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream,lineterminator="\n")
        writer.writerow(['split','id','audio','reference','draft','condition','edits','reference_audio_match','audible_substitutions','text_only_obvious_error','reviewer','notes'])
        for item in provenance:
            row=references[item['id']]
            writer.writerow([item['split'],item['id'],f"{item['split']}/audio/{item['id']}.wav",row['reference'],row['draft'],row['condition'],json.dumps(row['edits'],ensure_ascii=False),'','','','',''])


def build(cache, output, private, lexicon, dev_count, eval_count, seed):
    if (output/'metadata.json').exists():
        raise ValueError('Choose a new output directory/version; existing releases are not overwritten.')
    mapping = load_pairs(lexicon)
    pools, rejects = {}, {}
    for source_split in ('dev','test'):
        pools[source_split], rejects[source_split] = source_rows(fetch(cache, source_split), mapping, seed)
    dev_texts = {normalize(row['reference']) for row in pools['dev']}
    dev_ids = {row['source_id'] for row in pools['dev']}
    pools['test'] = [row for row in pools['test'] if row['source_id'] not in dev_ids and normalize(row['reference']) not in dev_texts
                     and all(difflib.SequenceMatcher(None, normalize(row['reference']), text, autojunk=False).ratio() < 0.85 for text in dev_texts)]
    selected = {'dev':choose(pools['dev'],dev_count,random.Random(seed)), 'eval':choose(pools['test'],eval_count,random.Random(seed+1))}
    summary, provenance, all_hashes = {}, [], set()
    for split, chosen in selected.items():
        for row, condition in chosen:
            row['id'] = hashlib.sha256(f'tye-fleurs-v1:{seed}:{split}:{row["source_filename"]}'.encode()).hexdigest()[:16]
        source_split = 'dev' if split == 'dev' else 'test'
        extract_audio(fetch(cache,source_split,audio=True),chosen,output/split)
        inputs, refs = [], []
        for row, condition in chosen:
            edits,draft,types = ([],row['reference'],[]) if condition == 'clean' else row['variants'][1 if condition == 'single' else 2]
            inputs.append({'id':row['id'],'audio':f'audio/{row["id"]}.wav','draft':draft})
            refs.append({'id':row['id'],'condition':condition,'reference':row['reference'],'draft':draft,'edits':edits})
            if row['audio_sha256'] in all_hashes:
                raise ValueError('Repeated audio across selected samples/splits.')
            all_hashes.add(row['audio_sha256'])
            provenance.append({k:row[k] for k in ('id','source_id','source_filename','reference','raw_transcription','gender','samples','audio_sha256','source_audio_sha256','pcm_sha256') } | {'split':split,'source_split':source_split,'condition':condition,'edit_types':types,'review_status':'pending_independent_listening','speaker_id':None})
        manifest={'name':f'tye-fleurs-ko-v1-{split}','protocol':VERSION,'conditions':['clean','single','multiple'],'items':refs}
        validate_manifest(manifest)
        public=output/split
        write_json(public/'inputs.json',{'name':manifest['name'],'items':inputs})
        with (public/'copy-draft.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream,lineterminator="\n")
            writer.writerow(['id','prediction'])
            writer.writerows((row['id'],row['draft']) for row in inputs)
        write_json(public/'references.json' if split=='dev' else private/'eval-references.json',manifest)
        copy_scores=score({row['id']:row['draft'] for row in refs},refs)
        write_json(public/'copy-draft.scores.json',copy_scores)
        lengths=[len(normalize(row['reference'])) for row in refs]
        summary[split]={'utterances':len(refs),'conditions':dict(Counter(row['condition'] for row in refs)), 'duration_seconds':sum(row['samples']/16000 for row,_ in chosen),'audio_bytes':sum(row['bytes'] for row,_ in chosen),'characters_min':min(lengths),'characters_max':max(lengths),'gender':dict(Counter(row['gender'] for row,_ in chosen)), 'inputs_sha256':digest(public/'inputs.json'), 'copy_macro_cer':copy_scores['macro_cer']}
        write_json(public/'audio-checksums.json',{row['id']:row['audio_sha256'] for row,_ in chosen})
    write_json(private/'provenance.json',provenance)
    write_review_materials(output,private,provenance)
    metadata={'name':'tye-fleurs-ko-v1','status':'pilot_pending_independent_listening','protocol':VERSION,'source':'google/fleurs','source_revision':REVISION,'language':'ko_kr','license':'CC-BY-4.0','seed':seed,'lexicon_sha256':digest(lexicon),'source_tsv_sha256':{s:digest(cache/f'{s}.tsv') for s in ('dev','test')},'source_archive_sha256':ARCHIVE_HASHES,'eligible_source_rows':{s:len(p) for s,p in pools.items()},'rejected':rejects,'splits':summary,'speaker_disjointness':'unverified: source TSV has no speaker identifiers; dev/test speakers may overlap','reference_policy':'Upstream normalized transcription, NFC only; not independently verified by our team','audio_policy':'Original 16 kHz WAV files copied byte-for-byte; no resampling or quantization','split_policy':'Official dev/test partitions; distinct sentence IDs, normalized texts (cross-split similarity < 0.85), and audio checksums; one recording per source sentence'}
    write_json(output/'metadata.json',metadata)
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('datasets/tye-fleurs-ko-v1'))
    parser.add_argument('--private-output',type=Path,default=Path('private-data/tye-fleurs-ko-v1'))
    parser.add_argument('--lexicon',type=Path,default=Path('datasets/tye-fleurs-ko-v1/substitutions.json'))
    parser.add_argument('--dev-count',type=int,default=30)
    parser.add_argument('--eval-count',type=int,default=75)
    parser.add_argument('--seed',type=int,default=20261015)
    args=parser.parse_args(); args.cache.mkdir(parents=True,exist_ok=True)
    metadata=build(args.cache,args.output,args.private_output,args.lexicon,args.dev_count,args.eval_count,args.seed)
    print(json.dumps(metadata['splits'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
