"""Package only the explicit public stress allowlist; never recurse into work."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from scripts.build_dataset import digest, write_json
from scripts.validate_public_eval_stress import validate


def package(public,probe,output,expected_rows=409):
    check=validate(public,probe,expected_rows=expected_rows)
    pairs=json.loads((probe/'pairs.json').read_text())['items']
    names=['NOTICE','README.md','plan.json','metadata.json','pairs.json','validation.json',
        'frozen-specification.md','eval/inputs.json','eval/references.json','inference/eval/inputs.json']
    names += ['eval/audio/'+p['id']+'.wav' for p in pairs]
    if output.exists():raise ValueError('Archive already exists; do not replace a published packet.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in sorted(names):
            path=(probe/name).resolve()
            if not path.is_relative_to(probe.resolve()):raise ValueError('Allowlist escapes the public probe.')
            info=zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644 << 16
            archive.writestr(info,path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist()==sorted(names) and archive.testzip() is None
        for name in names:
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest(probe/name)
    checksum=digest(output)
    output.with_suffix(output.suffix+'.sha256').write_text(checksum+'  '+output.name+'\n')
    receipt={'dataset':'tye-public-eval-stress-v1','file':output.name,'bytes':output.stat().st_size,
        'sha256':checksum,'archive_members':len(names),'unique_recordings':expected_rows,
        'derived_audio_rows':len(pairs),'private_test_used':False,'explicit_allowlist_verified':True,
        'all_archive_member_hashes_verified':True,'validation':check,
        'state':'public_development_candidate_not_listening_reviewed_not_model_evaluated'}
    write_json(output.with_suffix('.packaging.json'),receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['public','probe','output']:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.public,args.probe,args.output)))
