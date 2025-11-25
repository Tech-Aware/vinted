# Assistant d'annonces Vinted

Application de bureau légère construite avec [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
pour générer rapidement des titres et descriptions Vinted à partir de photos
et de commentaires utilisateur. L'outil est pensé pour être lancé aussi bien
sous Windows que sous Chromebook (via l'environnement Linux).

## Fonctionnalités

- Sélection de plusieurs photos avec prévisualisation vignette.
- Zone de saisie « Commentaire » (prioritaire) avec rappel de séparer plusieurs informations par des virgules.
- Génération automatique d'un titre et d'une description structurée grâce à
  l'API OpenAI Vision (GPT-4o).
- Résultats affichés dans deux zones éditables prêtes au copier/coller.
- Gestion des templates d'annonces (fournit un modèle Levi's femme par défaut).
- Onglet « Réponses aux clients » : scénarios prêts à l'emploi (favoris, contre-offre,
  remerciements, suivi d'envoi...) avec champs dynamiques selon le cas.

## Pré-requis

- Python 3.8 ou plus récent (version 64 bits recommandée sur Windows).
- Accès à l'API OpenAI avec un modèle vision (par exemple `gpt-4o-mini`).
- Clé API disponible via la variable d'environnement `OPENAI_API_KEY`.

## Installation

1. Créez un environnement virtuel et activez-le.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell : .venv\Scripts\Activate.ps1
   ```
2. Installez les dépendances Python.
   ```bash
   pip install -r requirements.txt
   ```
3. (Optionnel) Définissez un modèle vision spécifique (par défaut l'application utilise `gpt-4o`).
   ```bash
   export OPENAI_VISION_MODEL=gpt-4.1
   ```

## Lancement

Exécutez l'application en module afin que les imports relatifs fonctionnent :
```bash
python -m app.main
```

L'interface s'ouvre avec trois zones principales :

1. **Prévisualisation des images** : ajoutez vos photos via « Ajouter des photos ».
2. **Commentaires** : précisez les défauts ou informations complémentaires.
3. **Résultats** : titre et description générés, modifiables directement.

L'onglet « Réponses aux clients » déroule le flux suivant : sélection du type
d'article, choix d'un type de message (Remercier, Inciter, Négocier, Informer),
puis d'un scénario associé (achat, avis, favoris, lot, prix ferme, suivi, etc.).
Seules les négociations affichent des champs :
- « Offre du client » + « Votre proposition » pour proposer un prix plus haut ;
- « Offre du client » + « Prix ferme » pour refuser de négocier.
Le bouton « Générer la réponse » n'est affiché qu'en dernier.
Vous obtenez un texte prêt à coller dans Vinted et copiable en un clic.
Chaque réponse est rédigée en français avec un ton courtois, professionnel,
fun et convivial, en intégrant au moins deux émojis/smileys et en restant
concise (2 à 6 phrases).

Cliquez sur « Analyser » pour envoyer les photos et commentaires à GPT. Les
données transitent en base64 dans la requête OpenAI. Une fois la réponse
reçue, les champs sont remplis avec le template Levi's.

## Personnalisation des templates

Les templates sont déclarés dans `app/backend/templates.py`. Chaque entrée
comprend :

- `name` : identifiant affiché dans la liste déroulante.
- `description` : texte descriptif (pour usage futur dans l'UI).
- `prompt` : instructions complètes envoyées au modèle.

Ajoutez vos propres structures en enrichissant le dictionnaire `_templates`.

### Templates fournis par défaut

- `template-jean-levis-femme` : gabarit historique pour les jeans Levi’s (SKU `JLF-n`).
- `template-pull-tommy-femme` : descriptions détaillées des pulls et gilets Tommy Hilfiger (SKU `PTF-n`).
- `template-polaire-outdoor` : polaires et pulls techniques The North Face (`PTNF-n`) ou Columbia (`PC-n`) avec règle métier « sauf commentaire contraire → 100 % polyester par défaut » et hashtags outdoor dédiés.

## Intégration OpenAI

La classe `ListingGenerator` (fichier `app/backend/gpt_client.py`) encapsule
l'appel à `openai`. L'initialisation de la librairie est paresseuse afin de
permettre l'ouverture de l'interface même sans clé configurée. Toute erreur
renvoyée par l'API est affichée dans la barre de statut de l'application.

### Overrides utilisateur et nettoyage des tailles

Pour limiter les incohérences de tailles générées par le modèle vision, le
`ListingGenerator` applique deux garde-fous importants avant le rendu du titre
et de la description :

- **Overrides explicites** : lorsqu'un commentaire contient une taille FR
  (ex. « taille FR40 »), cette valeur est injectée dans les champs structurés
  et neutralise les tailles US W/L pour éviter toute conversion automatique.
  Les autres éléments clés du commentaire (couleur, marque, défauts) sont
  propagés de la même manière.
- **Purge des tailles halluciné es** : si aucune étiquette n'est visible sur les
  photos (`size_label_visible=False`) et qu'aucun override n'est fourni, les
  tailles FR ou US renvoyées par le modèle sont supprimées pour respecter la
  consigne « ne rien inventer ». Les mesures objectives (tour de taille en cm,
  etc.) restent intactes.

Deux tests d'intégration (`tests/test_gpt_client_overrides.py`) couvrent ces
cas : propagation d'une taille FR saisie manuellement et suppression des tailles
inventées lorsqu'aucune étiquette n'est lisible.

## Déploiement sur Chromebook

1. Activez Linux (Crostini) et installez un interpréteur Python récent (3.8 ou
   supérieur) depuis le terminal Linux.
2. Rendez les nouveaux scripts exécutables :

   ```bash
   chmod +x scripts/crostini/*.sh
   ```

3. Préparez l'environnement virtuel et installez les dépendances via :

   ```bash
   ./scripts/crostini/setup.sh
   ```

   Le script accepte un argument `--python /chemin/vers/python` si vous devez
   cibler un interpréteur spécifique. À la fin, vérifiez que la variable
   d'environnement `OPENAI_API_KEY` est exportée dans votre session Crostini :

   ```bash
   export OPENAI_API_KEY="votre_cle"
   ```

4. Lancez l'application depuis Crostini avec :

   ```bash
   ./scripts/crostini/run.sh
   ```

   Le script active automatiquement l'environnement virtuel `.venv` et relaie
   les arguments supplémentaires passés à `run.sh` vers `python -m app.main`.

## Déploiement sur Windows

- Installez Python 3.8 (ou plus récent) depuis python.org.
- Ouvrez PowerShell, créez l'environnement virtuel et installez les dépendances.
- Lancement identique : `python -m app.main`.

### Créer un binaire standalone (Windows 7/8/10/11)

Pour cibler des machines ne supportant pas le format MSIX (Windows 7/8), un
script PowerShell est disponible dans `packaging/windows/standalone/` :

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/standalone/build.ps1 -PythonPath "C:\\Python38\\python.exe"
```

La commande génère l'exécutable via PyInstaller puis produit
`dist/VintedAssistant-win64.zip`, prêt à être distribué. Décompressez l'archive
sur la machine cible et lancez `VintedAssistant.exe`.

### Créer un package MSIX signé

Un exemple complet de chaîne de packaging (PyInstaller → MakeAppx → signature)
est disponible dans `packaging/windows/msix/`. Le dossier contient :

- un fichier `vinted_msix.spec` pour générer l'exécutable autonome avec PyInstaller ;
- un manifeste `AppxManifest.xml` à personnaliser avec votre identité éditeur ;
- un script PowerShell `SignMsix.ps1` pour signer le package `*.msix` avec `signtool` ;
- une documentation pas-à-pas (`README.md`).

Reportez-vous à cette documentation pour adapter l'identité, ajouter vos logos
et signer le package avec votre certificat de signature de code.

## Limitations connues

- Une connexion Internet est nécessaire pour l'appel OpenAI.
- L'interface ne redimensionne pas encore dynamiquement les vignettes.
- Aucun cache n'est implémenté pour réutiliser des analyses précédentes.

## Licence

- **Code source** : distribué sous double licence [Apache License 2.0](LICENSE)
  *ou* [MIT](LICENSE-MIT). Vous êtes libre de choisir la licence la mieux
  adaptée à votre usage.
- **Ressources non-code** (images, données, templates, documents non techniques) :
  sous licence [Creative Commons Attribution-NonCommercial 4.0 International](LICENSE-RESOURCES).

Voir les fichiers de licence correspondants pour les termes complets et les
conditions détaillées.
