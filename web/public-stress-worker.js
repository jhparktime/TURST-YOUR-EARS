importScripts('scorer.js','scorer-v2.js','stress-scorer.js');
self.onmessage = ({data}) => {
  try {
    const text = new TextDecoder('utf-8',{fatal:true}).decode(data.csv);
    self.postMessage({result:TYEStressScorer.score(TYEScorerV2.parseCSV(text),data.manifest,data.pairing)});
  } catch (error) {
    self.postMessage({error:error instanceof TypeError ? 'Upload a valid UTF-8 CSV.' : error.message});
  }
};
