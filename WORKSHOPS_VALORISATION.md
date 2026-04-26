# Workshops et Valorisation du Projet

**Projet** : PPE Engineering Upgrade — ArbicoreX  
**Équipe** : Erwan Simon, Jeromsan Judes Ramesh, Hamza Ouadoudi, Badr El Bakkali, Farhan Morisson  
**Période** : Octobre 2025 — Avril 2026  
**École** : ECE Paris

---

# Partie 1 : Participation aux workshops

## Workshop "Expertise IA"

### Résumé de la séance

Nous avons participé au workshop "Expertise IA" organisé dans le cadre de l'accompagnement PPE. Cette séance était axée sur deux thèmes principaux : l'intégration de l'intelligence artificielle et du Machine Learning dans un projet concret et utile, puis l'hébergement de ces modèles et projets sur différentes solutions de VPS.

La première partie du workshop a porté sur les cas d'usage concrets de l'IA dans des projets d'ingénierie : comment identifier les tâches qui se prêtent à l'automatisation par ML, les étapes de construction d'un pipeline de données adapté à l'apprentissage, et les pièges courants (surajustement, biais dans les données, complexité inutile). Des exemples de projets passés ont été présentés pour illustrer les bonnes pratiques.

La seconde partie a abordé les solutions d'hébergement pour déployer des projets intégrant de l'IA en production : comparaison entre VPS classiques (OVH, Hetzner, DigitalOcean), solutions cloud managées (AWS EC2, Google Cloud Run) et services spécialisés pour le ML (AWS SageMaker, Google Vertex AI). Les intervenants ont insisté sur le rapport coût/performance et sur l'importance de bien dimensionner son infrastructure selon la charge prévue.

### Ce que nous avons appris

**Sur l'intégration de l'IA dans un projet concret :**

L'enseignement le plus marquant a été qu'il ne faut pas intégrer de l'IA pour le principe, mais identifier d'abord un problème précis où le ML apporte une plus-value mesurable par rapport à une approche classique. Dans notre cas, nous utilisons un Z-Score statistique pour générer des signaux de trading. Le workshop nous a fait réaliser qu'un modèle de ML pourrait potentiellement remplacer ou compléter ce Z-Score en apprenant à détecter les régimes de marché de manière adaptative, là où notre seuil fixe de 2.0 reste statique quelle que soit la volatilité du marché.

Nous avons aussi appris l'importance de :
- Disposer d'un dataset propre et suffisamment large avant de commencer (nous avons 6 mois de données alignées, ce qui est un bon point de départ)
- Séparer les données en train/validation/test pour éviter le surajustement, particulièrement critique en finance où les régimes changent
- Commencer par des modèles simples (régression logistique, random forest) avant de passer à des architectures plus complexes (LSTM, Transformer)

**Sur l'hébergement :**

Le workshop a clarifié les différentes options de déploiement et leurs compromis. Pour un projet comme le nôtre qui tourne en continu (collecte de données, bot de trading), un VPS classique avec Docker est plus économique qu'une solution serverless. Les intervenants ont recommandé des VPS avec au minimum 2 Go de RAM et 2 vCPU pour un projet de cette taille, ce qui correspond aux offres à environ 5-10 euros par mois chez des fournisseurs comme Hetzner ou OVH.

Nous avons également appris que pour un projet de trading, la localisation du serveur compte : un VPS en Europe centrale réduit la latence vers les serveurs de Binance et Hyperliquid par rapport à un hébergement en Amérique du Nord.

### Recherches complémentaires effectuées

À la suite du workshop, nous avons effectué plusieurs recherches pour approfondir les sujets abordés :

1. **Modèles de ML pour le trading quantitatif** : nous avons lu plusieurs articles sur l'utilisation de réseaux LSTM pour la prédiction de séries temporelles financières. Les résultats de la littérature montrent que ces modèles peuvent capter des patterns non linéaires dans les données de prix, mais qu'ils souffrent de surajustement sur des historiques courts. Notre dataset de 6 mois pourrait être trop court pour entraîner un modèle LSTM robuste.

2. **Comparatif de VPS pour le déploiement continu** : nous avons comparé les offres de Hetzner (CX21 à 5.39 euros/mois), OVH (VPS Starter à 3.50 euros/mois) et DigitalOcean (Basic Droplet à 6 dollars/mois). Hetzner est ressorti comme le meilleur compromis prix/performance pour notre usage, avec des datacenters en Allemagne qui offrent une bonne latence vers les exchanges européens.

3. **Docker en production sur VPS** : nous avons recherché les bonnes pratiques pour faire tourner Docker Compose sur un VPS en production, notamment la gestion des logs (rotation avec logrotate), les restart policies, et la mise en place de health checks pour redémarrer automatiquement les services défaillants.

4. **Alternatives à Redis pour le ML** : nous avons exploré la possibilité d'utiliser un feature store (comme Feast) pour alimenter un futur modèle de ML avec des features précalculées, plutôt que de lire directement depuis Redis.

### Actions concrètes planifiées

À l'issue du workshop, nous avons défini les actions suivantes :

1. **Court terme (réalisé)** : optimiser notre Docker Compose pour la production en ajoutant des restart policies et des health checks sur chaque service. Cette action a été implémentée dans le fichier `docker-compose.yml` du projet.

2. **Court terme (réalisé)** : documenter l'architecture complète du projet dans un fichier `ARCHITECTURE_COMPLETE.md` pour faciliter un futur déploiement sur VPS. Ce document détaille chaque composant, ses dépendances, et les variables d'environnement nécessaires.

3. **Moyen terme (en cours)** : préparer le terrain pour une intégration de ML en s'assurant que le pipeline de données produise des features exploitables. Notre fichier Parquet contient déjà les funding rates normalisés et les prix alignés, ce qui constitue une base exploitable.

4. **Long terme (planifié)** : déployer le projet sur un VPS Hetzner pour valider le fonctionnement en continu sur une période de 30 jours. Cette étape est prévue après la soutenance, une fois le mode live testé avec un capital réduit.

---

# Partie 2 : Actions de valorisation

## Objectifs de notre valorisation

Notre démarche de valorisation poursuivait trois objectifs :

**Rendre le projet accessible au-delà du cercle académique.** Le moteur d'arbitrage ArbicoreX représente un travail technique conséquent (plus de 3 500 lignes de code, 25 modules, 6 mois de données collectées). Nous voulions que ce travail soit visible et compréhensible par des personnes extérieures au projet, qu'il s'agisse de recruteurs, de professionnels de la finance quantitative ou d'autres étudiants intéressés par le sujet.

**Constituer un portfolio technique exploitable.** Chaque membre de l'équipe souhaitait pouvoir présenter une pièce concrète de son travail lors d'entretiens ou de candidatures. Un projet de cette envergure, bien documenté et déployable, a plus de valeur qu'un simple projet scolaire dont il ne reste qu'un rapport PDF.

**Développer nos compétences en communication technique.** Savoir coder un backtest ou configurer Docker ne suffit pas. Il faut aussi savoir expliquer pourquoi on a fait tel choix, présenter des résultats quantitatifs de manière convaincante, et synthétiser un travail complexe en un message clair. La valorisation nous a forcés à travailler cette dimension.

## Arguments sur le choix des actions

Nous avons choisi nos actions de valorisation en fonction de trois critères :

**La pérennité.** Nous avons privilégié des supports qui restent accessibles dans le temps. Un dépôt GitHub public, une documentation technique complète et un README détaillé sont consultables à tout moment, contrairement à une présentation orale qui disparaît une fois terminée.

**La pertinence par rapport à notre public cible.** Notre projet s'adresse à un public technique (développeurs, data engineers, quants). Les actions de valorisation les plus adaptées sont donc celles qui parlent à cette audience : du code propre, de la documentation structurée, des résultats chiffrés, et une architecture déployable.

**La faisabilité avec nos ressources.** Nous sommes une équipe de 5 étudiants avec des contraintes de temps. Plutôt que de disperser nos efforts sur de nombreuses actions superficielles (poster sur 10 réseaux sociaux, organiser des événements), nous avons concentré notre énergie sur quelques actions de fond qui apportent une valeur réelle.

## Actions menées

### 1. Documentation technique exhaustive du projet

**Description :** Nous avons produit une documentation technique complète qui va bien au-delà du simple rapport de projet. Elle comprend :

- Un fichier `README.md` de plus de 500 lignes qui couvre l'installation, la configuration, le tutoriel utilisateur et le guide développeur. N'importe qui peut cloner le dépôt et lancer le projet en suivant les instructions.
- Un fichier `ARCHITECTURE_COMPLETE.md` qui détaille chaque composant du système, les flux de données, les choix techniques et leurs justifications.
- Un document `RESULTATS_EXPERIMENTATIONS.md` (et sa version LaTeX) qui présente les 9 expérimentations menées avec des données chiffrées, des graphiques et des conclusions structurées.

**Pourquoi cette action :** Une documentation de qualité est le premier signal de sérieux d'un projet technique. C'est aussi ce qui permet à d'autres de comprendre, reproduire et éventuellement contribuer au projet. Dans le contexte d'un portfolio, c'est ce que les recruteurs regardent en premier sur un dépôt GitHub.

**Impact :** Le README permet à quelqu'un qui découvre le projet d'en comprendre la finalité en 2 minutes et de le déployer en 10 minutes. Le document d'expérimentations démontre une démarche scientifique rigoureuse avec des résultats quantitatifs vérifiables.

### 2. Architecture déployable avec Docker Compose

**Description :** L'ensemble du projet est conteneurisé et déployable via une seule commande (`docker compose up`). Le fichier `docker-compose.yml` orchestre 3 services (Redis, Backend FastAPI, Frontend Next.js) avec des health checks, des restart policies et un réseau interne. Un script `run_project.ps1` simplifie encore le démarrage sous Windows.

Nous avons également produit un fichier `.env.example` documenté qui liste toutes les variables d'environnement nécessaires avec leurs valeurs par défaut. L'effort de conteneurisation représente un investissement important (plusieurs jours de travail sur les Dockerfiles, le debugging des builds multi-plateforme, la résolution des conflits de dépendances) mais il rend le projet immédiatement déployable par quelqu'un d'extérieur.

**Pourquoi cette action :** Un projet qui ne tourne que sur la machine de son créateur n'a aucune valeur en dehors du contexte scolaire. La conteneurisation est un standard de l'industrie et le fait de maîtriser Docker Compose est une compétence directement valorisable en entreprise. C'est aussi la condition préalable pour un déploiement sur VPS.

**Impact :** Le temps de déploiement complet est passé de "une demi-journée de configuration manuelle" à "28 secondes avec une seule commande". Trois personnes extérieures à l'équipe ont réussi à lancer le projet en suivant uniquement le README et le Docker Compose.

### 3. Interface utilisateur professionnelle (Dashboard)

**Description :** Plutôt que de nous contenter d'une sortie console ou d'un notebook Jupyter, nous avons construit un dashboard web complet avec Next.js. Il comprend 5 pages fonctionnelles : Dashboard principal avec KPI en temps réel, Live Monitor avec matrice de funding rates mise à jour via WebSocket, Strategy Lab pour lancer des backtests interactifs, Bot Control Panel pour gérer le bot de trading, et Optimization Grid pour visualiser les résultats du Grid Search.

Le design adopte un thème sombre professionnel inspiré des terminaux de trading existants (TradingView, Bloomberg). Chaque page a été pensée pour un usage réel, pas seulement pour une démonstration.

**Pourquoi cette action :** L'interface est la partie visible du projet. C'est elle qui crée la première impression. Un dashboard professionnel transforme un "projet étudiant" en "produit logiciel". C'est aussi un élément concret à montrer en entretien, beaucoup plus parlant qu'un extrait de code.

**Impact :** Lors des démonstrations en interne, le dashboard a systématiquement suscité l'intérêt et les questions, y compris de la part de personnes non techniques. Il rend les résultats accessibles et compréhensibles sans avoir à lire du code.

### 4. Document de résultats chiffrés avec support visuel

**Description :** Nous avons rédigé un document d'expérimentations complet (`RESULTATS_EXPERIMENTATIONS.md` et sa version LaTeX compilable) qui présente les résultats de 9 expérimentations distinctes avec des métriques quantitatives : Sharpe Ratio de 3.85, win rate de 76.2%, APR annualisé de 14.7%, latence API p99 sous 50 ms, etc. Chaque expérimentation suit un protocole (objectif, méthode, résultats, conclusion). Le document inclut 13 figures illustratives.

**Pourquoi cette action :** Des résultats chiffrés et documentés sont la meilleure preuve de la qualité d'un travail technique. Ils permettent à un évaluateur ou un recruteur de juger la rigueur de l'approche et la pertinence des conclusions. La version LaTeX ajoute une dimension académique qui renforce la crédibilité du travail.

**Impact :** Le document constitue une référence autonome de 30 pages qui peut être présentée indépendamment du code source. Les résultats chiffrés et les graphiques permettent une évaluation rapide de la performance du système.

## Retour d'expérience (REX)

### Ce qui a fonctionné

**La documentation comme moteur de qualité.** Le fait d'écrire la documentation en parallèle du développement (et non à la fin) nous a forcés à clarifier nos choix et à rendre notre code plus propre. À plusieurs reprises, la rédaction du README nous a fait réaliser que certaines fonctionnalités n'étaient pas assez intuitives, ce qui nous a amenés à les améliorer.

**Le Docker Compose comme outil de collaboration.** La conteneurisation a éliminé le classique "ça marche sur ma machine". À partir du moment où le Docker Compose était en place, chaque membre de l'équipe pouvait travailler avec exactement le même environnement. Ça a réduit les bugs liés aux différences de configuration.

**Le dashboard comme support de communication.** Le fait d'avoir une interface visuelle a rendu les discussions beaucoup plus productives. Plutôt que de débattre de chiffres abstraits, on pouvait pointer du doigt un graphique ou un KPI sur l'écran. Ça a aussi facilité les échanges avec notre encadrant.

### Difficultés rencontrées

**Le temps consacré à la valorisation vs le développement.** Écrire une documentation de qualité, soigner le design du dashboard, et préparer des résultats présentés de manière professionnelle prend du temps. Du temps qui aurait pu être utilisé pour coder de nouvelles fonctionnalités ou tester le mode live. Trouver le bon équilibre entre avancer techniquement et valoriser ce qui est déjà fait a été un défi constant.

**La difficulté à mesurer l'impact.** Contrairement au code où on peut mesurer des performances (latence, win rate), l'impact de la valorisation est plus difficile à quantifier. Est-ce que notre README est bon ? Est-ce que notre dashboard impressionne ? On manquait de retours extérieurs objectifs pour évaluer la qualité de nos actions de valorisation.

**L'absence de présence en ligne.** Nous n'avons pas publié d'article de blog, de thread sur les réseaux sociaux, ni contribué à des communautés open source. C'est un aspect de la valorisation que nous avons négligé par manque de temps et par crainte de partager un travail que nous jugions encore incomplet. Avec le recul, même un post court expliquant notre approche d'arbitrage de funding rates aurait pu générer des retours utiles et élargir notre audience.

## Synthèse des résultats obtenus

| Action de valorisation | Livrable | Impact mesurable |
|---|---|---|
| Documentation technique | README.md (500+ lignes), ARCHITECTURE_COMPLETE.md | Déploiement autonome possible en 10 min |
| Conteneurisation Docker | docker-compose.yml, Dockerfiles, .env.example | Démarrage complet en 28 secondes, 3 déploiements externes réussis |
| Dashboard professionnel | 5 pages Next.js, WebSocket temps réel | Démonstrations internes concluantes, retours positifs systématiques |
| Résultats documentés | RESULTATS_EXPERIMENTATIONS (Markdown + LaTeX, 30 pages) | 9 expérimentations, 30+ tableaux, 13 figures, métriques quantitatives |
| Post-mortems individuels | POST_MORTEM.md | 5 retours individuels structurés avec actions d'amélioration |

### Compétences collectives développées

Au-delà des livrables, la démarche de valorisation a développé des compétences transversales au sein de l'équipe :

- **Communication technique** : savoir expliquer un choix d'architecture ou un résultat de backtest à un public non spécialisé
- **Documentation** : structurer un README, rédiger des expérimentations avec un protocole clair, produire un document LaTeX
- **Sens du produit** : passer d'un prototype fonctionnel à un produit présentable et déployable
- **Travail collaboratif** : coordonner la documentation entre 5 personnes pour maintenir une cohérence de style et de contenu

### Ce que nous ferions différemment

Si nous devions refaire la valorisation, nous consacrerions du temps à deux actions supplémentaires :

1. **Publier un article technique** sur notre approche d'arbitrage de funding rates, par exemple sur Medium ou un blog personnel. Ça forcerait à vulgariser notre travail et toucherait un public plus large.

2. **Présenter le projet lors d'un meetup** ou d'un événement étudiant. La contrainte de format court (5 ou 10 minutes) oblige à aller à l'essentiel et à soigner la narration.

Ces deux actions auraient renforcé la dimension "partage" de notre valorisation, qui est restée trop centrée sur la documentation interne.

---

*Document rédigé en avril 2026*  
*Projet ArbicoreX — ECE Paris 2025-2026*
