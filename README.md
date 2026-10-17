# Contrepoint

*Performance ESG et sentiment de marché*

**Site : https://gaaabbb444.github.io/contrepoint/**

Contrepoint est un tableau de bord gratuit, mis à jour automatiquement chaque nuit, qui répond à deux questions :

1. **Les fonds ESG mondiaux font-ils mieux ou moins bien que le marché ?** On compare quatre ETF « responsables » à un ETF qui réplique le MSCI World (l'indice des grandes entreprises des pays développés).
2. **Quelle est l'humeur de l'actualité financière, et a-t-elle un lien avec cette différence de performance ?** Un modèle d'intelligence artificielle spécialisé en finance, FinBERT, lit chaque jour plusieurs centaines de titres de presse et les classe en positifs, neutres ou négatifs.

Le projet ne coûte rien : aucun abonnement, aucune API payante, aucun serveur. Tout le calcul est fait par GitHub (gratuitement), et l'ordinateur personnel n'a pas besoin d'être allumé.

---

## Sommaire

1. [Ce que montre le site](#1-ce-que-montre-le-site)
2. [Comment ça marche](#2-comment-ça-marche)
3. [Pourquoi ces choix](#3-pourquoi-ces-choix)
4. [Ce que le projet ne permet pas de conclure](#4-ce-que-le-projet-ne-permet-pas-de-conclure)
5. [Expliquer le projet en entretien](#5-expliquer-le-projet-en-entretien)
6. [Vérifier que tout tourne](#6-vérifier-que-tout-tourne)
7. [⚠️ Mises à jour manuelles à faire](#7-️-mises-à-jour-manuelles-à-faire)
8. [Travailler sur le projet depuis son ordinateur](#8-travailler-sur-le-projet-depuis-son-ordinateur)
9. [Organisation des fichiers](#9-organisation-des-fichiers)
10. [Crédits et licences](#10-crédits-et-licences)

---

## 1. Ce que montre le site

| Partie | Contenu |
|---|---|
| **En-tête** | Une synthèse de deux phrases (humeur du marché du jour, écart de performance de l'ETF choisi) ; la synthèse complète se déplie sur demande. |
| **Volet 1 — Performance** | Graphique de l'écart de performance entre l'ETF ESG choisi et le MSCI World, sur 1 mois à 5 ans ; tableau des indicateurs (performance, volatilité, perte maximale, ratio de Sharpe, écart de suivi) ; explication sectorielle de l'écart. |
| **Volet 2 — Sentiment** | Humeur du jour pour l'actualité « marché » et l'actualité « ESG », avec sa marge d'erreur ; historique ; titres les plus positifs et les plus négatifs. |
| **Volet 3 — Mise en parallèle** | Le lien entre sentiment et performance relative, testé statistiquement. Tant qu'il n'y a pas assez de jours (60 au minimum), le site affiche une barre de progression et la date estimée des premiers résultats. |
| **Méthodologie** | Toutes les sources, tous les calculs, toutes les limites. Le texte source est [contenu/methodologie.md](contenu/methodologie.md). |

Les ETF comparés :

| ETF | Approche | Rôle |
|---|---|---|
| iShares Core MSCI World | aucune sélection ESG | **référence** |
| iShares MSCI World Screened | exclusions légères (armes, charbon, tabac…) | ESG « large » |
| iShares MSCI World SRI | ne garde que les 25 % d'entreprises les mieux notées de chaque secteur | ESG « strict » (affiché par défaut) |
| iShares MSCI World Paris-Aligned Climate | trajectoire de baisse des émissions compatible avec l'accord de Paris | ESG « climat » |
| BNP Paribas Easy MSCI World SRI PAB | SRI + climat, labellisé ISR | complément, présenté à part |

Les trois ETF iShares ESG ont les mêmes frais (0,20 %), le même gestionnaire et le même domicile que la référence : l'écart observé vient donc de la méthode ESG, pas des frais.

---

## 2. Comment ça marche

Le projet est une **chaîne de traitement automatique** (un « pipeline ») en trois temps.

```
 Toutes les 3 heures                Chaque nuit (04:41 UTC)                 En permanence
 ───────────────────                ───────────────────────                 ─────────────
 Collecte des titres     ──►        Cours des ETF (Yahoo Finance)    ──►    Site statique
 de presse (flux RSS)               Taux BCE (EUR/USD, €STR)                (GitHub Pages)
 + analyse FinBERT                  Calcul des performances                 lit les fichiers
 → data/titres/                     Sentiment de la journée                 docs/data/*.json
                                    Tests statistiques, synthèse
                                    → docs/data/*.json
```

**1. Collecte des titres (toutes les 3 heures).** Le programme lit une trentaine de flux RSS (le format qu'utilisent les sites de presse pour diffuser leurs derniers articles), écarte les doublons (la même dépêche reprise par plusieurs journaux) et fait lire chaque titre par FinBERT. Seuls le titre, le média, la date et le score sont conservés : les résumés d'articles ne sont **jamais stockés** (droit d'auteur).

**2. Traitement de nuit.** Le programme télécharge tout l'historique des cours, vérifie les données (cours figés, cours aberrants, clôtures pas encore publiées), calcule les indicateurs, agrège le sentiment de la journée de bourse écoulée, lance les tests statistiques et rédige la synthèse.

**3. Site.** Le site est une simple page web (HTML, CSS, JavaScript, sans bibliothèque) qui lit les fichiers de résultats. Il n'y a ni base de données ni serveur : GitHub Pages sert les fichiers tels quels.

**Le « moteur » : GitHub Actions.** GitHub prête gratuitement des ordinateurs pour exécuter du code à heures fixes. Les deux tâches sont décrites dans [.github/workflows/](.github/workflows/). Après chaque exécution, les résultats sont enregistrés dans le dépôt (un « commit »), ce qui garde aussi un historique complet de chaque journée.

**Robustesse.**
- Si une étape échoue (Yahoo indisponible, par exemple), les autres continuent et le site garde ses **dernières données valides**, avec un bandeau « Dernière mise à jour réussie le… ».
- Chaque étape est notée dans [data/journal_execution.csv](data/journal_execution.csv).
- Les problèmes durables (un média qui prend trop de place, une source qui ne répond plus) ouvrent automatiquement un ticket (« issue ») sur GitHub.

---

## 3. Pourquoi ces choix

| Choix | Raison |
|---|---|
| **ETF plutôt qu'indices** | Les indices MSCI ESG ne sont pas diffusés gratuitement ; les ETF qui les répliquent sont cotés en bourse, donc leurs cours sont publics. Bonus : on mesure ce qu'un épargnant obtient vraiment, frais compris. |
| **ETF capitalisants, cotés en euros, à 17 h 30** | Les dividendes sont réinvestis dans le cours (rendement total sans calcul supplémentaire) ; même devise et même heure de clôture pour tous, donc des comparaisons justes. |
| **Yahoo Finance + BCE** | Gratuits et sans inscription. Stooq bloque désormais les robots ; le taux sans risque (€STR) et le change viennent de la source officielle, la BCE. |
| **FinBERT plutôt qu'un dictionnaire de mots** | Un dictionnaire compte « bon » et « mauvais » sans comprendre la phrase ; FinBERT a été entraîné sur des phrases financières annotées par des professionnels. Sa version est figée pour que les résultats restent comparables dans le temps. |
| **Une journée de sentiment = de 17 h 30 à 17 h 30 (Paris)** | Elle colle aux séances de bourse ; les articles du week-end comptent pour le lundi. Ainsi tous les articles d'une journée sont publiés **avant** la séance suivante, ce qui permet de tester si le sentiment précède les cours. |
| **Une étiquette seulement si le signal est net** | Le solde du jour (positifs − négatifs) a une marge d'erreur qui dépend du nombre d'articles. On ne dit « positif » ou « négatif » que si le solde dépasse cette marge ; avec moins de 30 articles : « signal insuffisant ». |
| **Un seul test principal, fixé à l'avance** | Avec 24 tests possibles, au moins un paraîtrait « significatif » par pur hasard. Le test principal a été choisi le 17/10/2026, avant toute donnée ; les 23 autres sont exploratoires et corrigés (méthode de Holm). La synthèse ne cite jamais un test exploratoire. |
| **Pas de conclusion avant 60 jours** | En dessous, une corrélation varie trop au hasard pour être interprétée. Le site montre la progression plutôt qu'un chiffre trompeur. |
| **Site statique sur GitHub Pages** | Gratuit, rapide, sans maintenance de serveur, et sans risque de sécurité lié à une base de données. |
| **Paramètres regroupés dans [config/](config/)** | Chaque choix de méthode (seuils, périodes, sources) se lit et se modifie sans toucher au code. |

---

## 4. Ce que le projet ne permet pas de conclure

- **Le passé ne prédit pas l'avenir.** De 2023 à 2026, les géants technologiques américains ont porté le marché ; les ETF ESG stricts, qui en détiennent moins, ont mécaniquement fait moins bien. Sur une autre période, le classement peut s'inverser.
- **Corrélation n'est pas causalité.** Même un lien statistique entre sentiment et performance ne prouverait pas que l'un cause l'autre.
- **Le sentiment mesure le ton des titres, pas la réalité économique**, et seulement dans la presse anglophone gratuite.
- **Le sentiment ESG ne se compare pas au sentiment marché** : FinBERT classe beaucoup de titres ESG comme neutres (informatifs, sans enjeu financier explicite). On le compare donc à son propre historique.
- **Ce n'est pas un conseil en investissement.**

Le détail figure dans la page Méthodologie du site.

---

## 5. Expliquer le projet en entretien

**En une phrase.** « J'ai construit un tableau de bord automatique et gratuit qui compare chaque nuit la performance des ETF ESG au MSCI World, et qui mesure avec un modèle d'IA l'humeur de la presse financière pour tester, avec un protocole statistique fixé à l'avance, si elle est liée à cet écart de performance. »

**Les questions probables, et les réponses.**

- *« Les fonds ESG sous-performent-ils ? »* — Sur les trois dernières années, oui pour les approches strictes (SRI). Mais l'explication n'est pas celle qu'on entend souvent : ce n'est pas l'exclusion de l'énergie (moins d'un dixième de point), c'est surtout l'absence de cinq des sept géants technologiques américains, qui explique environ la moitié du retard de l'ETF SRI. C'est la conséquence d'un choix de portefeuille dans un marché donné, pas une loi.
- *« Comment mesurez-vous le sentiment ? »* — Avec FinBERT, un modèle de langage entraîné sur des phrases financières. Chaque titre reçoit une probabilité d'être positif, neutre ou négatif ; le solde de la journée est la part de titres positifs moins la part de négatifs, avec une marge d'erreur.
- *« Comment évitez-vous de trouver un faux résultat ? »* — Un seul test principal décidé avant les données, une correction de Holm pour les autres, un minimum de 60 jours, une « zone du hasard » affichée autour de la corrélation glissante, et une règle : la synthèse automatique ne cite que le test principal.
- *« Comment vérifiez-vous les données ? »* — Contrôles automatiques (cours figés, variations aberrantes, pics isolés) ; un vrai bug de Yahoo a été détecté ainsi (un cours en dollars à la place des euros, le 24/10/2025). Les performances ont été comparées à celles publiées par les émetteurs et par justETF (écarts de l'ordre de 0,1 point, expliqués par l'heure de valorisation).
- *« Quelles difficultés ? »* — Des sources gratuites qui disparaissent (Stooq, notes ESG de Yahoo), un ETF dont la cotation en euros est récente (raccordement avec la cotation en dollars), des flux de presse de qualité inégale (liste noire documentée de producteurs de contenus automatiques).
- *« Qu'est-ce que vous amélioreriez ? »* — Allonger l'historique de sentiment (les résultats statistiques arrivent à partir de fin décembre 2026), ajouter des sources de presse non anglophones, et tester d'autres modèles de sentiment en parallèle.

**Compétences mises en œuvre** : analyse financière (performance, risque, attribution sectorielle), statistiques (corrélation, test de Welch, tests multiples), traitement automatique du langage, programmation Python, automatisation (GitHub Actions), conception d'interface et rédaction méthodologique.

---

## 6. Vérifier que tout tourne

- **Tâches automatiques** : onglet [Actions](https://github.com/Gaaabbb444/contrepoint/actions) du dépôt. Une coche verte signifie que tout va bien. Une croix rouge signifie qu'une étape a échoué : GitHub envoie alors un e-mail, et le site garde ses dernières données valides.
- **Journal** : [data/journal_execution.csv](data/journal_execution.csv), avec une ligne par étape et par exécution.
- **État affiché par le site** : [docs/data/etat.json](docs/data/etat.json).
- **Alertes** : onglet [Issues](https://github.com/Gaaabbb444/contrepoint/issues) du dépôt.
- **Lancer une tâche à la main** : onglet Actions, choisir la tâche, puis « Run workflow ».
- **Mise en veille par GitHub** : GitHub suspend les tâches planifiées d'un dépôt sans activité pendant 60 jours. Les tâches se réactivent elles-mêmes chaque nuit ; si elles venaient malgré tout à s'arrêter, un bouton « Enable workflow » apparaît dans l'onglet Actions.

---

## 7. ⚠️ Mises à jour manuelles à faire

Certaines informations ne peuvent pas être récupérées automatiquement : elles sont relevées à la main dans [config/etf.yaml](config/etf.yaml), avec leur source et leur date (`verifie_le`). Le site affiche ces dates.

| Quoi | Fréquence conseillée | Où vérifier |
|---|---|---|
| **Notes MSCI ESG** (note AAA à CCC, score de qualité, percentile) | chaque trimestre | Fiche (« factsheet ») de chaque ETF iShares, section « ESG Metrics » |
| **Label ISR** | chaque trimestre | Liste officielle, mise à jour chaque mois : https://www.lelabelisr.fr/fonds-labellises/ |
| **Label Greenfin** | chaque semestre | https://www.ecologie.gouv.fr/politiques-publiques/label-greenfin |
| **Classification SFDR et frais** | chaque année | Fiche et prospectus de chaque ETF |

Après chaque vérification, mettre à jour la valeur et la date `verifie_le` (et `date` pour les notes MSCI).

**Note MSCI du MSCI World** : non publiée par iShares pour ce fonds, et l'outil de recherche public de MSCI est désormais réservé à ses clients (constaté le 17/10/2026). Le site affiche « Non publiée ». À revérifier à chaque mise à jour.

---

## 8. Travailler sur le projet depuis son ordinateur

Rien de ceci n'est nécessaire au fonctionnement du site. Les commandes s'exécutent dans un terminal ouvert dans le dossier du projet, sous Windows.

```
python -m venv .venv                                       # une seule fois : crée l'environnement Python
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest                         # vérifie les calculs (tests automatiques)
.venv\Scripts\python.exe -m pipeline.traitement_nuit       # télécharge et calcule (sans FinBERT)
.venv\Scripts\python.exe -m analyses.resume_performance    # affiche les performances dans le terminal
.venv\Scripts\python.exe -m pipeline.site                  # régénère la page Méthodologie
.venv\Scripts\python.exe -m http.server 8000 -d docs       # aperçu du site : http://localhost:8000
```

FinBERT (environ 400 Mo) n'est installé que sur GitHub ([requirements-sentiment.txt](requirements-sentiment.txt)).

Modifier la page Méthodologie : éditer [contenu/methodologie.md](contenu/methodologie.md) ; le site est mis à jour à la tâche de nuit suivante.

L'image d'aperçu (partage du lien) et les icônes se régénèrent avec `python outils/images_partage.py` (dépendances indiquées en tête du fichier).

---

## 9. Organisation des fichiers

```
config/          Paramètres : ETF suivis, flux de presse, choix de méthode
pipeline/        Programme Python (collecte, calculs, tests, synthèse)
tests/           Tests automatiques des calculs (pytest)
analyses/        Scripts d'étude ponctuels (vérifications, démonstrations)
data/            Données brutes conservées : titres notés, sentiment quotidien, journal
contenu/         Texte source de la page Méthodologie
docs/            Le site publié (GitHub Pages) et ses fichiers de données (docs/data/)
outils/          Outils ponctuels (image d'aperçu, icônes)
.github/         Tâches automatiques (GitHub Actions)
PLAN_ARCHITECTURE.md   Plan détaillé et décisions prises au fil du projet
```

---

## 10. Crédits et licences

- **Analyse de sentiment** : FinBERT (ProsusAI/finbert), © MIH AI B.V., licence CC BY-NC-SA 4.0 (usage non commercial) ; Araci (2019) ; Financial PhraseBank, Malo et al. (2014).
- **Données de marché** : Yahoo Finance (cours), Banque centrale européenne (change, €STR).
- **Polices** : Newsreader et IBM Plex Sans, licence SIL Open Font License 1.1, hébergées avec le site.
- **Presse** : seuls les titres, médias et dates sont conservés ; chaque titre affiché renvoie vers l'article d'origine.

Projet personnel à visée pédagogique. Les informations présentées ne constituent pas un conseil en investissement.
