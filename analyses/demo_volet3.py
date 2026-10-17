"""Démonstration du volet 3 sur les VRAIES performances relatives de l'ETF SRI.

Lancement :  python -m analyses.demo_volet3

Le sentiment réel ne couvre encore que quelques journées : pour vérifier que
toute la chaîne fonctionne sur de vraies données de marché, on utilise les
120 dernières séances réelles de l'ETF SRI et du MSCI World, avec un
sentiment SIMULÉ dans deux scénarios :
  A. sentiment sans aucun lien avec la performance (pur hasard) ;
  B. sentiment construit pour être lié à la performance relative du lendemain.
Le volet 3 doit ne rien trouver en A et détecter le lien en B.
Rien n'est enregistré ; ces chiffres ne sont PAS des résultats du projet.
"""

import json

import numpy as np
import pandas as pd

from pipeline import parallele, synthese
from pipeline.config import DOSSIER_SITE_DATA, parametres


def main() -> None:
    perf = json.load(open(DOSSIER_SITE_DATA / "performance.json", encoding="utf-8"))
    dates = pd.to_datetime(perf["series"]["dates"])
    cours = pd.DataFrame({k: perf["series"]["base100"][k] for k in ("msci_world", "sri")}, index=dates).iloc[-121:]
    relatif = (cours["sri"].pct_change() - cours["msci_world"].pct_change()).dropna()
    rng = np.random.default_rng(2026)
    p = parametres()["parallele"]

    for nom, lien in (("A. sentiment simulé SANS lien", 0.0), ("B. sentiment simulé AVEC lien vers J+1", 0.5)):
        bruit = rng.normal(0, 15, len(relatif))
        lendemain = relatif.shift(-1).fillna(0).values
        solde = bruit + lien * lendemain / relatif.std() * 15
        etiquettes = np.where(solde > 10, "positif", np.where(solde < -10, "négatif", "neutre"))
        histo = pd.DataFrame([{"seance": d.date().isoformat(), "groupe": g, "solde": s, "solde_dates_fiables": s,
                               "etiquette": e, "couverture_partielle": False}
                              for d, s, e in zip(relatif.index, solde, etiquettes) for g in ("marche", "esg")])
        res = parallele.analyser(cours, "msci_world", histo, p)
        bloc = res["etf"]["sri"]["marche"]
        t, c = bloc["test_decalage_j1"], bloc["comparaison_jours"]
        print(f"\n=== {nom} ({t['n']} séances réelles de l'ETF SRI)")
        print(f"  même jour     : r = {bloc['correlation_meme_jour']['r']:+.3f}  p = {bloc['correlation_meme_jour']['p']:.3f}")
        print(f"  décalage J+1  : r = {t['r']:+.3f}  p = {t['p']:.3f}  → {'SIGNIFICATIF' if t['significatif'] else 'non significatif'}")
        if c["disponible"]:
            print(f"  jours positifs ({c['n_positifs']}) : {c['moyenne_jours_positifs_pts']:+.3f} pt/jour ; "
                  f"jours négatifs ({c['n_negatifs']}) : {c['moyenne_jours_negatifs_pts']:+.3f} pt/jour ; p = {c['p']:.3f}")
        else:
            print(f"  comparaison : non disponible ({c['n_positifs']} jours positifs, {c['n_negatifs']} négatifs)")
        gl = bloc["correlation_glissante"]
        print(f"  corrélation glissante 30 j : {len(gl)} valeurs, de {gl[0]['r']:+.2f} à {gl[-1]['r']:+.2f}")
        print("  synthèse :", synthese.phrase_lien(res))


if __name__ == "__main__":
    main()
