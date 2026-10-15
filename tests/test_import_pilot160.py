import zipfile

import pytest

from scripts.import_pilot160 import allocate, check_archive, correction_options, build
from server.scoring import score


def annotations(names):
    entities = [{'entity_id': str(i), 'name': name, 'occurrence': '1'} for i, (name, _) in enumerate(names)]
    corruptions = [{'entity_id': str(i), 'gold_name': name, 'occurrence': '1',
        'context_condition': 'misleading', 'is_corrupted': 'True', 'distractor': wrong}
        for i, (name, wrong) in enumerate(names)]
    return entities, corruptions


def test_converter_preserves_source_number_spelling_and_ignores_acronym_rewrite():
    source = '김민서는 삼십 년 동안 에스케이에서 일했다'
    entities, corruptions = annotations([('김민서', '김민수'), ('SK', 'KD')])
    variants, rejected = correction_options('example', source, entities, corruptions)
    assert variants['single']['reference'] == source
    assert variants['single']['draft'] == '김민수는 삼십 년 동안 에스케이에서 일했다'
    assert set(variants) == {'clean', 'single'}
    assert rejected[0]['reason'] == 'name_not_in_unchanged_source'


def test_adjacent_entities_cannot_be_counted_as_two_independent_corruptions():
    entities, corruptions = annotations([('김민서', '김민수'), ('박지훈', '박지한')])
    variants, rejected = correction_options('example', '김민서 박지훈이 말했다', entities, corruptions)
    assert set(variants) == {'clean', 'single'}
    assert any('unchanged scored character' in r['reason'] for r in rejected)


def test_occurrence_offsets_and_copy_restoration_are_not_inferred_by_string_presence():
    entities, corruptions = annotations([('김민서', '김민수')])
    entities[0]['occurrence'] = corruptions[0]['occurrence'] = '2'
    variants, _ = correction_options('example', '김민서가 다시 김민서라고 했다', entities, corruptions)
    row = variants['single']
    assert row['edits'] == [{'start': 8, 'end': 11, 'replacement': '김민수'}]
    assert row['draft'] == '김민서가 다시 김민수라고 했다'
    assert score({'example': row['draft']}, [row])['restoration_rate'] == 0


def test_balanced_allocator_never_repeats_audio_and_does_not_fabricate_missing_multiple():
    rows = [{'original_id': str(i), 'variants': {'clean': {}, **({'single': {}} if i < 4 else {}),
             **({'multiple': {}} if i < 2 else {})}} for i in range(7)]
    selected, reserve = allocate(rows, 2)
    assert len({r['original_id'] for r, _ in selected}) == 6
    assert len(reserve) == 1
    assert sorted(c for _, c in selected) == ['clean', 'clean', 'multiple', 'multiple', 'single', 'single']
    with pytest.raises(ValueError, match='Not enough valid multiple'):
        allocate(rows, 3)


def test_import_rejects_wrong_digest_and_overlapping_public_private_folders(tmp_path):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('untrusted/run.sh', 'exit 0')
    with pytest.raises(ValueError, match='SHA256'):
        check_archive(archive)
    with pytest.raises(ValueError, match='non-nested'):
        build(archive, tmp_path / 'public', tmp_path / 'public/private')
