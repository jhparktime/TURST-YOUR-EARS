from scripts.prepare_real_asr_v2 import assignment


def test_assignment_ignores_reference_draft_errors_and_input_order():
    rows = [{'id':str(i),'draft':'정상'} for i in range(409)]
    altered = [dict(row,draft='고의 오류',reference='사후 정답',asr_cer=100) for row in reversed(rows)]
    first = assignment(rows,'eval')
    assert first == assignment(altered,'eval')
    assert list(first.values()).count('whisper-turbo') == 205
    assert list(first.values()).count('qwen-omni') == 204
