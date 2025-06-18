
# =============================================================================
# APP: translations - Serializers (Gestion des traductions et services)
# =============================================================================

# translations/serializers.py
from rest_framework import serializers
from .models import Language, TranslationService, Translation, TranslationTask


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer pour les langues"""
    class Meta:
        model = Language
        fields = ('id', 'code', 'name', 'native_name', 'is_active')
        read_only_fields = ('id',)


class TranslationServiceSerializer(serializers.ModelSerializer):
    """Serializer pour les services de traduction"""
    supported_languages = LanguageSerializer(source='get_supported_languages', many=True, read_only=True)

    class Meta:
        model = TranslationService
        fields = (
            'id', 'name', 'display_name', 'base_url', 'is_active',
            'daily_quota', 'monthly_quota', 'config', 'supported_languages'
        )
        read_only_fields = ('id', 'supported_languages')
        extra_kwargs = {
            'api_key': {'write_only': True}
        }


class TranslationSerializer(serializers.ModelSerializer):
    """Serializer pour les traductions"""
    language_name = serializers.CharField(source='target_language.name', read_only=True)
    language_code = serializers.CharField(source='target_language.code', read_only=True)
    service_name = serializers.CharField(source='service.display_name', read_only=True)

    class Meta:
        model = Translation
        fields = (
            'id', 'string', 'target_language', 'language_name', 'language_code',
            'translated_text', 'translation_method', 'service', 'service_name',
            'confidence_score', 'created_at', 'updated_at', 'is_approved',
            'characters_count', 'words_count'
        )
        read_only_fields = (
            'id', 'language_name', 'language_code', 'service_name',
            'created_at', 'updated_at', 'characters_count', 'words_count'
        )


class TranslationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des traductions"""
    class Meta:
        model = Translation
        fields = ('string', 'target_language', 'translated_text', 'translation_method', 'service')


class TranslationTaskSerializer(serializers.ModelSerializer):
    """Serializer pour les tâches de traduction"""
    file_name = serializers.CharField(source='file.original_filename', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    service_name = serializers.CharField(source='service.display_name', read_only=True)
    target_languages_names = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = TranslationTask
        fields = (
            'id', 'file', 'file_name', 'user', 'user_email', 'target_languages',
            'target_languages_names', 'service', 'service_name', 'status',
            'progress', 'estimated_word_count', 'actual_word_count',
            'created_at', 'started_at', 'completed_at', 'error_message',
            'retry_count', 'duration'
        )
        read_only_fields = (
            'id', 'file_name', 'user_email', 'service_name', 'target_languages_names',
            'status', 'progress', 'actual_word_count', 'created_at',
            'started_at', 'completed_at', 'duration'
        )

    def get_target_languages_names(self, obj):
        return [lang.name for lang in obj.target_languages.all()]

    def get_duration(self, obj):
        if obj.completed_at and obj.started_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None


class TranslationTaskCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des tâches de traduction"""
    class Meta:
        model = TranslationTask
        fields = ('file', 'target_languages', 'service', 'estimated_word_count')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
