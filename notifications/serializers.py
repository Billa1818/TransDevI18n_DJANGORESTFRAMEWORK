# notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Notification"""
    
    # Champ en lecture seule pour afficher le type lisible
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    
    # Champ calculé pour l'âge de la notification
    time_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'notification_type',
            'notification_type_display',
            'is_read',
            'created_at',
            'related_object_id',
            'related_object_type',
            'action_url',
            'time_since_created'
        ]
        read_only_fields = ['id', 'created_at', 'user']
    
    def get_time_since_created(self, obj):
        """Retourne une représentation lisible du temps écoulé"""
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now())


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'title',
            'message',
            'notification_type',
            'related_object_id',
            'related_object_type',
            'action_url'
        ]
    
    def create(self, validated_data):
        # L'utilisateur sera défini dans la vue
        return super().create(validated_data)


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour des notifications (principalement is_read)"""
    
    class Meta:
        model = Notification
        fields = ['is_read']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer pour les préférences de notification"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_translation_complete',
            'email_translation_failed',
            'email_quota_warnings',
            'email_subscription_alerts',
            'email_payment_alerts',
            'app_translation_complete',
            'app_quota_warnings',
            'app_system_notifications'
        ]
        
    def update(self, instance, validated_data):
        """Met à jour les préférences de notification"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class NotificationListSerializer(serializers.ModelSerializer):
    """Serializer optimisé pour la liste des notifications"""
    
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'notification_type',
            'notification_type_display',
            'is_read',
            'created_at',
            'action_url'
        ]


class NotificationSummarySerializer(serializers.Serializer):
    """Serializer pour un résumé des notifications"""
    
    total_count = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    recent_notifications = NotificationListSerializer(many=True)
    
    class Meta:
        fields = ['total_count', 'unread_count', 'recent_notifications']


class MarkAllAsReadSerializer(serializers.Serializer):
    """Serializer pour marquer toutes les notifications comme lues"""
    
    success = serializers.BooleanField(read_only=True)
    marked_count = serializers.IntegerField(read_only=True)


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des notifications"""
    
    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    notifications_by_type = serializers.DictField()
    recent_activity = serializers.ListField()
    
    class Meta:
        fields = [
            'total_notifications',
            'unread_notifications', 
            'notifications_by_type',
            'recent_activity'
        ]