# =============================================================================
# files/filters.py
# =============================================================================

import django_filters
from django_filters import rest_framework as filters
from .models import TranslationFile, TranslationString


class TranslationFileFilter(filters.FilterSet):
    """Filtres pour les fichiers de traduction"""
    
    # Filtres par statut
    status = filters.ChoiceFilter(choices=TranslationFile.STATUS_CHOICES)
    
    # Filtres par type de fichier
    file_type = filters.CharFilter(lookup_expr='iexact')
    file_extension = filters.CharFilter(method='filter_by_extension')
    
    # Filtres par utilisateur
    uploaded_by = filters.NumberFilter(field_name='uploaded_by__id')
    uploaded_by_email = filters.CharFilter(
        field_name='uploaded_by__email', 
        lookup_expr='icontains'
    )
    
    # Filtres par date
    uploaded_after = filters.DateTimeFilter(
        field_name='uploaded_at', 
        lookup_expr='gte'
    )
    uploaded_before = filters.DateTimeFilter(
        field_name='uploaded_at', 
        lookup_expr='lte'
    )
    uploaded_date = filters.DateFilter(
        field_name='uploaded_at__date'
    )
    
    # Filtres par taille
    file_size_min = filters.NumberFilter(
        field_name='file_size', 
        lookup_expr='gte'
    )
    file_size_max = filters.NumberFilter(
        field_name='file_size', 
        lookup_expr='lte'
    )
    
    # Filtres par nom de fichier
    filename = filters.CharFilter(
        field_name='original_filename', 
        lookup_expr='icontains'
    )
    
    # Filtres par framework détecté
    framework = filters.CharFilter(
        field_name='detected_framework', 
        lookup_expr='iexact'
    )
    
    # Filtre par nombre de chaînes
    has_strings = filters.BooleanFilter(method='filter_has_strings')
    strings_count_min = filters.NumberFilter(method='filter_strings_count_min')
    strings_count_max = filters.NumberFilter(method='filter_strings_count_max')

    class Meta:
        model = TranslationFile
        fields = [
            'status', 'file_type', 'uploaded_by', 'uploaded_date'
        ]

    def filter_by_extension(self, queryset, name, value):
        """Filtre par extension de fichier"""
        return queryset.filter(original_filename__iendswith=f'.{value}')

    def filter_has_strings(self, queryset, name, value):
        """Filtre les fichiers qui ont des chaînes ou non"""
        if value:
            return queryset.filter(translationstring__isnull=False).distinct()
        else:
            return queryset.filter(translationstring__isnull=True)

    def filter_strings_count_min(self, queryset, name, value):
        """Filtre par nombre minimum de chaînes"""
        from django.db.models import Count
        return queryset.annotate(
            strings_count=Count('translationstring')
        ).filter(strings_count__gte=value)

    def filter_strings_count_max(self, queryset, name, value):
        """Filtre par nombre maximum de chaînes"""
        from django.db.models import Count
        return queryset.annotate(
            strings_count=Count('translationstring')
        ).filter(strings_count__lte=value)


class TranslationStringFilter(filters.FilterSet):
    """Filtres pour les chaînes de traduction"""
    
    # Filtres de recherche
    search = filters.CharFilter(method='search_filter')
    key_contains = filters.CharFilter(field_name='key', lookup_expr='icontains')
    source_text_contains = filters.CharFilter(field_name='source_text', lookup_expr='icontains')
    context_contains = filters.CharFilter(field_name='context', lookup_expr='icontains')
    comment_contains = filters.CharFilter(field_name='comment', lookup_expr='icontains')
    
    # Filtres de fichier
    file_id = filters.UUIDFilter(field_name='file__id')
    file_name_contains = filters.CharFilter(field_name='file__original_filename', lookup_expr='icontains')
    file_type = filters.CharFilter(field_name='file__file_type')
    file_status = filters.CharFilter(field_name='file__status')
    
    # Filtres de statut
    is_fuzzy = filters.BooleanFilter()
    is_plural = filters.BooleanFilter()
    
    # Filtres de date
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Filtres spéciaux
    has_translations = filters.BooleanFilter(method='has_translations_filter')
    needs_translation = filters.BooleanFilter(method='needs_translation_filter')
    
    class Meta:
        model = TranslationString
        fields = [
            'file', 'is_fuzzy', 'is_plural'
        ]

    def search_filter(self, queryset, name, value):
        """Recherche globale dans key, source_text et context"""
        from django.db.models import Q
        return queryset.filter(
            Q(key__icontains=value) |
            Q(source_text__icontains=value) |
            Q(context__icontains=value)
        )

    def has_translations_filter(self, queryset, name, value):
        """Filtre les chaînes qui ont des traductions ou non"""
        if value:
            return queryset.filter(translations__isnull=False).distinct()
        else:
            return queryset.filter(translations__isnull=True)

    def needs_translation_filter(self, queryset, name, value):
        """Filtre les chaînes qui nécessitent une traduction"""
        if value:
            return queryset.filter(translations__isnull=True)
        else:
            return queryset.filter(translations__isnull=False)

