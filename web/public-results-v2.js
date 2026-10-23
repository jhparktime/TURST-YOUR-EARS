/* Public Eval history and bounded, portable submission packages. */
(function(root){
  const KEY='tye-public-eval-history-v1', LIMIT=20;
  function valid(row,version){return row&&row.version===version&&row.metrics?.utterances===409&&Number.isFinite(row.metrics.micro_cer)&&row.metrics.micro_cer>=0&&typeof row.name==='string'&&typeof row.at==='string'}
  function historyStore(storage,version){
    function read(){try{const value=JSON.parse(storage.getItem(KEY)||'[]');return Array.isArray(value)?value.filter(r=>valid(r,version)).slice(-LIMIT):[]}catch{return []}}
    return {read,append(metrics,kind,name,at=new Date().toISOString()){
      if(!valid({version,metrics,name,at},version))throw new Error('Invalid Eval result.');
      const rows=read();rows.push({version,metrics,kind,name,at});const kept=rows.slice(-LIMIT);
      storage.setItem(KEY,JSON.stringify(kept));return kept;
    }};
  }
  async function digest(bytes){return [...new Uint8Array(await root.crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('')}
  async function makePackage(file,{team,method,code_url,version,consent}){
    if(!consent)throw new Error('consent');
    if(!team.trim()||team.trim().length>60||!method.trim()||method.trim().length>160||code_url.length>300)throw new Error('fields');
    let url;try{url=new URL(code_url)}catch{throw new Error('fields')}
    if(url.protocol!=='https:'||url.username||url.password)throw new Error('fields');
    if(!file||file.size>2*1024*1024)throw new Error('size');
    const bytes=await file.arrayBuffer();
    const compressed=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
    let binary='';for(const n of compressed)binary+=String.fromCharCode(n);
    const packet={format:'tye-public-submission-v1',manifest_sha256:version,team:team.trim(),method:method.trim(),code_url:url.href,consent:true,encoding:'gzip+base64',csv_sha256:await digest(bytes),csv:btoa(binary)};
    const text=JSON.stringify(packet);
    if(text.length>60000)throw new Error('size');
    return text;
  }
  root.TYEPublicResults={historyStore,makePackage,KEY};
  if(typeof module!=='undefined')module.exports=root.TYEPublicResults;
})(typeof window==='undefined'?globalThis:window);
