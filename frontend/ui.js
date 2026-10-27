"use strict";
/* Reusable, escaped UI primitives shared by every analytics page. */
const UI = (() => {
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value == null ? '—' : typeof value === 'number' ? new Intl.NumberFormat('en', {maximumFractionDigits:Math.abs(value)>0&&Math.abs(value)<.01?6:2}).format(value) : String(value);
  const compact = value => typeof value === 'number' && Math.abs(value) >= 100000 ? new Intl.NumberFormat('en', {notation:'compact',maximumFractionDigits:2}).format(value) : fmt(value);
  const iconPaths = {dashboard:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',explorer:'M4 4h16v16H4z M4 9h16 M10 9v11',chat:'M4 4h16v12H9l-5 4z M8 8h8 M8 12h5',quality:'M12 3l8 3v6c0 4-8 9-8 9s-8-5-8-9V6z M8 12l3 3 5-6',insights:'M12 3v4 M12 17v4 M3 12h4 M17 12h4 M8 8l4-2 4 6-4 6-4-6z',segmentation:'M9 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6 M3 20v-3c0-4 12-4 12 0v3 M17 5a3 3 0 0 1 0 6 M18 14c3 0 3 3 3 6',anomalies:'M3 18l5-6 4 3 5-11 4 6 M3 21h18'};
  const icon = name => `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[name]||iconPaths.dashboard}"/></svg>`;
  const badge = (text, verified=false) => `<span class="badge ${verified?'verified':''}">${esc(text)}</span>`;
  const metrics = (data, foot='Calculated from active data') => `<div class="metrics">${Object.entries(data).filter(([,v])=>v!==undefined&&v!==null).map(([name,value],i)=>`<article class="metric"><div class="metric-label">${esc(name)}<span class="metric-symbol" aria-hidden="true">${['◈','▤','♧','▦','↗'][i%5]}</span></div><div class="metric-value" title="${esc(fmt(value))}">${esc(compact(value))}</div><div class="metric-foot">${esc(foot)}</div></article>`).join('')}</div>`;
  const panel = (title, body, subtitle='', extra='') => `<article class="panel ${extra}"><h2>${esc(title)}</h2>${subtitle?`<p class="subtext">${esc(subtitle)}</p>`:''}${body}</article>`;
  function table(data, max=100) {
    if(!data?.columns?.length || !data.rows.length) return '<p class="note">No matching records to display.</p>';
    return `<div class="table-wrap" tabindex="0" aria-label="Scrollable results"><table><thead><tr>${data.columns.map(c=>`<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${data.rows.slice(0,max).map(r=>`<tr>${data.columns.map(c=>`<td title="${esc(fmt(r[c]))}">${esc(fmt(r[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="note">Showing ${fmt(Math.min(max,data.rows.length))} of ${fmt(data.total_rows)} returned rows${data.truncated?' · Display capped; filter or aggregate for a smaller result.':''}</p>`;
  }
  let chartId = 0;
  const palette = ['#5B5CEB','#24a28b','#9c8aeb','#e7ab55','#528ccb','#cc789b'];
  const chartLayout = () => ({paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Segoe UI, Arial, sans-serif',size:12,color:'#606b80'},margin:{l:55,r:20,t:20,b:65},height:350,colorway:palette,hoverlabel:{bgcolor:'#182033',font:{color:'white'}},bargap:.28,xaxis:{gridcolor:'#eef0f6',zeroline:false,automargin:true},yaxis:{gridcolor:'#eef0f6',zeroline:false,automargin:true},legend:{orientation:'h',y:-.25}});
  function chart(figure) {
    if(!figure) return '<div class="chart-empty">A chart is not applicable to this result. The calculated table is available below.</div>';
    const id='chart-'+(++chartId);
    setTimeout(async()=>{const target=document.getElementById(id);if(!target)return;try{await Plotly.newPlot(target,figure.data,{...chartLayout(),...figure.layout,title:undefined},{responsive:true,displaylogo:false,modeBarButtons:[['toImage'],['zoom2d','pan2d','autoScale2d','resetScale2d']]});}catch{target.innerHTML='<p class="note">Chart unavailable. Review the calculated data table.</p>'; }},0);
    return `<div id="${id}" class="chart" role="img" aria-label="Interactive analytical chart"></div>`;
  }
  function customChart(data,x,y,kind='bar') {
    if(!data?.rows?.length)return '<p class="note">No values to chart.</p>';
    const rows=data.rows, trace={type:kind==='pie'?'pie':kind==='line'||kind==='scatter'?'scatter':'bar',x:rows.map(r=>r[x]),y:rows.map(r=>r[y]),marker:{color:palette[0]},mode:kind==='line'?'lines+markers':'markers'};
    if(kind==='pie'){trace.labels=trace.x;trace.values=trace.y;trace.hole=.64;delete trace.x;delete trace.y;trace.marker={colors:palette};trace.textinfo='percent';}
    return chart({data:[trace],layout:chartLayout()});
  }
  const analysisCard = a => panel(a.title,chart(a.figure)+`<details><summary>View calculated data & SQL</summary>${table(a.table)}<pre>${esc(a.sql)}</pre></details>`,'Active view and filters · calculated with DuckDB');
  const findings = values => `<ul class="findings">${values.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`;
  const options = (values, selected) => values.map(v=>`<option value="${esc(v)}" ${String(v)===String(selected)?'selected':''}>${esc(v)}</option>`).join('');
  function notice(message) {$('#notice').textContent=message;$('#notice').hidden=false;}
  function error(e) {$('#alert').innerHTML=`<strong>We couldn’t complete that action.</strong><div>${esc(e.message||e)}</div>${e.detail?`<details><summary>Technical details</summary>${esc(e.detail)}</details>`:''}`;$('#alert').hidden=false;}
  let pending=0;
  let locked=[];
  async function api(path,body,opts={}) {
    if(!pending){locked=Array.from(document.querySelectorAll('#dataset-strip select, #global-filters input, #global-filters select, #global-filters button')).filter(e=>!e.disabled);locked.forEach(e=>e.disabled=true);}
    pending++;$('#busy').hidden=false;$('#busy-text').textContent=opts.message||'Calculating your analysis…';
    try{const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-DataPilot':'1'},body:body===undefined?undefined:JSON.stringify(body)});let result;try{result=await response.json();}catch{throw Error('The server did not return a valid response. Check the connection and try again.');}if(!response.ok){const e=Error(result.error||'Request failed.');e.detail=result.detail;throw e;}return result;}
    finally{pending--;if(!pending){$('#busy').hidden=true;locked.forEach(e=>e.disabled=false);locked=[];}}
  }
  async function run(fn, button) {$('#alert').hidden=true;if(button)button.disabled=true;try{return await fn();}catch(e){error(e);}finally{if(button)button.disabled=false;}}
  return {$,esc,fmt,compact,icon,badge,metrics,panel,table,chart,customChart,analysisCard,findings,options,notice,error,api,run};
})();
