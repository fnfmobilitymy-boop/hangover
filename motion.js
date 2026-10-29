// Small, independent motion layers preserve the centered hero geometry.
(()=>{
 const preference=matchMedia('(prefers-reduced-motion: reduce)');
 function arm(){document.body.classList.add('motion-ready')}
 if(document.documentElement.classList.contains('intro-pending'))document.addEventListener('kenny-intro-finished',arm,{once:true});else arm();
 const stage=document.querySelector('.cinema-stage');let pointerFrame=0;
 if(stage){stage.addEventListener('pointermove',event=>{if(preference.matches||event.pointerType!=='mouse'||pointerFrame)return;const bounds=stage.getBoundingClientRect(),x=Math.max(35,Math.min(65,(event.clientX-bounds.left)/bounds.width*100)),y=Math.max(30,Math.min(60,(event.clientY-bounds.top)/bounds.height*100));pointerFrame=requestAnimationFrame(()=>{stage.style.setProperty('--light-x',x+'%');stage.style.setProperty('--light-y',y+'%');pointerFrame=0})},{passive:true});stage.addEventListener('pointerleave',()=>{stage.style.setProperty('--light-x','50%');stage.style.setProperty('--light-y','45%')})}
 const visibility=new IntersectionObserver(entries=>entries.forEach(entry=>entry.target.classList.toggle('motion-paused',!entry.isIntersecting)),{rootMargin:'60px'});
 document.querySelectorAll('.cinema-stage,.cinema-marquee,.editorial-craft-art').forEach(element=>visibility.observe(element));
 document.addEventListener('visibilitychange',()=>document.querySelectorAll('.cinema-stage,.cinema-marquee,.editorial-craft-art').forEach(element=>{if(document.hidden)element.classList.add('motion-paused');else{const bounds=element.getBoundingClientRect();element.classList.toggle('motion-paused',bounds.bottom< -60||bounds.top>innerHeight+60)}}));
})();
