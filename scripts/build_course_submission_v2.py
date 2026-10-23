"""Embed the actual-ASR workshop, public grader and aggregates in one HTML.

Public data-v2 assets and two public Eval audio examples are consumed.
No private folder is read or embedded.
"""
import argparse
import base64
import json
import re
from pathlib import Path

from scripts.build_course_submission import safe_json

ROOT = Path(__file__).resolve().parent.parent


def build(output):
    web=ROOT/'web'
    manifest=json.loads((web/'data-v2/eval.json').read_text())
    if manifest['protocol']!='ko-correction-v2' or manifest['name']!='tye-ko-asr-v2-eval' or len(manifest['items'])!=409:
        raise ValueError('Wrong v2 public Eval asset.')
    assets={'manifest':manifest,'metadata':json.loads((web/'data-v2/metadata.json').read_text()),
        'baselines':json.loads((web/'data-v2/baselines.json').read_text()),
        'scorer':(web/'scorer.js').read_text(),'scorer_v2':(web/'scorer-v2.js').read_text(),
        'worker':(web/'public-eval-worker-v2.js').read_text(),
        'copy_csv':base64.b64encode((web/'data-v2/eval-copy.csv').read_bytes()).decode()}
    if assets['baselines']['dataset']!='tye-ko-asr-v2':
        raise ValueError('Wrong v2 baseline aggregate asset.')
    html=(web/'index.html').read_text()
    html=html.replace('<script src="config-v2.js"></script>',
        '<script>window.TYE_V2_EMBEDDED='+safe_json(assets)+';</script>\n<script>'+ (web/'config-v2.js').read_text()+'</script>')
    for name in ('scorer.js','scorer-v2.js','leaderboard-v2.js','public-results-v2.js','community-v2.js','v2-app.js'):
        source=(web/name).read_text()
        if '</script' in source.lower():
            raise ValueError('Unsafe script close tag.')
        html=re.sub(r'<script src="'+re.escape(name)+r'(?:\?[^"<>]*)?"></script>',lambda _: '<script>'+source+'</script>',html)
    # The one-file course submission also carries the two public audio examples.
    for path in re.findall(r'<audio\b[^>]*\bsrc="([^"]+)"',html):
        audio=(web/path).read_bytes()
        html=html.replace('src="'+path+'"','src="data:audio/wav;base64,'+base64.b64encode(audio).decode()+'"')
    html=html.replace('href="data-v2/eval-copy.csv"','href="data:text/csv;base64,'+assets['copy_csv']+'"')
    for name,url in [('data-v2/baselines.json','https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/web/data-v2/baselines.json'),
                     ('scorer-v2.js','https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/web/scorer-v2.js'),
                     ('stress.html','https://jhparktime.github.io/TURST-YOUR-EARS/stress.html'),
                     ('archive-v1.html','https://jhparktime.github.io/TURST-YOUR-EARS/archive-v1.html')]:
        html=html.replace('href="'+name+'"','href="'+url+'"')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html)
    return {'file':str(output),'bytes':output.stat().st_size,'protocol':manifest['protocol'],
            'measurements':len(assets['baselines']['entries']),'pending':len(assets['baselines']['pending']),
            'private_test_rows':0,'external_runtime_assets':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().output)))
