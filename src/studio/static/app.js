"use strict";
const $ = (id) => document.getElementById(id);
const state = {token:"", library:[], score:null, view:"read", selected:null, group:null, mixer:[],
  playing:false, position:0, started:0, speed:1, eventIndex:0, timer:null, audio:null, master:null,
  nodes:new Set(), metronome:false, metroNext:0, metroCount:0, scrollStart:null, scrollOrigin:0,
  currentMeasure:0, saving:Promise.resolve(), openGeneration:0};
const sounds = ["Piano", "Flute", "Strings", "Organ", "Bell"];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const time = s => `${Math.floor(Math.max(0,s)/60)}:${String(Math.floor(Math.max(0,s)%60)).padStart(2,"0")}`;
let toastTimer;
function toast(message, error=false) { $("toast").textContent=message; $("toast").classList.toggle("error",error); $("toast").hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$("toast").hidden=true,error?10000:4000); }
function busy(value, text="Opening score…") { $("busy-text").textContent=text; $("busy").hidden=!value; }
async function api(path, data) {
  const response = await fetch(path, data===undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json","X-Studio-Token":state.token},body:JSON.stringify(data)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || "Something went wrong. Please try again.");
  return result;
}
function run(fn) { return async (...args) => { try { await fn(...args); } catch(e) { busy(false); toast(e.message,true); } }; }
function on(id, event, fn) { $(id).addEventListener(event,run(fn)); }
async function library() {
  const result = await api("/api/library"); state.library=result.scores; state.scanner=result.scanner;syncScanJobs(result.scanJobs||[]);
  $("score-count").textContent=state.library.filter(s=>!s.trashed).length;
  renderLibrary();
}
function filteredScores() { const q=$("search").value.toLowerCase();return state.library.filter(s=>!!s.trashed===!!state.trash && (!state.group || s.group===state.group) && `${s.title} ${s.composer} ${s.group}`.toLowerCase().includes(q)); }
function renderLibrary() {
  const groups=[...new Set(state.library.filter(s=>!s.trashed).map(s=>s.group).filter(Boolean))].sort();
  $("groups").innerHTML=groups.map(g=>`<button class="group-item ${state.group===g?"selected":""}" data-group="${esc(g)}"><span class="group-dot"></span>${esc(g)}<span>${state.library.filter(s=>!s.trashed && s.group===g).length}</span></button>`).join("");
  $("groups").querySelectorAll("button").forEach(b=>b.onclick=()=>{state.trash=false;state.group=b.dataset.group;showLibrary();renderLibrary();});
  const list=filteredScores();
  $("score-list").innerHTML=list.map(s=>`<button class="score-link ${state.score?.id===s.id?"selected":""}" data-score="${s.id}"><strong>${esc(s.title)}</strong><small>${esc(s.group)} · ${s.origin==="Composition"?"Composition":s.reviewed?"Reviewed":"To review"}</small></button>`).join("") || '<p class="empty-hint">No scores here yet.</p>';
  $("library-cards").innerHTML=list.map(s=>`<button class="score-card" data-score="${s.id}"><div class="card-art" aria-hidden="true">𝄞 ♩ ♫</div><div class="card-content"><strong>${esc(s.title)}</strong><small>${esc(s.group)} · ${esc(s.origin)}${s.reviewed?" · Reviewed":""}</small></div></button>`).join("") || '<p class="empty-hint">Import a score or start a new composition to fill this space.</p>';
  document.querySelectorAll("[data-score]").forEach(b=>{
    const id=b.dataset.score, wrapper=document.createElement('div');wrapper.className='score-item';b.replaceWith(wrapper);wrapper.appendChild(b);
    const menu=document.createElement('button');menu.className='score-more';menu.textContent='⋯';menu.setAttribute('aria-label','Actions for '+state.library.find(s=>s.id===id).title);menu.setAttribute('aria-haspopup','menu');wrapper.appendChild(menu);
    menu.onclick=e=>{e.stopPropagation();openScoreMenu(id,menu.getBoundingClientRect().left,menu.getBoundingClientRect().bottom);};
    wrapper.oncontextmenu=e=>{e.preventDefault();openScoreMenu(id,e.clientX,e.clientY);};
    b.onclick=run(()=>state.trash?openScoreMenu(id,menu.getBoundingClientRect().left,menu.getBoundingClientRect().bottom):openScore(id));
    b.onkeydown=e=>{if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();menu.click();}};
  });
}
function showLibrary() { pause();$("score-view").hidden=true;$("library-view").hidden=false;$("breadcrumb").textContent="Score library";document.body.dataset.page="library";toggleKeyboard(false); }
function safeSvg(svg) {
  const doc=new DOMParser().parseFromString(svg,"image/svg+xml");
  doc.querySelectorAll("script,foreignObject,iframe,image,a").forEach(n=>n.remove());
  for(const n of doc.querySelectorAll("*")) for(const a of [...n.attributes]) {
    if(a.name.startsWith("on") || ((a.localName==="href") && !a.value.startsWith("#"))) n.removeAttributeNode(a);
  }
  return document.importNode(doc.documentElement,true);
}
async function openScore(id, preserve=false) {
  if(mixSave) {clearTimeout(mixSave);mixSave=null;if(state.score)await queueMeta({mixer:structuredClone(state.mixer)});}
  await state.saving;
  const generation=++state.openGeneration;
  pause();state.scrollStart=null;$("scroll-only").textContent="▷ Scroll without sound";
  const oldPosition=preserve?state.position:0, oldScroll=preserve?$("score-scroll").scrollTop:0;
  busy(true,"Engraving your score…");
  const result=await api(`/api/score/${id}?mode=${$("solfa-mode").value}&minor=${$("minor-do").checked}&solfa=${$("solfa").checked}`);
  if(generation!==state.openGeneration)return;
  state.score=result;
  $("reader-format").querySelectorAll("option").forEach(o=>{if(o.value!=="notation")o.disabled=result.sourceType!=="application/pdf";});
  $("reader-format").value=result.sourceType==="application/pdf"?"compare":"notation";state.position=Math.min(oldPosition,result.duration);state.selected=null;
  state.mixer=result.parts.map((p,i)=>({...{sounds:["Piano"],volume:.7,mute:false,solo:false},...(result.meta.mixer?.[i]||{})}));
  if(!preserve) {
    const practice=result.meta.practice||{};
    $("tempo").value=practice.tempo||Math.round(result.baseTempo); state.currentMeasure=0;
    $("follow").checked=practice.follow??true;$("scroll-mode").value=practice.scrollMode||"score";
    $("scroll-duration").value=practice.scrollDuration||120;$("scroll-duration-field").hidden=$("scroll-mode").value!=="timed";
  }
  state.speed=Number($("tempo").value)/result.baseTempo;
  $("score-title").textContent=result.title;$("score-eyebrow").textContent=result.meta.group || "UNGROUPED";
  $("score-subtitle").textContent=[result.composer,`${result.parts.length} parts`,`${result.parts[0]?.measures.length||0} bars`,`${result.pages.length} ${result.pages.length===1?"page":"pages"}`].filter(Boolean).join("  ·  ");
  $("breadcrumb").textContent="Score reader";$("library-view").hidden=true;$("score-view").hidden=false;
  $("scan-banner").hidden=result.meta.reviewed || (result.meta.origin!=="Scan" && !result.issues.length);
  $("scan-banner").textContent=result.issues.length?`${result.issues.length} notation checks need attention. Open “Check score” before relying on playback.`:"Recognition is a first draft. Compare the scan, correct notes, then mark it reviewed.";
  const pageContainers=result.pages.map(()=>{const el=document.createElement('div');el.className='score-page';el.style.minHeight='400px';return el;});
  $("pages").replaceChildren(...pageContainers);
  function mountPage(i){
    if(generation!==state.openGeneration)return;
    const container=pageContainers[i];container.appendChild(safeSvg(result.pages[i]));container.style.minHeight='';
    const number=document.createElement('div');number.className='page-number';number.textContent=`${i+1} / ${result.pages.length}`;container.appendChild(number);
    container.querySelectorAll('.measure[id^="ss-measure-"]').forEach(measure=>{
      const box=measure.getBBox(), marker=document.createElementNS('http://www.w3.org/2000/svg','rect');
      for(const [key,value] of Object.entries({x:box.x-12,y:box.y-12,width:box.width+24,height:box.height+24,rx:12}))marker.setAttribute(key,String(value));
      marker.classList.add('playback-bar-marker');marker.setAttribute('aria-hidden','true');measure.insertBefore(marker,measure.firstChild);
    });
  container.querySelectorAll(".note,.rest,.mRest").forEach(note=>{
    if(!result.notes[note.id])return;
    note.setAttribute("tabindex","0");note.setAttribute("role","button");
    // SVG groups otherwise only respond on the thin painted note/stem paths.
    // Give the whole note a forgiving, transparent hit area for mouse/touch.
    const bounds=note.getBBox(), hit=document.createElementNS("http://www.w3.org/2000/svg","rect");
    for(const [key,value] of Object.entries({x:bounds.x-20,y:bounds.y-20,width:bounds.width+40,height:bounds.height+40,fill:"transparent","pointer-events":"all"}))hit.setAttribute(key,String(value));
    hit.setAttribute("aria-hidden","true");note.insertBefore(hit,note.firstChild);
    const n=result.notes[note.id];note.setAttribute("aria-label",`${result.parts[n.part].name}, bar ${n.measure+1}, ${n.rest?"rest":n.step+n.octave}`);
    note.addEventListener("click",()=>selectNote(note.id));note.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();selectNote(note.id);}});
  });
  }
  if(result.pages.length)mountPage(0);
  let nextPage=1;
  function mountLater(){if(generation!==state.openGeneration||nextPage>=result.pages.length)return;mountPage(nextPage++);(window.requestIdleCallback||requestAnimationFrame)(mountLater);}
  (window.requestIdleCallback||requestAnimationFrame)(mountLater);
  renderMixer();renderBookmarks();renderIssues();fillComposer();setView(state.view);updateTransport();
  $("reviewed").checked=!!result.meta.reviewed;$("source-btn").disabled=!result.hasSource;
  $("source-btn").textContent=result.hasSource?"View original scan ↗":"No scan attached · MusicXML source";
  $("apply-note").disabled=true;$("note-selection").textContent="Select a note on the score";
  $("score-scroll").scrollTop=oldScroll;renderLibrary();busy(false);await readerFormat();
}
function setView(view) {
  state.view=view;
  document.body.dataset.page=view;
  document.querySelector(".inspector").hidden=view==="read";
  $("breadcrumb").textContent={read:"Read",practice:"Practice",compose:"Compose",review:"Review"}[view];
  $("minor-do").closest("label").hidden=$("solfa-mode").value!=="movable";
  document.querySelectorAll("[data-view]").forEach(b=>{b.classList.toggle("active",b.dataset.view===view);b.setAttribute("aria-selected",String(b.dataset.view===view));});
  ["read","compose","review"].forEach(v=>$(v+"-panel").hidden=(v==="read" ? view!=="practice" : v!==view));
}
function selectNote(id) {
  const n=state.score.notes[id];if(!n)return;
  document.querySelectorAll(".selected-note").forEach(el=>el.classList.remove("selected-note"));
  $(id)?.classList.add("selected-note");state.selected=id;state.currentMeasure=n.measure;
  $("note-details").open=true;
  $("note-step").value=n.step;$("note-alter").value=n.alter;$("note-octave").value=n.octave;$("note-lyric").value=n.lyric;
  $("note-selection").textContent=`${state.score.parts[n.part].name} · bar ${n.measure+1} · ${n.duration} quarter beats`;
  $("apply-note").disabled=!n.pitched;$("compose-part").value=n.part;fillBars(n.measure);setView("compose");
}
function fillComposer() { $("compose-part").innerHTML=state.score.parts.map((p,i)=>`<option value="${i}">${esc(p.name)}</option>`).join("");fillBars(state.currentMeasure); }
function fillBars(index=0) {
  const p=state.score.parts[Number($("compose-part").value)||0];
  $("compose-bar").innerHTML=p.measures.map((m,i)=>`<option value="${i}">${esc(m.number)}</option>`).join("");
  $("compose-bar").value=Math.min(index,p.measures.length-1);updateCapacity();
}
function updateCapacity() {
  if(!state.score)return;const m=state.score.parts[Number($("compose-part").value)].measures[Number($("compose-bar").value)];
  $("bar-capacity").textContent=`${m.beats}/${m.beatType} · This bar needs ${m.length} quarter beats.`;
}
function renderMixer() {
  $("mixer").innerHTML=state.score.parts.map((p,i)=>{const m=state.mixer[i];return `<div class="mixer-part"><div class="mixer-part-title"><div class="part-title"><span class="part-badge">${esc(p.name.charAt(0))}</span>${esc(p.name)}</div><div class="mix-switches"><button class="${m.mute?"on":""}" data-mute="${i}" aria-pressed="${m.mute}" title="Mute ${esc(p.name)}">M</button><button class="${m.solo?"on":""}" data-solo="${i}" aria-pressed="${m.solo}" title="Solo ${esc(p.name)}">S</button></div></div><div class="sounds">${sounds.map(s=>`<button class="sound-chip ${m.sounds.includes(s)?"on":""}" data-sound="${s}" data-part="${i}" aria-pressed="${m.sounds.includes(s)}">${s}</button>`).join("")}</div><label class="mixer-volume">−<input type="range" value="${m.volume}" min="0" max="1" step="0.01" data-volume="${i}" aria-label="${esc(p.name)} volume">＋</label></div>`;}).join("");
  $("mixer").querySelectorAll("[data-sound]").forEach(b=>b.onclick=()=>{const m=state.mixer[+b.dataset.part];m.sounds=m.sounds.includes(b.dataset.sound)?m.sounds.filter(s=>s!==b.dataset.sound):[...m.sounds,b.dataset.sound];refreshMix();renderMixer();persistMixer();});
  for(const key of ["mute","solo"])$("mixer").querySelectorAll(`[data-${key}]`).forEach(b=>b.onclick=()=>{state.mixer[+b.dataset[key]][key]=!state.mixer[+b.dataset[key]][key];refreshMix();renderMixer();persistMixer();});
  $("mixer").querySelectorAll("[data-volume]").forEach(i=>{i.oninput=()=>state.mixer[+i.dataset.volume].volume=+i.value;i.onchange=()=>{refreshMix();persistMixer();};});
}
let mixSave;
function persistMixer() { clearTimeout(mixSave); const id=state.score.id, mixer=structuredClone(state.mixer);mixSave=setTimeout(()=>{mixSave=null;queueMeta({mixer},id);},350); }
function queueMeta(meta,id=state.score?.id) {
  state.saving=state.saving.then(async()=>{
    if(state.score?.id!==id)return;
    $("save-status").textContent="Saving…";
    const r=await api("/api/meta",{id,revision:state.score.revision,meta});
    if(state.score?.id===id){state.score.revision=r.revision;state.score.meta=r.meta;}
    $("save-status").textContent="● Saved locally";await library();
  }).catch(e=>{$("save-status").textContent="Not saved";toast(e.message,true);});
  return state.saving;
}
function savePractice() {
  if(!state.score)return;
  return queueMeta({practice:{tempo:+$("tempo").value,follow:$("follow").checked,scrollMode:$("scroll-mode").value,scrollDuration:+$("scroll-duration").value}});
}
async function edit(action,values,extra={}) {
  if(!state.score)return;
  pause();await state.saving;busy(true,"Saving and engraving…");
  const id=state.score.id;
  await api("/api/edit",{id,revision:state.score.revision,action,values,...extra});
  await library();await openScore(id,true);toast("Saved locally. Use Undo to restore the previous version.");
}
function renderBookmarks() {
  const bookmarks=state.score.meta.bookmarks||[];
  $("bookmarks").innerHTML=bookmarks.map((b,i)=>`<div class="bookmark-row"><button data-bookmark="${i}">♧ ${esc(b.label)}<span>BAR ${b.measure+1}</span></button><button class="icon-button" data-remove-bookmark="${i}" aria-label="Remove ${esc(b.label)} bookmark">×</button></div>`).join("") || '<p class="empty-hint">Save a tricky entrance or a favourite phrase. Find it here next time.</p>';
  $("bookmarks").querySelectorAll("[data-bookmark]").forEach(b=>b.onclick=()=>jumpBar(bookmarks[+b.dataset.bookmark].measure));
  $("bookmarks").querySelectorAll("[data-remove-bookmark]").forEach(b=>b.onclick=run(async()=>{const next=bookmarks.filter((_,i)=>i!==+b.dataset.removeBookmark);await queueMeta({bookmarks:next});renderBookmarks();}));
}
function jumpBar(index,part=0) {
  pause();state.currentMeasure=index;
  const events=state.score.events.filter(e=>e.measure===index);state.position=events[0]?.time??state.score.measureTimes[index]?.time??0;
  const note=Object.values(state.score.notes).find(n=>n.measure===index && n.part===part);
  if(note && $(note.id)) scrollToElement($(note.id));
  updateTransport();
}
function renderIssues() {
  const issues=state.score.issues;$("review-note").textContent=state.score.meta.reviewNote||"";$("issue-count").textContent=issues.length;$("review-pill").textContent=state.score.meta.reviewed?"REVIEWED":"TO REVIEW";
  $("issues").innerHTML=issues.length?issues.map((i,n)=>`<button class="issue" data-issue="${n}"><strong>${i.part!==undefined?`${esc(state.score.parts[i.part].name)} · bar ${i.measure+1}`:"PLAYBACK NOTE"}</strong>${esc(i.message)}</button>`).join(""):'<p class="empty-hint">✓ No structural problems found.<br>Pitch and symbol accuracy still need a visual check.</p>';
  if(state.score.engravingLog) { const details=document.createElement("details");details.innerHTML='<summary class="hint">Engraver notices</summary>';const p=document.createElement("p");p.className="hint";p.textContent=state.score.engravingLog;details.appendChild(p);$("issues").appendChild(details); }
  $("issues").querySelectorAll("[data-issue]").forEach(b=>b.onclick=()=>{const i=issues[+b.dataset.issue];if(i.measure!==undefined){jumpBar(i.measure,i.part);$("compose-part").value=i.part;fillBars(i.measure);$("meter-bar").value=i.measure+1;if(!i.code){setView("compose");toast("This part and bar are selected. Click a note to change pitch, or use the bar composer to replace its rhythm.");}}});
}
let textCallback;
function textDialog(title,label,value,callback) { $("text-title").textContent=title;$("text-label").textContent=label;$("text-value").value=value;textCallback=callback;$("text-dialog").showModal();$("text-value").focus();$("text-value").select(); }
function bookmark() {
  if(!state.score)return;const measure=state.currentMeasure;
  textDialog("Keep this moment",`Bookmark bar ${measure+1}`,"Rehearse this phrase",async label=>{await queueMeta({bookmarks:[...(state.score.meta.bookmarks||[]),{measure,label}]});renderBookmarks();});
}

// Web Audio synthesis is fully offline. These are lightweight instrument tones,
// not sampled orchestral recordings. Use an audio-clock lookahead for timing.
async function audioReady() {
  if(!state.audio) {
    state.audio=new AudioContext();state.master=state.audio.createGain();state.master.gain.value=+$("master-volume").value*1.3;
    const compressor=state.audio.createDynamicsCompressor();state.master.connect(compressor);compressor.connect(state.audio.destination);
  }
  if(state.audio.state!=="running")await state.audio.resume();
}
function tone(pitch,duration,start,sound="Piano",volume=.6) {
  const ctx=state.audio;if(!ctx || volume<=0)return;
  const freq=440*2**((pitch-69)/12), gain=ctx.createGain();gain.connect(state.master);
  const profiles={Piano:[[1,1],[2,.28],[3,.09]],Flute:[[1,1],[2,.25],[3,.12]],Strings:[[1,.65],[2,.3],[3,.16],[4,.08]],Organ:[[1,.7],[2,.4],[4,.15]],Bell:[[1,.8],[2.76,.25],[5.4,.07]]};
  const attack=sound==="Strings"?.08:.012,release=sound==="Piano"?.25:sound==="Bell"?.5:.08;
  const end=start+Math.max(.035,duration);
  gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(volume*.22,start+Math.min(attack,duration/3));
  if(sound==="Piano"||sound==="Bell")gain.gain.exponentialRampToValueAtTime(Math.max(.001,volume*.025),Math.max(start+attack,end));
  else gain.gain.setValueAtTime(volume*.18,Math.max(start+attack,end));
  gain.gain.linearRampToValueAtTime(0,end+release);
  for(const [harmonic,level] of profiles[sound]||profiles.Piano) {
    const osc=ctx.createOscillator(), partial=ctx.createGain();osc.type="sine";osc.frequency.value=freq*harmonic;partial.gain.value=level;osc.connect(partial);partial.connect(gain);
    state.nodes.add(osc);osc.onended=()=>{state.nodes.delete(osc);osc.disconnect();partial.disconnect();};osc.start(start);osc.stop(end+release+.01);
  }
  setTimeout(()=>gain.disconnect(),Math.max(0,(end+release-ctx.currentTime)*1000)+100);
}
function click(at,accent=false) { tone(accent?94:88,.035,at,"Flute",.5); }
function silence() { for(const node of state.nodes)try{node.stop();}catch{}state.nodes.clear(); }
function position() { return state.playing ? Math.min(state.score.duration,(state.audio.currentTime-state.started)*state.speed) : state.position; }
async function play() {
  if(!state.score)return;if(state.playing){pause();return;}
  await audioReady();
  if(state.score.meta.playbackReady===false){toast("Recognition is not ready. The original PDF is available to read and annotate.");return;}
  busy(true,"Loading sampled instruments…");
  try{
    const needed=new Map(),solo=state.mixer.some(m=>m.solo);
    for(const e of state.score.events){const mix=state.mixer[e.part];if(!mix||mix.mute||(solo&&!mix.solo))continue;for(const name of mix.sounds){if(!needed.has(name))needed.set(name,new Set());needed.get(name).add(e.pitch);}}
    await Promise.all([...needed].map(([name,pitches])=>StudioSamples.load(state.audio,name,[...pitches])));
  }finally{busy(false);}
  state.scrollStart=null;$("scroll-only").textContent="▷ Scroll without sound";
  if(state.position>=state.score.duration-.01)state.position=0;
  state.speed=+$("tempo").value/state.score.baseTempo;
  state.started=state.audio.currentTime+.04-state.position/state.speed;state.playing=true;
  state.eventIndex=state.score.events.findIndex(e=>e.time>=state.position-.001);if(state.eventIndex<0)state.eventIndex=state.score.events.length;
  // Resume sustained notes when seeking into a note, without retriggering old notes in the scheduler.
  for(const e of state.score.events)if(e.time<state.position-.001 && e.time+e.duration>state.position)playEvent({...e,time:state.position,duration:e.time+e.duration-state.position});
  state.metroNext=state.audio.currentTime+.04;state.metroCount=0;
  $("play").textContent="Ⅱ";$("play").setAttribute("aria-label","Pause score");ensureScheduler();schedule();
}
function refreshMix() {
  if(state.playing){pause();play().catch(e=>toast(e.message,true));}
}
function playEvent(e) {
  const m=state.mixer[e.part],solo=state.mixer.some(p=>p.solo);
  if(!m||m.mute||(solo&&!m.solo))return;
  const start=Math.max(state.audio.currentTime,state.started+e.time/state.speed);
  for(const s of m.sounds)StudioSamples.play(state.audio,state.master,state.nodes,e.pitch,e.duration/state.speed,start,s,m.volume/Math.sqrt(Math.max(1,m.sounds.length)));
}
function ensureScheduler() { if(!state.timer)state.timer=setInterval(schedule,25); }
function scoreBeatTime(q) {
  const map=state.score.timeline;let a=map[0];
  for(let i=1;i<map.length;i++){const b=map[i];if(b.qstamp>=q && b.qstamp>a.qstamp)return (a.tstamp+(b.tstamp-a.tstamp)*(q-a.qstamp)/(b.qstamp-a.qstamp))/1000;a=b;}
  return state.score.duration;
}
function scoreQuarterAt(seconds) {
  const map=state.score.timeline;let a=map[0];
  for(let i=1;i<map.length;i++){const b=map[i];if(b.tstamp>=seconds*1000 && b.tstamp>a.tstamp)return a.qstamp+(b.qstamp-a.qstamp)*(seconds*1000-a.tstamp)/(b.tstamp-a.tstamp);a=b;}
  return a.qstamp;
}
function schedule() {
  if(!state.audio)return;const now=state.audio.currentTime;
  if(state.playing) {
    const horizon=(now+.16-state.started)*state.speed;
    while(state.eventIndex<state.score.events.length && state.score.events[state.eventIndex].time<horizon)playEvent(state.score.events[state.eventIndex++]);
    if(state.metronome) {
      if(state.nextQuarter===undefined)state.nextQuarter=Math.ceil(scoreQuarterAt(position())-.001);
      while(state.nextQuarter<100000) {
        const t=scoreBeatTime(state.nextQuarter);if(t>=state.score.duration || state.started+t/state.speed>=now+.16)break;
        const at=state.started+t/state.speed;if(at>=now-.02)click(Math.max(now,at),state.score.measureTimes.some(m=>Math.abs(m.qstamp-state.nextQuarter)<.001));state.nextQuarter++;
      }
    }
    if(position()>=state.score.duration){pause();state.position=state.score.duration;updateTransport();}
  } else if(state.metronome) {
    if(state.metroNext<now-.1)state.metroNext=now;
    while(state.metroNext<now+.12){click(state.metroNext,state.metroCount++%4===0);state.metroNext+=60/Number($("tempo").value);}
  }
  if(!state.playing&&!state.metronome){clearInterval(state.timer);state.timer=null;}
}
function pause() {
  if(state.playing)state.position=position();state.playing=false;state.nextQuarter=undefined;silence();
  $("play").textContent="▶";$("play").setAttribute("aria-label","Play score");
  if(state.audio)state.metroNext=state.audio.currentTime+.05;
}
function updateTransport() {
  const p=state.score?position():0;$("time-current").textContent=time(p/state.speed);$("time-total").textContent=time((state.score?.duration||0)/state.speed);
  $("seek").max=state.score?.duration||1;$("seek").value=p;
  updatePlaybackHighlight(p);
}
function updatePlaybackHighlight(p) {
  document.querySelectorAll('.playing-note,.playing-bar').forEach(el=>el.classList.remove('playing-note','playing-bar'));
  if(!state.score)return;
  const measure=[...state.score.measureTimes].reverse().find(m=>m.time<=p);
  if(measure){
    state.currentMeasure=measure.measure;$(measure.id)?.classList.add('playing-bar');
    $('playback-location').textContent=`Bar position ${measure.measure+1}${state.score.meta.reviewed?'':' · draft'}`;
  }
  state.score.events.filter(e=>e.time<=p && e.time+e.duration>p).forEach(e=>$(e.id)?.classList.add('playing-note'));
}
function scrollToElement(el) {
  const pane=$("score-scroll"), rect=el.getBoundingClientRect(), parent=pane.getBoundingClientRect();
  pane.scrollTo({top:pane.scrollTop+rect.top-parent.top-90,behavior:"smooth"});
}
let lastVisual=-1,lastFollow="";
function animate() {
  if(state.playing&&state.score) {
    updateTransport();const p=position();
    if(Math.abs(p-lastVisual)>.045) {
      lastVisual=p;
      const measure=[...state.score.measureTimes].reverse().find(m=>m.time<=p);
      if(measure)state.currentMeasure=measure.measure;
      if($("follow").checked && $("reader-format").value!=="pdf") {
        const pane=$("score-scroll");
        if($("scroll-mode").value==="timed")pane.scrollTop=(pane.scrollHeight-pane.clientHeight)*Math.min(1,p/state.speed/(+$("scroll-duration").value||120));
        else if(measure && lastFollow!==measure.id){lastFollow=measure.id;const el=$(measure.id);if(el){const r=el.getBoundingClientRect(),pr=pane.getBoundingClientRect();if(r.top<pr.top+20 || r.bottom>pr.bottom-30)scrollToElement(el);}}
      }
    }
  }
  if(state.scrollStart!==null) {
    const pane=$("score-scroll"),duration=$("scroll-mode").value==="timed"?+$("scroll-duration").value:(state.score?.duration||60)/state.speed;
    const fraction=Math.min(1,(performance.now()-state.scrollStart)/1000/Math.max(5,duration));
    pane.scrollTop=state.scrollOrigin+(pane.scrollHeight-pane.clientHeight-state.scrollOrigin)*fraction;
    if(fraction===1){state.scrollStart=null;$("scroll-only").textContent="▷ Scroll without sound";}
  }
  requestAnimationFrame(animate);
}
function makeKeyboard() {
  const names=["C","C♯","D","D♯","E","F","F♯","G","G♯","A","A♯","B"];
  let white=0;
  const keys=[];
  for(let midi=21;midi<=108;midi++) {
    const name=names[midi%12],black=name.includes("♯");
    const left=black?white*44-14:white++*44;
    keys.push(`<button class="piano-key ${black?"black":""}" style="left:${left}px" data-midi="${midi}" aria-label="${name}${Math.floor(midi/12)-1}">${name}${Math.floor(midi/12)-1}</button>`);
  }
  $("keyboard").innerHTML=keys.join("");
  $("keyboard").querySelectorAll("button").forEach(b=>b.onclick=run(()=>keyboardNote(+b.dataset.midi)));
}
async function keyboardNote(midi) {
  await audioReady();const transposed=midi;
  await StudioSamples.load(state.audio,"Piano",[transposed]);StudioSamples.play(state.audio,state.master,state.nodes,transposed,.55,state.audio.currentTime,"Piano",.85);const b=document.querySelector(`[data-midi="${midi}"]`);b?.classList.add("pressed");setTimeout(()=>b?.classList.remove("pressed"),250);
  if(state.view==="compose" && $("keyboard-entry").checked) {
    const names=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
    addPhrase(`${names[transposed%12]}${Math.floor(transposed/12)-1}`);
  }
}
function addPhrase(pitch) { $("phrase").value=[$("phrase").value.trim(),`${pitch}/${$("entry-duration").value}`].filter(Boolean).join(" ");renderDraft(); }
function toggleKeyboard(force) { $("keyboard-panel").hidden=force===undefined?!$("keyboard-panel").hidden:!force;$("keyboard-btn").setAttribute("aria-expanded",String(!$("keyboard-panel").hidden)); if(!$("keyboard-panel").hidden)$("keyboard-scroll").scrollLeft=23*44; }
async function importFile(file,options={}) {
  if(!file)return;if(file.size>40*1024*1024)throw new Error("Choose a file smaller than 40 MB.");
  const scan=/\.(pdf|png|jpe?g|tiff?)$/i.test(file.name);
  
  busy(true,scan?"Preparing your scan…":"Importing MusicXML…");
  const base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=reject;reader.readAsDataURL(file);});
  const result=await api(scan?"/api/scan":"/api/import",{data:base64,name:file.name,options});
  if(!scan){await library();await openScore(result.id);toast("Score imported. Your original file is unchanged.");return;}
  busy(false);await library();await openScore(result.id);
  if(!result.job){toast("PDF saved for reading. Install Audiveris to enable recognition.");return;}
  toast("Scanning locally. You can read and annotate the original now.");
  syncScanJobs([{job:result.job,id:result.id,name:file.name,status:"running",stage:0,message:"Preparing scan",elapsed:0}]);
}

on("library-nav","click",()=>{state.trash=false;state.group=null;showLibrary();renderLibrary();});
on("search","input",()=>{showLibrary();renderLibrary();});
on("new-group","click",()=>{if(!state.score){toast("Open a score first to place it in a collection.");return;}textDialog("Give your music a home","Collection name",state.score.meta.group||"",async group=>{await queueMeta({group});$("score-eyebrow").textContent=group;toast("Score moved to the collection.");});});
on("score-eyebrow","click",()=>$ ("new-group").click());
on("new-btn","click",()=>$("new-dialog").showModal());
on("new-form","submit",async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));for(const k of ["bars","beats","beat_type","fifths","tempo"])data[k]=Number(data[k]);busy(true,"Creating your score…");const r=await api("/api/new",data);$("new-dialog").close();await library();state.view="compose";await openScore(r.id);});
on("text-form","submit",async e=>{e.preventDefault();const value=$("text-value").value.trim();if(!value)return;await textCallback(value);$("text-dialog").close();});
document.querySelectorAll(".close-dialog").forEach(b=>b.onclick=()=>b.closest("dialog").close());
document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>setView(b.dataset.view));
for(const id of ["solfa","solfa-mode","minor-do"])on(id,"change",()=>state.score&&openScore(state.score.id,true));
on("zoom","change",()=>$("pages").style.setProperty("--zoom",$("zoom").value));
on("import-btn","click",()=>$("file-input").click());
on("file-input","change",async e=>{const file=e.target.files[0];e.target.value="";if(file&&/\.(pdf|png|jpe?g|tiff?)$/i.test(file.name)){pendingScan=file;$("scan-dialog").showModal();}else await importFile(file);});
on("bookmark-btn","click",bookmark);on("bookmark-add","click",bookmark);
on("export-btn","click",async()=>{if(!state.score)return;const r=await fetch(`/api/xml/${state.score.id}`);const url=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=url;a.download=state.score.title.replace(/[<>:"/\\|?*]/g,"_")+".musicxml";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
on("print-btn","click",()=>window.print());
on("compose-part","change",()=>fillBars(0));on("compose-bar","change",updateCapacity);
on("entry-keyboard","click",()=>{toggleKeyboard(true);$("keyboard-entry").checked=true;});
on("entry-rest","click",()=>addPhrase("R"));
on("entry-back","click",()=>{$("phrase").value=$("phrase").value.trim().split(/\s+/).slice(0,-1).join(" ");renderDraft();});
on("note-form","submit",async e=>{e.preventDefault();if(!state.selected)return;await edit("note",{nid:state.selected,step:$("note-step").value,alter:+$("note-alter").value,octave:+$("note-octave").value,lyric:$("note-lyric").value});});
on("replace-bar","click",()=>edit("bar",{part:+$("compose-part").value,measure:+$("compose-bar").value,phrase:$("phrase").value}));
on("append-bar","click",()=>edit("append"));
on("undo-btn","click",async()=>{if(!state.score)return;await state.saving;busy(true,"Restoring previous version…");const id=state.score.id;await api("/api/undo",{id,revision:state.score.revision});await library();await openScore(id,true);toast("Previous version restored.");});
on("xml-btn","click",async()=>{const r=await fetch(`/api/xml/${state.score.id}`);$("xml-editor").value=await r.text();$("xml-dialog").showModal();});
on("xml-save","click",async()=>{await edit("xml",undefined,{xml:$("xml-editor").value});$("xml-dialog").close();});
on("source-btn","click",()=>{if(state.score.hasSource){$("source-frame").src=`/api/source/${state.score.id}`;$("source-dialog").showModal();}});
on("reviewed","change",async()=>{await queueMeta({reviewed:$("reviewed").checked});renderIssues();$("scan-banner").hidden=state.score.meta.reviewed||state.score.meta.origin!=="Scan";});
on("scroll-mode","change",async()=>{$("scroll-duration-field").hidden=$("scroll-mode").value!=="timed";await savePractice();});
on("follow","change",savePractice);
on("scroll-duration","change",async()=>{$("scroll-duration").value=Math.max(5,Math.min(7200,+$("scroll-duration").value||120));await savePractice();});
on("scroll-only","click",()=>{if(state.scrollStart!==null){state.scrollStart=null;$("scroll-only").textContent="▷ Scroll without sound";return;}pause();state.scrollStart=performance.now();state.scrollOrigin=$("score-scroll").scrollTop;$("scroll-only").textContent="Ⅱ Pause scrolling";});
on("play","click",play);
on("restart","click",()=>{pause();state.position=0;lastFollow="";updateTransport();$("score-scroll").scrollTop=0;});
on("seek","input",e=>{pause();state.position=+e.target.value;lastFollow="";updateTransport();});
on("tempo","change",async()=>{const wasPlaying=state.playing;pause();$("tempo").value=Math.max(20,Math.min(300,+$("tempo").value||96));state.speed=+$("tempo").value/(state.score?.baseTempo||120);updateTransport();await savePractice();if(wasPlaying)await play();});
on("master-volume","input",()=>{if(state.master)state.master.gain.setTargetAtTime(+$("master-volume").value*1.3,state.audio.currentTime,.02);});
on("metronome","click",async()=>{await audioReady();state.metronome=!state.metronome;state.nextQuarter=undefined;state.position=position();state.metroNext=state.audio.currentTime+.03;$("metronome").setAttribute("aria-pressed",String(state.metronome));ensureScheduler();});
on("keyboard-btn","click",()=>toggleKeyboard());on("close-keyboard","click",()=>toggleKeyboard(false));
document.addEventListener("keydown",run(async e=>{
  if(e.target.closest("input,textarea,select,dialog")||e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.code==="Space"){e.preventDefault();await play();return;}
  if(e.repeat||$("keyboard-panel").hidden)return;
  const index="awsedftgyhujk".indexOf(e.key.toLowerCase());if(index>=0){e.preventDefault();await keyboardNote(60+index);}
}));
window.addEventListener("beforeunload",()=>{pause();});
run(async()=>{state.token=(await api("/api/session")).token;makeKeyboard();await library();if(state.library.length)await openScore(state.library[0].id);showLibrary();requestAnimationFrame(animate);})();

function renderDraft(){
  const symbols={w:"𝅝",h:"𝅗𝅥",q:"♩",e:"♪",s:"♬"};
  $("visual-draft").innerHTML=$("phrase").value.trim().split(/\s+/).filter(Boolean).map((token,i)=>{
    const [pitch,duration]=token.split("/");return `<button class="draft-note" data-index="${i}" title="Remove this note"><strong>${pitch==="R"?"𝄽":symbols[duration?.[0]]||"♩"}${duration?.endsWith(".")?"·":""}</strong><small>${esc(pitch)}</small></button>`;
  }).join("")||'<span class="hint">Choose a symbol, then click a pitch to add it.</span>';
  $("visual-draft").querySelectorAll("button").forEach(b=>b.onclick=()=>{const tokens=$("phrase").value.trim().split(/\s+/);tokens.splice(+b.dataset.index,1);$("phrase").value=tokens.join(" ");renderDraft();});
}
document.querySelectorAll("[data-duration]").forEach(b=>b.onclick=()=>{$("entry-duration").value=b.dataset.duration;document.querySelectorAll("[data-duration]").forEach(n=>n.setAttribute("aria-pressed",String(n===b)));});
document.querySelectorAll("[data-pitch]").forEach(b=>b.onclick=()=>addPhrase(b.dataset.pitch+$("entry-octave").value));
on("phrase","input",renderDraft);
on("keyboard-lower","click",()=>$("keyboard-scroll").scrollBy({left:-308,behavior:"smooth"}));
on("keyboard-higher","click",()=>$("keyboard-scroll").scrollBy({left:308,behavior:"smooth"}));
renderDraft();

async function readerFormat(){
  const format=$("reader-format").value,original=format!=="notation";
  $("reader-surfaces").classList.toggle("comparison",format==="compare");
  StudioPDF.setComparison(format==="compare");
  const controls=$("pdf-controls");
  if(format==="compare")$("reader-surfaces").before(controls);
  else $("pdf-reader").prepend(controls);
  controls.hidden=!original;
  $("digital-reader").hidden=format==="pdf";
  $("pages").hidden=format==="pdf";$("pdf-reader").hidden=!original;
  if(original&&state.score){const id=state.score.id;await StudioPDF.open(id,state.score.meta.annotations,marks=>queueMeta({annotations:marks},id));}
}
on("reader-format","change",readerFormat);

let menuScore=null,menuReturn=null;
function closeScoreMenu(){ $('score-menu').hidden=true;menuReturn?.focus(); }
function openScoreMenu(id,x,y){
  menuScore=id;menuReturn=document.activeElement;
  const item=state.library.find(s=>s.id===id);if(!item)return;
  const actions=item.trashed?[['restore','Restore score']]:[['open','Open'],['rename','Rename'],['group','Move to collection…'],['ungroup','Remove from collection'],['duplicate','Duplicate'],['share','Share / download original'],['export','Export MusicXML'],['trash','Move to Trash']];
  $('score-menu').innerHTML=actions.map(([action,label])=>`<button role="menuitem" data-action="${action}">${label}</button>`).join('');
  const menu=$('score-menu');menu.hidden=false;menu.style.left=Math.max(8,Math.min(x,innerWidth-250))+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-menu.offsetHeight-8))+'px';
  menu.querySelectorAll('button').forEach(b=>b.onclick=run(()=>scoreAction(id,b.dataset.action)));menu.querySelector('button').focus();
}
async function manageMeta(id,meta){
  await state.saving;await library();const item=state.library.find(s=>s.id===id);
  const result=await api('/api/meta',{id,revision:item.revision,meta});
  for(const [field,value] of Object.entries(meta)){
    if(result.meta?.[field]!==value)throw new Error('The server did not save this change. Close the old Studio server, start Studio again, then refresh this page.');
  }
  if(state.score?.id===id){state.score.revision=result.revision;state.score.meta=result.meta;state.score.title=result.meta.title;$('score-title').textContent=result.meta.title;$('score-eyebrow').textContent=result.meta.group;}
  await library();
}
async function scoreAction(id,action){
  closeScoreMenu();const item=state.library.find(s=>s.id===id);
  if(action==='open')return openScore(id);
  if(action==='rename')return textDialog('Rename score','Display name (original filename is retained)',item.title,value=>manageMeta(id,{title:value}));
  if(action==='group')return textDialog('Move to collection','Choose an existing collection or type a new name',item.group||'',value=>manageMeta(id,{group:value}));
  if(action==='ungroup')return manageMeta(id,{group:'Ungrouped'});
  if(action==='trash'||action==='restore'){await manageMeta(id,{trashed:action==='trash'});if(state.score?.id===id)showLibrary();toast(action==='trash'?'Moved to Trash. You can restore it from the sidebar.':'Score restored.');return;}
  if(action==='duplicate'){await state.saving;const result=await api('/api/duplicate',{id,revision:item.revision});await library();state.trash=false;state.group=null;showLibrary();renderLibrary();toast('Independent copy created.');return;}
  if(action==='share'||action==='export'){
    let response=action==='share'?await fetch(`/api/source/${id}`):null;
    const original=response?.ok;
    if(!original)response=await fetch(`/api/xml/${id}`);
    if(!response.ok)throw new Error('Could not export this score.');
    const blob=await response.blob(),name=original?(item.sourceFileName||item.title):item.title.replace(/\.[^.]+$/,'')+'.musicxml';
    const file=new File([blob],name,{type:blob.type});
    if(action==='share'&&navigator.canShare?.({files:[file]})){
      try{await navigator.share({files:[file],title:item.title});return;}catch(e){if(e.name==='AbortError')return;}
    }
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);toast('Downloaded. Attach this file to share it. Annotations are stored separately.');
  }
}
on('trash-nav','click',()=>{state.trash=true;state.group=null;showLibrary();$('breadcrumb').textContent='Trash';renderLibrary();});
on('score-menu-btn','click',e=>{if(state.score){const r=e.currentTarget.getBoundingClientRect();openScoreMenu(state.score.id,r.left,r.bottom);}});
document.addEventListener('pointerdown',e=>{if(!$('score-menu').hidden&&!e.target.closest('#score-menu,.score-more,#score-menu-btn'))$('score-menu').hidden=true;});
$('score-menu').onkeydown=e=>{const items=[...$('score-menu').querySelectorAll('button')],i=items.indexOf(document.activeElement);if(e.key==='Escape'){closeScoreMenu();return;}if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();items[(i+(e.key==='ArrowDown'?1:-1)+items.length)%items.length].focus();}};
$('text-value').setAttribute('list','collection-suggestions');
const suggestions=document.createElement('datalist');suggestions.id='collection-suggestions';document.body.appendChild(suggestions);
$('text-dialog').addEventListener('toggle',()=>{suggestions.innerHTML=[...new Set(state.library.filter(s=>!s.trashed).map(s=>s.group))].map(g=>`<option value="${esc(g)}">`).join('');});

const scanJobs=new Map();let scanPollTimer=null;
function syncScanJobs(jobs){
  for(const job of jobs){if(scanJobs.get(job.job)?.dismissed)continue;scanJobs.set(job.job,job);}
  renderScanJobs();scheduleScanPoll();
}
function renderScanJobs(){
  const visible=[...scanJobs.values()].filter(j=>!j.dismissed);$('scan-progress').hidden=!visible.length;
  $('scan-progress').innerHTML=visible.map(j=>`<div class="scan-job"><div class="scan-job-title"><strong>${esc(j.name||'Score scan')}</strong><span>${Math.floor((j.elapsed||0)/60)}m ${(j.elapsed||0)%60}s</span>${j.status!=='running'?`<button class="icon-button" data-dismiss-scan="${j.job}" aria-label="Dismiss scan status">×</button>`:''}</div><p role="status">${esc(j.message||j.error||'Scanning…')}</p><progress max="4" value="${j.stage||0}" aria-label="Scan stages completed"></progress><small>${j.status==='error'?esc(j.error):esc(j.detail||(['Preparing','Recognizing','Exporting','Checking','Ready'][j.stage||0]))}${j.status==='running'?' · Stage progress; timing varies by score':''}</small></div>`).join('');
  $('scan-progress').querySelectorAll('[data-dismiss-scan]').forEach(b=>b.onclick=()=>{scanJobs.get(b.dataset.dismissScan).dismissed=true;renderScanJobs();});
}
function scheduleScanPoll(){if(!scanPollTimer&&[...scanJobs.values()].some(j=>j.status==='running'))scanPollTimer=setTimeout(pollScans,2000);}
async function pollScans(){
  try{
    for(const [id,previous] of scanJobs){
      if(previous.status!=='running')continue;
      const next=await api('/api/job/'+id);scanJobs.set(id,{...previous,...next});
      if(next.status==='done'){await state.saving;await library();if(state.score?.id===next.id)await openScore(next.id,true);toast('Scan ready. Compare the result with the original.');}
    }
  }catch(e){for(const j of scanJobs.values())if(j.status==='running')j.detail='Connection interrupted · retrying…';}
  finally{scanPollTimer=null;renderScanJobs();scheduleScanPoll();}
}

on("apply-meter","click",()=>edit("meter",{measure:+$("meter-bar").value-1,beats:+$("meter-beats").value,beat_type:+$("meter-unit").value,all_parts:true}));

let pendingScan=null;
on("rescan-btn","click",()=>{if(!state.score?.hasSource){toast("No original scan is attached.");return;}pendingScan=state.score.id;$("scan-dialog").showModal();});
on("scan-form","submit",async e=>{
  e.preventDefault();const options={pages:$("scan-pages").value,layout:document.querySelector('input[name="scan-ensemble"]:checked').value};
  if(typeof pendingScan==='string'){
    const result=await api('/api/rescan',{id:pendingScan,options});$('scan-dialog').close();
    if(result.job)syncScanJobs([{job:result.job,id:result.id,name:state.score.title,status:'running',stage:0,message:'Preparing rescan',elapsed:0}]);else toast('Audiveris is unavailable.');
  }else{const file=pendingScan;pendingScan=null;$('scan-dialog').close();await importFile(file,options);}
});
