# App Notifications - Système de notifications

## Vue d'ensemble

L'application `notifications` gère un système complet de notifications pour les utilisateurs. Elle supporte différents types de notifications, la gestion des préférences utilisateur, et des fonctionnalités avancées comme les actions en lot et la recherche.

## Fonctionnalités principales

### 🔔 Types de notifications
- **Traduction** : Notifications de fin de traduction ou d'échec
- **Quotas** : Alertes de quota dépassé ou d'avertissement
- **Abonnements** : Notifications d'expiration d'abonnement
- **Paiements** : Confirmations de paiement réussi ou échoué
- **Système** : Notifications générales du système

### 📱 Gestion des notifications
- **Création** de notifications personnalisées
- **Lecture** et marquage comme lues
- **Suppression** individuelle ou en lot
- **Recherche** et filtrage avancés
- **Pagination** pour de grandes quantités

### ⚙️ Préférences utilisateur
- **Notifications par email** configurables par type
- **Notifications in-app** configurables par type
- **Gestion granulaire** des préférences

### 📊 Statistiques et monitoring
- **Compteurs** de notifications lues/non lues
- **Statistiques** par période et type
- **Monitoring** en temps réel

## Modèles

### Notification (Notification principale)
Modèle principal pour les notifications utilisateur.

**Champs principaux :**
- `id` : UUID unique
- `user` : Utilisateur destinataire
- `title` : Titre de la notification
- `message` : Contenu de la notification
- `notification_type` : Type de notification
- `is_read` : Statut de lecture
- `created_at` : Date de création
- `updated_at` : Date de dernière modification

**Types de notifications :**
- `translation_complete` : Traduction terminée
- `translation_failed` : Échec de traduction
- `quota_warning` : Avertissement de quota
- `quota_exceeded` : Quota dépassé
- `subscription_expiring` : Abonnement expirant
- `subscription_expired` : Abonnement expiré
- `payment_success` : Paiement réussi
- `payment_failed` : Échec de paiement
- `system_notification` : Notification système

**Champs contextuels :**
- `related_object_id` : ID de l'objet lié
- `related_object_type` : Type d'objet lié
- `action_url` : URL d'action associée

**Méthodes principales :**
- `mark_as_read()` : Marque comme lue

### NotificationPreference (Préférences de notification)
Gestion des préférences de notification par utilisateur.

**Champs principaux :**
- `id` : UUID unique
- `user` : Utilisateur (relation OneToOne)

**Préférences email :**
- `email_translation_complete` : Notifications de fin de traduction
- `email_translation_failed` : Notifications d'échec
- `email_quota_warnings` : Alertes de quota
- `email_subscription_alerts` : Alertes d'abonnement
- `email_payment_alerts` : Alertes de paiement

**Préférences in-app :**
- `app_translation_complete` : Notifications de fin de traduction
- `app_quota_warnings` : Alertes de quota
- `app_system_notifications` : Notifications système

## API Endpoints

### CRUD de base
- `GET /api/notifications/` : Liste des notifications (avec pagination et filtres)
- `POST /api/notifications/` : Création d'une notification
- `GET /api/notifications/{id}/` : Détails d'une notification
- `PUT /api/notifications/{id}/` : Modification complète
- `PATCH /api/notifications/{id}/` : Modification partielle
- `DELETE /api/notifications/{id}/` : Suppression

### Notifications spécialisées
- `GET /api/notifications/unread/` : Notifications non lues
- `GET /api/notifications/type/{type}/` : Notifications par type
- `GET /api/notifications/search/` : Recherche dans les notifications

### Actions sur les notifications
- `POST /api/notifications/{id}/mark-read/` : Marquer comme lue
- `POST /api/notifications/mark-all-read/` : Marquer toutes comme lues
- `POST /api/notifications/bulk-mark-read/` : Marquage en lot
- `DELETE /api/notifications/bulk-delete/` : Suppression en lot
- `DELETE /api/notifications/delete-read/` : Supprimer les lues

### Statistiques et monitoring
- `GET /api/notifications/summary/` : Résumé des notifications
- `GET /api/notifications/stats/` : Statistiques détaillées
- `GET /api/notifications/unread-count/` : Compteur de non lues
- `GET /api/notifications/preferences/` : Préférences utilisateur
- `PUT /api/notifications/preferences/` : Mise à jour des préférences

### Notifications par période et priorité
- `GET /api/notifications/period/{period}/` : Par période (today, week, month)
- `GET /api/notifications/priority/{priority}/` : Par priorité (low, medium, high)

## Paramètres de requête

### Filtres de base
- `page` : Numéro de page (défaut: 1)
- `page_size` : Taille de page (défaut: 20)
- `is_read` : Filtrer par statut de lecture (true/false)
- `notification_type` : Filtrer par type
- `ordering` : Tri (-created_at, created_at, -updated_at, etc.)

### Filtres avancés
- `search` : Recherche dans titre et message
- `priority` : Filtrer par priorité
- `created_after` : Notifications créées après une date
- `period` : Période (today, week, month, year)

## Utilisation

### Création d'une notification
```python
from notifications.models import Notification

# Création simple
notification = Notification.objects.create(
    user=user,
    title="Traduction terminée",
    message="Votre fichier a été traduit avec succès",
    notification_type="translation_complete"
)

# Création avec contexte
notification = Notification.objects.create(
    user=user,
    title="Quota dépassé",
    message="Vous avez dépassé votre quota quotidien",
    notification_type="quota_exceeded",
    related_object_id=file_id,
    related_object_type="translation_file",
    action_url="/files/upgrade/"
)
```

### Gestion des préférences
```python
from notifications.models import NotificationPreference

# Récupérer ou créer les préférences
prefs, created = NotificationPreference.objects.get_or_create(user=user)

# Désactiver les notifications email pour les traductions
prefs.email_translation_complete = False
prefs.save()

# Vérifier si une notification doit être envoyée
if prefs.email_translation_complete:
    # Envoyer l'email
    send_translation_email(user, notification)
```

### Requêtes avancées
```python
from notifications.models import Notification

# Notifications non lues récentes
unread = Notification.objects.filter(
    user=user,
    is_read=False
).order_by('-created_at')[:10]

# Notifications par type
translation_notifications = Notification.objects.filter(
    user=user,
    notification_type__in=['translation_complete', 'translation_failed']
)

# Statistiques
stats = Notification.objects.filter(user=user).aggregate(
    total=Count('id'),
    unread=Count('id', filter=Q(is_read=False)),
    today=Count('id', filter=Q(created_at__date=timezone.now().date()))
)
```

## Exemples d'utilisation de l'API

### Client Python pour les notifications
```python
from tests.notifications import NotificationAPIClient

# Initialisation
client = NotificationAPIClient()
client.login("user@example.com", "password")

# Créer une notification
notification = client.create_notification(
    title="Test notification",
    message="Ceci est un test",
    notification_type="system_notification"
)

# Lister les notifications non lues
unread = client.get_unread_notifications(page_size=10)

# Marquer comme lue
client.mark_notification_read(notification['id'])

# Rechercher des notifications
results = client.search_notifications("traduction", notification_type="translation_complete")

# Actions en lot
client.bulk_mark_notifications_read([1, 2, 3, 4, 5])
client.bulk_delete_notifications([10, 11, 12])

# Statistiques
stats = client.get_notifications_stats()
summary = client.get_notifications_summary()
```

### Requêtes cURL
```bash
# Connexion
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Créer une notification
curl -X POST http://localhost:8000/api/notifications/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test",
    "message": "Message de test",
    "notification_type": "system_notification"
  }'

# Lister les notifications
curl -X GET "http://localhost:8000/api/notifications/?page=1&page_size=20&is_read=false" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Marquer comme lue
curl -X POST http://localhost:8000/api/notifications/1/mark-read/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Configuration

### Paramètres de notification
```python
# settings.py
NOTIFICATION_SETTINGS = {
    'DEFAULT_PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,
    'AUTO_MARK_READ_DELAY': 30,  # secondes
    'NOTIFICATION_RETENTION_DAYS': 90,
    'BULK_OPERATION_LIMIT': 100,
}
```

### Templates d'email
```python
# notifications/templates/notifications/
# - translation_complete_email.html
# - quota_warning_email.html
# - subscription_expiring_email.html
# - system_notification_email.html
```

## Monitoring et statistiques

### Métriques disponibles
- **Compteur de notifications** : Total, lues, non lues
- **Notifications par type** : Répartition par catégorie
- **Notifications par période** : Évolution temporelle
- **Taux de lecture** : Pourcentage de notifications lues
- **Temps de lecture** : Délai moyen avant lecture

### Endpoints de monitoring
- `/api/notifications/stats/` : Statistiques complètes
- `/api/notifications/summary/` : Résumé rapide
- `/api/notifications/unread-count/` : Compteur en temps réel

## Tests

L'application inclut des tests complets :
- Tests CRUD des notifications
- Tests des actions en lot
- Tests de recherche et filtrage
- Tests des préférences utilisateur
- Tests de monitoring

Pour exécuter les tests :
```bash
python manage.py test notifications
```

## Dépendances

- `django` : Framework principal
- `djangorestframework` : API REST
- `django-filter` : Filtrage avancé
- `celery` : Tâches asynchrones (pour envoi d'emails) 