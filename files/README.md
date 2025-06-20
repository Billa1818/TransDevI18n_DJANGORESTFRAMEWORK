# 📁 Documentation API – Application `files`

## Endpoints principaux

---

## 1. Fichiers de traduction (`TranslationFileViewSet`)

### - **Lister les fichiers**
`GET /api/files/`
- Liste paginée des fichiers de traduction de l'utilisateur connecté (ou tous si admin).
- **Filtres** : nom, type, statut, date, etc.
- **Tri** : par date, taille, statut, nom.

### - **Créer (uploader) un fichier**
`POST /api/files/`
- Upload d'un fichier PO/JSON.
- **Body** : fichier à uploader (champ `file`)
- **Réponse** : infos détaillées du fichier créé.

### - **Voir le détail d'un fichier**
`GET /api/files/{id}/`
- Détail complet d'un fichier (métadonnées, stats, etc.)

### - **Mettre à jour un fichier**
`PUT /api/files/{id}/`
- Mise à jour des métadonnées (ex : langue détectée, etc.)

### - **Supprimer un fichier**
`DELETE /api/files/{id}/`
- Supprime le fichier et toutes ses chaînes associées.

### - **Relancer le traitement d'un fichier**
`POST /api/files/{id}/reprocess/`
- Relance l'analyse et l'extraction des chaînes du fichier (supprime les anciennes chaînes).

### - **Télécharger le fichier original**
`GET /api/files/{id}/download/`
- Retourne l'URL de téléchargement du fichier original.

### - **Voir la progression du traitement**
`GET /api/files/{id}/progress/`
- Retourne l'état d'avancement du traitement (upload, parsing, completed, error, etc.)

### - **Statistiques globales sur les fichiers**
`GET /api/files/statistics/`
- Statistiques agrégées : nombre total de fichiers, par statut, par type, taille totale, nombre total de chaînes.

---

## 2. Chaînes de traduction (`TranslationStringViewSet`)

### - **Lister les chaînes**
`GET /api/strings/`
- Liste paginée des chaînes de tous les fichiers de l'utilisateur (ou tous si admin).
- **Filtres** : clé, texte source, contexte, fichier, fuzzy, pluriel, etc.
- **Tri** : par date, ligne, clé.

### - **Créer une chaîne**
`POST /api/strings/`
- Ajoute une nouvelle chaîne à un fichier.

### - **Voir le détail d'une chaîne**
`GET /api/strings/{id}/`
- Détail complet d'une chaîne (clé, texte source, contexte, etc.)

### - **Mettre à jour une chaîne**
`PUT /api/strings/{id}/`
- Modifie le texte source, le contexte, etc.

### - **Supprimer une chaîne**
`DELETE /api/strings/{id}/`
- Supprime la chaîne.

### - **Lister les chaînes d'un fichier**
`GET /api/strings/by_file/?file_id={file_uuid}`
- Liste paginée des chaînes d'un fichier spécifique.

### - **Statistiques globales sur les chaînes**
`GET /api/strings/statistics/`
- Statistiques agrégées : nombre total de chaînes, traduites, non traduites, fuzzy, pluriel, par fichier, taux de progression.

---

## 3. Paramètres de pagination et de filtrage

- **Pagination** :  
  - `page` (int), `page_size` (int, max 100)
- **Recherche** :  
  - `search` (texte global)
- **Filtres principaux** :  
  - Par fichier, par clé, par texte source, par contexte, par statut (fuzzy, pluriel), par date, etc.
- **Tri** :  
  - Par date, ligne, clé, etc.

---

## 4. Exemples de réponses

### - **Fichier**
```json
{
  "id": "uuid",
  "original_filename": "messages.po",
  "file_type": "po",
  "file_size": 12345,
  "uploaded_by": { "id": 1, "email": "user@mail.com" },
  "uploaded_at": "2024-01-15T10:30:00Z",
  "status": "completed",
  "total_strings": 50,
  "detected_language": "fr",
  "detected_language_confidence": 0.98
}
```

### - **Chaîne**
```json
{
  "id": "uuid",
  "file": "uuid",
  "key": "welcome_message",
  "source_text": "Welcome",
  "context": "Message d'accueil",
  "comment": "",
  "is_fuzzy": false,
  "is_plural": false,
  "line_number": 12,
  "created_at": "2024-01-15T10:31:00Z"
}
```

### - **Statistiques fichiers**
```json
{
  "total_files": 12,
  "by_status": { "completed": 10, "processing": 2 },
  "by_type": { "po": 8, "json": 4 },
  "total_size": 1234567,
  "total_strings": 500
}
```

### - **Statistiques chaînes**
```json
{
  "total_strings": 500,
  "translated": 350,
  "untranslated": 150,
  "fuzzy": 20,
  "plural": 10,
  "by_file": { "messages.po": 200, "app.po": 300 },
  "progress_percentage": 70.0
}
```

---

## 5. Sécurité

- **Authentification requise** (JWT ou session)
- Les utilisateurs non admin ne voient que leurs propres fichiers/chaînes.

---

## 6. Résumé des routes

| Méthode | Endpoint                                 | Description                                 |
|---------|------------------------------------------|---------------------------------------------|
| GET     | /api/files/                              | Liste des fichiers                          |
| POST    | /api/files/                              | Upload d'un fichier                         |
| GET     | /api/files/{id}/                         | Détail d'un fichier                         |
| PUT     | /api/files/{id}/                         | Modifier un fichier                         |
| DELETE  | /api/files/{id}/                         | Supprimer un fichier                        |
| POST    | /api/files/{id}/reprocess/               | Relancer le traitement                      |
| GET     | /api/files/{id}/download/                | Télécharger le fichier                      |
| GET     | /api/files/{id}/progress/                | Voir la progression du traitement           |
| GET     | /api/files/statistics/                   | Statistiques globales fichiers              |
| GET     | /api/strings/                            | Liste des chaînes                           |
| POST    | /api/strings/                            | Créer une chaîne                            |
| GET     | /api/strings/{id}/                       | Détail d'une chaîne                         |
| PUT     | /api/strings/{id}/                       | Modifier une chaîne                         |
| DELETE  | /api/strings/{id}/                       | Supprimer une chaîne                        |
| GET     | /api/strings/by_file/?file_id={uuid}     | Chaînes d'un fichier                        |
| GET     | /api/strings/statistics/                 | Statistiques globales chaînes               |

## Vue d'ensemble

L'application `files` gère l'upload, le traitement et l'analyse des fichiers de traduction. Elle supporte actuellement uniquement les formats `.po` et `.json` avec détection automatique de framework.

## Fonctionnalités

### Formats supportés

- **Fichiers PO (.po)** : Format Gettext standard utilisé par de nombreux frameworks
- **Fichiers JSON (.json)** : Format JSON pour les traductions modernes

### Détection automatique de framework

Le système détecte automatiquement le framework utilisé basé sur le contenu du fichier :

#### Frameworks détectés pour les fichiers PO :
- **Django** : Détecté par les références aux fichiers `.py` et mentions de Django
- **Flask** : Détecté par les références aux fichiers `.py` et mentions de Flask
- **Vue.js** : Détecté par les références aux fichiers `.vue`
- **React** : Détecté par les références aux fichiers `.jsx` et `.tsx`
- **Angular** : Détecté par les références aux fichiers `.ts`
- **Laravel** : Détecté par les références aux fichiers `.php` et mentions de Laravel
- **Symfony** : Détecté par les mentions de Symfony
- **WordPress** : Détecté par les mentions de WordPress
- **Joomla** : Détecté par les mentions de Joomla
- **Drupal** : Détecté par les mentions de Drupal

#### Frameworks détectés pour les fichiers JSON :
- **React** : Détecté par les mentions de React, JSX, TSX
- **Vue.js** : Détecté par les mentions de Vue, vue-i18n, vuex
- **Angular** : Détecté par les mentions d'Angular, @angular, ngx-translate
- **Flutter** : Détecté par les mentions de Flutter, flutter_localizations
- **React Native** : Détecté par les mentions de react-native
- **Next.js** : Détecté par les mentions de Next.js
- **Nuxt.js** : Détecté par les mentions de Nuxt
- **Svelte** : Détecté par les mentions de Svelte
- **Ember** : Détecté par les mentions d'Ember

## Modèles

### TranslationFile

Représente un fichier de traduction uploadé.

**Champs principaux :**
- `id` : UUID unique
- `original_filename` : Nom original du fichier
- `file_path` : Chemin vers le fichier stocké
- `file_type` : Type de fichier ('po' ou 'json')
- `file_size` : Taille du fichier en bytes
- `uploaded_by` : Utilisateur qui a uploadé le fichier
- `uploaded_at` : Date d'upload
- `status` : Statut du traitement
- `detected_framework` : Framework détecté automatiquement
- `encoding` : Encodage détecté du fichier
- `total_strings` : Nombre total de chaînes extraites

**Statuts possibles :**
- `uploaded` : Fichier uploadé
- `parsing` : En cours d'analyse
- `processing` : En cours de traitement
- `parsed` : Analyse terminée
- `translating` : En cours de traduction
- `completed` : Traitement terminé
- `error` : Erreur lors du traitement

### TranslationString

Représente une chaîne de traduction individuelle.

**Champs principaux :**
- `id` : UUID unique
- `file` : Référence au fichier parent
- `key` : Clé de traduction
- `source_text` : Texte source
- `translated_text` : Texte traduit
- `context` : Contexte/commentaire
- `comment` : Commentaire additionnel
- `is_fuzzy` : Indique si la traduction est floue (pour les fichiers PO)
- `is_plural` : Indique si c'est une forme plurielle

## Tâches Celery

### process_translation_file

Tâche principale qui traite un fichier de traduction de manière asynchrone.

**Fonctionnalités :**
- Détection automatique de l'encodage
- Détection automatique du framework
- Traitement selon le type de fichier
- Gestion des erreurs et retry automatique
- Mise à jour du statut en temps réel

### Fonctions de détection

#### detect_framework_from_content
Fonction principale qui orchestre la détection de framework selon le type de fichier.

#### detect_framework_from_po
Détecte le framework basé sur le contenu d'un fichier PO en analysant :
- Les références aux fichiers source
- Les mentions spécifiques de frameworks
- Les patterns de commentaires

#### detect_framework_from_json
Détecte le framework basé sur le contenu d'un fichier JSON en analysant :
- Les clés et valeurs contenant des mentions de frameworks
- La structure des données
- Les métadonnées spécifiques

## API

### Endpoints principaux

- `POST /api/files/` : Upload d'un fichier
- `GET /api/files/` : Liste des fichiers
- `GET /api/files/{id}/` : Détails d'un fichier
- `POST /api/files/{id}/reprocess/` : Retraiter un fichier
- `GET /api/files/{id}/download/` : Télécharger un fichier
- `GET /api/files/{id}/progress/` : Progrès du traitement

### Validation

Les fichiers uploadés sont validés selon les critères suivants :
- Extension autorisée : `.po` ou `.json` uniquement
- Taille maximale : 10MB
- Fichier non vide

## Utilisation

### Upload d'un fichier

```python
from files.models import TranslationFile
from files.tasks import process_translation_file

# Créer un fichier
translation_file = TranslationFile.objects.create(
    original_filename="fr.po",
    file_path=file_object,
    file_type="po",
    file_size=file_object.size,
    uploaded_by=user
)

# Lancer le traitement
process_translation_file.delay(translation_file.id)
```

### Vérifier le framework détecté

```python
# Après le traitement
translation_file.refresh_from_db()
print(f"Framework détecté: {translation_file.detected_framework}")
```

## Limitations

- Seuls les formats `.po` et `.json` sont supportés
- La détection de framework est basée sur des patterns et peut ne pas être 100% précise
- Les fichiers de plus de 10MB sont rejetés
- L'encodage est automatiquement détecté avec fallback sur UTF-8

## Dépendances

- `polib` : Pour le traitement des fichiers PO
- `chardet` : Pour la détection d'encodage
- `celery` : Pour le traitement asynchrone 