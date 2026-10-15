/* Browser implementation of frozen ko-correction-v1 for PUBLIC eval only.
 * Release manifests are validated by server.scoring before being packaged.
 * Python/browser parity is checked in tests/test_browser_scoring.py.
 */
(() => {
  const VERSION = "ko-correction-v1";
  const CONDITIONS = ["clean", "single", "multiple"];
  const ignored = new Set(Array.from(',!?;:"\'“”‘’()[]{}<>，！？。…·'));
  const whitespace = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/gu;
  // Generated from Python str.isdigit(), covering non-ASCII decimal spellings.
  const digits = new Set(Array.from("0123456789²³¹٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹߀߁߂߃߄߅߆߇߈߉०१२३४५६७८९০১২৩৪৫৬৭৮৯੦੧੨੩੪੫੬੭੮੯૦૧૨૩૪૫૬૭૮૯୦୧୨୩୪୫୬୭୮୯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯೦೧೨೩೪೫೬೭೮೯൦൧൨൩൪൫൬൭൮൯෦෧෨෩෪෫෬෭෮෯๐๑๒๓๔๕๖๗๘๙໐໑໒໓໔໕໖໗໘໙༠༡༢༣༤༥༦༧༨༩၀၁၂၃၄၅၆၇၈၉႐႑႒႓႔႕႖႗႘႙፩፪፫፬፭፮፯፰፱០១២៣៤៥៦៧៨៩᠐᠑᠒᠓᠔᠕᠖᠗᠘᠙᥆᥇᥈᥉᥊᥋᥌᥍᥎᥏᧐᧑᧒᧓᧔᧕᧖᧗᧘᧙᧚᪀᪁᪂᪃᪄᪅᪆᪇᪈᪉᪐᪑᪒᪓᪔᪕᪖᪗᪘᪙᭐᭑᭒᭓᭔᭕᭖᭗᭘᭙᮰᮱᮲᮳᮴᮵᮶᮷᮸᮹᱀᱁᱂᱃᱄᱅᱆᱇᱈᱉᱐᱑᱒᱓᱔᱕᱖᱗᱘᱙⁰⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉①②③④⑤⑥⑦⑧⑨⑴⑵⑶⑷⑸⑹⑺⑻⑼⒈⒉⒊⒋⒌⒍⒎⒏⒐⓪⓵⓶⓷⓸⓹⓺⓻⓼⓽⓿❶❷❸❹❺❻❼❽❾➀➁➂➃➄➅➆➇➈➊➋➌➍➎➏➐➑➒꘠꘡꘢꘣꘤꘥꘦꘧꘨꘩꣐꣑꣒꣓꣔꣕꣖꣗꣘꣙꤀꤁꤂꤃꤄꤅꤆꤇꤈꤉꧐꧑꧒꧓꧔꧕꧖꧗꧘꧙꧰꧱꧲꧳꧴꧵꧶꧷꧸꧹꩐꩑꩒꩓꩔꩕꩖꩗꩘꩙꯰꯱꯲꯳꯴꯵꯶꯷꯸꯹０１２３４５６７８９𐒠𐒡𐒢𐒣𐒤𐒥𐒦𐒧𐒨𐒩𐩀𐩁𐩂𐩃𐴰𐴱𐴲𐴳𐴴𐴵𐴶𐴷𐴸𐴹𐵀𐵁𐵂𐵃𐵄𐵅𐵆𐵇𐵈𐵉𐹠𐹡𐹢𐹣𐹤𐹥𐹦𐹧𐹨𑁒𑁓𑁔𑁕𑁖𑁗𑁘𑁙𑁚𑁦𑁧𑁨𑁩𑁪𑁫𑁬𑁭𑁮𑁯𑃰𑃱𑃲𑃳𑃴𑃵𑃶𑃷𑃸𑃹𑄶𑄷𑄸𑄹𑄺𑄻𑄼𑄽𑄾𑄿𑇐𑇑𑇒𑇓𑇔𑇕𑇖𑇗𑇘𑇙𑋰𑋱𑋲𑋳𑋴𑋵𑋶𑋷𑋸𑋹𑑐𑑑𑑒𑑓𑑔𑑕𑑖𑑗𑑘𑑙𑓐𑓑𑓒𑓓𑓔𑓕𑓖𑓗𑓘𑓙𑙐𑙑𑙒𑙓𑙔𑙕𑙖𑙗𑙘𑙙𑛀𑛁𑛂𑛃𑛄𑛅𑛆𑛇𑛈𑛉𑛐𑛑𑛒𑛓𑛔𑛕𑛖𑛗𑛘𑛙𑛚𑛛𑛜𑛝𑛞𑛟𑛠𑛡𑛢𑛣𑜰𑜱𑜲𑜳𑜴𑜵𑜶𑜷𑜸𑜹𑣠𑣡𑣢𑣣𑣤𑣥𑣦𑣧𑣨𑣩𑥐𑥑𑥒𑥓𑥔𑥕𑥖𑥗𑥘𑥙𑯰𑯱𑯲𑯳𑯴𑯵𑯶𑯷𑯸𑯹𑱐𑱑𑱒𑱓𑱔𑱕𑱖𑱗𑱘𑱙𑵐𑵑𑵒𑵓𑵔𑵕𑵖𑵗𑵘𑵙𑶠𑶡𑶢𑶣𑶤𑶥𑶦𑶧𑶨𑶩𑽐𑽑𑽒𑽓𑽔𑽕𑽖𑽗𑽘𑽙𖄰𖄱𖄲𖄳𖄴𖄵𖄶𖄷𖄸𖄹𖩠𖩡𖩢𖩣𖩤𖩥𖩦𖩧𖩨𖩩𖫀𖫁𖫂𖫃𖫄𖫅𖫆𖫇𖫈𖫉𖭐𖭑𖭒𖭓𖭔𖭕𖭖𖭗𖭘𖭙𖵰𖵱𖵲𖵳𖵴𖵵𖵶𖵷𖵸𖵹𜳰𜳱𜳲𜳳𜳴𜳵𜳶𜳷𜳸𜳹𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿𞅀𞅁𞅂𞅃𞅄𞅅𞅆𞅇𞅈𞅉𞋰𞋱𞋲𞋳𞋴𞋵𞋶𞋷𞋸𞋹𞓰𞓱𞓲𞓳𞓴𞓵𞓶𞓷𞓸𞓹𞗱𞗲𞗳𞗴𞗵𞗶𞗷𞗸𞗹𞗺𞥐𞥑𞥒𞥓𞥔𞥕𞥖𞥗𞥘𞥙🄀🄁🄂🄃🄄🄅🄆🄇🄈🄉🄊🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹"));
  const chars = (s) => Array.from(s);
  function normalize(text) {
    const value = chars(text.normalize("NFC").toLowerCase().replace(whitespace, ""));
    return value.filter((c, i) => !ignored.has(c) && (c !== "." ||
      (i > 0 && i + 1 < value.length && digits.has(value[i-1]) && digits.has(value[i+1])))).join("");
  }
  const words = (text) => text.split(whitespace).map(normalize).filter(Boolean);
  function distance(left, right) {
    const a = typeof left === "string" ? chars(left) : left;
    const b = typeof right === "string" ? chars(right) : right;
    let previous = Array.from({length: b.length + 1}, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const row = [i];
      for (let j = 1; j <= b.length; j++) row[j] = Math.min(row[j-1]+1,
        previous[j]+1, previous[j-1]+Number(a[i-1] !== b[j-1]));
      previous = row;
    }
    return previous[b.length];
  }
  function alignment(reference, hypothesis) {
    const a = chars(reference), b = chars(hypothesis);
    const matrix = [Int32Array.from({length: b.length + 1}, (_, i) => i)];
    for (let i = 1; i <= a.length; i++) {
      const row = new Int32Array(b.length + 1); row[0] = i;
      for (let j = 1; j <= b.length; j++) row[j] = Math.min(row[j-1]+1,
        matrix[i-1][j]+1, matrix[i-1][j-1]+Number(a[i-1] !== b[j-1]));
      matrix.push(row);
    }
    const values = Array(a.length).fill(""), inserted = Array(a.length+1).fill("");
    let i = a.length, j = b.length;
    while (i || j) {
      if (i && j && matrix[i][j] === matrix[i-1][j-1]+Number(a[i-1] !== b[j-1])) {
        values[i-1] = b[j-1]; i--; j--;
      } else if (i && matrix[i][j] === matrix[i-1][j]+1) i--;
      else { inserted[i] = b[j-1] + inserted[i]; j--; }
    }
    return [values.map((c, k) => c+inserted[k+1]), inserted[0], matrix[a.length][b.length]];
  }
  function corruption(row) {
    const raw = chars(row.reference), spans = [];
    let cursor = 0, size = 0;
    for (const edit of row.edits) {
      size += chars(normalize(raw.slice(cursor, edit.start).join(""))).length;
      const length = chars(normalize(raw.slice(edit.start, edit.end).join(""))).length;
      spans.push([size, size+length]); size += length; cursor = edit.end;
    }
    return spans;
  }
  function parseCSV(text) {
    if (new TextEncoder().encode(text).length > 2*1024*1024) throw new Error("Maximum submission size is 2 MiB.");
    text = text.replace(/^\uFEFF/, "");
    const rows = []; let row = [], field = "", quoted = false, closed = false, started = false;
    function endField() { row.push(field); field = ""; closed = false; started = false; }
    function endRow() { if (!started && !row.length && !field) { if (!rows.length) rows.push([]); return; }
      endField(); rows.push(row); row = []; }
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"') {
          if (text[i+1] === '"') { field += '"'; i++; } else { quoted = false; closed = true; }
        } else field += c;
      } else if (c === ",") endField();
      else if (c === "\n" || c === "\r") { endRow(); if (c === "\r" && text[i+1] === "\n") i++; }
      else if (closed) throw new Error("Upload a valid UTF-8 CSV file.");
      else if (c === '"' && !started && !field) { quoted = true; started = true; }
      else { field += c; started = true; }
    }
    if (quoted) throw new Error("Upload a valid UTF-8 CSV file.");
    if (started || row.length || field) endRow();
    const header = rows.shift();
    if (!header || header.length !== 2 || header[0] !== "id" || header[1] !== "prediction")
      throw new Error("CSV header must be exactly: id,prediction.");
    const predictions = new Map();
    for (const cells of rows) {
      if (cells.length !== 2) throw new Error("Every row must have exactly two CSV fields.");
      const id = cells[0].replace(new RegExp(`^${whitespace.source}+|${whitespace.source}+$`, "gu"), "");
      if (!id || predictions.has(id)) throw new Error("IDs must be non-empty and unique.");
      if (chars(id).length > 120 || chars(cells[1]).length > 4000) throw new Error("An ID or prediction exceeds the size limit.");
      predictions.set(id, cells[1]);
      if (predictions.size > 20000) throw new Error("Too many rows.");
    }
    if (!predictions.size) throw new Error("The submission is empty.");
    return predictions;
  }
  const rate = (n, d) => d ? 100*n/d : null;
  const counter = () => ({errors:0, draft_errors:0, characters:0, word_errors:0, words:0,
    utterances:0, restored:0, edit_total:0, harmed:0, preserved_total:0, clean_changed:0, clean_total:0});
  function metrics(b) {
    return {...b, cer:rate(b.errors,b.characters), draft_cer:rate(b.draft_errors,b.characters),
      cer_improvement_pp:rate(b.draft_errors-b.errors,b.characters), wer:rate(b.word_errors,b.words),
      restoration_rate:rate(b.restored,b.edit_total), harmful_edit_rate:rate(b.harmed,b.preserved_total),
      clean_change_rate:rate(b.clean_changed,b.clean_total)};
  }
  function score(predictions, manifest) {
    if (manifest.protocol !== VERSION || !manifest.items?.length ||
        CONDITIONS.some(c => !manifest.conditions.includes(c))) throw new Error("Unsupported evaluation manifest.");
    const refs = manifest.items;
    if (new Set(refs.map(r => r.id)).size !== refs.length || predictions.size !== refs.length ||
        refs.some(r => !predictions.has(r.id))) throw new Error("Submission IDs must exactly match this evaluation set (no missing or extra IDs).");
    const groups = Object.fromEntries(CONDITIONS.map(c => [c, counter()]));
    let cells = 0;
    for (const row of refs) {
      const reference = normalize(row.reference), hypothesis = normalize(predictions.get(row.id)), draft = normalize(row.draft);
      const a = chars(reference), b = chars(hypothesis), d = chars(draft);
      const rw = words(row.reference), hw = words(predictions.get(row.id));
      cells += (a.length+1)*(b.length+1)+(a.length+1)*(d.length+1)+(rw.length+1)*(hw.length+1);
      if (cells > 40000000) throw new Error("Submission exceeds the scorer computation limit. Contact the organizers.");
      const spans = corruption(row), bucket = groups[row.condition];
      const [draftAligned, draftLeading, draftErrors] = alignment(reference, draft);
      const covered = new Set(spans.flatMap(([start,end]) => Array.from({length:end-start}, (_,k) => start+k)));
      let bad = a.some((c,k) => !covered.has(k) && draftAligned[k] !== c);
      spans.forEach(([start,end],k) => {
        const found = (start === 0 ? draftLeading : "") + draftAligned.slice(start,end).join("");
        bad ||= found !== normalize(row.edits[k].replacement);
      });
      bad ||= Boolean(draftLeading) && (!spans.length || spans[0][0] !== 0);
      if (bad) throw new Error("Ambiguous reference-to-draft alignment; revise the corruption spans or exclude the sample.");
      const [aligned, leading, errors] = alignment(reference, hypothesis);
      bucket.errors += errors; bucket.draft_errors += draftErrors; bucket.characters += a.length;
      bucket.word_errors += distance(rw,hw); bucket.words += rw.length; bucket.utterances++;
      for (const [start,end] of spans) {
        const value = (start === 0 ? leading : "") + aligned.slice(start,end).join("");
        bucket.restored += Number(value === a.slice(start,end).join("")); bucket.edit_total++;
      }
      a.forEach((c,k) => { if (!covered.has(k)) {
        bucket.preserved_total++; bucket.harmed += Number((k === 0 ? leading : "")+aligned[k] !== c);
      }});
      if (!spans.length) { bucket.clean_total++; bucket.clean_changed += Number(hypothesis !== reference); }
    }
    const conditions = Object.fromEntries(CONDITIONS.map(c => [c,metrics(groups[c])]));
    const totals = counter();
    for (const key of Object.keys(totals)) totals[key] = CONDITIONS.reduce((s,c) => s+groups[c][key],0);
    const aggregate = metrics(totals);
    const macro = CONDITIONS.reduce((s,c) => s+conditions[c].cer,0)/3;
    const draftMacro = CONDITIONS.reduce((s,c) => s+conditions[c].draft_cer,0)/3;
    const result = {scorer:VERSION, primary_metric:"macro_cer", macro_cer:macro, draft_macro_cer:draftMacro,
      cer_improvement_pp:draftMacro-macro, micro_cer:aggregate.cer, micro_wer:aggregate.wer,
      worst_cer:Math.max(...CONDITIONS.map(c => conditions[c].cer)), conditions, utterances:refs.length};
    for (const key of ["restoration_rate","restored","edit_total","harmful_edit_rate","harmed",
      "preserved_total","clean_change_rate","clean_changed","clean_total"]) result[key] = aggregate[key];
    return result;
  }
  const api = {VERSION, normalize, distance, alignment, parseCSV, score};
  if (typeof module !== "undefined") module.exports = api;
  else globalThis.TYEScorer = api;
})();
