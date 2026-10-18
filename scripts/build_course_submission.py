"""Produce the course's one-HTML submission from the original workshop website.

CSS, scripts, the public-eval manifest, aggregate results and sample CSVs are
embedded. This does not embed audio or any private test row.
"""
import argparse
import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def build(output):
    web = ROOT / 'web'
    html = (web / 'archive-v1.html').read_text()
    css = (web / 'style.css').read_text()
    html = re.sub(r'<link rel="stylesheet"[^>]+>', lambda _: '<style>' + css + '</style>', html)
    scripts = re.findall(r'<script src="([^"?]+)(?:\?[^\"]*)?" defer></script>', html)
    html = re.sub(r'\s*<script src="[^\"]+" defer></script>', '', html)
    assets = {'manifest': json.loads((web / 'data/eval.json').read_text()),
              'baselines': json.loads((web / 'data/baselines.json').read_text()),
              'scorer': (web / 'scorer.js').read_text(),
              'worker': (web / 'public-eval-worker.js').read_text()}
    if assets['manifest']['name'] != 'tye-ko-merged-v1-eval' or len(assets['manifest']['items']) != 409:
        raise ValueError('Wrong public eval asset.')
    snippets = ['<script>window.TYE_EMBEDDED=' + safe_json(assets) + ';</script>']
    for name in scripts:
        source = (web / name).read_text()
        if '</script' in source.lower():
            raise ValueError('Script close tag must be escaped before embedding.')
        snippets.append('<script>' + source + '</script>')
    html = html.replace('</body>', '\n'.join(snippets) + '\n</body>')
    for asset, mime in [('assets/favicon.svg', 'image/svg+xml'),
                        ('assets/sample-submission.csv', 'text/csv'), ('data/eval-copy.csv', 'text/csv')]:
        data = base64.b64encode((web / asset).read_bytes()).decode()
        original = 'href="' + asset + '"'
        replacement = 'href="data:' + mime + ';base64,' + data + '"'
        html = html.replace(original, replacement)
        # Trusted i18n markup contains JSON-escaped href attributes as well.
        html = html.replace(json.dumps(original)[1:-1], json.dumps(replacement)[1:-1])
    # A single file has no same-origin API. Keep private submissions disabled
    # until the organizer supplies a real HTTPS API in the canonical config.
    html = html.replace('const awaitingService = !apiBase && location.hostname.endsWith("github.io");',
        'const awaitingService = !apiBase && (Boolean(window.TYE_EMBEDDED) || location.hostname.endsWith("github.io"));')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    return output.stat().st_size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'file': str(args.output), 'bytes': build(args.output), 'private_test_rows': 0}))


if __name__ == '__main__':
    main()
