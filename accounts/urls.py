# =============================================================================
# accounts/urls.py - Configuration des URLs pour l'authentification JWT avec gestion des appareils
# =============================================================================

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # =============================================================================
    # URLs D'AUTHENTIFICATION JWT
    # =============================================================================
    
    # Obtention des tokens JWT (connexion)
    path('token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # Rafraîchissement des tokens JWT
    path('token/refresh/', views.CustomTokenRefreshView.as_view(), name='token_refresh'),
    
    # Inscription avec JWT automatique
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    
    # Connexion avec JWT
    path('login/', views.UserLoginView.as_view(), name='login'),
    
    # Déconnexion (blacklist du refresh token)
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    
    # =============================================================================
    # URLs GESTION DES APPAREILS
    # =============================================================================
    
    # Lister tous les appareils de l'utilisateur
    path('devices/', views.UserDeviceListView.as_view(), name='device_list'),
    
    # Détails d'un appareil spécifique (GET/PUT/DELETE)
    path('devices/<str:device_id>/', views.UserDeviceDetailView.as_view(), name='device_detail'),
    
    # Marquer un appareil comme de confiance
    path('devices/<str:device_id>/trust/', views.TrustDeviceView.as_view(), name='trust_device'),
    
    # Retirer la confiance d'un appareil
    path('devices/<str:device_id>/untrust/', views.UntrustDeviceView.as_view(), name='untrust_device'),
    
    # Débloquer un appareil
    path('devices/<str:device_id>/unblock/', views.UnblockDeviceView.as_view(), name='unblock_device'),
    
    # Supprimer tous les appareils sauf le courant
    path('clear-devices/', views.clear_all_devices, name='clear_all_devices'),
    
    # =============================================================================
    # URLs TENTATIVES DE CONNEXION
    # =============================================================================
    
    # Lister les tentatives de connexion avec pagination et filtres
    path('login-attempts/', views.LoginAttemptListView.as_view(), name='login_attempts'),
    
    # =============================================================================
    # URLs RÉINITIALISATION MOT DE PASSE
    # =============================================================================
    
    # Demander la réinitialisation du mot de passe
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    
    # Confirmer la réinitialisation du mot de passe
    path('password-reset-confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Valider un token de réinitialisation
    path('validate-reset-token/', views.ValidatePasswordResetTokenView.as_view(), name='validate_reset_token'),
    
    # =============================================================================
    # URLs PROFIL UTILISATEUR
    # =============================================================================
    
    # Profil utilisateur (GET/PUT/PATCH)
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    
    # Changer le mot de passe
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    # Ajoutez ces URLs dans votre fichier urls.py
    path('verify-password/', views.VerifyPasswordView.as_view(), name='verify-password'),
    path('statistics/', views.UserStatisticsView.as_view(), name='user-statistics'),
    path('info/<str:info_type>/', views.UserSpecificInfoView.as_view(), name='user-specific-info'),
    
    # =============================================================================
    # URLs UTILITAIRES ET SÉCURITÉ
    # =============================================================================
    
    # Statistiques de sécurité de l'utilisateur
    path('security-stats/', views.user_security_stats, name='security_stats'),
    
    # Valider un token JWT
    path('validate-token/', views.validate_token, name='validate_token'),
]

# =============================================================================
# DOCUMENTATION DES ENDPOINTS
# =============================================================================

