"""Calculs de performance et de risque des ETF.

Toutes les fonctions de ce module sont des calculs « purs » : elles reçoivent
des séries de cours et renvoient des chiffres, sans rien télécharger. C'est ce
qui permet de les vérifier avec des tests automatiques (dossier tests/).

Conventions (expliquées dans la méthodologie du site) :
- rendement quotidien = cours du jour / cours de la veille − 1 ;
- volatilité annualisée = écart-type des rendements quotidiens × √252 ;
- tous les ETF sont comparés sur exactement les mêmes séances.
"""

import math

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Alignement des séries
# -----------------------------------------------------------------------------

def aligner(cours: dict[str, pd.Series]) -> pd.DataFrame:
    """Met les cours de tous les ETF dans un même tableau, sur les mêmes dates.

    On ne garde que les séances où TOUS les ETF ont un cours (« jointure
    interne »). Aucun cours n'est inventé ni recopié d'un jour sur l'autre.
    Conséquence : un jour férié sur une seule des places de cotation est
    retiré pour tout le monde, et la variation suivante couvre deux séances
    pour tous les ETF à la fois.
    """
    tableau = pd.concat(cours, axis=1, join="inner").dropna(how="any")
    return tableau.sort_index()


def _aller_retour(ecart: pd.Series, seuil: float) -> pd.Series:
    """Vrai les jours où l'écart dépasse le seuil, puis le dépasse en sens inverse le lendemain."""
    suivant = ecart.shift(-1)
    return (ecart.abs() > seuil) & (suivant.abs() > seuil) & (np.sign(ecart) != np.sign(suivant))


def supprimer_pics_isoles(tableau: pd.DataFrame, seuil: float, id_reference: str) -> tuple[pd.DataFrame, list[dict]]:
    """Retire les cours manifestement erronés (« pics isolés »), en prenant le MSCI World pour repère.

    Tous nos ETF suivent les grandes actions mondiales : d'une séance à
    l'autre, ils bougent presque comme le MSCI World. On calcule donc, chaque
    jour, l'écart entre la variation de chaque ETF ESG et celle du MSCI World.

    - Si TOUS les ETF bougent ensemble (krach puis rebond, comme début avril
      2025), les écarts restent faibles : la séance est réelle, on la garde.
    - Si UN SEUL ETF décroche de plus de `seuil` (ex. 5 %) par rapport au
      MSCI World, puis revient le lendemain alors que les autres ETF suivent
      le MSCI World, c'est une erreur de cet ETF : on écarte la séance.
    - Si c'est le MSCI World qui décroche seul (tous les ETF ESG s'en écartent
      dans le même sens, puis reviennent), l'erreur vient de la référence.

    La séance fautive est retirée pour TOUS les ETF (mêmes dates partout) ;
    rien n'est inventé à la place.
    """
    rendements = tableau.pct_change()
    esg = [c for c in tableau.columns if c != id_reference]
    ecarts = rendements[esg].sub(rendements[id_reference], axis=0)
    a_retirer, details = set(), []

    for col in esg:
        autres = [c for c in esg if c != col]
        # Les autres ETF ESG suivent-ils le MSCI World ce jour-là et le lendemain ?
        autres_calmes = (ecarts[autres].abs().median(axis=1) < seuil / 2) if autres else True
        autres_calmes_demain = (ecarts[autres].abs().median(axis=1).shift(-1) < seuil / 2) if autres else True
        pics = _aller_retour(ecarts[col], seuil) & autres_calmes & autres_calmes_demain
        for d in ecarts.index[pics]:
            a_retirer.add(d)
            details.append({"date": d.date().isoformat(), "etf": col,
                            "ecart_pct": round(float(ecarts.at[d, col]) * 100, 2)})

    # Erreur sur la référence : tous les ETF ESG s'en écartent ensemble, puis reviennent.
    if len(esg) >= 2:
        ecart_median = ecarts.median(axis=1)
        unanime = ecarts.apply(np.sign).abs().sum(axis=1).eq(ecarts.apply(np.sign).sum(axis=1).abs())
        pics_ref = _aller_retour(ecart_median, seuil) & unanime
        for d in ecarts.index[pics_ref]:
            a_retirer.add(d)
            details.append({"date": d.date().isoformat(), "etf": id_reference,
                            "ecart_pct": round(float(-ecart_median.at[d]) * 100, 2)})

    return tableau.drop(index=sorted(a_retirer)), details


def base_100(tableau: pd.DataFrame) -> pd.DataFrame:
    """Ramène chaque série à 100 à la première date (pour les graphiques)."""
    return tableau / tableau.iloc[0] * 100


# -----------------------------------------------------------------------------
# Périodes
# -----------------------------------------------------------------------------

def date_debut(dates: pd.DatetimeIndex, fin: pd.Timestamp, periode: dict) -> pd.Timestamp | None:
    """Trouve la séance de départ d'une période.

    Exemple : pour « 1 mois » au 16/10/2026, on cherche le dernier cours
    disponible au 16/09/2026 ou juste avant. Pour « depuis le 1er janvier »,
    c'est le dernier cours de l'année précédente.
    Renvoie None si l'historique commun ne remonte pas assez loin.
    """
    if periode.get("depuis_debut_annee"):
        cible = pd.Timestamp(year=fin.year - 1, month=12, day=31)
    else:
        cible = fin - pd.DateOffset(months=periode["mois"])
    candidates = dates[dates <= cible]
    if len(candidates) == 0:
        return None
    return candidates[-1]


def duree_en_annees(debut: pd.Timestamp, fin: pd.Timestamp) -> float:
    return (fin - debut).days / 365.25


# -----------------------------------------------------------------------------
# Indicateurs élémentaires
# -----------------------------------------------------------------------------

def rendements_quotidiens(cours: pd.Series) -> pd.Series:
    return cours.pct_change().dropna()


def performance_cumulee(cours: pd.Series) -> float:
    """Gain ou perte entre le premier et le dernier cours (0,05 = +5 %)."""
    return cours.iloc[-1] / cours.iloc[0] - 1


def annualiser(perf_cumulee: float, annees: float) -> float:
    """Rendement annuel moyen équivalent (taux actuariel)."""
    return (1 + perf_cumulee) ** (1 / annees) - 1


def volatilite_annualisee(cours: pd.Series, seances_par_an: int) -> float:
    return rendements_quotidiens(cours).std(ddof=1) * math.sqrt(seances_par_an)


def perte_maximale(cours: pd.Series) -> float:
    """Pire baisse entre un plus haut et un plus bas ultérieur (−0,20 = −20 %)."""
    return (cours / cours.cummax() - 1).min()


def ecart_de_suivi(cours_etf: pd.Series, cours_ref: pd.Series, seances_par_an: int) -> float:
    """Volatilité annualisée de la différence de rendement quotidien avec la référence.

    0 % = l'ETF fait exactement comme le MSCI World chaque jour ;
    plus c'est élevé, plus l'ETF s'en écarte.
    """
    ecarts = rendements_quotidiens(cours_etf) - rendements_quotidiens(cours_ref)
    return ecarts.dropna().std(ddof=1) * math.sqrt(seances_par_an)


def taux_sans_risque_annuel(estr: pd.Series, debut: pd.Timestamp, fin: pd.Timestamp) -> float | None:
    """Rendement annuel d'un placement au €STR entre deux dates.

    Le €STR est un taux annuel « base 360 jours » publié chaque jour ouvré.
    On capitalise jour par jour (les week-ends reprennent le taux du vendredi,
    comme sur le marché monétaire), puis on ramène le résultat à un an.
    """
    jours = pd.date_range(debut + pd.Timedelta(days=1), fin, freq="D")
    taux = estr.reindex(estr.index.union(jours)).sort_index().ffill().reindex(jours)
    if taux.isna().any() or len(jours) == 0:
        return None
    croissance = float(np.prod(1 + taux.values / 100 / 360))
    return croissance ** (1 / duree_en_annees(debut, fin)) - 1


# -----------------------------------------------------------------------------
# Tableau complet des indicateurs
# -----------------------------------------------------------------------------

def _pct(x: float | None, decimales: int = 2) -> float | None:
    """Convertit 0,0534 en 5,34 (pour l'affichage en %), ou laisse None."""
    if x is None or not np.isfinite(x):
        return None
    return round(float(x) * 100, decimales)


def indicateurs_periode(tableau: pd.DataFrame, id_reference: str, estr: pd.Series | None,
                        periode: dict, params: dict,
                        debut_risque_fiable: dict[str, pd.Timestamp] | None = None) -> dict:
    """Calcule tous les indicateurs de tous les ETF pour une période donnée.

    `debut_risque_fiable` : pour un ETF dont l'historique ancien vient d'une
    cotation bruitée (raccordement), date à partir de laquelle les indicateurs
    de risque quotidiens (volatilité, écart de suivi, Sharpe) sont fiables.
    Si la période commence avant, ces indicateurs sont signalés.
    """
    debut_risque_fiable = debut_risque_fiable or {}
    fin = tableau.index[-1]
    debut = date_debut(tableau.index, fin, periode)
    entete = {"id": periode["id"], "libelle": periode["libelle"], "fin": fin.date().isoformat()}
    if debut is None:
        return {**entete, "disponible": False,
                "raison": f"historique commun insuffisant (débute le {tableau.index[0].date().isoformat()})"}

    extrait = tableau.loc[debut:fin]
    annees = duree_en_annees(debut, fin)
    mois = periode.get("mois", 0)
    seances = params["seances_par_an"]
    calcul_sharpe = mois >= params["sharpe_duree_min_mois"]
    calcul_annualise = mois >= params["annualisation_duree_min_mois"]
    rf = taux_sans_risque_annuel(estr, debut, fin) if (calcul_sharpe and estr is not None) else None

    perf_ref = performance_cumulee(extrait[id_reference])
    resultats = {}
    for id_etf in tableau.columns:
        cours = extrait[id_etf]
        perf = performance_cumulee(cours)
        vol = volatilite_annualisee(cours, seances)
        ligne = {
            "perf_cumulee_pct": _pct(perf),
            "perf_annualisee_pct": _pct(annualiser(perf, annees)) if calcul_annualise else None,
            "volatilite_pct": _pct(vol),
            "perte_max_pct": _pct(perte_maximale(cours)),
            "sharpe": None,
        }
        # Seuil de 1e-6 plutôt que 0 : une volatilité « presque nulle » due aux
        # arrondis de l'ordinateur donnerait un Sharpe absurde (des milliards).
        if calcul_sharpe and rf is not None and vol > 1e-6:
            ligne["sharpe"] = round(float((annualiser(perf, annees) - rf) / vol), 2)
        if id_etf in debut_risque_fiable and debut < debut_risque_fiable[id_etf]:
            ligne["risque_fiabilite_reduite"] = True
        if id_etf != id_reference:
            # Performance relative : différence de performance, en points de %.
            ligne["perf_relative_pts"] = _pct(perf - perf_ref)
            ligne["ecart_suivi_pct"] = _pct(ecart_de_suivi(cours, extrait[id_reference], seances))
        resultats[id_etf] = ligne

    return {
        **entete,
        "disponible": True,
        "debut": debut.date().isoformat(),
        "nb_seances": int(len(extrait) - 1),
        "taux_sans_risque_pct": _pct(rf) if rf is not None else None,
        "etf": resultats,
    }
