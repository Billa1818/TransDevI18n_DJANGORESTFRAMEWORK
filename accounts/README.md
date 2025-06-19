# App Accounts - Gestion des utilisateurs et authentification

## Vue d'ensemble

L'application `accounts` gère l'authentification, l'inscription, la gestion des profils utilisateurs et la sécurité des comptes. Elle utilise JWT (JSON Web Tokens) pour l'authentification et inclut des fonctionnalités avancées de sécurité.

## Fonctionnalités principales

### 🔐 Authentification JWT
- **Connexion** avec email/mot de passe
- **Inscription** avec validation des données
- **Tokens d'accès** et de rafraîchissement
- **Renouvellement automatique** des tokens expirés
- **Déconnexion** sécurisée

### 👤 Gestion des utilisateurs
- **Profil utilisateur** étendu avec photo de profil
- **Gestion des abonnements** et quotas
- **Compteur quotidien** de mots traduits
- **Statut d'abonnement** avec dates d'expiration

### 🛡️ Sécurité avancée
- **Gestion des appareils** avec empreintes digitales
- **Limitation des tentatives** de connexion
- **Blocage automatique** des appareils suspects
- **Journal des tentatives** de connexion
- **Réinitialisation sécurisée** des mots de passe

### 🔗 Authentification OAuth
- **Support multi-providers** (Google, GitHub, etc.)
- **Liaison des comptes** OAuth aux utilisateurs
- **Gestion des tokens** OAuth

## Modèles

### User (Utilisateur principal)
Extension du modèle utilisateur Django avec des fonctionnalités avancées.

**Champs principaux :**
- `email` : Email unique (utilisé comme USERNAME_FIELD)
- `username` : Nom d'utilisateur
- `profile_picture` : Photo de profil
- `is_subscribed` : Statut d'abonnement
- `subscription_end_date` : Date de fin d'abonnement
- `daily_word_count` : Compteur quotidien de mots
- `last_word_count_reset` : Date de dernière réinitialisation

**Méthodes principales :**
- `check_subscription_status()` : Vérifie si l'abonnement est actif
- `can_translate_words(word_count)` : Vérifie les quotas
- `increment_daily_word_count(word_count)` : Incrémente le compteur
- `can_attempt_login(device_info)` : Vérifie les limites de connexion
- `can_request_password_reset()` : Vérifie les limites de réinitialisation

### UserDevice (Appareils utilisateur)
Gestion des appareils connectés avec sécurité.

**Champs principaux :**
- `device_id` : UUID unique de l'appareil
- `device_name` : Nom de l'appareil
- `device_type` : Type (desktop, laptop, tablet, mobile)
- `device_fingerprint` : Empreinte unique de l'appareil
- `user_agent` : User-Agent du navigateur
- `ip_address` : Adresse IP
- `is_trusted` : Appareil de confiance
- `is_blocked` : Statut de blocage

**Méthodes principales :**
- `increment_failed_attempts()` : Incrémente les échecs
- `reset_failed_attempts()` : Remet à zéro après succès
- `is_currently_blocked()` : Vérifie le statut de blocage
- `can_attempt_login()` : Autorise les tentatives

### LoginAttempt (Journal des connexions)
Journalisation de toutes les tentatives de connexion.

**Champs principaux :**
- `user` : Utilisateur concerné
- `device` : Appareil utilisé
- `ip_address` : Adresse IP
- `user_agent` : User-Agent
- `success` : Succès ou échec
- `failure_reason` : Raison de l'échec
- `timestamp` : Date/heure

### PasswordResetRequest (Demandes de réinitialisation)
Gestion sécurisée des réinitialisations de mot de passe.

**Champs principaux :**
- `user` : Utilisateur concerné
- `token` : Token unique de réinitialisation
- `is_used` : Token utilisé ou non
- `expires_at` : Date d'expiration
- `created_at` : Date de création

**Méthodes principales :**
- `is_expired()` : Vérifie l'expiration
- `is_valid()` : Vérifie la validité
- `mark_as_used()` : Marque comme utilisé

### OAuthProvider (Fournisseurs OAuth)
Configuration des fournisseurs OAuth.

**Champs principaux :**
- `name` : Nom du fournisseur
- `client_id` : ID client OAuth
- `client_secret` : Secret client OAuth
- `redirect_uri` : URI de redirection
- `is_active` : Statut actif

### UserOAuth (Liaisons OAuth)
Liaison entre utilisateurs et comptes OAuth.

**Champs principaux :**
- `user` : Utilisateur local
- `provider` : Fournisseur OAuth
- `provider_user_id` : ID utilisateur chez le fournisseur
- `access_token` : Token d'accès OAuth
- `refresh_token` : Token de rafraîchissement OAuth

## API Endpoints

### Authentification
- `POST /api/auth/register/` : Inscription d'un nouvel utilisateur
- `POST /api/auth/token/` : Connexion et obtention des tokens JWT
- `POST /api/auth/token/refresh/` : Renouvellement du token d'accès
- `POST /api/auth/logout/` : Déconnexion

### Profil utilisateur
- `GET /api/auth/profile/` : Récupération du profil
- `PUT /api/auth/profile/` : Modification du profil
- `PATCH /api/auth/profile/` : Modification partielle du profil

### Sécurité
- `POST /api/auth/password-reset/` : Demande de réinitialisation
- `POST /api/auth/password-reset/confirm/` : Confirmation de réinitialisation
- `GET /api/auth/devices/` : Liste des appareils
- `DELETE /api/auth/devices/{id}/` : Suppression d'un appareil

## Utilisation

### Inscription d'un utilisateur
```python
from accounts.models import User

# Création d'un utilisateur
user = User.objects.create_user(
    username="john_doe",
    email="john@example.com",
    password="secure_password123",
    first_name="John",
    last_name="Doe"
)
```

### Vérification des quotas
```python
# Vérifier si l'utilisateur peut traduire
if user.can_translate_words(1000):
    # Procéder à la traduction
    user.increment_daily_word_count(1000)
else:
    # Quota insuffisant
    print("Quota insuffisant")
```

### Gestion des appareils
```python
from accounts.models import UserDevice

# Créer ou récupérer un appareil
device, created = UserDevice.objects.get_or_create(
    user=user,
    device_fingerprint="unique_fingerprint",
    defaults={
        'device_name': 'Mon ordinateur',
        'device_type': 'desktop',
        'ip_address': '192.168.1.1'
    }
)

# Vérifier si l'appareil peut tenter une connexion
can_login, message = device.can_attempt_login()
```

## Sécurité

### Limites de connexion
- **Global** : 10 tentatives par heure par utilisateur
- **Par appareil** : 5 tentatives par 30 minutes
- **Blocage automatique** : 1 heure après 5 échecs

### Réinitialisation de mot de passe
- **Limite** : 10 demandes par 24 heures par utilisateur
- **Expiration** : 24 heures pour les tokens
- **Usage unique** : Chaque token ne peut être utilisé qu'une fois

### Gestion des appareils
- **Empreintes uniques** : Chaque appareil a une empreinte unique
- **Appareils de confiance** : Possibilité de marquer des appareils comme fiables
- **Blocage automatique** : Protection contre les tentatives répétées

## Configuration

### Variables d'environnement requises
```bash
# JWT Settings
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ACCESS_TOKEN_LIFETIME=5  # minutes
JWT_REFRESH_TOKEN_LIFETIME=1440  # minutes (24h)

# OAuth Settings
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

### Paramètres de sécurité
```python
# settings.py
LOGIN_ATTEMPT_LIMIT = 10  # Tentatives globales par heure
DEVICE_ATTEMPT_LIMIT = 5  # Tentatives par appareil par 30 minutes
PASSWORD_RESET_LIMIT = 10  # Demandes par 24 heures
DEVICE_BLOCK_DURATION = 60  # Minutes de blocage
```

## Tests

L'application inclut des tests complets pour toutes les fonctionnalités :
- Tests d'authentification JWT
- Tests de gestion des appareils
- Tests de sécurité et limitations
- Tests de réinitialisation de mot de passe

Pour exécuter les tests :
```bash
python manage.py test accounts
```

## Dépendances

- `djangorestframework-simplejwt` : Authentification JWT
- `Pillow` : Gestion des images de profil
- `django-cors-headers` : Gestion CORS pour les API 