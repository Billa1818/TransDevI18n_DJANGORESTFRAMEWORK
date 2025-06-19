# clients/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ClientKey

@admin.register(ClientKey)
class ClientKeyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'key_display', 
        'is_active_display', 
        'created_at_display',
        'actions_display'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'key']
    readonly_fields = ['id', 'key', 'created_at', 'key_copy_button']
    list_per_page = 25
    ordering = ['-created_at']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('name', 'is_active')
        }),
        ('Clé d\'accès', {
            'fields': ('key', 'key_copy_button'),
            'description': 'La clé est générée automatiquement lors de la création.'
        }),
        ('Métadonnées', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def key_display(self, obj):
        """Affiche une version tronquée de la clé avec possibilité de copier"""
        if obj.key:
            short_key = f"{obj.key[:8]}...{obj.key[-8:]}"
            return format_html(
                '<span title="{}" style="font-family: monospace; cursor: help;">{}</span>',
                obj.key,
                short_key
            )
        return "-"
    key_display.short_description = "Clé d'API"
    
    def is_active_display(self, obj):
        """Affiche le statut avec une icône colorée"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745;">✓ Actif</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545;">✗ Inactif</span>'
            )
    is_active_display.short_description = "Statut"
    
    def created_at_display(self, obj):
        """Affiche la date de création formatée"""
        return obj.created_at.strftime("%d/%m/%Y à %H:%M")
    created_at_display.short_description = "Créé le"
    
    def actions_display(self, obj):
        """Affiche des boutons d'action rapide"""
        toggle_text = "Désactiver" if obj.is_active else "Activer"
        toggle_color = "#ffc107" if obj.is_active else "#28a745"
        
        # Récupère dynamiquement le nom de l'app depuis les métadonnées du modèle
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        
        return format_html(
            '<a href="{}" style="color: {}; text-decoration: none; margin-right: 10px;">{}</a>',
            reverse(f'admin:{app_label}_{model_name}_change', args=[obj.pk]),
            toggle_color,
            toggle_text
        )
    actions_display.short_description = "Actions"
    
    def key_copy_button(self, obj):
        """Bouton pour copier la clé complète"""
        if obj.key:
            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 10px;">
                    <code style="background: #f8f9fa; padding: 5px; border-radius: 3px; font-size: 12px;">{}</code>
                    <button type="button" onclick="copyToClipboard('{}')" 
                            style="background: #007cba; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                        Copier
                    </button>
                </div>
                <script>
                function copyToClipboard(text) {{
                    navigator.clipboard.writeText(text).then(function() {{
                        alert('Clé copiée dans le presse-papiers !');
                    }}, function(err) {{
                        console.error('Erreur lors de la copie: ', err);
                        // Fallback pour les navigateurs plus anciens
                        var textArea = document.createElement("textarea");
                        textArea.value = text;
                        document.body.appendChild(textArea);
                        textArea.focus();
                        textArea.select();
                        try {{
                            document.execCommand('copy');
                            alert('Clé copiée dans le presse-papiers !');
                        }} catch (err) {{
                            alert('Impossible de copier automatiquement. Clé: ' + text);
                        }}
                        document.body.removeChild(textArea);
                    }});
                }}
                </script>
                ''',
                obj.key,
                obj.key
            )
        return "-"
    key_copy_button.short_description = "Clé complète"
    
    def get_queryset(self, request):
        """Optimise les requêtes pour la liste"""
        return super().get_queryset(request).select_related()
    
    def has_delete_permission(self, request, obj=None):
        """Autorise la suppression seulement pour les superutilisateurs"""
        return request.user.is_superuser
    
    def save_model(self, request, obj, form, change):
        """Personnalise la sauvegarde"""
        if not change:  # Lors de la création
            # La clé sera générée automatiquement par le modèle
            pass
        super().save_model(request, obj, form, change)
    
    # Actions personnalisées
    actions = ['activate_clients', 'deactivate_clients']
    
    def activate_clients(self, request, queryset):
        """Active les clients sélectionnés"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"{updated} client(s) activé(s) avec succès."
        )
    activate_clients.short_description = "Activer les clients sélectionnés"
    
    def deactivate_clients(self, request, queryset):
        """Désactive les clients sélectionnés"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} client(s) désactivé(s) avec succès."
        )
    deactivate_clients.short_description = "Désactiver les clients sélectionnés"
