function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function marketName(k){return String(k||'').replace(/^player_/,'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
function renderPicks(items,analysis,status){
 const box=document.getElementById('picks');
 const picks=items||[];
 document.getElementById('pick-count').textContent=picks.length+' value '+(picks.length===1?'picki':'picków');
 if(!picks.length){
  box.innerHTML='<article class="empty-state"><div class="empty-icon">⌁</div><h2>Brak zakładów spełniających kryteria</h2><p>To prawidłowy wynik skanera — nie publikujemy typów na siłę. Gdy kurs będzie wyraźnie lepszy od niezależnego konsensusu rynku i dane będą kompletne, propozycja pojawi się tutaj.</p><small>'+esc(status||'Progi selekcji są aktywne.')+'</small></article>';
  return;
 }
 box.innerHTML=picks.map(x=>{
  const f=x.form||{},l=x.l10||f.l10||{};
  const start=x.commence_time?new Date(x.commence_time).toLocaleString('pl-PL',{dateStyle:'short',timeStyle:'short'}):'Termin nieznany';
  const splits=(analysis?.[x.analysis_key]?.teammate_splits||[]).slice(0,2);
  const splitHtml=splits.length?splits.map(z=>'<div class="split-line"><b>'+esc(z.teammate)+'</b>: z nim '+esc(z.active_games)+' mecz. · '+esc(z.average_with_active)+' | bez niego '+esc(z.out_games)+' mecz. · '+esc(z.average_with_out)+' | Δ '+(z.delta_average>0?'+':'')+esc(z.delta_average)+(z.confidence==='small_sample'?' · mała próba':'')+'</div>').join(''):'<div class="split-line muted">Brak wystarczającej próby potwierdzonych absencji teammate’ów</div>';
  return '<article class="pick-card"><div class="pick-top"><span class="pick-market">'+esc(marketName(x.market))+'</span><span class="pick-ev">EV +'+(x.ev*100).toFixed(1)+'%</span></div><div class="pick-player">'+esc(x.player)+'</div><div class="pick-match">'+esc(x.away_team||'')+' @ '+esc(x.home_team||'')+' · '+esc(start)+'</div><div class="pick-main"><div><small>REKOMENDOWANY ZAKŁAD</small><strong>'+esc(x.side.toUpperCase())+' '+esc(x.line)+'</strong></div><div class="pick-odds"><small>KURS</small><strong>'+Number(x.decimal_odds).toFixed(2)+'</strong><span>'+esc(x.bookmaker)+'</span></div></div><div class="pick-metrics"><div><small>FAIR PROBABILITY</small><b>'+(x.fair_probability*100).toFixed(1)+'%</b></div><div><small>EDGE</small><b>+'+(x.edge*100).toFixed(1)+' pp</b></div><div><small>L10</small><b>'+esc(l.hits??'—')+'/'+esc(l.decided??'—')+'</b></div><div><small>PRÓBA</small><b>'+esc(f.sample_size??'—')+'</b></div></div><div class="pick-detail"><span>Konsensus bez marży z '+esc(x.reference_books)+' innych bukmacherów</span><span>Średnia L10: '+esc(f.average_l10??'—')+' · minuty: '+esc(f.average_minutes_l10??'—')+'</span></div><div class="split-box">'+splitHtml+'</div><small class="pick-foot">Kurs odświeżony '+esc(x.age_seconds)+' s temu · metoda: niezależny konsensus no-vig</small></article>';
 }).join('');
}
function renderInjuries(items){
 const box=document.getElementById('injuries-list');
 if(!items.length){box.innerHTML='<article class="provider"><b>Brak wpisów w raporcie</b><p>Brak wpisu nie oznacza potwierdzonej pełnej dyspozycji.</p></article>';return}
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
  renderPicks(data.picks||[],data.player_analysis||{},data.picks_status);renderInjuries(data.injuries||[]);renderGames(data.games||[]);
  const sources=data.sources||[],ok=sources.filter(s=>s.available).length;
  document.getElementById('system-status').textContent=sources.length&&ok===sources.length?'● WSZYSTKIE ŹRÓDŁA OK':ok?'● DANE CZĘŚCIOWE':'● BRAK DANYCH';
  document.getElementById('updated').textContent='Ostatnia analiza: '+new Date(data.generated_at).toLocaleString('pl-PL');
  document.getElementById('providers').innerHTML=sources.map(s=>'<article class="provider"><div class="odds-head"><b>'+esc(s.name)+'</b><span class="pill '+(s.available?'online':'')+'">'+(s.available?'OK':'BRAK DANYCH')+'</span></div>'+(s.error?'<p>'+esc(s.error)+'</p>':(s.message?'<p>'+esc(s.message)+'</p>':'<p>Źródło odpowiedziało poprawnie.</p>'))+'</article>').join('');
 }catch(e){
  document.getElementById('system-status').textContent='● BRAK SNAPSHOTU';
  document.getElementById('picks').innerHTML='<article class="provider"><b>Dane jeszcze nieopublikowane</b><p>'+esc(e.message)+' · uruchomienie workflow GitHub Actions utworzy pierwszy snapshot.</p></article>'
 }
}
loadSnapshot();
