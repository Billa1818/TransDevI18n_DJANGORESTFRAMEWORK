# =============================================================================
# accounts/views.py - Views JWT mis à jour avec gestion des appareils
# =============================================================================

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta
from .tasks import send_email_task
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db import transaction



from .models import User, OAuthProvider, UserOAuth, UserDevice, LoginAttempt, PasswordResetRequest
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    TokenRefreshResponseSerializer,
    UserDeviceSerializer,
    LoginAttemptSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)


# =============================================================================
# UTILITAIRES POUR RÉCUPÉRER LES INFORMATIONS DE L'APPAREIL
# =============================================================================

def get_device_info_from_request(request):
    """Extrait les informations de l'appareil depuis la requête"""
    return {
        'ip_address': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'name': request.data.get('device_name', 'Appareil inconnu'),
        'type': request.data.get('device_type', 'unknown'),
        'screen_resolution': request.data.get('screen_resolution', ''),
        'timezone': request.data.get('timezone', ''),
        'language': request.data.get('language', ''),
    }

def get_client_ip(request):
    """
    Récupère l'adresse IP du client de manière robuste
    """
    # Essayer les headers dans l'ordre de priorité
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Prendre la première IP de la liste (client original)
        ip = x_forwarded_for.split(',')[0].strip()
        if ip:
            return ip
    
    # Essayer d'autres headers
    headers_to_check = [
        'HTTP_X_REAL_IP',
        'HTTP_X_FORWARDED_FOR',
        'HTTP_CF_CONNECTING_IP',  # Cloudflare
        'REMOTE_ADDR'
    ]
    
    for header in headers_to_check:
        ip = request.META.get(header)
        if ip:
            # Si c'est une liste d'IPs, prendre la première
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            if ip and ip != 'unknown':
                return ip
    
    # Valeur par défaut si aucune IP n'est trouvée
    return '127.0.0.1'


# =============================================================================
# VUES D'AUTHENTIFICATION JWT AVEC GESTION DES APPAREILS
# =============================================================================



class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Vue personnalisée pour l'obtention des tokens JWT avec gestion des appareils
    POST /api/accounts/token/
    """
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            # Ajouter les informations de l'appareil aux données
            device_info = get_device_info_from_request(request)
            
            # S'assurer que l'IP address est disponible
            ip_address = get_client_ip(request)
            
            # Validation de l'IP
            if not ip_address:
                ip_address = '127.0.0.1'
                logger.warning("IP address not found, using default")
            
            # Créer une copie mutable des données
            mutable_data = request.data.copy()
            mutable_data['device_info'] = device_info
            mutable_data['ip_address'] = ip_address
            
            # Validation du serializer
            serializer = self.get_serializer(data=mutable_data)
            
            try:
                serializer.is_valid(raise_exception=True)
            except TokenError as e:
                logger.error(f"Token error: {e}")
                raise InvalidToken(e.args[0])
            
            # Récupérer l'utilisateur à partir des données validées
            validated_data = serializer.validated_data
            user = self._get_user_from_serializer(serializer, validated_data)
            
            # Traitement post-authentification
            if user:
                self._handle_successful_login(user, device_info, ip_address, request)
            
            return Response({
                'message': 'Connexion réussie',
                'data': validated_data,
                'success': True
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in CustomTokenObtainPairView: {e}")
            return Response({
                'message': 'Erreur lors de la connexion',
                'error': str(e),
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_user_from_serializer(self, serializer, validated_data):
        """Récupère l'utilisateur à partir du serializer ou du token"""
        user = None
        
        if hasattr(serializer, 'user'):
            user = serializer.user
        else:
            # Alternative: récupérer l'utilisateur à partir du token
            try:
                from rest_framework_simplejwt.tokens import UntypedToken
                untyped_token = UntypedToken(validated_data['access'])
                user_id = untyped_token.get('user_id')
                user = User.objects.get(id=user_id)
            except Exception as e:
                logger.error(f"Error getting user from token: {e}")
        
        return user
    
    def _handle_successful_login(self, user, device_info, ip_address, request):
        """Gère les actions post-connexion réussie"""
        try:
            with transaction.atomic():
                # Mise à jour du last_login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                # Préparer le contexte pour l'email
                email_context = {
                    'user': user,
                    'device_info': device_info,
                    'login_time': timezone.now(),
                    'ip_address': ip_address,
                    'user_agent': request.META.get('HTTP_USER_AGENT', 'Inconnu'),
                }
                
                # Envoi de l'email en arrière-plan
                self._send_login_notification(user, email_context)
                
        except Exception as e:
            logger.error(f"Error in post-login handling: {e}")
            # Ne pas faire échouer la connexion pour des erreurs non-critiques
    
    def _send_login_notification(self, user, email_context):
        """Envoie la notification email de connexion"""
        try:
            send_email_task.delay(
                subject='Connexion réussie - Nouveaux tokens générés',
                message=f'Bonjour {user.username}, de nouveaux tokens d\'accès ont été générés pour votre compte.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=render_to_string('accounts/login_success_email.html', email_context),
            )
        except Exception as e:
            logger.error(f"Error sending login notification: {e}")



class CustomTokenRefreshView(TokenRefreshView):
    """
    Vue personnalisée pour le rafraîchissement des tokens JWT
    POST /api/auth/token/refresh/
    """
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            logger.error(f"Token error during refresh: {e}")
            raise InvalidToken(e.args[0])
        
        # Récupérer l'utilisateur depuis le refresh token
        refresh_token = request.data.get('refresh')
        response_data = serializer.validated_data
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                user_id = token.get('user_id')
                
                if user_id:
                    user = User.objects.get(id=user_id)
                    response_data['user'] = {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_subscribed': getattr(user, 'is_subscribed', False),
                        'subscription_status': getattr(user, 'check_subscription_status', lambda: 'inactive')(),
                    }
                    
            except User.DoesNotExist:
                logger.error(f"User with id {user_id} not found")
            except Exception as e:
                logger.error(f"Error getting user from token: {e}")
        
        return Response({
            'data': response_data,
            'success': True
        }, status=status.HTTP_200_OK)

class UserRegistrationView(APIView):
    """
    Vue pour l'inscription d'un nouvel utilisateur avec JWT automatique et gestion des appareils
    POST /api/accounts/register/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Ajouter les informations de l'appareil
        device_info = get_device_info_from_request(request)
        request.data['device_info'] = device_info
        
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            
            response_data = {
                'message': 'Utilisateur créé avec succès',
                'user': {
                    'id': result['user'].id,
                    'username': result['user'].username,
                    'email': result['user'].email,
                    'is_subscribed': result['user'].is_subscribed,
                },
                'tokens': {
                    'refresh': result['refresh'],
                    'access': result['access'],
                },
                'success': True
            }
            
            # Ajouter les informations de l'appareil si disponible
            if 'device' in result:
                response_data['device'] = result['device']
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Erreur lors de la création du compte',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)




class UserLoginView(APIView):
    """
    Vue pour la connexion utilisateur avec JWT et gestion des appareils
    POST /api/accounts/login/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        # Ajouter les informations de l'appareil à la requête
        device_info = self.get_device_info_from_request(request)
        request.data['device_info'] = device_info
        
        serializer = UserLoginSerializer(data=request.data)
        
        if serializer.is_valid():
            result = serializer.validated_data
            user = result['user']
            device = result['device']
            
            # Mise à jour du last_login de l'utilisateur
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Préparer le contexte pour l'email de notification
            email_context = {
                'user': user,
                'device': device,
                'device_info': device_info,
                'login_time': timezone.now(),
                'ip_address': request.META.get('REMOTE_ADDR', 'Inconnue'),
                'user_agent': request.META.get('HTTP_USER_AGENT', 'Inconnu'),
            }
            
            # Envoi de l'email de notification (de manière asynchrone si possible)
            self.send_login_notification(user, email_context)
            
            return Response({
                'message': 'Connexion réussie',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_subscribed': getattr(user, 'is_subscribed', False),
                    'subscription_status': getattr(user, 'check_subscription_status', lambda: 'unknown')(),
                },
                'device': device.get_device_info(),
                'tokens': {
                    'refresh': result['refresh'],
                    'access': result['access'],
                },
                'success': True
            }, status=status.HTTP_200_OK)
        
        else:
            # En cas d'échec, incrémenter le compteur d'échecs pour l'appareil si possible
            self.handle_failed_login(request, serializer.errors)
            
            return Response({
                'message': 'Erreur de connexion',
                'errors': serializer.errors,
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def get_device_info_from_request(self, request):
        """Extraire les informations de l'appareil depuis la requête"""
        return {
            'ip_address': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'device_name': request.data.get('device_name', 'Appareil inconnu'),
            'screen_resolution': request.data.get('screen_resolution', ''),
            'timezone': request.data.get('timezone', ''),
            'language': request.data.get('language', ''),
            'platform': request.data.get('platform', ''),
            'canvas_fingerprint': request.data.get('canvas_fingerprint', ''),
            'webgl_fingerprint': request.data.get('webgl_fingerprint', ''),
        }
    
    def get_client_ip(self, request):
        """Obtenir l'adresse IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def send_login_notification(self, user, email_context):
        """Envoyer une notification par email de connexion"""
        
            
            
        send_email_task.delay(
                subject='Connexion réussie - Nouveaux tokens générés',
                message=f'Bonjour {user.username}, vous vous êtes connecté avec succès.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=render_to_string('accounts/login_success_email.html', email_context)
            )
            
        
    
    def handle_failed_login(self, request, errors):
        """Gérer les échecs de connexion pour la sécurité des appareils"""
        try:
            email = request.data.get('email')  # Changé de 'username' à 'email'
            if email:
                device_info = self.get_device_info_from_request(request)
                device_fingerprint = self.generate_device_fingerprint(device_info)
                
                # Essayer de trouver un appareil existant pour incrémenter les échecs
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(email=email)  # Recherche par email
                    device = UserDevice.objects.get(
                        user=user, 
                        device_fingerprint=device_fingerprint
                    )
                    device.increment_failed_attempts()
                except (User.DoesNotExist, UserDevice.DoesNotExist):
                    # L'utilisateur ou l'appareil n'existe pas, on ignore
                    pass
        except Exception as e:
            logger.error(f"Erreur lors de la gestion des échecs de connexion: {e}")
    
    def generate_device_fingerprint(self, device_info):
        """Générer une empreinte d'appareil (même logique que dans le serializer)"""
        import hashlib
        import json
        
        fingerprint_data = {
            'user_agent': device_info.get('user_agent', ''),
            'screen_resolution': device_info.get('screen_resolution', ''),
            'timezone': device_info.get('timezone', ''),
            'language': device_info.get('language', ''),
            'platform': device_info.get('platform', ''),
            'canvas_fingerprint': device_info.get('canvas_fingerprint', ''),
            'webgl_fingerprint': device_info.get('webgl_fingerprint', ''),
        }
        
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]   



class UserLogoutView(APIView):
    """
    Vue pour la déconnexion utilisateur (blacklist du refresh token)
    POST /api/accounts/logout/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            
            if not refresh_token:
                return Response({
                    'message': 'Refresh token requis',
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Blacklist du refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': 'Déconnexion réussie',
                'success': True
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'message': 'Erreur lors de la déconnexion',
                'error': str(e),
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# VUES GESTION DES APPAREILS
# =============================================================================

class UserDeviceListView(APIView):
    """
    Vue pour lister les appareils de l'utilisateur
    GET /api/accounts/devices/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = request.user.devices.all().order_by('-last_used')
        serializer = UserDeviceSerializer(devices, many=True)
        
        return Response({
            'devices': serializer.data,
            'total_devices': devices.count(),
            'success': True
        })


class UserDeviceDetailView(APIView):
    """
    Vue pour gérer un appareil spécifique
    GET/PUT/DELETE /api/accounts/devices/{device_id}/
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, device_id):
        return get_object_or_404(UserDevice, device_id=device_id, user=self.request.user)

    def get(self, request, device_id):
        device = self.get_object(device_id)
        serializer = UserDeviceSerializer(device)
        
        return Response({
            'device': serializer.data,
            'success': True
        })

    def put(self, request, device_id):
        device = self.get_object(device_id)
        serializer = UserDeviceSerializer(device, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Appareil mis à jour avec succès',
                'device': serializer.data,
                'success': True
            })
        
        return Response({
            'message': 'Erreur lors de la mise à jour',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, device_id):
        device = self.get_object(device_id)
        device_name = device.device_name
        device.delete()
        
        return Response({
            'message': f'Appareil "{device_name}" supprimé avec succès',
            'success': True
        }, status=status.HTTP_204_NO_CONTENT)


class TrustDeviceView(APIView):
    """
    Vue pour marquer un appareil comme de confiance
    POST /api/accounts/devices/{device_id}/trust/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        
        device.is_trusted = True
        device.save()
        
        return Response({
            'message': f'Appareil "{device.device_name}" marqué comme de confiance',
            'device': UserDeviceSerializer(device).data,
            'success': True
        })


class UntrustDeviceView(APIView):
    """
    Vue pour retirer la confiance d'un appareil
    POST /api/accounts/devices/{device_id}/untrust/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        
        device.is_trusted = False
        device.save()
        
        return Response({
            'message': f'Confiance retirée pour l\'appareil "{device.device_name}"',
            'device': UserDeviceSerializer(device).data,
            'success': True
        })


class UnblockDeviceView(APIView):
    """
    Vue pour débloquer un appareil
    POST /api/accounts/devices/{device_id}/unblock/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        
        device.unblock()
        
        return Response({
            'message': f'Appareil "{device.device_name}" débloqué avec succès',
            'device': UserDeviceSerializer(device).data,
            'success': True
        })


# =============================================================================
# VUES TENTATIVES DE CONNEXION
# =============================================================================

class LoginAttemptListView(APIView):
    """
    Vue pour lister les tentatives de connexion
    GET /api/accounts/login-attempts/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Paramètres de pagination
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        # Filtres
        success_filter = request.GET.get('success')
        device_id = request.GET.get('device_id')
        
        queryset = request.user.login_attempts.all()
        
        # Appliquer les filtres
        if success_filter is not None:
            queryset = queryset.filter(success=success_filter.lower() == 'true')
        
        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        
        # Pagination manuelle
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        attempts = queryset.order_by('-timestamp')[start:end]
        
        serializer = LoginAttemptSerializer(attempts, many=True)
        
        return Response({
            'attempts': serializer.data,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            },
            'success': True
        })


# =============================================================================
# VUES RÉINITIALISATION MOT DE PASSE AVEC SYSTÈME SÉCURISÉ
# =============================================================================

class PasswordResetRequestView(APIView):
    """
    Vue pour demander la réinitialisation du mot de passe avec système sécurisé
    POST /api/accounts/password-reset/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Ajouter le contexte de la requête
        context = {
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        serializer = PasswordResetRequestSerializer(data=request.data, context=context)
        
        if serializer.is_valid():
            reset_request = serializer.save()
            
            # Envoyer l'email
            self.send_reset_email(reset_request)
            
            return Response({
                'message': 'Un email de réinitialisation a été envoyé à votre adresse',
                'success': True
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Erreur lors de la demande',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    def send_reset_email(self, reset_request):
        """Envoie l'email de réinitialisation"""
        user = reset_request.user
        reset_url = f"{settings.FRONTEND_URL}/reset-password/{reset_request.token}/"
    
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Notre Site'),
            'expires_at': reset_request.expires_at,
        }
    
        subject = 'Réinitialisation de votre mot de passe'
        message = render_to_string('accounts/password_reset_email.txt', context)
        html_message = render_to_string('accounts/password_reset_email.html', context)
    
        
        send_email_task.delay(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    
        
class PasswordResetConfirmView(APIView):
    """
    Vue pour confirmer la réinitialisation du mot de passe
    POST /api/accounts/password-reset-confirm/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Collecter les informations de sécurité
                user_ip = self.get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', 'Inconnu')
                change_date = timezone.now().strftime('%d/%m/%Y à %H:%M')
                
                # Générer de nouveaux tokens JWT
                refresh = RefreshToken.for_user(user)
                
                # Préparer le contexte pour l'email
                email_context = {
                    'user': user,
                    'site_name': getattr(settings, 'SITE_NAME', 'Notre site'),
                    'change_date': change_date,
                    'user_ip': user_ip,
                    'user_agent': user_agent,
                    'account_url': f"{getattr(settings, 'FRONTEND_URL', '')}/dashboard",
                    'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
                }
                
                # Envoyer l'email de confirmation
                try:
                    send_email_task.delay(
                        subject='Mot de passe modifié avec succès',
                        message='Votre mot de passe a été modifié avec succès.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=render_to_string(
                            'accounts/password_reset_success_email.html', 
                            email_context
                        ),
                    )
                    logger.info(f"Email de confirmation envoyé à {user.email} pour réinitialisation mot de passe")
                except Exception as e:
                    logger.error(f"Erreur lors de l'envoi de l'email de confirmation: {str(e)}")
                    # On continue même si l'email échoue
                
                return Response({
                    'message': 'Mot de passe réinitialisé avec succès',
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    },
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_subscribed': getattr(user, 'is_subscribed', False),
                    },
                    'success': True
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Erreur lors de la réinitialisation du mot de passe: {str(e)}")
                return Response({
                    'message': 'Une erreur inattendue s\'est produite',
                    'success': False
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'message': 'Données invalides',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        """Récupère l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'Inconnue')
        return ip


class ValidatePasswordResetTokenView(APIView):
    """
    Vue pour valider un token de réinitialisation
    POST /api/accounts/validate-reset-token/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({
                'message': 'Token requis',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            reset_request = PasswordResetRequest.objects.get(token=token)
            is_valid = reset_request.is_valid()
            
            return Response({
                'valid': is_valid,
                'user_email': reset_request.user.email if is_valid else None,
                'expires_at': reset_request.expires_at if is_valid else None,
                'success': True
            })
        
        except PasswordResetRequest.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'Token invalide',
                'success': False
            })


# =============================================================================
# VUES PROFIL UTILISATEUR MISES À JOUR
# =============================================================================

class UserProfileView(APIView):
    """
    Vue pour récupérer et mettre à jour le profil utilisateur avec informations des appareils
    GET/PUT/PATCH /api/accounts/profile/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response({
            'user': serializer.data,
            'success': True
        })

    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profil mis à jour avec succès',
                'user': serializer.data,
                'success': True
            })
        return Response({
            'message': 'Erreur lors de la mise à jour',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profil mis à jour avec succès',
                'user': serializer.data,
                'success': True
            })
        return Response({
            'message': 'Erreur lors de la mise à jour',
            'errors': serializer.errors,
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Vue pour changer le mot de passe avec déconnexion des autres appareils
    POST /api/accounts/change-password/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        logout_other_devices = request.data.get('logout_other_devices', False)

        # Vérifications
        if not all([old_password, new_password, confirm_password]):
            return Response({
                'message': 'Tous les champs sont requis',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(old_password):
            return Response({
                'message': 'Ancien mot de passe incorrect',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({
                'message': 'Les nouveaux mots de passe ne correspondent pas',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validation du nouveau mot de passe
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(new_password, user)
        except Exception as e:
            return Response({
                'message': 'Mot de passe non valide',
                'error': str(e),
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Changement du mot de passe
        user.set_password(new_password)
        user.save()

        # Déconnexion des autres appareils si demandé
        if logout_other_devices:
            current_device_info = get_device_info_from_request(request)
            # Marquer les autres appareils comme non actifs
            user.devices.exclude(
                device_fingerprint=self._generate_device_fingerprint(current_device_info)
            ).update(is_active=False)

        # Génération de nouveaux tokens après changement de mot de passe
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Mot de passe changé avec succès',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'logged_out_other_devices': logout_other_devices,
            'success': True
        })

    def _generate_device_fingerprint(self, device_info):
        """Génère un fingerprint unique pour l'appareil"""
        import hashlib
        fingerprint_data = f"{device_info.get('user_agent', '')}_{device_info.get('screen_resolution', '')}_{device_info.get('timezone', '')}_{device_info.get('language', '')}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()




class VerifyPasswordView(APIView):
    """
    Vue pour vérifier le mot de passe de l'utilisateur
    POST /api/accounts/verify-password/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        password = request.data.get('password')
        
        if not password:
            return Response({
                'message': 'Mot de passe requis',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier le mot de passe
        is_valid = request.user.check_password(password)
        
        if is_valid:
            return Response({
                'message': 'Mot de passe valide',
                'valid': True,
                'success': True
            })
        else:
            return Response({
                'message': 'Mot de passe incorrect',
                'valid': False,
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)



# =============================================================================
# VUES UTILITAIRES 
# =============================================================================


class UserStatisticsView(APIView):
    """
    Vue pour récupérer les statistiques complètes de l'utilisateur
    GET /api/accounts/statistics/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Statistiques des appareils
        devices = user.devices.all()
        total_devices = devices.count()
        
        # Statistiques des tentatives de connexion
        login_attempts = user.login_attempts.all()
        
        # Statistiques temporelles (dernières 24h, 7 jours, 30 jours)
        from datetime import timedelta
        now = timezone.now()
        
        recent_24h = login_attempts.filter(timestamp__gte=now - timedelta(days=1))
        recent_7d = login_attempts.filter(timestamp__gte=now - timedelta(days=7))
        recent_30d = login_attempts.filter(timestamp__gte=now - timedelta(days=30))
        
        # Statistiques par appareil
        device_stats = []
        for device in devices:
            device_attempts = login_attempts.filter(device=device)
            device_stats.append({
                'device_id': device.device_id,
                'device_name': device.device_name,
                'total_attempts': device_attempts.count(),
                'successful_attempts': device_attempts.filter(success=True).count(),
                'failed_attempts': device_attempts.filter(success=False).count(),
                'last_used': device.last_used,
                'is_trusted': device.is_trusted,
                'is_blocked': device.is_blocked,
            })
        
        statistics = {
            'user_profile': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
                'is_subscribed': user.is_subscribed,
                'subscription_status': user.check_subscription_status(),
            },
            'devices': {
                'total': total_devices,
                'trusted': devices.filter(is_trusted=True).count(),
                'blocked': devices.filter(is_blocked=True).count(),
                'active': devices.filter(is_active=True).count(),
                'by_type': self._get_device_type_stats(devices),
                'details': device_stats,
            },
            'login_attempts': {
                'total': login_attempts.count(),
                'successful': login_attempts.filter(success=True).count(),
                'failed': login_attempts.filter(success=False).count(),
                'last_24h': {
                    'total': recent_24h.count(),
                    'successful': recent_24h.filter(success=True).count(),
                    'failed': recent_24h.filter(success=False).count(),
                },
                'last_7d': {
                    'total': recent_7d.count(),
                    'successful': recent_7d.filter(success=True).count(),
                    'failed': recent_7d.filter(success=False).count(),
                },
                'last_30d': {
                    'total': recent_30d.count(),
                    'successful': recent_30d.filter(success=True).count(),
                    'failed': recent_30d.filter(success=False).count(),
                },
            },
            'security_metrics': {
                'password_changed_recently': self._password_changed_recently(user),
                'has_suspicious_activity': self._has_suspicious_activity(user),
                'account_security_score': self._calculate_security_score(user),
            }
        }
        
        return Response({
            'statistics': statistics,
            'success': True
        })
    
    def _get_device_type_stats(self, devices):
        """Statistiques par type d'appareil"""
        stats = {}
        for device in devices:
            device_type = device.device_type or 'unknown'
            stats[device_type] = stats.get(device_type, 0) + 1
        return stats
    
    def _password_changed_recently(self, user):
        """Vérifie si le mot de passe a été changé récemment (30 jours)"""
        if hasattr(user, 'password_changed_at'):
            from datetime import timedelta
            return user.password_changed_at >= timezone.now() - timedelta(days=30)
        return False
    
    def _has_suspicious_activity(self, user):
        """Détecte une activité suspecte récente"""
        from datetime import timedelta
        recent_failed = user.login_attempts.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24),
            success=False
        ).count()
        return recent_failed >= 3
    
    def _calculate_security_score(self, user):
        """Calcule un score de sécurité sur 100"""
        score = 0
        
        # Mot de passe récent (+20)
        if self._password_changed_recently(user):
            score += 20
        
        # Appareils de confiance (+15)
        if user.devices.filter(is_trusted=True).exists():
            score += 15
        
        # Pas d'activité suspecte (+25)
        if not self._has_suspicious_activity(user):
            score += 25
        
        # Connexions récentes réussies (+20)
        if user.login_attempts.filter(
            timestamp__gte=timezone.now() - timedelta(days=7),
            success=True
        ).exists():
            score += 20
        
        # Pas d'appareils bloqués (+20)
        if not user.devices.filter(is_blocked=True).exists():
            score += 20
        
        return min(score, 100)
    
class UserSpecificInfoView(APIView):
    """
    Vue pour récupérer des informations spécifiques sur l'utilisateur
    GET /api/accounts/info/{info_type}/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, info_type):
        user = request.user
        
        info_handlers = {
            'profile': self._get_profile_info,
            'devices': self._get_devices_info,
            'security': self._get_security_info,
            'activity': self._get_activity_info,
            'subscription': self._get_subscription_info,
            'login-history': self._get_login_history,
        }
        
        if info_type not in info_handlers:
            return Response({
                'message': f'Type d\'information non supporté: {info_type}',
                'available_types': list(info_handlers.keys()),
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            info_data = info_handlers[info_type](user, request)
            return Response({
                'info_type': info_type,
                'data': info_data,
                'success': True
            })
        except Exception as e:
            return Response({
                'message': f'Erreur lors de la récupération des informations: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_profile_info(self, user, request):
        """Informations de profil détaillées"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': getattr(user, 'first_name', ''),
            'last_name': getattr(user, 'last_name', ''),
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }
    
    def _get_devices_info(self, user, request):
        """Informations détaillées sur les appareils"""
        devices = user.devices.all().order_by('-last_used')
        return {
            'total_devices': devices.count(),
            'devices': UserDeviceSerializer(devices, many=True).data,
            'current_device': self._identify_current_device(user, request),
        }
    
    def _get_security_info(self, user, request):
        """Informations de sécurité"""
        return {
            'trusted_devices_count': user.devices.filter(is_trusted=True).count(),
            'blocked_devices_count': user.devices.filter(is_blocked=True).count(),
            'recent_failed_attempts': user.login_attempts.filter(
                timestamp__gte=timezone.now() - timedelta(days=7),
                success=False
            ).count(),
            'password_reset_requests': user.password_reset_requests.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'can_login': user.can_attempt_login({})[0],
        }
    
    def _get_activity_info(self, user, request):
        """Informations d'activité récente"""
        recent_attempts = user.login_attempts.filter(
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).order_by('-timestamp')[:10]
        
        return {
            'recent_login_attempts': LoginAttemptSerializer(recent_attempts, many=True).data,
            'last_activity': user.last_login,
            'active_sessions': user.devices.filter(is_active=True).count(),
        }
    
    def _get_subscription_info(self, user, request):
        """Informations d'abonnement"""
        return {
            'is_subscribed': user.is_subscribed,
            'subscription_status': user.check_subscription_status(),
            'subscription_start': getattr(user, 'subscription_start', None),
            'subscription_end': getattr(user, 'subscription_end', None),
        }
    
    def _get_login_history(self, user, request):
        """Historique des connexions avec pagination"""
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        attempts = user.login_attempts.all().order_by('-timestamp')
        total = attempts.count()
        
        start = (page - 1) * page_size
        end = start + page_size
        paginated_attempts = attempts[start:end]
        
        return {
            'attempts': LoginAttemptSerializer(paginated_attempts, many=True).data,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }
        }
    
    def _identify_current_device(self, user, request):
        """Identifie l'appareil courant"""
        current_device_info = get_device_info_from_request(request)
        current_fingerprint = self._generate_device_fingerprint(current_device_info)
        
        try:
            current_device = user.devices.get(device_fingerprint=current_fingerprint)
            return UserDeviceSerializer(current_device).data
        except UserDevice.DoesNotExist:
            return None
    
    def _generate_device_fingerprint(self, device_info):
        """Génère un fingerprint unique pour l'appareil"""
        import hashlib
        fingerprint_data = f"{device_info.get('user_agent', '')}_{device_info.get('screen_resolution', '')}_{device_info.get('timezone', '')}_{device_info.get('language', '')}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_security_stats(request):
    """
    Vue pour récupérer les statistiques de sécurité de l'utilisateur
    GET /api/accounts/security-stats/
    """
    user = request.user
    
    # Statistiques des appareils
    devices = user.devices.all()
    total_devices = devices.count()
    trusted_devices = devices.filter(is_trusted=True).count()
    blocked_devices = devices.filter(is_blocked=True).count()
    
    # Statistiques des tentatives de connexion
    login_attempts = user.login_attempts.all()
    total_attempts = login_attempts.count()
    successful_attempts = login_attempts.filter(success=True).count()
    failed_attempts = login_attempts.filter(success=False).count()
    
    # Tentatives récentes (dernières 24h)
    from datetime import timedelta
    recent_attempts = login_attempts.filter(
        timestamp__gte=timezone.now() - timedelta(days=1)
    )
    
    stats = {
        'user_id': user.id,
        'devices': {
            'total': total_devices,
            'trusted': trusted_devices,
            'blocked': blocked_devices,
            'active': devices.filter(is_active=True).count(),
        },
        'login_attempts': {
            'total': total_attempts,
            'successful': successful_attempts,
            'failed': failed_attempts,
            'recent_24h': recent_attempts.count(),
        },
        'security_status': {
            'has_trusted_devices': trusted_devices > 0,
            'has_recent_failed_attempts': recent_attempts.filter(success=False).exists(),
            'account_locked': not user.can_attempt_login({})[0],
        }
    }
    
    return Response({
        'stats': stats,
        'success': True
    })





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_all_devices(request):
    """
    Vue pour supprimer tous les appareils de l'utilisateur sauf le courant
    POST /api/accounts/clear-devices/
    """
    password = request.data.get('password')
    
    if not password:
        return Response({
            'message': 'Mot de passe requis',
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    if not request.user.check_password(password):
        return Response({
            'message': 'Mot de passe incorrect',
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    # Récupérer l'appareil courant
    current_device_info = get_device_info_from_request(request)
    current_fingerprint = CustomTokenObtainPairSerializer()._generate_device_fingerprint(current_device_info)
    
    # Supprimer tous les autres appareils
    deleted_count = request.user.devices.exclude(
        device_fingerprint=current_fingerprint
    ).count()
    
    request.user.devices.exclude(
        device_fingerprint=current_fingerprint
    ).delete()

    return Response({
        'message': f'{deleted_count} appareils supprimés avec succès',
        'deleted_count': deleted_count,
        'success': True
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def validate_token(request):
    """
    Vue pour valider un token JWT et retourner les informations utilisateur
    POST /api/accounts/validate-token/
    """
    token = request.data.get('token')
    
    if not token:
        return Response({
            'valid': False,
            'message': 'Token requis',
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from rest_framework_simplejwt.tokens import UntypedToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        # Valider le token
        UntypedToken(token)
        
        # Décoder le token pour récupérer l'utilisateur
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        user = User.objects.get(id=access_token['user_id'])
        
        return Response({
            'valid': True,
            'user': UserProfileSerializer(user).data,
            'success': True
        })
        
    except (InvalidToken, TokenError, User.DoesNotExist):
        return Response({
            'valid': False,
            'message': 'Token invalide',
            'success': False
        }, status=status.HTTP_401_UNAUTHORIZED)