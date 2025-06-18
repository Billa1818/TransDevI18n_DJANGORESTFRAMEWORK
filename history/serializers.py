
# =============================================================================
# APP: history - Serializers (Historique et projets)
# =============================================================================

# history/serializers.py
from rest_framework import serializers
from .models import TranslationHistory


class TranslationHistorySerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des traductions"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    original_filename = serializers.CharField(source='original_file.original_filename', read_only=True)
    file_type = serializers.CharField(source='original_file.file_type', read_only=True)
    download_urls = serializers.SerializerMethodField()

    class Meta:
        model = TranslationHistory
        fields = (
            'id', 'user', 'user_email', 'original_file', 'original_filename',
            'file_type', 'task', 'translated_files', 'download_urls',
            'target_languages', 'strings_translated', 'words_translated',
            'success_rate', 'processing_time', 'created_at', 'service_used'
        )
        read_only_fields = (
            'id', 'user_email', 'original_filename', 'file_type', 'download_urls',
            'created_at'
        )

    def get_download_urls(self, obj):
        return {lang: obj.get_download_url(lang) for lang in obj.target_languages}


# =============================================================================
# APP: notifications - Serializers (Système de notifications)
# =============================================================================

# notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications"""
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Notification
        fields = (
            'id', 'user', 'user_email', 'title', 'message', 'notification_type',
            'is_read', 'created_at', 'related_object_id', 'related_object_type',
            'action_url'
        )
        read_only_fields = ('id', 'user_email', 'created_at')


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer pour les préférences de notification"""
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = NotificationPreference
        fields = (
            'id', 'user', 'user_email', 'email_translation_complete',
            'email_translation_failed', 'email_quota_warnings',
            'email_subscription_alerts', 'email_payment_alerts',
            'app_translation_complete', 'app_quota_warnings',
            'app_system_notifications'
        )
        read_only_fields = ('id', 'user_email')
