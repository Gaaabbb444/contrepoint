"""Modèle FinBERT et indicateurs quotidiens de sentiment.

- FinBERT (ProsusAI/finbert) : modèle de langage spécialisé en finance, qui
  classe une phrase en « positive », « negative » ou « neutral » avec une
  probabilité pour chaque classe. Il ne tourne QUE dans GitHub Actions.
  Licence CC BY-NC-SA 4.0, © MIH AI B.V. (usage non commercial, avec citation).
- Indicateurs d'une journée de sentiment : répartition, solde net, marge
  d'erreur et étiquette du jour (correction A).
"""

import math
import os

import pandas as pd

from pipeline.config import parametres

TRADUCTION = {"positive": "positif", "neutral": "neutre", "negative": "negatif"}


class FinBERT:
    """Charge FinBERT (version figée) et note des textes par lots."""

    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        p = parametres()["sentiment"]
        torch.set_num_threads(os.cpu_count() or 2)
        # HF_HOME (dossier de cache) est fixé par GitHub Actions : le modèle est
        # restauré depuis le cache au lieu d'être retéléchargé à chaque relevé.
        self.tokenizer = AutoTokenizer.from_pretrained(p["modele"], revision=p["revision"])
        self.modele = AutoModelForSequenceClassification.from_pretrained(p["modele"], revision=p["revision"])
        self.modele.eval()
        self.etiquettes = {i: TRADUCTION[l.lower()] for i, l in self.modele.config.id2label.items()}
        self.torch = torch

    def predire(self, textes: list[str], lot: int = 32) -> list[dict]:
        resultats = []
        with self.torch.no_grad():
            for debut in range(0, len(textes), lot):
                entree = self.tokenizer(textes[debut:debut + lot], padding=True, truncation=True,
                                        max_length=128, return_tensors="pt")
                probas = self.torch.softmax(self.modele(**entree).logits, dim=-1)
                for ligne in probas.tolist():
                    resultats.append({self.etiquettes[i]: float(v) for i, v in enumerate(ligne)})
        return resultats


# -----------------------------------------------------------------------------
# Indicateurs d'une journée
# -----------------------------------------------------------------------------

def marge_erreur(p: float, q: float, n: int, facteur: float) -> float:
    """Marge d'erreur (en points) du solde net « % positifs − % négatifs ».

    Le solde est la différence de deux proportions mesurées sur le même
    échantillon de n articles. Sa variance vaut (p + q − (p − q)²) / n.
    Marge = facteur (1,96 pour 95 %) × écart-type, exprimée en points.
    """
    if n == 0:
        return float("inf")
    return facteur * math.sqrt(max(p + q - (p - q) ** 2, 0) / n) * 100


def etiquette(solde: float, marge: float, n: int, p_cfg: dict) -> str:
    """Étiquette du jour : positif, négatif, neutre ou signal insuffisant."""
    if n < p_cfg["articles_min"] or marge > p_cfg["marge_max_points"]:
        return "signal insuffisant"
    if solde > marge:
        return "positif"
    if solde < -marge:
        return "négatif"
    return "neutre"


def poids_plafonnes(parts: pd.Series, plafond: float) -> pd.Series:
    """Poids par média après plafonnement (méthode des indices boursiers plafonnés).

    Un média qui dépasse le plafond est ramené au plafond ; l'excédent est
    redistribué aux autres médias au prorata de leur poids, et l'on recommence
    tant qu'un média dépasse. Exemple : avec un plafond de 25 %, un média à
    40 % est ramené à 25 %, et les 15 points libérés sont répartis entre les autres.
    """
    poids = parts / parts.sum()
    if plafond * len(poids) < 1:  # impossible de tous les mettre sous le plafond
        return poids
    for _ in range(50):
        au_dessus = poids > plafond + 1e-12
        if not au_dessus.any():
            break
        excedent = (poids[au_dessus] - plafond).sum()
        poids[au_dessus] = plafond
        libres = ~au_dessus & (poids < plafond)
        poids[libres] += excedent * poids[libres] / poids[libres].sum()
    return poids


def solde_avec_plafond(articles: pd.DataFrame, plafond_pct: float) -> float | None:
    """Solde net si chaque média était plafonné à `plafond_pct` % du groupe (simulation)."""
    if articles.empty or "media" not in articles:
        return None
    parts = articles["media"].value_counts(normalize=True)
    poids_media = poids_plafonnes(parts.copy(), plafond_pct / 100)
    poids_article = articles["media"].map(poids_media / articles["media"].value_counts())
    signe = articles["classe"].map({"positif": 1, "negatif": -1, "neutre": 0})
    return round(float((poids_article * signe).sum()) * 100, 1)


def couverture(debut: pd.Timestamp, fin: pd.Timestamp, releves: list[pd.Timestamp], p_cfg: dict) -> dict:
    """La journée de sentiment a-t-elle été correctement relevée ?

    `releves` : heures des relevés de titres réussis (toutes dates). On compte
    ceux tombés dans la journée, on exige un relevé APRÈS la clôture (pour les
    derniers articles), et l'on mesure le plus long intervalle sans relevé
    entre le début de la journée et ce premier relevé qui suit la clôture.
    """
    pas = pd.Timedelta(hours=p_cfg["intervalle_releves_heures"])
    attendus = max(1, math.ceil((fin - debut) / pas))
    dans_journee = sorted(r for r in releves if debut < r <= fin)
    # Points de passage : début de journée, relevés, jusqu'au premier relevé après la clôture
    # (cherché jusqu'à 12 h après, car les flux gardent leurs articles plus longtemps).
    suite = sorted(r for r in releves if debut < r <= fin + pd.Timedelta(hours=p_cfg["couverture_ecart_max_heures"]))
    points, apres_cloture = [debut], False
    for r in suite:
        points.append(r)
        if r >= fin:
            apres_cloture = True
            break
    ecart_max = max((b - a for a, b in zip(points, points[1:])), default=fin - debut)
    if not apres_cloture:
        ecart_max = max(ecart_max, fin - points[-1])
    taux = min(1.0, len(dans_journee) / attendus)
    complete = (taux * 100 >= p_cfg["couverture_min_pct"] and apres_cloture
                and ecart_max <= pd.Timedelta(hours=p_cfg["couverture_ecart_max_heures"]))
    return {
        "releves_reussis": len(dans_journee),
        "releves_attendus": attendus,
        "plus_long_trou_heures": round(ecart_max.total_seconds() / 3600, 1),
        "couverture_partielle": not complete,
    }


def indicateurs_journee(articles: pd.DataFrame, p_cfg: dict) -> dict:
    """Calcule les indicateurs d'un groupe d'articles (une journée, un groupe).

    Les articles sans date fiable (« date_approximative ») comptent dans
    l'indicateur du jour, mais un second solde, calculé sans eux, sert aux
    tests statistiques du volet 3.
    """
    n = int(len(articles))
    parts = articles["classe"].value_counts(normalize=True) if n else pd.Series(dtype=float)
    p, q = float(parts.get("positif", 0)), float(parts.get("negatif", 0))
    solde = (p - q) * 100
    marge = marge_erreur(p, q, n, p_cfg["facteur_confiance"])
    k = p_cfg["titres_extremes"]

    def extremes(classe: str, colonne: str) -> list[dict]:
        choisis = articles[articles["classe"] == classe].nlargest(k, colonne)
        return [{"titre": r.titre, "source": r.source, "lien": r.lien, "probabilite": round(float(getattr(r, colonne)), 3),
                 "date_publication_utc": r.date_publication_utc} for r in choisis.itertuples()]

    if n and "date_approximative" in articles:
        approx = articles["date_approximative"].astype(str).str.lower().eq("true")
    else:
        approx = pd.Series(False, index=articles.index)
    fiables = articles[~approx] if n else articles
    parts_f = fiables["classe"].value_counts(normalize=True) if len(fiables) else pd.Series(dtype=float)
    medias = articles["media"].value_counts(normalize=True) if (n and "media" in articles) else pd.Series(dtype=float)

    return {
        "nb_articles": n,
        "nb_sources": int(articles["media"].nunique()) if (n and "media" in articles) else (int(articles["source"].nunique()) if n else 0),
        "nb_dates_approximatives": int(approx.sum()),
        "solde_dates_fiables": round((float(parts_f.get("positif", 0)) - float(parts_f.get("negatif", 0))) * 100, 1)
                               if len(fiables) else None,
        "part_media_principal_pct": round(float(medias.iloc[0]) * 100, 1) if len(medias) else None,
        "media_principal": str(medias.index[0]) if len(medias) else None,
        "solde_avec_plafond": solde_avec_plafond(articles, p_cfg.get("plafond_media_pct", 25)) if n else None,
        "positif_pct": round(p * 100, 1),
        "neutre_pct": round(float(parts.get("neutre", 0)) * 100, 1),
        "negatif_pct": round(q * 100, 1),
        "solde": round(solde, 1),
        "marge_erreur": round(marge, 1) if math.isfinite(marge) else None,
        "etiquette": etiquette(solde, marge, n, p_cfg),
        "plus_positifs": extremes("positif", "p_positif") if n else [],
        "plus_negatifs": extremes("negatif", "p_negatif") if n else [],
    }
