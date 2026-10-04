/* Offline interaction and source-aware candidate search. No remote model calls. */
(() => {
  'use strict';
  const DATA = window.FLAVOR_DATA;
  if (!DATA?.ingredients?.length) return;
  const byId = new Map(DATA.ingredients.map(x => [x.id, x]));
  const categories = DATA.categories;
  const categoryNames = DATA.categoryDisplayNames || categories;
  const palette = ['#c8675b','#e4a344','#c38d9e','#859868','#54775f','#9ca275','#b88653','#926448','#ad9370','#7e8070','#c98160','#d8b671','#a8877c','#8b88a5'];
  const familyNames = Object.fromEntries(DATA.ingredients.map(x => [x.visualFamily,x.visualFamilyLabel]));
  const edgeMap = new Map();
  for (const edge of DATA.edges) {
    const key = [edge.mainId,edge.pairedId].sort().join('|');
    if (!edgeMap.has(key)) edgeMap.set(key,[]);
    edgeMap.get(key).push(edge);
  }
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cat = index => Array.isArray(categoryNames) ? categoryNames[index] : (categoryNames[categories[index]] || categories[index]);
  const get = id => byId.get(id);
  const identity = item => item.displayName.normalize('NFKC').replace(/\s+/g,'').toLocaleLowerCase();
  const findName = name => DATA.ingredients.find(x => x.name === name || x.displayName === name);
  const pairs = (a,b) => edgeMap.get([a,b].sort().join('|')) || [];
  const known = ingredient => ingredient.presence.map((v,i) => v === 1 ? i : -1).filter(i => i >= 0);
  const standard = ['草莓','奶油乳酪','烤葵花籽'].map(findName).filter(Boolean);
  const familiarNames=['苹果','草莓','树莓','蓝莓','芒果','香蕉','桃子','梨','葡萄干','干无花果','山竹'];
  const familiarity=item=>{const i=familiarNames.indexOf(item.displayName);return i<0?0:familiarNames.length-i;};
  const STORE = 'flavour-atelier-recipes-v1';
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(STORE) || '[]').filter(x => Array.isArray(x.ingredients)).slice(0,30); } catch (_) {}
  const state = {
    mode:'target', targets:new Set([0,2,7]), exclusions:new Set(), family:'fruit', query:'',
    selected:standard.map((x,i) => ({id:x.id,grams:[100,35,8][i]})),
    anchor:(findName('奶油乳酪') || standard[0] || DATA.ingredients[0]).id,
    replacement:null, crossFamily:false, chart:'bars', seed:0, visible:6,
    searchIndex:-1, searchMatches:[], resultKind:'ranked', name:'草莓 · 柔和烘烤', detailIngredient:null,
  };
  const modeCopy = {
    target:{title:'从想要的香气，找到食材',description:'选择你想探索的香气方向，发现带有这些标示的原料。',button:'寻找合适的原料',results:'与你的目标相遇'},
    replace:{title:'保留香气线索，换一种可能',description:'选择一款原料，比较具有相近香气标示的替代候选。',button:'寻找替代食材',results:'换一种原料，打开新方向'},
    compose:{title:'让不同食材，组成新的提案',description:'以一款主食材为起点，沿着原书的搭配关系探索组合。',button:'生成搭配提案',results:'把灵感加入配方'},
  };
  function similarity(a,b) {
    let both=0,union=0,comparable=0;
    for(let i=0;i<14;i++){
      if(a.presence[i]===null || b.presence[i]===null) continue;
      comparable++;
      if(a.presence[i]===1 || b.presence[i]===1) union++;
      if(a.presence[i]===1 && b.presence[i]===1) both++;
    }
    return {score:union ? both/union : 0,both,union,comparable};
  }
  function profile(selection) {
    const items=selection.map(x=>get(x.id || x)).filter(Boolean);
    return categories.map((_,i)=>({index:i,count:items.filter(x=>x.presence[i]===1).length,
      unknown:items.filter(x=>x.presence[i]===null).length,
      conflicts:items.filter(x=>x.conflictCategoryIndices.includes(i)).length,
      contributors:items.filter(x=>x.presence[i]===1).map(x=>x.displayName),total:items.length}));
  }
  function targetScore(ingredient) {
    const matches=[...state.targets].filter(i=>ingredient.presence[i]===1);
    const absent=[...state.exclusions].filter(i=>ingredient.presence[i]===1);
    const count=known(ingredient).length;
    return {score:(state.targets.size ? matches.length/state.targets.size : 0.5)*100 + (count ? matches.length/count : 0)*9 - absent.length*60,
      matches,avoided:absent,unknown:[...state.targets].filter(i=>ingredient.presence[i]===null)};
  }
  function candidates() {
    let items=DATA.ingredients.filter(x=>x.recommendationEligible);
    if(state.family) items=items.filter(x=>x.visualFamily===state.family);
    const query=state.query.trim().toLocaleLowerCase();
    if(query) items=items.filter(x=>x.searchText.toLocaleLowerCase().includes(query));
    const selected=new Set(state.selected.map(x=>identity(get(x.id))));
    const anchor=get(state.mode==='replace'?state.anchor:state.selected[0]?.id);
    const ranked=items.filter(x=>state.mode==='target' || !anchor || identity(x)!==identity(anchor)).filter(x=>state.mode!=='replace' || state.crossFamily || x.visualFamily===anchor?.visualFamily).map(item=>{
      const target=targetScore(item);
      const links=anchor ? pairs(anchor.id,item.id).filter(x=>x.recommendationEligible) : [];
      const sim=anchor ? similarity(anchor,item) : {score:0,both:0,union:0,comparable:14};
      let score=target.score;
      if(state.mode==='replace') score=sim.score*100;
      if(state.mode==='compose') score=(links.length ? 100 : 0)+Math.max(0,...links.map(e=>e.sharedCategories.length))*3+target.score*0.15-(selected.has(identity(item))?1000:0);
      return {item,score,target,links,sim};
    }).sort((a,b)=>b.score-a.score || familiarity(b.item)-familiarity(a.item) || (b.item.nameVisuallyReviewed?1:0)-(a.item.nameVisuallyReviewed?1:0) || b.item.mainRecordCount-a.item.mainRecordCount || a.item.displayName.localeCompare(b.item.displayName,'zh-Hans'));
    const shown=new Set();return ranked.filter(({item})=>{const key=identity(item);if(shown.has(key))return false;shown.add(key);return true;});
  }
  function artStatus(ingredient){return window.FLAVOR_ART_META?.[ingredient.id]?.status || 'illustrated';}
  function image(ingredient,cls='ingredient-thumb') {
    return `<img class="${cls}" src="${esc(window.FLAVOR_ASSETS?.[ingredient.id] || ingredient.image)}" alt="${esc(ingredient.displayName)}的${artStatus(ingredient)==='family_illustration'?'类别形态示意图':'风格化食材插画'}" loading="lazy" decoding="async" width="320" height="320">`;
  }
  function quality(ingredient) {
    if(ingredient.nameNeedsReview) return '名称待核';
    if(ingredient.conflictCategories.length) return '有不同来源标示';
    return ingredient.canonical.reviewStatus==='complete_visual_review' ? '已逐格核图' : '原书图示';
  }
  function badge(text,extra='') { return `<span class="small-badge ${extra}">${esc(text)}</span>`; }
  function toast(message) {
    const el=$('toast'); if(!el) return;
    el.textContent=message;el.hidden=false;el.classList.add('is-visible');
    clearTimeout(toast.timer);toast.timer=setTimeout(()=>{el.classList.remove('is-visible');el.hidden=true;},3200);
  }
  function renderCategories() {
    const el=$('targetCategories');if(!el)return;
    el.innerHTML=categories.map((_,i)=>`<button type="button" class="aroma-chip ${state.targets.has(i)?'is-active':''} ${state.exclusions.has(i)?'is-excluded':''}" data-category="${i}" aria-pressed="${state.targets.has(i)}" style="--aroma-color:${palette[i]}"><span class="aroma-dot"></span>${esc(cat(i))}${state.targets.has(i)?'<span class="chip-check">✓</span>':''}</button>`).join('');
  }
  function renderSelected() {
    const el=$('selectedIngredients');if(!el)return;
    const items=state.mode==='replace' ? [{id:state.anchor}] : state.selected;
    el.innerHTML=items.map((entry,i)=>{
      const item=get(entry.id);
      return `<span class="selected-chip">${image(item,'selected-thumb')}<span>${esc(item.displayName)}</span>${state.mode==='compose'?(i===0?'<small>主食材</small>':`<button type="button" class="make-main" data-make-main="${item.id}" aria-label="以${esc(item.displayName)}为主食材">设为主食材</button>`):''}${state.mode==='replace'?'':`<button type="button" data-remove="${item.id}" aria-label="移除${esc(item.displayName)}">×</button>`}</span>`;
    }).join('') || '<span class="muted-hint">搜索一款食材，开始探索。</span>';
    const anchor=get(state.anchor);
    if($('replaceAnchorLabel'))$('replaceAnchorLabel').textContent=anchor.displayName;
    if($('replaceOriginal'))$('replaceOriginal').innerHTML=`${image(anchor)}<div><strong>${esc(anchor.displayName)}</strong><small>${esc(anchor.visualFamilyLabel)} · ${known(anchor).length} 类香气标示</small></div>`;
  }
  function renderCandidates() {
    const list=candidates();
    const offset=state.mode==='target'&&list.length?(state.seed*6)%list.length:0;
    const ordered=[...list.slice(offset),...list.slice(0,offset)];const displayed=ordered.slice(0,state.visible);
    $('candidateCount').textContent=`${list.length.toLocaleString()} 个候选`;
    $('candidateSummary').textContent=state.mode==='target' ? `已选择 ${state.targets.size} 个目标方向 · 按图示命中与相关性排序` : state.mode==='replace' ? `与「${get(state.anchor).displayName}」比较 · ${state.crossFamily?'跨类别探索':'同类优先'}` : '优先展示与主食材有原书配对记录的候选';
    $('candidateGrid').innerHTML=displayed.map(({item,target,links,sim})=>{
      const selected=state.selected.some(x=>identity(get(x.id))===identity(item));
      let label=state.targets.size?`${target.matches.length}/${state.targets.size} 目标标示`:`${known(item).length} 类原书标示`;
      let detail=target.matches.map(cat).join(' · ') || '可探索其他香气方向';
      if(state.mode==='replace') { label=`${Math.round(sim.score*100)}% 标示相似`;detail=`共同标示 ${sim.both} 类 · ${sim.comparable}/14 类可比较`; }
      if(state.mode==='compose') { label=links.length?'原书有配对记录':'组合探索';detail=links.length?`共享标示：${[...new Set(links.flatMap(e=>e.sharedCategories))].slice(0,3).join(' · ') || '本表未标共享类别'}`:'目前没有这对食材的直接记录'; }
      return `<article class="ingredient-card ${selected?'is-selected':''}">
        <button type="button" class="card-image" data-detail="${item.id}" aria-label="查看${esc(item.displayName)}的来源">${image(item,'ingredient-art')}${artStatus(item)==='family_illustration'?'<span class="art-method-badge">类别示意</span>':''}<span class="image-inspect" aria-hidden="true">↗</span></button>
        <div class="card-content"><span class="card-category">${esc(item.visualFamilyLabel)}</span><h3>${esc(item.displayName)}</h3><p class="card-match">${esc(label)}</p><p class="card-reason">${esc(detail)}</p>
        <div class="card-foot"><span class="card-quality">${esc(quality(item))}</span><button type="button" class="card-add" data-add="${item.id}" aria-label="${state.mode==='replace'?'试用替换':'加入配方'}${esc(item.displayName)}">${state.mode==='replace'?'替换':selected?'已加入':'＋'}</button></div></div></article>`;
    }).join('') || '<div class="empty-state"><span>没有找到这样的原料</span><p>试试更短的名称，或切换食材类别。</p><button type="button" class="text-button" data-clear-filter>清除筛选</button></div>';
    let more=$('loadMoreButton');
    if(!more){more=document.createElement('button');more.id='loadMoreButton';more.type='button';more.className='load-more';$('candidateGrid').after(more);more.onclick=()=>{state.visible+=6;renderCandidates();};}
    more.hidden=list.length<=state.visible;more.textContent=`继续浏览 · 还有 ${Math.max(0,list.length-state.visible)} 项`;
  }
  function currentProfileItems() {
    if(state.mode==='replace') return [{id:state.replacement || state.anchor}];
    return state.selected;
  }
  function renderRecipe() {
    const entries=currentProfileItems();
    $('recipeTitle').textContent=state.mode==='replace' ? '替换前后，一眼比较' : '你的风味提案';
    $('recipeDescription').textContent=state.mode==='replace' ? (state.replacement ? `${get(state.anchor).displayName} → ${get(state.replacement).displayName}` : '选一个替代候选，查看香气标示的变化。') : '先用图示寻找方向，再用试做判断味道。';
    if($('recipeName')) { $('recipeName').value=state.name; $('recipeName').closest('.recipe-name-field').hidden=state.mode==='replace'; }
    $('recipeIngredients').innerHTML=entries.map((entry,i)=>{
      const item=get(entry.id); const grams=entry.grams ?? 100;
      return `<div class="recipe-row">${image(item,'recipe-thumb')}<div class="recipe-row-main"><button type="button" class="ingredient-name-button" data-detail="${item.id}">${esc(item.displayName)}</button><small>${state.mode==='compose'&&i===0?'主食材 · ':''}${esc(item.visualFamilyLabel)}</small></div>${state.mode==='replace'?badge('当前候选'):`<label class="amount-input"><input type="number" min="0.1" max="5000" step="0.1" value="${grams}" data-grams="${item.id}" aria-label="${esc(item.displayName)}试做克数"><span>g</span></label><button type="button" class="row-remove" data-remove="${item.id}" aria-label="移除${esc(item.displayName)}">×</button>`}</div>`;
    }).join('') || '<div class="recipe-empty">从左侧加入原料，开始一份新提案。</div>';
    const p=profile(entries); const coverage=p.filter(x=>x.count>0).length;
    if($('recipeMeta')) $('recipeMeta').textContent=state.mode==='replace' ? '相似度只比较原书香气标示' : `${entries.length} 款食材 · 覆盖 ${coverage}/14 类标示 · 克数供试做，不参与风味强度预测`;
    renderChart();renderEvidence();
  }
  function renderChart() {
    const entries=currentProfileItems();const p=profile(entries);const container=$('aromaChart');
    const before=state.mode==='replace'?profile([{id:state.anchor}]):null;
    container.setAttribute('aria-label','原书香气标示，非实测强度：'+p.map(v=>`${cat(v.index)} ${v.count}/${v.total}${v.unknown?`，${v.unknown}项未知`:''}`).join('；'));
    document.querySelectorAll('[data-chart]').forEach(b=>{b.classList.toggle('is-active',b.dataset.chart===state.chart);b.setAttribute('aria-pressed',String(b.dataset.chart===state.chart));});
    if(state.chart==='bars'){
      container.className='aroma-chart aroma-chart-bars';
      container.innerHTML=p.map((v,i)=>{
        const percent=v.total ? v.count/v.total*100 : 0;
        const old=before?.[i].count || 0;const oldUnknown=before?.[i].unknown || 0;
        const label=before?`${oldUnknown?'未知':old?'有标示':'未标示'} → ${v.unknown?'未知':v.count?'有标示':'未标示'}`:`${v.count}/${v.total}${v.unknown?` · ${v.unknown} 未知`:''}`;
        return `<div class="aroma-bar-row ${state.targets.has(i)?'is-target':''}" title="${esc(`${cat(i)}：${v.contributors.join('、') || '当前代表记录未标示'}${v.conflicts?'；存在其他来源差异':''}`)}"><span class="aroma-bar-label"><i style="background:${palette[i]}"></i>${esc(cat(i))}</span><span class="aroma-bar-track">${before?`<span class="aroma-bar-before ${oldUnknown?'is-unknown':''}" style="width:${oldUnknown?100:old*100}%"></span>`:''}<span class="aroma-bar-fill" style="width:${percent}%;background:${palette[i]}"></span>${v.unknown?`<span class="aroma-bar-unknown" style="left:${percent}%;width:${v.unknown/v.total*100}%"></span>`:''}</span><span class="aroma-bar-value">${esc(label)}</span></div>`;
      }).join('');
      $('chartLegend').innerHTML=before?'<span><i class="legend-line-before"></i>细线：替换前</span><span>色条：当前候选</span>':'<span>标示食材数 / 当前食材数</span><span>悬停查看贡献食材</span>';
    }else{
      const total=p.reduce((sum,v)=>sum+v.count,0);let angle=0;
      const paths=p.filter(v=>v.count>0).map(v=>{
        const fraction=v.count/total;const start=angle;angle+=fraction*360;
        const cx=130,cy=130,r=95,toXY=a=>[cx+r*Math.cos((a-90)*Math.PI/180),cy+r*Math.sin((a-90)*Math.PI/180)];
        const a=toXY(start),b=toXY(angle===360?359.9999:angle);
        return `<path d="M ${cx},${cy} L ${a[0]},${a[1]} A ${r},${r} 0 ${fraction>0.5?1:0} 1 ${b[0]},${b[1]} Z" fill="${palette[v.index]}"><title>${esc(cat(v.index))}：${v.count} 次标示（${(fraction*100).toFixed(1)}%）</title></path>`;
      }).join('');
      container.className='aroma-chart aroma-chart-donut';
      container.innerHTML=`<div class="donut-wrap"><svg viewBox="0 0 260 260" role="img" aria-label="各香气类别标示次数构成，非气味强度">${total?paths:'<circle cx="130" cy="130" r="95" fill="#e7e2d9"/>'}<circle cx="130" cy="130" r="68" fill="var(--panel,#fffdf8)"/><text x="130" y="126" text-anchor="middle" class="donut-number">${p.filter(v=>v.count>0).length}</text><text x="130" y="151" text-anchor="middle" class="donut-subtitle">类香气标示</text></svg></div><div class="donut-legend">${p.filter(v=>v.count>0).map(v=>`<span><i style="background:${palette[v.index]}"></i><b>${esc(cat(v.index))}</b><em>${v.count} 次</em></span>`).join('') || '<span>加入食材后查看构成</span>'}</div>`;
      $('chartLegend').innerHTML=`<span>共 ${total} 次类别标示 · 每种食材可同时标示多类</span>`;
    }
    const conflicts=entries.map(x=>get(x.id)).filter(x=>x.conflictCategories.length);
    $('profileNote').textContent=`图表按原书代表记录计算${state.chart==='donut'?'标示次数构成':'类别覆盖'}，不代表实测强度或浓度。${conflicts.length?`其中 ${conflicts.length} 款食材有不同来源标示，可点击名称查看。`:''}${p.some(v=>v.unknown)?'未知值保持未知。':''}`;
  }
  function renderEvidence() {
    let ids=currentProfileItems().map(x=>x.id);
    if(state.mode==='replace'){
      const a=get(state.anchor),b=get(state.replacement || state.anchor);const s=similarity(a,b);
      $('evidenceList').innerHTML=`<div class="evidence-item"><span class="evidence-kicker">${state.replacement?'替换依据':'原料来源'}</span><strong>${state.replacement?`${Math.round(s.score*100)}% 香气标示相似度`:esc(a.displayName)}</strong><p>${state.replacement?`共同标示 ${s.both} 类，在任一方标示的 ${s.union} 类中计算相似度。相似标示不保证实际风味相同。`:'从代表来源记录读取14类标示；点食材名称可查看源页及其他记录。'}</p><button type="button" class="text-button" data-detail="${b.id}">查看来源与差异 ↗</button></div>`;
      return;
    }
    const notes=[];
    for(let i=0;i<ids.length;i++)for(let j=i+1;j<ids.length;j++){
      const links=pairs(ids[i],ids[j]).filter(e=>e.recommendationEligible);const a=get(ids[i]),b=get(ids[j]);
      if(links.length){
        const edge=[...links].sort((x,y)=>y.sharedCategories.length-x.sharedCategories.length)[0];
        notes.push(`<div class="evidence-item"><span class="evidence-kicker">原书配对 · PDF ${edge.sourceRef.pdfPage} 页</span><strong>${esc(a.displayName)} × ${esc(b.displayName)}</strong><p>${edge.sharedCategories.length?`此表的共享标示：${edge.sharedCategories.map(x=>esc(x)).join('、')}。`:'此表收录了这对食材，未标示可辨识的共享类别。'}${edge.unknownSharedCategories.length?`另有 ${edge.unknownSharedCategories.length} 类共享标示未辨清。`:''}<span class="source-inline">来源主食材：${esc(get(edge.mainId).displayName)}</span></p></div>`);
      }else notes.push(`<div class="evidence-item is-exploratory"><span class="evidence-kicker">待试做的组合探索</span><strong>${esc(a.displayName)} × ${esc(b.displayName)}</strong><p>当前可用资料中没有这对食材的直接配对依据。</p></div>`);
    }
    $('evidenceList').innerHTML=notes.join('') || '<div class="evidence-item"><span class="evidence-kicker">灵感从一款原料开始</span><p>加入至少两款食材，查看原书关系与待探索的连接。</p></div>';
  }
  function renderMode() {
    const copy=modeCopy[state.mode];document.body.dataset.mode=state.mode;
    document.querySelectorAll('[data-mode]').forEach(b=>{const active=b.dataset.mode===state.mode;b.classList.toggle('is-active',active);b.setAttribute('aria-pressed',String(active));b.tabIndex=0;});
    for(const mode of ['target','replace','compose']) if($(mode+'Controls')) $(mode+'Controls').hidden=mode!==state.mode;
    if($('modeTitle'))$('modeTitle').textContent=copy.title;
    if($('modeDescription'))$('modeDescription').textContent=copy.description;
    $('suggestButton').textContent=copy.button;
    $('ingredientSearch').placeholder=state.mode==='replace'?'搜索要替换的食材，例如奶油乳酪':'搜索食材名称，支持简体与繁体';
    if($('crossFamilyToggle'))$('crossFamilyToggle').checked=state.crossFamily;
    renderCategories();renderSelected();renderCandidates();renderRecipe();
  }
  function addIngredient(id) {
    const item=get(id);if(!item)return;
    if(!item.recommendationEligible){showDetail(id);toast('这项记录暂不参与配方推荐，请先查看来源。');return;}
    if(state.mode==='replace'){state.replacement=id;renderRecipe();renderCandidates();toast(`正在比较：${item.displayName}`);return;}
    if(state.selected.some(x=>identity(get(x.id))===identity(item))){toast('这款食材已经在配方中。');return;}
    if(state.selected.length>=5){toast('每份提案最多 5 款食材，便于逐项试做与判断。');return;}
    state.selected.push({id,grams:state.selected.length?10:100});renderSelected();renderCandidates();renderRecipe();
    toast(`已加入 ${item.displayName}`);
  }
  function selectSearch(id) {
    if(!get(id).recommendationEligible){showDetail(id);hideSearch();toast('该名称尚待核对，暂不加入配方。');return;}
    if(state.mode==='replace') {state.anchor=id;state.replacement=null;state.family='';if($('categoryFilter'))$('categoryFilter').value='';}
    else if(get(id).recommendationEligible) {
      if(state.mode==='compose' && !state.selected.length) state.selected=[{id,grams:100}];
      else addIngredient(id);
    } else showDetail(id);
    state.query='';$('ingredientSearch').value='';hideSearch();state.visible=6;renderMode();
  }
  function search() {
    const q=$('ingredientSearch').value.trim().toLocaleLowerCase();state.query=q;state.visible=6;state.searchIndex=-1;
    const matches=(q?DATA.ingredients.filter(x=>x.searchText.toLocaleLowerCase().includes(q)):DATA.ingredients.filter(x=>standard.some(y=>x.id===y.id))).sort((a,b)=>Number(b.recommendationEligible)-Number(a.recommendationEligible) || b.recordCount-a.recordCount);
    const names=new Set();const items=matches.filter(item=>{const key=identity(item);if(names.has(key))return false;names.add(key);return true;}).slice(0,30);
    state.searchMatches=items;
    $('searchResults').innerHTML=items.map((item,i)=>`<button type="button" class="search-result" id="search-option-${i}" role="option" aria-selected="false" data-search-id="${item.id}">${image(item,'search-thumb')}<span><strong>${esc(item.displayName)}</strong><small>${esc(item.visualFamilyLabel)}${item.nameNeedsReview?' · 名称待核':''}</small></span><span class="search-arrow">${item.nameNeedsReview?'查看':'↵'}</span></button>`).join('') || '<p class="search-empty">没有找到，试试更短的关键词。</p>';
    $('searchPopover').hidden=false;$('ingredientSearch').setAttribute('aria-expanded','true');renderCandidates();
  }
  function hideSearch() { $('searchPopover').hidden=true;$('ingredientSearch').setAttribute('aria-expanded','false');$('ingredientSearch').removeAttribute('aria-activedescendant'); }
  function suggest() {
    if(state.mode==='replace') {
      const candidate=candidates()[0];if(candidate){state.replacement=candidate.item.id;renderRecipe();renderCandidates();toast('已选中标示最相近的候选，实际替换仍需试做。');}
      else toast('没有同类候选，可以开启跨类别探索。');
      return;
    }
    if(state.mode==='target'){state.visible=6;renderCandidates();toast(`已按 ${state.targets.size} 个香气目标重新筛选。`);return;}
    if(!state.selected.length){toast('先选择一款主食材。');$('ingredientSearch').focus();return;}
    const anchor=state.selected[0];const ranked=candidates().filter(x=>x.links.length && x.item.id!==anchor.id);
    if(!ranked.length){toast('这款原料暂无可用的直接配对记录，可以手动加入候选。');return;}
    const chosen=[];const used=new Set([get(anchor.id).visualFamily]);
    const pool=ranked.slice(0,Math.min(30,ranked.length));const rotate=state.seed%pool.length;
    const ordered=[...pool.slice(rotate),...pool.slice(0,rotate)];
    for(const candidate of ordered){if(!used.has(candidate.item.visualFamily)){chosen.push(candidate.item);used.add(candidate.item.visualFamily);}if(chosen.length===2)break;}
    for(const candidate of ordered){if(chosen.length>=2)break;if(!chosen.some(x=>x.id===candidate.item.id))chosen.push(candidate.item);}
    state.selected=[anchor,...chosen.map((item,i)=>({id:item.id,grams:i?8:25}))];
    state.name=`${get(anchor.id).displayName} · 新的搭配提案`;
    renderSelected();renderCandidates();renderRecipe();toast('已生成有来源依据的试做提案；克数是可编辑起点。');
  }
  function showDetail(id=null) {
    const dialog=$('sourceDialog');state.detailIngredient=id;
    let content=$('sourceDialogContent');if(!content){content=document.createElement('div');content.id='sourceDialogContent';dialog.append(content);}
    if(!id){
      const summary=DATA.meta.summary || {};
      content.innerHTML=`<div class="source-intro"><p class="eyebrow">SOURCE & METHOD</p><h2>每个灵感，都有出处。</h2><p>来自《食物风味搭配科学》的圆点表。当前收录 ${DATA.ingredients.length.toLocaleString()} 个原始名称，保留品种、部位和加工状态。</p><div class="source-facts"><div><strong>${DATA.edges.length.toLocaleString()}</strong><span>表内配对记录</span></div><div><strong>14</strong><span>香气类别</span></div><div><strong>${DATA.ingredients.filter(x=>x.recommendationEligible).length.toLocaleString()}</strong><span>可推荐原始条目</span></div></div><p>柱形图表示被标示的食材数，圆环图表示各类别标示次数构成。两者都不代表浓度、香气强度、口感或好吃概率。</p><p>同名食材在候选列表中合并展示，原始记录仍分别保留。代表特征优先采用已核图主行，再采用其他主行或实际来源记录。不同来源的标示差异保留，不做平均。组合建议由本地可解释规则生成，尚未经过试吃验证。</p><p>原始名称有疑点的记录暂不进入推荐；图片为风格化视觉资产，不是食材身份鉴定照片。教学示例不参与正式推荐。</p><button class="text-button" type="button" data-download-catalog>下载完整来源数据 ↗</button><button class="text-button" type="button" data-download-manifest>下载本地图片资产目录 ↗</button></div>`;
    } else {
      const item=get(id);const rows=item.records.slice(0,35);
      const pdf='../'+encodeURIComponent('食物風味搭配科學 ( etc.) (Z-Library).pdf');
      content.innerHTML=`<div class="source-ingredient-head">${image(item,'source-art')}<div><p class="eyebrow">INGREDIENT RECORD</p><h2>${esc(item.displayName)}</h2><p>${esc(item.visualFamilyLabel)} · ${item.recordCount} 条来源记录</p>${badge(quality(item))}</div></div><p class="source-note">${item.nameNeedsReview?'名称仍待源图确认，暂不参与自动推荐。':item.displayNameCorrections?'显示名称已根据源图核对；原始文字与编号保留。':'显示名称支持简繁转换，保留原始食材身份。'}${item.conflictCategories.length?` 不同来源在 ${item.conflictCategories.map(esc).join('、')} 等类别有不同标示，当前图表采用一条代表记录。`:''}</p><div class="source-profile">${item.presence.map((v,i)=>`<span class="source-category ${v===1?'is-marked':''}"><i style="background:${palette[i]}"></i>${esc(cat(i))}<b>${v===null?'?':v?'有':'未标'}</b></span>`).join('')}</div><p class="source-note">${artStatus(item)==='family_illustration'?'图片采用同类形态示意，不表示该品种的精确外观。':'图片为统一风格插画，供界面识别与视觉探索。'}</p><p class="source-note">原始名称：${esc(item.name)} · 代表记录：${esc(item.canonical.recordId)}。未标示不等于化学不存在。</p><div class="source-records">${rows.map(r=>`<div class="source-record"><div><strong>PDF ${r.pdfPage} 页 · ${r.role==='main'?'主食材':'搭配行'}</strong><small>${esc(r.tableId)} · ${r.reviewStatus==='complete_visual_review'?'逐格核图':'自动读取或局部复核'}</small></div><a href="${pdf}#page=${r.pdfPage}" target="_blank" rel="noopener">查看原页 ↗</a></div>`).join('')}</div>${item.records.length>35?`<p class="source-note">共 ${item.records.length} 条，完整记录可在来源数据中查看。</p>`:''}`;
    }
    content.querySelector('h2').id='sourceDialogTitle';
    if(!dialog.open)dialog.showModal();
  }
  function makeExport() {
    const entries=state.mode==='replace'?[{id:state.replacement||state.anchor,grams:100}]:state.selected;
    return {schema:'flavour-atelier-proposal-v1',name:state.mode==='replace'?`${get(state.anchor).displayName} → ${get(state.replacement||state.anchor).displayName}`:state.name,createdAt:new Date().toISOString(),mode:state.mode,replacementOf:state.mode==='replace'?{id:state.anchor,name:get(state.anchor).displayName,aromaMarkers:get(state.anchor).presence}:null,
      status:'untested_proposal',targets:[...state.targets].map(cat),
      ingredients:entries.map(x=>{const i=get(x.id);return {id:x.id,name:i.displayName,sourceName:i.name,grams:x.grams,aromaMarkers:i.presence,sourceRef:i.canonical.sourceRef,conflictingCategories:i.conflictCategories};}),
      aromaMarkerCounts:profile(entries).map(v=>({category:cat(v.index),count:v.count,unknown:v.unknown,totalIngredients:v.total})),
      method:'Ingredient amounts are editable trial quantities, not a flavor-intensity prediction. Aroma charts count categorical source markings. Pair links never validate a whole mixture.',
      pairEvidence:entries.flatMap((a,i)=>entries.slice(i+1).flatMap(b=>pairs(a.id,b.id).filter(e=>e.recommendationEligible).map(e=>({tableId:e.tableId,mainIngredient:get(e.mainId).displayName,pairedIngredient:get(e.pairedId).displayName,sharedCategories:e.sharedCategories,sharedMarkers:e.shared,unknownSharedCategories:e.unknownSharedCategories,sourceRef:e.sourceRef}))))};
  }
  function downloadJSON(value,filename) {const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
  let exportValue=null;
  function showExport(value){exportValue=value;$('exportText').value=JSON.stringify(value,null,2);$('exportDialog').showModal();}
  $('downloadExportButton').onclick=()=>{if(exportValue)downloadJSON(exportValue,`${exportValue.name}.json`);};
  $('copyExportButton').onclick=async()=>{try{await navigator.clipboard.writeText($('exportText').value);toast('提案内容已复制。');}catch(_){$('exportText').focus();$('exportText').select();toast('内容已选中，可复制后保存。');}};
  function saveRecipe() {
    if(!currentProfileItems().length){toast('先添加一款食材。');return;}
    const proposal=makeExport();saved.unshift(proposal);saved=saved.slice(0,30);
    try{localStorage.setItem(STORE,JSON.stringify(saved));toast('提案已保存在这台设备，可从“我的灵感”再次打开。');}
    catch(_){downloadJSON(proposal,`${state.name}.json`);toast('浏览器未允许本地保存，已改为下载提案。');}
    updateSavedCount();
  }
  function updateSavedCount(){if($('savedCount'))$('savedCount').textContent=String(saved.length);}
  function showSaved() {
    const dialog=$('savedRecipesDialog');if(!dialog)return;
    $('savedRecipesList').innerHTML=saved.map((r,i)=>`<article class="saved-recipe"><div class="saved-art-stack">${r.ingredients.slice(0,3).map(x=>get(x.id)?image(get(x.id),'saved-thumb'):'').join('')}</div><div><h3>${esc(r.name)}</h3><p>${r.ingredients.map(x=>esc(x.name)).join(' · ')}</p><small>待试做提案 · ${new Date(r.createdAt).toLocaleDateString('zh-CN')}</small></div><div class="saved-actions"><button type="button" class="text-button" data-load-saved="${i}">打开</button><button type="button" class="text-button" data-export-saved="${i}">导出</button><button type="button" class="text-button" data-delete-saved="${i}" aria-label="删除${esc(r.name)}">删除</button></div></article>`).join('') || '<div class="empty-state"><h3>还没有保存的提案</h3><p>选好食材后，点击“保存提案”。</p></div>';
    if(!dialog.open)dialog.showModal();
  }
  function setMode(mode) { if(!modeCopy[mode])return;state.mode=mode;state.query='';state.family='';state.visible=6;state.replacement=null;$('ingredientSearch').value='';if($('categoryFilter'))$('categoryFilter').value='';hideSearch();renderMode(); }
  document.addEventListener('click',event=>{
    const t=event.target.closest('button,a');
    if(t?.hasAttribute('data-download-catalog')){downloadJSON(DATA,'食材来源数据.json');return;}
    if(t?.hasAttribute('data-download-manifest')){if(window.FLAVOR_ASSET_MANIFEST){downloadJSON(window.FLAVOR_ASSET_MANIFEST,'图片资产目录.json');}else{const a=document.createElement('a');a.href='assets/manifest.json';a.download='图片资产目录.json';a.click();}return;}
    if(t?.dataset.mode) {setMode(t.dataset.mode);return;}
    if(t?.dataset.category!==undefined){const i=Number(t.dataset.category);state.targets.has(i)?state.targets.delete(i):state.targets.add(i);state.seed=0;renderCategories();renderCandidates();renderChart();return;}
    if(t?.dataset.makeMain){const chosen=state.selected.find(x=>x.id===t.dataset.makeMain);state.selected=[chosen,...state.selected.filter(x=>x.id!==chosen.id)];renderSelected();renderCandidates();renderRecipe();toast(`以 ${get(chosen.id).displayName} 为主食材。`);return;}
    if(t?.dataset.add){addIngredient(t.dataset.add);return;}
    if(t?.dataset.remove){state.selected=state.selected.filter(x=>x.id!==t.dataset.remove);renderSelected();renderCandidates();renderRecipe();return;}
    if(t?.dataset.searchId){selectSearch(t.dataset.searchId);return;}
    if(t?.dataset.detail){showDetail(t.dataset.detail);return;}
    if(t?.dataset.chart){state.chart=t.dataset.chart;renderChart();return;}
    if(t?.hasAttribute('data-clear-filter')){state.query='';state.family='';$('ingredientSearch').value='';$('categoryFilter').value='';hideSearch();renderCandidates();return;}
    if(t?.dataset.loadSaved!==undefined){const r=saved[Number(t.dataset.loadSaved)];state.selected=r.ingredients.filter(x=>byId.has(x.id)).map(x=>({id:x.id,grams:Number.isFinite(x.grams)?Math.max(0.1,Math.min(5000,x.grams)):10}));state.name=r.name;state.targets=new Set(r.targets.map(n=>categories.findIndex((_,i)=>cat(i)===n)).filter(i=>i>=0));$('savedRecipesDialog').close();if(r.mode==='replace'&&byId.has(r.replacementOf?.id)){setMode('replace');state.anchor=r.replacementOf.id;state.replacement=r.ingredients[0]?.id;renderMode();}else{setMode('compose');}toast('已恢复保存的提案。');return;}
    if(t?.dataset.exportSaved!==undefined){const r=saved[Number(t.dataset.exportSaved)];showExport(r);return;}
    if(t?.dataset.deleteSaved!==undefined){saved.splice(Number(t.dataset.deleteSaved),1);try{localStorage.setItem(STORE,JSON.stringify(saved));}catch(_){}updateSavedCount();showSaved();return;}
    if(!event.target.closest('.search-field,.search-wrap,.ingredient-search,.search-popover') && event.target!==$('ingredientSearch') && !$('searchPopover').contains(event.target))hideSearch();
  });
  $('ingredientSearch').addEventListener('input',search);
  $('ingredientSearch').addEventListener('focus',search);
  $('ingredientSearch').setAttribute('role','combobox');$('ingredientSearch').setAttribute('aria-autocomplete','list');$('ingredientSearch').setAttribute('aria-controls','searchResults');$('ingredientSearch').setAttribute('aria-expanded','false');$('searchResults').setAttribute('role','listbox');
  $('ingredientSearch').addEventListener('keydown',event=>{
    if(event.key==='Escape'){hideSearch();return;}
    if(['ArrowDown','ArrowUp'].includes(event.key)){
      event.preventDefault();if($('searchPopover').hidden)search();
      const n=state.searchMatches.length;if(!n)return;
      state.searchIndex=state.searchIndex<0?(event.key==='ArrowDown'?0:n-1):(state.searchIndex+(event.key==='ArrowDown'?1:-1)+n)%n;
      [...$('searchResults').querySelectorAll('[role=option]')].forEach((b,i)=>{b.classList.toggle('is-highlighted',i===state.searchIndex);b.setAttribute('aria-selected',String(i===state.searchIndex));});
      const id=`search-option-${state.searchIndex}`;$('ingredientSearch').setAttribute('aria-activedescendant',id);$(id)?.scrollIntoView({block:'nearest'});
    }
    if(event.key==='Enter' && state.searchMatches.length){event.preventDefault();selectSearch(state.searchMatches[Math.max(0,state.searchIndex)].id);}
  });
  document.addEventListener('change',event=>{
    if(event.target.matches('[data-grams]')){const n=Number(event.target.value);const row=state.selected.find(x=>x.id===event.target.dataset.grams);if(row){row.grams=Number.isFinite(n)?Math.max(0.1,Math.min(5000,n)):10;event.target.value=row.grams;}}
  });
  $('suggestButton').onclick=suggest;
  if($('shuffleButton'))$('shuffleButton').onclick=()=>{state.seed++;if(state.mode==='compose')suggest();else if(state.mode==='replace'){const c=candidates();if(c.length){state.replacement=c[state.seed%c.length].item.id;renderRecipe();}}else {state.visible=6;renderCandidates();toast('已换一组值得探索的候选。');}};
  $('resetButton').onclick=()=>{state.seed=0;state.anchor=(findName('奶油乳酪')||standard[0]).id;state.crossFamily=false;state.targets=new Set([0,2,7]);state.family=state.mode==='target'?'fruit':'';state.query='';state.visible=6;state.selected=standard.map((x,i)=>({id:x.id,grams:[100,35,8][i]}));state.replacement=null;state.name='草莓 · 柔和烘烤';$('ingredientSearch').value='';$('categoryFilter').value=state.family;hideSearch();renderMode();toast('已恢复初始灵感。');};
  $('saveRecipeButton').onclick=saveRecipe;
  if($('exportRecipeButton'))$('exportRecipeButton').onclick=()=>showExport(makeExport());
  if($('recipeName'))$('recipeName').addEventListener('input',e=>state.name=e.target.value.trim() || '未命名风味提案');
  $('sourceButton').onclick=()=>showDetail();$('sourceDialogClose').onclick=()=>$('sourceDialog').close();
  if($('savedButton'))$('savedButton').onclick=showSaved;
  if($('savedRecipesClose'))$('savedRecipesClose').onclick=()=>$('savedRecipesDialog').close();
  if($('savedRecipesDialogClose'))$('savedRecipesDialogClose').onclick=()=>$('savedRecipesDialog').close();
  document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',event=>{if(event.target===d){const rect=d.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)d.close();}}));
  if($('categoryFilter')){
    $('categoryFilter').innerHTML='<option value="">所有食材类别</option>'+Object.entries(familyNames).sort((a,b)=>a[1].localeCompare(b[1],'zh-Hans')).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('');
    $('categoryFilter').value=state.family;
    $('categoryFilter').onchange=e=>{state.family=e.target.value;state.visible=6;renderCandidates();};
  }
  if($('crossFamilyToggle'))$('crossFamilyToggle').onchange=e=>{state.crossFamily=e.target.checked;state.visible=6;renderCandidates();};
  $('ingredientTotal').textContent=DATA.ingredients.length.toLocaleString()+' 项食材记录';
  if($('assetCount'))$('assetCount').textContent=DATA.ingredients.length.toLocaleString();
  updateSavedCount();renderMode();
  window.FLAVOR_ENGINE={similarity,profile,candidates,makeExport,getState:()=>({...state,targets:[...state.targets]}),setMode};
})();
