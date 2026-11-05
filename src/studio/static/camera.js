/* Local rear-camera preview: no recording, streaming server or upload. */
(() => {
  const panel=document.getElementById('conductor-camera'),video=document.getElementById('camera-video'),button=document.getElementById('camera-toggle');
  let stream=null,drag=null,request=0;
  function stop(){request++;stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;panel.hidden=true;button.setAttribute('aria-pressed','false');}
  button.onclick=async()=>{
    if(stream){stop();return;}
    if(!navigator.mediaDevices?.getUserMedia){alert('Camera needs HTTPS or localhost and a supported browser.');return;}
    const ticket=++request;button.disabled=true;
    try{
      const next=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:640},height:{ideal:480}},audio:false});
      if(ticket!==request){next.getTracks().forEach(t=>t.stop());return;}
      stream=next;video.srcObject=stream;panel.hidden=false;await video.play();button.setAttribute('aria-pressed','true');
    }catch(e){stop();alert(`Camera unavailable: ${e.message}`);}finally{button.disabled=false;}
  };
  document.getElementById('camera-close').onclick=stop;
  const handle=document.getElementById('camera-handle');
  handle.onpointerdown=e=>{if(e.target.closest('button'))return;const r=panel.getBoundingClientRect();drag={x:e.clientX-r.left,y:e.clientY-r.top};handle.setPointerCapture(e.pointerId);};
  handle.onpointermove=e=>{if(!drag)return;panel.style.left=`${Math.max(0,Math.min(innerWidth-panel.offsetWidth,e.clientX-drag.x))}px`;panel.style.top=`${Math.max(0,Math.min(innerHeight-panel.offsetHeight,e.clientY-drag.y))}px`;panel.style.right='auto';panel.style.bottom='auto';};
  handle.onpointerup=handle.onpointercancel=()=>drag=null;
  window.addEventListener('pagehide',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
