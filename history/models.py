# =============================================================================
# APP: history (Historique et projets)
# =============================================================================

# history/models.py
from django.db import models
from django.conf import settings

class TranslationHistory(models.Model):
    """Historique des traductions terminées"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='translation_history')
    original_file = models.ForeignKey('files.TranslationFile', on_delete=models.CASCADE)
    task = models.OneToOneField('translations.TranslationTask', on_delete=models.CASCADE)
    
    # Fichiers générés
    translated_files = models.JSONField(default=dict)  # {language_code: file_path}
    
    # Statistiques
    target_languages = models.JSONField(default=list)
    strings_translated = models.IntegerField(default=0)
    words_translated = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    processing_time = models.DurationField(blank=True, null=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    service_used = models.CharField(max_length=50)
    
    def get_download_url(self, language_code):
        """Retourne l'URL de téléchargement pour une langue"""
        if language_code in self.translated_files:
            return self.translated_files[language_code]
        return None
    
    def __str__(self):
        return f"History {self.id} - {self.original_file.original_filename}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Translation histories"
