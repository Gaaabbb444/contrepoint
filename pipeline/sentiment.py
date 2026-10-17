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


def indicateurs_journee(articles: pd.DataFrame, p_cfg: dict) -> dict:
    """Calcule les indicateurs d'un groupe d'articles (une journée, un groupe)."""
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

    return {
        "nb_articles": n,
        "nb_sources": int(articles["source"].nunique()) if n else 0,
        "positif_pct": round(p * 100, 1),
        "neutre_pct": round(float(parts.get("neutre", 0)) * 100, 1),
        "negatif_pct": round(q * 100, 1),
        "solde": round(solde, 1),
        "marge_erreur": round(marge, 1) if math.isfinite(marge) else None,
        "etiquette": etiquette(solde, marge, n, p_cfg),
        "plus_positifs": extremes("positif", "p_positif") if n else [],
        "plus_negatifs": extremes("negatif", "p_negatif") if n else [],
    }
