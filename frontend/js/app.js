/* Frontend is a fully working same-origin SPA. All network actions require login. */
const $ = s => document.querySelector(s);
const safe = v => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={token:sessionStorage.getItem('sentinel_token'), role:'analyst',user:null,types:{},activeCase:null,chart:null,extractionPending:false};
const $content=$('#content');
let toastTimer;
function toast(message,error=false){const node=$('#toast');node.textContent=message;node.style.background=error?'#a8324d':'#102948';node.classList.add('open');clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove('open'),4500)}
async function api(url,opts={}){
  const headers={...(opts.headers||{})};if(state.token)headers.Authorization='Bearer '+state.token;
  if(opts.body && !(opts.body instanceof FormData))headers['Content-Type']='application/json';
  let res;try{res=await fetch(url,{...opts,headers})}catch(e){throw Error('Cannot reach the FastAPI server. Check it is running.');}
  let data;const raw=await res.text();try{data=raw?JSON.parse(raw):{}}catch(e){data={detail:raw.slice(0,160)}}
  if(!res.ok){if(res.status===401&&url!=='/api/auth/login')logout();let msg=data.detail||'Unexpected error';if(typeof msg!=='string')msg=JSON.stringify(msg);throw Error(msg)}
  return data;
}
async function login(event){event.preventDefault();$('#login-error').textContent='';const btn=event.submitter;btn.disabled=true;
  try{const out=await api('/api/auth/login',{method:'POST',body:JSON.stringify({email:$('#email').value,password:$('#password').value})});
    state.token=out.access_token;sessionStorage.setItem('sentinel_token',state.token);await init();}
  catch(e){$('#login-error').textContent=e.message}finally{btn.disabled=false}}
function logout(){state.token=null;state.user=null;state.activeCase=null;sessionStorage.removeItem('sentinel_token');$('#app').hidden=true;$('#login').hidden=false;$('#password').value=''}
async function init(){if(!state.token)return;
  try{state.user=await api('/api/auth/me');state.role=state.user.role;state.types=await api('/api/insurance-types');
    $('#login').hidden=true;$('#app').hidden=false;$('#user-email').textContent=state.user.email;
    $('#role-chip').textContent=state.role;$('#admin-nav').hidden=state.role!=='admin';await go('dashboard');}
  catch(e){toast(e.message,true);logout()}}
const num=v=>v===null||v===undefined?'—':Number(v).toLocaleString();
const panel=(title,inner)=>`<section class="panel"><h2>${safe(title)}</h2>${inner}</section>`;
async function go(view){
  $('#heading').textContent=({dashboard:'Overview',new:'New Case Analysis',cases:'Case Management',models:'Model Readiness',admin:'Administrator & Audit',details:'Case Details'})[view]||view;
  document.querySelectorAll('[data-view]').forEach(btn=>btn.classList.toggle('active',btn.dataset.view===view));
  $content.innerHTML='<div class="panel">Loading records…</div>';
  try{if(view==='dashboard')await dashboard();else if(view==='new')await newCase();else if(view==='cases')await cases();else if(view==='models')await models();else if(view==='admin')await adminView();}
  catch(e){$content.innerHTML=panel('Unable to display data',`<p class="bad">${safe(e.message)}</p>`)}
}
function badge(s){return `<span class="status ${safe(s)}">${safe(s)}</span>`}
async function dashboard(){const d=await api('/api/dashboard');
  $content.innerHTML=`<div class="section-head"><div><h2>Decision support at a glance</h2><p>Verified outcomes are distinct from possible indicators.</p></div><button id="start-analysis" class="btn primary">＋ Analyze new case</button></div>
  <div class="grid cards"><div class="metric"><span class="label">TOTAL CASES</span><strong>${num(d.total_cases)}</strong><small>All registered categories</small></div>
  <div class="metric"><span class="label">AWAITING HUMAN REVIEW</span><strong>${num(d.requiring_review)}</strong><small>Review is not a fraud verdict</small></div>
  <div class="metric"><span class="label">CASES WITH RULE INDICATORS</span><strong>${num(d.fraud_indicator_cases)}</strong><small>Detected inconsistencies</small></div>
  <div class="metric"><span class="label">CONFIRMED FRAUD OUTCOMES</span><strong>${num(d.confirmed_fraud_outcomes)}</strong><small>Human-recorded labels only</small></div></div>
  <div class="grid cols-2" style="margin-top:18px">${panel('Cases by insurance category','<div class="chartbox"><canvas id="category-chart" aria-label="Insurance types bar chart"></canvas></div>')}
  ${panel('Risk distribution','<div class="chartbox"><canvas id="bands-chart" aria-label="Provisional bands chart"></canvas></div>')}</div>
  <div class="grid cols-2" style="margin-top:18px">${panel('Recent cases',table(['Case','Category','Status'],d.recent_activity.map(c=>[
    `<button class="link" data-case="${safe(c.case_id)}">${safe(c.case_id.slice(0,8))}</button>`,safe(c.category),badge(c.status)])))}
  ${panel('Processing & oversight',`<div class="score-group"><div class="score-tile"><span>Average scoring latency</span><strong>${d.average_analysis_ms===null?'—':d.average_analysis_ms+' ms'}</strong></div><div class="score-tile"><span>Human-suspected outcomes</span><strong>${num(d.suspected_outcomes)}</strong></div></div><div class="info" style="margin-top:16px">${safe(d.note)}</div>`)}</div>`;
  $('#start-analysis').onclick=()=>go('new');bindCaseLinks();
  renderChart('category-chart','bar',d.categories);renderChart('bands-chart','doughnut',d.bands);
}
function renderChart(id,type,values){let canvas=$('#'+id);if(!canvas)return;
  const names=Object.keys(values);if(!window.Chart){canvas.replaceWith(document.createTextNode('Chart requires the optional Chart.js CDN. Counts: '+JSON.stringify(values)));return;}
  const palette=['#345fec','#21b3ad','#7a95e9','#d6a664','#9f83cb','#55a6cf','#9bd1b0'];
  new Chart(canvas,{type,data:{labels:names.length?names:['No records'],datasets:[{data:names.length?Object.values(values):[0],backgroundColor:palette,borderRadius:7}]},
    options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:type==='bar'?{y:{beginAtZero:true,ticks:{precision:0}}}:{}}});
}
function table(headers,rows){return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(v=>`<td>${v}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}" class="muted">No records yet</td></tr>`}</tbody></table></div>`}
const title=s=>s.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
async function newCase(){const options=Object.entries(state.types).map(([key,value])=>`<option value="${safe(key)}">${safe(value.name)}</option>`).join('');
  $content.innerHTML=`<div class="grid cols-2"><div>${panel('1. Case details',`<form id="case-form"><div class="field-grid"><label>Insurance type<select id="cat">${options}</select></label>
    <label>Case type<select id="kind"><option value="claim">Claim</option><option value="application">Application</option></select></label>
    <label>Reference (optional)<input id="extref" maxlength="80" placeholder="Your external tracking ID"></label></div>
    <hr class="separator"><div id="dynamic-fields" class="field-grid"></div><div class="btn-row" style="margin-top:20px"><button type="submit" class="btn primary">Save new case</button>
    <button type="button" class="btn" id="clear-form">Clear form</button></div></form>`)}
    </div><div>${panel('2. Evidence documents',`<div class="drop"><h3>PDF · PNG · JPEG · DOCX</h3><p class="muted">Create your case first; then attach one or more documents.</p>
      <label>Choose an evidence file<input type="file" id="doc-upload" accept=".pdf,.jpg,.jpeg,.png,.docx" disabled></label>
      <button id="upload-btn" class="btn" disabled>Upload & extract fields</button></div><div id="upload-status"></div>`)}
    ${panel('3. Run analysis',`<p class="muted">Review extracted policy, invoice, hospital and trip fields, then analyze. Synthetic demonstration models require administrator activation; no automatic retraining.</p>
    <button id="analyze-btn" class="btn success" disabled>Analyze saved case</button><p id="active-ref" class="muted"></p>`)}</div></div>`;
  renderFields();$('#cat').onchange=renderFields;$('#case-form').onsubmit=saveCase;$('#clear-form').onclick=()=>{state.activeCase=null;go('new')};
  $('#upload-btn').onclick=uploadDoc;$('#analyze-btn').onclick=runAnalysis;
}
function renderFields(keep={}){const cat=$('#cat').value;const r=state.types[cat];
  $('#dynamic-fields').innerHTML=Object.entries(r.fields).map(([key,kind])=>{
    const type=kind==='date'?'date':kind==='integer'||kind==='number'?'number':'text';
    const required=r.required.includes(key)?' <span class="muted">(priority field)</span>':'';
    return `<label class="${kind==='textarea'?'long':''}" for="field-${safe(key)}">${safe(title(key))}${required}${kind==='textarea'?`<textarea id="field-${safe(key)}" data-field="${safe(key)}"></textarea>`:`<input id="field-${safe(key)}" data-field="${safe(key)}" type="${type}" ${type==='number'?'step="any" min="0"':''}>`}</label>`;
  }).join('');
  document.querySelectorAll('[data-field]').forEach(el=>{if(keep[el.dataset.field]!==undefined)el.value=keep[el.dataset.field]});
}
function formData(){const data={};document.querySelectorAll('[data-field]').forEach(el=>{if(el.value.trim())data[el.dataset.field]=el.value.trim()});return data;}
function activeStatus(id){state.activeCase=id;$('#doc-upload').disabled=false;$('#upload-btn').disabled=false;$('#analyze-btn').disabled=false;
  $('#active-ref').textContent='Active case: '+id;}
async function saveCase(event){event.preventDefault();const btn=event.submitter;btn.disabled=true;
  try{const payload={category:$('#cat').value,kind:$('#kind').value,external_ref:$('#extref').value.trim()||null,data:formData()};
    const res=await api(state.activeCase?'/api/cases/'+state.activeCase:'/api/cases',{method:state.activeCase?'PATCH':'POST',body:JSON.stringify(payload)});
    activeStatus(res.id);state.extractionPending=false;toast('Case saved. You can upload evidence or analyze it.');}
  catch(e){toast(e.message,true)}finally{btn.disabled=false}}
async function uploadDoc(){if(!state.activeCase){toast('Save the case first',true);return;}const file=$('#doc-upload').files[0];if(!file){toast('Choose a file first',true);return;}
  const form=new FormData();form.append('file',file);$('#upload-btn').disabled=true;
  try{const res=await api(`/api/cases/${state.activeCase}/documents`,{method:'POST',body:form});
    const entries=Object.entries(res.extracted);let filled=0,conflicts=[];
    entries.forEach(([key,value])=>{const field=document.querySelector(`[data-field="${key}"]`);if(!field)return;
      if(!field.value){field.value=value.value;filled++}else if(String(field.value)!==String(value.value))conflicts.push(key);
    });
    $('#upload-status').innerHTML=`<div class="info" style="margin-top:12px">Uploaded ${safe(file.name)}. ${entries.length} fields found; ${filled} empty fields populated.
    ${conflicts.length?`<strong>Review conflicts: ${safe(conflicts.join(', '))}</strong>`:''}</div>
    <p class="muted">${res.warnings.map(safe).join(' · ')}</p>
    <p class="muted">These values are unconfirmed OCR/regex results. Review them and click “Save new case” before analysis.</p>`;
    state.extractionPending=true;toast('Document processed. Review extraction and save corrections.');$('#doc-upload').value='';}
  catch(e){toast(e.message,true)}finally{$('#upload-btn').disabled=false}}
async function runAnalysis(){if(!state.activeCase)return;$('#analyze-btn').disabled=true;
  try{
    if(state.extractionPending){
      if(!confirm('Have you reviewed the automatically extracted values? Confirm to save the displayed fields and analyze.'))return;
      await api('/api/cases/'+state.activeCase,{method:'PATCH',body:JSON.stringify({category:$('#cat').value,
        kind:$('#kind').value,external_ref:$('#extref').value.trim()||null,data:formData()})});
      state.extractionPending=false;
    }
    await api(`/api/cases/${state.activeCase}/analyze`,{method:'POST'});await showCase(state.activeCase);toast('Analysis stored successfully');}
  catch(e){toast(e.message,true)}finally{const btn=$('#analyze-btn');if(btn)btn.disabled=false}}
async function cases(){const types=Object.entries(state.types).map(([k,v])=>`<option value="${safe(k)}">${safe(v.name)}</option>`).join('');
  $content.innerHTML=panel('Find saved claims',`<form id="search-form" class="form-row"><label>Case ID or reference<input id="search" placeholder="Search by reference"></label>
    <label>Category<select id="filter-cat"><option value="">All insurance types</option>${types}</select></label>
    <label>Status<select id="filter-status"><option value="">All statuses</option><option value="draft">Draft</option><option value="review">Review</option><option value="processed">Processed</option></select></label>
    <button class="btn primary">Search cases</button></form>`)+`<section class="panel" style="margin-top:20px"><h2>Case records</h2><div id="case-list">Loading…</div><div id="case-pagination"></div></section>`;
  $('#search-form').onsubmit=e=>{e.preventDefault();loadCaseList(0)};await loadCaseList(0);
}
async function loadCaseList(offset){const q=new URLSearchParams({q:$('#search').value,category:$('#filter-cat').value,status:$('#filter-status').value,limit:'20',offset:String(offset)});
  const r=await api('/api/cases?'+q);$('#case-list').innerHTML=table(['Case','Category','Claim','Status','Latest score','Created'],r.items.map(c=>[
    `<button class="link" data-case="${safe(c.id)}">${safe(c.external_ref||c.id.slice(0,12))}</button>`,safe(title(c.category)),safe(c.kind),badge(c.status),
    c.latest_score===null?'Unavailable':safe(c.latest_score+'/100'),safe(c.created_at.slice(0,10))]));bindCaseLinks();
  $('#case-pagination').innerHTML=`<p class="muted">Showing ${offset+1}–${offset+r.items.length} of ${r.total} cases</p>
    <div class="btn-row"><button id="prev-page" class="btn" ${offset===0?'disabled':''}>Previous</button><button id="next-page" class="btn" ${offset+r.items.length>=r.total?'disabled':''}>Next</button></div>`;
  $('#prev-page').onclick=()=>loadCaseList(Math.max(0,offset-20));$('#next-page').onclick=()=>loadCaseList(offset+20);
}
function bindCaseLinks(){document.querySelectorAll('[data-case]').forEach(btn=>btn.onclick=()=>showCase(btn.dataset.case))}
async function showCase(id){const c=await api('/api/cases/'+id);$('#heading').textContent='Case · '+(c.external_ref||c.id.slice(0,12));
  const result=c.analyses.at(-1)?.result;
  const scoreTiles=result?`<div class="score-group"><div class="score-tile"><span>Fraud suspicion index (demo if modeled)</span><strong>${result.fraud_suspicion_score===null?'Unavailable':safe(result.fraud_suspicion_score)+'/100'}</strong></div>
      <div class="score-tile"><span>Underwriting risk</span><strong>Not trained</strong></div>
      <div class="score-tile"><span>Data completeness</span><strong>${safe(result.data_completeness_pct)}%</strong></div><div class="score-tile"><span>Decision band</span><strong>${safe(result.decision_band)}</strong></div></div>
      <p class="warning">${safe(result.fraud_score_interpretation)}. ${safe(result.disclaimer)}</p>
      <div class="model-readiness"><strong>Model readiness:</strong> ${safe(result.model?.status||'unavailable')} — ${safe(result.model?.reason|| (result.model?.training_data_kind==='synthetic_demo'?'SIMULATED training labels; NOT a verified fraud probability.':'See below'))}
        <p><strong>Model input completeness:</strong> ${safe(result.model_input_completeness_pct??'—')}% (${safe(result.model_inputs_present?.length??'—')} of 7 supported inputs; minimum ${safe(result.minimum_model_inputs||5)})</p>
        <p>Missing model inputs: ${safe((result.missing_model_inputs||[]).map(title).join(', ')||'none')}</p>
        ${(result.next_steps||[]).map(t=>`<p>➜ ${safe(t)}</p>`).join('')}
        ${result.fraud_suspicion_score===null && state.role==='admin'?'<button id="setup-missing-model" class="btn primary">Manage demonstration models</button>':''}
      </div>
      <h3>Evidence-backed findings (${result.rules.length})</h3>${result.rules.length?result.rules.map(rule=>`<div class="flag"><strong>${safe(rule.code)} · ${safe(rule.severity)} / 100 severity</strong><p>${safe(rule.message)}</p><pre>${safe(JSON.stringify(rule.evidence,null,2))}</pre></div>`).join(''):'<p class="muted">No deterministic discrepancies detected; this does not prove legitimacy.</p>'}
      <h3>Model output & explanation</h3><pre class="json">${safe(JSON.stringify(result.model,null,2))}</pre>
      <div class="info"><strong>Recommendation:</strong> ${safe(result.recommendation)}<p>Missing fields: ${safe(result.missing_required.join(', ')||'none')}</p><p>${safe(result.scoring_method)}</p></div>`:'<p class="muted">Not analyzed yet. Upload documents and save corrections first.</p>';
  const docs=c.documents.map(d=>`<div class="doc-card"><strong>${safe(d.name)}</strong> · ${safe(Math.round(d.bytes/1024))} KB <div class="btn-row" style="margin-top:10px">
    <button class="btn" data-download="${safe(d.id)}">Download evidence</button><button class="btn danger" data-delete="${safe(d.id)}">Delete evidence</button></div>
    <details><summary>Extracted fields & technical observations</summary><pre class="json">${safe(JSON.stringify({fields:d.extracted,image:d.image_assessment,warnings:d.warnings},null,2))}</pre></details></div>`).join('');
  const fields=Object.entries(c.data).map(([key,value])=>`<tr><td>${safe(title(key))}</td><td>${safe(value)}</td></tr>`).join('');
  $content.innerHTML=`<div class="section-head"><div><h2>${safe(c.external_ref||c.id)}</h2><p>${safe(title(c.category))} · ${badge(c.status)} · Human outcome: ${safe(c.outcome)}</p></div>
     <div class="btn-row"><button id="case-back" class="btn">← Case list</button><button id="case-analyze" class="btn primary">↻ Re-run analysis</button><button id="edit-values" class="btn">Correct fields</button></div></div>
    ${panel('Risk analysis & evidence',scoreTiles)}<div class="grid cols-2" style="margin-top:18px">${panel('Saved case fields',`<table>${fields||'<tr><td>No manual fields</td></tr>'}</table>`)}
    ${panel('Supporting documents',docs||'<p class="muted">No evidence uploaded.</p>')}</div>
    ${state.role==='admin'?panel('Authorized investigation outcome',`<form id="outcome-form" class="form-row"><label>Verified human outcome<select name="outcome">
      ${['unknown','suspected','confirmed_fraud','legitimate','unresolved'].map(x=>`<option value="${x}" ${c.outcome===x?'selected':''}>${safe(title(x))}</option>`).join('')}</select></label><button class="btn">Save verified outcome</button></form>`):''}`;
  if($('#setup-missing-model'))$('#setup-missing-model').onclick=()=>go('admin');
  $('#case-back').onclick=()=>go('cases');$('#case-analyze').onclick=async()=>{await api('/api/cases/'+id+'/analyze',{method:'POST'});showCase(id);toast('Fresh analysis stored');};
  $('#edit-values').onclick=async()=>{await go('new');$('#cat').value=c.category;renderFields(c.data);$('#cat').disabled=true;$('#kind').value=c.kind;$('#extref').value=c.external_ref||'';activeStatus(id);};
  document.querySelectorAll('[data-download]').forEach(btn=>btn.onclick=()=>downloadDoc(btn.dataset.download));
  document.querySelectorAll('[data-delete]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Permanently delete this evidence document?'))return;try{await api('/api/documents/'+btn.dataset.delete,{method:'DELETE'});showCase(id)}catch(e){toast(e.message,true)}});
  if(state.role==='admin')$('#outcome-form').onsubmit=async event=>{event.preventDefault();const form=new FormData(event.target);try{await api(`/api/cases/${id}/outcome`,{method:'POST',body:form});showCase(id);toast('Human outcome saved.')}catch(e){toast(e.message,true)}};
}
async function downloadDoc(id){try{const res=await fetch('/api/documents/'+id+'/download',{headers:{Authorization:'Bearer '+state.token}});
  if(!res.ok)throw Error((await res.json()).detail||'Download failed');const blob=await res.blob();
  const header=res.headers.get('content-disposition')||'';const match=header.match(/filename\*?=(?:UTF-8'')?"?([^";]*)/i);
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=match?decodeURIComponent(match[1]):'evidence';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);
}catch(e){toast(e.message,true)}}
async function models(){const data=await api('/api/models');const readiness=Object.entries(state.types).map(([key,v])=>{
  const active=data.find(m=>m.category===key&&m.deployed);
  return [safe(v.name),active?badge(active.is_synthetic?'synthetic_demo':'research_trained'):badge('unavailable'),
    active?safe(active.id.slice(0,8)):'—',safe('Underwriting: unavailable')];
});
  $content.innerHTML=`<div class="warning">A synthetic demonstration model is NOT validated for real insurance claims. Model metrics describe only the relevant held-out dataset. Form completeness does not guarantee enough model inputs.</div>
  <div style="margin-top:18px">${panel('Category-specific model readiness',table(['Insurance category','Fraud model','Version','Other tasks'],readiness))}</div>
  <div style="margin-top:18px">${panel('Model history and held-out evaluation',table(['Category','Model ID','State','Training data','Held-out PR-AUC','Deployed'],data.map(m=>[
    safe(title(m.category)),safe(m.id.slice(0,13)),badge(m.approval_status),m.is_synthetic?'SYNTHETIC demonstration':'Authorized dataset',
    m.metrics?.held_out_test?.pr_auc==null?'—':safe(Number(m.metrics.held_out_test.pr_auc).toFixed(3)),m.deployed?'Yes':'No'])))}</div>`;
}
async function adminView(){if(state.role!=='admin'){toast('Administrator role required',true);return go('dashboard')}
  const [datasets,versions,audit,settings]=await Promise.all([api('/api/admin/datasets'),api('/api/models'),api('/api/admin/audit'),api('/api/admin/settings')]);
  const opts=Object.entries(state.types).map(([id,type])=>`<option value="${safe(id)}">${safe(type.name)}</option>`).join('');
  $content.innerHTML=`${panel('Set up SYNTHETIC demo models',`<p>These models use fictional training data only. Deploy motor, health and travel so you can test the bundled PDFs, or activate all 14 supported categories. Existing active models are preserved and this operation is idempotent.</p>
    <div class="btn-row"><button class="btn primary" id="demo-three">Prepare Motor + Health + Travel</button><button class="btn" id="demo-all">Prepare all 14 categories</button></div>
    <p class="muted" id="demo-progress">Training may take 10–90 seconds depending on your laptop. Models persist in runtime/model_artifacts; return to your case and click Re-run analysis.</p>`)}
    <div class="grid cols-2" style="margin-top:18px">${panel('Import labeled CSV',`<form id="dataset-form"><div class="field-grid"><label>Insurance category<select name="category">${opts}</select></label>
    <label>Data provenance<input name="source" required placeholder="Dataset owner/source"></label><label>Permission / license<input name="permitted_use" required placeholder="Permitted research use"></label>
    <label class="long">Target definition<input name="label_definition" required placeholder="0 = legitimate, 1 = confirmed fraud only"></label>
    <label class="long">Upload CSV<input name="file" type="file" required accept=".csv"></label>
    <label><input name="synthetic" type="checkbox" value="true" style="width:auto"> Clearly labeled synthetic data</label></div>
    <button class="btn primary" type="submit">Import & validate dataset</button></form><p class="muted">CSV requires: fraud_label, ${safe(['claim_amount','coverage_amount','invoice_total','prior_claims','days_to_report','claim_coverage_ratio','claim_invoice_gap'].join(', '))}. Optional entity_group protects against cross-split identity leakage.</p>`)}
    ${panel('Training workflow',`<p class="muted">Train on labeled data using scikit-learn and XGBoost, compare validation performance, and record a separate held-out test result.</p>
    ${table(['Dataset','Category','Type','Actions'],datasets.map(d=>[safe(d.id.slice(0,10)),safe(d.category),d.is_synthetic?'Synthetic':'Authorized',`<button class="btn train" data-train="${d.id}">Train candidate</button>`]))}`)}</div>
    <div class="grid cols-2" style="margin-top:18px">${panel('Model deployment / rollback',table(['Model','Category','Validation state','Actions'],versions.map(m=>[
      safe(m.id.slice(0,10)),safe(m.category),badge(m.approval_status),m.deployed?'Active':`<button class="btn deploy" data-deploy="${m.id}">Deploy version</button>`])))}
    ${panel('Provisional risk-scoring configuration',`<form id="settings-form"><div class="field-grid">
    <label>Model weight (0–1)<input type="number" step="0.05" min="0" max="1" name="model_weight" value="${safe(settings.scoring_policy.model_weight)}" required></label>
    <label>Low upper boundary<input type="number" min="1" max="98" name="low" value="${safe(settings.scoring_policy.thresholds.low)}" required></label>
    <label>Moderate upper boundary<input type="number" min="2" max="99" name="moderate" value="${safe(settings.scoring_policy.thresholds.moderate)}" required></label>
    <label>High upper boundary<input type="number" min="3" max="100" name="high" value="${safe(settings.scoring_policy.thresholds.high)}" required></label>
    </div><p class="muted">Rules receive the remaining weight. Provisional settings are not approved decision thresholds.</p><button class="btn">Save & audit settings</button></form>`)}
    ${panel('Recent audit events',table(['Action','Object','Time'],audit.slice(0,35).map(e=>[safe(e.action),safe((e.object_id||'').slice(0,12)),safe(e.at.slice(0,19).replace('T',' '))])))}</div>`;
  async function provisionCategories(cats,btn){
    if(!confirm('Train and deploy strictly SYNTHETIC demonstration models for '+cats.length+' categories? Existing deployed models will not be replaced.'))return;
    btn.disabled=true;$('#demo-progress').textContent='Training synthetic models. Please keep this page open…';
    try{const res=await api('/api/admin/demo-models',{method:'POST',body:JSON.stringify({categories:cats})});
      state.types=await api('/api/insurance-types');
      const completed=res.results.filter(r=>r.status==='trained_and_deployed').length;
      toast('Demo model preparation complete: '+completed+' new models. Existing cases must be re-analyzed.');await adminView();
    }catch(e){toast(e.message,true);$('#demo-progress').textContent='Training failed: '+e.message;btn.disabled=false}
  }
  $('#demo-three').onclick=e=>provisionCategories(['motor','health','travel'],e.currentTarget);
  $('#demo-all').onclick=e=>provisionCategories(Object.keys(state.types),e.currentTarget);
  $('#settings-form').onsubmit=async event=>{
    event.preventDefault();try{const body=new FormData(event.target);
      const res=await api('/api/admin/settings',{method:'POST',body});toast(res.warning);await adminView();
    }catch(e){toast(e.message,true)}
  };
  $('#dataset-form').onsubmit=async event=>{event.preventDefault();const btn=event.submitter;btn.disabled=true;
    try{const body=new FormData(event.target);if(!body.has('synthetic'))body.set('synthetic','false');const r=await api('/api/admin/datasets',{method:'POST',body});
      toast(`Imported dataset: ${r.quality.rows} rows, ${r.quality.duplicate_rows} exact duplicates`);await adminView();}
    catch(e){toast(e.message,true)}finally{btn.disabled=false}};
  document.querySelectorAll('[data-train]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Train a new model candidate now? This may take a while.'))return;
    btn.disabled=true;try{const r=await api('/api/admin/train/'+btn.dataset.train,{method:'POST'});
      toast('Trained model '+r.model_id.slice(0,8)+'; review evaluation before deployment');await adminView();}
    catch(e){toast(e.message,true)}finally{btn.disabled=false}});
  document.querySelectorAll('[data-deploy]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Deploy this model for DEMONSTRATION? A previously deployed model will be deactivated.'))return;
    try{const r=await api('/api/admin/models/'+btn.dataset.deploy+'/deploy',{method:'POST'});toast(r.warning);state.types=await api('/api/insurance-types');await adminView();}
    catch(e){toast(e.message,true)}});
}
$('#login-form').addEventListener('submit',login);$('#logout').onclick=logout;
document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>go(btn.dataset.view)));
init();
