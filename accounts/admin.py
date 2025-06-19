# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.contrib import messages
from datetime import timedelta

from .models import (
    User, UserDevice, LoginAttempt, PasswordResetRequest, 
    OAuthProvider, UserOAuth
)


# =============================================================================
# FILTRES PERSONNALISÉS
# =============================================================================

class SubscriptionStatusFilter(SimpleListFilter):
    title = 'Statut d\'abonnement'
    parameter_name = 'subscription_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Abonnement actif'),
            ('expired', 'Abonnement expiré'),
            ('never', 'Jamais abonné'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(
                is_subscribed=True,
                subscription_end_date__gt=timezone.now()
            )
        elif self.value() == 'expired':
            return queryset.filter(
                is_subscribed=True,
                subscription_end_date__lt=timezone.now()
            )
        elif self.value() == 'never':
            return queryset.filter(is_subscribed=False)


class RecentLoginFilter(SimpleListFilter):
    title = 'Dernière connexion'
    parameter_name = 'recent_login'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Aujourd\'hui'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois'),
            ('never', 'Jamais connecté'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(last_login__date=now.date())
        elif self.value() == 'week':
            return queryset.filter(last_login__gte=now - timedelta(days=7))
        elif self.value() == 'month':
            return queryset.filter(last_login__gte=now - timedelta(days=30))
        elif self.value() == 'never':
            return queryset.filter(last_login__isnull=True)


class DeviceTypeFilter(SimpleListFilter):
    title = 'Type d\'appareil'
    parameter_name = 'device_type'

    def lookups(self, request, model_admin):
        return (
            ('mobile', 'Mobile'),
            ('desktop', 'Desktop'),
            ('tablet', 'Tablette'),
            ('unknown', 'Inconnu'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device_type=self.value())


class DeviceStatusFilter(SimpleListFilter):
    title = 'Statut de l\'appareil'
    parameter_name = 'device_status'

    def lookups(self, request, model_admin):
        return (
            ('trusted', 'Appareil de confiance'),
            ('blocked', 'Bloqué'),
            ('active', 'Actif'),
            ('inactive', 'Inactif'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'trusted':
            return queryset.filter(is_trusted=True)
        elif self.value() == 'blocked':
            return queryset.filter(is_blocked=True)
        elif self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)


# =============================================================================
# ADMIN PERSONNALISÉ POUR USER
# =============================================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'email', 'username', 'get_full_name', 'subscription_status_display',
        'daily_word_count', 'last_login_display', 'is_active', 'created_at'
    ]
    list_filter = [
        SubscriptionStatusFilter, RecentLoginFilter, 'is_active', 
        'is_staff', 'is_superuser', 'created_at'
    ]
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-created_at']
    readonly_fields = [
        'last_login', 'date_joined', 'created_at', 'last_word_count_reset',
        'subscription_status_display', 'devices_count', 'login_attempts_count'
    ]
    
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('username', 'email', 'first_name', 'last_name', 'profile_picture')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Abonnement', {
            'fields': ('is_subscribed', 'subscription_end_date', 'subscription_status_display'),
            'classes': ('collapse',)
        }),
        ('Statistiques d\'utilisation', {
            'fields': ('daily_word_count', 'last_word_count_reset'),
            'classes': ('collapse',)
        }),
        ('Informations de connexion', {
            'fields': ('last_login', 'date_joined', 'created_at'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('devices_count', 'login_attempts_count'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_subscribed'),
        }),
    )
    
    def subscription_status_display(self, obj):
        if obj.is_subscribed:
            if obj.check_subscription_status():
                return format_html(
                    '<span style="color: green;">✓ Actif jusqu\'au {}</span>',
                    obj.subscription_end_date.strftime('%d/%m/%Y') if obj.subscription_end_date else 'N/A'
                )
            else:
                return format_html('<span style="color: red;">✗ Expiré</span>')
        return format_html('<span style="color: gray;">Pas d\'abonnement</span>')
    subscription_status_display.short_description = 'Statut abonnement'
    
    def last_login_display(self, obj):
        if obj.last_login:
            return format_html(
                '<span title="{}">{}</span>',
                obj.last_login.strftime('%d/%m/%Y %H:%M:%S'),
                obj.last_login.strftime('%d/%m/%Y')
            )
        return format_html('<span style="color: red;">Jamais</span>')
    last_login_display.short_description = 'Dernière connexion'
    
    def devices_count(self, obj):
        count = obj.devices.count()
        url = reverse('admin:accounts_userdevice_changelist') + f'?user__id__exact={obj.id}'
        return format_html('<a href="{}">{} appareil(s)</a>', url, count)
    devices_count.short_description = 'Appareils'
    
    def login_attempts_count(self, obj):
        count = obj.login_attempts.count()
        url = reverse('admin:accounts_loginattempt_changelist') + f'?user__id__exact={obj.id}'
        return format_html('<a href="{}">{} tentative(s)</a>', url, count)
    login_attempts_count.short_description = 'Tentatives de connexion'
    
    actions = ['reset_daily_word_count', 'extend_subscription', 'block_users']
    
    def reset_daily_word_count(self, request, queryset):
        updated = 0
        for user in queryset:
            user.reset_daily_word_count()
            updated += 1
        self.message_user(
            request,
            f'Compteur quotidien remis à zéro pour {updated} utilisateur(s).',
            messages.SUCCESS
        )
    reset_daily_word_count.short_description = "Remettre à zéro le compteur quotidien"
    
    def extend_subscription(self, request, queryset):
        updated = 0
        for user in queryset:
            if user.subscription_end_date:
                user.subscription_end_date += timedelta(days=30)
            else:
                user.subscription_end_date = timezone.now() + timedelta(days=30)
            user.is_subscribed = True
            user.save()
            updated += 1
        self.message_user(
            request,
            f'Abonnement prolongé de 30 jours pour {updated} utilisateur(s).',
            messages.SUCCESS
        )
    extend_subscription.short_description = "Prolonger l'abonnement de 30 jours"
    
    def block_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} utilisateur(s) bloqué(s).',
            messages.WARNING
        )
    block_users.short_description = "Bloquer les utilisateurs sélectionnés"


# =============================================================================
# ADMIN POUR USERDEVICE
# =============================================================================

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'device_name', 'device_type', 'trust_status_display',
        'block_status_display', 'failed_login_attempts', 'last_used', 'created_at'
    ]
    list_filter = [
        DeviceTypeFilter, DeviceStatusFilter, 'is_trusted', 'is_blocked',
        'is_active', 'created_at', 'last_used'
    ]
    search_fields = [
        'user__email', 'user__username', 'device_name', 'device_fingerprint',
        'ip_address'
    ]
    readonly_fields = [
        'device_id', 'created_at', 'last_used', 'device_fingerprint',
        'failed_login_attempts', 'last_failed_attempt'
    ]
    ordering = ['-last_used']
    
    fieldsets = (
        ('Informations de l\'appareil', {
            'fields': ('user', 'device_name', 'device_type', 'device_fingerprint', 'device_id')
        }),
        ('Détails techniques', {
            'fields': ('user_agent', 'ip_address'),
            'classes': ('collapse',)
        }),
        ('Statut et sécurité', {
            'fields': ('is_trusted', 'is_active', 'is_blocked', 'blocked_until')
        }),
        ('Historique des échecs', {
            'fields': ('failed_login_attempts', 'last_failed_attempt'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def trust_status_display(self, obj):
        if obj.is_trusted:
            return format_html('<span style="color: green;">✓ Appareil de confiance</span>')
        return format_html('<span style="color: orange;">Appareil non vérifié</span>')
    trust_status_display.short_description = 'Confiance'
    
    def block_status_display(self, obj):
        if obj.is_currently_blocked():
            return format_html(
                '<span style="color: red;">🚫 Bloqué jusqu\'au {}</span>',
                obj.blocked_until.strftime('%d/%m/%Y %H:%M') if obj.blocked_until else 'N/A'
            )
        return format_html('<span style="color: green;">✓ Actif</span>')
    block_status_display.short_description = 'Statut'
    
    actions = ['trust_devices', 'untrust_devices', 'unblock_devices', 'block_devices']
    
    def trust_devices(self, request, queryset):
        updated = queryset.update(is_trusted=True)
        self.message_user(
            request,
            f'{updated} appareil(s) marqué(s) comme appareil de confiance.',
            messages.SUCCESS
        )
    trust_devices.short_description = "Marquer comme appareil de confiance"
    
    def untrust_devices(self, request, queryset):
        updated = queryset.update(is_trusted=False)
        self.message_user(
            request,
            f'{updated} appareil(s) retiré(s) de la liste des appareils de confiance.',
            messages.WARNING
        )
    untrust_devices.short_description = "Retirer de la liste des appareils de confiance"
    
    def unblock_devices(self, request, queryset):
        updated = 0
        for device in queryset:
            device.reset_failed_attempts()
            updated += 1
        self.message_user(
            request,
            f'{updated} appareil(s) débloqué(s).',
            messages.SUCCESS
        )
    unblock_devices.short_description = "Débloquer les appareils"
    
    def block_devices(self, request, queryset):
        updated = 0
        for device in queryset:
            device.is_blocked = True
            device.blocked_until = timezone.now() + timedelta(hours=24)
            device.save()
            updated += 1
        self.message_user(
            request,
            f'{updated} appareil(s) bloqué(s) pour 24h.',
            messages.WARNING
        )
    block_devices.short_description = "Bloquer les appareils pour 24h"


# =============================================================================
# ADMIN POUR LOGINATTEMPT
# =============================================================================

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'success_display', 'ip_address', 'device_info', 'timestamp'
    ]
    list_filter = ['success', 'timestamp']
    search_fields = ['user__email', 'user__username', 'ip_address', 'failure_reason']
    readonly_fields = ['user', 'device', 'ip_address', 'user_agent', 'success', 'failure_reason', 'timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def success_display(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓ Réussie</span>')
        else:
            return format_html(
                '<span style="color: red;">✗ Échouée</span><br><small>{}</small>',
                obj.failure_reason or 'Raison inconnue'
            )
    success_display.short_description = 'Résultat'
    
    def device_info(self, obj):
        if obj.device:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:accounts_userdevice_change', args=[obj.device.pk]),
                obj.device.device_name
            )
        return 'Appareil inconnu'
    device_info.short_description = 'Appareil'


# =============================================================================
# ADMIN POUR PASSWORDRESETREQUEST
# =============================================================================

@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'status_display', 'ip_address', 'created_at', 'expires_at'
    ]
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__email', 'user__username', 'ip_address', 'token']
    readonly_fields = [
        'user', 'ip_address', 'user_agent', 'token', 'created_at', 
        'expires_at', 'used_at', 'is_used'
    ]
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def status_display(self, obj):
        if obj.is_used:
            return format_html('<span style="color: blue;">✓ Utilisé</span>')
        elif obj.is_expired():
            return format_html('<span style="color: red;">⏰ Expiré</span>')
        else:
            return format_html('<span style="color: green;">⏳ Actif</span>')
    status_display.short_description = 'Statut'


# =============================================================================
# ADMIN POUR OAUTHPROVIDER
# =============================================================================

@admin.register(OAuthProvider)
class OAuthProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'users_count']
    list_filter = ['is_active']
    search_fields = ['name']
    
    def users_count(self, obj):
        count = obj.useroauth_set.count()
        if count > 0:
            url = reverse('admin:accounts_useroauth_changelist') + f'?provider__id__exact={obj.id}'
            return format_html('<a href="{}">{} utilisateur(s)</a>', url, count)
        return '0 utilisateur'
    users_count.short_description = 'Utilisateurs connectés'


# =============================================================================
# ADMIN POUR USEROAUTH
# =============================================================================

@admin.register(UserOAuth)
class UserOAuthAdmin(admin.ModelAdmin):
    list_display = ['user', 'provider', 'provider_user_id', 'created_at']
    list_filter = ['provider', 'created_at']
    search_fields = ['user__email', 'user__username', 'provider_user_id']
    readonly_fields = ['created_at']
    
    def has_change_permission(self, request, obj=None):
        # Permettre la modification mais protéger les tokens
        return True


# =============================================================================
# CONFIGURATION GLOBALE DE L'ADMIN
# =============================================================================
