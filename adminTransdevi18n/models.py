# app: clients/models.py
import uuid
from django.db import models

class ClientKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text="Nom du client/dev frontend")
    key = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.key:
            # Générer une clé sécurisée unique (par exemple UUID4 hex)
            self.key = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {'Actif' if self.is_active else 'Inactif'}"
