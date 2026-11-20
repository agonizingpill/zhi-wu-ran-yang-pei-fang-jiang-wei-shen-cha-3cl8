import {escape,decimal,localTime} from '../utils.js';
async function fetchShared(token){const r=await fetch('/api/shared/atlas?token='+encodeURIComponent(token));const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'无法访问图谱');return d;}
function plot(a){const xs=a.points.map(p=>p.x),ys=a.points.map(p=>p.y),minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);return `<svg viewBox="0 0 640 330" aria-label="外协染样 PCA 图谱"><path d="M35 15V300H620" stroke="currentColor" fill="none" opacity=".3"/>${a.points.map(p=>`<circle cx="${40+(p.x-minx)/(maxx-minx||1)*560}" cy="${280-(p.y-miny)/(maxy-miny||1)*240}" r="6" fill="oklch(55% .12 250)"><title>${escape(p.lot)} · ${decimal(p.x)}, ${decimal(p.y)}</title></circle><text x="${46+(p.x-minx)/(maxx-minx||1)*560}" y="${274-(p.y-miny)/(maxy-miny||1)*240}" font-size="10">${escape(p.lot)}</text>`).join('')}<text x="550" y="324" font-size="12">PC1</text><text x="5" y="15" font-size="12">PC2</text></svg>`;}
export async function show(token){
 const app=document.querySelector('#app');
 app.innerHTML=`<section class="login"><div class="login-form"><div class="eyebrow">栖色织研 / 外协只读</div><h2>外协染样图谱</h2><p class="hint">正在核验访问令牌…</p></div></section>`;
 try{
  const a=await fetchShared(token||'');
  app.innerHTML=`<header><div class="brand">栖色织研<small>外协染样图谱 / 只读视图</small></div><div class="account">${escape(a.factory)}</div></header><main style="padding:24px;max-width:960px;margin:0 auto"><section class="panel"><h2>${escape(a.factory)} · 获准染样 PCA 图谱</h2><div class="metricline"><div><strong>${decimal(a.explained_variance[0]*100)}%</strong>PC1 解释方差</div><div><strong>${decimal(a.explained_variance[1]*100)}%</strong>PC2 解释方差</div><div><strong>${decimal(a.reconstruction_mse,4)}</strong>标准化重构 MSE</div></div><div class="atlas-wrap">${plot(a)}</div><p class="hint">${escape(a.method)} · ${a.count} 张获准染样 · 发布于 ${localTime(a.published_at)}<br>本视图仅含贵厂获准染样坐标，不涉及厂内配方与其他外协厂数据。</p></section></main>`;
 }catch(e){
  app.innerHTML=`<section class="login"><div class="login-form"><div class="eyebrow">栖色织研 / 外协只读</div><h2>外协染样图谱</h2><p class="hint">${escape(e.message)}</p></div></section>`;
 }
}
