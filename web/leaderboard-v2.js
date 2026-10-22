/* Rank raw CER values, retaining exact ties and separating splits. */
(function(root){
  function rank(entries, split, local){
    const rows=entries.filter(e=>e.split===split).map(e=>({...e}));
    if(local&&split==='eval')rows.push({baseline:'local',split,metrics:local,local:true});
    rows.sort((a,b)=>a.metrics.micro_cer-b.metrics.micro_cer||Number(!!a.local)-Number(!!b.local)||a.baseline.localeCompare(b.baseline));
    let previous,position=0;
    return rows.map((entry,index)=>{if(entry.metrics.micro_cer!==previous){position=index+1;previous=entry.metrics.micro_cer}return {...entry,rank:position}});
  }
  root.TYELeaderboard={rank};
  if(typeof module!=='undefined')module.exports={rank};
})(typeof window==='undefined'?globalThis:window);
