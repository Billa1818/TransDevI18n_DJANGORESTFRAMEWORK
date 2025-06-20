# =============================================================================
# APP: translations (Gestion des traductions avec Google Translate)
# =============================================================================

# translations/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import json

class Language(models.Model):
    """Langues disponibles"""
    code = models.CharField(max_length=10, unique=True)  # fr, en, es, etc.
    name = models.CharField(max_length=100)  # French, English, Spanish
    native_name = models.CharField(max_length=100)  # Français, English, Español
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['name']

class Translation(models.Model):
    """Traductions individuelles avec Google Translate"""
    string = models.ForeignKey('files.TranslationString', on_delete=models.CASCADE, related_name='translations')
    target_language = models.ForeignKey(Language, on_delete=models.CASCADE)
    translated_text = models.TextField()
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
    """Tâches de traduction avec Google Translate"""
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
