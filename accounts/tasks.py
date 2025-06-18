from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

User = get_user_model()

# Mapping des types d'email vers les champs de préférence
EMAIL_PREFERENCE_MAPPING = {
    'translation_complete': 'email_translation_complete',
    'translation_failed': 'email_translation_failed',
    'quota_warning': 'email_quota_warnings',
    'subscription_alert': 'email_subscription_alerts',
    'payment_alert': 'email_payment_alerts',
    'system_notification': 'email_system_notifications',
    # Ajoutez d'autres types selon vos besoins
}

@shared_task
def send_email_task(
    subject, 
    message, 
    from_email, 
    recipient_list, 
    email_type=None,
    user_id=None,
    html_message=None, 
    fail_silently=True  # Changé à True par défaut pour éviter les erreurs Celery
):
    """
    Envoie un email en vérifiant d'abord les préférences utilisateur
    
    Args:
        subject: Sujet de l'email
        message: Contenu textuel de l'email
        from_email: Adresse email expéditeur
        recipient_list: Liste des destinataires
        email_type: Type d'email (doit correspondre à EMAIL_PREFERENCE_MAPPING)
        user_id: ID de l'utilisateur (requis si email_type est spécifié)
        html_message: Contenu HTML de l'email (optionnel)
        fail_silently: Ne pas lever d'exception en cas d'erreur
    
    Returns:
        dict: Dictionnaire avec le statut et le message
    """
    try:
        # Validation des paramètres d'entrée
        if not subject or not message or not from_email or not recipient_list:
            error_msg = "Paramètres manquants pour l'envoi d'email"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}
        
        if not isinstance(recipient_list, list):
            recipient_list = [recipient_list]
        
        # Vérification des préférences utilisateur SEULEMENT si un type d'email est spécifié
        if email_type and user_id:
            if not _check_user_email_preference(user_id, email_type):
                logger.info(
                    f"Email de type '{email_type}' annulé pour l'utilisateur {user_id} "
                    f"selon ses préférences"
                )
                return {
                    'success': False, 
                    'message': f"Email annulé - Type '{email_type}' désactivé dans les préférences utilisateur",
                    'cancelled': True
                }
        elif email_type and not user_id:
            logger.warning(
                f"Type d'email '{email_type}' spécifié mais pas d'user_id. "
                f"Envoi sans vérification des préférences."
            )
        elif not email_type:
            logger.debug("Aucun type d'email spécifié - Envoi automatique")
        
        # Envoi de l'email avec gestion d'erreur améliorée
        try:
            if html_message:
                result = send_mail(
                    subject,
                    message,
                    from_email,
                    recipient_list,
                    html_message=html_message,
                    fail_silently=fail_silently,
                )
            else:
                result = send_mail(
                    subject,
                    message,
                    from_email,
                    recipient_list,
                    fail_silently=fail_silently,
                )
            
            # Vérifier le résultat de send_mail
            if result == 0:
                error_msg = "Aucun email n'a été envoyé (problème de configuration SMTP)"
                logger.warning(error_msg)
                return {'success': False, 'message': error_msg}
            
            # Log du succès
            logger.info(f"Email envoyé à {recipient_list} avec le sujet: {subject}")
            return {'success': True, 'message': "Email envoyé avec succès"}
            
        except Exception as email_error:
            # Gestion spécifique des erreurs d'envoi d'email
            error_msg = f"Erreur lors de l'envoi d'email: {str(email_error)}"
            logger.error(error_msg, exc_info=True)
            
            # Si fail_silently=False, on re-lance l'exception
            if not fail_silently:
                raise
            
            return {'success': False, 'message': error_msg}
            
    except Exception as e:
        # Gestion des autres erreurs (préférences utilisateur, etc.)
        error_msg = f"Échec de l'envoi d'email: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Si fail_silently=False, on re-lance l'exception
        if not fail_silently:
            raise
            
        return {'success': False, 'message': error_msg}


def _check_user_email_preference(user_id, email_type):
    """
    Vérifie si l'utilisateur a activé les emails pour ce type
    
    Args:
        user_id: ID de l'utilisateur
        email_type: Type d'email à vérifier
    
    Returns:
        bool: True si l'email peut être envoyé, False sinon
    """
    try:
        # Vérifier si le type d'email est supporté
        if email_type not in EMAIL_PREFERENCE_MAPPING:
            logger.warning(f"Type d'email non reconnu: {email_type}")
            return True  # Par défaut, envoyer l'email si le type n'est pas reconnu
        
        # Récupérer l'utilisateur
        user = User.objects.get(id=user_id)
        
        # Récupérer les préférences de notification
        try:
            from notifications.models import NotificationPreference
            preference, created = NotificationPreference.objects.get_or_create(
                user=user
            )
            
            # Vérifier la préférence spécifique
            preference_field = EMAIL_PREFERENCE_MAPPING[email_type]
            is_enabled = getattr(preference, preference_field, True)  # True par défaut
            
            logger.debug(
                f"Préférence email pour l'utilisateur {user_id}, "
                f"type '{email_type}': {is_enabled}"
            )
            
            return is_enabled
            
        except ImportError:
            logger.warning("Module notifications.models non trouvé, envoi par défaut")
            return True
        
    except ObjectDoesNotExist:
        logger.error(f"Utilisateur avec l'ID {user_id} introuvable")
        return False  # Ne pas envoyer l'email si l'utilisateur n'existe pas
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des préférences: {str(e)}")
        return True  # En cas d'erreur, envoyer l'email par sécurité


@shared_task
def send_bulk_email_task(emails_data):
    """
    Envoie plusieurs emails en vérifiant les préférences pour chacun
    
    Args:
        emails_data: Liste de dictionnaires contenant les données d'email
        Format: [
            {
                'subject': 'Sujet',
                'message': 'Message',
                'from_email': 'from@example.com',
                'recipient_list': ['to@example.com'],
                'email_type': 'translation_complete',
                'user_id': 1,
                'html_message': '<html>...</html>',  # optionnel
                'fail_silently': True,  # optionnel
            },
            ...
        ]
    
    Returns:
        dict: Statistiques d'envoi détaillées
    """
    if not emails_data or not isinstance(emails_data, list):
        logger.error("Données d'email invalides pour l'envoi groupé")
        return {
            'sent': 0,
            'cancelled': 0,
            'failed': 1,
            'details': [{'error': 'Données d\'email invalides'}]
        }
    
    results = {
        'sent': 0,
        'cancelled': 0,
        'failed': 0,
        'details': []
    }
    
    for i, email_data in enumerate(emails_data):
        try:
            # Validation des données d'email
            required_fields = ['subject', 'message', 'from_email', 'recipient_list']
            missing_fields = [field for field in required_fields if not email_data.get(field)]
            
            if missing_fields:
                error_msg = f"Champs manquants pour l'email {i}: {missing_fields}"
                logger.error(error_msg)
                results['failed'] += 1
                results['details'].append({
                    'email_index': i,
                    'recipient': email_data.get('recipient_list', []),
                    'result': error_msg
                })
                continue
            
            # Appel synchrone de la tâche pour le traitement groupé
            result = send_email_task(
                subject=email_data['subject'],
                message=email_data['message'],
                from_email=email_data['from_email'],
                recipient_list=email_data['recipient_list'],
                email_type=email_data.get('email_type'),
                user_id=email_data.get('user_id'),
                html_message=email_data.get('html_message'),
                fail_silently=email_data.get('fail_silently', True)
            )
            
            # Traitement du résultat
            if result['success']:
                results['sent'] += 1
            elif result.get('cancelled'):
                results['cancelled'] += 1
            else:
                results['failed'] += 1
                
            results['details'].append({
                'email_index': i,
                'recipient': email_data['recipient_list'],
                'result': result['message'],
                'success': result['success']
            })
            
        except Exception as e:
            error_msg = f"Erreur lors du traitement de l'email {i}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['failed'] += 1
            results['details'].append({
                'email_index': i,
                'recipient': email_data.get('recipient_list', []),
                'result': error_msg,
                'success': False
            })
    
    logger.info(f"Envoi groupé terminé - Envoyés: {results['sent']}, "
               f"Annulés: {results['cancelled']}, Échecs: {results['failed']}")
    
    return results


# Fonctions utilitaires pour les différents types d'emails

@shared_task
def send_translation_complete_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email de traduction terminée"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='translation_complete',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi d'email de traduction: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}


@shared_task
def send_quota_warning_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email d'avertissement de quota"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='quota_warning',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi d'email de quota: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}


@shared_task
def send_payment_alert_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email d'alerte de paiement"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='payment_alert',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi d'email de paiement: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}


@shared_task
def send_translation_failed_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email d'échec de traduction"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='translation_failed',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi d'email d'échec: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}


@shared_task
def send_subscription_alert_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email d'alerte d'abonnement"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='subscription_alert',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi d'email d'abonnement: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}


@shared_task
def send_system_notification_email(user_id, subject, message, from_email, html_message=None, fail_silently=True):
    """Envoie un email de notification système"""
    try:
        user = User.objects.get(id=user_id)
        result = send_email_task(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            email_type='system_notification',
            user_id=user_id,
            html_message=html_message,
            fail_silently=fail_silently
        )
        return result
    except ObjectDoesNotExist:
        error_msg = f"Utilisateur {user_id} introuvable"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi de notification système: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'success': False, 'message': error_msg}