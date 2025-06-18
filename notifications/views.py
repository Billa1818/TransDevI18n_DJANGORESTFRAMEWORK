# notifications/views.py
from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from datetime import timedelta, datetime
from django_filters.rest_framework import DjangoFilterBackend
import django_filters

from .models import Notification, NotificationPreference
from .serializers import (
    NotificationSerializer,
    NotificationCreateSerializer,
    NotificationUpdateSerializer,
    NotificationPreferenceSerializer,
    NotificationListSerializer,
    NotificationSummarySerializer,
    MarkAllAsReadSerializer,
    NotificationStatsSerializer
)


class NotificationPagination(PageNumberPagination):
    """Pagination personnalisée pour les notifications"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationFilter(django_filters.FilterSet):
    """Filtres avancés pour les notifications"""
    
    # Filtres de base
    is_read = django_filters.BooleanFilter()
    notification_type = django_filters.CharFilter(lookup_expr='iexact')
    
    # Filtres de date
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    created_date = django_filters.DateFilter(field_name='created_at__date')
    
    # Filtre par période
    period = django_filters.ChoiceFilter(
        choices=[
            ('today', 'Aujourd\'hui'),
            ('yesterday', 'Hier'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois'),
            ('3months', '3 derniers mois'),
        ],
        method='filter_by_period'
    )
    
    # Filtre de recherche dans le titre et message
    search = django_filters.CharFilter(method='filter_search')
    
    # Filtre par priorité (si vous avez ce champ)
    priority = django_filters.ChoiceFilter(
        choices=[
            ('low', 'Faible'),
            ('medium', 'Moyenne'),
            ('high', 'Haute'),
            ('urgent', 'Urgente'),
        ]
    )
    
    class Meta:
        model = Notification
        fields = ['is_read', 'notification_type', 'priority']
    
    def filter_by_period(self, queryset, name, value):
        """Filtre par période prédéfinie"""
        now = timezone.now()
        
        if value == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start_date)
        
        elif value == 'yesterday':
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return queryset.filter(created_at__range=[start_date, end_date])
        
        elif value == 'week':
            # Début de la semaine (lundi)
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return queryset.filter(created_at__gte=start_date)
        
        elif value == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start_date)
        
        elif value == '3months':
            start_date = now - timedelta(days=90)
            return queryset.filter(created_at__gte=start_date)
        
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Recherche dans le titre et le message"""
        return queryset.filter(
            Q(title__icontains=value) | Q(message__icontains=value)
        )


class NotificationListCreateView(generics.ListCreateAPIView):
    """Vue pour lister et créer des notifications avec pagination et filtres"""
    
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = NotificationFilter
    ordering_fields = ['created_at', 'is_read', 'notification_type']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NotificationCreateSerializer
        return NotificationListSerializer
    
    def get_queryset(self):
        """Retourne les notifications de l'utilisateur connecté"""
        return Notification.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Associe l'utilisateur connecté à la notification"""
        serializer.save(user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Override pour ajouter des métadonnées dans la réponse"""
        response = super().list(request, *args, **kwargs)
        
        # Ajouter des statistiques de base
        queryset = self.filter_queryset(self.get_queryset())
        total_count = queryset.count()
        unread_count = queryset.filter(is_read=False).count()
        
        response.data['meta'] = {
            'total_filtered': total_count,
            'unread_filtered': unread_count,
            'filters_applied': bool(request.query_params)
        }
        
        return response


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vue pour récupérer, modifier ou supprimer une notification"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return NotificationUpdateSerializer
        return NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """Vue pour récupérer et modifier les préférences de notification"""
    
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Récupère ou crée les préférences de l'utilisateur"""
        preference, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preference


class NotificationSummaryView(APIView):
    """Vue pour obtenir un résumé des notifications avec filtres optionnels"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        notifications = Notification.objects.filter(user=user)
        
        # Appliquer les filtres si fournis
        notification_type = request.query_params.get('type')
        period = request.query_params.get('period')
        
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        if period:
            filter_instance = NotificationFilter()
            notifications = filter_instance.filter_by_period(notifications, 'period', period)
        
        total_count = notifications.count()
        unread_count = notifications.filter(is_read=False).count()
        recent_notifications = notifications.order_by('-created_at')[:5]
        
        # Statistiques par type
        type_stats = dict(
            notifications.values('notification_type')
            .annotate(count=Count('id'))
            .values_list('notification_type', 'count')
        )
        
        data = {
            'total_count': total_count,
            'unread_count': unread_count,
            'recent_notifications': recent_notifications,
            'type_statistics': type_stats
        }
        
        serializer = NotificationSummarySerializer(data)
        return Response(serializer.data)


class MarkAllAsReadView(APIView):
    """Vue pour marquer toutes les notifications comme lues avec filtres optionnels"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        unread_notifications = Notification.objects.filter(
            user=user, 
            is_read=False
        )
        
        # Appliquer les filtres si fournis
        notification_type = request.data.get('type')
        if notification_type:
            unread_notifications = unread_notifications.filter(
                notification_type=notification_type
            )
        
        marked_count = unread_notifications.count()
        unread_notifications.update(is_read=True)
        
        data = {
            'success': True,
            'marked_count': marked_count,
            'message': f'{marked_count} notifications marquées comme lues'
        }
        
        serializer = MarkAllAsReadSerializer(data)
        return Response(serializer.data)


class MarkAsReadView(APIView):
    """Vue pour marquer une notification spécifique comme lue"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        notification = get_object_or_404(
            Notification, 
            pk=pk, 
            user=request.user
        )
        
        notification.is_read = True
        notification.save()
        
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)


class NotificationStatsView(APIView):
    """Vue pour obtenir des statistiques détaillées sur les notifications"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        notifications = Notification.objects.filter(user=user)
        
        # Appliquer les filtres de période si fournis
        period = request.query_params.get('period', 'month')
        filter_instance = NotificationFilter()
        
        if period:
            notifications = filter_instance.filter_by_period(notifications, 'period', period)
        
        # Statistiques de base
        total_notifications = notifications.count()
        unread_notifications = notifications.filter(is_read=False).count()
        
        # Notifications par type
        notifications_by_type = dict(
            notifications.values('notification_type')
            .annotate(count=Count('id'))
            .values_list('notification_type', 'count')
        )
        
        # Notifications par statut de lecture
        read_stats = {
            'read': notifications.filter(is_read=True).count(),
            'unread': unread_notifications
        }
        
        # Activité par jour (pour la période sélectionnée)
        daily_activity = list(
            notifications.extra(select={'day': 'date(created_at)'})
            .values('day')
            .annotate(
                total=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            )
            .order_by('day')
        )
        
        # Notifications par priorité (si ce champ existe)
        priority_stats = {}
        if hasattr(Notification, 'priority'):
            priority_stats = dict(
                notifications.values('priority')
                .annotate(count=Count('id'))
                .values_list('priority', 'count')
            )
        
        data = {
            'period': period,
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'notifications_by_type': notifications_by_type,
            'read_statistics': read_stats,
            'daily_activity': daily_activity,
            'priority_statistics': priority_stats
        }
        
        serializer = NotificationStatsSerializer(data)
        return Response(serializer.data)


class UnreadNotificationsView(generics.ListAPIView):
    """Vue pour lister uniquement les notifications non lues avec pagination"""
    
    serializer_class = NotificationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = NotificationFilter
    ordering_fields = ['created_at', 'notification_type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user,
            is_read=False
        )


class DeleteAllReadNotificationsView(APIView):
    """Vue pour supprimer toutes les notifications lues avec filtres optionnels"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request):
        user = request.user
        read_notifications = Notification.objects.filter(
            user=user,
            is_read=True
        )
        
        # Appliquer les filtres si fournis
        notification_type = request.data.get('type')
        older_than_days = request.data.get('older_than_days')
        
        if notification_type:
            read_notifications = read_notifications.filter(
                notification_type=notification_type
            )
        
        if older_than_days:
            cutoff_date = timezone.now() - timedelta(days=int(older_than_days))
            read_notifications = read_notifications.filter(
                created_at__lt=cutoff_date
            )
        
        deleted_count = read_notifications.count()
        read_notifications.delete()
        
        return Response({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} notifications supprimées avec succès'
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notification_count(request):
    """Vue fonction pour obtenir rapidement le nombre de notifications non lues"""
    
    # Compter par type si demandé
    by_type = request.query_params.get('by_type', 'false').lower() == 'true'
    
    if by_type:
        counts = dict(
            Notification.objects.filter(user=request.user, is_read=False)
            .values('notification_type')
            .annotate(count=Count('id'))
            .values_list('notification_type', 'count')
        )
        total_count = sum(counts.values())
        
        return Response({
            'total_unread': total_count,
            'by_type': counts
        })
    else:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return Response({
            'unread_count': unread_count
        })


class BulkMarkAsReadView(APIView):
    """Vue pour marquer plusieurs notifications comme lues"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        notification_ids = request.data.get('notification_ids', [])
        
        if not notification_ids:
            return Response(
                {'error': 'Aucun ID de notification fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=request.user,
            is_read=False
        )
        
        marked_count = notifications.count()
        notifications.update(is_read=True)
        
        return Response({
            'success': True,
            'marked_count': marked_count,
            'message': f'{marked_count} notifications marquées comme lues'
        })


class BulkDeleteView(APIView):
    """Vue pour supprimer plusieurs notifications en masse"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request):
        notification_ids = request.data.get('notification_ids', [])
        
        if not notification_ids:
            return Response(
                {'error': 'Aucun ID de notification fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=request.user
        )
        
        deleted_count = notifications.count()
        notifications.delete()
        
        return Response({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} notifications supprimées avec succès'
        })


class NotificationsByTypeView(generics.ListAPIView):
    """Vue pour lister les notifications par type avec pagination"""
    
    serializer_class = NotificationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        notification_type = self.kwargs.get('notification_type')
        return Notification.objects.filter(
            user=self.request.user,
            notification_type=notification_type
        )


class NotificationSearchView(generics.ListAPIView):
    """Vue dédiée à la recherche de notifications"""
    
    serializer_class = NotificationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'message', 'notification_type']
    ordering_fields = ['created_at', 'is_read']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)