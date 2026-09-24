"""Tests ohne Netz: die GitHub-API wird durch feste Antworten ersetzt.

Aufruf:  python -m unittest discover -s tests
"""

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import repo_radar as rr  # noqa: E402

SEIT = datetime(2026, 9, 20, tzinfo=timezone.utc)


def repo(name, sterne=0, forks=0, issues=0, fork=False):
    return {"name": name, "stargazers_count": sterne, "forks_count": forks,
            "open_issues_count": issues, "fork": fork}


def stern(login, zeit):
    return {"user": {"login": login}, "starred_at": zeit}


class FalscheAPI(rr.GitHub):
    """Liefert vorbereitete Antworten und merkt sich, was abgefragt wurde."""

    def __init__(self, antworten, token="t"):
        super().__init__(token)
        self.antworten = antworten
        self.abgefragt = []

    def hole(self, pfad, parameter=None, accept="application/vnd.github+json"):
        parameter = parameter or {}
        self.abgefragt.append((pfad, parameter.get("page"), parameter.get("q")))
        if pfad == "/search/issues":
            return {"items": self.antworten["suche"](parameter["q"])}
        schluessel = (pfad, parameter.get("page", 1))
        return self.antworten.get(schluessel, [])


class Hilfsfunktionen(unittest.TestCase):
    def test_differenz(self):
        self.assertEqual(rr.differenz(5, 3), " (+2)")
        self.assertEqual(rr.differenz(3, 5), " (-2)")
        self.assertEqual(rr.differenz(3, 3), "")
        self.assertEqual(rr.differenz(3, None), "")

    def test_kaputter_stand_faengt_neu_an(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = Path(ordner) / "stand.json"
            datei.write_text("{kaputt", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as meldung:
                self.assertEqual(rr.stand_laden(datei), {})
            self.assertIn("nicht lesbar", meldung.getvalue())
            self.assertEqual(rr.stand_laden(Path(ordner) / "fehlt.json"), {})

    def test_stand_speichern_und_laden(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = Path(ordner) / "unter" / "stand.json"
            rr.stand_speichern(datei, {"nutzer": "x", "zahl": 1})
            self.assertEqual(rr.stand_laden(datei), {"nutzer": "x", "zahl": 1})


class Sterngucker(unittest.TestCase):
    def test_liest_von_der_letzten_seite_rueckwaerts(self):
        alt = [stern(f"alt{i}", "2026-01-01T00:00:00Z") for i in range(100)]
        neu = [stern("anna", "2026-09-21T10:00:00Z"), stern("ben", "2026-09-22T10:00:00Z")]
        api = FalscheAPI({("/repos/j/r/stargazers", 1): alt, ("/repos/j/r/stargazers", 2): neu})

        treffer = rr.neue_sterngucker(api, "j", "r", 102, SEIT)

        self.assertEqual([g["user"]["login"] for g in treffer], ["ben", "anna"])
        self.assertEqual([seite for _, seite, _ in api.abgefragt], [2, 1])

    def test_hoert_bei_alten_sternen_auf(self):
        seite = [stern("alt", "2026-09-01T00:00:00Z"), stern("neu", "2026-09-23T00:00:00Z")]
        api = FalscheAPI({("/repos/j/r/stargazers", 1): seite})
        treffer = rr.neue_sterngucker(api, "j", "r", 2, SEIT)
        self.assertEqual([g["user"]["login"] for g in treffer], ["neu"])


class Radar(unittest.TestCase):
    def setUp(self):
        self.repos = [repo("klein", sterne=1), repo("gross", sterne=5, forks=2, issues=1),
                      repo("gabel", sterne=9, fork=True)]

        def suche(q):
            if q.startswith("is:pr"):
                return [{"html_url": "https://github.com/o/p/pull/7", "number": 7, "title": "Fix",
                         "state": "closed", "pull_request": {"merged_at": "2026-09-21T00:00:00Z"},
                         "repository_url": "https://api.github.com/repos/o/p"}]
            return [{"html_url": "https://github.com/j/gross/issues/3", "number": 3, "title": "Bug",
                     "state": "open", "user": {"login": "kim"},
                     "repository_url": "https://api.github.com/repos/j/gross"}]

        self.antworten = {("/users/j/repos", 1): self.repos, "suche": suche,
                          ("/repos/j/gross/stargazers", 1): [stern("anna", "2026-09-21T10:00:00Z")]}

    def test_erster_lauf(self):
        zeilen, neu = rr.radar(FalscheAPI(self.antworten), "j", {}, SEIT, mit_forks=False)
        text = "\n".join(zeilen)

        self.assertNotIn("gabel", text)  # Forks nur mit --forks
        self.assertLess(text.index("gross"), text.index("klein"))  # nach Sternen sortiert
        self.assertIn("erster Lauf", text)
        self.assertIn("[Issue] gross#3 Bug - kim", text)
        self.assertIn("o/p#7 [gemergt] Fix", text)
        self.assertEqual(neu["repos"]["gross"], {"sterne": 5, "forks": 2, "issues": 1})
        self.assertEqual(neu["fremde_prs"], {"https://github.com/o/p/pull/7": "gemergt"})

    def test_vergleich_mit_letztem_lauf(self):
        stand = {"repos": {"gross": {"sterne": 4, "forks": 2, "issues": 1},
                           "klein": {"sterne": 1, "forks": 0, "issues": 0}},
                 "fremde_prs": {"https://github.com/o/p/pull/7": "offen"}}
        zeilen, _ = rr.radar(FalscheAPI(self.antworten), "j", stand, SEIT, mit_forks=False)
        text = "\n".join(zeilen)

        self.assertIn("5 (+1)", text)
        self.assertIn("- gross: anna", text)
        self.assertIn("<- vorher offen", text)

    def test_ohne_token_nur_anzahl(self):
        stand = {"repos": {"gross": {"sterne": 3}, "klein": {"sterne": 1}}}
        api = FalscheAPI(self.antworten, token=None)
        zeilen, _ = rr.radar(api, "j", stand, SEIT, mit_forks=False)

        self.assertIn("- gross: +2 (wer, zeigt repo-radar mit Token)", zeilen)
        self.assertFalse(any("stargazers" in pfad for pfad, _, _ in api.abgefragt))


if __name__ == "__main__":
    unittest.main()
