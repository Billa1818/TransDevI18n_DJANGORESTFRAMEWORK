# =============================================================================
# URLs PRINCIPAL DU PROJET
# =============================================================================

# myproject/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.documentation import include_docs_urls

# Router principal pour l'API
router = DefaultRouter()

urlpatterns = [
    # Administration
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/', include([
        path('auth/', include('accounts.urls')),
        path('files/', include('files.urls')),
        path('notifications/', include('notifications.urls')),
        #path('translations/', include('translations.urls')),
        #path('subscriptions/', include('subscriptions.urls')),
        #path('usage/', include('usage.urls')),
        #path('history/', include('history.urls')),
        #path('statistics/', include('statistics.urls')),
    ])),
    
    #  dfr auth
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)