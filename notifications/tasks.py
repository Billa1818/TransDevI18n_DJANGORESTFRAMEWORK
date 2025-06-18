# notifications/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import Notification
import logging
from django.contrib.auth import get_user_model
User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task
def replicate_notification(title, message, notification_type, user_ids=None):
    """
    Répliquer une notification pour plusieurs utilisateurs
    
    Args:
        title: Titre de la notification
        message: Message de la notification  
        notification_type: Type de notification
        user_ids: Liste des IDs utilisateurs (si None = tous les utilisateurs)
    """
    # Sélectionner les utilisateurs
    if user_ids:
        users = User.objects.filter(id__in=user_ids)
    else:
        users = User.objects.all()
    
    # Créer une notification pour chaque utilisateur
    notifications = []
    for user in users:
        notification = Notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )
        notifications.append(notification)
    
    # Création en lot
    Notification.objects.bulk_create(notifications)
    
    return f"Créé {len(notifications)} notifications"







@shared_task(bind=True, max_retries=3)
def cleanup_old_notifications(self, days_to_keep=30):
    """
    Supprime les notifications anciennes selon la politique de rétention.
    
    Args:
        days_to_keep (int): Nombre de jours à conserver (défaut: 30)
    
    Returns:
        dict: Statistiques de suppression
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Compter les notifications à supprimer
        notifications_to_delete = Notification.objects.filter(
            created_at__lt=cutoff_date
        )
        
        total_count = notifications_to_delete.count()
        
        if total_count == 0:
            logger.info("Aucune notification ancienne à supprimer")
            return {
                'status': 'success',
                'deleted_count': 0,
                'message': 'Aucune notification à supprimer'
            }
        
        # Statistiques par type avant suppression
        stats_by_type = {}
        for notification_type, _ in Notification.NOTIFICATION_TYPES:
            count = notifications_to_delete.filter(
                notification_type=notification_type
            ).count()
            if count > 0:
                stats_by_type[notification_type] = count
        
        # Suppression en lot
        deleted_count, _ = notifications_to_delete.delete()
        
        logger.info(
            f"Suppression réussie: {deleted_count} notifications supprimées "
            f"(plus anciennes que {days_to_keep} jours)"
        )
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'stats_by_type': stats_by_type,
            'message': f'{deleted_count} notifications supprimées avec succès'
        }
        
    except Exception as exc:
        logger.error(f"Erreur lors de la suppression des notifications: {str(exc)}")
        
        # Retry avec backoff exponentiel
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),
            exc=exc
        )

@shared_task(bind=True, max_retries=3)
def cleanup_read_notifications(self, days_to_keep=7):
    """
    Supprime les notifications lues plus anciennes que X jours.
    
    Args:
        days_to_keep (int): Nombre de jours à conserver pour les notifications lues
    
    Returns:
        dict: Statistiques de suppression
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Notifications lues uniquement
        read_notifications = Notification.objects.filter(
            is_read=True,
            updated_at__lt=cutoff_date  # Utilise updated_at car c'est quand elle a été lue
        )
        
        total_count = read_notifications.count()
        
        if total_count == 0:
            logger.info("Aucune notification lue ancienne à supprimer")
            return {
                'status': 'success',
                'deleted_count': 0,
                'message': 'Aucune notification lue à supprimer'
            }
        
        deleted_count, _ = read_notifications.delete()
        
        logger.info(
            f"Suppression des notifications lues: {deleted_count} notifications "
            f"supprimées (lues depuis plus de {days_to_keep} jours)"
        )
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'message': f'{deleted_count} notifications lues supprimées'
        }
        
    except Exception as exc:
        logger.error(f"Erreur lors de la suppression des notifications lues: {str(exc)}")
        
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),
            exc=exc
        )

@shared_task(bind=True, max_retries=2)
def cleanup_notifications_by_type(self, notification_type, days_to_keep=14):
    """
    Supprime les notifications d'un type spécifique plus anciennes que X jours.
    
    Args:
        notification_type (str): Type de notification à nettoyer
        days_to_keep (int): Nombre de jours à conserver
    
    Returns:
        dict: Statistiques de suppression
    """
    try:
        # Vérifier que le type existe
        valid_types = [choice[0] for choice in Notification.NOTIFICATION_TYPES]
        if notification_type not in valid_types:
            raise ValueError(f"Type de notification invalide: {notification_type}")
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        notifications_to_delete = Notification.objects.filter(
            notification_type=notification_type,
            created_at__lt=cutoff_date
        )
        
        total_count = notifications_to_delete.count()
        
        if total_count == 0:
            return {
                'status': 'success',
                'deleted_count': 0,
                'notification_type': notification_type,
                'message': f'Aucune notification {notification_type} à supprimer'
            }
        
        deleted_count, _ = notifications_to_delete.delete()
        
        logger.info(
            f"Suppression par type: {deleted_count} notifications '{notification_type}' "
            f"supprimées (plus anciennes que {days_to_keep} jours)"
        )
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'notification_type': notification_type,
            'cutoff_date': cutoff_date.isoformat(),
            'message': f'{deleted_count} notifications {notification_type} supprimées'
        }
        
    except Exception as exc:
        logger.error(
            f"Erreur lors de la suppression des notifications {notification_type}: {str(exc)}"
        )
        
        raise self.retry(
            countdown=30 * (2 ** self.request.retries),
            exc=exc
        )

@shared_task
def cleanup_notifications_comprehensive():
    """
    Tâche de nettoyage complète avec différentes politiques de rétention.
    
    Returns:
        dict: Résumé complet du nettoyage
    """
    results = {
        'total_deleted': 0,
        'operations': []
    }
    
    try:
        # 1. Supprimer les notifications lues anciennes (7 jours)
        read_result = cleanup_read_notifications.delay(days_to_keep=7).get()
        results['operations'].append({
            'operation': 'cleanup_read_notifications',
            'result': read_result
        })
        results['total_deleted'] += read_result.get('deleted_count', 0)
        
        # 2. Supprimer les notifications système anciennes (14 jours)
        system_result = cleanup_notifications_by_type.delay(
            notification_type='system',
            days_to_keep=14
        ).get()
        results['operations'].append({
            'operation': 'cleanup_system_notifications',
            'result': system_result
        })
        results['total_deleted'] += system_result.get('deleted_count', 0)
        
        # 3. Supprimer les notifications de traduction anciennes (30 jours)
        for notif_type in ['translation_complete', 'translation_failed']:
            type_result = cleanup_notifications_by_type.delay(
                notification_type=notif_type,
                days_to_keep=30
            ).get()
            results['operations'].append({
                'operation': f'cleanup_{notif_type}',
                'result': type_result
            })
            results['total_deleted'] += type_result.get('deleted_count', 0)
        
        # 4. Nettoyage général des très anciennes notifications (90 jours)
        general_result = cleanup_old_notifications.delay(days_to_keep=90).get()
        results['operations'].append({
            'operation': 'cleanup_old_notifications',
            'result': general_result
        })
        results['total_deleted'] += general_result.get('deleted_count', 0)
        
        logger.info(f"Nettoyage complet terminé: {results['total_deleted']} notifications supprimées")
        
        return results
        
    except Exception as exc:
        logger.error(f"Erreur lors du nettoyage complet: {str(exc)}")
        return {
            'status': 'error',
            'error': str(exc),
            'partial_results': results
        }