function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function marketName(k){return String(k||'').replace(/^player_/,'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
let allOdds=[];let visibleOdds=200;let playerAnalysis={};
function renderOdds(items,analysis){
 allOdds=items||[];playerAnalysis=analysis||{};visibleOdds=200;drawOdds();
}
function drawOdds(){
 const box=document.getElementById('odds');
 const term=(document.getElementById('odds-search')?.value||'').trim().toLocaleLowerCase('pl-PL');
 const filtered=allOdds.filter(x=>[x.player,x.home_team,x.away_team,x.market,x.bookmaker].join(' ').toLocaleLowerCase('pl-PL').includes(term));
 document.getElementById('odds-count').textContent=filtered.length+' ofert'+(term?' · filtrowanie':'');
 if(!filtered.length){box.innerHTML='<article class="provider"><b>Brak pasujących linii</b><p>Zmień wyszukiwaną frazę albo poczekaj na kolejną aktualizację.</p></article>';document.getElementById('odds-more').hidden=true;return}
 box.innerHTML=filtered.slice(0,visibleOdds).map(x=>{
  const start=x.commence_time?new Date(x.commence_time).toLocaleString('pl-PL',{dateStyle:'short',timeStyle:'short'}):'Termin nieznany';
  const f=x.form;
  const l10=f?.l10?('L10: '+f.l10.hits+'/'+f.l10.decided+(f.l10.pushes?' · push '+f.l10.pushes:'')+(f.l10.rate!==null?' ('+Math.round(f.l10.rate*100)+'%)':'')):'L10: brak historii';
  const l5=f?.l5?('L5: '+f.l5.hits+'/'+f.l5.decided+(f.l5.pushes?' · push '+f.l5.pushes:'')):'L5: —';
  const analysis=playerAnalysis[x.analysis_key]||{};
  const splits=(analysis.teammate_splits||[]).slice(0,2);
  const splitHtml=splits.length?splits.map(z=>'<div class="split-line"><b>'+esc(z.teammate)+'</b>: z nim '+esc(z.active_games)+' mecz. avg '+esc(z.average_with_active)+' · bez niego '+esc(z.out_games)+' mecz. avg '+esc(z.average_with_out)+' · różnica '+(z.delta_average>0?'+':'')+esc(z.delta_average)+(z.confidence==='small_sample'?' · mała próba':'')+'</div>').join(''):'<div class="split-line muted">Brak wystarczającej próby potwierdzonych absencji konkretnych kolegów z drużyny</div>';
  return '<article class="provider"><div class="odds-head"><b>'+esc(x.player)+'</b><span class="pill">'+esc(x.side)+' '+esc(x.line)+'</span></div><p>'+esc(marketName(x.market))+' · '+esc(x.home_team||'')+' – '+esc(x.away_team||'')+'</p><div class="odds-price"><strong>'+Number(x.decimal_odds).toFixed(2)+'</strong><span>'+esc(x.bookmaker)+'</span></div><div class="form-row"><b>'+esc(l10)+'</b><span>'+esc(l5)+'</span></div>'+(f?'<small>Średnia L10: '+esc(f.average_l10)+' · minuty: '+esc(f.average_minutes_l10)+' · próba: '+esc(f.sample_size)+'</small>':'<small>Statystyki historyczne niedostępne lub zawodnik nie został jednoznacznie dopasowany</small>')+'<div class="split-box">'+splitHtml+'</div><small>Mecz: '+esc(start)+' · kurs zaktualizowany '+esc(x.age_seconds)+' s temu</small></article>'
 }).join('');
 const more=document.getElementById('odds-more');
 more.hidden=filtered.length<=visibleOdds;
 more.textContent='POKAŻ WIĘCEJ ('+Math.min(200,filtered.length-visibleOdds)+')';
}
function renderInjuries(items){
 const box=document.getElementById('injuries-list');
 if(!items.length){box.innerHTML='<article class="provider"><b>Brak wpisów w raporcie</b><p>Źródło nie zwróciło obecnie zgłoszonych absencji. Brak wpisu nie oznacza potwierdzonej pełnej dyspozycji.</p></article>';return}
 box.innerHTML=items.map(x=>'<article class="provider"><div class="odds-head"><b>'+esc(x.player||'Nieznany zawodnik')+'</b><span class="pill">'+esc(x.status||'STATUS NIEZNANY')+'</span></div><p>'+esc(x.team||'Drużyna nieznana')+(x.details?' · '+esc(x.details):'')+'</p><small>Źródło: ESPN · '+esc(x.date||'data aktualizacji niepodana')+'</small></article>').join('');
}
function renderGames(items){
 const box=document.getElementById('games-list');
 if(!items.length){box.innerHTML='<article class="provider"><b>Brak meczów w pobranym terminarzu</b></article>';return}
 box.innerHTML=items.map(g=>{
  const teams=(g.competitors||[]).map(t=>esc(t.abbreviation||t.name||'TBD')).join(' vs ');
  const date=g.date?new Date(g.date).toLocaleString('pl-PL',{dateStyle:'short',timeStyle:'short'}):'Termin nieznany';
  return '<article class="provider"><b>'+teams+'</b><p>'+esc(date)+' · '+esc(g.status||'Status nieznany')+'</p></article>'
 }).join('');
}
async function loadSnapshot(){
 try{
  const res=await fetch('./data/latest.json?ts='+Date.now(),{cache:'no-store'});
  if(!res.ok)throw new Error('Nie udało się pobrać snapshotu ('+res.status+')');
  const data=await res.json();
  renderOdds(data.odds||[],data.player_analysis||{});renderInjuries(data.injuries||[]);renderGames(data.games||[]);
  const sources=data.sources||[];
  const ok=sources.filter(s=>s.available).length;
  const status=sources.length&&ok===sources.length?'● WSZYSTKIE ŹRÓDŁA OK':ok?'● DANE CZĘŚCIOWE':'● BRAK DANYCH';
  document.getElementById('system-status').textContent=status;
  document.getElementById('updated').textContent='Ostatnia analiza: '+new Date(data.generated_at).toLocaleString('pl-PL');
  document.getElementById('pick-count').textContent=(data.picks||[]).length+' rekomendacji';
  document.getElementById('providers').innerHTML=(data.sources||[]).map(s=>'<article class="provider"><div class="odds-head"><b>'+esc(s.name)+'</b><span class="pill '+(s.available?'online':'')+'">'+(s.available?'OK':'BRAK DANYCH')+'</span></div>'+(s.error?'<p>'+esc(s.error)+'</p>':(s.message?'<p>'+esc(s.message)+'</p>':'<p>Źródło odpowiedziało poprawnie.</p>'))+'</article>').join('');
  if(!data.picks?.length){document.getElementById('picks').innerHTML='<article class="provider"><b>Model w przygotowaniu</b><p>Feed kursów i dane źródłowe są prezentowane, ale rekomendacje value pozostają wyłączone do czasu walidacji modelu.</p></article>'}
 }catch(e){
  document.getElementById('system-status').textContent='● BRAK SNAPSHOTU';
  document.getElementById('picks').innerHTML='<article class="provider"><b>Dane jeszcze nieopublikowane</b><p>'+esc(e.message)+' · uruchomienie workflow GitHub Actions utworzy pierwszy snapshot.</p></article>'
 }
}
document.getElementById('odds-search')?.addEventListener('input',()=>{visibleOdds=200;drawOdds()});
document.getElementById('odds-more')?.addEventListener('click',()=>{visibleOdds+=200;drawOdds()});
loadSnapshot();
