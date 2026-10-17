"""Test de l'alerte « plafond par média dépassé »."""

from datetime import date

import pandas as pd

from pipeline.alertes import alertes_flux, alertes_plafond


def test_alerte_si_un_media_depasse_25_pct():
    sentiment = {"repartition_medias": {
        "marche": {"nb_articles": 1200, "nb_seances": 20, "parts_pct": {"CNBC": 27.4, "Financial Times": 21.0}},
        "esg": {"nb_articles": 800, "nb_seances": 20, "parts_pct": {"ESG News": 18.0}},
    }}
    alertes = alertes_plafond(sentiment, 25, 20)
    assert len(alertes) == 1
    titre, texte = alertes[0]
    assert titre == "Plafond dépassé : CNBC pèse plus de 25 % du groupe marché"
    assert "27.4 %" in texte and "20 dernières séances" in texte


def test_pas_d_alerte_sous_le_plafond():
    sentiment = {"repartition_medias": {"marche": {"nb_articles": 10, "nb_seances": 2, "parts_pct": {"FT": 22.2}}}}
    assert alertes_plafond(sentiment, 25, 20) == []


def journal_de_test(pannes: list[tuple[str, str]]) -> pd.DataFrame:
    """Journal fictif : (horodatage UTC, nom du flux) pour chaque relevé en échec, plus un relevé réussi."""
    lignes = [{"horodatage_utc": h, "etape": f"flux:{nom}", "statut": "avertissement", "message": "406 Not Acceptable"}
              for h, nom in pannes]
    lignes.append({"horodatage_utc": "2026-10-20 06:00:00", "etape": "collecte_titres", "statut": "ok", "message": ""})
    return pd.DataFrame(lignes)


def test_un_echec_isole_ne_declenche_pas_d_alerte():
    journal = journal_de_test([("2026-10-17 01:05:57", "Euronews Business")])
    assert alertes_flux(journal, {"Euronews Business"}, date(2026, 10, 20), 3, 5) == []


def test_flux_en_panne_trois_jours_sur_cinq():
    journal = journal_de_test([("2026-10-17 01:05:57", "Euronews Business"), ("2026-10-17 04:05:00", "Euronews Business"),
                               ("2026-10-18 13:00:00", "Euronews Business"), ("2026-10-20 07:00:00", "Euronews Business")])
    alertes = alertes_flux(journal, {"Euronews Business"}, date(2026, 10, 20), 3, 5)
    assert len(alertes) == 1
    titre, texte = alertes[0]
    assert titre == "Flux en panne : Euronews Business"
    assert "3 jours différents" in texte and "17/10, 18/10, 20/10" in texte and "4 relevés" in texte


def test_jours_comptes_a_l_heure_de_paris_et_flux_inactif_ignore():
    # 22 h 30 UTC le 16/10 = 0 h 30 à Paris le 17/10 : deux échecs le même jour (à Paris), pas trois jours.
    journal = journal_de_test([("2026-10-16 22:30:00", "X"), ("2026-10-17 09:00:00", "X"), ("2026-10-18 09:00:00", "X")])
    assert alertes_flux(journal, {"X"}, date(2026, 10, 20), 3, 5) == []
    # Un flux déjà désactivé (ImpactAlpha) ne donne jamais lieu à un ticket.
    journal = journal_de_test([(f"2026-10-{j} 09:00:00", "ImpactAlpha") for j in (16, 17, 18, 19)])
    assert alertes_flux(journal, {"Euronews Business"}, date(2026, 10, 20), 3, 5) == []
