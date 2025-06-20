# translations/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import json

from .models import Language, Translation, TranslationTask


class LanguageFilter(admin.SimpleListFilter):
    """Filtre personnalisé pour les langues"""
    title = 'Langue'
    parameter_name = 'language'

    def lookups(self, request, model_admin):
        languages = Language.objects.filter(is_active=True)
        return [(lang.code, f"{lang.name} ({lang.code})") for lang in languages]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(target_language__code=self.value())
        return queryset


class ApprovalStatusFilter(admin.SimpleListFilter):
    """Filtre pour le statut d'approbation"""
    title = 'Statut d\'approbation'
    parameter_name = 'approval'

    def lookups(self, request, model_admin):
        return [
            ('approved', 'Approuvées'),
            ('pending', 'En attente'),
            ('high_confidence', 'Haute confiance (>90%)'),
            ('low_confidence', 'Faible confiance (≤70%)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'approved':
            return queryset.filter(is_approved=True)
        elif self.value() == 'pending':
            return queryset.filter(is_approved=False)
        elif self.value() == 'high_confidence':
            return queryset.filter(confidence_score__gte=0.9)
        elif self.value() == 'low_confidence':
            return queryset.filter(confidence_score__lte=0.70)
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    """Filtre par période"""
    title = 'Période de création'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Aujourd\'hui'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois'),
            ('quarter', 'Ce trimestre'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'week':
            start_week = now - timedelta(days=7)
            return queryset.filter(created_at__gte=start_week)
        elif self.value() == 'month':
            start_month = now.replace(day=1)
            return queryset.filter(created_at__gte=start_month)
        elif self.value() == 'quarter':
            quarter_start = now.replace(month=((now.month-1)//3)*3+1, day=1)
            return queryset.filter(created_at__gte=quarter_start)
        return queryset


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'native_name', 'is_active', 'translation_count']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'native_name']
    list_editable = ['is_active']
    ordering = ['name']

    def translation_count(self, obj):
        """Nombre de traductions dans cette langue"""
        count = obj.translation_set.count()
        if count > 0:
            url = reverse('admin:translations_translation_changelist')
            return format_html(
                '<a href="{}?target_language__id__exact={}">{} traductions</a>',
                url, obj.id, count
            )
        return "0"
    translation_count.short_description = "Traductions"


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = [
        'string_key', 'source_text_preview', 'target_language', 'translated_text_preview',
        'confidence_display', 'approval_status', 'word_count_display', 'created_at'
    ]
    list_filter = [
        LanguageFilter, ApprovalStatusFilter, DateRangeFilter,
        'is_approved', 'target_language', 'created_at'
    ]
    search_fields = [
        'string__key', 'string__source_text', 'translated_text',
        'target_language__name', 'target_language__code'
    ]
    readonly_fields = ['characters_count', 'words_count', 'created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Information principale', {
            'fields': ('string', 'target_language', 'translated_text')
        }),
        ('Qualité', {
            'fields': ('confidence_score', 'is_approved'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('characters_count', 'words_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_translations', 'reject_translations', 'export_translations']

    def string_key(self, obj):
        """Clé de traduction avec lien"""
        if obj.string:
            return format_html(
                '<a href="{}" title="{}">{}</a>',
                reverse('admin:files_translationstring_change', args=[obj.string.id]),
                obj.string.source_text[:100] + ('...' if len(obj.string.source_text) > 100 else ''),
                obj.string.key
            )
        return "-"
    string_key.short_description = "Clé"
    string_key.admin_order_field = 'string__key'

    def source_text_preview(self, obj):
        """Aperçu du texte source"""
        if obj.string and obj.string.source_text:
            text = obj.string.source_text
            if len(text) > 50:
                return text[:50] + '...'
            return text
        return "-"
    source_text_preview.short_description = "Texte source"

    def translated_text_preview(self, obj):
        """Aperçu du texte traduit"""
        if obj.translated_text:
            if len(obj.translated_text) > 50:
                return obj.translated_text[:50] + '...'
            return obj.translated_text
        return "-"
    translated_text_preview.short_description = "Traduction"

    def confidence_display(self, obj):
        """Affichage coloré du score de confiance"""
        if obj.confidence_score is None:
            return format_html('<span style="color: gray;">N/A</span>')
        
        score = round(obj.confidence_score * 100, 1)
        if score >= 90:
            color = 'green'
        elif score > 70:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, score
        )
    confidence_display.short_description = "Confiance"
    confidence_display.admin_order_field = 'confidence_score'

    def approval_status(self, obj):
        """Statut d'approbation avec icône"""
        if obj.is_approved:
            return format_html(
                '<span style="color: green;">✓ Approuvée</span>'
            )
        else:
            return format_html(
                '<span style="color: orange;">⏳ En attente</span>'
            )
    approval_status.short_description = "Statut"
    approval_status.admin_order_field = 'is_approved'

    def word_count_display(self, obj):
        """Affichage du nombre de mots"""
        return "{} mots".format(obj.words_count)
    word_count_display.short_description = "Mots"
    word_count_display.admin_order_field = 'words_count'

    def approve_translations(self, request, queryset):
        """Approuver les traductions sélectionnées"""
        updated = queryset.update(is_approved=True)
        self.message_user(
            request,
            f"{updated} traduction(s) approuvée(s) avec succès."
        )
    approve_translations.short_description = "Approuver les traductions sélectionnées"

    def reject_translations(self, request, queryset):
        """Rejeter les traductions sélectionnées"""
        updated = queryset.update(is_approved=False)
        self.message_user(
            request,
            f"{updated} traduction(s) rejetée(s)."
        )
    reject_translations.short_description = "Rejeter les traductions sélectionnées"

    def export_translations(self, request, queryset):
        """Exporter les traductions sélectionnées"""
        # Logique d'export à implémenter
        self.message_user(
            request,
            f"Export de {queryset.count()} traduction(s) en cours..."
        )
    export_translations.short_description = "Exporter les traductions sélectionnées"


class TaskStatusFilter(admin.SimpleListFilter):
    """Filtre pour le statut des tâches"""
    title = 'Statut de la tâche'
    parameter_name = 'task_status'

    def lookups(self, request, model_admin):
        return [
            ('pending', 'En attente'),
            ('in_progress', 'En cours'),
            ('completed', 'Terminées'),
            ('failed', 'Échouées'),
            ('cancelled', 'Annulées'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


@admin.register(TranslationTask)
class TranslationTaskAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'file_name', 'user', 'status_display', 'progress_bar',
        'languages_list', 'word_count_info', 'created_at'
    ]
    list_filter = [
        TaskStatusFilter, 'status', 'created_at', 'user'
    ]
    search_fields = [
        'file__original_filename', 'user__username', 'user__email'
    ]
    readonly_fields = [
        'progress', 'actual_word_count', 'created_at', 
        'started_at', 'completed_at', 'retry_count'
    ]
    
    fieldsets = (
        ('Information principale', {
            'fields': ('file', 'user', 'target_languages', 'status')
        }),
        ('Progression', {
            'fields': ('progress', 'estimated_word_count', 'actual_word_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Gestion des erreurs', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        }),
    )

    actions = ['restart_failed_tasks', 'cancel_pending_tasks']

    def file_name(self, obj):
        """Nom du fichier avec lien"""
        if obj.file:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:files_translationfile_change', args=[obj.file.id]),
                obj.file.original_filename
            )
        return "-"
    file_name.short_description = "Fichier"

    def status_display(self, obj):
        """Affichage du statut avec couleur"""
        status_colors = {
            'pending': 'orange',
            'in_progress': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Statut"

    def progress_bar(self, obj):
        """Barre de progression"""
        if obj.status == 'completed':
            progress = 100
            color = 'green'
        elif obj.status == 'failed':
            progress = 0
            color = 'red'
        else:
            progress = obj.progress
            color = 'blue'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; height: 20px; background-color: {}; border-radius: 3px;"></div>'
            '</div>{}%',
            progress, color, round(progress, 1)
        )
    progress_bar.short_description = "Progression"

    def languages_list(self, obj):
        """Liste des langues cibles"""
        languages = obj.target_languages.all()
        if languages:
            return ", ".join([f"{lang.name} ({lang.code})" for lang in languages])
        return "-"
    languages_list.short_description = "Langues cibles"

    def word_count_info(self, obj):
        """Information sur le nombre de mots"""
        return f"{obj.actual_word_count} / {obj.estimated_word_count}"
    word_count_info.short_description = "Mots"

    def restart_failed_tasks(self, request, queryset):
        """Redémarrer les tâches échouées"""
        failed_tasks = queryset.filter(status='failed')
        updated = failed_tasks.update(status='pending', retry_count=0, error_message='')
        self.message_user(
            request,
            f"{updated} tâche(s) échouée(s) redémarrée(s)."
        )
    restart_failed_tasks.short_description = "Redémarrer les tâches échouées"

    def cancel_pending_tasks(self, request, queryset):
        """Annuler les tâches en attente"""
        pending_tasks = queryset.filter(status='pending')
        updated = pending_tasks.update(status='cancelled')
        self.message_user(
            request,
            f"{updated} tâche(s) en attente annulée(s)."
        )
    cancel_pending_tasks.short_description = "Annuler les tâches en attente"

