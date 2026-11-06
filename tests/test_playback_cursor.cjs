'use strict';
const assert=require('node:assert/strict');
const Cursor=require('../src/studio/static/playback-cursor.js');
const events=Array.from({length:10000},(_,i)=>({id:'n'+i,time:i/10,duration:i%7===0?10:.3}));
events.push({id:'n0',time:1001,duration:2});
const measures=Array.from({length:501},(_,i)=>({id:'m'+i,time:i*2}));
const cursor=new Cursor(events,measures);
for(const time of [0,.1,.3,1,10,500,999,1001,1002,1004,3,3.1,0,100]){
 const result=cursor.at(time);
 assert.deepEqual([...result.ids].sort(),[...new Set(events.filter(e=>e.time<=time&&e.time+e.duration>time).map(e=>e.id))].sort());
 assert.equal(result.measure,measures.filter(m=>m.time<=time).at(-1));
}
const start=performance.now();const sequential=new Cursor(events,measures);
for(let i=0;i<20000;i++)sequential.at(i/20);
console.log('Playhead seek/repeat/long-note checks passed; 20,000 updates over 10,000 events:',Math.round(performance.now()-start),'ms (lookup only, not browser rendering).');
