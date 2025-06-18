# =============================================================================
# files/views.py
# =============================================================================

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
import logging
from uuid import UUID

from .models import TranslationFile, TranslationString
from .serializers import (
    TranslationFileListSerializer,
    TranslationFileDetailSerializer,
    TranslationFileCreateSerializer,
    TranslationStringListSerializer,
    TranslationStringDetailSerializer
)
from .filters import TranslationFileFilter, TranslationStringFilter
from .pagination import TranslationFilePagination, TranslationStringPagination

logger = logging.getLogger(__name__)


class TranslationFileViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des fichiers de traduction"""
    
    queryset = TranslationFile.objects.select_related('uploaded_by').all()
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TranslationFileFilter
    search_fields = ['original_filename', 'uploaded_by__email']
    ordering_fields = ['uploaded_at', 'file_size', 'status', 'original_filename']
    ordering = ['-uploaded_at']
    pagination_class = TranslationFilePagination

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        try:
            if self.action == 'create':
                return TranslationFileCreateSerializer
            elif self.action in ['retrieve', 'update', 'partial_update']:
                return TranslationFileDetailSerializer
            return TranslationFileListSerializer
        except Exception as e:
            logger.error(f"Erreur lors de la sélection du serializer: {e}")
            return TranslationFileListSerializer

    def get_queryset(self):
        """Filtre les fichiers par utilisateur si non admin"""
        try:
            queryset = super().get_queryset()
            if not self.request.user.is_staff:
                queryset = queryset.filter(uploaded_by=self.request.user)
            return queryset
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du queryset: {e}")
            return TranslationFile.objects.none()

    def handle_exception(self, exc):
        """Gestion centralisée des exceptions"""
        if isinstance(exc, ObjectDoesNotExist):
            return Response(
                {'error': 'Ressource non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        elif isinstance(exc, PermissionDenied):
            return Response(
                {'error': 'Permissions insuffisantes'},
                status=status.HTTP_403_FORBIDDEN
            )
        elif isinstance(exc, ValidationError):
            return Response(
                {'error': 'Données invalides', 'details': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            logger.error(f"Erreur non gérée dans TranslationFileViewSet: {exc}")
            return super().handle_exception(exc)

    @method_decorator(cache_page(60 * 5))  # Cache 5 minutes
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Retourne les statistiques des fichiers"""
        try:
            queryset = self.get_queryset()
            
            # Vérifier que le queryset n'est pas vide
            if not queryset.exists():
                return Response({
                    'total_files': 0,
                    'by_status': {},
                    'by_type': {},
                    'total_size': 0,
                    'total_strings': 0
                })
            
            # Calculs avec gestion d'erreurs
            total_files = queryset.count()
            
            # Statistiques par statut avec gestion des valeurs nulles
            by_status = {}
            try:
                status_counts = queryset.values('status').annotate(count=Count('id'))
                by_status = {item['status']: item['count'] for item in status_counts if item['status']}
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des statistiques par statut: {e}")
                by_status = {}
            
            # Statistiques par type avec gestion des valeurs nulles
            by_type = {}
            try:
                type_counts = queryset.values('file_type').annotate(count=Count('id'))
                by_type = {item['file_type']: item['count'] for item in type_counts if item['file_type']}
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des statistiques par type: {e}")
                by_type = {}
            
            # Taille totale avec gestion des valeurs nulles
            total_size = 0
            try:
                size_aggregate = queryset.aggregate(total=Sum('file_size'))
                total_size = size_aggregate['total'] or 0
            except Exception as e:
                logger.warning(f"Erreur lors du calcul de la taille totale: {e}")
                total_size = 0
            
            # Nombre total de chaînes avec gestion des valeurs nulles
            total_strings = 0
            try:
                strings_aggregate = queryset.aggregate(total=Sum('total_strings'))
                total_strings = strings_aggregate['total'] or 0
            except Exception as e:
                logger.warning(f"Erreur lors du calcul du nombre total de chaînes: {e}")
                total_strings = 0
            
            stats = {
                'total_files': total_files,
                'by_status': by_status,
                'by_type': by_type,
                'total_size': total_size,
                'total_strings': total_strings
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques: {e}")
            return Response(
                {'error': 'Erreur lors du calcul des statistiques'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """Relance le traitement d'un fichier"""
        try:
            file_obj = self.get_object()
            
            # Vérifier les permissions
            if not request.user.is_staff and file_obj.uploaded_by != request.user:
                raise PermissionDenied("Vous n'avez pas la permission de retraiter ce fichier")
            
            if file_obj.status == 'processing':
                return Response(
                    {'error': 'Le fichier est déjà en cours de traitement'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vérifier que le fichier existe encore
            if not file_obj.file_path or not file_obj.file_path.name:
                return Response(
                    {'error': 'Fichier source non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Transaction pour assurer la cohérence
            with transaction.atomic():
                # Supprimer les anciennes chaînes
                try:
                    deleted_count = file_obj.translationstring_set.all().delete()[0]
                    logger.info(f"Suppression de {deleted_count} chaînes pour le fichier {file_obj.id}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression des chaînes: {e}")
                
                # Relancer le traitement
                try:
                    from .tasks import process_translation_file
                    task = process_translation_file.delay(file_obj.id)
                    file_obj.task_id = task.id
                    file_obj.status = 'processing'
                    file_obj.error_message = ''
                    file_obj.total_strings = 0
                    file_obj.save()
                    
                    logger.info(f"Retraitement lancé pour le fichier {file_obj.id}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors du lancement du retraitement: {e}")
                    return Response(
                        {'error': 'Erreur lors du lancement du retraitement'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            return Response({
                'message': 'Retraitement lancé',
                'task_id': file_obj.task_id
            })
            
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Fichier non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f"Erreur lors du retraitement du fichier {pk}: {e}")
            return Response(
                {'error': 'Erreur interne du serveur'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Télécharge le fichier original"""
        try:
            file_obj = self.get_object()
            
            # Vérifier les permissions
            if not request.user.is_staff and file_obj.uploaded_by != request.user:
                raise PermissionDenied("Vous n'avez pas la permission de télécharger ce fichier")
            
            # Vérifier que le fichier existe
            if not file_obj.file_path or not file_obj.file_path.name:
                return Response(
                    {'error': 'Fichier non disponible'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Vérifier que le fichier existe physiquement
            try:
                file_exists = file_obj.file_path.storage.exists(file_obj.file_path.name)
                if not file_exists:
                    return Response(
                        {'error': 'Fichier physique non trouvé'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            except Exception as e:
                logger.error(f"Erreur lors de la vérification du fichier: {e}")
                return Response(
                    {'error': 'Erreur lors de l\'accès au fichier'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            try:
                download_url = file_obj.file_path.url
            except Exception as e:
                logger.error(f"Erreur lors de la génération de l'URL: {e}")
                return Response(
                    {'error': 'Erreur lors de la génération du lien de téléchargement'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'download_url': download_url,
                'filename': file_obj.original_filename,
                'size': file_obj.file_size
            })
            
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Fichier non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier {pk}: {e}")
            return Response(
                {'error': 'Erreur interne du serveur'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Retourne le progrès de traitement"""
        try:
            file_obj = self.get_object()
            
            # Vérifier les permissions
            if not request.user.is_staff and file_obj.uploaded_by != request.user:
                raise PermissionDenied("Vous n'avez pas la permission de voir ce fichier")
            
            if file_obj.status != 'processing':
                progress_value = 100 if file_obj.status == 'completed' else 0
                return Response({
                    'progress': progress_value,
                    'status': file_obj.status,
                    'error_message': file_obj.error_message if file_obj.status == 'error' else None
                })
            
            if not hasattr(file_obj, 'task_id') or not file_obj.task_id:
                return Response({
                    'progress': 0, 
                    'status': 'unknown',
                    'error': 'Task ID manquant'
                })
            
            try:
                from celery.result import AsyncResult
                result = AsyncResult(file_obj.task_id)
                
                if result.state == 'PROGRESS':
                    info = result.info or {}
                    return Response({
                        'progress': info.get('current', 0),
                        'total': info.get('total', 100),
                        'status': 'processing',
                        'strings_created': info.get('strings_created', 0)
                    })
                elif result.state == 'SUCCESS':
                    return Response({
                        'progress': 100, 
                        'status': 'completed',
                        'result': result.result
                    })
                elif result.state == 'FAILURE':
                    error_msg = str(result.info) if result.info else 'Erreur inconnue'
                    return Response({
                        'progress': 0, 
                        'status': 'error',
                        'error': error_msg
                    })
                else:
                    return Response({
                        'progress': 0, 
                        'status': result.state.lower(),
                        'info': 'Statut de tâche non reconnu'
                    })
                    
            except ImportError:
                logger.error("Celery non disponible pour vérifier le progrès")
                return Response({
                    'progress': 0, 
                    'status': 'error',
                    'error': 'Service de traitement non disponible'
                })
            except Exception as e:
                logger.error(f"Erreur lors de la vérification du progrès: {e}")
                return Response({
                    'progress': 0, 
                    'status': 'error',
                    'error': 'Erreur lors de la vérification du progrès'
                })
            
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Fichier non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du progrès du fichier {pk}: {e}")
            return Response(
                {'error': 'Erreur interne du serveur'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    def create(self, request, *args, **kwargs):
        """Upload d'un fichier avec réponse complète"""
        serializer = TranslationFileCreateSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Créer le fichier
            translation_file = serializer.save()
            
            # Utiliser le serializer détaillé existant pour la réponse
            response_serializer = TranslationFileDetailSerializer(translation_file)
            
            return Response({
                'success': True,
                'message': 'Fichier uploadé avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Erreur lors de l\'upload',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)




class TranslationStringViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des chaînes de traduction"""
    
    queryset = TranslationString.objects.select_related('file', 'file__uploaded_by').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TranslationStringFilter
    search_fields = ['key', 'source_text', 'context']
    ordering_fields = ['created_at', 'line_number', 'key', 'is_translated']
    ordering = ['line_number', 'key']
    pagination_class = TranslationStringPagination

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        try:
            if self.action in ['retrieve', 'update', 'partial_update']:
                return TranslationStringDetailSerializer
            return TranslationStringListSerializer
        except Exception as e:
            logger.error(f"Erreur lors de la sélection du serializer: {e}")
            return TranslationStringListSerializer

    def get_queryset(self):
        """Filtre les chaînes par utilisateur si non admin"""
        try:
            queryset = super().get_queryset()
            if not self.request.user.is_staff:
                queryset = queryset.filter(file__uploaded_by=self.request.user)
            return queryset
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du queryset: {e}")
            return TranslationString.objects.none()

    def handle_exception(self, exc):
        """Gestion centralisée des exceptions"""
        if isinstance(exc, ObjectDoesNotExist):
            return Response(
                {'error': 'Ressource non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        elif isinstance(exc, PermissionDenied):
            return Response(
                {'error': 'Permissions insuffisantes'},
                status=status.HTTP_403_FORBIDDEN
            )
        elif isinstance(exc, ValidationError):
            return Response(
                {'error': 'Données invalides', 'details': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            logger.error(f"Erreur non gérée dans TranslationStringViewSet: {exc}")
            return super().handle_exception(exc)

    @action(detail=False, methods=['get'])
    def by_file(self, request):
        """Retourne les chaînes groupées par fichier"""
        try:
            file_id = request.query_params.get('file_id')
            if not file_id:
                return Response(
                    {'error': 'Paramètre file_id requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Valider que file_id est un entier
            try:
                file_id = UUID(file_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'file_id doit être un entier valide'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vérifier que le fichier existe et que l'utilisateur y a accès
            try:
                file_obj = TranslationFile.objects.get(id=file_id)
                if not request.user.is_staff and file_obj.uploaded_by != request.user:
                    raise PermissionDenied("Vous n'avez pas accès à ce fichier")
            except TranslationFile.DoesNotExist:
                return Response(
                    {'error': 'Fichier non trouvé'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            queryset = self.get_queryset().filter(file_id=file_id)
            
            # Appliquer les filtres avec gestion d'erreurs
            try:
                queryset = self.filter_queryset(queryset)
            except Exception as e:
                logger.warning(f"Erreur lors de l'application des filtres: {e}")
                # Continuer avec le queryset non filtré
            
            # Paginer avec gestion d'erreurs
            try:
                page = self.paginate_queryset(queryset)
                if page is not None:
                    serializer = self.get_serializer(page, many=True)
                    return self.get_paginated_response(serializer.data)
            except Exception as e:
                logger.error(f"Erreur lors de la pagination: {e}")
                # Retourner les données sans pagination
            
            try:
                serializer = self.get_serializer(queryset, many=True)
                return Response(serializer.data)
            except Exception as e:
                logger.error(f"Erreur lors de la sérialisation: {e}")
                return Response(
                    {'error': 'Erreur lors de la récupération des données'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des chaînes par fichier: {e}")
            return Response(
                {'error': 'Erreur interne du serveur'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @method_decorator(cache_page(60 * 2))  # Cache 2 minutes
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Retourne les statistiques des chaînes"""
        try:
            queryset = self.get_queryset()
            
            # Vérifier que le queryset n'est pas vide
            if not queryset.exists():
                return Response({
                    'total_strings': 0,
                    'translated': 0,
                    'untranslated': 0,
                    'fuzzy': 0,
                    'plural': 0,
                    'by_file': {},
                    'progress_percentage': 0
                })
            
            # Calculs avec gestion d'erreurs
            total_strings = queryset.count()
            
            # Compteurs avec gestion d'erreurs
            translated = 0
            untranslated = 0
            fuzzy = 0
            plural = 0
            
            try:
                translated = queryset.filter(is_translated=True).count()
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des chaînes traduites: {e}")
            
            try:
                untranslated = queryset.filter(is_translated=False).count()
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des chaînes non traduites: {e}")
            
            try:
                fuzzy = queryset.filter(is_fuzzy=True).count()
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des chaînes fuzzy: {e}")
            
            try:
                plural = queryset.filter(is_plural=True).count()
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des chaînes plurielles: {e}")
            
            # Statistiques par fichier avec gestion d'erreurs
            by_file = {}
            try:
                file_counts = queryset.values('file__original_filename').annotate(count=Count('id'))
                by_file = {
                    item['file__original_filename']: item['count'] 
                    for item in file_counts 
                    if item['file__original_filename']
                }
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des statistiques par fichier: {e}")
            
            # Calcul du pourcentage de progression
            progress_percentage = 0
            if total_strings > 0:
                try:
                    progress_percentage = round((translated / total_strings) * 100, 2)
                except (ZeroDivisionError, TypeError):
                    progress_percentage = 0
            
            stats = {
                'total_strings': total_strings,
                'translated': translated,
                'untranslated': untranslated,
                'fuzzy': fuzzy,
                'plural': plural,
                'by_file': by_file,
                'progress_percentage': progress_percentage
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques des chaînes: {e}")
            return Response(
                {'error': 'Erreur lors du calcul des statistiques'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )