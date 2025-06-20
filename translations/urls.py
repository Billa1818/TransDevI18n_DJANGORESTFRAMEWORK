# =============================================================================
# APP: translations - URLs (API pour traductions de fichiers uniquement)
# =============================================================================

# translations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LanguageViewSet, TranslationViewSet, TranslationTaskViewSet, FileTranslationViewSet,
    FailedTranslationsListView, TranslationCorrectionView, BulkTranslationCorrectionView,
    translation_statistics
)

router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'translations', TranslationViewSet, basename='translation')
router.register(r'tasks', TranslationTaskViewSet, basename='translation-task')
router.register(r'files', FileTranslationViewSet, basename='file-translation')

app_name = 'translations'

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints pour correction manuelle
    path('corrections/', FailedTranslationsListView.as_view(), name='failed-translations-list'),
    path('corrections/<uuid:translation_id>/', TranslationCorrectionView.as_view(), name='translation-correction'),
    path('corrections/bulk/', BulkTranslationCorrectionView.as_view(), name='bulk-correction'),
    path('statistics/', translation_statistics, name='translation-statistics'),
] 