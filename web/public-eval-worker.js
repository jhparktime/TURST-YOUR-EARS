/* Public references only. Participant files never leave the browser. */
if (!self.TYEScorer) importScripts("scorer.js");
self.onmessage = ({data}) => {
  try {
    const text = new TextDecoder("utf-8", {fatal:true}).decode(data.csv);
    const result = TYEScorer.score(TYEScorer.parseCSV(text), data.manifest);
    self.postMessage({result});
  } catch (error) {
    self.postMessage({error: error instanceof TypeError ? "Upload a valid UTF-8 CSV file." : error.message});
  }
};
