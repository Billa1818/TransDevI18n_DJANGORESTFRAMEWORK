# app: clients/admin.py
from django.contrib import admin
from .models import ClientKey
import uuid

@admin.register(ClientKey)
class ClientKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_active', 'created_at')
    readonly_fields = ('key', 'created_at')

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = uuid.uuid4().hex
        super().save_model(request, obj, form, change)
