const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync('src/studio/static/app.js','utf8');
const state={
  score:{duration:8,events:[{time:1,duration:2},{time:3,duration:2},{time:4,duration:1}]},
  loop:{start:2,end:4},speed:1,audio:{currentTime:4.01},started:0,playing:true,eventIndex:2
};
const played=[];
const ctx=vm.createContext({state,playEvent:e=>played.push(e)});
for(const name of ['position','beginPass','schedule']){
  const start=code.indexOf('function '+name+'(');
  vm.runInContext(code.slice(start,code.indexOf('\n}',start)+2).split('\nasync function')[0],ctx);
}
vm.runInContext('schedule()',ctx);
assert.equal(state.position,2);
assert.equal(played[0].time,2);
assert.equal(played[0].duration,1);
state.audio.currentTime+=1.99;
vm.runInContext('schedule()',ctx);
assert.deepEqual(played.map(e=>e.time),[2,3]);
console.log('Loop wraps, resumes held notes and excludes the next bar.');
