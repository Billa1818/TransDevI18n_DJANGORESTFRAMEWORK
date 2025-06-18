
# =============================================================================
# APP: usage - Serializers (Suivi de l'utilisation)
# =============================================================================

# usage/serializers.py
from rest_framework import serializers
from .models import WordUsage, QuotaLimit


class WordUsageSerializer(serializers.ModelSerializer):
    """Serializer pour l'usage des mots"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    task_id = serializers.IntegerField(source='task.id', read_only=True)

    class Meta:
        model = WordUsage
        fields = (
            'id', 'user', 'user_email', 'task', 'task_id', 'words_used',
            'usage_date', 'service_used', 'source_language', 'target_languages',
            'file_type'
        )
        read_only_fields = ('id', 'user_email', 'task_id', 'usage_date')


class UsageStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques d'usage"""
    daily_usage = serializers.IntegerField()
    monthly_usage = serializers.IntegerField()
    total_usage = serializers.IntegerField()
    remaining_quota = serializers.IntegerField()


class QuotaLimitSerializer(serializers.ModelSerializer):
    """Serializer pour les limites de quota"""
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = QuotaLimit
        fields = (
            'id', 'user', 'user_email', 'daily_limit_override',
            'monthly_limit_override', 'is_unlimited', 'created_at'
        )
        read_only_fields = ('id', 'user_email', 'created_at')

