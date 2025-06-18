# =============================================================================
# APP: usage (Suivi de l'utilisation)
# =============================================================================

# usage/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class WordUsage(models.Model):
    """Suivi de l'utilisation des mots"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='word_usage')
    task = models.ForeignKey('translations.TranslationTask', on_delete=models.CASCADE, blank=True, null=True)
    words_used = models.IntegerField()
    usage_date = models.DateTimeField(auto_now_add=True)
    service_used = models.CharField(max_length=50)
    
    # Métadonnées
    source_language = models.CharField(max_length=10)
    target_languages = models.JSONField(default=list)
    file_type = models.CharField(max_length=20, blank=True)
    
    @classmethod
    def get_daily_usage(cls, user, date=None):
        """Récupère l'usage quotidien d'un utilisateur"""
        if date is None:
            date = timezone.now().date()
        return cls.objects.filter(
            user=user,
            usage_date__date=date
        ).aggregate(total=models.Sum('words_used'))['total'] or 0
    
    @classmethod
    def get_monthly_usage(cls, user, year=None, month=None):
        """Récupère l'usage mensuel d'un utilisateur"""
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
            
        return cls.objects.filter(
            user=user,
            usage_date__year=year,
            usage_date__month=month
        ).aggregate(total=models.Sum('words_used'))['total'] or 0
    
    def __str__(self):
        return f"{self.user.email} - {self.words_used} words - {self.usage_date.date()}"
    
    class Meta:
        ordering = ['-usage_date']

class QuotaLimit(models.Model):
    """Limites de quota personnalisées"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quota_limit')
    daily_limit_override = models.IntegerField(blank=True, null=True)
    monthly_limit_override = models.IntegerField(blank=True, null=True)
    is_unlimited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Quota for {self.user.email}"
