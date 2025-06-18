
# =============================================================================
# APP: notifications (Système de notifications)
# =============================================================================

# notifications/models.py
from django.db import models
from django.conf import settings
import uuid
class Notification(models.Model):
    id= models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Notifications utilisateur"""
    NOTIFICATION_TYPES = [
        ('translation_complete', 'Translation Complete'),
        ('translation_failed', 'Translation Failed'),
        ('quota_warning', 'Quota Warning'),
        ('quota_exceeded', 'Quota Exceeded'),
        ('subscription_expiring', 'Subscription Expiring'),
        ('subscription_expired', 'Subscription Expired'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('system_notification', 'System Notification'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Données contextuelles
    related_object_id = models.IntegerField(blank=True, null=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    action_url = models.URLField(blank=True)
    
    def mark_as_read(self):
        """Marque la notification comme lue"""
        self.is_read = True
        self.save()
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    class Meta:
        ordering = ['-created_at']

class NotificationPreference(models.Model):
    id= models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Préférences de notification par utilisateur"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email notifications
    email_translation_complete = models.BooleanField(default=True)
    email_translation_failed = models.BooleanField(default=True)
    email_quota_warnings = models.BooleanField(default=True)
    email_subscription_alerts = models.BooleanField(default=True)
    email_payment_alerts = models.BooleanField(default=True)
    
    # In-app notifications
    app_translation_complete = models.BooleanField(default=True)
    app_quota_warnings = models.BooleanField(default=True)
    app_system_notifications = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
