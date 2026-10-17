"""Suivi du taux de titres « neutres » et analyse par type de titre ESG (point 11).

Lancement :  python -m analyses.suivi_neutres_esg

1. Taux de neutres par groupe et par journée (historique data/sentiment_quotidien.csv).
2. Sur les titres ESG collectés : part de neutres selon le type de titre
   (réglementation et publications / annonces d'entreprises / autres), repéré
   par des mots-clés simples. Sert à vérifier comment FinBERT traite l'ESG.
"""

import glob
import re

import pandas as pd

REGLEMENTATION = (r"\b(?:rule|rules|regulat\w*|directive|law|legislat\w*|SFDR|CSRD|ISSB|ESMA|SEC|EU|commission|"
                  r"propos\w*|consultation|standard\w*|disclosure\w*|report\w*|guidance)\b")
ANNONCE = r"\b(?:launch\w*|announc\w*|unveil\w*|partner\w*|appoint\w*|join\w*|sign\w*|invest\w*|fund\w*|acquir\w*|raise\w*|issue\w*)\b"


def main() -> None:
    try:
        histo = pd.read_csv("data/sentiment_quotidien.csv", encoding="utf-8-sig")
        print("1. Taux de neutres par journée (en %)")
        print(histo.pivot(index="seance", columns="groupe", values="neutre_pct").to_string())
    except FileNotFoundError:
        print("1. Pas encore d'historique.")

    titres = pd.concat([pd.read_csv(f, encoding="utf-8-sig", dtype=str)
                        for f in glob.glob("data/titres/**/*.csv", recursive=True)]).drop_duplicates("id")
    titres = titres[titres["id"] != "id"]
    esg = titres[titres["groupe"] == "esg"].copy()
    esg["type_titre"] = "autre"
    esg.loc[esg["titre"].str.contains(ANNONCE, flags=re.I, regex=True), "type_titre"] = "annonce"
    esg.loc[esg["titre"].str.contains(REGLEMENTATION, flags=re.I, regex=True), "type_titre"] = "réglementation"
    print(f"\n2. Titres ESG ({len(esg)}) : répartition des classes FinBERT selon le type de titre (en %)")
    tableau = esg.groupby("type_titre")["classe"].value_counts(normalize=True).mul(100).round(1).unstack(fill_value=0)
    tableau["nb_titres"] = esg["type_titre"].value_counts()
    print(tableau.to_string())
    marche = titres[titres["groupe"] == "marche"]
    print(f"\nPour comparaison, groupe marché : {round((marche['classe'] == 'neutre').mean() * 100, 1)} % de neutres")
    print("\nExemples de titres « réglementation » classés neutres :")
    print(esg[(esg["type_titre"] == "réglementation") & (esg["classe"] == "neutre")]["titre"].head(6).to_string(index=False))


if __name__ == "__main__":
    main()
