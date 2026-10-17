"""Tests de l'analyse sectorielle."""

import numpy as np
import pandas as pd
import pytest

from pipeline import secteurs

EXTRAIT_CSV = '''Fund Holdings as of,"15/Oct/2026"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,Exchange,Market Currency
"AAPL","APPLE","Information Technology","Equity","8,393,562,360.00","5.50","1","1","1","United States","NASDAQ","USD"
"NVDA","NVIDIA","Information Technology","Equity","8,345,188,489.56","5.47","1","1","1","United States","NASDAQ","USD"
"XOM","EXXON MOBIL CORP","Energy","Equity","1","1.03","1","1","1","United States","NYSE","USD"
"GOOGL","ALPHABET CLASS A","Communication","Equity","1","2.24","1","1","1","United States","NASDAQ","USD"
"GOOG","ALPHABET CLASS C","Communication","Equity","1","1.77","1","1","1","United States","NASDAQ","USD"
"USD","USD CASH","Cash and/or Derivatives","Cash","1","0.10","1","1","1","United States","-","USD"

"The content contained herein is owned or licensed by BlackRock"
'''


def test_lire_composition():
    date, df = secteurs.lire_composition(EXTRAIT_CSV)
    assert date == "2026-10-15"
    assert len(df) == 6
    poids = secteurs.poids_par_secteur(df)
    assert poids["Technologies de l'information"] == pytest.approx(10.97)
    assert poids["Énergie"] == pytest.approx(1.03)
    assert poids["Liquidités et autres"] == pytest.approx(0.10)


def test_grandes_tech_regroupe_les_deux_actions_alphabet():
    _, df = secteurs.lire_composition(EXTRAIT_CSV)
    gt = secteurs.poids_grandes_tech(df, ["AAPL", "NVDA", "GOOGL", "GOOG", "MSFT"])
    assert gt["total_pct"] == pytest.approx(5.50 + 5.47 + 2.24 + 1.77)
    assert gt["detail"]["ALPHABET CLASS A"] == pytest.approx(2.24)


def test_effet_sectoriel_retrouve_un_pari_connu():
    # On fabrique un ETF ESG qui se comporte EXACTEMENT comme
    # « marché − 30 % de l'écart tech + 5 % de l'écart énergie + 0,01 %/jour ».
    rng = np.random.default_rng(42)
    n = 750
    dates = pd.bdate_range("2023-10-16", periods=n + 1)
    r_ref = rng.normal(0.0005, 0.01, n)
    r_tech = r_ref + rng.normal(0.0004, 0.008, n)
    r_ener = r_ref + rng.normal(-0.0002, 0.012, n)
    r_esg = r_ref - 0.30 * (r_tech - r_ref) + 0.05 * (r_ener - r_ref) + 0.0001
    cours = pd.DataFrame({k: 100 * np.cumprod(np.r_[1, 1 + v]) for k, v in
                          {"esg": r_esg, "ref": r_ref, "tech": r_tech, "ener": r_ener}.items()}, index=dates)
    res = secteurs.effet_sectoriel(cours, "esg", "ref", ["tech", "ener"])
    assert res["r2_pct"] == pytest.approx(100, abs=0.1)
    assert res["sensibilites"]["tech"] == pytest.approx(-0.30, abs=1e-6)
    assert res["sensibilites"]["ener"] == pytest.approx(0.05, abs=1e-6)
    # La décomposition est exacte : les parts s'additionnent pour donner l'écart total.
    assert sum(res["contributions_pts"].values()) == pytest.approx(res["ecart_somme_quotidienne_pts"], abs=0.02)
