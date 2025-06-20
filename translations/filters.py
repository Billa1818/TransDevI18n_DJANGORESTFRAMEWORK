# =============================================================================
# APP: translations - Filtres personnalisés
# =============================================================================

# translations/filters.py
from django_filters import rest_framework as filters
from django.db.models import Q
from django.db import models
from .models import Translation, TranslationTask, Language
from files.models import TranslationFile


class TranslationFilter(filters.FilterSet):
    """
    Filtres pour les traductions
    """
    # Filtres de texte
    search = filters.CharFilter(method='search_filter', label='Recherche')
    key_contains = filters.CharFilter(field_name='string__key', lookup_expr='icontains', label='Clé contient')
    source_text_contains = filters.CharFilter(field_name='string__source_text', lookup_expr='icontains', label='Texte source contient')
    translated_text_contains = filters.CharFilter(field_name='translated_text', lookup_expr='icontains', label='Texte traduit contient')
    
    # Filtres de langue
    target_language = filters.ModelChoiceFilter(queryset=Language.objects.filter(is_active=True), label='Langue cible')
    target_language_code = filters.CharFilter(field_name='target_language__code', lookup_expr='exact', label='Code langue cible')
    
    # Filtres de fichier
    file_id = filters.UUIDFilter(field_name='string__file_id', label='ID du fichier')
    file_name_contains = filters.CharFilter(field_name='string__file__original_filename', lookup_expr='icontains', label='Nom du fichier contient')
    
    # Filtres de qualité
    is_approved = filters.BooleanFilter(label='Approuvé')
    confidence_min = filters.NumberFilter(field_name='confidence_score', lookup_expr='gte', label='Confiance minimum')
    confidence_max = filters.NumberFilter(field_name='confidence_score', lookup_expr='lte', label='Confiance maximum')
    confidence_range = filters.RangeFilter(field_name='confidence_score', label='Plage de confiance')
    
    # Filtres de date
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')
    updated_after = filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte', label='Modifié après')
    updated_before = filters.DateTimeFilter(field_name='updated_at', lookup_expr='lte', label='Modifié avant')
    
    # Filtres de statistiques
    word_count_min = filters.NumberFilter(field_name='words_count', lookup_expr='gte', label='Nombre de mots minimum')
    word_count_max = filters.NumberFilter(field_name='words_count', lookup_expr='lte', label='Nombre de mots maximum')
    char_count_min = filters.NumberFilter(field_name='characters_count', lookup_expr='gte', label='Nombre de caractères minimum')
    char_count_max = filters.NumberFilter(field_name='characters_count', lookup_expr='lte', label='Nombre de caractères maximum')
    
    # Filtres spéciaux
    needs_review = filters.BooleanFilter(method='needs_review_filter', label='Nécessite une révision')
    high_quality = filters.BooleanFilter(method='high_quality_filter', label='Haute qualité')
    low_quality = filters.BooleanFilter(method='low_quality_filter', label='Faible qualité')
    
    class Meta:
        model = Translation
        fields = {
            'id': ['exact'],
            'string__key': ['exact', 'icontains', 'istartswith', 'iendswith'],
            'translated_text': ['exact', 'icontains', 'istartswith', 'iendswith'],
            'confidence_score': ['exact', 'gte', 'lte'],
            'is_approved': ['exact'],
            'created_at': ['exact', 'gte', 'lte'],
            'updated_at': ['exact', 'gte', 'lte'],
        }
    
    def search_filter(self, queryset, name, value):
        """
        Recherche dans la clé, le texte source et le texte traduit
        """
        return queryset.filter(
            Q(string__key__icontains=value) |
            Q(string__source_text__icontains=value) |
            Q(translated_text__icontains=value)
        )
    
    def needs_review_filter(self, queryset, name, value):
        """
        Filtre les traductions qui nécessitent une révision
        """
        if value:
            return queryset.filter(
                Q(is_approved=False) | Q(confidence_score__lte=0.70)
            )
        return queryset
    
    def high_quality_filter(self, queryset, name, value):
        """
        Filtre les traductions de haute qualité
        """
        if value:
            return queryset.filter(
                Q(is_approved=True) & Q(confidence_score__gt=0.70)
            )
        return queryset
    
    def low_quality_filter(self, queryset, name, value):
        """
        Filtre les traductions de faible qualité
        """
        if value:
            return queryset.filter(
                Q(is_approved=False) | Q(confidence_score__lte=0.70)
            )
        return queryset


class TranslationTaskFilter(filters.FilterSet):
    """
    Filtres pour les tâches de traduction
    """
    # Filtres de texte
    search = filters.CharFilter(method='search_filter', label='Recherche')
    file_name_contains = filters.CharFilter(field_name='file__original_filename', lookup_expr='icontains', label='Nom du fichier contient')
    
    # Filtres de statut
    status = filters.ChoiceFilter(choices=TranslationTask.STATUS_CHOICES, label='Statut')
    status_in = filters.MultipleChoiceFilter(choices=TranslationTask.STATUS_CHOICES, label='Statuts')
    
    # Filtres d'utilisateur
    user_email = filters.CharFilter(field_name='user__email', lookup_expr='icontains', label='Email utilisateur')
    user_username = filters.CharFilter(field_name='user__username', lookup_expr='icontains', label='Nom d\'utilisateur')
    
    # Filtres de langue
    target_language = filters.ModelChoiceFilter(queryset=Language.objects.filter(is_active=True), label='Langue cible')
    target_language_code = filters.CharFilter(field_name='target_languages__code', lookup_expr='exact', label='Code langue cible')
    
    # Filtres de progression
    progress_min = filters.NumberFilter(field_name='progress', lookup_expr='gte', label='Progression minimum')
    progress_max = filters.NumberFilter(field_name='progress', lookup_expr='lte', label='Progression maximum')
    progress_range = filters.RangeFilter(field_name='progress', label='Plage de progression')
    
    # Filtres de mots
    word_count_min = filters.NumberFilter(field_name='actual_word_count', lookup_expr='gte', label='Nombre de mots minimum')
    word_count_max = filters.NumberFilter(field_name='actual_word_count', lookup_expr='lte', label='Nombre de mots maximum')
    
    # Filtres de date
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')
    started_after = filters.DateTimeFilter(field_name='started_at', lookup_expr='gte', label='Démarré après')
    started_before = filters.DateTimeFilter(field_name='started_at', lookup_expr='lte', label='Démarré avant')
    completed_after = filters.DateTimeFilter(field_name='completed_at', lookup_expr='gte', label='Terminé après')
    completed_before = filters.DateTimeFilter(field_name='completed_at', lookup_expr='lte', label='Terminé avant')
    
    # Filtres spéciaux
    has_error = filters.BooleanFilter(method='has_error_filter', label='A une erreur')
    is_stuck = filters.BooleanFilter(method='is_stuck_filter', label='Bloquée')
    is_recent = filters.BooleanFilter(method='is_recent_filter', label='Récente')
    
    class Meta:
        model = TranslationTask
        fields = {
            'id': ['exact'],
            'status': ['exact', 'in'],
            'progress': ['exact', 'gte', 'lte'],
            'actual_word_count': ['exact', 'gte', 'lte'],
            'estimated_word_count': ['exact', 'gte', 'lte'],
            'retry_count': ['exact', 'gte', 'lte'],
            'created_at': ['exact', 'gte', 'lte'],
            'started_at': ['exact', 'gte', 'lte'],
            'completed_at': ['exact', 'gte', 'lte'],
        }
    
    def search_filter(self, queryset, name, value):
        """
        Recherche dans le nom du fichier et les messages d'erreur
        """
        return queryset.filter(
            Q(file__original_filename__icontains=value) |
            Q(error_message__icontains=value)
        )
    
    def has_error_filter(self, queryset, name, value):
        """
        Filtre les tâches qui ont des erreurs
        """
        if value:
            return queryset.filter(
                Q(status='failed') | Q(error_message__isnull=False)
            )
        return queryset
    
    def is_stuck_filter(self, queryset, name, value):
        """
        Filtre les tâches qui semblent bloquées
        """
        if value:
            from django.utils import timezone
            from datetime import timedelta
            
            # Tâches en cours depuis plus de 1 heure
            one_hour_ago = timezone.now() - timedelta(hours=1)
            return queryset.filter(
                Q(status='in_progress', started_at__lt=one_hour_ago) |
                Q(status='pending', created_at__lt=one_hour_ago)
            )
        return queryset
    
    def is_recent_filter(self, queryset, name, value):
        """
        Filtre les tâches récentes (créées dans les dernières 24h)
        """
        if value:
            from django.utils import timezone
            from datetime import timedelta
            
            one_day_ago = timezone.now() - timedelta(days=1)
            return queryset.filter(created_at__gte=one_day_ago)
        return queryset


class LanguageFilter(filters.FilterSet):
    """
    Filtres pour les langues
    """
    search = filters.CharFilter(method='search_filter', label='Recherche')
    code_contains = filters.CharFilter(field_name='code', lookup_expr='icontains', label='Code contient')
    name_contains = filters.CharFilter(field_name='name', lookup_expr='icontains', label='Nom contient')
    native_name_contains = filters.CharFilter(field_name='native_name', lookup_expr='icontains', label='Nom natif contient')
    
    # Filtres de statut
    is_active = filters.BooleanFilter(label='Active')
    
    # Filtres de statistiques
    has_translations = filters.BooleanFilter(method='has_translations_filter', label='A des traductions')
    translation_count_min = filters.NumberFilter(method='translation_count_min_filter', label='Nombre de traductions minimum')
    translation_count_max = filters.NumberFilter(method='translation_count_max_filter', label='Nombre de traductions maximum')
    
    class Meta:
        model = Language
        fields = {
            'code': ['exact', 'icontains', 'istartswith', 'iendswith'],
            'name': ['exact', 'icontains', 'istartswith', 'iendswith'],
            'native_name': ['exact', 'icontains', 'istartswith', 'iendswith'],
            'is_active': ['exact'],
        }
    
    def search_filter(self, queryset, name, value):
        """
        Recherche dans le code, le nom et le nom natif
        """
        return queryset.filter(
            Q(code__icontains=value) |
            Q(name__icontains=value) |
            Q(native_name__icontains=value)
        )
    
    def has_translations_filter(self, queryset, name, value):
        """
        Filtre les langues qui ont des traductions
        """
        if value:
            return queryset.filter(translation__isnull=False).distinct()
        return queryset
    
    def translation_count_min_filter(self, queryset, name, value):
        """
        Filtre les langues avec un nombre minimum de traductions
        """
        return queryset.annotate(
            translation_count=models.Count('translation')
        ).filter(translation_count__gte=value)
    
    def translation_count_max_filter(self, queryset, name, value):
        """
        Filtre les langues avec un nombre maximum de traductions
        """
        return queryset.annotate(
            translation_count=models.Count('translation')
        ).filter(translation_count__lte=value) 