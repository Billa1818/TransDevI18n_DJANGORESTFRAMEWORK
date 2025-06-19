# App Files - Gestion des fichiers de traduction

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
- `is_translated` : Indique si la chaîne est traduite
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