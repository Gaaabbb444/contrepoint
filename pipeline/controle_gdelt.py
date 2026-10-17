"""Indicateur de contrôle facultatif : la « tonalité » GDELT.

GDELT (projet universitaire gratuit, sans clé) mesure la tonalité moyenne des
articles de presse du monde entier en comptant les mots positifs et négatifs
d'un dictionnaire, sur l'article complet. C'est une MÉTHODE DIFFÉRENTE de
FinBERT (réseau de neurones appliqué à nos titres) : les deux séries ne sont
jamais mélangées ni comparées en niveau, seulement en tendance.

Constaté le 17/10/2026 : l'API refuse très souvent les requêtes (« trop de
requêtes »). Cette étape est donc tentée une fois par nuit et son échec n'a
AUCUNE conséquence sur le reste du traitement.
"""

import time

import pandas as pd
import requests

API = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUETES = {
    "marche": '("stock market" OR stocks OR "wall street") sourcelang:english',
    "esg": '(ESG OR "sustainable finance" OR "sustainable investing") sourcelang:english',
}


def lire_tonalite(reponse_json: dict) -> pd.Series:
    """Transforme la réponse « timelinetone » de GDELT en série datée."""
    points = reponse_json["timeline"][0]["data"]
    dates = pd.to_datetime([p["date"] for p in points], format="%Y%m%dT%H%M%SZ", utc=True)
    return pd.Series([float(p["value"]) for p in points], index=dates.date)


def telecharger(groupe: str) -> pd.Series:
    params = {"query": REQUETES[groupe], "mode": "timelinetone", "timespan": "3months", "format": "json"}
    r = requests.get(API, params=params, timeout=60, headers={"User-Agent": "Contrepoint (projet personnel)"})
    r.raise_for_status()
    return lire_tonalite(r.json())


def collecter(pause_secondes: int = 20, essais: int = 2) -> dict[str, pd.Series]:
    """Une requête par groupe, bien espacées (GDELT demande au moins 5 s entre deux requêtes).

    Chaque groupe est tenté séparément : on garde ce qui a réussi. Lève une
    erreur seulement si aucun groupe n'a pu être obtenu.
    """
    resultats, erreurs = {}, []
    for groupe in REQUETES:
        for essai in range(essais):
            time.sleep(pause_secondes if (resultats or erreurs or essai) else 0)
            try:
                resultats[groupe] = telecharger(groupe)
                break
            except Exception as erreur:  # noqa: BLE001
                erreurs.append(f"{groupe} : {erreur}")
    if not resultats:
        raise RuntimeError(" ; ".join(erreurs))
    return resultats
