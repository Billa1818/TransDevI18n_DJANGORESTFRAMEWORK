# 🌍 Documentation API – Application `translations`

## Endpoints principaux

---

## 1. Langues (`LanguageViewSet`)

### - **Lister les langues**
`GET /api/translations/languages/`
- Liste paginée des langues supportées.
- **Filtres** : code, nom, nom natif, actif, nombre de traductions, etc.

### - **Voir une langue**
`GET /api/translations/languages/{id}/`
- Détail d'une langue.

### - **Lister les langues supportées par Google Translate**
`GET /api/translations/languages/supported/`
- Retourne la liste des langues disponibles via Google Translate.

---

## 2. Traductions (`TranslationViewSet`)

### - **Lister les traductions**
`GET /api/translations/translations/`
- Liste paginée des traductions de l'utilisateur.
- **Filtres** : clé, texte source, langue cible, fichier, approuvé, confiance, etc.

### - **Voir une traduction**
`GET /api/translations/translations/{id}/`
- Détail d'une traduction.

---

## 3. Tâches de traduction (`TranslationTaskViewSet`)

### - **Lister les tâches**
`GET /api/translations/tasks/`
- Liste paginée des tâches de traduction de l'utilisateur.
- **Filtres** : statut, langue cible, fichier, progression, etc.

### - **Créer une tâche de traduction**
`POST /api/translations/tasks/`
- Lance une nouvelle tâche de traduction pour un fichier et une ou plusieurs langues cibles.

### - **Voir une tâche**
`GET /api/translations/tasks/{id}/`
- Détail d'une tâche.

### - **Voir la progression d'une tâche**
`GET /api/translations/tasks/{id}/progress/`
- Retourne la progression détaillée de la tâche (nombre de chaînes, progression, etc.)

### - **Annuler une tâche**
`POST /api/translations/tasks/{id}/cancel/`
- Annule une tâche de traduction (si non terminée).

---

## 4. Fichiers et gestion avancée (`FileTranslationViewSet`)

### - **Lister les fichiers de l'utilisateur avec infos de traduction**
`GET /api/translations/files/my_files/`
- Liste tous les fichiers de l'utilisateur avec progression par langue.

### - **Traduire un fichier**
`POST /api/translations/files/{id}/translate_file/`
- Lance la traduction automatique d'un fichier dans une langue cible.
- **Paramètres** :
  - `target_language` (obligatoire) : code langue cible (ex : `fr`)
  - `force_retranslate` (optionnel, booléen) : si `true`, force la suppression des anciennes traductions et relance la traduction même si tout est déjà traduit
  - `previous_detected_language` (optionnel) : code langue détectée précédemment (utile si la langue détectée a été modifiée)

- **Comportement anti-doublon** :
  - Si toutes les chaînes du fichier sont déjà traduites dans la langue cible (depuis la langue détectée actuelle), la traduction est refusée (erreur 400), sauf si :
    - `force_retranslate=true` est passé dans la requête
    - la langue détectée a changé (dans ce cas, les anciennes traductions sont supprimées et une nouvelle tâche est créée)
  - Si une tâche de traduction est déjà en cours pour ce fichier/langue, la création est refusée (erreur 400).
  - Si la langue détectée a changé (modification manuelle ou redétection), l'utilisateur peut relancer la traduction : toutes les anciennes traductions pour ce fichier/langue cible sont supprimées avant de lancer la nouvelle tâche.

- **Exemple de requête** :
```json
POST /api/translations/files/123e4567-e89b-12d3-a456-426614174000/translate_file/
{
  "target_language": "fr"
}
```

- **Exemple pour forcer la retraduction** :
```json
POST /api/translations/files/123e4567-e89b-12d3-a456-426614174000/translate_file/
{
  "target_language": "fr",
  "force_retranslate": true
}
```

- **Exemple pour relancer après modification de la langue détectée** :
```json
POST /api/translations/files/123e4567-e89b-12d3-a456-426614174000/translate_file/
{
  "target_language": "fr",
  "previous_detected_language": "en"
}
```

- **Réponse en cas de refus (déjà tout traduit)** :
```json
{
  "error": "Toutes les chaînes de ce fichier sont déjà traduites en French (depuis la langue détectée actuelle).",
  "info": "Pour forcer une nouvelle traduction, utilisez force_retranslate=true."
}
```

- **Réponse en cas de succès** :
```json
{
  "message": "Traduction du fichier \"messages.po\" lancée avec succès",
  "task_id": 42,
  "file_name": "messages.po",
  "target_language": "French",
  "total_strings": 50,
  "status": "started",
  "force_retranslate": false,
  "langue_detectee_changee": false
}
```

### - **Détecter automatiquement la langue d'un fichier**
`POST /api/translations/files/{id}/detect_language/`
- Déclenche la détection automatique de la langue source.

### - **Mettre à jour la langue détectée**
`POST /api/translations/files/{id}/update_detected_language/`
- Permet de corriger manuellement la langue détectée.

### - **Résumé des traductions d'un fichier**
`GET /api/translations/files/{id}/translations_summary/`
- Retourne un résumé par langue (progression, nombre de traductions, etc.)

### - **Statut détaillé des traductions d'un fichier**
`GET /api/translations/files/{id}/translation_status/`
- Vérifie si un fichier a des traductions, progression, alertes, etc.

### - **Voir toutes les traductions d'un fichier**
`GET /api/translations/files/{id}/all_translations/`
- Liste paginée/groupée de toutes les traductions d'un fichier, filtrable par langue, approuvé, confiance, etc.

---

## 5. Correction manuelle

### - **Corriger une traduction**
`PUT /api/translations/corrections/{id}/`
- Corrige manuellement une traduction (texte, statut approuvé, commentaire).

### - **Correction en lot**
`POST /api/translations/corrections/bulk/`
- Corrige plusieurs traductions en une seule requête.

### - **Lister les traductions à corriger**
`GET /api/translations/corrections/`
- Liste paginée des traductions échouées ou à faible confiance.

---

## 6. Statistiques

### - **Statistiques globales**
`GET /api/translations/statistics/`
- Statistiques sur les traductions : nombre total, approuvées, échouées, par langue, par fichier, taux d'approbation, etc.

---

## 7. Paramètres de pagination, filtrage, tri

- **Pagination** :  
  - `page`, `page_size`
- **Recherche** :  
  - `search`
- **Filtres principaux** :  
  - Par langue, fichier, approuvé, confiance, date, etc.
- **Tri** :  
  - Par date, confiance, approuvé, etc.

---

## 8. Exemples de réponses

### - **Traduction**
```json
{
  "id": "uuid",
  "string": {
    "id": "uuid",
    "key": "welcome_message",
    "source_text": "Welcome to our application"
  },
  "target_language": {
    "code": "fr",
    "name": "French"
  },
  "translated_text": "Bienvenue dans notre application",
  "confidence_score": 0.85,
  "is_approved": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

### - **Statut de traduction d'un fichier**
```json
{
  "file_id": "uuid",
  "file_name": "messages.po",
  "has_translations": true,
  "total_strings": 50,
  "total_translations": 150,
  "languages_with_translations": ["fr", "es", "de"],
  "translation_languages_count": 3,
  "overall_progress": 75.0,
  "last_translation_date": "2024-01-15T11:30:00Z",
  "needs_attention": true,
  "attention_reasons": [
    "25 traductions en attente d'approbation",
    "10 traductions avec faible confiance"
  ]
}
```

### - **Statistiques**
```json
{
  "general": {
    "total_translations": 1500,
    "approved_translations": 1200,
    "failed_translations": 300,
    "low_confidence_translations": 200,
    "approval_rate": 80.0
  },
  "by_language": [
    {
      "language": "fr",
      "language_name": "French",
      "total": 500,
      "approved": 450,
      "failed": 50,
      "low_confidence": 30,
      "avg_confidence": 0.85
    }
  ],
  "by_file": [
    {
      "file_id": "uuid",
      "filename": "messages.po",
      "total": 300,
      "approved": 280,
      "failed": 20,
      "low_confidence": 15
    }
  ]
}
```

---

## 9. Sécurité

- **Authentification requise** (JWT ou session)
- Les utilisateurs non admin ne voient que leurs propres traductions/tâches/fichiers.

---

## 10. Résumé des routes

| Méthode | Endpoint                                                        | Description                                 |
|---------|-----------------------------------------------------------------|---------------------------------------------|
| GET     | /api/translations/languages/                                    | Liste des langues                           |
| GET     | /api/translations/languages/{id}/                               | Détail d'une langue                         |
| GET     | /api/translations/languages/supported/                          | Langues supportées Google Translate         |
| GET     | /api/translations/translations/                                 | Liste des traductions                       |
| GET     | /api/translations/translations/{id}/                            | Détail d'une traduction                     |
| GET     | /api/translations/tasks/                                        | Liste des tâches                            |
| POST    | /api/translations/tasks/                                        | Créer une tâche de traduction               |
| GET     | /api/translations/tasks/{id}/                                   | Détail d'une tâche                          |
| GET     | /api/translations/tasks/{id}/progress/                          | Progression d'une tâche                     |
| POST    | /api/translations/tasks/{id}/cancel/                            | Annuler une tâche                           |
| GET     | /api/translations/files/my_files/                               | Fichiers de l'utilisateur                   |
| POST    | /api/translations/files/{id}/translate_file/                    | Traduire un fichier                         |
| POST    | /api/translations/files/{id}/detect_language/                   | Détecter la langue d'un fichier             |
| POST    | /api/translations/files/{id}/update_detected_language/          | Corriger la langue détectée                 |
| GET     | /api/translations/files/{id}/translations_summary/              | Résumé des traductions d'un fichier         |
| GET     | /api/translations/files/{id}/translation_status/                | Statut détaillé des traductions d'un fichier|
| GET     | /api/translations/files/{id}/all_translations/                  | Toutes les traductions d'un fichier         |
| PUT     | /api/translations/corrections/{id}/                             | Corriger une traduction                     |
| POST    | /api/translations/corrections/bulk/                             | Correction en lot                           |
| GET     | /api/translations/corrections/                                  | Traductions à corriger                      |
| GET     | /api/translations/statistics/                                   | Statistiques globales                       |
