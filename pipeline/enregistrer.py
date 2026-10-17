"""Enregistrement sûr des résultats dans le dépôt GitHub (utilisé par les deux tâches automatiques).

Lancement :  python -m pipeline.enregistrer --message "Titres du …" data/titres data/journal_execution.csv

Deux protections contre les conflits d'enregistrement :
1. Les deux tâches font partie du même groupe « ecriture-depot » sur GitHub :
   elles ne s'exécutent jamais en même temps.
2. Si le dépôt a quand même changé entre-temps (par exemple une modification
   faite à la main), ce script récupère les dernières modifications, rejoue
   l'enregistrement par-dessus, puis réessaie l'envoi, jusqu'à 5 fois avec une
   attente croissante. Les fichiers qui ne font que s'allonger (journal,
   titres) sont fusionnés en gardant les lignes des deux côtés (règle
   « merge=union » du fichier .gitattributes).
"""

import argparse
import subprocess
import sys
import time


def git(*args: str, verifier: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=verifier)


def enregistrer(message: str, chemins: list[str], essais: int = 5, attente_base: float = 5.0) -> bool:
    """Ajoute, enregistre et envoie les fichiers. Renvoie True si tout est envoyé (ou s'il n'y a rien à faire)."""
    git("add", "--", *chemins, verifier=False)
    if git("diff", "--cached", "--quiet", verifier=False).returncode == 0:
        print("Rien de nouveau à enregistrer.")
        return True
    git("commit", "-m", message)
    for essai in range(1, essais + 1):
        recuperation = git("pull", "--rebase", verifier=False)
        if recuperation.returncode != 0:
            # Conflit impossible à fusionner automatiquement : on annule et on réessaie plus tard.
            git("rebase", "--abort", verifier=False)
            print(f"Essai {essai} : récupération impossible ({recuperation.stderr.strip()[:200]})")
        elif git("push", verifier=False).returncode == 0:
            print(f"Enregistré et envoyé (essai {essai}).")
            return True
        else:
            print(f"Essai {essai} : envoi refusé (le dépôt a changé entre-temps).")
        time.sleep(attente_base * essai)
    print("Échec de l'enregistrement après plusieurs essais.", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True)
    parser.add_argument("chemins", nargs="+")
    args = parser.parse_args()
    return 0 if enregistrer(args.message, args.chemins) else 1


if __name__ == "__main__":
    sys.exit(main())
