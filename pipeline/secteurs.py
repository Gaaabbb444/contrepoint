"""Expliquer les écarts de performance : poids par secteur et effet des paris sectoriels.

Deux approches complémentaires :

1. PHOTOGRAPHIE (statique) : à partir du fichier officiel de composition de
   chaque fonds iShares (toutes les actions détenues, avec leur secteur et leur
   poids), on compare le poids de chaque secteur dans les ETF ESG et dans le
   MSCI World, ainsi que le poids des grandes valeurs technologiques
   américaines. Limite : c'est le portefeuille d'aujourd'hui, pas celui d'il y
   a 3 ans.

2. MESURE (dynamique) : sur les 3 dernières années, on vérifie dans quelle
   mesure les écarts QUOTIDIENS de performance (ETF ESG − MSCI World)
   s'expliquent par l'écart du jour entre le secteur technologique et le
   marché, et entre le secteur de l'énergie et le marché (régression
   linéaire). On en déduit la part de l'écart cumulé due à ces deux paris.

Seuls des agrégats (poids par secteur) sont publiés, jamais la liste complète
des positions.
"""

import io
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from pipeline.collecte_prix import NAVIGATEUR

SECTEURS_FR = {
    "Information Technology": "Technologies de l'information",
    "Financials": "Finance",
    "Health Care": "Santé",
    "Consumer Discretionary": "Consommation discrétionnaire",
    "Communication": "Services de communication",
    "Industrials": "Industrie",
    "Consumer Staples": "Consommation de base",
    "Energy": "Énergie",
    "Materials": "Matériaux",
    "Utilities": "Services aux collectivités",
    "Real Estate": "Immobilier",
}
AUTRES = "Liquidités et autres"


# -----------------------------------------------------------------------------
# 1. Photographie : composition des fonds
# -----------------------------------------------------------------------------

def lire_composition(texte_csv: str) -> tuple[str, pd.DataFrame]:
    """Lit un fichier « latest-holdings.csv » d'iShares.

    Renvoie la date de la composition (AAAA-MM-JJ) et un tableau avec, pour
    chaque ligne : code, nom, secteur, poids (%).
    """
    lignes = texte_csv.splitlines()
    date_brute = lignes[0].split(",", 1)[1].strip().strip('"')           # ex. 15/Oct/2026
    date_iso = datetime.strptime(date_brute, "%d/%b/%Y").date().isoformat()
    entete = next(i for i, l in enumerate(lignes) if l.startswith("Ticker,"))
    df = pd.read_csv(io.StringIO("\n".join(lignes[entete:])), on_bad_lines="skip", dtype=str)
    df["poids"] = pd.to_numeric(df["Weight (%)"].str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=["poids"])
    return date_iso, df.rename(columns={"Ticker": "code", "Name": "nom", "Sector": "secteur"})


def poids_par_secteur(df: pd.DataFrame) -> dict[str, float]:
    """Poids total (en %) de chaque secteur, en français, du plus gros au plus petit."""
    secteur = df["secteur"].map(SECTEURS_FR).fillna(AUTRES)
    poids = df.groupby(secteur)["poids"].sum().sort_values(ascending=False)
    return {s: round(float(p), 2) for s, p in poids.items()}


def poids_grandes_tech(df: pd.DataFrame, codes: list[str]) -> dict:
    """Poids total et détaillé des grandes valeurs technologiques américaines."""
    selection = df[df["code"].isin(codes)]
    detail = selection.groupby("nom")["poids"].sum().sort_values(ascending=False)
    return {"total_pct": round(float(detail.sum()), 2),
            "detail": {n: round(float(p), 2) for n, p in detail.items()}}


def telecharger_composition(url: str) -> tuple[str, pd.DataFrame]:
    r = requests.get(url, headers={"User-Agent": NAVIGATEUR}, timeout=60)
    r.raise_for_status()
    return lire_composition(r.text.lstrip("﻿"))


# -----------------------------------------------------------------------------
# 2. Mesure : effet des paris sectoriels sur la performance relative
# -----------------------------------------------------------------------------

def effet_sectoriel(cours: pd.DataFrame, id_etf: str, id_ref: str, facteurs: list[str]) -> dict:
    """Régression des écarts quotidiens de performance sur les écarts sectoriels.

    `cours` : cours alignés (mêmes dates) de l'ETF, de la référence et des ETF
    sectoriels. Pour chaque séance :
        écart ESG     = rendement ETF ESG − rendement MSCI World
        écart secteur = rendement ETF sectoriel − rendement MSCI World
    On estime : écart ESG = a + b_tech × écart tech + b_énergie × écart énergie + résidu.

    - R² : part (0 à 100 %) des variations quotidiennes de l'écart ESG
      expliquée par les deux paris sectoriels.
    - b : sensibilité. Exemple : b_énergie = −0,05 signifie que l'ETF ESG se
      comporte comme s'il avait 5 points d'énergie en moins que le marché.
    - Décomposition de l'écart cumulé : la somme des écarts quotidiens se
      répartit exactement entre la part « technologie », la part « énergie »
      et le reste (propriété de la régression avec constante). La somme des
      écarts quotidiens est une approximation de l'écart cumulé.
    """
    r = cours.pct_change().dropna()
    y = r[id_etf] - r[id_ref]
    X = pd.DataFrame({f: r[f] - r[id_ref] for f in facteurs})
    A = np.column_stack([np.ones(len(X)), X.values])
    coefs, *_ = np.linalg.lstsq(A, y.values, rcond=None)
    ajuste = A @ coefs
    r2 = 1 - np.sum((y.values - ajuste) ** 2) / np.sum((y.values - y.values.mean()) ** 2)
    contributions = {f: float(coefs[i + 1] * X[f].sum()) for i, f in enumerate(facteurs)}
    contributions["autres_facteurs"] = float(coefs[0] * len(y))
    total = float(y.sum())
    # Écart relatif : ce que vaut l'ETF ESG par rapport à ce qu'il vaudrait
    # s'il avait fait exactement comme le MSCI World (−10 % = 10 % de moins).
    ecart_relatif = (cours[id_etf].iloc[-1] / cours[id_etf].iloc[0]) / (cours[id_ref].iloc[-1] / cours[id_ref].iloc[0]) - 1
    return {
        "debut": cours.index[0].date().isoformat(),
        "fin": cours.index[-1].date().isoformat(),
        "nb_seances": int(len(y)),
        "r2_pct": round(float(r2) * 100, 1),
        "sensibilites": {f: round(float(coefs[i + 1]), 3) for i, f in enumerate(facteurs)},
        "ecart_relatif_pct": round(float(ecart_relatif) * 100, 2),
        "ecart_somme_quotidienne_pts": round(total * 100, 2),
        "contributions_pts": {k: round(v * 100, 2) for k, v in contributions.items()},
        # Part de l'écart total due à chaque facteur (somme = 100 %).
        "parts_de_l_ecart_pct": {k: round(v / total * 100) for k, v in contributions.items()} if abs(total) > 1e-4 else None,
    }


def facteur_panier(cours: dict[str, pd.Series], poids: dict[str, float]) -> pd.Series:
    """Indice d'un panier d'actions à poids fixes (rééquilibré chaque jour).

    Sert à fabriquer le facteur « grandes valeurs technologiques » : chaque
    jour, son rendement est la moyenne pondérée des rendements des 7 actions.
    """
    tableau = pd.concat(cours, axis=1, join="inner").dropna()
    w = pd.Series(poids)[tableau.columns]
    rendements = (tableau.pct_change().fillna(0) * (w / w.sum())).sum(axis=1)
    return 100 * (1 + rendements).cumprod()


def horodatage() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
