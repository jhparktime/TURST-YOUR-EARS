/* Real-ASR correction, ko-correction-v2. V1 remains a separate frozen scorer.
 * Python parity, including insertion/deletion slots, is tested independently.
 * Load scorer.js first (normalization and strict CSV parser are shared).
 */
(() => {
  const base = typeof module !== "undefined" ? require("./scorer.js") : globalThis.TYEScorer;
  const {normalize, words, distance, parseCSV} = base;
  const VERSION = "ko-correction-v2", PRIMARY_METRIC = "micro_cer";
  const CONDITIONS = ["clean", "substitution", "deletion", "insertion", "mixed"];
  const chars = Array.from;
  const rate = (n, d) => d ? 100 * n / d : null;
  function alignedSlots(reference, hypothesis) {
    const a = chars(reference), b = chars(hypothesis);
    const matrix = [Int32Array.from({length:b.length+1}, (_,i) => i)];
    for (let i = 1; i <= a.length; i++) {
      const row = new Int32Array(b.length+1); row[0] = i;
      for (let j = 1; j <= b.length; j++) row[j] = Math.min(row[j-1]+1,
        matrix[i-1][j]+1, matrix[i-1][j-1]+Number(a[i-1] !== b[j-1]));
      matrix.push(row);
    }
    const values = Array(a.length).fill(""), gaps = Array(a.length+1).fill("");
    let i = a.length, j = b.length;
    while (i || j) {
      if (i && j && matrix[i][j] === matrix[i-1][j-1]+Number(a[i-1] !== b[j-1])) {
        values[i-1] = b[j-1]; i--; j--;
      } else if (i && matrix[i][j] === matrix[i-1][j]+1) i--;
      else { gaps[i] = b[j-1] + gaps[i]; j--; }
    }
    return {characters:values, gaps, errors:matrix[a.length][b.length],
      substitutions:values.filter((c,k) => c && c !== a[k]).length,
      deletions:values.filter(c => !c).length,
      insertions:gaps.reduce((s,c) => s+chars(c).length,0)};
  }
  function condition(aligned) {
    const kinds = [["substitution","substitutions"],["deletion","deletions"],
      ["insertion","insertions"]].filter(([,key]) => aligned[key]).map(([name]) => name);
    return kinds.length === 1 ? kinds[0] : kinds.length ? "mixed" : "clean";
  }
  function validateReferences(refs) {
    if (!Array.isArray(refs) || !refs.length || refs.length > 20000) throw new Error("Invalid v2 reference manifest.");
    const seen = new Set();
    for (const row of refs) {
      if (!row || Object.keys(row).sort().join(",") !== "draft,id,reference,source")
        throw new Error("V2 references require exactly id, reference, draft, source.");
      if (typeof row.id !== "string" || !row.id || chars(row.id).length > 120 || row.id !== row.id.trim() || seen.has(row.id))
        throw new Error("Reference IDs must be nonempty and unique.");
      seen.add(row.id);
      for (const key of ["reference","draft"]) {
        const text = row[key];
        if (typeof text !== "string" || text !== text.normalize("NFC") || chars(text).length > 4000)
          throw new Error("Reference and draft must be bounded NFC text.");
        const length = chars(normalize(text)).length;
        if (length > 1000 || (key === "reference" && !length))
          throw new Error("Reference requires 1–1000 scored characters; draft may be empty.");
      }
      if (typeof row.source !== "string" || !row.source || chars(row.source).length > 80)
        throw new Error("A nonempty drafter source label is required.");
    }
  }
  function counter() {
    return {errors:0,draft_errors:0,characters:0,word_errors:0,words:0,utterances:0,
      cer_sum:0,draft_cer_sum:0,restored_slots:0,error_slot_total:0,changed_slots:0,
      harmed:0,preserved_total:0,inserted_clean_gaps:0,clean_gap_total:0,clean_changed:0,
      clean_total:0,substitutions:0,deletions:0,insertions:0,draft_substitutions:0,
      draft_deletions:0,draft_insertions:0};
  }
  function metrics(b) {
    return {...b,cer:rate(b.errors,b.characters),draft_cer:rate(b.draft_errors,b.characters),
      macro_cer:b.cer_sum/b.utterances,draft_macro_cer:b.draft_cer_sum/b.utterances,
      cer_improvement_pp:rate(b.draft_errors-b.errors,b.characters),wer:rate(b.word_errors,b.words),
      slot_restoration_rate:rate(b.restored_slots,b.error_slot_total),
      correction_precision:rate(b.restored_slots,b.changed_slots),
      correction_f1:rate(2*b.restored_slots,b.changed_slots+b.error_slot_total),
      harmful_edit_rate:rate(b.harmed,b.preserved_total),
      unwanted_insertion_rate:rate(b.inserted_clean_gaps,b.clean_gap_total),
      clean_change_rate:rate(b.clean_changed,b.clean_total)};
  }
  function score(predictions, manifest) {
    if (manifest?.protocol !== VERSION || typeof manifest.name !== "string" || !manifest.name.trim())
      throw new Error("Unsupported evaluation manifest.");
    const refs = manifest.items;
    validateReferences(refs);
    if (predictions.size !== refs.length || refs.some(r => !predictions.has(r.id)))
      throw new Error("Submission IDs must exactly match this evaluation set (no missing or extra IDs).");
    const groups = new Map(), sources = new Map(), total = counter();
    let cells = 0;
    for (const row of refs) {
      const prediction = predictions.get(row.id);
      if (typeof prediction !== "string" || chars(prediction).length > 4000)
        throw new Error("Prediction must be a string of at most 4000 characters.");
      const reference = normalize(row.reference), draft = normalize(row.draft), hypothesis = normalize(prediction);
      const targetChars = chars(reference), rw = words(row.reference), hw = words(prediction);
      cells += (targetChars.length+1)*(chars(draft).length+1)+(targetChars.length+1)*(chars(hypothesis).length+1);
      cells += (rw.length+1)*(hw.length+1);
      if (cells > 40000000) throw new Error("Submission exceeds the scorer computation limit. Contact the organizers.");
      const before = alignedSlots(reference,draft), after = alignedSlots(reference,hypothesis), value = counter();
      Object.assign(value,{errors:after.errors,draft_errors:before.errors,characters:targetChars.length,
        word_errors:distance(rw,hw),words:rw.length,utterances:1,
        cer_sum:100*after.errors/targetChars.length,draft_cer_sum:100*before.errors/targetChars.length});
      for (const [channel,targets] of [["characters",targetChars],["gaps",Array(targetChars.length+1).fill("")]]) {
        targets.forEach((target,k) => {
          const old = before[channel][k], current = after[channel][k], dirty = old !== target;
          value.error_slot_total += Number(dirty);
          value.restored_slots += Number(dirty && current === target);
          value.changed_slots += Number(old !== current);
          if (!dirty) {
            if (channel === "characters") { value.preserved_total++; value.harmed += Number(current !== target); }
            else { value.clean_gap_total++; value.inserted_clean_gaps += Number(Boolean(current)); }
          }
        });
      }
      if (!before.errors) { value.clean_total = 1; value.clean_changed = Number(hypothesis !== reference); }
      for (const key of ["substitutions","deletions","insertions"]) {
        value[key] = after[key]; value["draft_"+key] = before[key];
      }
      const label = condition(before);
      if (!groups.has(label)) groups.set(label,counter());
      if (!sources.has(row.source)) sources.set(row.source,counter());
      for (const bucket of [groups.get(label),sources.get(row.source),total])
        for (const key of Object.keys(value)) bucket[key] += value[key];
    }
    const aggregate = metrics(total);
    const conditions = Object.fromEntries(CONDITIONS.filter(k => groups.has(k)).map(k => [k,metrics(groups.get(k))]));
    const result = {scorer:VERSION,primary_metric:PRIMARY_METRIC,micro_cer:aggregate.cer,
      micro_wer:aggregate.wer,draft_micro_cer:aggregate.draft_cer,
      worst_cer:Math.max(...Object.values(conditions).map(c => c.cer)),conditions,
      sources:Object.fromEntries([...sources.keys()].sort().map(k => [k,metrics(sources.get(k))])),utterances:refs.length};
    for (const key of ["macro_cer","draft_macro_cer","cer_improvement_pp","slot_restoration_rate",
      "restored_slots","error_slot_total","changed_slots","correction_precision","correction_f1",
      "harmful_edit_rate","harmed","preserved_total","unwanted_insertion_rate","inserted_clean_gaps",
      "clean_gap_total","clean_change_rate","clean_changed","clean_total"]) result[key] = aggregate[key];
    result.counts = Object.fromEntries(["errors","draft_errors","characters","substitutions","deletions",
      "insertions","draft_substitutions","draft_deletions","draft_insertions"].map(k => [k,total[k]]));
    return result;
  }
  const api = {VERSION,PRIMARY_METRIC,normalize,words,distance,parseCSV,alignedSlots,condition,score};
  if (typeof module !== "undefined") module.exports = api;
  else globalThis.TYEScorerV2 = api;
})();
