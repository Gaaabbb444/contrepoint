"""Volet 3 : mise en parallèle du sentiment et de la performance relative des ETF ESG.

Pour chaque ETF ESG et chaque groupe de sentiment (marché, ESG), on calcule :
1. la corrélation glissante sur 30 séances entre le solde de sentiment du
   jour et la performance relative du jour (ETF ESG − MSCI World) ;
2. le test de décalage : sentiment du jour J et performance relative de la
   séance J+1 (les articles de J sont tous publiés AVANT la séance J+1) ;
3. la comparaison de la performance relative moyenne les jours de sentiment
   négatif et les jours de sentiment positif (test t de Welch).
Plus un CONTRÔLE DE VALIDITÉ de l'indicateur : le sentiment « marché » du jour
est-il lié à la performance du MSCI World le même jour ?

Garde-fous :
- seules les journées « exploitables » comptent : étiquette autre que
  « signal insuffisant », couverture complète, solde calculé sans les
  articles à date approximative ;
- aucun résultat n'est présenté avant 60 journées exploitables : on affiche
  à la place la progression et une date estimée ;
- une corrélation n'est jamais présentée comme une causalité.
"""

import math

import numpy as np
import pandas as pd
from scipy import stats

from pipeline import fenetres

AVERTISSEMENTS = [
    "Corrélation n'est pas causalité : un lien statistique ne prouve pas que le sentiment fait bouger les prix.",
    "Plusieurs tests sont menés (4 ETF, 2 groupes, 3 tests) : sur 20 tests, environ un peut paraître "
    "« significatif » par pur hasard au seuil de 5 %.",
]


# -----------------------------------------------------------------------------
# Préparation des données
# -----------------------------------------------------------------------------

def journees_exploitables(historique: pd.DataFrame, groupe: str) -> pd.Series:
    """Solde de sentiment des journées exploitables d'un groupe, indexé par date de séance."""
    d = historique[historique["groupe"] == groupe].copy()
    partielle = d["couverture_partielle"].astype(str).str.lower().eq("true")
    d = d[(d["etiquette"] != "signal insuffisant") & ~partielle]
    solde = pd.to_numeric(d.get("solde_dates_fiables", d["solde"]), errors="coerce").fillna(pd.to_numeric(d["solde"]))
    return pd.Series(solde.values, index=pd.to_datetime(d["seance"]), name="solde").sort_index()


def etiquettes_exploitables(historique: pd.DataFrame, groupe: str) -> pd.Series:
    d = historique[historique["groupe"] == groupe]
    partielle = d["couverture_partielle"].astype(str).str.lower().eq("true")
    d = d[(d["etiquette"] != "signal insuffisant") & ~partielle]
    return pd.Series(d["etiquette"].values, index=pd.to_datetime(d["seance"])).sort_index()


def table_jointe(rendement: pd.Series, solde: pd.Series) -> pd.DataFrame:
    """Associe à chaque journée de sentiment J le rendement du jour J et celui de la séance suivante J+1."""
    rendement = rendement.dropna().sort_index()
    suivant = rendement.shift(-1)
    lignes = []
    for jour, valeur in solde.items():
        meme_jour = rendement.get(jour, np.nan)
        apres = rendement.index[rendement.index > jour]
        lendemain = rendement[apres[0]] if len(apres) else np.nan
        lignes.append({"seance": jour, "solde": valeur, "rendement_j": meme_jour, "rendement_j1": lendemain})
    return pd.DataFrame(lignes).set_index("seance") if lignes else pd.DataFrame(columns=["solde", "rendement_j", "rendement_j1"])


# -----------------------------------------------------------------------------
# Tests statistiques
# -----------------------------------------------------------------------------

def correlation(x: pd.Series, y: pd.Series, p: dict) -> dict:
    """Corrélation de Pearson entre deux séries, avec sa probabilité critique (p-value)."""
    d = pd.concat([x, y], axis=1).dropna()
    n = int(len(d))
    if n < p["jours_min"]:
        return {"disponible": False, "n": n}
    r, valeur_p = stats.pearsonr(d.iloc[:, 0], d.iloc[:, 1])
    return {"disponible": True, "n": n, "r": round(float(r), 3), "p": round(float(valeur_p), 4),
            "significatif": bool(valeur_p < p["seuil_p"]),
            "sens": "positif" if r > 0 else "négatif"}


def comparaison(rendement_j: pd.Series, etiquettes: pd.Series, p: dict) -> dict:
    """Performance relative moyenne (en points de %) les jours négatifs et les jours positifs, test de Welch."""
    d = pd.concat([rendement_j.rename("r"), etiquettes.rename("e")], axis=1).dropna()
    neg, pos = d.loc[d["e"] == "négatif", "r"], d.loc[d["e"] == "positif", "r"]
    resultat = {"n_negatifs": int(len(neg)), "n_positifs": int(len(pos)), "requis_par_categorie": p["jours_min_par_categorie"]}
    if len(neg) < p["jours_min_par_categorie"] or len(pos) < p["jours_min_par_categorie"] or len(d) < p["jours_min"]:
        return resultat | {"disponible": False}
    t, valeur_p = stats.ttest_ind(pos, neg, equal_var=False)
    return resultat | {
        "disponible": True,
        "moyenne_jours_positifs_pts": round(float(pos.mean()) * 100, 3),
        "moyenne_jours_negatifs_pts": round(float(neg.mean()) * 100, 3),
        "ecart_pts": round(float(pos.mean() - neg.mean()) * 100, 3),
        "p": round(float(valeur_p), 4),
        "significatif": bool(valeur_p < p["seuil_p"]),
    }


def correlation_glissante(table: pd.DataFrame, fenetre: int) -> list[dict]:
    """Corrélation sur les `fenetre` dernières journées exploitables, recalculée chaque jour."""
    d = table[["solde", "rendement_j"]].dropna()
    glissante = d["solde"].rolling(fenetre, min_periods=fenetre).corr(d["rendement_j"]).dropna()
    return [{"seance": s.date().isoformat(), "r": round(float(v), 3)} for s, v in glissante.items() if math.isfinite(v)]


def progression(n: int, derniere_seance: str | None, p: dict, code_calendrier: str) -> dict:
    """Où en est-on des 60 journées requises, et quand les résultats deviendront-ils interprétables ?"""
    manquants = max(0, p["jours_min"] - n)
    estimation = None
    if manquants and derniere_seance:
        estimation = fenetres.nieme_seance_suivante(derniere_seance, manquants, code_calendrier)
    return {"jours_exploitables": n, "jours_requis": p["jours_min"], "pourcentage": round(min(100, n / p["jours_min"] * 100)),
            "date_estimee": estimation,
            "hypothese": "si chaque séance à venir est exploitable (articles suffisants et relevés complets)"}


# -----------------------------------------------------------------------------
# Analyse complète
# -----------------------------------------------------------------------------

def analyser(cours: pd.DataFrame, id_ref: str, historique: pd.DataFrame, p: dict, code_calendrier: str = "XETR") -> dict:
    """Calcule tout le volet 3. `cours` : cours alignés des ETF (base quelconque)."""
    rendements = cours.pct_change().dropna(how="all")
    derniere = str(historique["seance"].max()) if len(historique) else None
    resultats = {"etf": {}, "validation": {}, "avertissements": AVERTISSEMENTS}

    for groupe in ("marche", "esg"):
        solde = journees_exploitables(historique, groupe)
        etiquettes = etiquettes_exploitables(historique, groupe)
        for id_etf in cours.columns:
            if id_etf == id_ref:
                continue
            relatif = rendements[id_etf] - rendements[id_ref]
            table = table_jointe(relatif, solde)
            n = int(table["rendement_j"].notna().sum()) if len(table) else 0
            resultats["etf"].setdefault(id_etf, {})[groupe] = {
                "progression": progression(n, derniere, p, code_calendrier),
                "correlation_meme_jour": correlation(table.get("solde", pd.Series(dtype=float)),
                                                     table.get("rendement_j", pd.Series(dtype=float)), p),
                "test_decalage_j1": correlation(table.get("solde", pd.Series(dtype=float)),
                                                table.get("rendement_j1", pd.Series(dtype=float)), p),
                "comparaison_jours": comparaison(table.get("rendement_j", pd.Series(dtype=float)), etiquettes, p),
                "correlation_glissante": correlation_glissante(table, p["fenetre_glissante"]) if len(table) else [],
                "journees": [{"seance": s.date().isoformat(), "solde": r.solde,
                              "relatif_j_pts": None if pd.isna(r.rendement_j) else round(float(r.rendement_j) * 100, 3)}
                             for s, r in table.iterrows()],
            }

    # Contrôle de validité : sentiment « marché » du jour J et performance du MSCI World le même jour.
    table_ref = table_jointe(rendements[id_ref], journees_exploitables(historique, "marche"))
    n_ref = int(table_ref["rendement_j"].notna().sum()) if len(table_ref) else 0
    resultats["validation"] = {
        "description": "Lien entre le sentiment « marché » du jour et la performance du MSCI World le même jour. "
                       "Un lien positif indique que l'indicateur capte bien l'humeur du marché. "
                       "C'est un contrôle de validité, pas une prévision.",
        "progression": progression(n_ref, derniere, p, code_calendrier),
        "correlation": correlation(table_ref.get("solde", pd.Series(dtype=float)),
                                   table_ref.get("rendement_j", pd.Series(dtype=float)), p),
    }
    return resultats
