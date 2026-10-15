from collections import Counter

import pytest

from scripts.build_five_hour_dataset import (
    assign_conditions, build_neighbors, duration_select, jamo, particle_class, pronunciation_key, variants_for)
from scripts.build_dataset import has_batchim
from server.scoring import score
from scripts.zeroth_source import source_files


def test_phonetic_distractors_are_attested_close_words_with_matching_particle_class():
    vocabulary = {'사랑': 3, '사람': 2, '자랑': 4, '가방': 3, '가상': 3, '가정': 2,
                  '카레': 3, '카래': 3, '희귀': 1}
    neighbors = build_neighbors(vocabulary)
    assert '사람' in neighbors['사랑']
    for word, alternatives in neighbors.items():
        for other in alternatives:
            assert vocabulary[other] >= 2
            assert word != other and has_batchim(word) == has_batchim(other)
            assert particle_class(word) == particle_class(other)
            assert pronunciation_key(word) != pronunciation_key(other)
            assert 1 <= sum(a != b for a, b in zip(jamo(word), jamo(other))) <= 2
    assert '카래' not in neighbors.get('카레', [])
    assert '희귀' not in neighbors


def test_rieul_coda_is_not_exchanged_with_other_codas_before_ro_particle():
    neighbors = build_neighbors({'서울': 3, '서운': 3, '추억': 3})
    assert '서운' not in neighbors.get('서울', [])


def test_generated_drafts_do_not_rewrite_gold_or_corrupt_normal_spans():
    source = '사랑을 담은 가방을 보냈다'
    tokens = [{'word': w, 'start': source.index(w), 'end': source.index(w) + len(w)} for w in ['사랑', '가방']]
    variants = variants_for(source, tokens, {'사랑': ['사람'], '가방': ['가상']})
    assert set(variants) == {'clean', 'single', 'multiple'}
    assert {v['reference'] for v in variants.values()} == {source}
    for label, row in variants.items():
        assert len(row['edits']) == {'clean': 0, 'single': 1, 'multiple': 2}[label]
        result = score({'candidate': row['draft']}, [row])
        assert result['harmful_edit_rate'] == 0
        if label != 'clean': assert result['restoration_rate'] == 0


def test_independent_multiple_spans_require_a_preserved_character():
    source = '사랑 가방'
    tokens = [{'word': w, 'start': source.index(w), 'end': source.index(w) + len(w)} for w in ['사랑', '가방']]
    assert variants_for(source, tokens, {'사랑': ['사람'], '가방': ['가상']}) is None


def test_duration_selection_does_not_count_duplicate_readings_as_new_speech():
    rows = [
        {'source_id': 'a', 'speaker_id': '1', 'reference': '같은 문장', 'duration_seconds': 10},
        {'source_id': 'b', 'speaker_id': '2', 'reference': '같은문장', 'duration_seconds': 10},
        {'source_id': 'c', 'speaker_id': '3', 'reference': '다른 발화', 'duration_seconds': 10}]
    selected = duration_select(rows, 20)
    assert len(selected) == 2 and 'c' in {r['source_id'] for r in selected}


def test_condition_assignment_preserves_all_rows_and_balances_counts():
    rows = [{'source_id': str(i), 'samples': 16000 * (i + 4)} for i in range(14)]
    assigned = assign_conditions(rows, 'test')
    assert {r['source_id'] for r, _ in assigned} == {r['source_id'] for r in rows}
    counts = Counter(c for _, c in assigned)
    assert max(counts.values()) - min(counts.values()) == 1


def test_source_shards_must_come_from_the_pinned_allowlist():
    assert len(source_files(['test-00000-of-00001.parquet'])) == 1
    with pytest.raises(ValueError): source_files(['../../private/reference.json'])
    with pytest.raises(ValueError): source_files([])
