# =============================================================================
# files/urls.py
# =============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TranslationFileViewSet, TranslationStringViewSet

router = DefaultRouter()
router.register(r'files', TranslationFileViewSet, basename='translationfile')
router.register(r'strings', TranslationStringViewSet, basename='translationstring')

urlpatterns = [
    path('', include(router.urls)),
]
