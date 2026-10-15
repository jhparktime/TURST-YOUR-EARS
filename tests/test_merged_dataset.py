import pytest

from scripts.merge_correction_datasets import balanced_conditions, select_duration


def recording(ident, speaker, text, seconds):
    return {'source_id': ident, 'speaker_id': speaker, 'reference': text,
            'samples': seconds * 16000, 'duration_seconds': seconds}


def test_alternate_readers_cannot_inflate_available_unique_speech():
    rows = [recording('a', '1', '같은 문장', 10),
            recording('b', '2', '같은문장', 10),
            recording('c', '3', '새로운 발화', 10)]
    with pytest.raises(ValueError, match='Not enough unique'):
        select_duration(rows, 25)
    selected = select_duration(rows, 20)
    assert len(selected) == 2
    assert sum(r['samples'] for r in selected) == 20 * 16000


def test_input_file_order_does_not_change_the_heldout_selection():
    rows = [recording(str(i), str(i % 3), f'서로 다른 문장 {i}', 5 + i) for i in range(8)]
    assert select_duration(rows, 30) == select_duration(list(reversed(rows)), 30)


def test_rebalancing_never_changes_or_drops_the_selected_source_recordings():
    rows = [recording(str(i), str(i), f'발화 {i}', 5 + i) for i in range(10)]
    original = [dict(r) for r in rows]
    result = balanced_conditions(rows, 'test')
    assert {r['source_id'] for r, _ in result} == {r['source_id'] for r in rows}
    assert len(result) == len(rows)
    assert sorted(sum(c == label for _, c in result) for label in ('clean', 'single', 'multiple')) == [3, 3, 4]
    assert rows == original
