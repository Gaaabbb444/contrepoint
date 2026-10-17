"""Tests du volet 3 (mise en parallèle) et de la synthèse automatique."""

import numpy as np
import pandas as pd
import pytest

from pipeline import parallele, synthese

P = {"jours_min": 60, "jours_min_par_categorie": 15, "fenetre_glissante": 30, "seuil_p": 0.05}


def donnees_simulees(n: int, lien_lendemain: float = 0.0, lien_meme_jour_ref: float = 0.0, graine: int = 0):
    """Fabrique des cours (MSCI World + un ETF ESG) et un historique de sentiment.

    lien_lendemain : force du lien entre le sentiment du jour et la performance
    relative du lendemain (0 = aucun lien, pur hasard).
    """
    rng = np.random.default_rng(graine)
    dates = pd.bdate_range("2026-01-05", periods=n + 2)
    r_ref = rng.normal(0.0004, 0.01, len(dates))
    r_rel = rng.normal(0, 0.003, len(dates))
    bruit = rng.normal(0, 15, len(dates))
    solde = bruit.copy()
    solde[:-1] += lien_lendemain * r_rel[1:] / 0.003 * 15      # sentiment de J lié au relatif de J+1
    solde += lien_meme_jour_ref * r_ref / 0.01 * 15             # sentiment de J lié au marché de J
    cours = pd.DataFrame({"ref": 100 * np.cumprod(1 + r_ref), "sri": 100 * np.cumprod(1 + r_ref + r_rel)}, index=dates)
    etiquettes = np.where(solde > 10, "positif", np.where(solde < -10, "négatif", "neutre"))
    lignes = []
    for i, d in enumerate(dates[1:n + 1], start=1):
        for groupe in ("marche", "esg"):
            lignes.append({"seance": d.date().isoformat(), "groupe": groupe, "solde": round(solde[i], 1),
                           "solde_dates_fiables": round(solde[i], 1), "etiquette": etiquettes[i],
                           "couverture_partielle": False})
    return cours, pd.DataFrame(lignes)


def test_lien_connu_detecte_par_le_test_de_decalage():
    cours, histo = donnees_simulees(150, lien_lendemain=0.6)
    res = parallele.analyser(cours, "ref", histo, P)["etf"]["sri"]["marche"]
    test = res["test_decalage_j1"]
    assert test["disponible"] and test["significatif"] and test["sens"] == "positif" and test["r"] > 0.3
    assert len(res["correlation_glissante"]) == 150 - 30 + 1


def test_pur_hasard_pas_de_lien():
    cours, histo = donnees_simulees(150, lien_lendemain=0.0, graine=3)
    test = parallele.analyser(cours, "ref", histo, P)["etf"]["sri"]["marche"]["test_decalage_j1"]
    assert test["disponible"] and not test["significatif"]


def test_controle_de_validite():
    cours, histo = donnees_simulees(150, lien_meme_jour_ref=0.7, graine=5)
    val = parallele.analyser(cours, "ref", histo, P)["validation"]["correlation"]
    assert val["disponible"] and val["significatif"] and val["sens"] == "positif"


def test_echantillon_insuffisant_progression_et_date_estimee():
    cours, histo = donnees_simulees(12)
    histo["seance"] = [s for s in pd.bdate_range("2026-10-05", periods=12).strftime("%Y-%m-%d") for _ in (0, 1)]
    cours.index = pd.bdate_range("2026-10-02", periods=len(cours))
    res = parallele.analyser(cours, "ref", histo, P)["etf"]["sri"]["marche"]
    assert not res["test_decalage_j1"]["disponible"] and not res["comparaison_jours"]["disponible"]
    prog = res["progression"]
    assert prog["jours_exploitables"] == 12 and prog["jours_requis"] == 60 and prog["pourcentage"] == 20
    # 48 séances manquantes après le 20/10/2026, selon le calendrier officiel de Xetra
    # (fêtes de fin d'année exclues) : le 29/12/2026.
    assert prog["date_estimee"] == "2026-12-29"


def test_journees_non_exploitables_exclues():
    histo = pd.DataFrame([
        {"seance": "2026-10-16", "groupe": "marche", "solde": -12.9, "solde_dates_fiables": -13.5, "etiquette": "neutre", "couverture_partielle": False},
        {"seance": "2026-10-15", "groupe": "marche", "solde": -36.8, "solde_dates_fiables": -36.8, "etiquette": "signal insuffisant", "couverture_partielle": False},
        {"seance": "2026-10-19", "groupe": "marche", "solde": 5.0, "solde_dates_fiables": 5.0, "etiquette": "neutre", "couverture_partielle": True},
    ])
    solde = parallele.journees_exploitables(histo, "marche")
    assert list(solde.index.strftime("%Y-%m-%d")) == ["2026-10-16"]
    assert solde.iloc[0] == -13.5   # solde calculé sans les articles à date approximative


def test_comparaison_jours_positifs_negatifs():
    rng = np.random.default_rng(1)
    jours = pd.bdate_range("2026-01-05", periods=80)
    etiquettes = pd.Series(["positif"] * 30 + ["négatif"] * 30 + ["neutre"] * 20, index=jours)
    rendement = pd.Series(np.r_[rng.normal(0.002, 0.002, 30), rng.normal(-0.002, 0.002, 30), rng.normal(0, 0.002, 20)], index=jours)
    res = parallele.comparaison(rendement, etiquettes, P)
    assert res["disponible"] and res["significatif"] and res["ecart_pts"] > 0.3
    # Moins de 15 jours négatifs : pas de conclusion.
    assert not parallele.comparaison(rendement, etiquettes.replace({"négatif": "neutre"}), P)["disponible"]


# --- Synthèse en français ---------------------------------------------------------

def test_format_des_nombres_en_francais():
    assert synthese.nombre(-12.94, 0, True) == "−13"
    assert synthese.nombre(0.42, 1) == "0,4"
    assert synthese.nombre(7.7, 0, True) == "+8"
    assert synthese.nombre(-0.04, 1) == "0,0"
    assert synthese.jour_fr("2026-10-16") == "vendredi 16/10"


def test_phrases_de_la_synthese():
    g = {"etiquette": "négatif", "solde": -14.2, "marge_erreur": 9.8, "nb_articles": 180, "couverture_partielle": False}
    assert synthese.phrase_humeur("Humeur du marché", g, "2026-10-16") == \
        "Humeur du marché : négative le vendredi 16/10 (solde −14, marge ±10, 180 articles)."
    insuffisant = {"etiquette": "signal insuffisant", "nb_articles": 24, "couverture_partielle": True}
    assert synthese.phrase_humeur("Actualité ESG", insuffisant, "2026-10-16") == \
        "Actualité ESG le vendredi 16/10 : signal insuffisant (24 articles) — journée partiellement relevée."
    assert synthese.verbe_ecart(-0.42) == "sous-performe" and synthese.verbe_ecart(0.05) == "fait jeu égal avec"
    histo = [{"groupe": "marche", "etiquette": e} for e in ["négatif", "négatif", "neutre", "positif", "signal insuffisant"]]
    assert synthese.phrase_bilan(histo, "marche") == \
        "Sur les 5 dernières journées de bourse : 2 négatives, 1 neutre, 1 positive, 1 sans signal suffisant."


def test_phrase_performance_et_lien():
    perf = {"reference": "ref", "etf": [{"id": "sri", "nom_court": "World SRI"}, {"id": "ref", "nom_court": "MSCI World"}],
            "series": {"dates": [str(i) for i in range(6)],
                       "base100": {"ref": [100, 100, 100, 100, 100, 101.6], "sri": [100, 100, 100, 100, 100, 101.2]}},
            "periodes": [{"id": "1a", "disponible": True, "etf": {"sri": {"perf_relative_pts": -1.57}}}]}
    assert synthese.phrase_performance(perf, "sri") == ("Sur 5 séances, l'ETF World SRI sous-performe le MSCI World "
                                                       "de 0,4 point (+1,2 % contre +1,6 %) ; sur un an, l'écart est de −1,6 point.")
    par = {"etf": {"sri": {"marche": {"progression": {"jours_exploitables": 12, "jours_requis": 60, "date_estimee": "2026-12-29"},
                                      "test_decalage_j1": {"disponible": False, "n": 12}}}}}
    assert synthese.phrase_lien(par, "sri") == ("Lien entre sentiment et performance relative : pas encore interprétable "
                                               "(12 / 60 jours de bourse exploitables ; résultats attendus vers le 29/12/2026).")
