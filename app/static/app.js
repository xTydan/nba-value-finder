function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
async function loadGames(){
  const box=document.getElementById('games');
  try{
    const response=await fetch('/api/games');
    if(!response.ok)throw new Error('ESPN HTTP '+response.status);
    const data=await response.json();
    if(!data.events.length){box.innerHTML='<article class="provider"><b>Brak meczów w wybranym dniu</b><p>Sprawdź terminarz ponownie później.</p></article>';return}
    box.innerHTML=data.events.map(game=>{
      const teams=(game.competitors||[]).map(team=>`<span>${escapeHtml(team.abbreviation||team.name||'TBD')}</span>`).join('<i>vs</i>');
      const date=game.date?new Date(game.date).toLocaleString('pl-PL',{dateStyle:'short',timeStyle:'short'}):'Termin nieznany';
      return `<article class="provider game-card"><div class="game-date">${escapeHtml(date)}</div><div class="game-teams">${teams}</div><p>${escapeHtml(game.status||'Status nieznany')}${game.venue?' · '+escapeHtml(game.venue):''}</p></article>`;
    }).join('');
  }catch(error){box.innerHTML='<article class="provider"><b>Nie udało się pobrać terminarza</b><p>'+escapeHtml(error.message)+'</p></article>'}
}
async function refreshStatus(){
  const box=document.getElementById('providers');
  box.innerHTML='<p>Sprawdzanie źródeł…</p>';
  try{
    const response=await fetch('/api/status');
    const data=await response.json();
    box.innerHTML=data.providers.map(provider=>{
      const online=provider.available;
      return `<article class="provider"><b>${escapeHtml(provider.provider)}</b><span class="pill ${online?'online':''}">${online?'POŁĄCZONO':'NIEPODŁĄCZONE'}</span><p>${escapeHtml(provider.message)}</p></article>`;
    }).join('');
    document.getElementById('updated').textContent='Status: '+new Date(data.generated_at).toLocaleString('pl-PL');
  }catch(error){box.innerHTML='<article class="provider">Nie udało się pobrać statusu backendu.</article>'}
}
refreshStatus();
loadGames();
