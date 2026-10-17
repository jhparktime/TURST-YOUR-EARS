/* Public development probe only. The v2 official Test is unaffected. */
(() => {
  const scorer = typeof module !== 'undefined' ? require('./scorer-v2.js') : globalThis.TYEScorerV2;
  const conditions = ['original', 'gaussian_5db', 'packet_loss_20'];
  function score(predictions, manifest, pairing) {
    if (manifest.name !== 'tye-public-eval-stress-v1-eval' || manifest.items.length !== 1227 ||
        pairing.dataset !== 'tye-public-eval-stress-v1' || pairing.items.length !== 1227)
      throw new Error('Wrong public stress dataset.');
    const pairs = new Map(pairing.items.map(r => [r.id, r]));
    if (pairs.size !== 1227) throw new Error('Duplicate pairing IDs.');
    for (const r of manifest.items) {
      const p=pairs.get(r.id);
      if (!p || !conditions.includes(p.condition) || r.id!==p.base_id+'--'+p.condition ||
          typeof p.draft_correct!=='boolean' ||
          p.draft_correct!==(scorer.normalize(r.reference)===scorer.normalize(r.draft)))
        throw new Error('Invalid public pairing metadata.');
    }
    scorer.score(predictions, manifest); // Full strict CSV coverage and text limits.
    const groups = {}, originals=new Set(pairing.items.filter(r=>r.condition==='original').map(r=>r.base_id));
    for (const condition of conditions) {
      const items = manifest.items.filter(r => pairs.get(r.id)?.condition === condition);
      if (items.length !== 409 || new Set(items.map(r => pairs.get(r.id).base_id)).size !== 409 ||
          items.some(r=>!originals.has(pairs.get(r.id).base_id)))
        throw new Error('Incomplete paired condition.');
      const calculate = rows => scorer.score(new Map(rows.map(r => [r.id, predictions.get(r.id)])), {...manifest, items:rows});
      const clean = items.filter(r => pairs.get(r.id).draft_correct);
      const erroneous = items.filter(r => !pairs.get(r.id).draft_correct);
      groups[condition] = {all:calculate(items), original_draft_correct:calculate(clean), original_draft_error:calculate(erroneous)};
    }
    return {dataset:pairing.dataset, protocol:'ko-correction-v2', scope:'public_eval_development_only',
      unique_recordings:409, derived_audio_rows:1227, private_test_used:false, by_condition:groups};
  }
  const api = {score};
  if (typeof module !== 'undefined') module.exports = api;
  else globalThis.TYEStressScorer = api;
})();
