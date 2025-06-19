# notifications/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.contrib import messages
from datetime import timedelta
from django.db.models import Case, When, IntegerField

from .models import Notification, NotificationPreference


# =============================================================================
# FILTRES PERSONNALISÉS
# =============================================================================

class NotificationTypeFilter(SimpleListFilter):
    title = 'Type de notification'
    parameter_name = 'notification_type'

    def lookups(self, request, model_admin):
        return [
            ('translation_complete', '✅ Traduction terminée'),
            ('translation_failed', '❌ Traduction échouée'),
            ('quota_warning', '⚠️ Avertissement quota'),
            ('quota_exceeded', '🚫 Quota dépassé'),
            ('subscription_expiring', '⏰ Abonnement expire'),
            ('subscription_expired', '💀 Abonnement expiré'),
            ('payment_success', '💳 Paiement réussi'),
            ('payment_failed', '💸 Paiement échoué'),
            ('system_notification', '🔧 Notification système'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(notification_type=self.value())


class ReadStatusFilter(SimpleListFilter):
    title = 'Statut de lecture'
    parameter_name = 'read_status'

    def lookups(self, request, model_admin):
        return (
            ('unread', '📬 Non lues'),
            ('read', '📭 Lues'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'unread':
            return queryset.filter(is_read=False)
        elif self.value() == 'read':
            return queryset.filter(is_read=True)


class RecentNotificationsFilter(SimpleListFilter):
    title = 'Période'
    parameter_name = 'recent'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Aujourd\'hui'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois'),
            ('older', 'Plus anciennes'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'week':
            return queryset.filter(created_at__gte=now - timedelta(days=7))
        elif self.value() == 'month':
            return queryset.filter(created_at__gte=now - timedelta(days=30))
        elif self.value() == 'older':
            return queryset.filter(created_at__lt=now - timedelta(days=30))


class UserActivityFilter(SimpleListFilter):
    title = 'Activité utilisateur'
    parameter_name = 'user_activity'

    def lookups(self, request, model_admin):
        return (
            ('high', 'Utilisateurs très actifs (>50 notifications)'),
            ('medium', 'Utilisateurs actifs (10-50 notifications)'),
            ('low', 'Utilisateurs peu actifs (<10 notifications)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'high':
            active_users = queryset.values('user').annotate(
                notif_count=Count('id')
            ).filter(notif_count__gt=50).values_list('user', flat=True)
            return queryset.filter(user__in=active_users)
        elif self.value() == 'medium':
            medium_users = queryset.values('user').annotate(
                notif_count=Count('id')
            ).filter(notif_count__gte=10, notif_count__lte=50).values_list('user', flat=True)
            return queryset.filter(user__in=medium_users)
        elif self.value() == 'low':
            low_users = queryset.values('user').annotate(
                notif_count=Count('id')
            ).filter(notif_count__lt=10).values_list('user', flat=True)
            return queryset.filter(user__in=low_users)


# =============================================================================
# ADMIN PERSONNALISÉ POUR NOTIFICATION
# =============================================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'notification_icon', 'title_with_status', 'user_link', 'notification_type_display',
        'read_status_display', 'time_ago', 'has_action_url'
    ]
    list_filter = [
        NotificationTypeFilter, ReadStatusFilter, RecentNotificationsFilter,
        UserActivityFilter, 'created_at', 'updated_at'
    ]
    search_fields = [
        'title', 'message', 'user__email', 'user__username',
        'user__first_name', 'user__last_name'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'notification_icon',
        'related_object_display', 'time_ago'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('id', 'user', 'title', 'message', 'notification_type')
        }),
        ('Statut et suivi', {
            'fields': ('is_read', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Données contextuelles', {
            'fields': ('related_object_id', 'related_object_type', 'related_object_display', 'action_url'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def notification_icon(self, obj):
        icons = {
            'translation_complete': '✅',
            'translation_failed': '❌',
            'quota_warning': '⚠️',
            'quota_exceeded': '🚫',
            'subscription_expiring': '⏰',
            'subscription_expired': '💀',
            'payment_success': '💳',
            'payment_failed': '💸',
            'system_notification': '🔧',
        }
        return icons.get(obj.notification_type, '📢')
    notification_icon.short_description = ''
    
    def title_with_status(self, obj):
        title = obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
        if obj.is_read:
            return format_html('<span style="color: #666;">{}</span>', title)
        else:
            return format_html('<strong>{}</strong>', title)
    title_with_status.short_description = 'Titre'
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.pk])
        display_name = obj.user.get_full_name() or obj.user.username
        email = obj.user.email
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            url, email, display_name
        )
    user_link.short_description = 'Utilisateur'
    
    def notification_type_display(self, obj):
        type_styles = {
            'translation_complete': 'background: #d4edda; color: #155724; border-radius: 3px; padding: 2px 6px;',
            'translation_failed': 'background: #f8d7da; color: #721c24; border-radius: 3px; padding: 2px 6px;',
            'quota_warning': 'background: #fff3cd; color: #856404; border-radius: 3px; padding: 2px 6px;',
            'quota_exceeded': 'background: #f8d7da; color: #721c24; border-radius: 3px; padding: 2px 6px;',
            'subscription_expiring': 'background: #fff3cd; color: #856404; border-radius: 3px; padding: 2px 6px;',
            'subscription_expired': 'background: #f8d7da; color: #721c24; border-radius: 3px; padding: 2px 6px;',
            'payment_success': 'background: #d1ecf1; color: #0c5460; border-radius: 3px; padding: 2px 6px;',
            'payment_failed': 'background: #f8d7da; color: #721c24; border-radius: 3px; padding: 2px 6px;',
            'system_notification': 'background: #e2e3e5; color: #383d41; border-radius: 3px; padding: 2px 6px;',
        }
        type_names = {
            'translation_complete': 'Traduction OK',
            'translation_failed': 'Traduction KO',
            'quota_warning': 'Avertissement',
            'quota_exceeded': 'Quota dépassé',
            'subscription_expiring': 'Expire bientôt',
            'subscription_expired': 'Expiré',
            'payment_success': 'Paiement OK',
            'payment_failed': 'Paiement KO',
            'system_notification': 'Système',
        }
        style = type_styles.get(obj.notification_type, '')
        name = type_names.get(obj.notification_type, obj.notification_type)
        return format_html('<span style="{}">{}</span>', style, name)
    notification_type_display.short_description = 'Type'
    
    def read_status_display(self, obj):
        if obj.is_read:
            return format_html('<span style="color: green;">📭 Lue</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">📬 Non lue</span>')
    read_status_display.short_description = 'Statut'
    
    def time_ago(self, obj):
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 30:
            return format_html('<span style="color: #999;">il y a {} mois</span>', diff.days // 30)
        elif diff.days > 0:
            return format_html('<span style="color: #666;">il y a {} jour(s)</span>', diff.days)
        elif diff.seconds > 3600:
            return format_html('<span style="color: #333;">il y a {}h</span>', diff.seconds // 3600)
        elif diff.seconds > 60:
            return format_html('<span style="color: #000;">il y a {}min</span>', diff.seconds // 60)
        else:
            return format_html('<span style="color: red; font-weight: bold;">À l\'instant</span>')
    time_ago.short_description = 'Ancienneté'
    
    def has_action_url(self, obj):
        if obj.action_url:
            return format_html('🔗 <a href="{}" target="_blank">Action</a>', obj.action_url)
        return '—'
    has_action_url.short_description = 'Action'
    
    def related_object_display(self, obj):
        if obj.related_object_id and obj.related_object_type:
            return format_html(
                'Type: <strong>{}</strong><br>ID: <strong>{}</strong>',
                obj.related_object_type,
                obj.related_object_id
            )
        return 'Aucun objet lié'
    related_object_display.short_description = 'Objet lié'
    
    # Actions personnalisées
    actions = [
        'mark_as_read', 'mark_as_unread', 'delete_old_notifications',
        'send_test_notification', 'bulk_delete_by_type'
    ]
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True, updated_at=timezone.now())
        self.message_user(
            request,
            f'{updated} notification(s) marquée(s) comme lue(s).',
            messages.SUCCESS
        )
    mark_as_read.short_description = "📭 Marquer comme lues"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False, updated_at=timezone.now())
        self.message_user(
            request,
            f'{updated} notification(s) marquée(s) comme non lue(s).',
            messages.SUCCESS
        )
    mark_as_unread.short_description = "📬 Marquer comme non lues"
    
    def delete_old_notifications(self, request, queryset):
        # Supprimer les notifications de plus de 90 jours
        old_date = timezone.now() - timedelta(days=90)
        old_notifications = queryset.filter(created_at__lt=old_date)
        count = old_notifications.count()
        old_notifications.delete()
        self.message_user(
            request,
            f'{count} notification(s) anciennes supprimée(s) (+ de 90 jours).',
            messages.WARNING
        )
    delete_old_notifications.short_description = "🗑️ Supprimer les anciennes notifications"
    
    def send_test_notification(self, request, queryset):
        # Action pour envoyer une notification de test aux utilisateurs sélectionnés
        users = set(queryset.values_list('user', flat=True))
        created_count = 0
        
        for user_id in users:
            Notification.objects.create(
                user_id=user_id,
                title="🧪 Notification de test",
                message="Ceci est une notification de test envoyée depuis l'administration.",
                notification_type='system_notification'
            )
            created_count += 1
        
        self.message_user(
            request,
            f'Notification de test envoyée à {created_count} utilisateur(s).',
            messages.INFO
        )
    send_test_notification.short_description = "🧪 Envoyer notification de test"
    
    def bulk_delete_by_type(self, request, queryset):
        # Grouper par type et afficher les comptes
        type_counts = {}
        for notification in queryset:
            type_name = dict(Notification.NOTIFICATION_TYPES).get(
                notification.notification_type, 
                notification.notification_type
            )
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        total = queryset.count()
        queryset.delete()
        
        details = ', '.join([f'{count} {type_name}' for type_name, count in type_counts.items()])
        self.message_user(
            request,
            f'{total} notification(s) supprimée(s): {details}',
            messages.WARNING
        )
    bulk_delete_by_type.short_description = "🗑️ Supprimer par type"


# =============================================================================
# ADMIN PERSONNALISÉ POUR NOTIFICATIONPREFERENCE
# =============================================================================

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_info', 'email_notifications_summary', 'app_notifications_summary',
        'total_enabled_count', 'last_updated'
    ]
    list_filter = [
        'email_translation_complete', 'email_quota_warnings', 
        'email_subscription_alerts', 'app_system_notifications'
    ]
    search_fields = [
        'user__email', 'user__username', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = ['id', 'total_enabled_count', 'preferences_summary']
    
    fieldsets = (
        ('Utilisateur', {
            'fields': ('id', 'user')
        }),
        ('📧 Notifications par email', {
            'fields': (
                'email_translation_complete',
                'email_translation_failed', 
                'email_quota_warnings',
                'email_subscription_alerts',
                'email_payment_alerts'
            ),
            'classes': ('collapse',)
        }),
        ('📱 Notifications dans l\'application', {
            'fields': (
                'app_translation_complete',
                'app_quota_warnings',
                'app_system_notifications'
            ),
            'classes': ('collapse',)
        }),
        ('📊 Résumé', {
            'fields': ('total_enabled_count', 'preferences_summary'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def user_info(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.pk])
        display_name = obj.user.get_full_name() or obj.user.username
        email = obj.user.email
        return format_html(
            '<a href="{}" title="{}">{}</a><br><small style="color: #666;">{}</small>',
            url, email, display_name, email
        )
    user_info.short_description = 'Utilisateur'
    
    def email_notifications_summary(self, obj):
        enabled = []
        fields = [
            ('email_translation_complete', '✅ Trad. OK'),
            ('email_translation_failed', '❌ Trad. KO'),
            ('email_quota_warnings', '⚠️ Quota'),
            ('email_subscription_alerts', '⏰ Abonnement'),
            ('email_payment_alerts', '💳 Paiement'),
        ]
        
        for field, label in fields:
            if getattr(obj, field):
                enabled.append(label)
        
        if enabled:
            return format_html('<small>{}</small>', ', '.join(enabled))
        return format_html('<span style="color: #999;">Aucune</span>')
    email_notifications_summary.short_description = '📧 Email activées'
    
    def app_notifications_summary(self, obj):
        enabled = []
        fields = [
            ('app_translation_complete', '✅ Trad.'),
            ('app_quota_warnings', '⚠️ Quota'),
            ('app_system_notifications', '🔧 Système'),
        ]
        
        for field, label in fields:
            if getattr(obj, field):
                enabled.append(label)
        
        if enabled:
            return format_html('<small>{}</small>', ', '.join(enabled))
        return format_html('<span style="color: #999;">Aucune</span>')
    app_notifications_summary.short_description = '📱 App activées'
    
    def total_enabled_count(self, obj):
        email_count = sum([
            obj.email_translation_complete,
            obj.email_translation_failed,
            obj.email_quota_warnings,
            obj.email_subscription_alerts,
            obj.email_payment_alerts,
        ])
        
        app_count = sum([
            obj.app_translation_complete,
            obj.app_quota_warnings,
            obj.app_system_notifications,
        ])
        
        total = email_count + app_count
        return format_html(
            '<strong>Total: {}</strong><br><small>📧 {} | 📱 {}</small>',
            total, email_count, app_count
        )
    total_enabled_count.short_description = 'Notifications activées'
    
    def preferences_summary(self, obj):
        summary = []
        
        # Email preferences
        email_fields = [
            ('email_translation_complete', 'Traductions terminées'),
            ('email_translation_failed', 'Traductions échouées'),
            ('email_quota_warnings', 'Avertissements quota'),
            ('email_subscription_alerts', 'Alertes abonnement'),
            ('email_payment_alerts', 'Alertes paiement'),
        ]
        
        summary.append('<strong>📧 Notifications Email:</strong>')
        for field, label in email_fields:
            status = '✅' if getattr(obj, field) else '❌'
            summary.append(f'  {status} {label}')
        
        # App preferences
        app_fields = [
            ('app_translation_complete', 'Traductions terminées'),
            ('app_quota_warnings', 'Avertissements quota'),
            ('app_system_notifications', 'Notifications système'),
        ]
        
        summary.append('<br><strong>📱 Notifications App:</strong>')
        for field, label in app_fields:
            status = '✅' if getattr(obj, field) else '❌'
            summary.append(f'  {status} {label}')
        
        return format_html('<br>'.join(summary))
    preferences_summary.short_description = 'Détail des préférences'
    
    def last_updated(self, obj):
        # Simule une date de dernière mise à jour
        return format_html('<span style="color: #666;">Auto-configuré</span>')
    last_updated.short_description = 'Dernière MAJ'
    
    # Actions personnalisées
    actions = [
        'enable_all_email_notifications', 'disable_all_email_notifications',
        'enable_all_app_notifications', 'disable_all_app_notifications',
        'reset_to_defaults', 'enable_critical_only'
    ]
    
    def enable_all_email_notifications(self, request, queryset):
        updated = 0
        for preference in queryset:
            preference.email_translation_complete = True
            preference.email_translation_failed = True
            preference.email_quota_warnings = True
            preference.email_subscription_alerts = True
            preference.email_payment_alerts = True
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Toutes les notifications email activées pour {updated} utilisateur(s).',
            messages.SUCCESS
        )
    enable_all_email_notifications.short_description = "📧 ✅ Activer toutes les notifications email"
    
    def disable_all_email_notifications(self, request, queryset):
        updated = 0
        for preference in queryset:
            preference.email_translation_complete = False
            preference.email_translation_failed = False
            preference.email_quota_warnings = False
            preference.email_subscription_alerts = False
            preference.email_payment_alerts = False
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Toutes les notifications email désactivées pour {updated} utilisateur(s).',
            messages.WARNING
        )
    disable_all_email_notifications.short_description = "📧 ❌ Désactiver toutes les notifications email"
    
    def enable_all_app_notifications(self, request, queryset):
        updated = 0
        for preference in queryset:
            preference.app_translation_complete = True
            preference.app_quota_warnings = True
            preference.app_system_notifications = True
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Toutes les notifications app activées pour {updated} utilisateur(s).',
            messages.SUCCESS
        )
    enable_all_app_notifications.short_description = "📱 ✅ Activer toutes les notifications app"
    
    def disable_all_app_notifications(self, request, queryset):
        updated = 0
        for preference in queryset:
            preference.app_translation_complete = False
            preference.app_quota_warnings = False
            preference.app_system_notifications = False
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Toutes les notifications app désactivées pour {updated} utilisateur(s).',
            messages.WARNING
        )
    disable_all_app_notifications.short_description = "📱 ❌ Désactiver toutes les notifications app"
    
    def reset_to_defaults(self, request, queryset):
        updated = 0
        for preference in queryset:
            # Réinitialiser aux valeurs par défaut du modèle
            preference.email_translation_complete = True
            preference.email_translation_failed = True
            preference.email_quota_warnings = True
            preference.email_subscription_alerts = True
            preference.email_payment_alerts = True
            preference.app_translation_complete = True
            preference.app_quota_warnings = True
            preference.app_system_notifications = True
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Préférences réinitialisées aux valeurs par défaut pour {updated} utilisateur(s).',
            messages.INFO
        )
    reset_to_defaults.short_description = "🔄 Réinitialiser aux valeurs par défaut"
    
    def enable_critical_only(self, request, queryset):
        updated = 0
        for preference in queryset:
            # Activer seulement les notifications critiques
            preference.email_translation_complete = False
            preference.email_translation_failed = True
            preference.email_quota_warnings = True
            preference.email_subscription_alerts = True
            preference.email_payment_alerts = True
            preference.app_translation_complete = False
            preference.app_quota_warnings = True
            preference.app_system_notifications = True
            preference.save()
            updated += 1
        
        self.message_user(
            request,
            f'Seules les notifications critiques activées pour {updated} utilisateur(s).',
            messages.INFO
        )
    enable_critical_only.short_description = "⚠️ Activer seulement les notifications critiques"


# =============================================================================
# CONFIGURATION GLOBALE DE L'ADMIN
# =============================================================================