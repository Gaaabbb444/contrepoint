# Méthodologie — texte source

*Ce fichier est la source rédactionnelle de la page « Méthodologie » du site (étape 5). Il est complété à chaque étape. Les chiffres cités sont datés ; le site affiche les valeurs du jour.*

---

## Performance des ETF

### Ce que l'on compare
Quatre ETF ESG, tous construits à partir du MSCI World, sont comparés à un ETF qui réplique le MSCI World lui-même. Trois sont de la même famille (iShares : mêmes frais de 0,20 %, même gestion, même domicile), pour que l'écart observé vienne de la méthode ESG et non des frais. Un cinquième, BNP Paribas Easy MSCI World SRI PAB (labellisé ISR, 0,25 % de frais), est présenté en complément.

### Comment
- **Rendement total** : tous les ETF sont capitalisants (les dividendes sont réinvestis dans le fonds) ; leur cours de bourse suffit donc à mesurer un rendement « dividendes réinvestis ».
- **Mêmes dates, même devise** : tous les cours sont en euros et seules les séances communes à tous les ETF sont retenues.
- **Mêmes horaires** : tous les ETF clôturent à 17 h 30 (Francfort, Paris, Amsterdam). Les comparaisons entre eux sont donc homogènes. En revanche, nos chiffres peuvent différer de quelques dixièmes de point de ceux publiés par les émetteurs, qui calculent sur la valeur liquidative arrêtée après la clôture de Wall Street (vérifié : écart de 0,1 point sur 3 et 5 ans pour l'ETF SRI).
- **Indicateurs** : performance cumulée ; performance annualisée (à partir de 3 ans) ; performance relative (ETF ESG − MSCI World, en points) ; volatilité annualisée (écart-type des variations quotidiennes × √252) ; perte maximale ; ratio de Sharpe (à partir d'1 an, avec le €STR de la BCE comme taux sans risque) ; écart de suivi (volatilité de la différence quotidienne avec le MSCI World).

### Contrôle des données
- **Cours erronés** : une séance est écartée si un seul ETF s'écarte de plus de 5 % du MSCI World puis revient le lendemain, alors que les autres ETF suivent le MSCI World. Un vrai choc de marché (comme début avril 2025) touche tous les ETF ensemble et n'est jamais écarté. Exemple réel détecté : le 24/10/2025, Yahoo Finance affichait pour un ETF coté en euros son cours en dollars.
- **Clôtures provisoires** : Yahoo publie parfois la clôture officielle avec plusieurs heures de retard. On utilise alors le dernier prix de la séance, signalé comme **provisoire** (astérisque), puis remplacé automatiquement par la clôture officielle dès sa publication. Tout l'historique est retéléchargé chaque nuit.

### Le cas de l'ETF Paris-Aligned (raccordement et taux de change)
Sa cotation en euros à Francfort n'existe que depuis le 25/08/2025. Avant cette date, on utilise sa cotation en dollars d'Amsterdam, convertie en euros au taux de référence de la BCE, et l'on « raccorde » les deux séries (seules les variations sont reprises).

Deux sources de bruit affectent cette partie ancienne :
1. **Le décalage horaire du taux de change** : le taux de la BCE est fixé vers 14 h 15, alors que l'ETF clôture à 17 h 30. Si l'euro bouge entre ces deux heures, la variation en euros d'une séance est légèrement faussée, puis corrigée le lendemain. Sur des périodes longues, ces erreurs se compensent et sont négligeables ; sur les variations quotidiennes, elles ajoutent du bruit.
2. **Le peu d'échanges** sur la cotation d'Amsterdam (cours inchangé une séance sur quinze environ).

Mesure (sur 14 mois où les deux cotations existent) : écart quotidien moyen de 0,28 point, écart de suivi gonflé à 5,9 % contre 2,0 % en direct, mais seulement 0,5 point d'écart sur la performance cumulée. C'est pourquoi la **performance** de cet ETF est fiable sur toutes les périodes, alors que ses **indicateurs de risque quotidiens** (volatilité, écart de suivi, Sharpe) et la mesure de l'effet sectoriel sont signalés « fiabilité réduite » sur 3 et 5 ans.

---

## Pourquoi les approches ESG strictes ont-elles fait moins bien ?

*Données : composition officielle des fonds iShares au 15/10/2026 ; mesure sur les séances du 16/10/2023 au 15/10/2026.*

Une idée répandue veut que les fonds ESG sous-performent parce qu'ils excluent le secteur de l'énergie. Les données racontent une histoire différente.

**1. Ce n'est pas d'abord une question de secteur, mais de quelques très grandes entreprises.** L'ETF SRI contient autant de technologie que le MSCI World (environ 30 %). Mais il ne détient, parmi les sept géants technologiques américains, que Nvidia et Tesla : ni Apple, ni Microsoft, ni Amazon, ni Alphabet, ni Meta, écartés par sa méthode de sélection « best-in-class ». Ces sept valeurs pèsent environ 25 % du MSCI World, contre 12 % de l'ETF SRI.

**2. L'énergie a peu compté sur la période.** Les ETF ESG détiennent peu ou pas d'énergie (0 % pour le SRI, contre 4,3 % pour le MSCI World), mais ce secteur a évolué à peu près comme le marché sur ces trois années : ce pari a pesé pour moins d'un dixième de point.

**3. Mesure.** On compare, séance par séance, l'écart de performance de chaque ETF ESG avec le MSCI World, à l'écart entre un panier des sept géants technologiques et le MSCI World, et à l'écart entre le secteur de l'énergie et le MSCI World (régression linéaire). Sur trois ans :
- **ETF SRI** : environ **la moitié** de son retard s'explique par la sous-pondération des géants technologiques ; l'autre moitié vient de ses autres choix de valeurs.
- **BNP Easy SRI PAB** : environ **70 %** de son retard s'explique de la même façon.
- **ETF Screened** (exclusions légères) : sa légère avance vient de ce qu'en excluant quelques secteurs, il **surpondère** mécaniquement ces géants.

**4. Limites.** La composition utilisée est celle d'aujourd'hui, pas celle d'il y a trois ans. Le panier des sept géants est pondéré selon leurs poids actuels. La régression mesure une association statistique, pas une causalité. Pour l'ETF Paris-Aligned, la mesure est peu fiable (données quotidiennes bruitées avant août 2025, voir plus haut).

**5. Le résultat dépend de la période (rappel affiché sur le site).** De 2023 à 2026, les géants technologiques américains ont porté le marché : tout indice qui les sous-pondère a mécaniquement fait moins bien. Sur une autre période — un recul de ces valeurs, ou une hausse de l'énergie — le classement peut s'inverser. La sous-performance observée n'est donc pas une « loi » de l'investissement responsable, mais la conséquence de ses choix de portefeuille dans un marché donné.


---

## Sentiment de l'actualité

### Sources
Deux groupes de flux RSS gratuits, en anglais : la presse financière et économique générale (CNBC, Wall Street Journal, Financial Times, Bloomberg, BBC, The Guardian, New York Times, Euronews, Deutsche Welle) et la presse spécialisée en finance durable (ESG Today, ESG Dive, ESG News, Responsible Investor, ImpactAlpha, Trellis, FT Moral Money, etc.), complétée par deux recherches Google Actualités (« ESG investing », « sustainable finance »). La liste complète, et les flux écartés avec leur raison, figurent dans `config/flux_rss.yaml`.

Les flux sont relevés toutes les 3 heures : beaucoup ne gardent que leurs 10 à 30 derniers articles, et un relevé quotidien en manquerait la majorité.

### Traitement
- Seuls le **titre** et le **début du résumé** sont analysés ; l'article complet n'est jamais récupéré.
- **Doublons** : un article est ignoré s'il a le même lien, ou un titre quasi identique (similarité ≥ 90 %), qu'un article déjà retenu dans le même groupe au cours des 3 derniers jours. Quand un article apparaît à la fois dans un flux direct et dans Google Actualités, c'est la version du média lui-même qui est gardée.
- **Droit d'auteur** : le résumé sert uniquement au calcul et n'est jamais enregistré. Le dépôt public ne conserve que le titre, la source, le lien, la date et le score.

### Le modèle : FinBERT
FinBERT (ProsusAI/finbert) est un modèle de langage de type BERT, spécialisé en finance : il a été entraîné sur des textes financiers (corpus Reuters TRC2), puis sur des phrases de presse financière annotées à la main comme positives, négatives ou neutres (Financial PhraseBank, Malo et al., 2014). Pour chaque texte, il donne trois probabilités ; on retient la plus élevée. Chaque article compte autant.

Version figée (Hugging Face, commit `0bc2ac10`, 12/10/2026) pour que les résultats restent comparables dans le temps. Licence CC BY-NC-SA 4.0, © MIH AI B.V. (Prosus) : usage non commercial, avec citation. Références : Araci (2019), *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models* ; Malo et al. (2014), *Good debt or bad debt*.

Pourquoi l'anglais : aucun modèle de sentiment financier en français n'a fait l'objet d'une validation comparable.

### Indicateurs d'une journée
- **Répartition** positif / neutre / négatif, en %.
- **Solde net** = % positifs − % négatifs (de −100 à +100).
- **Étiquette du jour** : le seuil n'est pas fixe, il dépend du nombre d'articles. C'est la **marge d'erreur statistique à 95 %** du solde : 1,96 × √((p + q − (p − q)²) / n), où *n* est le nombre d'articles, *p* la part de positifs et *q* la part de négatifs. L'étiquette est « positif » si le solde dépasse +marge, « négatif » s'il est inférieur à −marge, « neutre » sinon (impossible à distinguer du hasard de l'échantillon). Exemple : avec 30 % de positifs et 30 % de négatifs, la marge vaut ±9,6 points pour 250 articles, mais ±19,6 pour 60. Avec peu d'articles, il faut donc un écart beaucoup plus net pour conclure.
- **Signal insuffisant** : moins de 30 articles, ou marge d'erreur supérieure à 25 points.
- **Limite** : la formule suppose des articles indépendants ; or plusieurs médias couvrent souvent le même événement. Le dédoublonnage réduit ce problème sans le supprimer : la vraie marge est un peu plus large.

### La « journée » de sentiment
Une journée de sentiment couvre les articles publiés **de la clôture de la séance de bourse précédente (17 h 30, heure de Paris) jusqu'à la clôture de la séance du jour**, d'après le calendrier officiel de Xetra (y compris ses clôtures anticipées). Les articles publiés le week-end ou un jour férié sont rattachés à la séance suivante : la journée du lundi va du vendredi 17 h 30 au lundi 17 h 30.

**Pourquoi ce choix.** La performance d'une séance se mesure de la clôture de la veille à celle du jour : la journée de sentiment couvre exactement la même plage.
- Le **test du même jour** (sentiment J et performance J) ne permet aucune interprétation de sens : les articles peuvent faire bouger le marché, mais aussi simplement **commenter** un marché qui a bougé (« les marchés chutent… »).
- Le **test de décalage** (sentiment J et performance J+1) élimine cet effet : tous les articles de la journée J sont publiés **avant** le début de la séance J+1 ; un article ne peut pas commenter une variation qui n'a pas encore eu lieu. Il reste soumis à la règle « corrélation n'est pas causalité » : un troisième facteur peut agir sur les deux.
- **Limite connue** : Wall Street reste ouverte jusqu'à 22 h (heure de Paris). Les articles publiés en soirée sur la séance américaine tombent dans la journée suivante ; ils ne faussent pas le test de décalage, car ils restent antérieurs à la clôture suivante.

Un article sans date de publication reçoit l'heure de sa collecte (à 3 heures près) ; il compte dans l'indicateur du jour mais est exclu des tests statistiques.

### Contrôle externe : GDELT
GDELT, projet universitaire gratuit, publie la « tonalité » moyenne de la presse mondiale, calculée en comptant les mots positifs et négatifs d'un dictionnaire sur les articles complets. C'est une méthode très différente de FinBERT ; les deux séries sont affichées séparément et ne se comparent qu'en tendance. Le service refuse souvent les requêtes : cette série peut donc présenter des trous.
