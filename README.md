# NBA Value Finder

Publiczny, statyczny portal do wyszukiwania opłacalnych linii statystycznych zawodników NBA.

## Jak działa strona

1. GitHub Actions uruchamia skaner co 30 minut (minuty 07 i 37 każdej godziny).
2. Skaner pobiera przedmeczowe player props z PropLine, aktualny raport absencji i terminarz z ESPN oraz bieżącego sezonu NBA game logs i historyczne oficjalne raporty absencji przetworzone przez SportsDataverse.
3. Dane są normalizowane i zapisywane do `site/data/latest.json`.
4. GitHub Pages publikuje statyczną stronę. Przeglądarka nie łączy się bezpośrednio z API bukmacherskim, a klucz PropLine nigdy nie trafia do frontendu.
5. TOP VALUE pozostaje pusty, dopóki model prawdopodobieństwa nie przejdzie walidacji. Same linie i pokrycie L10 nie są wystarczającą podstawą do rekomendacji.

## Jednorazowa konfiguracja GitHub Pages

W repozytorium otwórz **Settings → Pages → Build and deployment** i ustaw **Source: GitHub Actions**. Workflow podejmuje też próbę automatycznego włączenia Pages, ale token GitHub Actions może nie mieć uprawnień administracyjnych.

Po włączeniu Pages workflow opublikuje stronę. Adres będzie miał postać:

`https://xtydan.github.io/nba-value-finder/`

## Sekrety

W Settings → Secrets and variables → Actions wymagany jest sekret:

- `ODDS_API_KEY` — klucz PropLine. Tylko workflow po stronie serwera ma do niego dostęp.

Nie umieszczaj klucza w plikach repozytorium, JavaScript ani w danych publikowanych na stronie.

## Aktualne źródła i ograniczenia

- ESPN public endpoints: terminarz i bieżący raport kontuzji.
- SportsDataverse: bieżący sezon NBA player game logs oraz historyczne wersje oficjalnych raportów absencji NBA. Pliki są cache'owane w GitHub Actions; na kartach pokazujemy datę ostatniego meczu w źródle.
- PropLine: zbiorczy feed NBA player props. Do publicznego widoku dopuszczamy wyłącznie rozpoznanych operatorów bukmacherskich; platformy fantasy i rynki predykcyjne są odrzucane.
- Superbet PL i STS nie są potwierdzonymi źródłami NBA player props w PropLine, więc nie będą wyświetlane pod ich nazwami.
- Linie są odrzucane, jeżeli mecz już się rozpoczął albo aktualizacja kursu jest starsza niż skonfigurowany limit.
- Gdy źródło jest niedostępne, strona pokazuje brak danych zamiast udawać, że stare dane są aktualne.

## Etapy rozwoju

- [x] Połączenie z PropLine i test uwierzytelnienia.
- [x] Automatyczny generator statycznego snapshotu.
- [x] Harmonogram GitHub Actions co 30 minut.
- [x] Frontend bez backendu działającego 24/7.
- [x] Filtrowanie feedu do rozpoznanych bukmacherów.
- [ ] Publikacja GitHub Pages (wymaga jednorazowego włączenia Pages w Settings).
- [ ] Pobieranie i normalizacja game logów całej ligi.
- [ ] Historyczne statusy dostępności zawodników i analiza absencji konkretnych teammate'ów.
- [ ] Model rozkładu wyników, kalibracja prawdopodobieństw i EV.
- [ ] Walidacja out-of-sample i dopiero potem publikowanie TOP VALUE.
- [ ] Rozliczanie historycznych typów i monitoring jakości modelu.

## Uruchomienie lokalne (opcjonalne)

```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Lokalny backend jest narzędziem developerskim. Docelowa publiczna strona korzysta z danych wygenerowanych przez GitHub Actions.
