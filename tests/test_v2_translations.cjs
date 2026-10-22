const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
test('participant v2 page has complete English translations and unique IDs',()=>{
 const html=fs.readFileSync('web/index.html','utf8');
 const script=fs.readFileSync('web/v2-app.js','utf8');
 const source=script.slice(script.indexOf('const english = ')+16,script.indexOf('  const korean')).trim().replace(/;$/,'');
 const en=vm.runInNewContext('('+source+')');
 for(const [,key] of html.matchAll(/data-t="([^"]+)"/g))assert.equal(typeof en[key],'string',key);
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(ids.length,new Set(ids).size);
 for(const [,anchor] of html.matchAll(/href="#([^"]+)"/g))assert.ok(ids.includes(anchor),anchor);
});
