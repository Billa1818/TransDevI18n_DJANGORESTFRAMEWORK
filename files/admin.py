from django.contrib import admin
from .models import TranslationFile, TranslationString

# Register your models here.

admin.site.register(TranslationFile)
admin.site.register(TranslationString)