/* PDF spreads with lazy rendering and page-normalized annotation history. */
window.StudioPDF = (() => {
  const $=id=>document.getElementById(id),redoByPage=new Map();
  let pdf=null,page=1,scoreId=null,marks=[],save=null,tool='pan',stroke=null,observer=null,slots=[],generation=0,comparison=false,savedDirection='vertical';
  function controls(){
    $('pdf-undo').disabled=!!stroke||!marks.some(m=>m.page===page);
    $('pdf-redo').disabled=!!stroke||!redoByPage.get(page)?.length;
    $('pdf-prev').disabled=page===1;$('pdf-next').disabled=!pdf||page===pdf.numPages;
    $('pdf-page-label').textContent=pdf?`${page} / ${pdf.numPages}`:'';
  }
  function draw(slot){
    slot.ink.replaceChildren();
    for(const mark of marks.filter(m=>m.page===slot.number)){
      const path=document.createElementNS('http://www.w3.org/2000/svg','polyline');
      for(const [name,value] of Object.entries({points:mark.points.map(p=>p.join(',')).join(' '),fill:'none',stroke:mark.tool==='highlight'?'#ffdc19':'#e13d4d','stroke-width':mark.tool==='highlight'?22:3,opacity:mark.tool==='highlight'?.35:1,'stroke-linecap':'round','stroke-linejoin':'round'}))path.setAttribute(name,String(value));
      slot.ink.appendChild(path);
    }
    controls();
  }
  function redraw(){slots.forEach(draw);}
  function point(svg,e){const r=svg.getBoundingClientRect();return [Math.max(0,Math.min(1000,(e.clientX-r.left)/r.width*1000)),Math.max(0,Math.min(1000,(e.clientY-r.top)/r.height*1000))];}
  function bind(slot){
    const svg=slot.ink;
    svg.onpointerdown=e=>{if(tool==='pan'||e.button!==0||stroke)return;page=slot.number;e.preventDefault();svg.setPointerCapture(e.pointerId);stroke={page,tool,points:[point(svg,e)]};marks.push(stroke);draw(slot);};
    svg.onpointermove=e=>{if(stroke?.page!==slot.number)return;stroke.points.push(point(svg,e));draw(slot);};
    svg.onpointerup=()=>{if(stroke?.page!==slot.number)return;if(stroke.points.length===1)stroke.points.push([stroke.points[0][0]+.1,stroke.points[0][1]+.1]);redoByPage.delete(page);stroke=null;draw(slot);save?.(structuredClone(marks));};
    svg.onpointercancel=()=>{if(stroke?.page===slot.number){marks.pop();stroke=null;draw(slot);}};
    slot.sheet.onpointerenter=()=>{if(!stroke){page=slot.number;controls();}};
  }
  async function render(slot){
    if(slot.canvas||slot.rendering)return;slot.rendering=true;const ticket=generation,doc=pdf;
    try{
      const p=await doc.getPage(slot.number),viewport=p.getViewport({scale:1.4});
      const canvas=document.createElement('canvas');canvas.width=viewport.width;canvas.height=viewport.height;
      await p.render({canvasContext:canvas.getContext('2d'),viewport}).promise;
      if(ticket!==generation||!slot.near)return;
      slot.sheet.style.aspectRatio=`${viewport.width}/${viewport.height}`;slot.surface.replaceChildren(canvas);slot.canvas=canvas;
    }catch(e){if(ticket===generation)slot.surface.textContent='Could not render this page: '+e.message;}
    finally{slot.rendering=false;}
  }
  function arrange(){
    observer?.disconnect();
    const host=$('pdf-pages'),width=+$('pdf-layout').value||1,horizontal=!comparison&&$('pdf-direction').value==='horizontal';
    host.classList.toggle('horizontal',horizontal);host.style.setProperty('--pages-per-spread',width);
    const groups=[];
    for(let i=0;i<slots.length;i+=width){const spread=document.createElement('div');spread.className='pdf-spread';slots.slice(i,i+width).forEach(slot=>spread.appendChild(slot.sheet));groups.push(spread);}
    host.replaceChildren(...groups);$('pdf-direction').disabled=comparison;
    observer=new IntersectionObserver(entries=>{
      for(const entry of entries){const slot=slots[+entry.target.dataset.page-1];slot.near=entry.isIntersecting;
        if(slot.near)render(slot);else if(slot.canvas){slot.surface.replaceChildren();slot.canvas=null;}
      }
      const visible=slots.filter(s=>s.near).map(s=>({slot:s,r:s.sheet.getBoundingClientRect()})).filter(x=>x.r.bottom>0&&x.r.right>0).sort((a,b)=>Math.abs(a.r.top-$('score-scroll').getBoundingClientRect().top)-Math.abs(b.r.top-$('score-scroll').getBoundingClientRect().top));
      if(visible.length&&!stroke){page=visible[0].slot.number;controls();}
    },{root:$('score-scroll'),rootMargin:'250px',threshold:0});
    slots.forEach(s=>observer.observe(s.sheet));controls();
  }
  async function open(id,annotations,onSave){
    if(scoreId!==id||JSON.stringify(marks)!==JSON.stringify(annotations||[]))redoByPage.clear();
    marks=structuredClone(annotations||[]);save=onSave;
    if(scoreId!==id){
      const module=await import('/vendor/pdf.mjs');module.GlobalWorkerOptions.workerSrc='/vendor/pdf.worker.mjs';
      const response=await fetch('/api/source/'+id);if(!response.ok)throw new Error('Original PDF is unavailable.');
      const next=await module.getDocument({data:new Uint8Array(await response.arrayBuffer()),isEvalSupported:false}).promise;
      generation++;observer?.disconnect();if(pdf)await pdf.destroy();pdf=next;scoreId=id;page=1;
      slots=Array.from({length:pdf.numPages},(_,i)=>{
        const sheet=document.createElement('div'),surface=document.createElement('div'),ink=document.createElementNS('http://www.w3.org/2000/svg','svg');
        sheet.className='pdf-sheet';sheet.dataset.page=i+1;surface.className='pdf-surface';
        ink.setAttribute('viewBox','0 0 1000 1000');ink.setAttribute('preserveAspectRatio','none');ink.classList.add('pdf-ink');ink.setAttribute('aria-label','Annotations on page '+(i+1));
        const label=document.createElement('span');label.className='pdf-sheet-number';label.textContent=i+1;
        sheet.append(surface,ink,label);const slot={number:i+1,sheet,surface,ink};bind(slot);return slot;
      });arrange();
    }
    setTool(tool);redraw();
  }
  function setTool(next){tool=next;slots.forEach(s=>{s.ink.style.touchAction=tool==='pan'?'auto':'none';s.ink.style.pointerEvents=tool==='pan'?'none':'auto';});document.querySelectorAll('[data-ink]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ink===tool)));}
  document.querySelectorAll('[data-ink]').forEach(b=>b.onclick=()=>setTool(b.dataset.ink));
  function navigate(delta){page=Math.max(1,Math.min(pdf?.numPages||1,page+delta*(+$('pdf-layout').value||1)));const slot=slots[page-1];if(!slot)return;const host=$('pdf-pages');if(host.classList.contains('horizontal'))host.scrollTo({left:slot.sheet.parentElement.offsetLeft-host.offsetLeft,behavior:'smooth'});else{const pane=$('score-scroll');pane.scrollTo({top:pane.scrollTop+slot.sheet.getBoundingClientRect().top-pane.getBoundingClientRect().top-90,behavior:'smooth'});}controls();}
  $('pdf-prev').onclick=()=>navigate(-1);$('pdf-next').onclick=()=>navigate(1);
  $('pdf-layout').onchange=$('pdf-direction').onchange=()=>{if(pdf)arrange();};
  $('pdf-undo').onclick=()=>{if(stroke)return;const i=marks.findLastIndex(m=>m.page===page);if(i>=0){const history=redoByPage.get(page)||[];history.push({index:i,mark:marks.splice(i,1)[0]});redoByPage.set(page,history);redraw();save?.(structuredClone(marks));}};
  $('pdf-redo').onclick=()=>{if(stroke)return;const entry=redoByPage.get(page)?.pop();if(entry){marks.splice(Math.min(entry.index,marks.length),0,entry.mark);redraw();save?.(structuredClone(marks));}};
  function setComparison(value){if(comparison===value)return;if(value){savedDirection=$('pdf-direction').value;$('pdf-direction').value='vertical';}else $('pdf-direction').value=savedDirection;comparison=value;if(pdf)arrange();}
  return {open,setComparison};
})();
