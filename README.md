# Assistant d'annonces Vinted

Application de bureau légère construite avec [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
pour générer rapidement des titres et descriptions Vinted à partir de photos
et de commentaires utilisateur. L'outil est pensé pour être lancé aussi bien
sous Windows que sous Chromebook (via l'environnement Linux).

## Fonctionnalités

- Sélection de plusieurs photos avec prévisualisation vignette.
- Zone de saisie des tâches et défauts détectés par l'utilisateur.
- Génération automatique d'un titre et d'une description structurée grâce à
  l'API OpenAI Vision (GPT-4o).
- Résultats affichés dans deux zones éditables prêtes au copier/coller.
- Gestion des templates d'annonces (fournit un modèle Levi's femme par défaut).

## Pré-requis

- Python 3.8 ou plus récent (version 64 bits recommandée sur Windows).
- Accès à l'API OpenAI avec un modèle vision (par exemple `gpt-5-mini`).
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
3. (Optionnel) Définissez un modèle vision spécifique (par défaut l'application utilise `gpt-5-mini`).
   ```bash
   export OPENAI_VISION_MODEL=gpt-5-mini
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
