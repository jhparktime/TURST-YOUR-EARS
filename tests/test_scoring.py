import pytest
from server.scoring import distance, parse_submission, score, words


def test_standard_edit_cases():
    assert distance('a b c'.split(), 'a x c d'.split()) == 2
    assert distance(['a', 'b'], []) == 2
    assert distance([], ['a']) == 1
    assert words('Ｍarina,  HELLO!') == ['marina', 'hello']
    assert words('15') != words('fifteen')


def test_macro_not_micro():
    refs = [{'id': 'a', 'condition': 'short', 'reference': 'one'},
            {'id': 'b', 'condition': 'long', 'reference': 'one two three four'}]
    result = score({'a': '', 'b': 'one two three four'}, refs)
    assert result['macro_wer'] == 50
    assert result['micro_wer'] == 20
    assert result['conditions']['short']['wer'] == 100


def test_insertion_rate_can_exceed_100():
    refs = [{'id': 'a', 'condition': 'c', 'reference': 'a'}]
    assert score({'a': 'x y z'}, refs)['macro_wer'] == 300


@pytest.mark.parametrize('body', [b'id,prediction\nx,one\nx,two', b'id,prediction\nx,one,two',
                                b'name,text\nx,a', b'id,prediction\nx', b'id,prediction\n', b'\xff'])
def test_bad_csv(body):
    with pytest.raises(ValueError): parse_submission(body)


def test_csv_quoted_commas_empty_and_bom():
    assert parse_submission(b'\xef\xbb\xbfid,prediction\nx,"hello, world"\ny,') == {'x': 'hello, world', 'y': ''}


def test_exact_ids():
    with pytest.raises(ValueError):
        score({'wrong': 'a'}, [{'id': 'a', 'condition': 'c', 'reference': 'a'}])


def test_excessive_work_rejected():
    refs = [{'id': str(i), 'condition': 'c', 'reference': 'word ' * 500} for i in range(41)]
    with pytest.raises(ValueError, match='computation limit'):
        score({str(i): 'word ' * 500 for i in range(41)}, refs)
