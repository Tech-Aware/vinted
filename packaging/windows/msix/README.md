# Chaîne de packaging MSIX

Ce dossier fournit un exemple de chaîne de construction pour livrer et signer
l'assistant Vinted sous forme de package MSIX. Les commandes sont à exécuter
sur un poste Windows disposant :

- de Python 3.8+ et `pip` ;
- de [PyInstaller](https://pyinstaller.org/en/stable/) (`pip install pyinstaller`);
- du [Windows App SDK](https://developer.microsoft.com/fr-fr/windows/downloads/windows-sdk/)
  incluant `makeappx.exe` et `signtool.exe` ;
- du [MSIX Packaging Tool](https://learn.microsoft.com/windows/msix/)
  (optionnel mais utile pour tester le package).

> ⚠️ Remplacez systématiquement les valeurs d'exemple (nom du publisher,
> certificats, logos) par vos propres éléments avant diffusion.

> ℹ️ Le format MSIX requiert Windows 10 build 19041 ou ultérieur. Pour les
> versions plus anciennes (Windows 7/8), utilisez le packaging standalone décrit
> dans `packaging/windows/standalone/`.

## 1. Générer l'exécutable autonome

1. Clonez le dépôt et installez les dépendances.
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install pyinstaller
   ```
2. Depuis la racine du dépôt, exécutez PyInstaller avec le fichier spec fourni :
   ```powershell
   pyinstaller packaging/windows/msix/vinted_msix.spec --noconfirm --clean
   ```
   L'exécutable et ses dépendances sont générés dans `dist/VintedAssistant/`.

## 2. Préparer les assets MSIX

- Copiez vos logos dans `packaging/windows/msix/Assets/` en respectant les noms
  référencés dans `AppxManifest.xml` (`StoreLogo`, `Square150x150Logo`,
  `Square44x44Logo`, `Wide310x150Logo`).
- Ouvrez `AppxManifest.xml` et adaptez les champs suivants :
  - `Identity` (`Name`, `Publisher`, `Version`)
  - `Properties.DisplayName` et `PublisherDisplayName`
  - `Applications.Application` (`Id`, `Executable`, `VisualElements`)

> Astuce : conservez l'exécutable PyInstaller dans un dossier `VintedAssistant`
> à la racine du projet MSIX afin de correspondre au chemin configuré dans le
> manifeste (`VintedAssistant\VintedAssistant.exe`).

## 3. Créer le package MSIX

1. Regroupez le contenu dans une arborescence temporaire, par exemple :
   ```text
   msix-layout/
   ├── AppxManifest.xml
   ├── Assets/
   └── VintedAssistant/
       └── ... (contenu de dist/VintedAssistant)
   ```
2. Exécutez `makeappx.exe` :
   ```powershell
   makeappx.exe pack /d msix-layout /p VintedAssistant.msix
   ```

## 4. Signature du package

Utilisez le script `SignMsix.ps1` pour signer le package :
```powershell
# Exemple avec certificat .pfx protégé par mot de passe
powershell -ExecutionPolicy Bypass -File packaging/windows/msix/SignMsix.ps1 \`
    -MsixPath VintedAssistant.msix \`
    -CertificatePath .\certificats\publisher.pfx \`
    -CertificatePassword "motdepasse" \`
    -TimestampUrl "http://timestamp.digicert.com"
```

Le script recherche automatiquement `signtool.exe` dans le SDK Windows. Si vous
utilisez un certificat issu d'une autorité interne, fournissez l'URL de
timestamp correspondante ou remplacez `/tr` par `/t` dans le script.

## 5. Tests et distribution

- Installez le package sur une machine de test :
  ```powershell
  Add-AppxPackage -Path .\VintedAssistant.msix
  ```
- Vérifiez que l'application se lance correctement et que la clé API OpenAI est
  disponible via `OPENAI_API_KEY` (environnement utilisateur, fichier `.env`,
  etc.).
- Distribuez la MSIX signée via votre canal habituel (Microsoft Intune, Store,
  lien de téléchargement, ...).

## Personnalisation avancée

- Ajoutez des déclarations de capacités UWP supplémentaires si nécessaire dans
  le manifeste.
- Automatisez le packaging au sein d'un pipeline CI/CD en orchestrant PyInstaller,
  MakeAppx et la signature avec votre agent Windows.
- Pour générer un certificat de test, utilisez :
  ```powershell
  New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Contoso Software" \
      -CertStoreLocation Cert:\CurrentUser\My
  ```
  Exportez ensuite le certificat et sa clé privée via `Export-PfxCertificate`.
