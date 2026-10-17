"""Affiche un résumé lisible de docs/data/performance.json.

Lancement :  python -m analyses.resume_performance
"""

from pipeline.config import DOSSIER_SITE_DATA
from pipeline.sorties import lire_json


def fmt(x, suffixe="", signe=False):
    if x is None:
        return "—"
    texte = f"{x:+.2f}" if signe else f"{x:.2f}"
    return texte.replace(".", ",") + suffixe


def main() -> None:
    d = lire_json(DOSSIER_SITE_DATA / "performance.json")
    noms = {e["id"]: e["nom_court"] for e in d["etf"]}
    print(f"Dernière séance : {d['derniere_seance']} | séances communes depuis le "
          f"{d['premiere_seance_commune']} : {d['nb_seances_communes']} | devise : {d['devise']}")
    for p in d["periodes"]:
        if not p["disponible"]:
            print(f"\n■ {p['libelle']} : indisponible ({p['raison']})")
            continue
        rf = f" | taux sans risque €STR : {fmt(p['taux_sans_risque_pct'], ' %')}" if p["taux_sans_risque_pct"] else ""
        print(f"\n■ {p['libelle']} (du {p['debut']} au {p['fin']}, {p['nb_seances']} séances){rf}")
        print(f"  {'ETF':<22}{'Perf.':>9}{'Annualisée':>12}{'Relative':>10}{'Volat.':>8}{'Perte max':>11}{'Sharpe':>8}{'Écart suivi':>13}")
        for id_etf, v in p["etf"].items():
            print(f"  {noms[id_etf]:<22}{fmt(v['perf_cumulee_pct'], ' %', True):>9}"
                  f"{fmt(v['perf_annualisee_pct'], ' %', True):>12}{fmt(v.get('perf_relative_pts'), ' pt', True):>10}"
                  f"{fmt(v['volatilite_pct'], ' %'):>8}{fmt(v['perte_max_pct'], ' %'):>11}"
                  f"{fmt(v['sharpe']):>8}{fmt(v.get('ecart_suivi_pct'), ' %'):>13}"
                  f"{'  ⚠ risque peu fiable' if v.get('risque_fiabilite_reduite') else ''}")


if __name__ == "__main__":
    main()
