// Frontend membership flow only. No identity verification or real account service.
(async()=>{
 await window.kennyBackendReady;
 if(window.kennyBackend?.available){window.kennyInstallServerAuth();return}
 let pendingPurchase=null;
 function profile(){const saved=demoStorage.read('kenny-demo-profile',null);return saved&&typeof saved.name==='string'&&typeof saved.email==='string'?saved:null}
 function signedIn(){try{return !!profile()&&sessionStorage.getItem('kenny-demo-session')==='active'}catch{return false}}
 function refresh(){const active=signedIn(),label=document.querySelector('#member-label'),dot=document.querySelector('#member-dot');if(label)label.textContent=active?'Your profile':'Log in / Join';if(dot)dot.hidden=!active}
 function startSession(){try{sessionStorage.setItem('kenny-demo-session','active')}catch{}refresh();featureDialog.close();const resume=pendingPurchase;pendingPurchase=null;if(resume)setTimeout(resume,0)}
 window.kennyRequireMember=resume=>{if(signedIn())return true;pendingPurchase=resume;openUtility('member');return false};
 const previousOpen=openUtility;
 openUtility=function(type){if(type!=='member')return previousOpen(type);const saved=profile();
  if(!saved){previousOpen(type);const heading=document.querySelector('#feature-content h2');if(heading)heading.textContent='Register to keep moving.';const form=document.querySelector('#member-form');if(form){const note=document.createElement('p');note.className='member-gate-note';note.textContent='Register a demo profile to continue shopping. Registration starts a local demo session automatically.';form.before(note)}return}
  if(signedIn()){previousOpen(type);const links=document.querySelector('.member-links');if(links){const signOut=document.createElement('button');signOut.className='text-link';signOut.id='demo-sign-out';signOut.textContent='Log out';signOut.onclick=()=>{try{sessionStorage.removeItem('kenny-demo-session')}catch{}refresh();openUtility('member')};links.after(signOut)}return}
  const content=document.querySelector('#feature-content');content.innerHTML='<span class="eyebrow">KENNY / MEMBER ACCESS</span><h2>Welcome back.</h2><p>Log in to continue shopping.</p><p class="demo-notice">Demo login only. This restores a session in this browser without verifying identity. Real accounts require a connected authentication service.</p><div class="returning-profile"><strong id="returning-name" data-no-translate></strong><span id="returning-email" data-no-translate></span></div><button class="button dark" id="demo-login">One-click demo login ↗</button><button class="text-link" id="different-profile">Use a different demo profile</button>';
  document.querySelector('#returning-name').textContent=saved.name;document.querySelector('#returning-email').textContent=saved.email;document.querySelector('#demo-login').onclick=startSession;document.querySelector('#different-profile').onclick=()=>{demoStorage.write('kenny-demo-profile',null);try{sessionStorage.removeItem('kenny-demo-session')}catch{}refresh();openUtility('member')};if(!featureDialog.open)featureDialog.showModal();
 };
 document.addEventListener('submit',event=>{if(event.target.id!=='member-form')return;event.preventDefault();event.stopImmediatePropagation();const form=event.target;if(!form.reportValidity())return;const data=new FormData(form);demoStorage.write('kenny-demo-profile',{name:String(data.get('memberName')).trim(),email:String(data.get('memberEmail')).trim()});startSession()},true);
 document.addEventListener('DOMContentLoaded',refresh);document.addEventListener('kenny-language-change',refresh);addEventListener('storage',refresh);refresh();
 const checkout=document.querySelector('#checkout-content');if(checkout&&document.querySelector('#checkout-form')&&!signedIn()){
  checkout.hidden=true;const gate=document.createElement('div');gate.className='checkout-member-gate';gate.innerHTML='<span class="eyebrow">KENNY / MEMBERS FIRST</span><h2>One step before checkout.</h2><p>Please register or log in to continue your demo purchase.</p><button class="button dark" id="resume-member-checkout">Log in / Register ↗</button>';checkout.before(gate);
  const resume=()=>{if(!window.kennyRequireMember(()=>{checkout.hidden=false;gate.remove()}))return;checkout.hidden=false;gate.remove()};document.querySelector('#resume-member-checkout').onclick=resume;
  if(document.documentElement.classList.contains('intro-pending'))document.addEventListener('kenny-intro-finished',resume,{once:true});else setTimeout(resume,0);
 }
 document.addEventListener('submit',event=>{if(event.target.id==='checkout-form'&&!signedIn()){event.preventDefault();event.stopImmediatePropagation();window.kennyRequireMember(()=>event.target.requestSubmit())}},true);
})();
