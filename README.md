# DocFlow — Plateforme de Traitement de Documents

DocFlow est une solution pour l'automatisation du traitement des documents administratifs (factures, devis, attestations). Le projet suit une architecture Data-Driven avec un pipeline de traitement intelligent.

> [!NOTE]
> Pour une analyse plus approfondie de l'architecture, consultez le [Document d'Architecture Technique (DAT)](./doc/DAT_DocFlow.md).

## 🎥 Démonstration
[![Démonstration Vidéo](https://img.shields.io/badge/Vidéo-Démonstration-red?style=for-the-badge&logo=youtube)](URL_DE_VOTRE_VIDEO_ICI)

## 🚀 Fonctionnalités implémentées

### 1. Upload multi-documents
- **Interface** : Zone de Drag & Drop sur la page `Upload`.
- **Backend** : Endpoint `/api/documents/upload` gérant l'upload massif.
- **Asynchronisme** : Les fichiers sont enregistrés en zone **Bronze** puis traités en arrière-plan via `BackgroundTasks`.

### 2. Classification automatique
- **Moteur** : Utilisation de LLM via Ollama ou Groq.
- **Logique** : Le classifieur (`classifier.py`) analyse le texte OCR pour catégoriser le document (`facture`, `devis`, `attestation`, `autre`).
- **Précision** : Modèle de prompt avec instructions strictes pour garantir un format JSON valide en sortie.

### 3. Extraction des informations clés (OCR)
- **Support Multi-format** : Prise en charge des PDF (natifs ou scannés) et des images (`PNG`, `JPG`, `WEBP`, `TIFF`, etc.).
- **Couche Bas Niveau** : [Tesseract OCR](https://tesseract-ocr.github.io/) avec fallback intelligent via `pypdf` pour les textes natifs.
- **Intelligence d'extraction** : Le service `extractor.py` structure les données brutes via LLM (Groq ou Ollama) :
    - **Identifiants** : SIREN (9 chiffres), SIRET (14 chiffres).
    - **Finances** : Montants HT, TVA, TTC et devise.
    - **Métadonnées** : Dates d'émission, nom de l'émetteur et du destinataire.

### 4. Vérification et détection d'incohérences
Implémenté dans `fraud.py`, effectue une **analyse cross-documents** :
- **SIRET Mismatch** : Alerte critique si un fournisseur présente des SIRET différents sur deux documents distincts.
- **Écart de montants** : Alerte si la facture dépasse le devis correspondant de plus de 5%.
- **Chronologie** : Détection de factures dont la date est antérieure au devis.
- **Validité SIREN** : Vérification du format structurel.

### 5. Architecture Medallion (Data Lake)
Le stockage (`datalake.py`) est organisé en trois zones physiques :
- **Zone Bronze (Raw)** : Stockage des fichiers originaux (Local ou **Cloudinary**) et des manifestes bruts.
- **Zone Silver (Clean)** : Données extraites par le LLM, normalisées et sauvegardées dans **MongoDB**.
- **Zone Gold (Curated)** : Données enrichies des alertes de fraude, prêtes pour la consommation métier.

### 6. Intégration Métier (Front-ends)
- **Dashboard Conformité** : Vue d'ensemble du taux de conformité, KPIs par sévérité et liste filtrable des alertes.
- **CRM Fournisseurs** : Vue consolidée par SIREN regroupant tous les documents, le CA total généré par émetteur et l'état des preuves administratives.

---

## 🛠 Architecture Technique

- **Backend** : FastAPI (Python 3.12) géré par `uv`.
- **Frontend** : React 18 / TypeScript / Vite géré par `fnm`.
- **LLM Switching** : Support dynamique de **Ollama** (Local) et **Groq** (API haute performance) via la variable `LLM_PROVIDER`.
- **Qualité** : Linting strict par Ruff et 24+ tests unitaires/intégration.

## 🏁 Installation et Lancement

Le projet peut être lancé de deux manières. **L'utilisation de Docker est fortement recommandée** car elle inclut nativement toutes les dépendances système complexes (OCR, PDF processing).

### Option A : Docker (Recommandé) 🐳

Cette méthode installe automatiquement **Tesseract OCR** et **Poppler** à l'intérieur des conteneurs.

```bash
# Lancer tout le projet (Backend + Frontend)
docker-compose up --build
```

- **Frontend** : [http://localhost](http://localhost) (Port 80)
- **API Docs** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **Note** : Le dossier `backend/storage` est monté en volume pour conserver vos documents.

### Option B : Installation Locale (Développement) 🛠️

Si vous souhaitez lancer le projet sans Docker, vous devez installer manuellement les dépendances système pour l'OCR :

1.  **Dépendances Système (Obligatoires pour l'OCR, commande à vérifier)** :
    -   **macOS** : `brew install poppler tesseract tesseract-lang`
    -   **Ubuntu/Debian** : `sudo apt install poppler-utils tesseract-ocr tesseract-ocr-fra`
    -   **Windows** : `choco install poppler tesseract`

2.  **Lancement des services** :
    ```bash
    # Utilise uv pour le python et npm pour le front
    ./start.sh
    ```

- **Frontend** : [http://localhost:5173](http://localhost:5173)
- **Backend** : [http://localhost:8000](http://localhost:8000)

---

## ⚙️ Configuration (Variables d'environnement)

Créez un fichier `backend/.env` (basé sur `.env.example`) :

| Variable | Description | Défaut |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `ollama` ou `groq` | `ollama` |
| `GROQ_API_KEY` | Requis si provider = `groq` | - |
| `OLLAMA_BASE_URL` | URL de votre instance Ollama | `http://host.docker.internal:11434` |
| `CLOUDINARY_URL` | Alternatif aux clés séparées | - |
| `CLOUDINARY_CLOUD_NAME` | Pour le stockage distant | - |
| `CLOUDINARY_API_KEY` | - | - |
| `CLOUDINARY_API_SECRET` | - | - |

---

## 🧪 Tests et Qualité

```bash
cd backend
# Lancer les tests
uv run pytest

# Linting
uvx ruff check .
```

## MongoDB

- Variables d'environnement : `MONGODB_URI` et `MONGODB_DB_NAME`
- Local : `MONGODB_URI=mongodb://localhost:27017`
- Docker Compose : un service `mongodb` et un volume `mongodb-data` sont ajoutes
