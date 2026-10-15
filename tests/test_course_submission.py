import json
import re
from scripts.build_course_submission import build, safe_json


def test_standalone_html_has_public_eval_but_no_external_runtime_assets(tmp_path):
    path = tmp_path / 'Team.html'
    size = build(path)
    html = path.read_text()
    assert size > 200000
    assert 'tye-ko-merged-v1-eval' in html
    assert not re.search(r'<script[^>]+src=', html)
    assert not re.search(r'<link[^>]+rel="stylesheet"', html)
    assert 'window.TYE_EMBEDDED=' in html
    assert 'public-eval-form' in html
    assert 'private-data/' not in html
    assert 'test-references.json' not in html
    assert 'source-pool.json' not in html


def test_embedding_cannot_close_script_or_lose_unicode():
    value = {'text':'</script><script>alert(1)</script>한글\u2028'}
    encoded = safe_json(value)
    assert '</script' not in encoded
    assert json.loads(encoded) == value
