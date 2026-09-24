"""repo-radar: Was hat sich seit dem letzten Mal auf meinen GitHub-Repos getan?

Fragt die GitHub-REST-API ab und zeigt:
  * Sterne, Forks und offene Issues je Repo - mit Änderung seit dem letzten Lauf
  * wer neu einen Stern vergeben hat
  * neue Issues und Pull Requests von anderen in meinen Repos
  * den Stand meiner eigenen Pull Requests in fremden Repos

Nur lesend, keine Abhängigkeiten außer Python 3.10+.
Ohne Token reicht das Kontingent (60 Anfragen/Stunde) für gelegentliche Läufe;
mit GITHUB_TOKEN (oder eingeloggtem gh) sind es 5000.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"
VERSION = "0.1.0"
STANDARD_STAND = Path(__file__).resolve().parent / "daten" / "stand.json"


class ApiFehler(Exception):
    pass


# ---------------------------------------------------------------- API-Zugriff

def token_finden() -> str | None:
    """GITHUB_TOKEN aus der Umgebung, sonst das Token von gh (falls eingeloggt)."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    if shutil.which("gh"):
        try:
            aus = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                 text=True, timeout=10)
            if aus.returncode == 0 and aus.stdout.strip():
                return aus.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None


class GitHub:
    def __init__(self, token: str | None):
        self.token = token
        self.anfragen = 0
        self.rest: str | None = None

    def hole(self, pfad: str, parameter: dict | None = None,
             accept: str = "application/vnd.github+json"):
        url = API + pfad
        if parameter:
            url += "?" + urllib.parse.urlencode(parameter)
        kopf = {
            "Accept": accept,
            "User-Agent": f"repo-radar/{VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            kopf["Authorization"] = f"Bearer {self.token}"
        anfrage = urllib.request.Request(url, headers=kopf)
        try:
            with urllib.request.urlopen(anfrage, timeout=20) as antwort:
                self.anfragen += 1
                # Die Suche hat ein eigenes, kleines Kontingent - gezeigt wird das normale
                if antwort.headers.get("X-RateLimit-Resource", "core") == "core":
                    self.rest = antwort.headers.get("X-RateLimit-Remaining")
                return json.load(antwort)
        except urllib.error.HTTPError as fehler:
            if fehler.code in (403, 429) and fehler.headers.get("X-RateLimit-Remaining") == "0":
                reset = fehler.headers.get("X-RateLimit-Reset")
                um = datetime.fromtimestamp(int(reset)).strftime("%H:%M") if reset else "?"
                raise ApiFehler(f"API-Kontingent aufgebraucht, wieder frei um {um} Uhr. "
                                "Mit GITHUB_TOKEN gibt es deutlich mehr.") from None
            if fehler.code == 404:
                raise ApiFehler(f"Nicht gefunden: {pfad}") from None
            if fehler.code == 401:
                if not self.token:
                    raise ApiFehler(f"{pfad} geht nur mit Token (GITHUB_TOKEN oder gh auth login).") from None
                raise ApiFehler("Token ungültig oder abgelaufen.") from None
            raise ApiFehler(f"GitHub antwortet mit {fehler.code} auf {pfad}") from None
        except urllib.error.URLError as fehler:
            raise ApiFehler(f"Keine Verbindung zu GitHub ({fehler.reason})") from None

    def alle_seiten(self, pfad: str, parameter: dict | None = None,
                    accept: str = "application/vnd.github+json", max_seiten: int = 10):
        parameter = dict(parameter or {}, per_page=100)
        for seite in range(1, max_seiten + 1):
            daten = self.hole(pfad, dict(parameter, page=seite), accept)
            yield from daten
            if len(daten) < 100:
                break

    def suche(self, q: str, max_treffer: int = 100) -> list[dict]:
        daten = self.hole("/search/issues", {"q": q, "sort": "created",
                                             "order": "desc", "per_page": max_treffer})
        return daten.get("items", [])


# ---------------------------------------------------------------- Stand

def stand_laden(pfad: Path) -> dict:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        print(f"Hinweis: {pfad} ist nicht lesbar, fange neu an.", file=sys.stderr)
        return {}


def stand_speichern(pfad: Path, stand: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(stand, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(pfad)


# ---------------------------------------------------------------- Auswertung

def iso(zeit: datetime) -> str:
    return zeit.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lesbar(zeitstempel: str) -> str:
    zeit = datetime.fromisoformat(zeitstempel.replace("Z", "+00:00"))
    return zeit.astimezone().strftime("%d.%m.%Y %H:%M")


def differenz(neu: int, alt: int | None) -> str:
    if alt is None or neu == alt:
        return ""
    return f" ({neu - alt:+d})"


def radar(gh: GitHub, nutzer: str, stand: dict, seit: datetime,
          mit_forks: bool) -> tuple[list[str], dict]:
    zeilen: list[str] = []
    alt_repos: dict = stand.get("repos", {})
    neu_repos: dict = {}

    repos = [r for r in gh.alle_seiten(f"/users/{nutzer}/repos", {"type": "owner"})
             if mit_forks or not r["fork"]]
    repos.sort(key=lambda r: (-r["stargazers_count"], r["name"].lower()))

    zeilen.append(f"## Repos von {nutzer} ({len(repos)})")
    zeilen.append("")
    zeilen.append(f"{'Repo':<40} {'Sterne':>10} {'Forks':>9} {'Issues':>9}")
    summe = 0
    for r in repos:
        alt = alt_repos.get(r["name"], {})
        sterne, forks, issues = r["stargazers_count"], r["forks_count"], r["open_issues_count"]
        summe += sterne
        neu_repos[r["name"]] = {"sterne": sterne, "forks": forks, "issues": issues}
        zeilen.append(f"{r['name'][:40]:<40} "
                      f"{str(sterne) + differenz(sterne, alt.get('sterne')):>10} "
                      f"{str(forks) + differenz(forks, alt.get('forks')):>9} "
                      f"{str(issues) + differenz(issues, alt.get('issues')):>9}")
    zeilen.append(f"{'Summe':<40} {summe:>10}")
    zeilen.append("")

    # Neue Sterne: nur dort nachsehen, wo die Zahl gestiegen ist (spart Anfragen)
    zeilen.append("## Neue Sterne")
    gefunden = False
    if alt_repos:
        for r in repos:
            vorher = alt_repos.get(r["name"], {}).get("sterne")
            if vorher is None or r["stargazers_count"] <= vorher:
                continue
            if not gh.token:
                # Die Liste der Sterngucker gibt GitHub nur mit Login heraus
                zeilen.append(f"- {r['name']}: {r['stargazers_count'] - vorher:+d} "
                              "(wer, zeigt repo-radar mit Token)")
                gefunden = True
                continue
            gucker = list(gh.alle_seiten(f"/repos/{nutzer}/{r['name']}/stargazers",
                                         accept="application/vnd.github.star+json",
                                         max_seiten=3))
            for g in gucker:
                if g.get("starred_at", "") > iso(seit):
                    zeilen.append(f"- {r['name']}: {g['user']['login']} ({lesbar(g['starred_at'])})")
                    gefunden = True
    else:
        zeilen.append("- (erster Lauf - ab dem nächsten Mal steht hier, wer neu dazukam)")
        gefunden = True
    if not gefunden:
        zeilen.append("- keine")
    zeilen.append("")

    # Issues und PRs von anderen in meinen Repos
    zeilen.append(f"## Neu von anderen in meinen Repos (seit {seit.astimezone():%d.%m.%Y %H:%M})")
    treffer = gh.suche(f"user:{nutzer} -author:{nutzer} created:>{iso(seit)}")
    if not treffer:
        zeilen.append("- nichts Neues")
    for t in treffer:
        art = "PR" if "pull_request" in t else "Issue"
        repo = t["repository_url"].rsplit("/", 1)[-1]
        zeilen.append(f"- [{art}] {repo}#{t['number']} {t['title']} "
                      f"- {t['user']['login']}, {t['state']} ({t['html_url']})")
    zeilen.append("")

    # Eigene PRs in fremden Repos
    zeilen.append("## Meine Pull Requests in fremden Repos")
    alt_prs: dict = stand.get("fremde_prs", {})
    neu_prs: dict = {}
    eigene = gh.suche(f"is:pr author:{nutzer} -user:{nutzer}", max_treffer=30)
    if not eigene:
        zeilen.append("- keine")
    for t in eigene:
        zustand = t["state"]
        if zustand == "closed" and t.get("pull_request", {}).get("merged_at"):
            zustand = "gemergt"
        elif zustand == "closed":
            zustand = "geschlossen"
        else:
            zustand = "offen"
        neu_prs[t["html_url"]] = zustand
        vorher = alt_prs.get(t["html_url"])
        wechsel = f"  <- vorher {vorher}" if vorher and vorher != zustand else ""
        repo = "/".join(t["repository_url"].split("/")[-2:])
        zeilen.append(f"- {repo}#{t['number']} [{zustand}] {t['title']}{wechsel}")
    zeilen.append("")

    return zeilen, {"repos": neu_repos, "fremde_prs": neu_prs}


# ---------------------------------------------------------------- Aufruf

def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="repo_radar.py",
        description="Zeigt, was sich seit dem letzten Lauf auf deinen GitHub-Repos getan hat.",
        epilog="Beispiele:\n"
               "  python repo_radar.py JacobMenge\n"
               "  python repo_radar.py JacobMenge --tage 7 --markdown bericht.md\n"
               "  python repo_radar.py JacobMenge --nur-anzeigen",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("nutzer", help="GitHub-Benutzername")
    parser.add_argument("--tage", type=int, metavar="N",
                        help="Zeitraum für neue Issues/Sterne (Standard: seit dem letzten Lauf, "
                             "beim ersten Lauf 7 Tage)")
    parser.add_argument("--forks", action="store_true", help="geforkte Repos mitzählen")
    parser.add_argument("--markdown", metavar="DATEI", help="Bericht zusätzlich als Markdown speichern")
    parser.add_argument("--stand", metavar="DATEI", default=str(STANDARD_STAND),
                        help="wo der letzte Stand liegt (Standard: daten/stand.json)")
    parser.add_argument("--nur-anzeigen", action="store_true",
                        help="Stand nicht aktualisieren (nächster Lauf vergleicht mit demselben Stand)")
    parser.add_argument("--version", action="version", version=f"repo-radar {VERSION}")
    args = parser.parse_args()

    if args.tage is not None and args.tage < 1:
        parser.error("--tage muss mindestens 1 sein")

    stand_pfad = Path(args.stand)
    stand = stand_laden(stand_pfad)
    if stand.get("nutzer") and stand["nutzer"].lower() != args.nutzer.lower():
        print(f"Hinweis: Der gespeicherte Stand gehört zu {stand['nutzer']}, "
              "Vergleich wird übersprungen.", file=sys.stderr)
        stand = {}

    jetzt = datetime.now(timezone.utc)
    if args.tage is not None:
        seit = jetzt - timedelta(days=args.tage)
    elif stand.get("zeit"):
        seit = datetime.fromisoformat(stand["zeit"].replace("Z", "+00:00"))
    else:
        seit = jetzt - timedelta(days=7)

    gh = GitHub(token_finden())
    try:
        zeilen, neu = radar(gh, args.nutzer, stand, seit, args.forks)
    except ApiFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1

    kopf = [f"# repo-radar - {args.nutzer} - {jetzt.astimezone():%d.%m.%Y %H:%M}", ""]
    if stand.get("zeit"):
        kopf += [f"Letzter Lauf: {lesbar(stand['zeit'])}", ""]
    bericht = "\n".join(kopf + zeilen)
    print(bericht)
    fuss = f"{gh.anfragen} API-Anfragen" + (f", noch {gh.rest} frei" if gh.rest else "")
    fuss += "" if gh.token else " (ohne Token)"
    print(fuss)

    if args.markdown:
        Path(args.markdown).write_text(bericht + "\n", encoding="utf-8")
        print(f"Markdown gespeichert: {args.markdown}")

    if not args.nur_anzeigen:
        stand_speichern(stand_pfad, dict(neu, nutzer=args.nutzer, zeit=iso(jetzt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
