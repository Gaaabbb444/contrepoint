# Contrepoint

*Performance ESG et sentiment de marché*

> README provisoire. La version pédagogique complète sera rédigée à l'étape 5.
> Le plan détaillé est dans [PLAN_ARCHITECTURE.md](PLAN_ARCHITECTURE.md).

## Lancer les calculs sur son ordinateur (développement)

```
.venv\Scripts\python.exe -m pytest                        # vérifie les calculs
.venv\Scripts\python.exe -m pipeline.traitement_nuit      # télécharge et calcule
.venv\Scripts\python.exe -m analyses.resume_performance   # affiche le résultat
```

## Vérifier que tout tourne

- **Tâches automatiques** : onglet [Actions](https://github.com/Gaaabbb444/contrepoint/actions) du dépôt. Une coche verte signifie que tout va bien. Une croix rouge signifie qu'une étape a échoué : GitHub envoie alors un e-mail, et le site garde ses dernières données valides.
- **Journal** : [data/journal_execution.csv](data/journal_execution.csv), avec une ligne par étape et par exécution.
- **État affiché par le site** : [docs/data/etat.json](docs/data/etat.json).
- **Lancer une tâche à la main** : onglet Actions, choisir la tâche, puis « Run workflow ».

## ⚠️ Mises à jour manuelles à faire

Certaines informations ne peuvent pas être récupérées automatiquement : elles sont relevées à la main dans [config/etf.yaml](config/etf.yaml), avec leur source et leur date (`verifie_le`). Le site affiche ces dates.

| Quoi | Fréquence conseillée | Où vérifier |
|---|---|---|
| **Notes MSCI ESG** (note AAA à CCC, score de qualité, percentile) | chaque trimestre | Fiche (« factsheet ») de chaque ETF iShares, section « ESG Metrics » |
| **Label ISR** | chaque trimestre | Liste officielle, mise à jour chaque mois : https://www.lelabelisr.fr/fonds-labellises/ |
| **Label Greenfin** | chaque semestre | https://www.ecologie.gouv.fr/politiques-publiques/label-greenfin |
| **Classification SFDR et frais** | chaque année | Fiche et prospectus de chaque ETF |

Après chaque vérification, mettre à jour la valeur et la date `verifie_le` (et `date` pour les notes MSCI).

**Note MSCI du MSCI World** : non publiée par iShares pour ce fonds, et l'outil de recherche public de MSCI est désormais réservé à ses clients (constaté le 17/10/2026). À revérifier à chaque mise à jour.
