const {test}=require('node:test');
const assert=require('node:assert/strict');
const {rank}=require('../web/leaderboard-v2.js');
const entries=[['Copy',11.7663],['Whisper',6.1852],['Qwen',13.5399]].map(([baseline,cer])=>({baseline,split:'eval',metrics:{micro_cer:cer}}));
test('raw CER ties share ranks and Test does not receive local results',()=>{
  const rows=rank(entries,'eval',{micro_cer:11.7663});
  assert.deepEqual(rows.map(e=>e.rank),[1,2,2,4]);
  assert.equal(rows[2].local,true);
  assert.deepEqual(rank(entries,'test',{micro_cer:0}),[]);
  assert.equal(entries[0].baseline,'Copy');
});
test('display rounding cannot turn distinct scores into a shared rank',()=>{
  const rows=rank(entries,'eval',{micro_cer:6.18519});
  assert.equal(rows[0].local,true);
  assert.equal(rows[1].rank,2);
});
