/* Complete evidence workbench. Source records remain independent and traceable. */
(() => {
'use strict';
const D=window.FLAVOR_DATA,E=window.FLAVOR_EVIDENCE;
if(!D||!E||!window.FlavorFullEngine) return;
const engine=window.FlavorFullEngine.create(D,E),byId=new Map(D.ingredients.map(x=>[x.id,x]));
const $=id=>document.getElementById(id),get=id=>byId.get(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cat=i=>Array.isArray(D.categoryDisplayNames)?D.categoryDisplayNames[i]:D.categoryDisplayNames[D.categories[i]]||D.categories[i];
const palette=['#c8675b','#e4a344','#c38d9e','#859868','#54775f','#9ca275','#b88653','#926448','#ad9370','#7e8070','#c98160','#d8b671','#a8877c','#8b88a5'];
const domainLabels={aroma:'香气与描述',compound:'分子与气味',taste:'基本滋味',texture:'质地与口感',chemesthesis:'辣麻凉等刺激',process:'加工与状态',numeric:'原文明示数值',context:'条件与语境',relative:'相对主次与变化',pairing:'搭配关系'};
const categoryStatus=v=>v.status==='conflict'&&v.unknown>0?'来源分歧且含未知':statusLabels[v.status];
const statusLabels={marked:'来源一致有标示',unmarked:'来源一致未标示',conflict:'来源有分歧',unknown:'包含未知'};
const norm=s=>String(s??'').normalize('NFKC').replace(/\s+/g,'').toLocaleLowerCase();
const identity=x=>norm(x.displayName),findName=n=>D.ingredients.find(x=>x.name===n||x.displayName===n);
const standard=['草莓','奶油乳酪','烤葵花籽'].map(findName).filter(Boolean);
const evidenceById=new Map(E.records.map(r=>[r.id,r]));
const rawRows=new Map((E.dotSource?.rows||[]).map(r=>[r.row_id,r]));
const allRows=D.ingredients.flatMap(i=>i.records.map(r=>({...r,ingredientId:i.id,displayName:i.displayName,sourceName:i.name,searchText:i.searchText+' '+r.id+' '+r.tableId+' '+r.pdfPage})));
const profileCache=new Map(),compareCache=new Map(),evidenceCache=new Map();
const profile=id=>{if(!profileCache.has(id))profileCache.set(id,engine.sourceProfile(id));return profileCache.get(id);};
const evidenceFor=id=>{if(!evidenceCache.has(id))evidenceCache.set(id,engine.evidenceFor(id));return evidenceCache.get(id);};
const compare=(a,b)=>{const k=[a,b].join('|');if(!compareCache.has(k))compareCache.set(k,engine.compare(a,b));return compareCache.get(k);};
const pair=(a,b)=>engine.pairEvidence(a,b);
const state={view:'workbench',mode:'target',targets:new Set([0,2,7]),descriptors:new Set(),evidenceQuery:'',query:'',family:'fruit',selected:standard.map(x=>({id:x.id,grams:null})),anchor:(findName('奶油乳酪')||standard[0]).id,replacement:null,crossFamily:false,chart:'bars',visible:6,offset:0,seed:0,name:'草莓 · 完整证据提案',conditions:'',searchIndex:-1,searchMatches:[],searchVisible:30,researchQuery:'',researchDomain:'',researchPage:0,detailId:null};
const STORE='flavour-atelier-full-evidence-v2';let saved=[];
try{const current=localStorage.getItem(STORE);saved=JSON.parse(current||localStorage.getItem('flavour-atelier-recipes-v1')||'[]').filter(r=>Array.isArray(r.ingredients));}catch(_){}
const sourceLink=(page,label)=>`<a class="source-link" target="_blank" rel="noopener" href="../${encodeURIComponent(D.meta.sourcePdf)}#page=${Number(page)||1}">${esc(label||`PDF ${page} 页`)} ↗</a>`;
const jsonView=(v,title='完整原记录')=>`<details class="raw-record"><summary>${esc(title)}</summary><pre>${esc(JSON.stringify(v,null,2))}</pre></details>`;
const badge=(text,cls='')=>`<span class="small-badge ${cls}">${esc(text)}</span>`;
const artStatus=i=>window.FLAVOR_ART_META?.[i.id]?.status||'illustrated';
function image(i,cls='ingredient-thumb'){return `<img class="${cls}" src="${esc(window.FLAVOR_ASSETS?.[i.id]||i.image)}" width="320" height="320" loading="lazy" decoding="async" alt="${esc(i.displayName)}${artStatus(i)==='family_illustration'?'类别示意':'食材插画'}">`;}
function toast(s){$('toast').textContent=s;$('toast').hidden=false;$('toast').classList.add('is-visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>{$('toast').hidden=true;},3500);}
function download(value,name){const u=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),10000);}
function terms(){return [...state.descriptors].map(id=>E.source.taxonomy.find(t=>t.descriptor_id===id)?.descriptor).filter(Boolean).concat(state.evidenceQuery.trim()?[state.evidenceQuery.trim()]:[]);}
function mentionMatches(id,searchTerms=terms()){
 const ev=evidenceFor(id),test=r=>searchTerms.every(t=>norm(r.searchText||JSON.stringify(r.original)).includes(norm(t)));
 return {direct:ev.direct.filter(test),related:ev.related.filter(test),active:searchTerms.length>0};
}
function candidates(){
 const q=norm(state.query),anchor=state.mode==='replace'?state.anchor:state.selected[0]?.id;
 let list=D.ingredients.filter(i=>i.recommendationEligible&&(!state.family||i.visualFamily===state.family)&&(!q||norm(i.searchText).includes(q)));
 if(state.mode!=='target')list=list.filter(i=>i.id!==anchor);
 if(state.mode==='replace'&&!state.crossFamily)list=list.filter(i=>i.visualFamily===get(anchor).visualFamily);
 const result=list.map(item=>{const t=engine.targetMatch(item.id,[...state.targets]);const m=mentionMatches(item.id,state.mode==='target'?terms():[]);const c=state.mode==='replace'?compare(anchor,item.id):null;const links=state.mode==='compose'&&anchor?pair(anchor,item.id):null;return {item,target:t,mentions:m,comparison:c,links};}).filter(x=>!x.mentions.active||x.mentions.direct.length||x.mentions.related.length);
 result.sort((a,b)=>{
  if(state.mode==='replace'){const score=(b.comparison.min??-1)-(a.comparison.min??-1);if(score)return score;}
  if(state.mode==='compose'){const direct=Number(!!b.links?.included.length)-Number(!!a.links?.included.length);if(direct)return direct;}
  if(state.mode==='target'&&terms().length){const direct=b.mentions.direct.length-a.mentions.direct.length;if(direct)return direct;}
  if(state.mode==='target'){const all=b.target.matchedAllSource.length-a.target.matchedAllSource.length;if(all)return all;const some=b.target.markedSomeSource.length-a.target.markedSomeSource.length;if(some)return some;}
  return a.item.displayName.localeCompare(b.item.displayName,'zh-Hans')||a.item.id.localeCompare(b.item.id);
 });return result;
}
function pctRange(c){return c.min===null||c.min===undefined?'可比资料不足':`${Math.round(c.min*100)}${c.max!==c.min?'–'+Math.round(c.max*100):''}%`;}
function renderTargets(){
 $('targetCategories').innerHTML=D.categories.map((_,i)=>`<button type="button" class="aroma-chip ${state.targets.has(i)?'is-active':''}" data-category="${i}" aria-pressed="${state.targets.has(i)}" style="--aroma-color:${palette[i]}"><span class="aroma-dot"></span>${esc(cat(i))}${state.targets.has(i)?' ✓':''}</button>`).join('');
 $('descriptorTargets').innerHTML=[...state.descriptors].map(id=>`<button type="button" data-descriptor-remove="${id}">${esc(E.source.taxonomy.find(t=>t.descriptor_id===id)?.descriptor)} ×</button>`).join('');
}
function renderSelected(){
 const entries=state.mode==='replace'?[{id:state.anchor}]:state.selected;
 $('selectedIngredients').innerHTML=entries.map((x,index)=>{const i=get(x.id);return `<span class="selected-chip">${image(i,'selected-thumb')}<span>${esc(i.displayName)}</span>${state.mode==='compose'?(index===0?'<small>主食材</small>':`<button class="make-main" type="button" data-main="${i.id}">设为主食材</button>`):''}${state.mode==='replace'?'':`<button type="button" data-remove="${i.id}" aria-label="移除${esc(i.displayName)}">×</button>`}</span>`;}).join('')||'<span class="muted-hint">搜索一款食材开始；所有来源身份分别保留。</span>';
}
function renderCandidates(){
 const list=candidates(),offset=state.mode==='target'&&list.length?state.offset%list.length:0;const ordered=list.slice(offset).concat(list.slice(0,offset));
 $('candidateCount').textContent=`${list.length.toLocaleString()} 个来源条目`;
 $('candidateSummary').textContent=state.mode==='target'?'按全部来源一致命中、部分来源命中依次排序；同名条目不合并。':state.mode==='replace'?'展示全部来源版本的相似范围；按范围下界排序。':'显示全部直接配对记录；整体配方效应仍需试做。';
 $('candidateGrid').innerHTML=ordered.slice(0,state.visible).map(x=>{
 const i=x.item,p=profile(i.id),chosen=state.selected.some(y=>y.id===i.id);let label=`${x.target.matchedAllSource.length} 类一致命中 · ${x.target.markedSomeSource.length} 类部分来源标示`;
 if(state.mode==='replace')label=`${pctRange(x.comparison)} 标示相似范围`;
 if(state.mode==='compose')label=x.links?.included.length?`${x.links.included.length} 条直接配对依据`:'目前无可用直接配对依据';
 const detail=x.mentions.active?`${x.mentions.direct.length} 条同名/别名提及 · ${x.mentions.related.length} 条相关语境`:`${p.recordCount} 条记录 · ${p.variantCount} 种完整标示版本`;
 return `<article class="ingredient-card ${chosen?'is-selected':''}"><button type="button" class="card-image" data-detail="${i.id}" aria-label="查看${esc(i.displayName)}全部来源">${image(i,'ingredient-art')}${artStatus(i)==='family_illustration'?'<span class="art-method-badge">类别示意</span>':''}<span class="image-inspect">↗</span></button><div class="card-content"><span class="card-category">${esc(i.visualFamilyLabel)}</span><h3>${esc(i.displayName)}</h3><p class="card-match">${esc(label)}</p><p class="card-reason">${esc(detail)}</p><p class="identity-caption">原名 ${esc(i.name)} · ${i.id.slice(-6)}</p><div class="card-foot"><button class="text-button" data-detail="${i.id}" type="button">完整证据 ↗</button><button class="card-add" data-add="${i.id}" type="button" aria-label="${state.mode==='replace'?'比较':'加入'}${esc(i.displayName)}">${state.mode==='replace'?'比较':chosen?'已加入':'＋'}</button></div></div></article>`;
 }).join('')||'<div class="empty-state"><h3>当前筛选没有食材条目</h3><p>证据可能属于尚未精确关联的食材或不同处理状态。</p><button type="button" data-browse-mentions class="text-button">在全部属性证据中检索 ↗</button><button type="button" data-clear-filter class="text-button">清除筛选</button></div>';
 let more=$('loadMoreButton');if(!more){more=document.createElement('button');more.id='loadMoreButton';more.type='button';more.className='load-more';$('candidateGrid').after(more);more.onclick=()=>{state.visible+=12;renderCandidates();};}more.hidden=state.visible>=list.length;more.textContent=`继续加载 · 还有 ${Math.max(0,list.length-state.visible)} 项`;
}
function currentEntries(){return state.mode==='replace'?[{id:state.replacement||state.anchor,grams:null}]:state.selected;}
function renderRecipe(){
 const entries=currentEntries();$('recipeTitle').textContent=state.mode==='replace'?'多来源下的替换比较':'你的完整证据提案';
 $('recipeDescription').textContent=state.mode==='replace'?`${get(state.anchor).displayName} → ${get(state.replacement||state.anchor).displayName}`:'记录原料与条件；配比由你填写，生成时不预设克数。';
 $('recipeName').closest('.recipe-name-field').hidden=state.mode==='replace';$('recipeName').value=state.name;
 $('trialConditions').value=state.conditions;
 $('recipeIngredients').innerHTML=entries.map((x,index)=>{const i=get(x.id);return `<div class="recipe-row">${image(i,'recipe-thumb')}<div class="recipe-row-main"><button type="button" class="ingredient-name-button" data-detail="${i.id}">${esc(i.displayName)}</button><small>${state.mode==='compose'&&index===0?'主食材 · ':''}${profile(i.id).recordCount} 条来源，${profile(i.id).variantCount} 种标示版本</small></div>${state.mode==='replace'?badge('比较项'):`<label class="amount-input"><input type="number" min="0" step="any" value="${x.grams??''}" placeholder="待填" data-grams="${i.id}" aria-label="${esc(i.displayName)}试做克数"><span>g</span></label><button type="button" class="row-remove" data-remove="${i.id}" aria-label="移除${esc(i.displayName)}">×</button>`}</div>`;}).join('')||'<div class="recipe-empty">加入食材后，展开完整来源。</div>';
 $('recipeMeta').textContent=`${entries.length} 项原料 · ${entries.filter(x=>x.grams===null||x.grams===undefined).length} 项用量待填 · 香气强度预测：缺少配方实测数据`;
 renderChart();renderDimensions();renderPairEvidence();
}
function chartEntries(){return currentEntries();}
function donut(parts,center,caption){
 const total=parts.reduce((a,b)=>a+b.value,0);let angle=0;
 const paths=parts.filter(x=>x.value>0).map(part=>{const start=angle;angle+=part.value/total*360;const point=a=>[130+96*Math.cos((a-90)*Math.PI/180),130+96*Math.sin((a-90)*Math.PI/180)];const a=point(start),b=point(Math.min(angle,359.99999));return `<path d="M130 130 L${a[0]} ${a[1]} A96 96 0 ${part.value/total>.5?1:0} 1 ${b[0]} ${b[1]} Z" fill="${part.color}"><title>${esc(part.label)}：${part.value}${part.unit||''}</title></path>`;}).join('');
 return `<div class="donut-wrap"><svg viewBox="0 0 260 260" role="img" aria-label="${esc(caption)}">${total?paths:'<circle cx="130" cy="130" r="96" fill="#e4dfd4"/>'}<circle cx="130" cy="130" r="69" fill="#fffefa"/><text x="130" y="125" text-anchor="middle" class="donut-number">${esc(center)}</text><text x="130" y="150" text-anchor="middle" class="donut-subtitle">${esc(caption)}</text></svg></div><div class="donut-legend">${parts.map(x=>`<span><i style="background:${x.color}"></i><b>${esc(x.label)}</b><em>${esc(x.display??x.value)}</em></span>`).join('')}</div>`;
}
function renderChart(){
 const entries=chartEntries(),mix=engine.mixture(entries),c=$('aromaChart');
 document.querySelectorAll('[data-chart]').forEach(b=>{b.classList.toggle('is-active',b.dataset.chart===state.chart);b.setAttribute('aria-pressed',String(b.dataset.chart===state.chart));});
 c.className='aroma-chart '+(state.chart==='bars'?'aroma-chart-bars':'aroma-chart-donut');
 if(state.chart==='mass'){
  const missing=entries.filter(x=>!Number.isFinite(x.grams)||x.grams<=0),total=entries.reduce((n,x)=>n+(Number.isFinite(x.grams)?x.grams:0),0);
  c.innerHTML=missing.length||!total?`<div class="chart-empty"><strong>填写用量后显示质量占比</strong><p>${missing.length} 项用量未知。不会把空值补成预设比例。</p></div>`:donut(entries.map((x,i)=>({label:get(x.id).displayName,value:x.grams,color:palette[i%14],unit:'g',display:`${x.grams}g · ${(x.grams/total*100).toFixed(1)}%`})),Number(total.toFixed(2))+'g','已填写配方总质量');
  $('chartLegend').textContent='质量占比随克数变化；它描述配方用量。';$('profileNote').textContent='目前没有足够的配方浓度、释放、掩蔽和感官数据，无法计算混合后的香气强度。';c.setAttribute('aria-label',missing.length||!total?'质量占比暂不可计算，用量尚未完整填写':'配方质量占比，总质量'+total+'克');return;
 }
 const before=state.mode==='replace'?engine.mixture([{id:state.anchor}]):null;
 if(state.chart==='bars'){
  c.innerHTML=mix.categories.map((v,i)=>{const n=entries.length||1,yes=v.certainIngredientIds.length,mixed=v.variableIngredientIds.length,unknown=v.unknownIngredientIds.length,both=v.variableIngredientIds.filter(id=>v.unknownPresentIngredientIds.includes(id)).length;const left=before?.categories[i];
   const text=before?`${categoryStatus(profile(state.anchor).categories[i])} → ${categoryStatus(profile(entries[0].id).categories[i])}`:`一致有 ${yes} · 分歧 ${mixed-both} · 未知 ${unknown}${both?` · 分歧且未知 ${both}`:''}`;
   const title=[['一致有',v.certainIngredientIds],['分歧',v.variableIngredientIds],['含未知（可与分歧重叠）',v.unknownPresentIngredientIds],['一致未标',v.unmarkedIngredientIds]].map(([label,ids])=>label+'：'+(ids.map(id=>get(id).displayName).join('、')||'无')).join('；');
   return `<div class="full-aroma-row" title="${esc(title)}"><span class="aroma-bar-label"><i style="background:${palette[i]}"></i>${esc(cat(i))}</span><div class="full-aroma-track">${left?`<span class="previous-profile">前：${esc(categoryStatus(profile(state.anchor).categories[i]))}</span>`:''}<span class="full-aroma-fill" style="width:${yes/n*100}%;background:${palette[i]}"></span><span class="full-aroma-conflict" style="left:${yes/n*100}%;width:${(mixed-both)/n*100}%;--stripe:${palette[i]}"></span><span class="full-aroma-both" style="left:${(yes+mixed-both)/n*100}%;width:${both/n*100}%;--stripe:${palette[i]}"></span><span class="full-aroma-unknown" style="left:${(yes+mixed)/n*100}%;width:${unknown/n*100}%"></span></div><span class="full-aroma-value">${esc(text)}</span></div>`;
  }).join('');
  $('chartLegend').innerHTML='<span>实色：全部来源一致有标示</span><span>斜纹：来源分歧</span><span>点纹：未知</span><span>交错纹：分歧且未知</span>';
 }else{
  const totals={marked:0,conflict:0,conflictUnknown:0,unknown:0,unmarked:0};for(const entry of entries)for(const v of profile(entry.id).categories)totals[v.status==='conflict'&&v.unknown>0?'conflictUnknown':v.status]++;
  c.innerHTML=donut([{label:'一致有标示',value:totals.marked,color:'#687e5d'},{label:'来源分歧',value:totals.conflict,color:'#bd855d'},{label:'分歧且含未知',value:totals.conflictUnknown,color:'#946878'},{label:'含未知但无标示冲突',value:totals.unknown,color:'#9084a0'},{label:'一致未标示',value:totals.unmarked,color:'#d7d0c2'}],entries.length*14,'食材 × 类别判断');
  $('chartLegend').textContent='圆环展示全部来源的一致性构成；每款食材在每个类别计一次。';
 }
 $('profileNote').textContent='每项原料使用全部正式来源记录：有/未标冲突保留，未知不补0。同一食材的重复记录不会按次数放大香气。图表不预测浓度、强度或喜好。';
 c.setAttribute('aria-label','全部来源香气标示，包含一致、分歧与未知。'+mix.categories.map((v,i)=>`${cat(i)}：一致有${v.certainIngredientIds.length}，分歧${v.variableIngredientIds.length}，未知${v.unknownPresentIngredientIds.length}`).join('；'));
}
function evidenceCard(record,{compact=false,linkKind=''}={}){
 const r=record.original||record,id=record.id||r.evidence_id;const domains=(record.domains||[]).map(k=>domainLabels[k]||k);
 return `<article class="evidence-record-card" id="evidence-${esc(id)}"><div class="evidence-record-head"><span class="evidence-id">${esc(id)}</span><span>${sourceLink(r.pdf_page)}</span></div><h3>${esc(r.ingredient)}${r.state?`<small>${esc(r.state)}</small>`:''}</h3><div class="evidence-tags">${domains.map(x=>badge(x)).join('')}${linkKind?badge(linkKind,'context-badge'):''}</div><p class="evidence-attributes">${esc((r.attributes||[]).join(' · '))}</p><div class="evidence-relation">${typeof r.relation_or_value==='object'?`<pre>${esc(JSON.stringify(r.relation_or_value,null,2))}</pre>`:esc(r.relation_or_value)}</div>${r.note?`<p class="evidence-condition"><b>适用条件与限制</b> ${esc(r.note)}</p>`:''}${r.numeric_values?`<div class="evidence-numbers">${r.numeric_values.map(n=>numericCard(n)).join('')}</div>`:''}<p class="verification-label">${esc(r.verification||'核验状态未提供')}</p>${compact?`<button type="button" data-evidence="${esc(id)}" class="text-button">展开全部字段与关联范围 ↗</button>`:jsonView(r,'原记录全部字段（逐字段保留）')}</article>`;
}
function numericCard(n){
 const range=(n.minimum!==null&&n.minimum!==undefined)||(n.maximum!==null&&n.maximum!==undefined)?`${n.minimum??'?'} – ${n.maximum??'?'}`:n.value??'未给定';
 return `<article class="numeric-card"><span class="evidence-id">${esc(n.evidence_id||n.recordId||'原文数值')}</span><h3>${esc(n.ingredient||'')}${n.state?`<small>${esc(n.state)}</small>`:''}</h3><p>${esc(n.attribute||'')}</p><div class="numeric-value">${esc(n.operator||'')}${esc(range)} <small>${esc(n.unit||'单位未给定')}</small></div><dl><dt>分母 / 基准</dt><dd>${esc(n.denominator??'未提供')}</dd><dt>条件与限制</dt><dd>${esc(n.note??'未提供')}</dd></dl>${n.pdf_page?sourceLink(n.pdf_page):''}${jsonView(n,'保留原数值字段')}</article>`;
}
function renderDimensions(){
 const ids=state.mode==='replace'?[state.anchor,...(state.replacement?[state.replacement]:[])]:currentEntries().map(x=>x.id);
 $('dimensionEvidence').innerHTML=ids.map(id=>{const i=get(id),ev=evidenceFor(id);return `<div class="ingredient-evidence-summary"><div class="dimension-head">${image(i,'selected-thumb')}<strong>${esc(i.displayName)}</strong><button type="button" data-detail="${id}" class="text-button">查看全部 ↗</button></div><p>${ev.direct.length} 条同名/别名证据 · ${ev.related.length} 条相关语境（分开使用）</p><div class="dimension-statuses">${['aroma','compound','taste','texture','chemesthesis','process','numeric'].map(key=>{const count=ev.direct.filter(r=>r.domains.includes(key)).length;return `<span class="${count?'has-evidence':''}">${domainLabels[key]}<b>${count?count+' 条':'未精确关联'}</b></span>`;}).join('')}</div>${ev.direct.length?`<details><summary>展开全部 ${ev.direct.length} 条同名/别名证据</summary>${ev.direct.map(r=>evidenceCard(r,{compact:true,linkKind:'仍需核对原处理条件'})).join('')}</details>`:''}${ev.related.length?`<details><summary>另有 ${ev.related.length} 条相关语境，不能直接赋给此食材</summary>${ev.related.map(r=>evidenceCard(r,{compact:true,linkKind:'相关语境'})).join('')}</details>`:''}</div>`;}).join('')||'<p class="muted-hint">先加入食材；也可直接浏览全部253条证据。</p>';
}
function edgeCard(edge){const a=get(edge.mainId),b=get(edge.pairedId),sharedCategories=D.categories.filter((_,i)=>edge.shared[i]===1),unknownSharedCategories=D.categories.filter((_,i)=>edge.shared[i]===null);return `<div class="edge-record"><p><b>${esc(a?.displayName||edge.mainId)} → ${esc(b?.displayName||edge.pairedId)}</b> ${sourceLink(edge.sourceRef?.pdfPage)}</p><p>表号 ${esc(edge.tableId)} · ${edge.included?'可用于候选关系':'保留记录，未用于推荐'}</p><div class="dot-inline">${D.categories.map((_,i)=>`<span title="${esc(cat(i))}：${edge.shared[i]===null?'未知':edge.shared[i]?'原表标共享':'原表未标共享'}" class="mini-dot ${edge.shared[i]===1?'shared':edge.shared[i]===null?'unknown':''}" style="--dot:${palette[i]}">${edge.shared[i]===null?'?':''}</span>`).join('')}</div><p>${sharedCategories.length?'共享标示：'+esc(sharedCategories.join('、')):'原表未标出已辨识的共享类别'}${unknownSharedCategories.length?'；未知：'+esc(unknownSharedCategories.join('、')):''}</p>${jsonView(edge.original||edge,'此配对原记录全部字段')}</div>`;}
function renderPairEvidence(){
 if(state.mode==='replace'){
  if(!state.replacement){$('evidenceList').innerHTML='<p class="source-note">选择替代项后查看全部版本的比较范围。</p>';return;}
  const c=compare(state.anchor,state.replacement);$('evidenceList').innerHTML=`<div class="evidence-item"><span class="evidence-kicker">全部来源版本逐一比较</span><strong>${pctRange(c)} 已知标示相似范围</strong><p>这是可辨识类别的交并比范围，未按频次平均。包含未知的版本单独保留，分子、滋味、质地与工艺证据见上方。</p><button type="button" data-comparison-detail class="text-button">展开每一种版本比较与未知边界 ↗</button></div>`;return;
 }
 const ids=state.selected.map(x=>x.id),html=[];
 for(let a=0;a<ids.length;a++)for(let b=a+1;b<ids.length;b++){
  const p=pair(ids[a],ids[b]);html.push(`<div class="evidence-item ${p.included.length?'':'is-exploratory'}"><span class="evidence-kicker">${p.included.length} 条可用直接关系 · ${p.excluded.length} 条保留未采用</span><strong>${esc(get(ids[a]).displayName)} × ${esc(get(ids[b]).displayName)}</strong>${p.all.length?`<details><summary>展开全部 ${p.all.length} 条配对来源</summary>${p.all.map(edgeCard).join('')}</details>`:'<p>当前资料没有这对原始身份的直接配对记录。保持未知，不从第三种食材传递推断。</p>'}</div>`);
 }
 $('evidenceList').innerHTML=html.join('')||'<p class="source-note">加入至少两款食材查看完整配对来源。</p>';
}
const copy={target:['从完整证据，寻找原料','同时使用大类来源范围、细分词与原文条件；保留每一个原始身份。','查找匹配证据'],replace:['保留差异，比较替换','逐版本比较，并展开两侧的分子、味觉、质地和加工条件。','比较全部候选'],compose:['把证据组织成试做提案','以直接搭配关系构造候选，保留每对来源与未解决的条件。','生成配方候选']};
function renderMode(){
 document.body.dataset.mode=state.mode;document.querySelectorAll('button[data-mode]').forEach(b=>{b.classList.toggle('is-active',b.dataset.mode===state.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));});
 for(const mode of ['target','replace','compose'])$(mode+'Controls').hidden=state.mode!==mode;
 $('modeTitle').textContent=copy[state.mode][0];$('modeDescription').textContent=copy[state.mode][1];$('suggestButton').textContent=copy[state.mode][2];$('crossFamilyToggle').checked=state.crossFamily;
 $('ingredientSearch').placeholder=state.mode==='replace'?'搜索待替换原料，保留原始身份':'搜索名称、品种或加工状态';
 renderTargets();renderSelected();renderCandidates();renderRecipe();
}
function setMode(mode){state.mode=mode;if(mode==='replace')state.chart='bars';state.query='';state.family='';state.visible=6;state.offset=0;state.replacement=null;$('ingredientSearch').value='';$('categoryFilter').value='';hideSearch();renderMode();}
function add(id){const i=get(id);if(!i)return;if(!i.recommendationEligible){showDetail(id);toast('记录完整保留；身份待核或教学示例不自动用于配方。');return;}if(state.mode==='replace'){state.replacement=id;renderRecipe();return;}if(state.selected.some(x=>x.id===id)){toast('这条来源身份已加入。');return;}state.selected.push({id,grams:null});renderSelected();renderCandidates();renderRecipe();}
function selectSearch(id){if(!get(id).recommendationEligible){showDetail(id);hideSearch();return;}if(state.mode==='replace'){state.anchor=id;state.replacement=null;state.family='';$('categoryFilter').value='';}else add(id);state.query='';$('ingredientSearch').value='';hideSearch();renderMode();}
function search(){
 state.query=$('ingredientSearch').value.trim();state.visible=6;state.searchIndex=-1;const q=norm(state.query);state.searchMatches=D.ingredients.filter(i=>!q||norm(i.searchText).includes(q));state.searchVisible=30;renderSearch();renderCandidates();
}
function renderSearch(){
 $('searchResults').innerHTML=state.searchMatches.slice(0,state.searchVisible).map((i,index)=>`<button type="button" class="search-result" role="option" id="search-option-${index}" aria-selected="false" data-search-id="${i.id}">${image(i,'search-thumb')}<span><strong>${esc(i.displayName)}</strong><small>原名 ${esc(i.name)} · ${i.recordCount} 条来源 · ${i.id.slice(-6)}${i.nameNeedsReview?' · 身份待核':''}</small></span><span class="search-arrow">↵</span></button>`).join('')+(state.searchMatches.length>state.searchVisible?`<button type="button" class="text-button" data-search-more>继续显示剩余 ${state.searchMatches.length-state.searchVisible} 项</button>`:'')||'<p class="search-empty">未找到原始食材身份；可在全部属性证据中继续检索。</p>';
 $('searchPopover').hidden=false;$('ingredientSearch').setAttribute('aria-expanded','true');
}
function hideSearch(){$('searchPopover').hidden=true;$('ingredientSearch').setAttribute('aria-expanded','false');$('ingredientSearch').removeAttribute('aria-activedescendant');}
function suggest(){
 if(state.mode==='target'){state.visible=6;renderCandidates();toast('已按全部来源和原文条件重新检索。');return;}
 if(state.mode==='replace'){const top=candidates()[0];if(top){state.replacement=top.item.id;renderRecipe();}return;}
 const anchor=state.selected[0];if(!anchor){toast('先选择主食材。');return;}
 const ranked=candidates().filter(x=>x.links?.included.length&&identity(x.item)!==identity(get(anchor.id)));
 if(!ranked.length){toast('没有可用的直接关系；可手动加入原料，未知关系会保留。');return;}
 const first=ranked[state.seed%ranked.length].item;const second=ranked.filter(x=>identity(x.item)!==identity(first));
 second.sort((a,b)=>Number(!!pair(first.id,b.item.id).included.length)-Number(!!pair(first.id,a.item.id).included.length));
 const linkedSecond=second.filter(x=>pair(first.id,x.item.id).included.length);const secondPool=linkedSecond.length?linkedSecond:second;
 const chosen=[first,...(secondPool.length?[secondPool[state.seed%secondPool.length].item]:[])];
 const old=new Map(state.selected.map(x=>[x.id,x.grams]));state.selected=[anchor,...chosen.map(i=>({id:i.id,grams:old.get(i.id)??null}))];state.name=`${get(anchor.id).displayName} · 多来源试做提案`;renderSelected();renderCandidates();renderRecipe();toast('已生成候选。用量保持待填，全部两两关系已展开保留。');
}
function recordTable(rows){
 return `<div class="record-table-scroll"><table class="source-matrix"><thead><tr><th>身份 / 记录</th><th>来源与角色</th>${D.categories.map((_,i)=>`<th>${esc(cat(i))}</th>`).join('')}<th>核验与全部字段</th></tr></thead><tbody>${rows.map(r=>{const id=r.ingredientId||state.detailId,ingredient=get(id);return `<tr><td>${ingredient?`<button type="button" class="text-button" data-detail="${id}">${esc(ingredient.displayName)}</button>`:''}<small>${esc(r.sourceName||ingredient?.name||'')}<br>${esc(r.id)}</small></td><td>${sourceLink(r.pdfPage)}<small>${esc(r.tableId)}<br>${r.role==='main'?'主食材':'配料行'}${r.isExample?' · 教学示例':''}</small></td>${r.presence.map((v,i)=>`<td class="matrix-cell" title="${esc(cat(i))}：${v===null?'未知':v?'已标示':'未标示'}${r.role!=='main'?'；共享='+String(r.sharedWithMain?.[i]):''}"><span class="matrix-dot ${v===1?'marked':''} ${r.sharedWithMain?.[i]===1?'shared':''} ${v===null?'unknown':''}" style="--dot:${palette[i]}">${v===null?'?':''}</span>${r.role!=='main'&&r.sharedWithMain?.[i]===null?'<sup>?</sup>':''}</td>`).join('')}<td><span class="verification-label">${esc(r.reviewStatus)} · ${esc(r.nameReviewStatus)}</span>${jsonView({sourceOriginal:rawRows.get(r.id)||r,appRecord:r},'全部原始字段与核名记录')}</td></tr>`;}).join('')}</tbody></table></div>`;
}
function openDialog(html){$('sourceDialogContent').innerHTML=html;const h=$('sourceDialogContent').querySelector('h2');if(h)h.id='sourceDialogTitle';if(!$('sourceDialog').open)$('sourceDialog').showModal();}
function showComparison(){
 const c=compare(state.anchor,state.replacement),categoryList=ids=>ids.map(cat).join('、')||'无';
 const vector=(values)=>`<div class="comparison-vector">${values.map((v,i)=>`<span title="${esc(cat(i))}：${v===null?'未知':v===1?'有标示':'未标示'}" class="${v===null?'unknown':v===1?'marked':''}" style="--dot:${palette[i]}">${esc(cat(i))}<b>${v===null?'?':v===1?'●':'○'}</b></span>`).join('')}</div>`;
 const references=refs=>refs.map(r=>`<span>${sourceLink(r.pdfPage,r.rowId)} </span>`).join('');
 openDialog(`<p class="eyebrow">ALL SOURCE VERSION COMPARISONS</p><h2>${esc(get(state.anchor).displayName)} × ${esc(get(state.replacement).displayName)}</h2><div class="comparison-overview"><strong>${pctRange(c)}</strong><span>已知类别标示相似范围</span><p>${c.variantComparisons} 个完整版本组合 · ${c.sourcePairCount} 对来源记录 · ${c.unknownComparisons} 个组合包含未知</p></div><p>相似度逐版本按双方已知类别的交并比计算，不按出现次数平均。数值表示图示标记的重合程度；同类别标示不等于共享同一分子。</p><p><b>两侧所有来源均标示：</b>${esc(categoryList(c.commonCertain))}<br><b>至少一个版本组合共同标示：</b>${esc(categoryList(c.sharedPossible))}<br><b>未知值的数学可能范围：</b>${pctRange(c.unknownBounds)}，这是缺失值全部可能取值的边界，不是置信区间。</p>${c.details.map((d,index)=>`<article class="comparison-record"><div class="evidence-record-head"><span class="evidence-id">版本组合 ${index+1} / ${c.details.length}</span><b>${d.knownJaccard===null?'已知资料不足':(d.knownJaccard*100).toFixed(2)+'%'}</b></div><p>${d.intersection} 类共同标示 / ${d.union} 类至少一侧标示 · ${d.knownDimensions} 类双方已知 · ${d.unknownDimensions} 类含未知</p><h3>${esc(get(state.anchor).displayName)}</h3>${vector(d.aPresence)}<div class="comparison-refs">${references(d.aSourceRefs)}</div><h3>${esc(get(state.replacement).displayName)}</h3>${vector(d.bPresence)}<div class="comparison-refs">${references(d.bSourceRefs)}</div><p>未知值可能范围 ${pctRange(d.unknownBounds)}</p>${jsonView(d,'该版本组合的全部计算字段')}</article>`).join('')}${jsonView(c,'完整比较与全部来源记录')}`);
}
function showEvidence(id){const r=evidenceById.get(id);if(!r)return;openDialog(`<p class="eyebrow">UNABRIDGED SOURCE EVIDENCE</p><h2>条件、数值和原文，完整保留。</h2>${evidenceCard(r)}<h3>与食材身份的关联范围</h3>${r.links.length?r.links.map(l=>`<p><button class="text-button" data-detail="${l.ingredientId}" type="button">${esc(get(l.ingredientId)?.displayName||l.ingredientId)}</button> · ${esc(l.kind)}<br>${esc(l.reason)}</p>`).join(''):'<p>尚未精确关联圆点表身份；证据继续独立保留。</p>'}${jsonView(r,'证据索引与所有原字段')}`);}
function showDetail(id=null){
 state.detailId=id;
 if(!id){openDialog(`<p class="eyebrow">ALL EXTRACTED EVIDENCE · NO COLLAPSING</p><h2>完整保留，按来源判断。</h2><div class="source-facts"><div><strong>10,439</strong><span>圆点来源行</span></div><div><strong>253</strong><span>属性证据</span></div><div><strong>70</strong><span>细分描述词</span></div><div><strong>24</strong><span>原文明示数值</span></div></div><p>全量指当前已提取资料。原属性库注明为分段提取初版，不能宣称全书每张风味轮已量化或全部来源均经过人工验证。</p><p>原始名称、上下文、数值单位、分母、条件、证据等级、未知、冲突、坐标和核验记录逐字段保留。同名条目不在底层合并。图表和推荐不再采用单条代表向量。</p><p>目标排序依次比较全部来源一致命中、部分来源命中；文字命中表示原文提及。替换比较逐版本给出范围。组合使用直接配对关系；配方克数不预设，质量占比与香气来源图分开。</p><button type="button" data-export-all class="text-button">导出全部属性与原始圆点数据 ↗</button><button type="button" data-download-catalog class="text-button">导出完整浏览目录 ↗</button><button type="button" data-download-manifest class="text-button">导出图片资产目录 ↗</button>${jsonView(E.source.metadata,'属性库原始覆盖说明')}${jsonView(E.source.notes,'全部数据解释与限制')}${jsonView(E.source.field_schema,'全部字段定义')}${jsonView(E.source.verified_table,'保留早期逐格核验示例表')}${jsonView(E.source,'原属性库全部原字段')}${jsonView(D.meta,'圆点目录方法与核验边界')}`);return;}
 const i=get(id),p=profile(id),ev=evidenceFor(id);
 openDialog(`<div class="source-ingredient-head">${image(i,'source-art')}<div><p class="eyebrow">EVERY SOURCE RECORD</p><h2>${esc(i.displayName)}</h2><p>原名 ${esc(i.name)}<br>${esc(i.id)} · ${i.records.length} 条记录</p></div></div><p>${p.recordCount} 条正式来源，${p.variantCount} 种完整标示版本。${i.nameNeedsReview?'名称待核，保留原文。':''} ${artStatus(i)==='family_illustration'?'图片是类别形态示意。':''}</p><div class="source-profile">${p.categories.map((v,index)=>`<span class="source-category ${v.status==='marked'?'is-marked':''}"><i style="background:${palette[index]}"></i>${esc(cat(index))}<b>${esc(categoryStatus(v))}</b><small>有 ${v.marked} / 未标 ${v.unmarked} / 未知 ${v.unknown}</small></span>`).join('')}</div><h3>全部版本与来源</h3><p class="source-note">小点=原表标示；大点=相对于本表主食材标共享；?=未知。未标示不等于化学不存在。</p>${recordTable(i.records.map(r=>({...r,ingredientId:id})))}<h3>同名 / 别名属性证据 · ${ev.direct.length} 条</h3>${ev.direct.map(r=>evidenceCard(r,{linkKind:'仍保留原处理条件'})).join('')||'<p>未找到可精确关联的属性证据，保持未知。</p>'}<h3>相关食材与条件语境 · ${ev.related.length} 条</h3><p>以下证据不直接赋值为此食材的属性。</p>${ev.related.map(r=>evidenceCard(r,{linkKind:'相关语境'})).join('')}${jsonView(i,'该原始身份的全部目录字段')}`);
}
function renderResearch(){
 const kind=state.view,q=norm(state.researchQuery),domain=state.researchDomain;let items=[],title='',description='';const pageSize=kind==='records'?30:kind==='evidence'?15:24;
 if(kind==='evidence'){title='全部属性证据';description='253条原记录完整保留。名字、处理状态、分子、相对关系、数值条件及核验范围均可检索。未匹配到圆点表的证据也在这里。';items=E.records.filter(r=>(!q||norm(r.searchText||JSON.stringify(r.original)).includes(q))&&(!domain||r.domains.includes(domain)));}
 if(kind==='records'){title='全部圆点来源记录';description='10,439行独立保留，包含教学、待核和不同来源版本。圆点表示图示标记，不表示浓度。展开末列可查看原始坐标、未知格、名称和核验字段。';items=allRows.filter(r=>!q||norm(r.searchText+' '+JSON.stringify(rawRows.get(r.id)||r)).includes(q));}
 if(kind==='taxonomy'){title='完整的70个细分描述词';description='每个描述词保留上层类别和来源页。词典不是每种食材均具备该属性的测量矩阵；点击词语可检索全部已提取证据。';items=E.facets.descriptors.filter(r=>!q||norm(JSON.stringify(r)).includes(q));}
 if(kind==='numbers'){title='全部24条原文明示数值';description='值、范围、比较符、单位、分母和限制逐条保留。不同基准的数值不合成统一分数。';items=E.numbers.filter(r=>!q||norm(JSON.stringify(r)).includes(q));}
 $('researchTitle').textContent=title;$('researchDescription').textContent=description;$('researchDomain').closest('label').hidden=kind!=='evidence';
 const pages=Math.max(1,Math.ceil(items.length/pageSize));state.researchPage=Math.min(state.researchPage,pages-1);const page=items.slice(state.researchPage*pageSize,(state.researchPage+1)*pageSize);
 $('researchCount').textContent=`${items.length.toLocaleString()} 条匹配 · 第 ${state.researchPage+1}/${pages} 页（分页只控制显示，不删除数据）`;
 if(kind==='evidence')$('researchContent').innerHTML=page.map(r=>evidenceCard(r)).join('');
 if(kind==='records')$('researchContent').innerHTML=recordTable(page);
 if(kind==='numbers')$('researchContent').innerHTML=`<div class="numeric-grid">${page.map(numericCard).join('')}</div>`;
 if(kind==='taxonomy')$('researchContent').innerHTML=`<div class="taxonomy-grid">${page.map(t=>`<article><span>${esc(t.category)}</span><h3><button type="button" data-taxonomy-query="${esc(t.descriptor)}">${esc(t.displayDescriptor||t.descriptor)}</button></h3>${sourceLink(t.pdf_page)}${jsonView(t.original||t,'词典原字段')}</article>`).join('')}</div>`;
 if(!items.length)$('researchContent').innerHTML='<div class="empty-state">当前检索无匹配。原库仍完整保留。</div>';
 $('researchPagination').innerHTML=`<button type="button" data-page="${state.researchPage-1}" ${state.researchPage===0?'disabled':''}>上一页</button><label>跳转页码 <input id="researchPageInput" type="number" min="1" max="${pages}" value="${state.researchPage+1}"></label><button type="button" data-page-go>前往</button><button type="button" data-page="${state.researchPage+1}" ${state.researchPage===pages-1?'disabled':''}>下一页</button>`;
}
function setView(view,query){state.view=view;state.researchPage=0;if(query!==undefined){state.researchQuery=query;$('researchSearch').value=query;}document.body.dataset.view=view;$('workbenchView').hidden=view!=='workbench';$('researchView').hidden=view==='workbench';document.querySelectorAll('button[data-view]').forEach(b=>{b.classList.toggle('is-active',b.dataset.view===view);b.setAttribute('aria-pressed',String(b.dataset.view===view));});if(view!=='workbench')renderResearch();}
function fullExport(){const entries=currentEntries(),ids=entries.map(x=>x.id),pairs=[];for(let a=0;a<ids.length;a++)for(let b=a+1;b<ids.length;b++)pairs.push(pair(ids[a],ids[b]));return {schema:'flavour-atelier-full-evidence-proposal-v2',createdAt:new Date().toISOString(),name:state.name,mode:state.mode,status:'untested_proposal',ingredients:entries.map(x=>({...x,name:get(x.id).displayName,sourceIdentity:get(x.id),allSourceProfile:profile(x.id),attributeEvidence:evidenceFor(x.id),rawDotRecords:get(x.id).records.map(r=>rawRows.get(r.id)||r)})),replacementOf:state.mode==='replace'?state.anchor:null,replacementContext:state.mode==='replace'?{id:state.anchor,name:get(state.anchor).displayName,sourceIdentity:get(state.anchor),allSourceProfile:profile(state.anchor),attributeEvidence:evidenceFor(state.anchor),rawDotRecords:get(state.anchor).records.map(r=>rawRows.get(r.id)||r)}:null,comparison:state.mode==='replace'&&state.replacement?compare(state.anchor,state.replacement):null,trialConditions:state.conditions,targets:[...state.targets],descriptorTargets:[...state.descriptors],evidenceQuery:state.evidenceQuery,mixtureSourceStates:engine.mixture(entries),pairEvidence:pairs,dataCoverage:E.coverage,method:'All available source variants retained; no canonical substitution or averaging. Related textual contexts are not assigned as exact ingredient attributes. Mass amounts do not predict aroma intensity. Unknowns remain unknown.'};}
let exportValue=null;
function showExport(value){exportValue=value;$('exportText').value=JSON.stringify(value,null,2);if(!$('exportDialog').open)$('exportDialog').showModal();}
function saveRecipe(){if(!currentEntries().length)return;const proposal={schema:'full-evidence-selection-v2',name:state.mode==='replace'?`${get(state.anchor).displayName} → ${get(state.replacement||state.anchor).displayName}`:state.name,createdAt:new Date().toISOString(),mode:state.mode,ingredients:currentEntries().map(x=>({...x,name:get(x.id).displayName})),anchor:state.anchor,replacement:state.replacement,targets:[...state.targets],descriptors:[...state.descriptors],evidenceQuery:state.evidenceQuery,trialConditions:state.conditions};saved.unshift(proposal);try{localStorage.setItem(STORE,JSON.stringify(saved));toast('提案与条件已保存。导出时包含全部来源证据。');}catch(_){saved.shift();showExport(fullExport());toast('本地存储空间不足；完整提案已展开，可下载。');}}
function showSaved(){ $('savedRecipesList').innerHTML=saved.map((r,index)=>`<article class="saved-recipe"><div class="saved-art-stack">${r.ingredients.filter(x=>get(x.id)).map(x=>image(get(x.id),'saved-thumb')).join('')}</div><div><h3>${esc(r.name)}</h3><p>${r.ingredients.map(x=>esc(x.name||get(x.id)?.displayName||x.id)).join(' · ')}</p><small>${esc(r.createdAt)} ${r.schema?.includes('v2')?'完整证据版':'旧版保存项，按完整来源恢复'}</small></div><div class="saved-actions"><button type="button" class="text-button" data-load="${index}">打开</button><button type="button" class="text-button" data-export-saved="${index}">导出保存记录</button><button type="button" class="text-button" data-delete="${index}">删除</button></div></article>`).join('')||'<div class="empty-state">还没有保存的提案。</div>';if(!$('savedRecipesDialog').open)$('savedRecipesDialog').showModal();}
function loadSaved(r){state.selected=r.ingredients.filter(x=>get(x.id)).map(x=>({id:x.id,grams:Number.isFinite(x.grams)&&x.grams>0?x.grams:null}));state.name=r.name;state.conditions=r.trialConditions||'';state.targets=new Set((r.targets||[]).map(v=>typeof v==='number'?v:D.categories.findIndex((_,i)=>cat(i)===v)).filter(v=>v>=0));state.descriptors=new Set(r.descriptors||[]);state.evidenceQuery=r.evidenceQuery||'';$('evidenceTarget').value=state.evidenceQuery;setMode(r.mode||'compose');if(r.mode==='replace'){state.anchor=r.anchor||r.replacementOf?.id||state.anchor;state.replacement=r.replacement||r.ingredients[0]?.id;renderMode();}setView('workbench');$('savedRecipesDialog').close();}
document.addEventListener('click',event=>{
 const b=event.target.closest('button,a');if(!b)return;
 if(b.dataset.view){setView(b.dataset.view);return;}if(b.dataset.mode){setMode(b.dataset.mode);return;}
 if(b.dataset.category!==undefined){const i=+b.dataset.category;state.targets.has(i)?state.targets.delete(i):state.targets.add(i);state.offset=0;renderTargets();renderCandidates();return;}
 if(b.dataset.descriptorRemove){state.descriptors.delete(b.dataset.descriptorRemove);renderTargets();renderCandidates();return;}
 if(b.dataset.add){add(b.dataset.add);return;}if(b.dataset.remove){state.selected=state.selected.filter(x=>x.id!==b.dataset.remove);renderSelected();renderCandidates();renderRecipe();return;}
 if(b.dataset.main){state.selected=[state.selected.find(x=>x.id===b.dataset.main),...state.selected.filter(x=>x.id!==b.dataset.main)];renderSelected();renderCandidates();renderRecipe();return;}
 if(b.dataset.detail){showDetail(b.dataset.detail);return;}if(b.dataset.evidence){showEvidence(b.dataset.evidence);return;}
 if(b.dataset.searchId){selectSearch(b.dataset.searchId);return;}if(b.hasAttribute('data-search-more')){state.searchVisible+=30;renderSearch();return;}
 if(b.dataset.chart){state.chart=b.dataset.chart;renderChart();return;}
 if(b.hasAttribute('data-page-go')){state.researchPage=Math.max(0,Math.trunc(Number($('researchPageInput').value)||1)-1);renderResearch();return;}
 if(b.dataset.page!==undefined){state.researchPage=+b.dataset.page;renderResearch();return;}
 if(b.dataset.taxonomyQuery){setView('evidence',b.dataset.taxonomyQuery);return;}
 if(b.hasAttribute('data-browse-mentions')){setView('evidence',terms().join(' ')||state.query);return;}
 if(b.hasAttribute('data-clear-filter')){state.query='';state.family='';state.descriptors.clear();state.evidenceQuery='';$('ingredientSearch').value='';$('evidenceTarget').value='';$('categoryFilter').value='';hideSearch();renderTargets();renderCandidates();return;}
 if(b.hasAttribute('data-comparison-detail')){showComparison();return;}
 if(b.hasAttribute('data-export-all')){download(E,'全部属性与圆点原始数据.json');return;}
 if(b.hasAttribute('data-download-catalog')){download(D,'完整食材浏览目录.json');return;}
 if(b.hasAttribute('data-download-manifest')){if(window.FLAVOR_ASSET_MANIFEST)download(window.FLAVOR_ASSET_MANIFEST,'图片资产目录.json');else{const a=document.createElement('a');a.href='assets/manifest.json';a.download='图片资产目录.json';a.click();}return;}
 if(b.dataset.load!==undefined){loadSaved(saved[+b.dataset.load]);return;}
 if(b.dataset.exportSaved!==undefined){showExport(saved[+b.dataset.exportSaved]);return;}
 if(b.dataset.delete!==undefined){saved.splice(+b.dataset.delete,1);try{localStorage.setItem(STORE,JSON.stringify(saved));}catch(_){}showSaved();return;}
});
document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap'))hideSearch();});
$('ingredientSearch').addEventListener('input',search);$('ingredientSearch').addEventListener('focus',search);
$('ingredientSearch').addEventListener('keydown',event=>{if(event.key==='Escape')hideSearch();if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();if($('searchPopover').hidden)search();const n=Math.min(state.searchVisible,state.searchMatches.length);if(!n)return;state.searchIndex=state.searchIndex<0?(event.key==='ArrowDown'?0:n-1):(state.searchIndex+(event.key==='ArrowDown'?1:-1)+n)%n;$('searchResults').querySelectorAll('[role=option]').forEach((x,i)=>{x.classList.toggle('is-highlighted',i===state.searchIndex);x.setAttribute('aria-selected',String(i===state.searchIndex));});$('ingredientSearch').setAttribute('aria-activedescendant','search-option-'+state.searchIndex);$('search-option-'+state.searchIndex)?.scrollIntoView({block:'nearest'});}if(event.key==='Enter'&&state.searchMatches.length){event.preventDefault();selectSearch(state.searchMatches[Math.max(0,state.searchIndex)].id);}});
$('descriptorSelect').innerHTML='<option value="">添加细分描述词…</option>'+D.categories.map(category=>`<optgroup label="${esc(category)}">${E.source.taxonomy.filter(t=>t.category===category).map(t=>`<option value="${esc(t.descriptor_id)}">${esc(E.facets.descriptors.find(d=>d.descriptor_id===t.descriptor_id)?.displayDescriptor||t.descriptor)}</option>`).join('')}</optgroup>`).join('');
$('descriptorSelect').onchange=e=>{if(e.target.value)state.descriptors.add(e.target.value);e.target.value='';state.visible=6;renderTargets();renderCandidates();};
$('evidenceTarget').oninput=e=>{state.evidenceQuery=e.target.value;state.visible=6;renderCandidates();};
$('crossFamilyToggle').onchange=e=>{state.crossFamily=e.target.checked;renderCandidates();};
const families=Object.fromEntries(D.ingredients.map(i=>[i.visualFamily,i.visualFamilyLabel]));$('categoryFilter').innerHTML='<option value="">所有食材类别</option>'+Object.entries(families).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('');$('categoryFilter').value=state.family;$('categoryFilter').onchange=e=>{state.family=e.target.value;state.visible=6;state.offset=0;renderCandidates();};
$('suggestButton').onclick=suggest;$('shuffleButton').onclick=()=>{state.seed++;if(state.mode==='compose')suggest();else if(state.mode==='replace'){const list=candidates();if(list.length){state.replacement=list[state.seed%list.length].item.id;renderRecipe();}}else{state.offset+=6;renderCandidates();}};
$('resetButton').onclick=()=>{state.targets=new Set([0,2,7]);state.descriptors.clear();state.evidenceQuery='';state.query='';state.family=state.mode==='target'?'fruit':'';state.selected=standard.map(i=>({id:i.id,grams:null}));state.name='草莓 · 完整证据提案';state.conditions='';state.anchor=(findName('奶油乳酪')||standard[0]).id;state.replacement=null;state.visible=6;state.offset=0;state.seed=0;$('ingredientSearch').value='';$('evidenceTarget').value='';$('categoryFilter').value=state.family;hideSearch();renderMode();};
document.addEventListener('input',e=>{if(e.target.matches('[data-grams]')){const row=state.selected.find(x=>x.id===e.target.dataset.grams);if(row){const value=e.target.value.trim(),n=Number(value);row.grams=value&&Number.isFinite(n)&&n>0?n:null;$('recipeMeta').textContent=`${state.selected.length} 项原料 · ${state.selected.filter(x=>x.grams===null).length} 项用量待填 · 香气强度预测：缺少配方实测数据`;renderChart();}}});
document.addEventListener('keydown',e=>{if(e.target.id==='researchPageInput'&&e.key==='Enter'){state.researchPage=Math.max(0,Math.trunc(Number(e.target.value)||1)-1);renderResearch();}});
$('recipeName').oninput=e=>state.name=e.target.value||'未命名完整证据提案';$('trialConditions').oninput=e=>state.conditions=e.target.value;
$('researchSearch').oninput=e=>{state.researchQuery=e.target.value;state.researchPage=0;renderResearch();};
const domains=[...new Set(E.records.flatMap(r=>r.domains))];$('researchDomain').innerHTML='<option value="">全部维度</option>'+domains.map(d=>`<option value="${esc(d)}">${esc(domainLabels[d]||d)}</option>`).join('');$('researchDomain').onchange=e=>{state.researchDomain=e.target.value;state.researchPage=0;renderResearch();};
$('downloadResearch').onclick=()=>download({source:E.source,dotSource:E.dotSource,index:E.records,numbers:E.numbers,coverage:E.coverage},'完整来源证据.json');
$('sourceButton').onclick=()=>showDetail();$('sourceDialogClose').onclick=()=>$('sourceDialog').close();$('savedButton').onclick=showSaved;$('savedRecipesClose').onclick=()=>$('savedRecipesDialog').close();$('saveRecipeButton').onclick=saveRecipe;
const exportButton=document.createElement('button');exportButton.type='button';exportButton.className='button button-outline';exportButton.id='exportFullProposal';exportButton.textContent='导出完整证据';exportButton.onclick=()=>showExport(fullExport());$('saveRecipeButton').before(exportButton);
$('downloadExportButton').onclick=()=>{if(exportValue)download(exportValue,(exportValue.name||'完整证据')+'.json');};$('copyExportButton').onclick=async()=>{try{await navigator.clipboard.writeText($('exportText').value);toast('完整内容已复制。');}catch(_){$('exportText').focus();$('exportText').select();toast('内容已选中，可复制保存。');}};
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',event=>{if(event.target===d){const r=d.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)d.close();}}));
$('ingredientTotal').textContent=D.ingredients.length.toLocaleString()+' 个原始身份';
$('coverageRibbon').innerHTML='<strong>完整证据视图</strong><span>14 大类 / 70 描述词</span><span>253 条属性证据</span><span>24 条原文数值</span><span>10,439 条圆点记录</span><small>当前已提取范围；未测项保留未知</small>';
renderMode();
window.FLAVOR_ENGINE={...engine,getState:()=>({...state,targets:[...state.targets],descriptors:[...state.descriptors]}),fullExport,candidates};
})();
