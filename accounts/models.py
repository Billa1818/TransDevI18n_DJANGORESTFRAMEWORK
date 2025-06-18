# =============================================================================
# APP: accounts (Gestion des utilisateurs et authentification)
# =============================================================================

# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid

class User(AbstractUser):
    """Modèle utilisateur étendu"""
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_subscribed = models.BooleanField(default=False)
    subscription_end_date = models.DateTimeField(blank=True, null=True)
    daily_word_count = models.IntegerField(default=0)
    last_word_count_reset = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)
    from django.contrib.auth.models import Group, Permission
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def check_subscription_status(self):
        """Vérifie si l'abonnement est encore actif"""
        if self.subscription_end_date:
            return timezone.now() <= self.subscription_end_date
        return False
    
    def can_translate_words(self, word_count):
        """Vérifie si l'utilisateur peut traduire le nombre de mots demandé"""
        if self.is_subscribed and self.check_subscription_status():
            subscription = self.subscription
            if subscription:
                remaining_words = subscription.get_remaining_words()
                return remaining_words >= word_count
        return False
    
    def increment_daily_word_count(self, word_count):
        """Incrémente le compteur quotidien de mots"""
        # Reset si nouveau jour
        if self.last_word_count_reset.date() < timezone.now().date():
            self.reset_daily_word_count()
        
        self.daily_word_count += word_count
        self.save()
    
    def reset_daily_word_count(self):
        """Remet à zéro le compteur quotidien"""
        self.daily_word_count = 0
        self.last_word_count_reset = timezone.now()
        self.save()
    
    def can_attempt_login(self, device_info=None):
        """Vérifie si l'utilisateur peut tenter une connexion"""
        device = None
        if device_info:
            device, created = UserDevice.objects.get_or_create(
                user=self,
                device_fingerprint=device_info.get('fingerprint', ''),
                defaults={
                    'device_name': device_info.get('name', 'Appareil inconnu'),
                    'user_agent': device_info.get('user_agent', ''),
                    'ip_address': device_info.get('ip_address', ''),
                }
            )
        
        # Vérifier les tentatives globales de l'utilisateur
        recent_attempts = LoginAttempt.objects.filter(
            user=self,
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_attempts >= 10:
            return False, "Trop de tentatives de connexion. Réessayez dans 1 heure."
        
        # Vérifier les tentatives spécifiques à l'appareil si disponible
        if device:
            device_attempts = LoginAttempt.objects.filter(
                device=device,
                timestamp__gte=timezone.now() - timedelta(minutes=30)
            ).count()
            
            if device_attempts >= 5:
                return False, "Trop de tentatives sur cet appareil. Réessayez dans 30 minutes."
        
        return True, "Connexion autorisée"
    
    def can_request_password_reset(self):
        """Vérifie si l'utilisateur peut demander une réinitialisation de mot de passe"""
        recent_requests = PasswordResetRequest.objects.filter(
            user=self,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        if recent_requests >= 10:
            return False, "Limite de demandes de réinitialisation atteinte (10/24h)."
        
        return True, "Demande autorisée"
    
    def __str__(self):
        return self.email




class UserDevice(models.Model):
    """Modèle pour gérer les appareils des utilisateurs"""
    
    DEVICE_TYPES = [
        ('desktop', 'Ordinateur de bureau'),
        ('laptop', 'Ordinateur portable'),
        ('tablet', 'Tablette'),
        ('mobile', 'Mobile'),
        ('unknown', 'Inconnu'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_id = models.UUIDField(default=uuid.uuid4, unique=True, null=True, blank=True, editable=False)
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='unknown')
    device_fingerprint = models.CharField(max_length=255)  # Retiré unique=True car on utilise unique_together
    user_agent = models.TextField(blank=True, null=True)  # Ajouté blank=True, null=True
    ip_address = models.GenericIPAddressField(blank=True, null=True)  # Ajouté blank=True, null=True
    is_trusted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Compteurs de sécurité
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_attempt = models.DateTimeField(blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ['user', 'device_fingerprint']
        ordering = ['-last_used']
        verbose_name = "Appareil utilisateur"
        verbose_name_plural = "Appareils utilisateurs"
    
    def increment_failed_attempts(self):
        """Incrémente le compteur d'échecs et bloque si nécessaire"""
        self.failed_login_attempts += 1
        self.last_failed_attempt = timezone.now()
        
        # Bloquer l'appareil après 5 tentatives échouées
        if self.failed_login_attempts >= 5:
            self.is_blocked = True
            self.blocked_until = timezone.now() + timedelta(hours=1)
        
        self.save(update_fields=[
            'failed_login_attempts', 
            'last_failed_attempt', 
            'is_blocked', 
            'blocked_until'
        ])
    
    def reset_failed_attempts(self):
        """Remet à zéro le compteur d'échecs après une connexion réussie"""
        self.failed_login_attempts = 0
        self.last_failed_attempt = None
        self.is_blocked = False
        self.blocked_until = None
        self.save(update_fields=[
            'failed_login_attempts', 
            'last_failed_attempt', 
            'is_blocked', 
            'blocked_until'
        ])
    
    def is_currently_blocked(self):
        """Vérifie si l'appareil est actuellement bloqué"""
        if not self.is_blocked:
            return False
            
        if self.blocked_until and timezone.now() > self.blocked_until:
            # Débloquer automatiquement
            self.is_blocked = False
            self.blocked_until = None
            self.save(update_fields=['is_blocked', 'blocked_until'])
            return False
            
        return True
    
    def can_attempt_login(self):
        """Vérifie si une tentative de connexion est autorisée depuis cet appareil"""
        if self.is_currently_blocked():
            return False, f"Appareil bloqué jusqu'à {self.blocked_until}"
        return True, "Connexion autorisée"
    
    def get_device_info(self):
        """Retourne les informations de l'appareil sous forme de dictionnaire"""
        return {
            'device_id': str(self.device_id),
            'device_name': self.device_name,
            'device_type': self.device_type,
            'is_trusted': self.is_trusted,
            'last_used': self.last_used,
            'created_at': self.created_at,
        }
    
    def __str__(self):
        return f"{self.user.username} - {self.device_name}"

class LoginAttempt(models.Model):
    """Journal des tentatives de connexion"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts')
    device = models.ForeignKey(UserDevice, on_delete=models.CASCADE, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        status = "Réussie" if self.success else "Échouée"
        return f"{self.user.email} - {status} - {self.timestamp}"


class PasswordResetRequest(models.Model):
    """Journal des demandes de réinitialisation de mot de passe"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_requests')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    token = models.CharField(max_length=255, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def is_expired(self):
        """Vérifie si le token a expiré"""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Vérifie si le token est valide (non utilisé et non expiré)"""
        return not self.is_used and not self.is_expired()
    
    def mark_as_used(self):
        """Marque le token comme utilisé"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    def __str__(self):
        return f"{self.user.email} - {self.created_at}"


class OAuthProvider(models.Model):
    """Fournisseurs OAuth (Google, GitHub, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    redirect_uri = models.URLField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class UserOAuth(models.Model):
    """Liaison entre utilisateurs et fournisseurs OAuth"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='oauth_accounts')
    provider = models.ForeignKey(OAuthProvider, on_delete=models.CASCADE)
    provider_user_id = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['provider', 'provider_user_id']
    
    def __str__(self):
        return f"{self.user.email} - {self.provider.name}"
    



