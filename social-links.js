// Add your public profile URLs here when ready. Empty entries stay non-clickable.
window.KENNY_SOCIAL_LINKS = {
  facebook: '',
  tiktok: '',
  instagram: '',
  threads: '',
  telegram: ''
};
const socialIcons = {
  facebook: {name:'Facebook', svg:'<path d="M14.4 22v-8.2h2.8l.4-3.2h-3.2v-2c0-.9.2-1.6 1.6-1.6h1.7V4.1c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H8.2v3.2H11V22z"/>'},
  tiktok: {name:'TikTok', svg:'<path d="M15.7 2c.3 2.4 1.7 4 4.3 4.2v3.5a9.2 9.2 0 0 1-4.3-1.3v7.2a6.3 6.3 0 1 1-5.4-6.2v3.6a2.8 2.8 0 1 0 1.9 2.6V2z"/>'},
  instagram: {name:'Instagram', svg:'<rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="4.1" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17.5" cy="6.7" r="1.1"/>'},
  threads: {name:'Threads', svg:'<path d="M19.1 8C18.2 4.5 15.8 3 12.3 3 6.8 3 4.4 6.3 4.4 12s2.5 9 7.9 9c4.4 0 7.3-2.2 7.3-5.7 0-3.3-2.9-5.2-6.4-5.2-3.2 0-5.1 1.5-5.1 3.6 0 1.8 1.4 2.9 3.4 2.9 2.8 0 4-2 4-4.9 0-3.3-1.4-4.9-3.9-4.9-1.4 0-2.5.5-3.3 1.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'},
  telegram: {name:'Telegram', svg:'<path d="m21.4 3.2-3.1 17.2c-.2 1.2-.9 1.5-1.8.9L11.8 18l-2.3 2.3c-.3.3-.5.5-.9.5l.3-4.8 8.7-7.8c.4-.3-.1-.5-.6-.2L6.2 14.7l-4.6-1.4c-1-.3-1-1 .2-1.5L20 3c.8-.3 1.5.2 1.4.2z"/>'}
};
Object.entries(socialIcons).forEach(([key,{name,svg}])=>{
  const raw=window.KENNY_SOCIAL_LINKS[key];let url=null;
  try{const parsed=new URL(raw);if(parsed.protocol==='https:')url=parsed.href}catch{}
  const el=document.createElement(url?'a':'span');el.className='social-link';
  el.setAttribute('aria-label',name);el.title=url?name:`${name} — Link coming soon`;
  if(url){el.href=url;el.target='_blank';el.rel='noopener noreferrer'}else{el.setAttribute('aria-disabled','true');el.setAttribute('role','img')}
  el.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${svg}</svg>`;
  document.querySelector('#social-links').append(el);
});
