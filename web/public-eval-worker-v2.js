/* PUBLIC references only; the participant CSV never leaves the browser. */
if (!self.TYEScorerV2) importScripts('scorer.js', 'scorer-v2.js');
self.onmessage = ({data}) => {
  try {
    const text = new TextDecoder('utf-8', {fatal:true}).decode(data.csv);
    const result = TYEScorerV2.score(TYEScorerV2.parseCSV(text),data.manifest);
    self.postMessage({result});
  } catch (error) {
    self.postMessage({error:error instanceof TypeError ? 'Upload a valid UTF-8 CSV file.' : error.message});
  }
};
