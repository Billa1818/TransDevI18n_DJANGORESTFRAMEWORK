# files/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import TranslationFile, TranslationString

@admin.register(TranslationFile)
class TranslationFileAdmin(admin.ModelAdmin):
    list_display = [
        'original_filename', 
        'file_type', 
        'status_badge', 
        'uploaded_by', 
        'file_size_formatted',
        'total_strings',
        'uploaded_at',
        'view_strings_link'
    ]
    
    list_filter = [
        'file_type',
        'status',
        'detected_framework',
        'uploaded_at',
        'encoding',
        ('uploaded_by', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'original_filename',
        'uploaded_by__email',
        'uploaded_by__username',
        'error_message',
        'detected_framework'
    ]
    
    readonly_fields = [
        'id',
        'file_size',
        'uploaded_at',
        'task_id',
        'total_strings',
        'file_info_display'
    ]
    
    fieldsets = (
        ('Informations du fichier', {
            'fields': ('original_filename', 'file_path', 'file_type', 'file_size')
        }),
        ('Statut et traitement', {
            'fields': ('status', 'task_id', 'error_message', 'total_strings')
        }),
        ('Métadonnées', {
            'fields': ('detected_framework', 'encoding', 'uploaded_by', 'uploaded_at')
        }),
        ('Informations système', {
            'fields': ('id', 'file_info_display'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'uploaded_at'
    
    actions = ['mark_as_completed', 'reset_status', 'delete_with_files']
    
    def status_badge(self, obj):
        """Affiche le statut avec une couleur"""
        colors = {
            'uploaded': '#17a2b8',
            'parsing': '#ffc107', 
            'processing': '#fd7e14',
            'parsed': '#6f42c1',
            'translating': '#007bff',
            'completed': '#28a745',
            'error': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Statut'
    
    def file_size_formatted(self, obj):
        """Affiche la taille du fichier formatée"""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size_formatted.short_description = 'Taille'
    
    def view_strings_link(self, obj):
        """Lien vers les chaînes de traduction"""
        count = obj.strings.count()
        if count > 0:
            url = reverse('admin:files_translationstring_changelist')
            return format_html(
                '<a href="{}?file__id__exact={}">{} chaînes</a>',
                url, obj.id, count
            )
        return "Aucune chaîne"
    view_strings_link.short_description = 'Chaînes'
    
    def file_info_display(self, obj):
        """Affiche les informations détaillées du fichier"""
        if obj.file_path:
            return format_html(
                '<strong>Chemin:</strong> {}<br>'
                '<strong>Extension:</strong> {}<br>'
                '<strong>Encodage:</strong> {}',
                obj.file_path.name,
                obj.get_file_extension(),
                obj.encoding
            )
        return "Aucune information"
    file_info_display.short_description = 'Informations du fichier'
    
    def mark_as_completed(self, request, queryset):
        """Action pour marquer comme terminé"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} fichier(s) marqué(s) comme terminé(s).')
    mark_as_completed.short_description = "Marquer comme terminé"
    
    def reset_status(self, request, queryset):
        """Action pour réinitialiser le statut"""
        updated = queryset.update(status='uploaded', error_message='')
        self.message_user(request, f'{updated} fichier(s) réinitialisé(s).')
    reset_status.short_description = "Réinitialiser le statut"
    
    def delete_with_files(self, request, queryset):
        """Supprime les fichiers et les données"""
        count = 0
        for obj in queryset:
            obj.delete_temp_file()
            obj.delete()
            count += 1
        self.message_user(request, f'{count} fichier(s) supprimé(s) avec leurs données.')
    delete_with_files.short_description = "Supprimer fichiers et données"


@admin.register(TranslationString)
class TranslationStringAdmin(admin.ModelAdmin):
    list_display = [
        'key_truncated',
        'source_text_truncated', 
        'is_fuzzy_badge',
        'file_link',
        'line_number'
    ]
    
    list_filter = [
        'is_fuzzy',
        'is_plural',
        'created_at',
        ('file', admin.RelatedOnlyFieldListFilter),
        ('file__file_type', admin.ChoicesFieldListFilter),
        ('file__status', admin.ChoicesFieldListFilter),
    ]
    
    search_fields = [
        'key',
        'source_text',
        'translated_text',
        'context',
        'comment',
        'file__original_filename'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'file_info_display'
    ]
    
    fieldsets = (
        ('Contenu de traduction', {
            'fields': ('key', 'source_text', 'context', 'comment')
        }),
        ('Statut', {
            'fields': ('is_fuzzy', 'is_plural')
        }),
        ('Métadonnées', {
            'fields': ('file', 'line_number', 'created_at')
        }),
        ('Informations système', {
            'fields': ('id', 'file_info_display'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    actions = ['clear_fuzzy_flag']
    
    list_per_page = 50
    
    def key_truncated(self, obj):
        """Affiche la clé tronquée"""
        if len(obj.key) > 30:
            return obj.key[:30] + '...'
        return obj.key
    key_truncated.short_description = 'Clé'
    
    def source_text_truncated(self, obj):
        """Affiche le texte source tronqué"""
        if len(obj.source_text) > 40:
            return obj.source_text[:40] + '...'
        return obj.source_text
    source_text_truncated.short_description = 'Texte source'
    
    def is_fuzzy_badge(self, obj):
        """Badge pour le statut fuzzy"""
        if obj.is_fuzzy:
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;">✓ Fuzzy</span>'
            )
        else:
            return format_html(
                '<span style="color: #6c757d;">✗ Non fuzzy</span>'
            )
    is_fuzzy_badge.short_description = 'Fuzzy'
    
    def file_link(self, obj):
        """Lien vers le fichier parent"""
        url = reverse('admin:files_translationfile_change', args=[obj.file.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.file.original_filename
        )
    file_link.short_description = 'Fichier'
    
    def file_info_display(self, obj):
        """Informations sur le fichier parent"""
        return format_html(
            '<strong>Fichier:</strong> {}<br>'
            '<strong>Type:</strong> {}<br>'
            '<strong>Statut:</strong> {}',
            obj.file.original_filename,
            obj.file.get_file_type_display(),
            obj.file.get_status_display()
        )
    file_info_display.short_description = 'Informations du fichier'
    
    def clear_fuzzy_flag(self, request, queryset):
        """Supprime le flag fuzzy"""
        updated = queryset.update(is_fuzzy=False)
        self.message_user(request, f'{updated} chaîne(s) sans flag fuzzy.')
    clear_fuzzy_flag.short_description = "Supprimer le flag fuzzy"

