/* Locally bundled FluidR3 GM samples; see sounds/LICENSE.txt. */
window.StudioSamples = (() => {
  const banks = new Map(), pending = new Map();
  const sampleKey = pitch => Math.max(21,Math.min(108,Math.round(pitch)));
  async function load(ctx,name,pitches=[60]) {
    if(!banks.has(name))banks.set(name,new Map());
    const bank=banks.get(name),keys=[...new Set(pitches.map(sampleKey))];
    // Four workers per requested instrument; duplicate requests share a decode.
    let index=0;
    await Promise.all(Array.from({length:Math.min(4,keys.length)},async()=>{
      while(index<keys.length){
        const key=keys[index++],id=name+':'+key;if(bank.has(key))continue;
        if(!pending.has(id))pending.set(id,(async()=>{
          const response=await fetch(`/sounds/${name}/${key}.mp3`);
          if(!response.ok)throw new Error(`Cannot load ${name} note ${key}.`);
          bank.set(key,await ctx.decodeAudioData(await response.arrayBuffer()));
        })().finally(()=>pending.delete(id)));
        await pending.get(id);
      }
    }));
  }
  function play(ctx,master,nodes,pitch,duration,start,name,volume) {
    const bank=banks.get(name);if(!bank)throw new Error(`${name} is still loading.`);
    const key=sampleKey(pitch);
    if(!bank.has(key))throw new Error(`${name} note ${key} is still loading.`);
    const source=ctx.createBufferSource(),gain=ctx.createGain();
    source.buffer=bank.get(key);source.playbackRate.value=2**((pitch-key)/12);
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(volume*.65,start+.008);
    const end=start+Math.max(.03,duration);gain.gain.setValueAtTime(volume*.65,end);
    gain.gain.linearRampToValueAtTime(0,end+.12);
    source.connect(gain);gain.connect(master);nodes.add(source);
    source.onended=()=>{nodes.delete(source);source.disconnect();gain.disconnect();};
    source.start(start);source.stop(end+.13);
  }
  return {load,play};
})();
