# =============================================================================
# APP: translations - Serializers (Gestion des traductions avec Google Translate)
# =============================================================================

# translations/serializers.py
from rest_framework import serializers
from django.db import models
from .models import Language, Translation, TranslationTask
from files.models import TranslationFile, TranslationString


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer pour les langues"""
    class Meta:
        model = Language
        fields = ('id', 'code', 'name', 'native_name', 'is_active')
        read_only_fields = ('id',)


class TranslationSerializer(serializers.ModelSerializer):
    """Serializer pour les traductions avec Google Translate"""
    language_name = serializers.CharField(source='target_language.name', read_only=True)
    language_code = serializers.CharField(source='target_language.code', read_only=True)
    string_key = serializers.CharField(source='string.key', read_only=True)
    source_text = serializers.CharField(source='string.source_text', read_only=True)

    class Meta:
        model = Translation
        fields = (
            'id', 'string', 'string_key', 'source_text', 'target_language', 'language_name', 'language_code',
            'translated_text', 'confidence_score', 'created_at', 'updated_at', 
            'is_approved', 'characters_count', 'words_count'
        )
        read_only_fields = (
            'id', 'language_name', 'language_code', 'string_key', 'source_text', 'created_at', 'updated_at', 
            'characters_count', 'words_count'
        )


class TranslationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des traductions"""
    class Meta:
        model = Translation
        fields = ('string', 'target_language', 'translated_text')


class TranslationTaskSerializer(serializers.ModelSerializer):
    """Serializer pour les tâches de traduction avec Google Translate"""
    file_name = serializers.CharField(source='file.original_filename', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    target_languages_names = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = TranslationTask
        fields = (
            'id', 'file', 'file_name', 'user', 'user_email', 'target_languages',
            'target_languages_names', 'status', 'progress', 'estimated_word_count', 
            'actual_word_count', 'created_at', 'started_at', 'completed_at', 
            'error_message', 'retry_count', 'duration'
        )
        read_only_fields = (
            'id', 'file_name', 'user_email', 'target_languages_names',
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
        fields = ('file', 'target_languages', 'estimated_word_count')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class FileTranslationSummarySerializer(serializers.ModelSerializer):
    """Serializer pour le résumé des traductions d'un fichier"""
    detected_language_name = serializers.SerializerMethodField()
    translations_by_language = serializers.SerializerMethodField()
    
    class Meta:
        model = TranslationFile
        fields = (
            'id', 'original_filename', 'total_strings', 'detected_language', 
            'detected_language_confidence', 'detected_language_name', 'translations_by_language'
        )
    
    def get_detected_language_name(self, obj):
        if obj.detected_language:
            try:
                language = Language.objects.get(code=obj.detected_language)
                return language.name
            except Language.DoesNotExist:
                return obj.detected_language
        return None
    
    def get_translations_by_language(self, obj):
        from .models import Translation
        target_languages = Language.objects.filter(is_active=True)
        result = []
        
        for language in target_languages:
            translated_count = Translation.objects.filter(
                string__file=obj,
                target_language=language
            ).count()
            
            result.append({
                'language_code': language.code,
                'language_name': language.name,
                'translated_count': translated_count,
                'total_count': obj.total_strings,
                'progress_percentage': (translated_count / obj.total_strings * 100) if obj.total_strings > 0 else 0
            })
        
        return result


class FileTranslationStatusSerializer(serializers.Serializer):
    """Serializer pour vérifier le statut des traductions d'un fichier"""
    file_id = serializers.UUIDField()
    file_name = serializers.CharField()
    has_translations = serializers.BooleanField()
    total_strings = serializers.IntegerField()
    total_translations = serializers.IntegerField()
    languages_with_translations = serializers.ListField(child=serializers.CharField())
    translation_languages_count = serializers.IntegerField()
    overall_progress = serializers.FloatField()
    last_translation_date = serializers.DateTimeField(allow_null=True)
    needs_attention = serializers.BooleanField()
    attention_reasons = serializers.ListField(child=serializers.CharField(), required=False)


class FileTranslationsDetailSerializer(serializers.ModelSerializer):
    """Serializer pour les détails des traductions d'un fichier"""
    translations = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    
    class Meta:
        model = TranslationFile
        fields = (
            'id', 'original_filename', 'file_type', 'total_strings', 
            'detected_language', 'detected_language_confidence', 'uploaded_at',
            'translations', 'summary'
        )
    
    def get_translations(self, obj):
        """Récupère toutes les traductions du fichier groupées par langue"""
        from .models import Translation
        
        translations_by_language = {}
        target_languages = Language.objects.filter(is_active=True)
        
        for language in target_languages:
            translations = Translation.objects.filter(
                string__file=obj,
                target_language=language
            ).select_related('string', 'target_language').order_by('string__key')
            
            if translations.exists():
                translations_by_language[language.code] = {
                    'language_name': language.name,
                    'language_code': language.code,
                    'translations_count': translations.count(),
                    'approved_count': translations.filter(is_approved=True).count(),
                    'pending_count': translations.filter(is_approved=False).count(),
                    'average_confidence': translations.aggregate(
                        avg_confidence=models.Avg('confidence_score')
                    )['avg_confidence'] or 0.0,
                    'translations': TranslationSerializer(translations, many=True).data
                }
        
        return translations_by_language
    
    def get_summary(self, obj):
        """Récupère un résumé des traductions"""
        from .models import Translation
        
        total_translations = Translation.objects.filter(string__file=obj).count()
        approved_translations = Translation.objects.filter(string__file=obj, is_approved=True).count()
        languages_count = Translation.objects.filter(string__file=obj).values('target_language').distinct().count()
        
        return {
            'total_translations': total_translations,
            'approved_translations': approved_translations,
            'pending_translations': total_translations - approved_translations,
            'languages_count': languages_count,
            'approval_rate': (approved_translations / total_translations * 100) if total_translations > 0 else 0,
            'overall_progress': (total_translations / (obj.total_strings * languages_count) * 100) if obj.total_strings > 0 and languages_count > 0 else 0
        }


class TranslationStringSerializer(serializers.ModelSerializer):
    """Serializer pour les chaînes de traduction avec leurs traductions"""
    translations = TranslationSerializer(many=True, read_only=True)
    
    class Meta:
        model = TranslationString
        fields = (
            'id', 'key', 'source_text', 'context', 'comment',
            'line_number', 'is_fuzzy', 'is_plural', 'created_at', 'translations'
        )
        read_only_fields = ('id', 'created_at')


class FileTranslationProgressSerializer(serializers.Serializer):
    """Serializer pour la progression des traductions"""
    task_id = serializers.IntegerField()
    status = serializers.CharField()
    progress = serializers.FloatField()
    total_strings = serializers.IntegerField()
    translated_strings = serializers.IntegerField()
    estimated_words = serializers.IntegerField()
    actual_words = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    error_message = serializers.CharField(allow_blank=True)


class TranslationCorrectionSerializer(serializers.ModelSerializer):
    """Serializer pour corriger manuellement une traduction"""
    
    class Meta:
        model = Translation
        fields = ['translated_text', 'is_approved']
    
    def update(self, instance, validated_data):
        # Mettre à jour le texte traduit
        if 'translated_text' in validated_data:
            instance.translated_text = validated_data['translated_text']
        
        # Marquer comme approuvé si demandé
        if 'is_approved' in validated_data:
            instance.is_approved = validated_data['is_approved']
        
        instance.save()
        return instance


class TranslationCorrectionRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes de correction de traduction"""
    translation_id = serializers.UUIDField()
    corrected_text = serializers.CharField(max_length=10000)
    is_approved = serializers.BooleanField(default=True)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)


class FailedTranslationsFilterSerializer(serializers.Serializer):
    """Serializer pour filtrer les traductions échouées"""
    file_id = serializers.UUIDField(required=False)
    target_language = serializers.CharField(max_length=10, required=False)
    is_approved = serializers.BooleanField(required=False)
    confidence_min = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
    confidence_max = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
