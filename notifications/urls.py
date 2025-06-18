# notifications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'notifications'

# Configuration du router DRF
router = DefaultRouter()



urlpatterns = [
    # URLs du router DRF
    path('', include(router.urls)),
    
    #   Endpoints pour les notifications
    path('', views.NotificationListCreateView.as_view(), name='notification-list-create'),
    path('<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
    
    # Notifications spécialisées
    path('unread/', views.UnreadNotificationsView.as_view(), name='unread-notifications'),
    path('type/<str:notification_type>/', views.NotificationsByTypeView.as_view(), name='notifications-by-type'),
    path('search/', views.NotificationSearchView.as_view(), name='notification-search'),
    
    # Actions sur notifications individuelles
    path('<uuid:pk>/mark-read/', views.MarkAsReadView.as_view(), name='mark-as-read'),
    
    # Actions en masse
    path('mark-all-read/', views.MarkAllAsReadView.as_view(), name='mark-all-as-read'),
    path('bulk-mark-read/', views.BulkMarkAsReadView.as_view(), name='bulk-mark-as-read'),
    path('bulk-delete/', views.BulkDeleteView.as_view(), name='bulk-delete'),
    path('delete-all-read/', views.DeleteAllReadNotificationsView.as_view(), name='delete-all-read'),
    
    # Statistiques et résumés
    path('summary/', views.NotificationSummaryView.as_view(), name='notification-summary'),
    path('stats/', views.NotificationStatsView.as_view(), name='notification-stats'),
    path('count/', views.notification_count, name='notification-count'),
    
    # Préférences utilisateur
    path('preferences/', views.NotificationPreferenceView.as_view(), name='notification-preferences'),
]

