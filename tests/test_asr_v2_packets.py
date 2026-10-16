import zipfile

import pytest

from scripts.package_real_asr_v2 import archive


def test_explicit_archive_allowlist_excludes_neighboring_answers(tmp_path):
    inputs = tmp_path/'inputs.json'
    inputs.write_text('public input')
    (tmp_path/'test-references.json').write_text('PRIVATE GOLD SENTINEL')
    target = tmp_path/'packet.zip'
    result = archive(target,[(inputs,'test/inputs.json')],private=True)
    with zipfile.ZipFile(target) as packet:
        assert packet.namelist() == ['test/inputs.json']
        assert packet.read('test/inputs.json') == b'public input'
    assert result['files'] == 1 and target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError,match='overwrite'):
        archive(target,[(inputs,'test/inputs.json')])


@pytest.mark.parametrize('names',[['../answers.json'],['/answers.json'],['x','x']])
def test_archive_rejects_unsafe_or_duplicate_paths(tmp_path,names):
    source = tmp_path/'input'
    source.write_text('safe')
    with pytest.raises(ValueError,match='path'):
        archive(tmp_path/'packet.zip',[(source,name) for name in names])
