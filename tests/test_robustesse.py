"""Tests de résistance aux pannes (étape 3).

Règles du brief : une source en panne ne fait pas échouer tout le traitement ;
si une nuit échoue, le site garde les dernières données valides, avec leur
date ; l'échec est enregistré dans le journal.
"""

import json
from datetime import datetime, timezone

import pytest

from pipeline import traitement_nuit as tn
from pipeline.journal import Journal
from pipeline.sorties import ecrire_json_si_valide


@pytest.fixture
def chemins_temporaires(tmp_path, monkeypatch):
    """Redirige tous les fichiers écrits par le traitement vers un dossier de test."""
    for nom in ["FICHIER_PERFORMANCE", "FICHIER_PROVISOIRES", "FICHIER_SECTEURS", "FICHIER_SENTIMENT",
                "FICHIER_HISTO_SENTIMENT", "FICHIER_GDELT", "FICHIER_GDELT_SITE", "FICHIER_ETAT", "FICHIER_JOURNAL"]:
        monkeypatch.setattr(tn, nom, tmp_path / f"{nom.lower()}.json")
    import pipeline.journal as module_journal
    monkeypatch.setattr(module_journal, "FICHIER_JOURNAL", tmp_path / "journal.csv")
    return tmp_path


def test_yahoo_en_panne_le_site_garde_ses_donnees(chemins_temporaires, monkeypatch):
    anciennes = {"derniere_seance": "2026-10-16", "etf": [], "periodes": []}
    tn.FICHIER_PERFORMANCE.write_text(json.dumps(anciennes), encoding="utf-8")
    monkeypatch.setattr(tn.collecte_prix, "telecharger_cours", lambda *a, **k: None)
    monkeypatch.setattr(tn.collecte_prix, "telecharger_eurusd", lambda *a, **k: None)
    monkeypatch.setattr(tn.collecte_prix, "telecharger_estr", lambda *a, **k: None)
    journal = Journal()
    assert tn.etape_performance(journal) is None
    # Le fichier du site n'a pas bougé, et l'échec est noté.
    assert json.loads(tn.FICHIER_PERFORMANCE.read_text(encoding="utf-8")) == anciennes
    assert any(l["etape"] == "performance" and l["statut"] == "echec" for l in journal.lignes)


def test_une_etape_qui_plante_n_empeche_pas_les_autres(chemins_temporaires, monkeypatch):
    appels = []

    def plante(*a, **k):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(tn, "etape_performance", plante)
    monkeypatch.setattr(tn, "etape_secteurs", lambda j, t: appels.append("secteurs"))
    monkeypatch.setattr(tn, "etape_sentiment", lambda j: (appels.append("sentiment"), j.noter("sentiment", "ok", "")))
    monkeypatch.setattr(tn, "etape_gdelt", lambda j: appels.append("gdelt"))
    code = tn.main()
    assert appels == ["secteurs", "sentiment", "gdelt"]
    assert code == 1  # tâche marquée en échec : GitHub enverra un e-mail
    etat = json.loads(tn.FICHIER_ETAT.read_text(encoding="utf-8"))
    assert etat["etapes"]["performance"]["statut"] == "echec"
    assert etat["etapes"]["sentiment"]["statut"] == "ok"
    assert etat["tout_va_bien"] is False
    assert "panne simulée" in (chemins_temporaires / "journal.csv").read_text(encoding="utf-8-sig")


def test_etat_garde_la_date_de_derniere_reussite(chemins_temporaires):
    nuit1 = Journal()
    nuit1.noter("performance", "ok", "5 ETF")
    tn.ecrire_etat(nuit1, datetime(2026, 10, 19, 4, 45, tzinfo=timezone.utc))
    nuit2 = Journal()
    nuit2.noter("performance", "echec", "Yahoo indisponible")
    etat = tn.ecrire_etat(nuit2, datetime(2026, 10, 20, 4, 45, tzinfo=timezone.utc))
    assert etat["etapes"]["performance"]["statut"] == "echec"
    assert etat["etapes"]["performance"]["derniere_reussite_utc"] == "2026-10-19T04:45:00Z"
    assert etat["alertes_24h"][0]["message"] == "Yahoo indisponible"


def test_des_donnees_plus_anciennes_ne_remplacent_jamais_les_recentes(tmp_path):
    chemin = tmp_path / "f.json"
    ecrire_json_si_valide(chemin, {"derniere_seance": "2026-10-16"}, [])
    ecrit, raison = ecrire_json_si_valide(chemin, {"derniere_seance": "2026-10-15"},
                                          [("2026-10-15" >= "2026-10-16", "données plus anciennes")])
    assert not ecrit and raison == "données plus anciennes"
    assert json.loads(chemin.read_text(encoding="utf-8")) == {"derniere_seance": "2026-10-16"}
    # Une valeur non numérique (NaN) est refusée elle aussi.
    ecrit, _ = ecrire_json_si_valide(chemin, {"x": float("nan")}, [])
    assert not ecrit
