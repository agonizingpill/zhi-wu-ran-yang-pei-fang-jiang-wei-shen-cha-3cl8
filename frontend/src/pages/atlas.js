import {store,refresh} from '../store.js';import {api,session} from '../api.js';import {heading,recipeOptions,swatchTable} from '../components/common.js';import {escape,decimal,notify,formData,wait,localTime} from '../utils.js';
function plot(result){const xs=result.points.map(p=>p.x),ys=result.points.map(p=>p.y),minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);return `<svg viewBox="0 0 640 330" aria-label="PCA 染样图谱"><path d="M35 15V300H620" stroke="currentColor" fill="none" opacity=".3"/>${result.points.map(p=>`<circle cx="${40+(p.x-minx)/(maxx-minx||1)*560}" cy="${280-(p.y-miny)/(maxy-miny||1)*240}" r="5" fill="oklch(${43+p.recipe_id*7}% .10 ${245-p.recipe_id*65})"><title>${escape(p.lot)} · ${decimal(p.x)}, ${decimal(p.y)}</title></circle>`).join('')}<text x="550" y="324" font-size="12">PC1</text><text x="5" y="15" font-size="12">PC2</text></svg>`;}
let factoryId=null,detail=null,loading=false;
async function loadFactory(id,rerender){loading=true;try{const [grants,pubs]=await Promise.all([api('/factories/'+id+'/grants'),api('/factories/'+id+'/publications')]);let atlas=null,atlasMsg='';try{atlas=await api('/factories/'+id+'/atlas');}catch(e){atlasMsg=e.message;}detail={id,grants,pubs,atlas,atlasMsg};}catch(e){detail={id,error:e.message};}loading=false;rerender();}
function factoryAtlasView(d){
 if(d.error)return `<div class="empty">${escape(d.error)}</div>`;
 let body;
 if(d.atlas)body=`<div class="metricline"><div><strong>${decimal(d.atlas.result.explained_variance[0]*100)}%</strong>PC1 解释方差</div><div><strong>${decimal(d.atlas.result.explained_variance[1]*100)}%</strong>PC2 解释方差</div><div><strong>${decimal(d.atlas.result.reconstruction_mse,4)}</strong>标准化重构 MSE</div></div><div class="atlas-wrap">${plot(d.atlas.result)}</div><p class="hint">${escape(d.atlas.result.method)} · ${d.atlas.result.count} 张获准染样 · epoch ${d.atlas.epoch} · 发布于 ${localTime(d.atlas.published_at)}</p>`;
 else body=`<div class="empty">${escape(d.atlasMsg||'尚未生成图谱')}</div>`;
 const pubs=d.pubs.length?d.pubs.map(p=>`<tr><td>${localTime(p.created_at)}</td><td>${p.epoch}</td><td>${p.valid?'<span class="status approved">有效</span>':'<span class="status rejected">已失效</span>'}</td><td>${p.count} 张</td><td>${p.swatches.map(s=>escape(s.lot)).join('、')}</td></tr>`).join(''):'<tr><td colspan="5">尚无图谱发布记录</td></tr>';
 return body+`<h3>图谱档案回查</h3><p class="hint">厂内可回查每次出图使用过哪些染样；撤权后旧图对外失效，档案仍保留。</p><table><thead><tr><th>发布时间</th><th>epoch</th><th>状态</th><th>染样数</th><th>用过的染样</th></tr></thead><tbody>${pubs}</tbody></table>`;
}
function factoryPanel(){
 const role=session().role,admin=role==='admin',editor=role!=='viewer';
 const fs=store.factories||[];
 const f=fs.find(x=>x.id===factoryId)||fs[0];
 if(f)factoryId=f.id;
 const rows=fs.map(x=>`<tr class="${x.id===factoryId?'active':''}" data-fid="${x.id}" style="cursor:pointer"><td>${escape(x.code)}</td><td>${escape(x.name)}</td><td>${x.active?'<span class="status approved">授权中</span>':'<span class="status rejected">已撤权</span>'}</td><td>${x.epoch}</td><td>${x.grants}</td><td>${x.publications}</td></tr>`).join('');
 const left=`<h3>外协厂档案</h3><table><thead><tr><th>编号</th><th>名称</th><th>状态</th><th>epoch</th><th>染样</th><th>图谱</th></tr></thead><tbody>${rows||'<tr><td colspan="6">尚未建立外协厂档案</td></tr>'}</tbody></table>${admin?`<form id="factory-form"><label>外协厂编号<input name="code" required placeholder="PARTNER-XX"></label><label>外协厂名称<input name="name" required placeholder="外协厂名称"></label><button class="primary">建立外协厂档案</button></form>`:''}`;
 if(!f)return `<section class="panel"><h2>外协厂图谱授权</h2><p class="hint">主管按厂授权实测染样；图谱只用获准光谱拟合，坐标与解释方差和未授权染样无关。撤权后已生成的图与排队任务即刻失效，其他厂不受影响。</p><div class="split" style="grid-template-columns:1fr 1.4fr"><div>${left}</div><div><div class="empty">请先由主管建立外协厂档案</div></div></div></section>`;
 const d=detail&&detail.id===f.id?detail:null;
 const granted=d&&!d.error?d.grants:[];
 const share=`${location.origin}/#shared?token=${f.token}`;
 const right=`<h3>${escape(f.code)} · ${escape(f.name)}</h3>
 <p class="hint">外协只读链接（不含配方浓度与配方编号）：<code>${escape(share)}</code></p>
 ${d?`<p class="hint">已授权染样 ${granted.length} 张：${granted.map(g=>escape(g.lot)).join('、')||'（无）'}</p>`:''}
 ${admin&&f.active?`<form id="grant-form"><label>追加授权实测染样（按住 Ctrl 多选）<select name="swatch_ids" multiple size="8">${store.swatches.filter(s=>s.measured&&!granted.some(g=>g.swatch_id===s.id)).map(s=>`<option value="${s.id}">${escape(s.lot)}</option>`).join('')}</select></label><button class="primary">授权所选染样</button></form>`:''}
 <div class="actions" style="display:flex;gap:10px;margin:12px 0">
 ${admin?(f.active?`<button id="revoke" class="danger">撤回授权</button>`:`<button id="authorize" class="primary">重新授权</button>`):''}
 ${editor?`<button id="run-factory-atlas" class="primary" ${!f.active||f.grants<3?'disabled':''}>生成外协图谱</button>`:''}
 </div>
 ${!f.active?'<p class="hint">授权已撤回：已生成的图谱与排队任务全部失效，重新授权后需重新出图。</p>':f.grants<3?`<p class="hint">缺样：获准实测染样 ${f.grants} 张，PCA 至少需要 3 张，请先由主管授权更多染样。</p>`:''}
 <div id="factory-atlas">${d?factoryAtlasView(d):'<span class="hint">正在读取图谱档案…</span>'}</div>`;
 return `<section class="panel"><h2>外协厂图谱授权</h2><p class="hint">主管按厂授权实测染样；图谱只用获准光谱拟合，坐标与解释方差和未授权染样无关。撤权后已生成的图与排队任务即刻失效，其他厂不受影响。</p><div class="split" style="grid-template-columns:1fr 1.4fr"><div>${left}</div><div>${right}</div></div></section>`;
}
export function render(){const a=store.atlas;return heading('03','让三十六个波段，落在同一张图上','Python worker 标准化全部染样，再做二维 PCA。距离仅用于观察，复染仍以实测 ΔE76 审签。')+`<div class="split" style="grid-template-columns:1.5fr .8fr"><section class="panel"><h2>光谱群落</h2><button id="run-atlas" class="primary" ${session().role==='viewer'?'disabled':''}>重新计算 PCA 图谱</button><div class="metricline">${a?`<div><strong>${decimal(a.explained_variance[0]*100)}%</strong>PC1 解释方差</div><div><strong>${decimal(a.explained_variance[1]*100)}%</strong>PC2 解释方差</div><div><strong>${decimal(a.reconstruction_mse,4)}</strong>标准化重构 MSE</div>`:'<span class="hint">计算完成后显示解释方差、重构误差与所有染样坐标</span>'}</div><div class="atlas-wrap">${a?plot(a):'<div class="empty">点击计算，worker 将从数据库读取 36 波段实测数据。<br>至少需要三张染样。</div>'}</div><p class="hint">${a?escape(a.method)+' · '+a.count+' 张染样':'计算任务由 Redis 队列交给 Python worker；前端不计算坐标。'}</p></section><section class="panel"><h2>挑选复染配对</h2><form id="trial-form"><label>配方<select name="recipe_id">${recipeOptions(store.recipes)}</select></label><label>目标染样<select name="reference_swatch_id">${store.swatches.map(s=>`<option value="${s.id}">${escape(s.lot)}</option>`).join('')}</select></label><label>候选染样<select name="candidate_swatch_id">${store.swatches.map((s,i)=>`<option value="${s.id}" ${i===1?'selected':''}>${escape(s.lot)}</option>`).join('')}</select></label><label>工艺说明<input name="note" value="2026-11-17 亚麻复染审查"></label><button class="primary" ${session().role==='viewer'?'disabled':''}>建立复染试验</button></form><div class="rule">两张染样必须来自同一配方。ΔE = √(ΔL² + Δa² + Δb²)。</div></section></div>`+factoryPanel();}
export function bind(rerender){
 const f=store.factories.find(x=>x.id===factoryId)||store.factories[0];
 if(f){factoryId=f.id;if((!detail||detail.id!==f.id)&&!loading)loadFactory(f.id,rerender);}
 document.querySelector('#run-atlas').onclick=async e=>{e.target.disabled=true;e.target.textContent='worker 计算中…';try{const j=await api('/atlas','POST');for(let i=0;i<40;i++){let r=await api('/atlas/'+j.job_id);if(r.state==='done'){store.atlas=r.result;rerender();notify('图谱已由 Python worker 计算完成');return;}if(r.state==='failed')throw new Error(r.error);await wait(500);}throw new Error('计算尚未完成，请稍后重试');}catch(err){notify(err.message);e.target.disabled=false;e.target.textContent='重新计算 PCA 图谱';}};
 document.querySelector('#trial-form').onsubmit=async e=>{e.preventDefault();try{let d=formData(e.target);['recipe_id','reference_swatch_id','candidate_swatch_id'].forEach(k=>d[k]=Number(d[k]));let t=await api('/trials','POST',d);await refresh();notify('试验 #'+t.id+' 已建立，ΔE '+decimal(t.delta_e));location.hash='trials';}catch(err){notify(err.message);}};
 document.querySelectorAll('tr[data-fid]').forEach(tr=>tr.onclick=()=>{factoryId=Number(tr.dataset.fid);rerender();});
 const factoryForm=document.querySelector('#factory-form');
 if(factoryForm)factoryForm.onsubmit=async e=>{e.preventDefault();try{const x=await api('/factories','POST',formData(e.target));await refresh();factoryId=x.id;detail=null;rerender();notify('外协厂 '+x.code+' 已建立，可将只读链接交给对方');}catch(err){notify(err.message);}};
 const grantForm=document.querySelector('#grant-form');
 if(grantForm)grantForm.onsubmit=async e=>{e.preventDefault();try{const ids=new FormData(e.target).getAll('swatch_ids').map(Number);if(!ids.length)throw new Error('请先选择要授权的染样');await api('/factories/'+factoryId+'/grants','POST',{swatch_ids:ids});await refresh();detail=null;rerender();notify('已授权 '+ids.length+' 张实测染样');}catch(err){notify(err.message);}};
 const revoke=document.querySelector('#revoke');
 if(revoke)revoke.onclick=async()=>{try{await api('/factories/'+factoryId+'/revoke','POST');await refresh();detail=null;rerender();notify('授权已撤回：该厂已生成的图谱与排队任务即刻失效');}catch(err){notify(err.message);}};
 const authorize=document.querySelector('#authorize');
 if(authorize)authorize.onclick=async()=>{try{await api('/factories/'+factoryId+'/authorize','POST');await refresh();detail=null;rerender();notify('已重新授权，请重新生成图谱');}catch(err){notify(err.message);}};
 const run=document.querySelector('#run-factory-atlas');
 if(run)run.onclick=async e=>{e.target.disabled=true;e.target.textContent='worker 计算中…';try{const j=await api('/factories/'+factoryId+'/atlas','POST');for(let i=0;i<40;i++){let r=await api('/factories/'+factoryId+'/jobs/'+j.job_id);if(r.state==='done'){await refresh();detail=null;rerender();notify('外协图谱已发布，仅含获准染样');return;}if(r.state==='failed')throw new Error(r.error);if(r.state==='revoked')throw new Error(r.detail||r.error||'授权已撤回，任务失效');await wait(500);}throw new Error('计算尚未完成，请稍后重试');}catch(err){notify(err.message);await refresh();detail=null;rerender();}};
}
