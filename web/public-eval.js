/* Free public-eval scoring on GitHub Pages, separate from private test submissions. */
(() => {
  let manifest, baselineData, result, error, worker, downloadURL;
  let phase = "ready";
  const embedded = window.TYE_EMBEDDED;
  async function asset(name) {
    if (embedded) return embedded[name === "eval.json" ? "manifest" : "baselines"];
    const response = await fetch(`data/${name}`, {cache:"no-cache"});
    if (!response.ok) throw new Error(t("공개 평가 자료를 불러올 수 없습니다.", "Unable to load public evaluation data."));
    return response.json();
  }
  function render() {
    const box = $("public-eval-result");
    box.replaceChildren();
    $("public-eval-score").disabled = phase === "running";
    if (error) { box.append(element("p", errorMessage(error), "warning")); return; }
    if (!result) {
      box.append(element("p", phase === "running"
        ? t("409개 발화를 채점하고 있습니다…", "Scoring 409 utterances…")
        : t("공개 eval의 409행 예측 CSV를 선택하세요. 파일은 이 브라우저 안에서만 처리됩니다.",
            "Choose a 409-row prediction CSV for public eval. Your file stays in this browser.")));
      return;
    }
    box.append(element("p", "PUBLIC EVAL · tye-ko-merged-v1 · ko-correction-v1", "tag"));
    box.append(element("div", percent(result.macro_cer), "score-number"));
    box.append(element("p", "MACRO CER ↓", "score-label"));
    const summary = element("div"); summary.className = "table-wrap";
    summary.append(table([t("지표", "Metric"), t("값", "Value")], [
      [t("초안 대비 개선폭 ↑", "Improvement over draft ↑"), points(result.cer_improvement_pp)],
      [t("오류 구간 복원률 ↑", "Span restoration ↑"), `${percent(result.restoration_rate)} (${result.restored}/${result.edit_total})`],
      [t("정상 구간 훼손률 ↓", "Damage outside spans ↓"), `${percent(result.harmful_edit_rate)} (${result.harmed}/${result.preserved_total})`],
      [t("무오류 초안 변경률 ↓", "Clean changes ↓"), `${percent(result.clean_change_rate)} (${result.clean_changed}/${result.clean_total})`],
      ["Micro CER ↓", percent(result.micro_cer)], ["WER ↓", percent(result.micro_wer)],
      [t("최악 조건 CER ↓", "Worst-condition CER ↓"), percent(result.worst_cer)],
    ], t("공개 eval 진단 지표", "Public eval diagnostics")));
    box.append(summary);
    const conditions = element("div"); conditions.className = "table-wrap";
    conditions.append(table([t("조건", "Condition"), "N", "CER ↓", "WER ↓"],
      Object.entries(result.conditions).map(([name,m]) => [name,String(m.utterances),percent(m.cer),percent(m.wer)]),
      t("조건별 결과", "Results by condition")));
    box.append(conditions);
    const link = element("a", t("전체 지표 JSON 저장", "Save all metrics as JSON"));
    link.href = downloadURL; link.download = "tye-ko-merged-v1-public-eval.scores.json"; box.append(link);
  }
  function renderBaselines() {
    if (!baselineData) return;
    const box = $("baseline-results"); box.replaceChildren();
    const wrap = element("div"); wrap.className = "table-wrap"; wrap.tabIndex = 0;
    wrap.append(table([t("방법", "Method"), "Split", "Macro CER ↓", t("개선폭 ↑", "Δ CER ↑"),
      t("복원률 ↑", "Restoration ↑"), t("정상 구간 훼손률 ↓", "Damage ↓"), t("Clean 변경률 ↓", "Clean changes ↓")],
      baselineData.entries.map(({baseline,split,metrics:m}) => [baseline,split,percent(m.macro_cer),
        points(m.cer_improvement_pp),percent(m.restoration_rate),percent(m.harmful_edit_rate),percent(m.clean_change_rate)]),
      t("동일 merged-v1 평가셋 · 측정 완료된 결과만 표시", "Same merged-v1 evaluation sets · Completed measurements only")));
    box.append(wrap);
    if (baselineData.pending.length) box.append(element("p",
      t("Qwen2.5-Omni의 Text-only·Audio+draft·Audio-only 비교는 실행 준비/진행 중입니다. 미완료 점수는 순위에 포함하지 않습니다.",
        "Matched Qwen2.5-Omni Text-only, Audio+draft and Audio-only runs are being prepared or executed. Unfinished runs are excluded."), "fine"));
    const details = element("details"); details.append(element("summary", t("조건별 CER·WER와 전체 지표", "Condition CER/WER and full metrics")));
    const conditionWrap = element("div"); conditionWrap.className = "table-wrap";
    conditionWrap.append(table([t("방법", "Method"), "Split", "Clean CER", "Single CER", "Multiple CER", "Micro CER", "WER", "Worst CER"],
      baselineData.entries.map(({baseline,split,metrics:m}) => [baseline,split,...["clean","single","multiple"].map(c => percent(m.conditions[c].cer)),
        percent(m.micro_cer),percent(m.micro_wer),percent(m.worst_cer)]), "ko-correction-v1"));
    details.append(conditionWrap); box.append(details);
  }
  $("public-eval-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (phase === "running") return;
    const file = $("public-eval-file").files[0];
    error = null; result = null;
    if (!file) { error = localizedError("CSV 파일을 선택하세요.", "Choose a CSV file."); render(); return; }
    if (file.size > 2*1024*1024) { error = new Error("Maximum submission size is 2 MiB."); render(); return; }
    phase = "running"; render();
    try {
      manifest ||= await asset("eval.json");
      if (manifest.name !== "tye-ko-merged-v1-eval" || manifest.items.length !== 409) throw new Error("Public evaluation dataset mismatch.");
      const csv = await file.arrayBuffer();
      let url;
      if (embedded) url = URL.createObjectURL(new Blob([embedded.scorer, "\n", embedded.worker], {type:"text/javascript"}));
      else url = new URL("public-eval-worker.js", document.baseURI).href;
      worker = new Worker(url);
      const response = await new Promise((resolve,reject) => {
        worker.onmessage = event => resolve(event.data);
        worker.onerror = () => reject(new Error(t("채점을 시작할 수 없습니다. 브라우저 설정을 확인하세요.", "Unable to start scoring. Check browser settings.")));
        worker.postMessage({csv,manifest}, [csv]);
      });
      worker.terminate(); if (embedded) URL.revokeObjectURL(url);
      if (response.error) throw new Error(response.error);
      result = response.result;
      if (downloadURL) URL.revokeObjectURL(downloadURL);
      downloadURL = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)], {type:"application/json"}));
    } catch (exc) { error = exc; worker?.terminate(); }
    finally { phase = "ready"; render(); }
  });
  window.addEventListener("languagechange", () => { render(); renderBaselines(); });
  render();
  asset("baselines.json").then(data => { baselineData = data; renderBaselines(); }).catch(exc => {
    $("baseline-results").textContent = exc.message;
  });
})();
