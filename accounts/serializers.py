# =============================================================================
# accounts/serializers.py - Serializers JWT mis à jour avec gestion des appareils
# =============================================================================

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, OAuthProvider, UserOAuth, UserDevice, LoginAttempt, PasswordResetRequest
from django.contrib.auth import get_user_model
from django.utils import timezone
import hashlib
import secrets

User = get_user_model()

class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer pour les appareils utilisateur"""
    can_login = serializers.SerializerMethodField()
    is_currently_blocked = serializers.SerializerMethodField()
    
    class Meta:
        model = UserDevice
        fields = (
            'device_id', 'device_name', 'device_type', 'is_trusted', 
            'is_active', 'last_used', 'created_at', 'failed_login_attempts',
            'is_blocked', 'blocked_until', 'can_login', 'is_currently_blocked'
        )
        read_only_fields = (
            'device_id', 'last_used', 'created_at', 'failed_login_attempts',
            'is_blocked', 'blocked_until'
        )
    
    def get_can_login(self, obj):
        can_login, message = obj.can_attempt_login()
        return {'allowed': can_login, 'message': message}
    
    def get_is_currently_blocked(self, obj):
        return obj.is_currently_blocked()

class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer pour les tentatives de connexion"""
    device_name = serializers.CharField(source='device.device_name', read_only=True)
    
    class Meta:
        model = LoginAttempt
        fields = (
            'id', 'ip_address', 'user_agent', 'success', 'failure_reason',
            'timestamp', 'device_name'
        )
        read_only_fields = ('id', 'timestamp')




class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer personnalisé pour JWT avec informations utilisateur et gestion des appareils"""
    device_info = serializers.DictField(required=False, write_only=True)
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Ajouter des claims personnalisés
        token['username'] = user.username
        token['email'] = user.email
        token['is_subscribed'] = user.is_subscribed
        
        return token
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        device_info = attrs.get('device_info', {})
        
        # Récupérer l'utilisateur
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Identifiants incorrects.")
        
        # Vérifier si l'utilisateur peut tenter une connexion
        can_attempt, message = user.can_attempt_login(device_info)
        if not can_attempt:
            raise serializers.ValidationError(message)
        
        # Récupérer l'IP address de manière sécurisée
        ip_address = self._get_safe_ip_address(device_info)
        user_agent = device_info.get('user_agent', '')
        
        # Créer ou récupérer l'appareil
        device = None
        if device_info:
            device_fingerprint = self._generate_device_fingerprint(device_info)
            device, created = UserDevice.objects.get_or_create(
                user=user,
                device_fingerprint=device_fingerprint,
                defaults={
                    'device_name': device_info.get('name', 'Appareil inconnu'),
                    'device_type': device_info.get('type', 'unknown'),
                    'user_agent': user_agent,
                    'ip_address': ip_address,
                }
            )
            
            # Vérifier si l'appareil peut tenter une connexion
            can_device_login, device_message = device.can_attempt_login()
            if not can_device_login:
                raise serializers.ValidationError(device_message)
        
        # Tenter l'authentification
        authenticated_user = authenticate(username=email, password=password)
        
        # Enregistrer la tentative de connexion
        success = authenticated_user is not None
        failure_reason = "" if success else "Mot de passe incorrect"
        
        try:
            LoginAttempt.objects.create(
                user=user,  # Utiliser l'utilisateur récupéré, pas celui authentifié
                device=device,
                ip_address=ip_address,  # IP address sécurisée
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason
            )
        except Exception as e:
            # Log l'erreur mais ne pas faire échouer l'authentification
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la création de LoginAttempt: {e}")
        
        if not authenticated_user:
            # Incrémenter les tentatives échouées pour l'appareil
            if device:
                device.increment_failed_attempts()
            raise serializers.ValidationError("Identifiants incorrects.")
        
        if not authenticated_user.is_active:
            raise serializers.ValidationError("Compte désactivé.")
        
        # Réinitialiser les tentatives échouées en cas de succès
        if device:
            device.reset_failed_attempts()
            device.last_used = timezone.now()
            device.save()
        
        # Générer les tokens JWT
        refresh = RefreshToken.for_user(authenticated_user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': authenticated_user.id,
                'username': authenticated_user.username,
                'email': authenticated_user.email,
                'is_subscribed': authenticated_user.is_subscribed,
                'subscription_status': authenticated_user.check_subscription_status(),
            }
        }
        
        # Ajouter les informations de l'appareil si disponible
        if device:
            data['device'] = {
                'device_id': str(device.device_id),
                'device_name': device.device_name,
                'is_trusted': device.is_trusted,
                'is_new': created
            }
        
        return data
    
    def _get_safe_ip_address(self, device_info):
        """Récupère une adresse IP sécurisée (jamais vide)"""
        ip_address = device_info.get('ip_address', '').strip()
        
        # Si l'IP est vide ou None, utiliser l'IP par défaut
        if not ip_address or ip_address in ['', 'null', 'undefined']:
            return '127.0.0.1'
        
        # Validation basique de l'IP
        try:
            # Essayer de valider l'IP
            import ipaddress
            ipaddress.ip_address(ip_address)
            return ip_address
        except ValueError:
            # Si l'IP n'est pas valide, utiliser l'IP par défaut
            return '127.0.0.1'
    
    def _generate_device_fingerprint(self, device_info):
        """Génère un fingerprint unique pour l'appareil"""
        fingerprint_data = f"{device_info.get('user_agent', '')}_{device_info.get('screen_resolution', '')}_{device_info.get('timezone', '')}_{device_info.get('language', '')}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer pour l'inscription d'un utilisateur avec JWT automatique.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    device_info = serializers.DictField(required=False, write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'device_info')

    def validate_email(self, value):
        """Vérifie si l'e-mail est déjà utilisé"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet e-mail est déjà utilisé.")
        return value

    def validate(self, attrs):
        """Valide la correspondance des mots de passe"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        return attrs

    def create(self, validated_data):
        """Crée l'utilisateur après validation et génère les tokens JWT"""
        device_info = validated_data.pop('device_info', {})
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        
        # Créer l'appareil si les informations sont fournies
        device = None
        if device_info:
            device_fingerprint = self._generate_device_fingerprint(device_info)
            device = UserDevice.objects.create(
                user=user,
                device_name=device_info.get('name', f'Appareil de {user.username}'),
                device_type=device_info.get('type', 'unknown'),
                device_fingerprint=device_fingerprint,
                user_agent=device_info.get('user_agent', ''),
                ip_address=device_info.get('ip_address', ''),
                is_trusted=True  # Premier appareil = de confiance
            )
        
        # Générer les tokens JWT pour l'utilisateur nouvellement créé
        refresh = RefreshToken.for_user(user)
        
        result = {
            'user': user,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        if device:
            result['device'] = {
                'device_id': str(device.device_id),
                'device_name': device.device_name,
                'is_trusted': device.is_trusted
            }
        
        return result
    
    def _generate_device_fingerprint(self, device_info):
        """Génère un fingerprint unique pour l'appareil"""
        fingerprint_data = f"{device_info.get('user_agent', '')}_{device_info.get('screen_resolution', '')}_{device_info.get('timezone', '')}_{device_info.get('language', '')}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from .models import UserDevice
import hashlib
import json

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    device_info = serializers.JSONField(required=False)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        device_info = attrs.get('device_info', {})
        
        if not email or not password:
            raise serializers.ValidationError('Email et mot de passe requis.')
        
        # Authentification de l'utilisateur avec email
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError('Identifiants invalides.')
        
        if not user.is_active:
            raise serializers.ValidationError('Compte utilisateur désactivé.')
        
        # Gestion de l'appareil
        device_fingerprint = self.generate_device_fingerprint(device_info)
        
        # Récupérer ou créer l'appareil
        device, created = UserDevice.objects.get_or_create(
            user=user,
            device_fingerprint=device_fingerprint,
            defaults={
                'device_name': device_info.get('device_name', 'Appareil inconnu'),
                'device_type': self.detect_device_type(device_info),
                'ip_address': device_info.get('ip_address'),
                'user_agent': device_info.get('user_agent', ''),
                'is_trusted': False,
            }
        )
        
        # Vérifier si l'appareil peut tenter une connexion
        can_login, message = device.can_attempt_login()
        if not can_login:
            raise serializers.ValidationError(f'Connexion refusée: {message}')
        
        # Si l'appareil existe déjà, mettre à jour les informations
        if not created:
            device.ip_address = device_info.get('ip_address', device.ip_address)
            device.user_agent = device_info.get('user_agent', device.user_agent)
            device.last_used = timezone.now()
            device.save(update_fields=['ip_address', 'user_agent', 'last_used'])
        
        # Réinitialiser les tentatives échouées après une connexion réussie
        if device.failed_login_attempts > 0:
            device.reset_failed_attempts()
        
        # Générer les tokens JWT
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        
        return {
            'user': user,
            'device': device,
            'refresh': str(refresh),
            'access': str(access),
        }
    
    def generate_device_fingerprint(self, device_info):
        """Générer une empreinte unique pour l'appareil"""
        # Utiliser les informations disponibles pour créer une empreinte
        fingerprint_data = {
            'user_agent': device_info.get('user_agent', ''),
            'screen_resolution': device_info.get('screen_resolution', ''),
            'timezone': device_info.get('timezone', ''),
            'language': device_info.get('language', ''),
            'platform': device_info.get('platform', ''),
            'canvas_fingerprint': device_info.get('canvas_fingerprint', ''),
            'webgl_fingerprint': device_info.get('webgl_fingerprint', ''),
        }
        
        # Créer un hash à partir des données
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
    
    def detect_device_type(self, device_info):
        """Détecter le type d'appareil basé sur les informations"""
        user_agent = device_info.get('user_agent', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        elif 'macintosh' in user_agent or 'windows' in user_agent or 'linux' in user_agent:
            # Distinguer entre desktop et laptop est difficile via user agent
            return 'desktop'
        
        return 'unknown'



class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer pour demander une réinitialisation de mot de passe"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Vérifie si l'utilisateur existe et peut demander une réinitialisation"""
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Aucun compte associé à cet e-mail.")
        
        # Vérifier les limites de demandes
        can_request, message = user.can_request_password_reset()
        if not can_request:
            raise serializers.ValidationError(message)
        
        return value
    
    def create(self, validated_data):
        """Crée une demande de réinitialisation"""
        email = validated_data['email']
        user = User.objects.get(email=email)
        
        # Générer un token sécurisé
        token = secrets.token_urlsafe(32)
        
        # Créer la demande
        reset_request = PasswordResetRequest.objects.create(
            user=user,
            ip_address=self.context.get('ip_address', ''),
            user_agent=self.context.get('user_agent', ''),
            token=token,
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        return reset_request

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer pour confirmer la réinitialisation de mot de passe"""
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate_token(self, value):
        """Vérifie la validité du token"""
        try:
            reset_request = PasswordResetRequest.objects.get(token=value)
        except PasswordResetRequest.DoesNotExist:
            raise serializers.ValidationError("Token invalide.")
        
        if not reset_request.is_valid():
            raise serializers.ValidationError("Token expiré ou déjà utilisé.")
        
        return value
    
    def validate(self, attrs):
        """Vérifie la correspondance des mots de passe"""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Les mots de passe ne correspondent pas."})
        return attrs
    
    def save(self):
        """Réinitialise le mot de passe"""
        token = self.validated_data['token']
        new_password = self.validated_data['new_password']
        
        reset_request = PasswordResetRequest.objects.get(token=token)
        user = reset_request.user
        
        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        
        # Marquer le token comme utilisé
        reset_request.mark_as_used()
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer pour le profil utilisateur"""
    subscription_status = serializers.SerializerMethodField()
    remaining_daily_words = serializers.SerializerMethodField()
    devices = UserDeviceSerializer(many=True, read_only=True)
    recent_login_attempts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'profile_picture', 'is_subscribed',
            'subscription_end_date', 'daily_word_count', 'last_word_count_reset',
            'created_at', 'last_login', 'subscription_status', 'remaining_daily_words',
            'devices', 'recent_login_attempts'
        )
        read_only_fields = (
            'id', 'daily_word_count', 'last_word_count_reset', 'created_at',
            'last_login', 'subscription_status', 'remaining_daily_words',
            'devices', 'recent_login_attempts'
        )

    def get_subscription_status(self, obj):
        return obj.check_subscription_status()

    def get_remaining_daily_words(self, obj):
        if hasattr(obj, 'subscription'):
            return obj.subscription.get_remaining_words()
        return 0
    
    def get_recent_login_attempts(self, obj):
        """Retourne les 10 dernières tentatives de connexion"""
        attempts = obj.login_attempts.all()[:10]
        return LoginAttemptSerializer(attempts, many=True).data

class TokenRefreshResponseSerializer(serializers.Serializer):
    """Serializer pour la réponse de refresh token"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()