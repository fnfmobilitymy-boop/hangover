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
// Touch-driven light rays use passive events to preserve native scrolling.
(()=>{
 const preference=matchMedia('(prefers-reduced-motion: reduce)');
 const canvas=document.createElement('canvas');canvas.id='touch-light';canvas.setAttribute('aria-hidden','true');document.body.append(canvas);
 const context=canvas.getContext('2d');if(!context){canvas.remove();return}
 let beams=[],frame=0,lastPoint=null,lastSpawn=0;
 function resize(){const ratio=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(innerWidth*ratio);canvas.height=Math.round(innerHeight*ratio);context.setTransform(ratio,0,0,ratio,0,0);beams=[]}
 function clear(){beams=[];lastPoint=null;if(frame)cancelAnimationFrame(frame);frame=0;context.clearRect(0,0,innerWidth,innerHeight)}
 function allowed(target){return !preference.matches&&!document.hidden&&!target.closest('input,textarea,select,[contenteditable],#brand-intro')}
 function add(x,y,previous,burst=false){const now=performance.now();if(!burst&&now-lastSpawn<30)return;lastSpawn=now;beams.push({x,y,fromX:previous?previous.x:x-45,fromY:previous?previous.y:y+60,start:now,duration:burst?720:490,burst});if(beams.length>20)beams.shift();if(!frame)frame=requestAnimationFrame(draw)}
 function draw(now){frame=0;context.clearRect(0,0,innerWidth,innerHeight);beams=beams.filter(beam=>now-beam.start<beam.duration);for(const beam of beams){const progress=Math.max(0,(now-beam.start)/beam.duration),opacity=(1-progress)*(beam.burst?.65:.42);const endX=beam.burst?beam.x+100*progress:beam.x,endY=beam.burst?beam.y-130*progress:beam.y;const gradient=context.createLinearGradient(beam.fromX,beam.fromY,endX,endY);gradient.addColorStop(0,'rgba(186,201,255,0)');gradient.addColorStop(.45,`rgba(234,195,224,${opacity*.45})`);gradient.addColorStop(.85,`rgba(255,226,183,${opacity})`);gradient.addColorStop(1,'rgba(255,245,220,0)');context.save();context.strokeStyle=gradient;context.lineCap='round';context.lineWidth=beam.burst?2:1.4;context.shadowBlur=15;context.shadowColor='rgba(245,208,194,.8)';context.beginPath();context.moveTo(beam.fromX,beam.fromY);context.lineTo(endX,endY);context.stroke();context.restore();const radius=(beam.burst?46:27)*(1+progress*.5),glow=context.createRadialGradient(beam.x,beam.y,0,beam.x,beam.y,radius);glow.addColorStop(0,`rgba(255,242,210,${opacity*.35})`);glow.addColorStop(.3,`rgba(219,193,242,${opacity*.12})`);glow.addColorStop(1,'rgba(219,193,242,0)');context.fillStyle=glow;context.fillRect(beam.x-radius,beam.y-radius,radius*2,radius*2)}if(beams.length)frame=requestAnimationFrame(draw)}
 document.addEventListener('pointerdown',event=>{if(!allowed(event.target))return;lastPoint={x:event.clientX,y:event.clientY};add(event.clientX,event.clientY,null,true)},{passive:true});
 document.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||!event.buttons||!allowed(event.target))return;const point={x:event.clientX,y:event.clientY};add(point.x,point.y,lastPoint);lastPoint=point},{passive:true});
 document.addEventListener('touchmove',event=>{if(!event.touches[0]||!allowed(event.target))return;const touch=event.touches[0],point={x:touch.clientX,y:touch.clientY};add(point.x,point.y,lastPoint);lastPoint=point},{passive:true});
 document.addEventListener('touchend',()=>lastPoint=null,{passive:true});document.addEventListener('pointerup',()=>lastPoint=null,{passive:true});document.addEventListener('visibilitychange',()=>{if(document.hidden)clear()});preference.addEventListener('change',clear);addEventListener('resize',resize);resize();
})();
