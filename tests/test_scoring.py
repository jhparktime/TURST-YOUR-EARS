import itertools
import unicodedata
import pytest
from server.scoring import alignment, distance, normalize, parse_submission, score, validate_references


def ref(text='김민서가 발표합니다.', edits=None, **extra):
    edits = [] if edits is None else edits
    draft = text
    for e in reversed(edits):
        draft = draft[:e['start']] + e['replacement'] + draft[e['end']:]
    return {'id':'a', 'reference':text, 'draft':draft, 'edits':edits,
            'condition':'clean' if not edits else 'single' if len(edits) == 1 else 'multiple', **extra}


def test_korean_normalization():
    text = '오늘 회의를 시작합니다.'
    assert normalize(text) == normalize('오늘회의를시작합니다!')
    assert normalize(text) == normalize(unicodedata.normalize('NFD', text))
    assert normalize('OpenAI') == 'openai'
    assert normalize('3시') != normalize('세 시')
    assert normalize('- 3 . 5 %') == '-3.5%'
    assert normalize('-3.5%') != normalize('35%')
    assert normalize('민서가') != normalize('민서를')


def test_alignment_independently_matches_edit_distance_and_preserves_output():
    strings = [''.join(x) for n in range(4) for x in itertools.product('가나', repeat=n)]
    for reference in strings:
        for prediction in strings:
            parts, leading, cost = alignment(reference, prediction)
            assert cost == distance(reference, prediction)
            assert leading + ''.join(parts) == prediction


def test_macro_pools_characters_within_condition_and_includes_clean():
    refs = [ref('가', id='a'), ref('가나다라마바사아자', id='b'),
            ref('가나다라마', [{'start':0,'end':1,'replacement':'바'}], id='c')]
    result = score({'a':'','b':'가나다라마바사아자','c':'가나다라마'}, refs)
    assert result['conditions']['clean']['cer'] == 10
    assert result['macro_cer'] == 5  # score() permits subsets for diagnostic tests; manifests require all 3.
    assert result['micro_cer'] == pytest.approx(100/15)
    assert result['draft_macro_cer'] == 10
    assert result['cer_improvement_pp'] == 5
    assert result['clean_change_rate'] == 50


def test_copy_fix_and_overcorrection():
    row = ref('김민서가 발표합니다.', [{'start':0,'end':3,'replacement':'김민수'}])
    copied = score({'a':row['draft']}, [row])
    assert copied['cer_improvement_pp'] == 0
    assert copied['restoration_rate'] == 0
    assert copied['harmful_edit_rate'] == 0
    fixed = score({'a':row['reference']}, [row])
    assert fixed['macro_cer'] == 0
    assert fixed['restoration_rate'] == 100
    assert fixed['harmful_edit_rate'] == 0
    over = score({'a':'김민서를 발표합니다.'}, [row])
    assert over['restoration_rate'] == 100
    assert over['harmed'] == 1
    assert over['preserved_total'] == 6
    assert over['harmful_edit_rate'] == pytest.approx(100/6)
    assert score({'a':'김민수가 발표합니다. 김민서'}, [row])['restoration_rate'] == 0


def test_clean_control_and_normalization():
    row = ref('오늘 회의를 시작합니다.')
    result = score({'a':'오늘회의를 시작합니다!'}, [row])
    assert result['clean_change_rate'] == 0
    assert result['restoration_rate'] is None
    assert result['edit_total'] == 0
    assert score({'a':''}, [row])['clean_change_rate'] == 100
    assert score({'a':''}, [row])['harmful_edit_rate'] == 100


def test_insertions_and_empty_predictions():
    row = ref('가나다')
    for pred in ('라가나다', '가라나다', '가나다라'):
        result = score({'a':pred}, [row])
        assert result['harmed'] == 1
        assert result['macro_cer'] == pytest.approx(100/3)
    assert score({'a':'나라다'}, [ref('가')])['macro_cer'] == 300
    assert score({'a':''}, [row])['macro_cer'] == 100


def test_multiple_spans_and_different_length_replacement():
    row = ref('민서와 민서를 만납니다.', [{'start':0,'end':2,'replacement':'민수'},
                                       {'start':4,'end':6,'replacement':'수'}])
    result = score({'a':'민서와 수를 만납니다.'}, [row])
    assert result['restoration_rate'] == 50
    assert result['harmful_edit_rate'] == 0
    result = score({'a':row['reference']}, [row])
    assert result['restored'] == 2
    assert result['macro_cer'] == 0


def test_whole_reference_target_has_no_preserved_characters():
    row = ref('가', [{'start':0,'end':1,'replacement':'나'}])
    assert score({'a':'가'}, [row])['harmful_edit_rate'] is None


@pytest.mark.parametrize('mutation', [
    {'draft':'김민지가 발표합니다.'}, {'condition':'clean'}, {'context':'helpful'},
    {'edits':[{'start':True,'end':3,'replacement':'김민수'}]},
    {'edits':[{'start':0,'end':3,'replacement':'김민서'}]},
    {'edits':[{'start':0,'end':3,'replacement':''}]},
    {'edits':[{'start':0,'end':30,'replacement':'오류'}]},
])
def test_bad_annotations_and_unrecorded_draft_edits_rejected(mutation):
    row = ref(edits=[{'start':0,'end':3,'replacement':'김민수'}])
    row.update(mutation)
    with pytest.raises(ValueError): validate_references([row])


def test_overlap_adjacent_spans_and_ambiguous_decimal_rejected():
    with pytest.raises(ValueError):
        validate_references([ref('가나다', [{'start':0,'end':1,'replacement':'라'}, {'start':1,'end':2,'replacement':'마'}])])
    with pytest.raises(ValueError):
        validate_references([ref('3.5', [{'start':0,'end':1,'replacement':'삼'}])])


@pytest.mark.parametrize('body', [b'id,prediction\nx,one\nx,two', b'id,prediction\nx,one,two',
                                b'name,text\nx,a', b'id,prediction\nx', b'id,prediction\n', b'\xff'])
def test_bad_csv(body):
    with pytest.raises(ValueError): parse_submission(body)


def test_csv_quoted_commas_empty_and_bom():
    assert parse_submission(b'\xef\xbb\xbfid,prediction\nx,"hello, world"\ny,') == {'x':'hello, world','y':''}


def test_exact_ids_and_prediction_limit():
    with pytest.raises(ValueError): score({'wrong':'a'}, [ref()])
    with pytest.raises(ValueError): score({'a':'가'*4001}, [ref()])


def test_work_limit_checked_before_alignment(monkeypatch):
    def forbidden(*args):
        raise AssertionError('Alignment must not start before workload validation.')
    monkeypatch.setattr('server.scoring.alignment', forbidden)
    refs = [ref('가'*1000, id=str(i)) for i in range(32)]
    with pytest.raises(ValueError, match='computation limit'):
        score({str(i):'나'*1000 for i in range(32)}, refs)


def test_ambiguous_corruption_cannot_reward_copy_draft():
    row = ref('가가', [{'start':1, 'end':2, 'replacement':'나가'}])
    with pytest.raises(ValueError, match='Ambiguous reference-to-draft'):
        score({'a':row['draft']}, [row])
