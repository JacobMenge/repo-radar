# repo-radar

**Was hat sich seit dem letzten Mal auf meinen GitHub-Repos getan?**

Ein kleines Kommandozeilen-Tool für die GitHub-API. Nach einem Video will ich
wissen, ob auf den Repos dazu etwas passiert ist. Dafür klicke ich mich nicht
mehr durch die Benachrichtigungen, sondern starte einfach repo-radar.

Das Tool zeigt dir:

* **Sterne, Forks und offene Issues** pro Repo, dazu die Änderung seit dem
  letzten Lauf
* **wer neu einen Stern vergeben hat**
* **neue Issues und Pull Requests von anderen** in deinen Repos
* **deine eigenen Pull Requests** in fremden Repos: offen, gemergt oder
  geschlossen und ob sich daran seit dem letzten Mal etwas geändert hat

## Installation

Du brauchst nur Python 3.10 oder neuer. Weitere Pakete sind nicht nötig.

```bash
git clone https://github.com/JacobMenge/repo-radar.git
cd repo-radar
python repo_radar.py DEIN-NAME
```

## Aufruf

```bash
python repo_radar.py JacobMenge                          # seit dem letzten Lauf
python repo_radar.py JacobMenge --tage 7                 # die letzten 7 Tage
python repo_radar.py JacobMenge --markdown bericht.md    # zusätzlich als Datei
python repo_radar.py JacobMenge --nur-anzeigen           # Stand nicht speichern
```

| Option | Bedeutung |
|---|---|
| `--tage N` | Zeitraum für neue Issues und Sterne. Ohne Angabe gilt der letzte Lauf, beim ersten Mal sind es 7 Tage |
| `--forks` | geforkte Repos mitzählen |
| `--markdown DATEI` | Bericht zusätzlich als Markdown speichern |
| `--stand DATEI` | wo der letzte Stand liegt (Standard: `daten/stand.json`) |
| `--nur-anzeigen` | Stand nicht speichern, der nächste Lauf vergleicht also mit demselben |

So sieht das aus:

```
## Repos von JacobMenge (19)

Repo                                         Sterne     Forks    Issues
lern-unterlagen                              6 (+1)         7         0
device-orientation-color-interpolation            3         0         0
...

## Neue Sterne
- lern-unterlagen: beispiel-nutzer (24.09.2026 21:40)

## Meine Pull Requests in fremden Repos
- github/advisory-database#9773 [gemergt] ...  <- vorher offen
```

## Token (optional)

Ohne Anmeldung erlaubt GitHub 60 Anfragen pro Stunde. Ein Lauf braucht meist
3 bis 5, für ein paar Läufe am Tag reicht das also locker. Wer einen Stern
vergeben hat, verrät GitHub aber nur mit Token. Ohne Token siehst du dort nur
die Anzahl.

repo-radar sucht das Token selbst:

1. zuerst in der Umgebungsvariable `GITHUB_TOKEN` (oder `GH_TOKEN`)
2. sonst bei der GitHub CLI, wenn du mit `gh auth login` angemeldet bist

Ein [Fine-grained Token](https://github.com/settings/personal-access-tokens)
ohne zusätzliche Rechte reicht aus. repo-radar liest nur und ändert nichts auf
GitHub.

## Wie es funktioniert

| Was | API-Endpunkt |
|---|---|
| Repos mit Sternen, Forks und Issues | `GET /users/{user}/repos` |
| Wer wann einen Stern gab | `GET /repos/{owner}/{repo}/stargazers` mit `star+json`. Nur bei Repos mit mehr Sternen als beim letzten Mal, ab der neuesten Seite |
| Neue Issues und PRs von anderen | Suche `user:{user} -author:{user} created:>…` |
| Eigene PRs in fremden Repos | Suche `is:pr author:{user} -user:{user}` |

Der letzte Stand liegt in `daten/stand.json` und landet nicht im Repo. Wenn du
die Datei löschst, fängt repo-radar von vorne an.

## Tests

```bash
python -m unittest discover -s tests
```

Die Tests brauchen kein Netz, weil die GitHub-API durch feste Antworten
ersetzt wird. Bei jedem Push laufen sie per GitHub Action auf Python 3.10 bis
3.13.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
