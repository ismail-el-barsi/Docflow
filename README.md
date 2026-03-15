# DocFlow — Plateforme de Traitement de Documents

DocFlow est une solution pour l'automatisation du traitement des documents administratifs (factures, devis, attestations). Le projet suit une architecture Data-Driven avec un pipeline de traitement intelligent.

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
- **Couche Bas Niveau** : [Tesseract OCR](https://tesseract-ocr.github.io/) pour l'extraction du texte brut depuis les PDF.
- **Intelligence d'extraction** : Le service `extractor.py` structure les données brutes :
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
- **Zone Bronze (Raw)** : Stockage des PDF originaux et des manifestes bruts.
- **Zone Silver (Clean)** : Données extraites par le LLM, normalisées et structurées en JSON.
- **Zone Gold (Curated)** : Données enrichies des alertes de fraude et prêtes pour la consommation métier.

### 6. Intégration Métier (Front-ends)
- **Dashboard Conformité** : Vue d'ensemble du taux de conformité, KPIs par sévérité et liste filtrable des alertes.
- **CRM Fournisseurs** : Vue consolidée par SIREN regroupant tous les documents, le CA total généré par émetteur et l'état des preuves administratives.

---

## 🛠 Architecture Technique

- **Backend** : FastAPI (Python 3.12) géré par `uv`.
- **Frontend** : React 18 / TypeScript / Vite géré par `fnm`.
- **LLM Switching** : Support dynamique de **Ollama** (Local) et **Groq** (API haute performance) via la variable `LLM_PROVIDER`.
- **Qualité** : Linting strict par Ruff et 24+ tests unitaires/intégration.

## 🏁 Lancement Rapide

```bash
# Lancer tout le projet (Backend + Frontend)
./start.sh
```

- **Accès Frontend** : [http://localhost:5173](http://localhost:5173)
- **Documentation API** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **Mode Local** : Assurez-vous qu'Ollama est lancé si `LLM_PROVIDER=ollama`.

## 🐳 Déploiement Docker

Pour conteneuriser l'application et la rendre portable :

```bash
# Dans le dossier racine
docker-compose up --build
```

- **Backend** : Contient Tesseract et Poppler pré-installés.
- **Frontend** : Servi par Nginx sur le port **80**.
- **Data Lake** : Persisté via un volume lié au dossier `./backend/storage`.
- **Ollama** : Pour utiliser Ollama (Mac/Linux), le conteneur utilise `host.docker.internal` pour communiquer avec l'hôte.

## 🧪 Tests

```bash
cd backend
uv run pytest
```
