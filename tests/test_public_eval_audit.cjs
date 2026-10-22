// Pure state-machine unit tests, without a browser or human review records.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

function worksheet(){
  const template=fs.readFileSync(path.join(__dirname,'../scripts/templates/public_eval_audit.html'),'utf8');
  const script=template.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  const elements=new Map(),store=new Map();
  function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,disabled:false,hidden:false,
    textContent:'',children:[],listeners:{},append(o){this.children.push(o)},
    addEventListener(name,fn){this.listeners[name]=fn},click(){this.onclick?.()}});return elements.get(id)}
  element('audit-data').textContent=JSON.stringify({audit_id:'UNIT_TEST_ONLY',plan_sha256:'TEST_HASH',
    items:Array.from({length:40},(_,i)=>({id:`A${String(i+1).padStart(3,'0')}`,draft:'초안',audio:'data:audio/wav;base64,AAAA'}))});
  const context={document:{getElementById:element,createElement:()=>element(Symbol())},
    localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},
    console,Blob,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},setTimeout:()=>{}};
  let browserStatus='';Object.defineProperty(context,'status',{get:()=>browserStatus,set:v=>{browserStatus=String(v)},configurable:true});
  vm.runInNewContext(script,context);
  assert.equal(browserStatus,''); // browser Window.status must never be overwritten
  return {el:element,store};
}

test('no draft before a played, independent audio-first transcription is locked',()=>{
  const {el}=worksheet();
  assert.equal(el('stage2').hidden,true);assert.equal(el('draft').textContent,'');
  el('heard').value='독립 전사';el('lock').onclick();
  assert.equal(el('stage2').hidden,true);
  el('reviewer').value='UNIT_TEST_ONLY';el('independent').checked=true;el('lock').onclick();
  assert.equal(el('stage2').hidden,true);
  el('player').currentTime=1;el('player').listeners.timeupdate();el('lock').onclick();
  assert.equal(el('stage2').hidden,false);assert.equal(el('draft').textContent,'초안');
  assert.equal(el('heard').disabled,true);assert.equal(el('lock').disabled,true);
});

test('dropdown changes the sentence identity and audio for every index',()=>{
  const {el}=worksheet();
  assert.equal(el('utterance').children.length,40);
  for(let i=0;i<40;i++){
    el('utterance').value=String(i);el('utterance').onchange();
    assert.equal(el('identity').textContent,`${i+1}/40 · A${String(i+1).padStart(3,'0')}`);
    assert.equal(el('stage2').hidden,true);
  }
});

test('audio-needed requires a cue; a new item remains hidden and cannot reuse play state',()=>{
  const {el,store}=worksheet();
  el('reviewer').value='UNIT_TEST_ONLY';el('independent').checked=true;
  el('heard').value='독립 전사';el('player').currentTime=1;el('player').listeners.timeupdate();el('lock').onclick();
  el('errorStatus').value='genuine_asr_error';el('audioNeeded').value='yes';el('save').onclick();
  assert.equal(Object.keys(JSON.parse([...store.values()][0]).saved).length,0);
  el('evidence').value='unit-test cue';el('save').onclick();
  const saved=JSON.parse([...store.values()][0]).saved;
  assert.equal(saved.A001.heard_text_before_draft,'독립 전사');
  el('next').onclick();assert.equal(el('stage2').hidden,true);assert.equal(el('draft').textContent,'');
  el('heard').value='다음 전사';el('lock').onclick();assert.equal(el('stage2').hidden,true);
});
