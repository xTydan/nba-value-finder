# NBA Player Props

Statyczny portal do przeglądania przedmeczowych linii statystycznych zawodników NBA według pokrycia w ostatnich meczach.

## Jak działa

1. GitHub Actions odświeża dane co 30 minut.
2. Kursy player props pobierane są z PropLine; raport absencji i terminarz z ESPN; statystyki zawodników i historyczne raporty absencji z SportsDataverse.
3. Linie są łączone z historią zawodnika po identyfikatorze i zweryfikowanej nazwie.
4. Ranking pokazuje pokrycie Over i Under dla każdej konkretnej linii, wyniki ostatnich meczów, średnią, minuty oraz dostępne kursy obu stron.
5. Strona jest statyczna i publikowana przez GitHub Pages. Klucz API pozostaje w sekrecie GitHub Actions.

## Ranking i filtry

- Filtr statystyki: punkty, zbiórki, asysty, trójki, przechwyty, bloki, straty, P+R, P+A, R+A, PRA i bloki + przechwyty.
- Sortowanie: najwyższe pokrycie, średnia z ostatnich meczów, kurs, średnie minuty.
- Wyszukiwanie zawodnika.
- Pokrycie jest liczone jako liczba meczów, w których wynik był powyżej lub poniżej dokładnej linii. Push jest osobno oznaczony.
- Do rankingu trafiają linie z minimum 5 meczami historii. Jeśli gracz rozegrał mniej niż 10 spotkań w dostępnym feedzie sezonu, pokazujemy faktyczną liczbę, nie dopisujemy brakujących meczów.
- Pokrycie historyczne nie jest prognozą prawdopodobieństwa ani gwarancją wyniku.

## Bukmacherzy

PropLine dokumentuje Superbet PL i STS jako źródła linii meczowych NBA, ale nie potwierdza dla nich NBA player props. Dlatego portal nie będzie przypisywał im kursów zawodników, których feed faktycznie nie dostarcza. Gdy te rynki zostaną udostępnione, parser dopuści ich rzeczywiste oferty. Obecnie widoczne są wyłącznie kursy operatorów dostarczających player props.

## Konfiguracja

W GitHub → Settings → Secrets and variables → Actions ustaw sekret `ODDS_API_KEY` z kluczem PropLine.

GitHub Pages: Settings → Pages → Source: GitHub Actions.

Adres: https://xtydan.github.io/nba-value-finder/

## Zasady jakości danych

- Nie generujemy fikcyjnych linii ani kursów.
- Nie pokazujemy kursów z meczu, który już się rozpoczął.
- Stare kursy są odrzucane.
- Brak historii lub niejednoznaczne dopasowanie zawodnika oznacza brak tej linii w rankingu.
- Analiza wpływu absencji teammate'ów jest opisowa; małe próby nie są przedstawiane jako dowód przyczynowości.
