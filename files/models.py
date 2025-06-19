# =============================================================================
# APP: files (Gestion des fichiers de traduction)
# =============================================================================

# files/models.py
from django.db import models
from django.conf import settings
import os
import uuid

class TranslationFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Fichiers uploadés pour traduction"""
    FILE_TYPES = [
        ('po', 'PO File'),
        ('json', 'JSON File'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('parsing', 'Parsing'),
        ('processing', 'Processing'),  
        ('parsed', 'Parsed'),
        ('translating', 'Translating'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    
    original_filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='translation_files/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    file_size = models.BigIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_files')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    error_message = models.TextField(blank=True)
    
    
    task_id = models.CharField(max_length=255, blank=True, null=True, help_text="Celery task ID for processing")
    
   
    detected_framework = models.CharField(max_length=50, blank=True)
    encoding = models.CharField(max_length=50, default='utf-8')
    total_strings = models.IntegerField(default=0)
    
    def delete_temp_file(self):
        """Supprime le fichier physique"""
        if self.file_path and os.path.exists(self.file_path.path):
            os.remove(self.file_path.path)
    
    def get_file_extension(self):
        """Retourne l'extension du fichier"""
        return os.path.splitext(self.original_filename)[1]
    
    def __str__(self):
        return f"{self.original_filename} - {self.uploaded_by.email}"
    
    class Meta:
        ordering = ['-uploaded_at']

class TranslationString(models.Model):
    """Chaînes individuelles à traduire"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(TranslationFile, on_delete=models.CASCADE, related_name='strings')
    key = models.CharField(max_length=500)  # Clé de traduction
    source_text = models.TextField()  # Texte source
    translated_text = models.TextField(blank=True)  # Texte traduit
    context = models.TextField(blank=True)  # Contexte/commentaire
    comment = models.TextField(blank=True)  # Commentaire additionnel
    is_translated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Métadonnées pour certains formats
    line_number = models.IntegerField(blank=True, null=True)
    is_fuzzy = models.BooleanField(default=False)  # Pour les fichiers PO
    is_plural = models.BooleanField(default=False)
    
    
    
    def get_translations(self):
        """Retourne toutes les traductions de cette chaîne"""
        return self.translations.all()
    
    def __str__(self):
        return f"{self.key}: {self.source_text[:50]}..."
    
    class Meta:
        unique_together = ['file', 'key']
        ordering = ['line_number', 'key']