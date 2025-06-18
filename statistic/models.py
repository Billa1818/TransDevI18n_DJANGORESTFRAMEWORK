
# =============================================================================
# APP: statistics (Statistiques et analytics)
# =============================================================================

# statistics/models.py
from django.db import models
from django.conf import settings

class UserStatistics(models.Model):
    """Statistiques utilisateur"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='statistics')
    
    # Compteurs globaux
    total_files_processed = models.IntegerField(default=0)
    total_strings_translated = models.IntegerField(default=0)
    total_words_translated = models.IntegerField(default=0)
    total_characters_translated = models.IntegerField(default=0)
    
    # Moyennes
    average_processing_time = models.DurationField(blank=True, null=True)
    average_file_size = models.BigIntegerField(default=0)
    
    # Services les plus utilisés
    most_used_service = models.CharField(max_length=50, blank=True)
    most_translated_language = models.CharField(max_length=10, blank=True)
    
    # Timestamps
    last_updated = models.DateTimeField(auto_now=True)
    first_translation_date = models.DateTimeField(blank=True, null=True)
    
    def update_statistics(self):
        """Met à jour les statistiques utilisateur"""
        # Logique de calcul des statistiques
        pass
    
    def __str__(self):
        return f"Stats for {self.user.email}"

class SystemStatistics(models.Model):
    """Statistiques globales du système"""
    date = models.DateField(unique=True)
    
    # Activité quotidienne
    daily_translations = models.IntegerField(default=0)
    daily_words_translated = models.IntegerField(default=0)
    daily_active_users = models.IntegerField(default=0)
    daily_new_users = models.IntegerField(default=0)
    
    # Services
    google_translate_usage = models.IntegerField(default=0)
    deepl_usage = models.IntegerField(default=0)
    azure_usage = models.IntegerField(default=0)
    argos_usage = models.IntegerField(default=0)
    
    # Langues populaires
    language_stats = models.JSONField(default=dict)
    
    # Performance
    average_processing_time = models.FloatField(default=0.0)
    error_rate = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"System stats for {self.date}"
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "System statistics"