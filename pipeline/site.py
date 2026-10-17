"""Prépare le texte de la méthodologie pour le site.

Le texte source est contenu/methodologie.md (Markdown, lisible sur GitHub).
Il est converti en HTML et enregistré dans docs/data/methodologie.json, avec
un sommaire construit à partir des grands titres (« ## »). Le site affiche
donc toujours exactement le texte de référence, sans copie à la main.

Lancement :  python -m pipeline.site   (aussi exécuté chaque nuit)
"""

import re
import sys
import unicodedata
from datetime import datetime, timezone
from html import unescape

import markdown

from pipeline.config import DOSSIER_SITE_DATA, RACINE
from pipeline.sorties import ecrire_json_si_valide

SOURCE = RACINE / "contenu" / "methodologie.md"
FICHIER = DOSSIER_SITE_DATA / "methodologie.json"


def ancre(texte: str) -> str:
    """« Sentiment de l'actualité » → « sentiment-de-l-actualite »."""
    t = unicodedata.normalize("NFKD", unescape(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


LISTE = re.compile(r"^\s*(\d+\.|[-*])\s")


def preparer(md: str) -> str:
    """Corrections avant conversion.

    - Une liste qui suit directement un paragraphe (sans ligne vide) n'est pas
      reconnue par Markdown : on insère la ligne vide manquante.
    - Typographie française : espace insécable avant « : ; ! ? % » et après « « »,
      pour qu'aucun signe ne se retrouve seul en début de ligne.
    """
    lignes, sortie = md.split("\n"), []
    for i, ligne in enumerate(lignes):
        precedente = sortie[-1] if sortie else ""
        if LISTE.match(ligne) and precedente.strip() and not LISTE.match(precedente) and not precedente.startswith(("|", "#")):
            sortie.append("")
        sortie.append(ligne)
    texte = "\n".join(sortie)
    texte = re.sub(r" ([:;!?»%])(?=\s|$|[.,)])", " \\1", texte)
    return texte.replace("« ", "« ")


def convertir(md: str) -> dict:
    """Convertit le Markdown en HTML et numérote les grandes parties (01, 02…)."""
    md = preparer(md)
    # Le titre de premier niveau et le chapeau en italique de la source ne sont pas repris :
    # le site affiche son propre titre « Méthodologie ».
    md = re.sub(r"\A# .*\n+(\*[^\n]*\*\n+)?", "", md)
    html = markdown.markdown(md, extensions=["tables", "sane_lists"], output_format="html")
    html = html.replace("<hr />", "").replace("<hr>", "")
    sommaire = []

    def remplacer(m: re.Match) -> str:
        titre = m.group(1)
        numero = f"{len(sommaire) + 1:02d}"
        identifiant = "m-" + ancre(re.sub(r"<[^>]+>", "", titre))
        sommaire.append({"numero": numero, "titre": unescape(re.sub(r"<[^>]+>", "", titre)), "id": identifiant})
        return f'<h2 id="{identifiant}"><span class="k">{numero}</span>{titre}</h2>'

    html = re.sub(r"<h2>(.*?)</h2>", remplacer, html)
    # Le premier paragraphe, avant la première partie, sert de chapeau.
    if html.lstrip().startswith("<p>"):
        html = html.lstrip().replace("<p>", '<p class="chapeau">', 1)
    # Les tableaux larges défilent horizontalement au lieu de déborder.
    html = html.replace("<table>", '<div class="tableau-defilant"><table>').replace("</table>", "</table></div>")
    return {"html": html, "sommaire": sommaire}


def main() -> int:
    contenu = convertir(SOURCE.read_text(encoding="utf-8"))
    modifie = datetime.fromtimestamp(SOURCE.stat().st_mtime, tz=timezone.utc)
    donnees = {"source": "contenu/methodologie.md", "genere_le_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "source_modifiee_le_utc": modifie.strftime("%Y-%m-%dT%H:%M:%SZ"), **contenu}
    ecrit, raison = ecrire_json_si_valide(FICHIER, donnees, [(len(contenu["sommaire"]) >= 3, "sommaire trop court")])
    print(f"Méthodologie : {len(contenu['sommaire'])} parties" if ecrit else f"Méthodologie non écrite : {raison}")
    return 0 if ecrit else 1


if __name__ == "__main__":
    sys.exit(main())
