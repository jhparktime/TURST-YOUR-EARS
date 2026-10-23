"""Explicit-allowlist public and private v2 packets; never archive a parent tree.

The participant ZIP has only Train/Eval answers. Test inputs and organizer
answers are separate local files, even if this command runs before release.
"""
import argparse
import json
import zipfile
from pathlib import Path

from scripts.build_dataset import digest, write_json


def archive(target, files, private=False):
    if target.exists():
        raise ValueError('Refuse to overwrite an existing packet.')
    names = [name for _,name in files]
    if len(set(names)) != len(names) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
        raise ValueError('Invalid or duplicate archive path.')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as stream:
        for source,name in files:
            stream.write(source,name)
    if private:
        target.chmod(0o600)
    with zipfile.ZipFile(target) as stream:
        if stream.testzip() is not None or set(stream.namelist()) != set(names):
            raise ValueError('Archive CRC/allowlist mismatch.')
    checksum = digest(target)
    target.with_suffix(target.suffix+'.sha256').write_text(checksum+'  '+target.name+'\n')
    if private:
        target.with_suffix(target.suffix+'.sha256').chmod(0o600)
    return {'file':target.name,'bytes':target.stat().st_size,'sha256':checksum,'files':len(names)}


def package(public,private,output):
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    public_files = [(public / name,name) for name in ('README.md','NOTICE','metadata.json')]
    for split in ('train','eval'):
        for name in ('inputs.json','references.json','audio-checksums.json','copy-draft.csv',
                     'copy-draft.scores.json','listening-review.csv','review.html'):
            public_files.append((public / split / name,f'{split}/{name}'))
        public_files += [(p,str(p.relative_to(public))) for p in sorted((public/split/'audio').glob('*.wav'))]
    private_ids = {r['id'] for r in json.loads((private/'test-references.json').read_text())['items']}
    old_private_ids = {r['v1_id'] for r in json.loads((private/'source-mapping.json').read_text()) if r['split']=='test'}
    for path,_ in public_files:
        if path.suffix != '.wav':
            text = path.read_text()
            if any(i in text for i in private_ids | old_private_ids):
                raise ValueError('Private Test ID leaked into public packet.')
    public_packet = archive(output/'tye-ko-asr-v2-participant.zip',public_files)
    # Never include test-references, listening-review, predictions or mapping.
    test_files = [(public/'NOTICE','NOTICE'),(public/'README.md','README.md')]
    test_files += [(private/'test'/name,'test/'+name) for name in ('inputs.json','audio-checksums.json')]
    test_files += [(p,str(p.relative_to(private))) for p in sorted((private/'test/audio').glob('*.wav'))]
    test_packet = archive(output/'tye-ko-asr-v2-test-inputs.zip',test_files,private=True)
    organizer_files = [(p,str(p.relative_to(private))) for p in sorted(private.rglob('*')) if p.is_file()]
    organizer_packet = archive(output/'tye-ko-asr-v2-organizer.zip',organizer_files,private=True)
    result = {'dataset':'tye-ko-asr-v2','state':'packaged_not_published',
        'reference_verification':json.loads((public/'metadata.json').read_text()).get('reference_verification',{}),'public_participant':public_packet,
        'private_test_inputs':test_packet,'private_organizer':organizer_packet,
        'private_test_ids_in_public_files':0,'test_input_packet_answers_included':False}
    write_json(output/'packaging.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    package(args.public,args.private,args.output)
