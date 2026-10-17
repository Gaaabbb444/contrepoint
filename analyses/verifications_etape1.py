"""Vérifications ponctuelles de l'étape 1 (à relancer si besoin).

Lancement :  python -m analyses.verifications_etape1

1. Nos performances, calculées sur les cours de bourse Yahoo, sont comparées
   à celles publiées par iShares dans la fiche officielle de l'ETF SRI (part
   en euros, données au 30/09/2026, calculées sur la valeur liquidative).
2. Correction D : mesure du « bruit » ajouté par la conversion en euros de
   l'ETF Paris-Aligned (coté en dollars à Amsterdam, converti au taux BCE de
   14 h 15), en le comparant à sa cotation directe en euros sur Xetra
   (WPAB.DE, disponible seulement depuis août 2025).
"""

import math
from datetime import date

import pandas as pd

from pipeline import collecte_prix, performance
from pipeline.journal import Journal

# Chiffres de la fiche iShares SUSW (« Share Class », en %), au 30/09/2026.
FICHE_SRI = {
    "annee_2023": 20.70, "annee_2024": 18.25, "annee_2025": 1.55,
    "cumul_1m": 0.05, "cumul_3m": -0.26, "cumul_ytd": 15.70, "cumul_1a": 17.87,
    "annualise_3a": 14.25, "annualise_5a": 9.83,
}


def cours_a(serie: pd.Series, jour: str) -> float:
    """Dernier cours connu à une date donnée (ou juste avant)."""
    return float(serie[serie.index <= pd.Timestamp(jour)].iloc[-1])


def comparer_fiche_sri(journal: Journal) -> None:
    s = collecte_prix.telecharger_cours("2B7K.DE", journal)
    fin = "2026-09-30"
    calc = {
        "annee_2023": cours_a(s, "2023-12-31") / cours_a(s, "2022-12-31") - 1,
        "annee_2024": cours_a(s, "2024-12-31") / cours_a(s, "2023-12-31") - 1,
        "annee_2025": cours_a(s, "2025-12-31") / cours_a(s, "2024-12-31") - 1,
        "cumul_1m": cours_a(s, fin) / cours_a(s, "2026-08-31") - 1,
        "cumul_3m": cours_a(s, fin) / cours_a(s, "2026-06-30") - 1,
        "cumul_ytd": cours_a(s, fin) / cours_a(s, "2025-12-31") - 1,
        "cumul_1a": cours_a(s, fin) / cours_a(s, "2025-09-30") - 1,
        "annualise_3a": (cours_a(s, fin) / cours_a(s, "2023-09-30")) ** (1 / 3) - 1,
        "annualise_5a": (cours_a(s, fin) / cours_a(s, "2021-09-30")) ** (1 / 5) - 1,
    }
    print("\n1. ETF SRI : nos calculs (cours de bourse Xetra) contre la fiche iShares (valeur liquidative)")
    print(f"   {'indicateur':<14}{'Contrepoint':>13}{'iShares':>10}{'écart':>9}")
    for cle, officiel in FICHE_SRI.items():
        nous = calc[cle] * 100
        print(f"   {cle:<14}{nous:>12.2f}%{officiel:>9.2f}%{nous - officiel:>+8.2f}")


def mesurer_bruit_change(journal: Journal) -> None:
    eurusd = collecte_prix.telecharger_eurusd(date(2025, 1, 1), journal)
    converti = collecte_prix.convertir_en_euros(collecte_prix.telecharger_cours("WPAB.AS", journal), eurusd, 4)
    direct = collecte_prix.telecharger_cours("WPAB.DE", journal)
    tableau = performance.aligner({"converti": converti, "direct": direct})
    r = tableau.pct_change().dropna()
    ecart = r["converti"] - r["direct"]
    print("\n2. Correction D : ETF Paris-Aligned converti au taux BCE contre sa cotation directe en euros")
    print(f"   période commune : {tableau.index[0].date()} → {tableau.index[-1].date()} ({len(r)} séances)")
    print(f"   écart quotidien moyen (en valeur absolue) : {ecart.abs().mean() * 100:.3f} point")
    print(f"   écart quotidien maximal                 : {ecart.abs().max() * 100:.3f} point")
    print(f"   « bruit » annualisé (écart-type × √252)   : {ecart.std() * math.sqrt(252) * 100:.2f} %")
    print(f"   corrélation des rendements quotidiens     : {r['converti'].corr(r['direct']):.4f}")
    perf_c = performance.performance_cumulee(tableau["converti"]) * 100
    perf_d = performance.performance_cumulee(tableau["direct"]) * 100
    print(f"   performance cumulée : convertie {perf_c:.2f} % / directe {perf_d:.2f} % (écart {perf_c - perf_d:+.2f} point)")


if __name__ == "__main__":
    j = Journal()
    comparer_fiche_sri(j)
    mesurer_bruit_change(j)
