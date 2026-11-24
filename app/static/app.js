function byId(id){return document.getElementById(id)}
function setText(id,value){const el=byId(id);if(el)el.textContent=value}
function setHTML(id,value){const el=byId(id);if(el)el.innerHTML=value}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
const marketLabels={player_points:'Punkty',player_rebounds:'Zbiórki',player_assists:'Asysty',player_threes:'3 — Rzuty za trzy',player_steals:'Przechwyty',player_blocks:'Bloki',player_turnovers:'Straty',player_points_rebounds:'Punkty + zbiórki',player_points_assists:'Punkty + asysty',player_rebounds_assists:'Zbiórki + asysty',player_points_rebounds_assists:'PRA',player_blocks_steals:'Bloki + przechwyty'};
let allProps=[],analysisData={},selectedEvent=null,showAllMatchProps=false;
function selectedOddsRange(){const v=byId('odds-range')?.value||'main';return v==='wide'?[1.50,2.50]:v==='all'?[1.40,3.00]:[1.70,2.20]}
function quoteForRange(x,side){const range=selectedOddsRange(),list=x[side+'_quotes']||(x[side+'_quote']?[x[side+'_quote']]:[]);return list.filter(q=>Number(q.odds)>=range[0]&&Number(q.odds)<=range[1]).sort((a,b)=>Math.abs(Number(a.odds)-1.90)-Math.abs(Number(b.odds)-1.90))[0]||null}
function quoteHTML(q,label){if(!q)return '<div class="quote unavailable"><small>'+label+'</small><b>Brak kursu</b></div>';const odds=Number(q.odds);const preferred=odds>=1.70&&odds<=2.20;return '<div class="quote '+(preferred?'preferred':'')+'"><small>'+label+(preferred?' · PREFEROWANY ZAKRES':'')+'</small><b>'+odds.toFixed(2)+'</b><span>'+esc(q.bookmaker||'Bukmacher')+'</span></div>'}
function dateLabel(value){if(!value)return 'Data nieznana';const d=new Date(value+'T12:00:00');return Number.isNaN(d.getTime())?String(value):d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'});}
function recentHTML(games,line){return '<div class="recent-games-grid">'+games.map(g=>{const v=Number(g.value);const match=g.matchup||g.opponent||'Mecz '+(g.game_id||'');return '<div class="recent-game-cell" title="'+esc(match)+' · '+esc(g.date||'')+'"><span class="recent-chip '+(v>line?'hit':v<line?'miss':'push')+'">'+esc(v)+'</span><b>'+esc(dateLabel(g.date))+'</b><small>'+esc(match||'Rywal nieznany')+'</small></div>'}).join('')+'</div>'}
function cardHTML(x){
 x={...x,over_quote:quoteForRange(x,'over'),under_quote:quoteForRange(x,'under')};
 const start=x.commence_time?new Date(x.commence_time).toLocaleString('pl-PL',{dateStyle:'short',timeStyle:'short'}):'Termin nieznany';
 const split=(analysisData[x.analysis_key]?.teammate_splits||[]).slice(0,3);
 const splitHTML=split.length?split.map(s=>'<div class="split-line"><b>'+esc(s.teammate)+'</b>'+(s.position?' · '+esc(s.position):'')+(s.same_position?' · TA SAMA POZYCJA':'')+' · '+esc(s.average_teammate_minutes??'—')+' min śr.: z nim '+esc(s.active_games)+' mecz. · '+esc(s.average_with_active)+' | bez niego '+esc(s.out_games)+' mecz. · '+esc(s.average_with_out)+' | Δ '+(Number(s.delta_average)>0?'+':'')+esc(s.delta_average)+'</div>').join(''):'<div class="split-line muted">Brak wystarczającej próby potwierdzonych absencji w ostatnich 10 meczach</div>';
 return '<article class="pick-card"><div class="pick-top"><span class="pick-market">'+esc(marketLabels[x.market]||x.market)+'</span><span class="coverage-badge">'+x.sample_size+' MECZÓW</span></div><div class="pick-player">'+esc(x.player)+(x.player_position?' <span class="position-tag">'+esc(x.player_position)+'</span>':' <span class="position-tag muted">POZ. —</span>')+'</div><div class="pick-match">'+esc(x.away_team||'')+' @ '+esc(x.home_team||'')+' · '+esc(start)+'</div><div class="line-heading"><span>LINIA</span><strong>'+esc(x.line)+'</strong><span>ŚREDNIA L10: '+esc(x.average_l10??'—')+'</span><span>MINUTY: '+esc(x.average_minutes_l10??'—')+'</span></div><div class="coverage-grid"><div class="coverage over"><small>OVER — '+(x.over_quote?'KURS 1.60–2.20':'BRAK KURSU W ZAKRESIE')+'</small><strong>'+x.over_hits+'/'+x.sample_size+'</strong><span>'+Math.round(x.over_rate*100)+'%</span></div><div class="coverage under"><small>UNDER — '+(x.under_quote?'KURS 1.60–2.20':'BRAK KURSU W ZAKRESIE')+'</small><strong>'+x.under_hits+'/'+x.sample_size+'</strong><span>'+Math.round(x.under_rate*100)+'%</span></div></div><div class="recent-title">OSTATNIE MECZE · wynik statystyki względem linii</div>'+recentHTML(x.recent_games||[],Number(x.line))+'<div class="quote-grid">'+quoteHTML(x.over_quote,'KURS OVER')+quoteHTML(x.under_quote,'KURS UNDER')+'</div><div class="split-box">'+splitHTML+'</div><small class="pick-foot">'+(x.pushes?'Push: '+x.pushes+' · ':'')+'Dane historyczne: ostatnie '+x.sample_size+' występów · pokrycie nie jest prognozą</small></article>';
}
function renderBoard(){
 const market=byId('market-filter')?.value||'all',sort=byId('sort-filter')?.value||'coverage',name=(byId('player-filter')?.value||'').trim().toLowerCase();
 let rows=allProps.filter(x=>(market==='all'||x.market===market)&&(!name||String(x.player).toLowerCase().includes(name))&&(!selectedEvent||String(x.event_id)===String(selectedEvent)));
 rows=rows.filter(x=>{const oq=quoteForRange(x,'over'),uq=quoteForRange(x,'under');if(selectedEvent&&showAllMatchProps)return !!oq||!!uq;return (!!oq&&x.over_hits>=8)|| (!!uq&&x.under_hits>=8)});
 rows.sort((a,b)=>{
  if(sort==='average')return (b.average_l10??-Infinity)-(a.average_l10??-Infinity);
  if(sort==='minutes')return (b.average_minutes_l10??-Infinity)-(a.average_minutes_l10??-Infinity);
  const ao=[quoteForRange(a,'over')?.odds,quoteForRange(a,'under')?.odds].filter(Boolean),bo=[quoteForRange(b,'over')?.odds,quoteForRange(b,'under')?.odds].filter(Boolean);
  if(sort==='odds')return Math.min(...bo.map(v=>Math.abs(v-1.90)))-Math.min(...ao.map(v=>Math.abs(v-1.90)));
  const ah=Math.max(quoteForRange(a,'over')?a.over_hits:0,quoteForRange(a,'under')?a.under_hits:0),bh=Math.max(quoteForRange(b,'over')?b.over_hits:0,quoteForRange(b,'under')?b.under_hits:0);
  return bh-ah||Math.min(...ao.map(v=>Math.abs(v-1.90)))-Math.min(...bo.map(v=>Math.abs(v-1.90)))||b.sample_size-a.sample_size;
 });
 rows=rows.slice(0,24);
 setText('pick-count',rows.length+(selectedEvent?(showAllMatchProps?' linii meczu':' najlepszych linii meczu'):' najlepszych linii'));
 const toggle=byId('match-all-toggle');if(toggle){toggle.hidden=!selectedEvent;toggle.textContent=showAllMatchProps?'Pokaż tylko najlepsze propsy':'Pokaż wszystkie linie (maks. 24)'}
 const box=byId('picks');if(!box)return;
 box.innerHTML=rows.length?rows.map(cardHTML).join(''):'<article class="empty-state"><h2>'+(selectedEvent?'Brak pasujących propsów w tym meczu':'Brak mocnych propozycji')+'</h2><p>'+(selectedEvent?(showAllMatchProps?'Nie znaleziono ofert w wybranym zakresie kursów.':'Brak propsów z pokryciem co najmniej 8/10 w wybranym zakresie. Możesz rozszerzyć kursy lub wyświetlić wszystkie linie.'):'Brak ofert z pokryciem co najmniej 8/10 w wybranym zakresie kursów.')+'</p></article>';
}
function historyDayStats(picks){
 const counts={WIN:0,LOSS:0,PUSH:0,VOID:0,PENDING:0};
 let profit=0,settled=0;
 picks.forEach(p=>{const r=p.result||'PENDING';counts[r]=(counts[r]||0)+1;if(r==='WIN'){profit+=Number(p.odds)-1;settled++;}else if(r==='LOSS'){profit-=1;settled++;}});
 const decided=counts.WIN+counts.LOSS;
 return {...counts,profit,settled,decided,hitRate:decided?counts.WIN/decided*100:0,roi:settled?profit/settled*100:0};
}
function renderPickHistory(history,rootId='pick-history',summaryId='history-summary',allTypes=false){
 const root=byId(rootId);if(!root)return;
 const days=Object.entries(history?.days||{}).sort((a,b)=>b[0].localeCompare(a[0]));
 if(!days.length){root.innerHTML='<article class="empty-state"><h2>Historia dopiero się buduje</h2><p>'+(allTypes?'Od 25.11 archiwum zapisuje wszystkie kwalifikujące się strony OVER i UNDER widoczne na stronie.':'Archiwum zapisuje dzienną listę maksymalnie 24 najlepszych propozycji.')+' Wyniki będą rozliczane po pojawieniu się oficjalnych statystyk meczu.</p></article>';setText(summaryId,'0 dni');return;}
 let total={WIN:0,LOSS:0,PUSH:0,VOID:0,PENDING:0,profit:0,settled:0};
 root.innerHTML=days.map(([day,data])=>{
  const picks=data.picks||[],s=historyDayStats(picks);
  ['WIN','LOSS','PUSH','VOID','PENDING'].forEach(k=>total[k]+=s[k]);
  total.profit+=s.profit;total.settled+=s.settled;
  const rows=picks.map(p=>'<tr><td>'+esc(p.player||'—')+'</td><td>'+esc((p.away_team||'')+' @ '+(p.home_team||''))+'</td><td>'+esc(marketLabels[p.market]||p.market||'—')+'</td><td><b>'+esc(p.side||'—')+' '+esc(p.line)+'</b></td><td>'+Number(p.odds||0).toFixed(2)+'</td><td>'+esc(p.bookmaker||'—')+'</td><td>'+esc(p.l10_hits||0)+'/'+esc(p.l10_sample||0)+'</td><td>'+(p.actual===null||p.actual===undefined?'—':esc(p.actual))+'</td><td><span class="history-result '+String(p.result||'PENDING').toLowerCase()+'">'+esc(p.result||'PENDING')+'</span></td></tr>').join('');
  return '<article class="history-day"><div class="history-day-head"><div><b>'+esc(day)+'</b><small>Zapisano: '+esc(data.captured_at?new Date(data.captured_at).toLocaleString('pl-PL'):'—')+'</small></div><div class="history-day-score"><strong>'+s.WIN+'/'+(s.WIN+s.LOSS)+'</strong><small>skuteczność rozliczonych</small></div></div><div class="history-stats"><span><b>'+s.WIN+'</b> WIN</span><span><b>'+s.LOSS+'</b> LOSS</span><span><b>'+s.PUSH+'</b> PUSH</span><span><b>'+s.VOID+'</b> VOID</span><span><b>'+s.PENDING+'</b> PENDING</span><span class="'+(s.profit>=0?'positive':'negative')+'"><b>'+(s.profit>0?'+':'')+s.profit.toFixed(2)+'</b> j.</span></div><div class="history-table-wrap"><table class="history-table"><thead><tr><th>Zawodnik</th><th>Mecz</th><th>Rynek</th><th>Typ</th><th>Kurs</th><th>Bookmaker</th><th>L10</th><th>Wynik</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></div></article>';
 }).join('');
 const decided=total.WIN+total.LOSS,rate=decided?Math.round(total.WIN/decided*100):0,roi=total.settled?total.profit/total.settled*100:0;
 setText(summaryId,days.length+' dni · '+total.WIN+'W / '+total.LOSS+'L · '+rate+'% skuteczności · ROI '+roi.toFixed(1)+'%');
}
function renderInjuries(items){const box=byId('injuries-list');if(!box)return;const rows=Array.isArray(items)?items:[];box.innerHTML=rows.length?rows.map(x=>'<article class="provider"><div class="odds-head"><b>'+esc(x.player||'Nieznany zawodnik')+'</b><span class="pill">'+esc(x.status||'STATUS NIEZNANY')+'</span></div><p>'+esc(x.team||'Drużyna nieznana')+(x.details?' · '+esc(x.details):'')+'</p><small>Źródło: ESPN · '+esc(x.date||'data aktualizacji niepodana')+'</small></article>').join(''):'<article class="provider"><b>Brak wpisów w raporcie</b><p>Brak wpisu nie oznacza potwierdzonej pełnej dyspozycji.</p></article>'}
function renderGames(items){
 const box=byId('games-list');if(!box)return;
 const grouped=new Map();
 allProps.forEach(p=>{const id=String(p.event_id||'');if(!id)return;if(!grouped.has(id))grouped.set(id,{id,home:p.home_team||'Gospodarze',away:p.away_team||'Goście',date:p.commence_time,count:0,markets:new Set()});const g=grouped.get(id);g.count++;g.markets.add(p.market)});
 const rows=[...grouped.values()].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 const selected=selectedEvent?rows.find(g=>g.id===String(selectedEvent)):null;
 const back=selected?'<button class="back-matches" id="back-matches">← Wszystkie mecze</button>':'';
 const cards=selected?'<article class="provider selected-match"><b>'+esc(selected.away)+' @ '+esc(selected.home)+'</b><p>'+esc(selected.date?new Date(selected.date).toLocaleString('pl-PL',{dateStyle:'full',timeStyle:'short'}):'Termin nieznany')+'</p><small>'+selected.count+' linii · '+selected.markets.size+' statystyk</small></article>'+renderMatchInjuries(selected):rows.map(g=>'<button class="match-select" data-event="'+esc(g.id)+'"><b>'+esc(g.away)+' @ '+esc(g.home)+'</b><span>'+esc(g.date?new Date(g.date).toLocaleString('pl-PL',{dateStyle:'medium',timeStyle:'short'}):'Termin nieznany')+'</span><small>'+g.count+' linii · '+g.markets.size+' statystyk</small></button>').join('');
 box.innerHTML=back+(cards||'<article class="provider"><b>Brak meczów z dostępnymi liniami</b><p>Mecze pojawią się, gdy źródło udostępni przedmeczowe player props.</p></article>');
 box.querySelectorAll('[data-event]').forEach(button=>button.addEventListener('click',()=>{selectedEvent=button.dataset.event;showAllMatchProps=false;renderGames(items);renderBoard();byId('games')?.scrollIntoView({behavior:'smooth',block:'start'});}));
 byId('back-matches')?.addEventListener('click',()=>{selectedEvent=null;showAllMatchProps=false;renderGames(items);renderBoard();byId('games')?.scrollIntoView({behavior:'smooth',block:'start'});});
}
function renderMatchInjuries(match){
 const injuries=window.currentInjuries||[];
 const teams=[match.home,match.away].map(x=>String(x||'').toLowerCase());
 const rows=injuries.filter(x=>{const t=String(x.team||'').toLowerCase();return t&&teams.some(team=>team===t||team.includes(t)||t.includes(team));});
 return '<div class="match-injuries"><h3>Absencje w tym meczu</h3>'+(rows.length?rows.map(x=>'<div class="match-injury"><b>'+esc(x.player||'Nieznany zawodnik')+'</b><span>'+esc(x.team||'')+' · '+esc(x.status||'Status nieznany')+'</span>'+(x.details?'<small>'+esc(x.details)+'</small>':'')+'</div>').join(''):'<p>Brak potwierdzonych absencji starterów lub ważnej rotacji dla tych drużyn w aktualnym raporcie. Brak wpisu nie oznacza gwarantowanej pełnej dyspozycji.</p>')+'</div>';
}
async function loadSnapshot(){try{const res=await fetch('./data/latest.json?ts='+Date.now(),{cache:'no-store'});if(!res.ok)throw new Error('Snapshot HTTP '+res.status);const data=await res.json();const previousEvent=selectedEvent;allProps=Array.isArray(data.props_board)?data.props_board:[];analysisData=data.player_analysis||{};window.currentInjuries=Array.isArray(data.injuries)?data.injuries:[];const eventStillExists=previousEvent&&allProps.some(p=>String(p.event_id)===String(previousEvent));selectedEvent=eventStillExists?previousEvent:null;renderBoard();renderGames(data.games);const sources=Array.isArray(data.sources)?data.sources:[],ok=sources.filter(s=>s.available).length;setText('system-status',sources.length&&ok===sources.length?'● WSZYSTKIE ŹRÓDŁA OK':ok?'● DANE CZĘŚCIOWE':'● BRAK DANYCH');setText('updated',data.generated_at?'Ostatnia analiza: '+new Date(data.generated_at).toLocaleString('pl-PL'):'Brak daty analizy');setHTML('providers',sources.map(s=>'<article class="provider"><div class="odds-head"><b>'+esc(s.name)+'</b><span class="pill '+(s.available?'online':'')+'">'+(s.available?'OK':'BRAK DANYCH')+'</span></div>'+(s.error?'<p>'+esc(s.error)+'</p>':(s.message?'<p>'+esc(s.message)+'</p>':'<p>Źródło odpowiedziało poprawnie.</p>'))+'</article>').join(''))}catch(e){setText('system-status','● BŁĄD ŁADOWANIA DANYCH');setText('pick-count','—');setHTML('picks','<article class="provider"><b>Nie udało się wczytać danych</b><p>'+esc(e.message)+' · sprawdź GitHub Actions.</p></article>');setText('updated','Nie udało się pobrać aktualnego snapshotu')}}
async function loadPickHistory(){try{const res=await fetch('./data/pick_history.json?ts='+Date.now(),{cache:'no-store'});if(!res.ok)throw new Error('History HTTP '+res.status);renderPickHistory(await res.json());}catch(e){setText('history-summary','Archiwum chwilowo niedostępne');setHTML('pick-history','<article class="empty-state"><p>Nie udało się wczytać archiwum: '+esc(e.message)+'</p></article>');}}
async function loadAllPickHistory(){try{const res=await fetch('./data/all_pick_history.json?ts='+Date.now(),{cache:'no-store'});if(!res.ok)throw new Error('All history HTTP '+res.status);renderPickHistory(await res.json(),'all-pick-history','all-history-summary',true);}catch(e){setText('all-history-summary','Archiwum chwilowo niedostępne');setHTML('all-pick-history','<article class="empty-state"><p>Nie udało się wczytać pełnego archiwum: '+esc(e.message)+'</p></article>');}}
['market-filter','sort-filter','player-filter','odds-range'].forEach(id=>byId(id)?.addEventListener('input',renderBoard));
byId('match-all-toggle')?.addEventListener('click',()=>{showAllMatchProps=!showAllMatchProps;renderBoard()});
loadSnapshot();loadPickHistory();loadAllPickHistory();
// Odświeżaj snapshot i archiwum co 30 minut; nie resetuj filtrów ani wybranego meczu.
const AUTO_REFRESH_MS=30*60*1000;
let refreshInProgress=false;
setInterval(async()=>{if(refreshInProgress)return;refreshInProgress=true;try{await Promise.all([loadSnapshot(),loadPickHistory(),loadAllPickHistory()]);}finally{refreshInProgress=false;}},AUTO_REFRESH_MS);
