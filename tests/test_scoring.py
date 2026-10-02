import unicodedata
import pytest
from server.scoring import distance, normalize, parse_submission, score, validate_references


def ref(text='김민서가 발표합니다.', condition='helpful', **extra):
    return {'id': 'a', 'reference': text, 'condition': condition, **extra}


def test_korean_normalization():
    text = '오늘 회의를 시작합니다.'
    assert normalize(text) == normalize('오늘회의를시작합니다!')
    assert normalize(text) == normalize(unicodedata.normalize('NFD', text))
    assert normalize('OpenAI') == 'openai'
    assert normalize('3시') != normalize('세 시')
    assert normalize('-3.5%') == '-3.5%'
    assert normalize('- 3 . 5 %') == '-3.5%'
    assert normalize('-3.5%') != normalize('35%')
    assert normalize('민서가') != normalize('민서를')


def test_standard_edit_cases():
    assert distance('가나다', '가라다마') == 2
    assert distance('가나', '') == 2
    assert distance('', '가') == 1


def test_macro_pools_inside_condition_not_utterance_average():
    refs = [ref('가', id='a'), ref('가나다라마바사아자', id='b'), ref('가나다라마', id='c', condition='misleading')]
    result = score({'a': '', 'b': '가나다라마바사아자', 'c': '가나다라마'}, refs)
    assert result['conditions']['helpful']['cer'] == 10
    assert result['macro_cer'] == 5
    assert result['micro_cer'] == pytest.approx(100/15)
    assert result['worst_cer'] == 10


def test_no_context_excluded_from_ranking_and_diagnostics():
    refs = [ref('가', id='a'), ref('나', id='b', condition='no_context')]
    result = score({'a':'가', 'b':''}, refs)
    assert result['macro_cer'] == 0
    assert result['conditions']['no_context']['cer'] == 100


def test_insertion_rate_can_exceed_100():
    assert score({'a': '나라다'}, [ref('가')])['macro_cer'] == 300


def test_empty_is_deletion_and_missing_annotations_are_null():
    result = score({'a': ''}, [ref()])
    assert result['macro_cer'] == 100
    assert result['entity_accuracy'] is None
    assert result['wrong_context_rate'] is None
    assert result['mixed_accuracy'] is None


def test_entity_error_and_particle_error_are_separate():
    row = ref(entities=[{'start':0,'end':3,'text':'김민서','wrong':['김민수']}])
    wrong = score({'a':'김민수가 발표합니다.'}, [row])
    assert wrong['entity_accuracy'] == 0
    assert wrong['wrong_context_rate'] == 100
    particle = score({'a':'김민서는 발표합니다.'}, [row])
    assert particle['entity_accuracy'] == 100
    assert particle['macro_cer'] > 0
    # Merely appending a correct name must not fix the aligned occurrence.
    appended = score({'a':'김민수가 발표합니다. 김민서'}, [row])
    assert appended['entity_accuracy'] == 0


def test_alias_affects_entity_diagnostic_only():
    row = ref('AI가 발전합니다.', entities=[{'start':0,'end':2,'text':'AI','aliases':['에이아이']}])
    result = score({'a':'에이아이가 발전합니다.'}, [row])
    assert result['entity_accuracy'] == 100
    assert result['macro_cer'] > 0


def test_multiple_names_and_repeated_occurrences():
    row = ref('민서와 민서를 만납니다.', entities=[{'start':0,'end':2,'text':'민서'}, {'start':4,'end':6,'text':'민서'}])
    result = score({'a':'민서와 민수를 만납니다.'}, [row])
    assert result['entity_accuracy'] == 50


def test_mixed_joint_success_requires_all_targets():
    row = ref('민서가 네오젠을 소개합니다.', condition='partially_wrong', entities=[
        {'start':0,'end':2,'text':'민서','wrong':['민수']}, {'start':4,'end':7,'text':'네오젠'}])
    assert score({'a':row['reference']}, [row])['mixed_accuracy'] == 100
    result = score({'a':'민수가 네오젠을 소개합니다.'}, [row])
    assert result['mixed_accuracy'] == 0
    assert result['entity_accuracy'] == 50


@pytest.mark.parametrize('entity', [
    {'start':0,'end':2,'text':'김민서'},
    {'start':0,'end':3,'text':'김민서','aliases':['김민수'],'wrong':['김민수']},
    {'start':0,'end':3,'text':'김민서','aliases':['']},
])
def test_bad_annotations_rejected(entity):
    with pytest.raises(ValueError): validate_references([ref(entities=[entity])])


def test_partial_annotations_require_both_kinds():
    with pytest.raises(ValueError):
        validate_references([ref(condition='partially_wrong', entities=[{'start':0,'end':3,'text':'김민서','wrong':['김민수']}])])


@pytest.mark.parametrize('body', [b'id,prediction\nx,one\nx,two', b'id,prediction\nx,one,two',
                                b'name,text\nx,a', b'id,prediction\nx', b'id,prediction\n', b'\xff'])
def test_bad_csv(body):
    with pytest.raises(ValueError): parse_submission(body)


def test_csv_quoted_commas_empty_and_bom():
    assert parse_submission(b'\xef\xbb\xbfid,prediction\nx,"hello, world"\ny,') == {'x': 'hello, world', 'y': ''}


def test_exact_ids():
    with pytest.raises(ValueError): score({'wrong': 'a'}, [ref()])


def test_excessive_work_rejected_before_scoring():
    refs = [ref('가'*1000, id=str(i)) for i in range(16)]
    with pytest.raises(ValueError, match='computation limit'):
        score({str(i):'나'*1000 for i in range(16)}, refs)
