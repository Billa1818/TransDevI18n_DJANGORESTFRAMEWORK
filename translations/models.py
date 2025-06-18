# =============================================================================
# APP: translations (Gestion des traductions et services)
# =============================================================================

# translations/models.py
from django.db import models
from django.conf import settings
import json

class Language(models.Model):
    """Langues disponibles"""
    code = models.CharField(max_length=10, unique=True)  # fr, en, es, etc.
    name = models.CharField(max_length=100)  # French, English, Spanish
    native_name = models.CharField(max_length=100)  # Français, English, Español
    is_active = models.BooleanField(default=True)
    
    @classmethod
    def get_supported_by_service(cls, service_name):
        """Retourne les langues supportées par un service"""
        # Logique à implémenter selon les services
        return cls.objects.filter(is_active=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['name']

class TranslationService(models.Model):
    """Services de traduction disponibles"""
    SERVICE_TYPES = [
        ('google', 'Google Translate'),
        ('deepl', 'DeepL'),
        ('azure', 'Azure Translator'),
        ('argos', 'Argos Translate'),
    ]
    
    name = models.CharField(max_length=50, choices=SERVICE_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=500, blank=True)
    base_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    daily_quota = models.IntegerField(blank=True, null=True)
    monthly_quota = models.IntegerField(blank=True, null=True)
    
    # Configuration spécifique à chaque service
    config = models.JSONField(default=dict, blank=True)
    
    def get_supported_languages(self):
        """Retourne les langues supportées par ce service"""
        return Language.get_supported_by_service(self.name)
    
    def __str__(self):
        return self.display_name

class Translation(models.Model):
    """Traductions individuelles"""
    TRANSLATION_METHODS = [
        ('google', 'Google Translate'),
        ('deepl', 'DeepL'),
        ('azure', 'Azure Translator'),
        ('argos', 'Argos Translate'),
        ('manual', 'Manual Translation'),
    ]
    
    string = models.ForeignKey('files.TranslationString', on_delete=models.CASCADE, related_name='translations')
    target_language = models.ForeignKey(Language, on_delete=models.CASCADE)
    translated_text = models.TextField()
    translation_method = models.CharField(max_length=20, choices=TRANSLATION_METHODS)
    service = models.ForeignKey(TranslationService, on_delete=models.SET_NULL, null=True, blank=True)
    confidence_score = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    
    # Métadonnées
    characters_count = models.IntegerField(default=0)
    words_count = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement le nombre de caractères et mots
        if self.translated_text:
            self.characters_count = len(self.translated_text)
            self.words_count = len(self.translated_text.split())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.string.key} -> {self.target_language.code}"
    
    class Meta:
        unique_together = ['string', 'target_language']

class TranslationTask(models.Model):
    """Tâches de traduction"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    file = models.ForeignKey('files.TranslationFile', on_delete=models.CASCADE, related_name='translation_tasks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='translation_tasks')
    target_languages = models.ManyToManyField(Language)
    service = models.ForeignKey(TranslationService, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Progression
    progress = models.FloatField(default=0.0)  # 0-100
    estimated_word_count = models.IntegerField(default=0)
    actual_word_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Gestion des erreurs
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    def update_progress(self, progress_value):
        """Met à jour la progression"""
        self.progress = min(100.0, max(0.0, progress_value))
        self.save()
    
    def complete_task(self):
        """Marque la tâche comme terminée"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress = 100.0
        self.save()
    
    def __str__(self):
        return f"Task {self.id} - {self.file.original_filename}"
    
    class Meta:
        ordering = ['-created_at']
