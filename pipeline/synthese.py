"""Synthèse automatique en français, générée par des RÈGLES FIXES (aucune IA).

Chaque phrase est un modèle à trous, rempli avec les chiffres du jour selon
des règles écrites ci-dessous. Exemple :
« Humeur du marché : négative le vendredi 16/10 (solde −14, marge ±10, 139 articles). »

Règles :
1. Humeur du marché (dernière journée) : étiquette du jour, solde, marge,
   nombre d'articles ; mention si la journée a été partiellement relevée.
2. Bilan des 5 dernières journées : nombre de journées positives, neutres,
   négatives (les journées « signal insuffisant » sont comptées à part).
3. Actualité ESG : étiquette et solde de la dernière journée.
4. Performance relative de l'ETF ESG choisi sur 5 séances, puis sur 1 an :
   « surperforme » / « sous-performe » si l'écart atteint 0,1 point,
   sinon « fait jeu égal avec ».
5. Lien sentiment / performance : uniquement le TEST PRINCIPAL fixé à
   l'avance (sentiment « marché » de J → performance relative du SRI à J+1).
   Progression tant que l'échantillon est insuffisant ; sinon son résultat,
   avec le rappel que corrélation n'est pas causalité. Les tests
   exploratoires ne sont jamais cités.
"""

from datetime import date

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FEMININ = {"positif": "positive", "négatif": "négative", "neutre": "neutre"}


def nombre(x: float, decimales: int = 1, signe: bool = False) -> str:
    """Format français : virgule décimale, vrai signe moins (−), signe + facultatif."""
    texte = f"{abs(x):.{decimales}f}".replace(".", ",")
    if x < 0 and float(texte.replace(",", ".")) != 0:
        return "−" + texte
    return ("+" + texte) if signe and x > 0 else texte


def jour_fr(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{JOURS[d.weekday()]} {d.day:02d}/{d.month:02d}"


def date_fr(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def phrase_humeur(nom: str, g: dict, seance: str) -> str:
    if g["etiquette"] == "signal insuffisant":
        texte = f"{nom} le {jour_fr(seance)} : signal insuffisant ({g['nb_articles']} articles)."
    else:
        texte = (f"{nom} : {FEMININ[g['etiquette']]} le {jour_fr(seance)} (solde {nombre(g['solde'], 0, True)}, "
                 f"marge ±{nombre(g['marge_erreur'], 0)}, {g['nb_articles']} articles).")
    if g.get("couverture_partielle"):
        texte = texte[:-1] + " — journée partiellement relevée."
    return texte


def phrase_bilan(historique: list[dict], groupe: str, n: int = 5) -> str | None:
    lignes = [h for h in historique if h["groupe"] == groupe][-n:]
    if len(lignes) < 2:
        return None
    compte = {e: sum(1 for h in lignes if h["etiquette"] == e) for e in ("négatif", "neutre", "positif", "signal insuffisant")}
    morceaux = []
    for etiquette, singulier, pluriel in (("négatif", "négative", "négatives"), ("neutre", "neutre", "neutres"),
                                         ("positif", "positive", "positives")):
        if compte[etiquette]:
            morceaux.append(f"{compte[etiquette]} {singulier if compte[etiquette] == 1 else pluriel}")
    if compte["signal insuffisant"]:
        morceaux.append(f"{compte['signal insuffisant']} sans signal suffisant")
    return f"Sur les {len(lignes)} dernières journées de bourse : " + ", ".join(morceaux) + "."


def verbe_ecart(ecart_pts: float) -> str:
    if ecart_pts >= 0.1:
        return "surperforme"
    if ecart_pts <= -0.1:
        return "sous-performe"
    return "fait jeu égal avec"


def phrase_performance(perf: dict, id_esg: str) -> str | None:
    """Performance relative sur 5 séances (série base 100) et sur 1 an (tableau des périodes)."""
    series, noms = perf["series"], {e["id"]: e["nom_court"] for e in perf["etf"]}
    ref = perf["reference"]
    if id_esg not in series["base100"] or len(series["dates"]) < 6:
        return None
    b_esg, b_ref = series["base100"][id_esg], series["base100"][ref]
    p_esg = (b_esg[-1] / b_esg[-6] - 1) * 100
    p_ref = (b_ref[-1] / b_ref[-6] - 1) * 100
    ecart = p_esg - p_ref
    verbe = verbe_ecart(ecart)
    texte = f"Sur 5 séances, l'ETF {noms[id_esg]} {verbe} le MSCI World"
    texte += (f" ({nombre(p_esg, 1, True)} % contre {nombre(p_ref, 1, True)} %)" if verbe == "fait jeu égal avec"
              else f" de {nombre(abs(ecart), 1)} point{'s' if abs(ecart) >= 2 else ''} "
                   f"({nombre(p_esg, 1, True)} % contre {nombre(p_ref, 1, True)} %)")
    un_an = next((p for p in perf["periodes"] if p["id"] == "1a" and p["disponible"]), None)
    if un_an:
        rel = un_an["etf"][id_esg]["perf_relative_pts"]
        texte += f" ; sur un an, l'écart est de {nombre(rel, 1, True)} point{'s' if abs(rel) >= 2 else ''}"
    if perf.get("derniere_seance_provisoire"):
        texte += " — dernière clôture encore provisoire"
    return texte + "."


def phrase_lien(parallele: dict) -> str | None:
    """Résultat du SEUL test principal, fixé à l'avance.

    Règle : la synthèse ne cite JAMAIS un test exploratoire (autres ETF, groupe
    ESG, même jour, comparaison des jours), même « significatif » : ces tests
    servent à formuler des pistes, pas des conclusions.
    """
    principal = parallele.get("test_principal")
    if not principal or not principal.get("progression"):
        return None
    prog, test = principal["progression"], principal["resultat"]
    intitule = "Test principal (sentiment du marché du jour et performance relative de l'ETF World SRI le lendemain)"
    if not test.get("disponible"):
        texte = (f"{intitule} : pas encore interprétable "
                 f"({prog['jours_exploitables']} / {prog['jours_requis']} jours de bourse exploitables")
        if prog.get("date_estimee"):
            texte += f" ; résultats attendus vers le {date_fr(prog['date_estimee'])}"
        return texte + ")."
    if test["significatif"]:
        return (f"{intitule} : sur {test['n']} jours de bourse, lien {test['sens']} statistiquement significatif "
                f"(corrélation {nombre(test['r'], 2)}). Corrélation n'est pas causalité.")
    return (f"{intitule} : sur {test['n']} jours de bourse, aucun lien statistiquement significatif "
            f"(corrélation {nombre(test['r'], 2)}).")


def generer(perf: dict | None, sentiment: dict | None, parallele: dict | None, id_esg: str) -> list[str]:
    """Assemble les phrases disponibles (une source manquante supprime seulement ses phrases)."""
    phrases = []
    if sentiment and sentiment.get("groupes"):
        seance = sentiment["derniere_seance"]
        if "marche" in sentiment["groupes"]:
            phrases.append(phrase_humeur("Humeur du marché", sentiment["groupes"]["marche"], seance))
            bilan = phrase_bilan(sentiment.get("historique", []), "marche")
            if bilan:
                phrases.append(bilan)
        if "esg" in sentiment["groupes"]:
            phrases.append(phrase_humeur("Actualité ESG", sentiment["groupes"]["esg"], seance))
    if perf:
        p = phrase_performance(perf, id_esg)
        if p:
            phrases.append(p)
    if parallele:
        p = phrase_lien(parallele)  # toujours le test principal, quel que soit l'ETF affiché
        if p:
            phrases.append(p)
    return phrases


def essentiel(phrases: list[str]) -> list[str]:
    """Phrases affichées sur l'accueil (1 ou 2) : l'humeur du marché du jour et l'écart de performance.

    Règle fixe : on garde la phrase qui commence par « Humeur du marché » et celle
    qui commence par « Sur 5 séances ». Les autres (bilan de la semaine, actualité
    ESG, test principal) restent accessibles par « Lire la synthèse complète ».
    """
    return [p for p in phrases if p.startswith(("Humeur du marché", "Sur 5 séances"))]
