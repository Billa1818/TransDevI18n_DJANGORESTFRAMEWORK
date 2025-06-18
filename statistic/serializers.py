
# =============================================================================
# APP: statistics - Serializers (Statistiques et analytics)
# =============================================================================

# statistics/serializers.py
from rest_framework import serializers
from .models import UserStatistics, SystemStatistics


class UserStatisticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques utilisateur"""
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = UserStatistics
        fields = (
            'id', 'user', 'user_email', 'total_files_processed',
            'total_strings_translated', 'total_words_translated',
            'total_characters_translated', 'average_processing_time',
            'average_file_size', 'most_used_service', 'most_translated_language',
            'last_updated', 'first_translation_date'
        )
        read_only_fields = ('id', 'user_email', 'last_updated')


class SystemStatisticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques système"""
    class Meta:
        model = SystemStatistics
        fields = (
            'id', 'date', 'daily_translations', 'daily_words_translated',
            'daily_active_users', 'daily_new_users', 'google_translate_usage',
            'deepl_usage', 'azure_usage', 'argos_usage', 'language_stats',
            'average_processing_time', 'error_rate'
        )
        read_only_fields = ('id',)

