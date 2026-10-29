// Show the standalone KENNY opening once per tab visit, not on every store page.
(()=>{
 clearTimeout(window.kennyIntroFallback);
 let seen=false;try{seen=sessionStorage.getItem('kenny-intro-seen')==='1'}catch{}
 if(seen){document.documentElement.classList.remove('intro-pending');return}
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const overlay=document.createElement('div');overlay.id='brand-intro';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-labelledby','intro-accessible-title');overlay.tabIndex=-1;
 const chinese=document.documentElement.lang==='zh-CN';
 overlay.innerHTML=`<div class="intro-rays" aria-hidden="true"></div><div class="intro-logo"><span class="intro-caption">THE NEXT WAVE STARTS HERE</span><h2 class="intro-title" id="intro-accessible-title"><span>KENNY</span></h2><span class="intro-signature">Keep moving.</span><span class="intro-line" aria-hidden="true"></span></div><div class="intro-glitch" aria-hidden="true"></div><div class="intro-bottom"><span>KENNY / BRAND OPENING</span><span>${chinese?'即将进入商城':document.documentElement.lang==='ms'?'MEMASUKI KEDAI':'ENTERING THE STORE'}</span></div><div class="intro-progress" aria-hidden="true"></div>`;
 const previousFocus=document.activeElement,previousOverflow=document.body.style.overflow;let finished=false,timer;
 const inertStates=[...document.body.children].filter(el=>!['SCRIPT','STYLE'].includes(el.tagName)).map(el=>[el,el.inert]);
 inertStates.forEach(([el])=>el.inert=true);document.body.append(overlay);document.body.style.overflow='hidden';document.documentElement.classList.remove('intro-pending');
 function finish(){if(finished)return;finished=true;clearTimeout(timer);try{sessionStorage.setItem('kenny-intro-seen','1')}catch{}overlay.classList.add('leaving');overlay.setAttribute('aria-hidden','true');document.removeEventListener('keydown',onKey);setTimeout(()=>{overlay.remove();inertStates.forEach(([el,state])=>el.inert=state);document.body.style.overflow=previousOverflow;document.dispatchEvent(new Event('kenny-intro-finished'));if(previousFocus&&previousFocus!==document.body&&previousFocus.isConnected)previousFocus.focus({preventScroll:true})},reduced?0:450)}
 function onKey(e){if(e.key==='Escape'){e.preventDefault();finish()}if(e.key==='Tab'){e.preventDefault();overlay.focus()}}
 document.addEventListener('keydown',onKey);overlay.focus({preventScroll:true});timer=setTimeout(finish,reduced?700:2900);
})();
