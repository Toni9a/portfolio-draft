"use strict";
// Footer flower from the Codex SITE-HANDOFF (fixed footer settings). Video path is absolute because blog.html is served at /blog/<slug>.
const canvas=document.querySelector('#flower'),ctx=canvas.getContext('2d',{alpha:false});
const sample=document.createElement('canvas'),sc=sample.getContext('2d',{willReadFrequently:true});
const status=document.querySelector('#status');
// Fixed from Toni's flower-study screenshot for this footer variant.
const settings={dither:30,glyph:22,scatter:40,size:20,glow:76,transparency:72};
let petalColour="cycle",cycleHue=225,cursorColour=[200,63,213];
const hueStops=[225,280,330,398,585];
function updateCycle(now){const phase=(now/4500)%4,index=Math.floor(phase);cycleHue=(hueStops[index]+(hueStops[index+1]-hueStops[index])*smooth(phase-index))%360;}
const petalHues={purple:280,pink:330,amber:38};
function recolour(r,g,b){
 if(petalColour==='blue')return [r,g,b];
 const max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min;
 if(delta<2||max!==b)return [r,g,b];
 const hue=60*((r-g)/delta+4);
 // Feather the blue selection to keep cyan/green leaves and neutral highlights intact.
 const mask=smooth((hue-200)/18)*smooth((265-hue)/20);
 if(mask===0)return [r,g,b];
 const h=(petalColour==='cycle'?cycleHue:petalHues[petalColour])/60,x=delta*(1-Math.abs(h%2-1));
 const rgb=h<1?[delta,x,0]:h<2?[x,delta,0]:h<3?[0,delta,x]:h<4?[0,x,delta]:h<5?[x,0,delta]:[delta,0,x];
 return [r+(rgb[0]+min-r)*mask,g+(rgb[1]+min-g)*mask,b+(rgb[2]+min-b)*mask];
}
let scatterShape="hexagon";
function shapeRadius(angle){if(scatterShape==="circle")return 1;const n=scatterShape==="triangle"?3:6,sector=2*Math.PI/n;const a=((angle+Math.PI/2+sector/2) % sector+sector)%sector-sector/2;const polygon=Math.cos(Math.PI/n)/Math.cos(a);return scatterShape==="hexagon"?polygon*(1+.12*Math.sin(angle*6+.7)+.045*Math.sin(angle*12)):polygon;}
const pointer={x:-10000,y:-10000,inside:false};
let w=0,h=0,dpr=1,cols=0,rows=0,step=3,box,parts=[],last=0,frame=0,hit=false,blend=false,swaps=0;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
function video(){const v=document.createElement('video');v.src='/assets/blog/hydrangea.mp4';v.muted=true;v.playsInline=true;v.preload='auto';v.addEventListener('error',()=>{status.hidden=false;status.textContent='The flower video could not load.'});return v;}
let front=video(),back=video();
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x)};
function hash(i){let n=Math.sin(i*127.1+311.7)*43758.5453;return n-Math.floor(n)}
function layout(){const rect=canvas.getBoundingClientRect();w=rect.width;h=rect.height;dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
 const mobile=w<650;const bw=mobile?w*.98:Math.min(w*.74,1180,(h-160)*1280/720),bh=bw*720/1280;
 box={x:mobile?w*.01:w-bw-w*.025,y:mobile?h*.34:Math.max(115,(h-bh)*.55),w:bw,h:bh};
 step=1.8+settings.glyph*.044;cols=Math.ceil(bw/step);rows=Math.ceil(bh/step);sample.width=cols;sample.height=rows;
 parts=Array.from({length:cols*rows},(_,i)=>({x:0,y:0,vx:0,vy:0,seed:hash(i),alpha:0}));}
canvas.addEventListener('pointermove',e=>{const r=canvas.getBoundingClientRect();pointer.x=e.clientX-r.left;pointer.y=e.clientY-r.top;pointer.inside=true;if(front.paused&&!reduced)front.play().catch(()=>{})});
canvas.addEventListener('pointerleave',()=>pointer.inside=false);canvas.addEventListener('pointerup',e=>{if(e.pointerType!=='mouse')pointer.inside=false});canvas.addEventListener('pointercancel',()=>pointer.inside=false);
new ResizeObserver(layout).observe(canvas);
async function start(){try{await Promise.all([front,back].map(v=>new Promise(resolve=>{if(v.readyState>=2)resolve();else v.addEventListener('loadeddata',resolve,{once:true})})));await front.play();if(reduced)front.pause();status.hidden=true;requestAnimationFrame(draw)}catch{status.textContent='Tap to start the flower';canvas.addEventListener('pointerdown',()=>{front.play().then(()=>{status.hidden=true;requestAnimationFrame(draw)})},{once:true})}}
function source(){const duration=front.duration,fade=1.1;
 if(!reduced&&duration&&front.currentTime>=duration-fade&&!blend){blend=true;back.currentTime=0;back.play().catch(()=>{})}
 sc.globalAlpha=1;sc.drawImage(front,0,0,cols,rows);
 if(blend){sc.globalAlpha=smooth((front.currentTime-(duration-fade))/fade);if(back.readyState>=2)sc.drawImage(back,0,0,cols,rows);sc.globalAlpha=1;
 if(front.ended||front.currentTime>=duration-.045){front.pause();const old=front;front=back;back=old;back.currentTime=0;blend=false;swaps++}}
 return sc.getImageData(0,0,cols,rows).data;}
function draw(now){requestAnimationFrame(draw);if(now-last<28)return;const dt=Math.min((now-last)/16.667||1,2.5);last=now;if(!cols||front.readyState<2)return;
 updateCycle(now);const pixels=source();ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);hit=false;let sourceHit=false;
 // The only visible flower is this particle pass. Neither decoder is in the DOM.
 for(let i=0;i<parts.length;i++){const p=parts[i],k=i*4,x=i%cols,y=(i/cols)|0;const r=pixels[k],g=pixels[k+1],b=pixels[k+2],bright=Math.max(r,g,b);
 const edge=smooth(Math.min(x/cols,(cols-1-x)/cols)/.065)*smooth(Math.min(y/rows,(rows-1-y)/rows)/.025);
 p.alpha=smooth((bright-9)/28)*edge;p.r=r;p.g=g;p.b=b;p.bx=box.x+(x+.5)*step;p.by=box.y+(y+.5)*step;
 if(pointer.inside&&p.alpha>.3&&bright>35&&Math.abs(p.bx-pointer.x)<=step/2&&Math.abs(p.by-pointer.y)<=step/2)sourceHit=true;
 
 }
 const scatter=settings.scatter*.07; // New 100 equals the original 7.
 const radius=5+settings.size*.6;
 if(pointer.inside&&sourceHit&&settings.scatter>0){
 ctx.fillStyle=`rgba(${cursorColour.join(',')},${1-settings.transparency/100})`;ctx.beginPath();
 for(let j=0;j<=120;j++){const a=j/120*Math.PI*2,r=radius*shapeRadius(a),x=pointer.x+Math.cos(a)*r,y=pointer.y+Math.sin(a)*r;if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.closePath();ctx.fill();
 }
 let moved=0,maxDisplacement=0;
 for(let i=0;i<parts.length;i++){const p=parts[i];let tx=0,ty=0;
 if(pointer.inside&&settings.scatter>0){const dx=p.bx-pointer.x,dy=p.by-pointer.y,dist=Math.hypot(dx,dy),localRadius=radius*shapeRadius(Math.atan2(dy,dx));if(dist<localRadius){const angle=Math.atan2(dy,dx)+(p.seed-.5)*.7,force=Math.pow(1-dist/localRadius,.8)*(35+scatter*2.2)*(localRadius/(25+scatter*.88))*(.65+p.seed*.85);tx=Math.cos(angle)*force;ty=Math.sin(angle)*force}}
 p.vx+=(tx-p.x)*.065*dt;p.vy+=(ty-p.y)*.065*dt;p.vx*=Math.pow(.69,dt);p.vy*=Math.pow(.69,dt);p.x+=p.vx*dt;p.y+=p.vy*dt;
 if(p.alpha<.015)continue;
 const displacement=Math.hypot(p.x,p.y);if(displacement>3)moved++;maxDisplacement=Math.max(maxDisplacement,displacement);
 const d=settings.dither/100,noise=(p.seed-.5)*d*25,levels=256-d*224;
 const quant=c=>Math.max(0,Math.min(255,Math.round((c+noise)/255*levels)/levels*255));
 const colour=recolour(p.r,p.g,p.b);
 ctx.fillStyle=`rgba(${quant(colour[0])},${quant(colour[1])},${quant(colour[2])},${p.alpha})`;
 const px=p.bx+p.x,py=p.by+p.y;
 if(p.seed<.005+d*.015&&Math.max(p.r,p.g,p.b)>50){const size=step*(1.2+settings.glyph*.008);ctx.font=`${size}px monospace`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(p.seed<.009?'+':'·',px,py)}else{const size=step*(1-d*(.09+p.seed*.18));ctx.fillRect(px-size/2,py-size/2,size,size)}
 }
 // Sample the actual rendered surface, including gaps inside glyphs. No silhouette approximation.
 if(pointer.inside&&pointer.x>=0&&pointer.x<w&&pointer.y>=0&&pointer.y<h){const picked=ctx.getImageData(Math.floor(pointer.x*dpr),Math.floor(pointer.y*dpr),1,1).data;hit=Math.max(picked[0],picked[1],picked[2])>35}
 // Keep the warm centre alive inside a displaced gap, but only within the source flower.
 if((hit||sourceHit)&&settings.glow>0){const r=30+settings.glow*.8,gradient=ctx.createRadialGradient(pointer.x,pointer.y,0,pointer.x,pointer.y,r);gradient.addColorStop(0,`rgba(${cursorColour.join(',')},${settings.glow/100*.9*(1-settings.transparency/100)})`);gradient.addColorStop(.35,`rgba(${cursorColour.join(',')},${settings.glow/100*.48*(1-settings.transparency/100)})`);gradient.addColorStop(1,`rgba(${cursorColour.join(',')},0)`);ctx.fillStyle=gradient;ctx.fillRect(pointer.x-r,pointer.y-r,r*2,r*2)}
 frame++;if(frame%10===0){canvas.dataset.loops=swaps;canvas.dataset.hit=hit;canvas.dataset.moved=moved;canvas.dataset.time=front.currentTime.toFixed(2)}window.flowerDiagnostics={frame,hit,moved,maxDisplacement,swaps,videoTime:front.currentTime,blend,settings:{...settings},box,particles:parts.length};}
layout();start();
