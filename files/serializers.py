# =============================================================================
# # files/serializers.py
# =============================================================================


from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import TranslationFile, TranslationString
from translations.serializers import TranslationSerializer
User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    """Serializer minimal pour l'utilisateur"""
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')


class TranslationFileListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des fichiers de traduction"""
    uploaded_by = UserMinimalSerializer(read_only=True)
    file_extension = serializers.SerializerMethodField()
    strings_count = serializers.SerializerMethodField()
    processing_progress = serializers.SerializerMethodField()
    
    class Meta:
        model = TranslationFile
        fields = (
            'id', 'original_filename', 'file_type', 'file_size',
            'uploaded_by', 'uploaded_at', 'status', 'total_strings',
            'file_extension', 'strings_count', 'processing_progress'
        )

    def get_file_extension(self, obj):
        """Retourne l'extension du fichier"""
        return obj.original_filename.split('.')[-1].lower() if '.' in obj.original_filename else ''

    def get_strings_count(self, obj):
        """Retourne le nombre de chaînes traduites"""
        return obj.strings.count()

    def get_processing_progress(self, obj):
        """Retourne le progrès de traitement si en cours"""
        if obj.status == 'processing' and hasattr(obj, 'task_id'):
            from celery.result import AsyncResult
            result = AsyncResult(obj.task_id)
            if result.state == 'PROGRESS':
                return result.info.get('current', 0)
        return None
    


class TranslationFileDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un fichier de traduction"""
    uploaded_by = UserMinimalSerializer(read_only=True)
    file_extension = serializers.SerializerMethodField()
    strings_count = serializers.SerializerMethodField()
    translated_count = serializers.SerializerMethodField()
    translation_progress = serializers.SerializerMethodField()
    file_metadata = serializers.SerializerMethodField()
    
    class Meta:
        model = TranslationFile
        fields = (
            'id', 'original_filename', 'file_path', 'file_type', 'file_size',
            'uploaded_by', 'uploaded_at', 'status', 'error_message','task_id',
            'detected_framework', 'encoding', 'total_strings',
            'file_extension', 'strings_count', 'translated_count',
            'translation_progress', 'file_metadata'
        )

    def get_file_extension(self, obj):
        return obj.original_filename.split('.')[-1].lower() if '.' in obj.original_filename else ''

    def get_strings_count(self, obj):
        return obj.strings.count()

    def get_translated_count(self, obj):
        return obj.strings.filter(is_translated=True).count()


    def get_translation_progress(self, obj):
        total = self.get_strings_count(obj)
        if total == 0:
            return 0
        translated = self.get_translated_count(obj)
        return round((translated / total) * 100, 2)

    def get_file_metadata(self, obj):
        """Retourne les métadonnées du fichier"""
        return {
            'lines': obj.total_strings,
            'encoding': obj.encoding,
            'framework': obj.detected_framework,
            'size_human': self._format_file_size(obj.file_size)
        }

    def _format_file_size(self, size_bytes):
        """Formate la taille du fichier"""
        if size_bytes == 0:
            return "0B"
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"


class TranslationFileCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création/upload de fichiers"""
    file = serializers.FileField(write_only=True)
    
    class Meta:
        model = TranslationFile
        fields = ('file',)


    def validate_file(self, value):
        """Valide le fichier uploadé"""
        # Vérifier l'extension
        allowed_extensions = [
            'po', 'json', 'php', 'yml', 'yaml', 'xml', 
            'arb', 'properties', 'csv', 'ts'
        ]
        
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"Extension non supportée. Extensions autorisées: {', '.join(allowed_extensions)}"
            )

        # Vérifier que le fichier n'est pas vide
        if value.size == 0:
            raise serializers.ValidationError("Le fichier ne peut pas être vide")
        # Vérifier la taille (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Le fichier ne peut pas dépasser 10MB")
        
        return value

    def create(self, validated_data):
        file_obj = validated_data.pop('file')
    
        try:
            translation_file = TranslationFile.objects.create(
                original_filename=file_obj.name,
                file_path=file_obj,
                file_type=file_obj.name.split('.')[-1].lower(),
                file_size=file_obj.size,
                uploaded_by=self.context['request'].user,
                status='uploaded'
            )

            from .tasks import process_translation_file
            task = process_translation_file.delay(translation_file.id)
            translation_file.task_id = task.id
            translation_file.status = 'processing'
            translation_file.save()
        
            return translation_file
        except Exception as e:
            # Logger l'erreur et nettoyer si nécessaire
            if 'translation_file' in locals():
                translation_file.delete()
            raise serializers.ValidationError(f"Erreur lors de la création du fichier: {str(e)}")

class TranslationStringListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des chaînes de traduction"""
    file_name = serializers.CharField(source='file.original_filename', read_only=True)
    translations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TranslationString
        fields = (
            'id', 'file', 'file_name', 'key', 'source_text', 'context',
            'is_translated', 'is_fuzzy', 'is_plural', 'line_number',
            'created_at', 'translations_count'
        )

    def get_translations_count(self, obj):
        return obj.translations.count() if hasattr(obj, 'translations') else 0


class TranslationStringDetailSerializer(TranslationStringListSerializer):
    """Serializer détaillé pour une chaîne avec ses traductions"""
    translations = TranslationSerializer(many=True, read_only=True)
    file_details = TranslationFileListSerializer(source='file', read_only=True)

    class Meta(TranslationStringListSerializer.Meta):
        fields = TranslationStringListSerializer.Meta.fields + (
            'translations', 'file_details'
        )

