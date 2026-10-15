from scripts.diagnose_public_selective_correction import selective_draft


def test_selective_change_keeps_numbers_and_raw_punctuation():
    draft = '김민서가 15일 발표했다.'
    value, count = selective_draft(draft, '김민수가 십오일 발표했다.', 1, 2)
    assert value == '김민수가 15일 발표했다.' and count == 1


def test_correcting_a_word_keeps_tabs_newlines_and_quotes():
    value, count = selective_draft('오늘\t“김민서가,”\n발표했다.', '오늘 김민수가 발표했다.', 1, 2)
    assert value == '오늘\t“김민수가,”\n발표했다.' and count == 1


def test_nonparallel_word_alignment_and_zero_budget_preserve_draft():
    draft = '회의 시작합니다'
    assert selective_draft(draft, '회의를 이제 시작합니다', 2, 3) == (draft, 0)
    draft = '김민서가 발표했다'
    assert selective_draft(draft, '김민수가 발표했다', 0, 0) == (draft, 0)
