const {test}=require('node:test'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const {historyStore,makePackage,KEY}=require('../web/public-results-v2.js');
test('local history survives a new store instance, separates versions and keeps the latest 20',()=>{
 const memory=new Map(),storage={getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)};
 let store=historyStore(storage,'version1');
 for(let i=0;i<23;i++)store.append({utterances:409,micro_cer:i},'local','file'+i);
 const rows=historyStore(storage,'version1').read();assert.equal(rows.length,20);assert.equal(rows[0].name,'file3');
 assert.equal(rows.at(-1).metrics.micro_cer,22);assert.equal(historyStore(storage,'version2').read().length,0);
 memory.set(KEY,'bad json');assert.deepEqual(store.read(),[]);
});
test('storage refusal is reported to the caller and invalid metrics are not saved',()=>{
 const store=historyStore({getItem:()=>null,setItem:()=>{throw Error('denied')}},'v');
 assert.throws(()=>store.append({utterances:409,micro_cer:2},'local','file'),/denied/);
 assert.throws(()=>store.append({utterances:408,micro_cer:2},'local','file'),/Invalid/);
});
test('submission package preserves Korean CSV bytes, checksum and explicit consent',async()=>{
 const data='id,prediction\na,한국어 "전사"\n';
 const options={team:'team03',method:'Copy',code_url:'https://github.com/jhparktime/TURST-YOUR-EARS',version:'test-version',consent:true};
 const packet=JSON.parse(await makePackage(new Blob([data]),options));
 assert.equal(zlib.gunzipSync(Buffer.from(packet.csv,'base64')).toString('utf8'),data);
 assert.equal(packet.csv_sha256,require('node:crypto').createHash('sha256').update(data).digest('hex'));
 assert.equal(packet.manifest_sha256,'test-version');
 await assert.rejects(makePackage(new Blob([data]),{...options,consent:false}),/consent/);
 await assert.rejects(makePackage(new Blob([data]),{...options,code_url:'javascript:alert(1)'}),/fields/);
});
