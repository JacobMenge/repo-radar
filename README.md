# repo-radar

**Was hat sich seit dem letzten Mal auf meinen GitHub-Repos getan?**

Ein kleines Kommandozeilen-Werkzeug für die GitHub-REST-API. Ein Aufruf, und du
siehst auf einen Blick:

* **Sterne, Forks und offene Issues** je Repo – mit der Änderung seit dem
  letzten Lauf
* **wer neu einen Stern vergeben hat**
* **neue Issues und Pull Requests von anderen** in deinen Repos
* **den Stand deiner eigenen Pull Requests** in fremden Repos (offen, gemergt,
  geschlossen – und ob sich das seit dem letzten Mal geändert hat)

Ich nutze es, um nach einem Video zu sehen, ob auf den Repos dazu etwas
passiert ist, ohne mich durch die Benachrichtigungen zu klicken.

---

## Installation

Nur Python 3.10 oder neuer, keine weiteren Pakete.

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
python repo_radar.py JacobMenge --nur-anzeigen           # Stand nicht fortschreiben
```

| Option | Bedeutung |
|---|---|
| `--tage N` | Zeitraum für neue Issues und Sterne. Ohne Angabe: seit dem letzten Lauf, beim ersten Lauf 7 Tage |
| `--forks` | geforkte Repos mitzählen |
| `--markdown DATEI` | Bericht zusätzlich als Markdown speichern |
| `--stand DATEI` | wo der letzte Stand liegt (Standard: `daten/stand.json`) |
| `--nur-anzeigen` | Stand nicht aktualisieren – der nächste Lauf vergleicht noch mit demselben |

Beispiel:

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

Ohne Anmeldung erlaubt GitHub 60 Anfragen pro Stunde – für ein paar Läufe am
Tag reicht das, ein Lauf braucht meist 3 bis 5. **Wer einen Stern vergeben
hat**, gibt GitHub allerdings nur mit Token heraus; ohne Token steht dort nur
die Anzahl.

repo-radar nimmt automatisch

1. die Umgebungsvariable `GITHUB_TOKEN` (oder `GH_TOKEN`), sonst
2. das Token der GitHub CLI, wenn du mit `gh auth login` angemeldet bist.

Ein [Fine-grained Token](https://github.com/settings/personal-access-tokens)
ohne zusätzliche Rechte (nur öffentliche Repos lesen) genügt. repo-radar
liest nur, es ändert nichts auf GitHub.

## Wie es funktioniert

| Was | API-Endpunkt |
|---|---|
| Repos mit Sternen, Forks, Issues | `GET /users/{user}/repos` |
| Wer wann einen Stern gab | `GET /repos/{owner}/{repo}/stargazers` (mit `star+json`) – nur für Repos, deren Sternzahl gestiegen ist, von der neuesten Seite rückwärts |
| Neue Issues/PRs von anderen | Suche `user:{user} -author:{user} created:>…` |
| Eigene PRs in fremden Repos | Suche `is:pr author:{user} -user:{user}` |

Der letzte Stand liegt in `daten/stand.json` (steht nicht im Repo). Löschst du
die Datei, fängt repo-radar von vorne an.

## Tests

```bash
python -m unittest discover -s tests
```

Die Tests laufen ohne Netz – die GitHub-API wird durch feste Antworten
ersetzt. Bei jedem Push prüft eine GitHub Action alle Python-Versionen von
3.10 bis 3.13.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
