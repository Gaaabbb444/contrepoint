"""Tests automatiques des calculs de performance.

Principe : on fabrique des cours dont on connaît la bonne réponse à l'avance,
et on vérifie que le code retrouve exactement cette réponse.
Lancement :  python -m pytest
"""

import math

import numpy as np
import pandas as pd
import pytest

from pipeline import performance as perf
from pipeline.collecte_prix import controler_qualite, convertir_en_euros

PARAMS = {"seances_par_an": 252, "sharpe_duree_min_mois": 12, "annualisation_duree_min_mois": 36}


def serie(valeurs, debut="2024-01-01", freq="B"):
    return pd.Series(valeurs, index=pd.date_range(debut, periods=len(valeurs), freq=freq), dtype=float)


def test_performance_cumulee():
    assert perf.performance_cumulee(serie([100, 90, 110])) == pytest.approx(0.10)


def test_annualisation():
    # +21 % en 2 ans = +10 % par an (1,1 × 1,1 = 1,21)
    assert perf.annualiser(0.21, 2) == pytest.approx(0.10)


def test_perte_maximale():
    # Plus haut à 120, puis plus bas à 90 : −25 %, même si on remonte ensuite.
    assert perf.perte_maximale(serie([100, 120, 90, 130])) == pytest.approx(-0.25)


def test_volatilite_annualisee():
    # Rendements alternés +1 % / −1 % : écart-type connu.
    cours = [100.0]
    for i in range(200):
        cours.append(cours[-1] * (1.01 if i % 2 == 0 else 0.99))
    r = pd.Series(cours).pct_change().dropna()
    attendu = r.std(ddof=1) * math.sqrt(252)
    assert perf.volatilite_annualisee(serie(cours), 252) == pytest.approx(attendu)
    assert attendu == pytest.approx(0.01 * math.sqrt(252), rel=0.01)


def test_ecart_de_suivi_nul_si_identique():
    s = serie([100, 101, 99, 102, 103])
    assert perf.ecart_de_suivi(s, s * 2, 252) == pytest.approx(0.0)


def test_aligner_garde_seulement_les_dates_communes():
    a = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]))
    b = pd.Series([5.0, 6.0], index=pd.to_datetime(["2024-01-03", "2024-01-04"]))
    tableau = perf.aligner({"a": a, "b": b})
    assert list(tableau.index.strftime("%Y-%m-%d")) == ["2024-01-03", "2024-01-04"]


def test_date_debut_un_mois_prend_la_derniere_seance_disponible():
    dates = pd.to_datetime(["2026-09-14", "2026-09-15", "2026-09-17", "2026-10-16"])
    # Le 16/09 n'existe pas : on prend la séance précédente, le 15/09.
    debut = perf.date_debut(pd.DatetimeIndex(dates), pd.Timestamp("2026-10-16"), {"mois": 1})
    assert debut == pd.Timestamp("2026-09-15")


def test_date_debut_annee_en_cours():
    dates = pd.DatetimeIndex(pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02", "2026-10-16"]))
    debut = perf.date_debut(dates, pd.Timestamp("2026-10-16"), {"depuis_debut_annee": True})
    assert debut == pd.Timestamp("2025-12-31")


def test_date_debut_historique_insuffisant():
    dates = pd.DatetimeIndex(pd.to_datetime(["2026-01-02", "2026-10-16"]))
    assert perf.date_debut(dates, pd.Timestamp("2026-10-16"), {"mois": 36}) is None


def test_taux_sans_risque_constant():
    # €STR constant à 3,6 % (base 360) pendant un an : environ 3,66 % effectifs.
    estr = pd.Series(3.6, index=pd.date_range("2024-12-01", "2026-01-31", freq="B"))
    rf = perf.taux_sans_risque_annuel(estr, pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"))
    assert rf == pytest.approx((1 + 0.036 / 360) ** 365 - 1, rel=1e-3)


def test_indicateurs_periode_complet():
    dates = pd.date_range("2020-01-01", "2026-10-16", freq="B")
    n = len(dates)
    ref = pd.Series(100 * 1.0002 ** np.arange(n), index=dates)
    esg = pd.Series(100 * 1.0003 ** np.arange(n), index=dates)
    tableau = perf.aligner({"ref": ref, "esg": esg})
    estr = pd.Series(2.0, index=dates)
    res = perf.indicateurs_periode(tableau, "ref", estr, {"id": "1a", "libelle": "1 an", "mois": 12}, PARAMS)
    assert res["disponible"]
    ligne_esg = res["etf"]["esg"]
    attendu_relatif = (esg[res["debut"]:].iloc[-1] / esg[res["debut"]] - 1) - (ref[res["debut"]:].iloc[-1] / ref[res["debut"]] - 1)
    assert ligne_esg["perf_relative_pts"] == pytest.approx(round(attendu_relatif * 100, 2))
    # Croissance parfaitement régulière : volatilité et perte maximale nulles.
    assert ligne_esg["volatilite_pct"] == pytest.approx(0, abs=1e-6)
    assert ligne_esg["perte_max_pct"] == pytest.approx(0, abs=1e-6)
    assert "perf_relative_pts" not in res["etf"]["ref"]
    # Sharpe non calculable avec une volatilité nulle.
    assert ligne_esg["sharpe"] is None


def test_sharpe_et_periode_courte():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-01", "2026-10-16", freq="B")
    ref = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(dates))), index=dates)
    tableau = perf.aligner({"ref": ref})
    estr = pd.Series(2.0, index=dates)
    un_mois = perf.indicateurs_periode(tableau, "ref", estr, {"id": "1m", "libelle": "1 mois", "mois": 1}, PARAMS)
    assert un_mois["etf"]["ref"]["sharpe"] is None              # trop court pour un Sharpe
    assert un_mois["etf"]["ref"]["perf_annualisee_pct"] is None  # trop court pour annualiser
    trois_ans = perf.indicateurs_periode(tableau, "ref", estr, {"id": "3a", "libelle": "3 ans", "mois": 36}, PARAMS)
    ligne = trois_ans["etf"]["ref"]
    debut = pd.Timestamp(trois_ans["debut"])
    annees = perf.duree_en_annees(debut, dates[-1])
    rendement = perf.annualiser(ref.iloc[-1] / ref[debut] - 1, annees)
    vol = perf.volatilite_annualisee(ref[debut:], 252)
    rf = perf.taux_sans_risque_annuel(estr, debut, dates[-1])
    assert ligne["sharpe"] == pytest.approx(round((rendement - rf) / vol, 2))
    assert ligne["perf_annualisee_pct"] == pytest.approx(round(rendement * 100, 2))


def test_signalement_risque_peu_fiable():
    dates = pd.date_range("2020-01-01", "2026-10-16", freq="B")
    rng = np.random.default_rng(1)
    tableau = perf.aligner({
        "ref": pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates))), index=dates),
        "paris": pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates))), index=dates),
    })
    fiable = {"paris": pd.Timestamp("2025-08-25")}
    un_an = perf.indicateurs_periode(tableau, "ref", None, {"id": "1a", "libelle": "1 an", "mois": 12}, PARAMS, fiable)
    trois_ans = perf.indicateurs_periode(tableau, "ref", None, {"id": "3a", "libelle": "3 ans", "mois": 36}, PARAMS, fiable)
    assert "risque_fiabilite_reduite" not in un_an["etf"]["paris"]
    assert trois_ans["etf"]["paris"]["risque_fiabilite_reduite"] is True
    assert "risque_fiabilite_reduite" not in trois_ans["etf"]["ref"]


def test_conversion_en_euros_avec_jour_ferie():
    usd = pd.Series([110.0, 112.0], index=pd.to_datetime(["2026-05-01", "2026-05-04"]))
    # Pas de taux BCE le 1er mai (férié TARGET) : on reprend celui du 30 avril.
    taux = pd.Series([1.10, 1.12], index=pd.to_datetime(["2026-04-30", "2026-05-04"]))
    eur = convertir_en_euros(usd, taux, report_max_jours=4)
    assert eur.loc["2026-05-01"] == pytest.approx(100.0)
    assert eur.loc["2026-05-04"] == pytest.approx(100.0)


def test_conversion_refuse_un_taux_trop_ancien():
    usd = pd.Series([110.0], index=pd.to_datetime(["2026-05-20"]))
    taux = pd.Series([1.10], index=pd.to_datetime(["2026-05-01"]))
    assert convertir_en_euros(usd, taux, report_max_jours=4).empty


def tableau_depuis_rendements(rendements_pct: dict, dates) -> pd.DataFrame:
    """Reconstruit des cours (base 100) à partir de variations quotidiennes en %."""
    return pd.DataFrame({k: 100 * np.cumprod([1] + [1 + r / 100 for r in v]) for k, v in rendements_pct.items()},
                        index=pd.to_datetime(dates))


def test_pic_isole_retire_un_etf_qui_decroche_seul():
    dates = pd.to_datetime(["2025-10-22", "2025-10-23", "2025-10-24", "2025-10-27", "2025-10-28"])
    tableau = pd.DataFrame({
        # Cas réel : cours en dollars glissé dans la série en euros le 24/10.
        "screened": [10.30, 10.34, 12.10, 10.51, 10.53],
        "ref": [109.35, 109.79, 110.50, 111.37, 111.58],
        "sri": [12.05, 12.06, 12.14, 12.23, 12.26],
        "paris": [8.40, 8.42, 8.47, 8.53, 8.55],
    }, index=dates)
    propre, details = perf.supprimer_pics_isoles(tableau, 0.05, "ref")
    assert pd.Timestamp("2025-10-24") not in propre.index
    assert len(propre) == 4
    assert [d["etf"] for d in details] == ["screened"]


def test_vrai_choc_de_marche_avril_2025_conserve():
    # Variations réelles (en %) du 01/04 au 15/04/2025, telles que calculées
    # par Contrepoint : krach des droits de douane puis rebond violent.
    dates = ["2025-03-31", "2025-04-01", "2025-04-02", "2025-04-03", "2025-04-04", "2025-04-07",
             "2025-04-08", "2025-04-09", "2025-04-10", "2025-04-11", "2025-04-14", "2025-04-15"]
    variations = {
        "ref":      [1.19, -0.09, -4.92, -4.67, -2.65, 3.25, -4.84, 4.05, -0.87, 2.75, 1.05],
        "screened": [1.29, -0.01, -5.18, -4.57, -2.57, 3.36, -4.82, 4.07, -0.98, 2.80, 1.10],
        "sri":      [1.30, -0.14, -4.46, -4.06, -2.70, 3.18, -4.84, 3.74, -0.96, 2.84, 1.11],
        "paris":    [1.82, 0.14, -5.45, -4.19, -3.55, 3.89, -3.83, 4.93, -2.14, 3.01, 0.61],
        "bnp":      [1.17, -0.29, -4.08, -3.82, -2.93, 2.11, -4.14, 3.68, -1.24, 2.95, 1.08],
    }
    tableau = tableau_depuis_rendements(variations, dates)
    propre, details = perf.supprimer_pics_isoles(tableau, 0.05, "ref")
    assert details == [] and len(propre) == len(tableau)
    # Même un choc beaucoup plus violent (−12 % puis +11 %) est conservé
    # s'il touche tous les ETF ensemble.
    violent = {k: [r * 2.5 for r in v] for k, v in variations.items()}
    assert perf.supprimer_pics_isoles(tableau_depuis_rendements(violent, dates), 0.05, "ref")[1] == []


def test_erreur_sur_la_reference_detectee():
    dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    variations = {
        "ref": [0.5, 8.0, -7.5],   # le MSCI World « saute » seul puis revient
        "screened": [0.5, 0.3, 0.2],
        "sri": [0.4, 0.2, 0.3],
        "paris": [0.6, 0.4, 0.1],
    }
    propre, details = perf.supprimer_pics_isoles(tableau_depuis_rendements(variations, dates), 0.05, "ref")
    assert [d["etf"] for d in details] == ["ref"]
    assert pd.Timestamp("2025-01-06") not in propre.index


def test_cloture_provisoire():
    from pipeline.collecte_prix import cloture_provisoire
    index = pd.DatetimeIndex(pd.to_datetime(["2026-10-15", "2026-10-16"])).tz_localize("Europe/Berlin")
    cours = pd.Series([130.785, np.nan], index=index)
    # 16/10/2026 à 17 h 36 (heure de Berlin) : dernier prix de la séance.
    cloture = int(pd.Timestamp("2026-10-16 17:36", tz="Europe/Berlin").timestamp())
    meta = {"regularMarketPrice": 130.54, "regularMarketTime": cloture, "exchangeTimezoneName": "Europe/Berlin"}
    nuit = pd.Timestamp("2026-10-17 06:41", tz="Europe/Paris")
    assert cloture_provisoire(cours, meta, nuit) == ("2026-10-16", 130.54)
    # yfinance fournit l'heure sous forme de date avec fuseau, pas en secondes.
    meta_yf = {**meta, "regularMarketTime": pd.Timestamp("2026-10-16 17:36:10", tz="Europe/Berlin")}
    assert cloture_provisoire(cours, meta_yf, nuit) == ("2026-10-16", 130.54)
    # Pendant la séance (11 h 05), le prix n'est pas une clôture : rien.
    meta["regularMarketTime"] = int(pd.Timestamp("2026-10-16 11:00", tz="Europe/Berlin").timestamp())
    assert cloture_provisoire(cours, meta, pd.Timestamp("2026-10-16 11:05", tz="Europe/Paris")) is None
    # ETF peu échangé : dernière transaction à 11 h, séance finie → provisoire acceptée.
    assert cloture_provisoire(cours, meta, nuit) == ("2026-10-16", 130.54)
    # Clôture officielle déjà publiée : pas de provisoire.
    assert cloture_provisoire(cours.fillna(130.60), meta, nuit) is None


def test_provisoire_remplacee_par_l_officielle():
    from pipeline.collecte_prix import fusionner_provisoires
    # Nuit 1 : clôture du 16/10 vide chez Yahoo → valeur provisoire utilisée et mémorisée.
    officiel_nuit1 = pd.Series([130.785], index=pd.to_datetime(["2026-10-15"]))
    serie, memoire = fusionner_provisoires(officiel_nuit1, {}, ("2026-10-16", 130.54))
    assert serie.loc["2026-10-16"] == 130.54 and memoire == {"2026-10-16": 130.54}
    # Nuit 2 : la clôture officielle du 16/10 est toujours absente, celle du 19/10 aussi.
    officiel_nuit2 = officiel_nuit1.copy()
    serie, memoire = fusionner_provisoires(officiel_nuit2, memoire, ("2026-10-19", 131.10))
    assert list(memoire) == ["2026-10-16", "2026-10-19"] and serie.loc["2026-10-16"] == 130.54
    # Nuit 3 : les clôtures officielles sont publiées → elles remplacent les provisoires.
    officiel_nuit3 = pd.Series([130.785, 130.52, 131.05], index=pd.to_datetime(["2026-10-15", "2026-10-16", "2026-10-19"]))
    serie, memoire = fusionner_provisoires(officiel_nuit3, memoire, None)
    assert memoire == {} and serie.loc["2026-10-16"] == 130.52 and serie.loc["2026-10-19"] == 131.05


def test_raccorder_garde_les_variations():
    from pipeline.collecte_prix import raccorder
    ancienne = pd.Series([8.0, 8.8, 9.68, 9.0], index=pd.to_datetime(["2025-08-20", "2025-08-21", "2025-08-22", "2025-08-25"]))
    recente = pd.Series([20.0, 21.0], index=pd.to_datetime(["2025-08-25", "2025-08-26"]))
    serie, jonction = raccorder(ancienne, recente)
    assert jonction == pd.Timestamp("2025-08-25")
    assert list(serie.index.strftime("%m-%d")) == ["08-20", "08-21", "08-22", "08-25", "08-26"]
    # Les variations de l'ancienne série sont conservées (+10 % puis +10 %)...
    assert serie.iloc[1] / serie.iloc[0] == pytest.approx(1.10)
    assert serie.iloc[2] / serie.iloc[1] == pytest.approx(1.10)
    # ... et la série récente est reprise telle quelle à partir de la jonction.
    assert serie.loc["2025-08-25"] == 20.0 and serie.loc["2025-08-26"] == 21.0
    assert serie.loc["2025-08-25"] / serie.loc["2025-08-22"] == pytest.approx(9.0 / 9.68)


def test_controle_qualite():
    s = serie([100, 100, 100, 100, 101, 130])
    q = controler_qualite(s, seuil_fige=3, seuil_aberrant_pct=12)
    assert q["episodes_cours_figes"] == 1
    assert len(q["variations_aberrantes"]) == 1
