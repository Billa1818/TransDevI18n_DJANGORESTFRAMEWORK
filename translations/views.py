from django.shortcuts import render

# Create your views here.

# =============================================================================
# APP: translations - Views (API pour traductions de fichiers uniquement)
# =============================================================================

# translations/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from .models import Language, Translation, TranslationTask
from .serializers import (
    LanguageSerializer, TranslationSerializer, TranslationCreateSerializer,
    TranslationTaskSerializer, TranslationTaskCreateSerializer,
    FileTranslationStatusSerializer, FileTranslationsDetailSerializer
)
from .pagination import StandardResultsSetPagination, LargeResultsSetPagination, SmallResultsSetPagination
from .filters import TranslationFilter, TranslationTaskFilter, LanguageFilter
from .services import google_translate_service
from .tasks import translate_file_task, detect_file_language_task
from files.models import TranslationFile, TranslationString
import logging

logger = logging.getLogger(__name__)

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """Vues pour les langues supportées"""
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = LanguageFilter
    search_fields = ['code', 'name', 'native_name']
    ordering_fields = ['code', 'name', 'native_name']
    ordering = ['name']
    
    @action(detail=False, methods=['get'])
    def supported(self, request):
        """Retourne les langues supportées par Google Translate"""
        try:
            supported_languages = google_translate_service.get_supported_languages()
            return Response({
                'supported_languages': supported_languages,
                'message': 'Langues supportées récupérées avec succès'
            })
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des langues: {str(e)}")
            return Response({
                'error': 'Erreur lors de la récupération des langues supportées'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TranslationViewSet(viewsets.ModelViewSet):
    """Vues pour consulter les traductions existantes"""
    queryset = Translation.objects.all()
    serializer_class = TranslationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = TranslationFilter
    search_fields = ['string__key', 'string__source_text', 'translated_text']
    ordering_fields = ['created_at', 'updated_at', 'confidence_score', 'is_approved']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filtre les traductions par utilisateur (fichiers de l'utilisateur)"""
        return Translation.objects.filter(string__file__uploaded_by=self.request.user)

class TranslationTaskViewSet(viewsets.ModelViewSet):
    """Vues pour les tâches de traduction de fichiers"""
    serializer_class = TranslationTaskSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = TranslationTaskFilter
    search_fields = ['file__original_filename', 'error_message']
    ordering_fields = ['created_at', 'started_at', 'completed_at', 'progress', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return TranslationTask.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TranslationTaskCreateSerializer
        return TranslationTaskSerializer
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Récupère la progression d'une tâche de traduction"""
        task = self.get_object()
        
        # Calculer les statistiques
        total_strings = TranslationString.objects.filter(file=task.file).count()
        translated_strings = Translation.objects.filter(
            string__file=task.file,
            target_language__in=task.target_languages.all()
        ).count()
        
        progress_data = {
            'task_id': task.id,
            'status': task.status,
            'progress': task.progress,
            'total_strings': total_strings,
            'translated_strings': translated_strings,
            'estimated_words': task.estimated_word_count,
            'actual_words': task.actual_word_count,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'error_message': task.error_message
        }
        
        return Response(progress_data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une tâche de traduction"""
        task = self.get_object()
        
        if task.status in ['completed', 'cancelled']:
            return Response({
                'error': 'La tâche ne peut pas être annulée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            task.status = 'cancelled'
            task.save()
            
            return Response({
                'message': 'Tâche annulée avec succès',
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de la tâche: {str(e)}")
            return Response({
                'error': 'Erreur lors de l\'annulation de la tâche'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FileTranslationViewSet(viewsets.ViewSet):
    """Vues pour la gestion des traductions de fichiers"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_files(self, request):
        """
        Liste tous les fichiers de l'utilisateur avec leurs informations de traduction
        """
        try:
            # Récupérer tous les fichiers de l'utilisateur
            files = TranslationFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
            
            files_data = []
            for file in files:
                # Compter les traductions par langue
                translations_by_language = {}
                target_languages = Language.objects.filter(is_active=True)
                
                for language in target_languages:
                    translated_count = Translation.objects.filter(
                        string__file=file,
                        target_language=language
                    ).count()
                    
                    translations_by_language[language.code] = {
                        'language_name': language.name,
                        'translated_count': translated_count,
                        'total_count': file.total_strings,
                        'progress_percentage': (translated_count / file.total_strings * 100) if file.total_strings > 0 else 0
                    }
                
                # Vérifier s'il y a des tâches en cours
                active_tasks = TranslationTask.objects.filter(
                    file=file,
                    status__in=['pending', 'in_progress']
                )
                
                files_data.append({
                    'file_id': str(file.id),
                    'file_name': file.original_filename,
                    'file_type': file.file_type,
                    'total_strings': file.total_strings,
                    'detected_language': file.detected_language,
                    'detected_language_confidence': file.detected_language_confidence,
                    'uploaded_at': file.uploaded_at,
                    'translations_by_language': translations_by_language,
                    'active_tasks': [
                        {
                            'task_id': task.id,
                            'target_languages': [lang.name for lang in task.target_languages.all()],
                            'status': task.status,
                            'progress': task.progress
                        } for task in active_tasks
                    ]
                })
            
            return Response({
                'files': files_data,
                'total_files': len(files_data)
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des fichiers: {str(e)}")
            return Response({
                'error': 'Erreur lors de la récupération des fichiers'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def translate_file(self, request, pk=None):
        """
        Endpoint principal pour traduire un fichier complet
        L'utilisateur choisit un fichier et une langue, et tous les strings sont traduits automatiquement
        """
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        target_language_code = request.data.get('target_language')
        force_retranslate = request.data.get('force_retranslate', False)
        
        if not target_language_code:
            return Response({
                'error': 'La langue cible est requise'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Vérifier que la langue existe
            target_language = get_object_or_404(Language, code=target_language_code, is_active=True)
            detected_language = file.detected_language or None

            # Vérifier qu'il n'y a pas déjà une tâche en cours pour ce fichier et cette langue
            existing_task = TranslationTask.objects.filter(
                file=file,
                target_languages=target_language,
                status__in=['pending', 'in_progress']
            ).first()
            if existing_task:
                return Response({
                    'error': f'Une traduction est déjà en cours pour ce fichier en {target_language.name}',
                    'task_id': existing_task.id,
                    'status': existing_task.status
                }, status=status.HTTP_400_BAD_REQUEST)

            # Compter les strings à traduire
            total_strings = TranslationString.objects.filter(file=file).count()
            if total_strings == 0:
                return Response({
                    'error': 'Ce fichier ne contient aucun texte à traduire'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Vérifier si toutes les chaînes sont déjà traduites pour cette langue cible ET cette langue détectée
            translations_qs = Translation.objects.filter(
                string__file=file,
                target_language=target_language
            )
            already_translated_count = translations_qs.count()
            # On considère la langue détectée comme "source" logique
            # Si la langue détectée a changé, on autorise la retraduction
            previous_detected_language = request.data.get('previous_detected_language')
            langue_detectee_changee = False
            if previous_detected_language and previous_detected_language != detected_language:
                langue_detectee_changee = True

            if already_translated_count == total_strings and not force_retranslate and not langue_detectee_changee:
                return Response({
                    'error': f'Toutes les chaînes de ce fichier sont déjà traduites en {target_language.name} (depuis la langue détectée actuelle).',
                    'info': 'Pour forcer une nouvelle traduction, utilisez force_retranslate=true.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Si on force la retraduction ou si la langue détectée a changé, supprimer les anciennes traductions pour ce fichier/langue cible
            if force_retranslate or langue_detectee_changee:
                translations_qs.delete()

            # Créer et démarrer la tâche de traduction
            with transaction.atomic():
                task = TranslationTask.objects.create(
                    file=file,
                    user=request.user,
                    estimated_word_count=0
                )
                task.target_languages.add(target_language)
                # Démarrer la tâche en arrière-plan
                translate_file_task.delay(task.id, target_language_code)
            return Response({
                'message': f'Traduction du fichier "{file.original_filename}" lancée avec succès',
                'task_id': task.id,
                'file_name': file.original_filename,
                'target_language': target_language.name,
                'total_strings': total_strings,
                'status': 'started',
                'force_retranslate': force_retranslate,
                'langue_detectee_changee': langue_detectee_changee
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Erreur lors de la traduction du fichier: {str(e)}")
            return Response({
                'error': 'Erreur lors du lancement de la traduction'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def detect_language(self, request, pk=None):
        """Détecte automatiquement la langue d'un fichier"""
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        
        try:
            # Lancer la tâche de détection en arrière-plan
            result = detect_file_language_task.delay(str(file.id))
            
            return Response({
                'message': 'Détection de langue lancée en arrière-plan',
                'task_id': result.id,
                'file_id': str(file.id)
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection de langue: {str(e)}")
            return Response({
                'error': 'Erreur lors de la détection de langue'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_detected_language(self, request, pk=None):
        """Met à jour manuellement la langue détectée d'un fichier"""
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        detected_language = request.data.get('detected_language')
        confidence = request.data.get('confidence', 1.0)
        
        if not detected_language:
            return Response({
                'error': 'La langue détectée est requise'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file.detected_language = detected_language
            file.detected_language_confidence = confidence
            file.save()
            
            return Response({
                'message': 'Langue détectée mise à jour avec succès',
                'detected_language': detected_language,
                'confidence': confidence
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la langue: {str(e)}")
            return Response({
                'error': 'Erreur lors de la mise à jour de la langue'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def translations_summary(self, request, pk=None):
        """Récupère un résumé des traductions d'un fichier"""
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        
        # Récupérer toutes les langues cibles disponibles
        target_languages = Language.objects.filter(is_active=True)
        
        summary = {
            'file_id': str(file.id),
            'file_name': file.original_filename,
            'total_strings': file.total_strings,
            'detected_language': file.detected_language,
            'detected_language_confidence': file.detected_language_confidence,
            'translations_by_language': []
        }
        
        for language in target_languages:
            translated_count = Translation.objects.filter(
                string__file=file,
                target_language=language
            ).count()
            
            summary['translations_by_language'].append({
                'language_code': language.code,
                'language_name': language.name,
                'translated_count': translated_count,
                'total_count': file.total_strings,
                'progress_percentage': (translated_count / file.total_strings * 100) if file.total_strings > 0 else 0
            })
        
        return Response(summary)

    @action(detail=True, methods=['get'])
    def translation_status(self, request, pk=None):
        """
        Vérifie si un fichier a déjà au moins une traduction
        Retourne un statut détaillé des traductions du fichier
        """
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        
        try:
            # Compter les traductions totales
            total_translations = Translation.objects.filter(string__file=file).count()
            
            # Vérifier s'il y a des traductions
            has_translations = total_translations > 0
            
            # Récupérer les langues avec des traductions
            languages_with_translations = Translation.objects.filter(
                string__file=file
            ).values_list('target_language__code', flat=True).distinct()
            
            # Compter le nombre de langues avec traductions
            translation_languages_count = len(languages_with_translations)
            
            # Calculer la progression globale
            target_languages = Language.objects.filter(is_active=True)
            total_possible_translations = file.total_strings * target_languages.count()
            overall_progress = (total_translations / total_possible_translations * 100) if total_possible_translations > 0 else 0
            
            # Récupérer la date de la dernière traduction
            last_translation = Translation.objects.filter(
                string__file=file
            ).order_by('-created_at').first()
            last_translation_date = last_translation.created_at if last_translation else None
            
            # Vérifier s'il faut prêter attention
            needs_attention = False
            attention_reasons = []
            
            if not has_translations:
                needs_attention = True
                attention_reasons.append("Aucune traduction trouvée")
            
            if file.total_strings > 0 and overall_progress < 50:
                needs_attention = True
                attention_reasons.append("Progression faible")
            
            # Vérifier les traductions non approuvées
            pending_translations = Translation.objects.filter(
                string__file=file,
                is_approved=False
            ).count()
            
            if pending_translations > 0:
                needs_attention = True
                attention_reasons.append(f"{pending_translations} traductions en attente d'approbation")
            
            # Vérifier les traductions avec faible confiance
            low_confidence_translations = Translation.objects.filter(
                string__file=file,
                confidence_score__lte=0.70
            ).count()
            
            if low_confidence_translations > 0:
                needs_attention = True
                attention_reasons.append(f"{low_confidence_translations} traductions avec faible confiance")
            
            status_data = {
                'file_id': str(file.id),
                'file_name': file.original_filename,
                'has_translations': has_translations,
                'total_strings': file.total_strings,
                'total_translations': total_translations,
                'languages_with_translations': list(languages_with_translations),
                'translation_languages_count': translation_languages_count,
                'overall_progress': round(overall_progress, 2),
                'last_translation_date': last_translation_date,
                'needs_attention': needs_attention,
                'attention_reasons': attention_reasons
            }
            
            serializer = FileTranslationStatusSerializer(status_data)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du statut: {str(e)}")
            return Response({
                'error': 'Erreur lors de la vérification du statut des traductions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def all_translations(self, request, pk=None):
        """
        Récupère toutes les traductions d'un fichier spécifique
        Groupées par langue avec pagination
        """
        file = get_object_or_404(TranslationFile, id=pk, uploaded_by=request.user)
        
        try:
            # Paramètres de pagination
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            
            # Paramètres de filtrage
            target_language_code = request.query_params.get('target_language')
            is_approved = request.query_params.get('is_approved')
            confidence_min = request.query_params.get('confidence_min')
            confidence_max = request.query_params.get('confidence_max')
            
            # Construire le queryset de base
            translations = Translation.objects.filter(string__file=file)
            
            # Appliquer les filtres
            if target_language_code:
                translations = translations.filter(target_language__code=target_language_code)
            
            if is_approved is not None:
                is_approved_bool = is_approved.lower() == 'true'
                translations = translations.filter(is_approved=is_approved_bool)
            
            if confidence_min:
                translations = translations.filter(confidence_score__gte=float(confidence_min))
            
            if confidence_max:
                translations = translations.filter(confidence_score__lte=float(confidence_max))
            
            # Compter le total
            total_translations = translations.count()
            
            # Pagination
            start = (page - 1) * page_size
            end = start + page_size
            translations_page = translations.select_related('string', 'target_language').order_by('target_language__code', 'string__key')[start:end]
            
            # Grouper par langue
            translations_by_language = {}
            for translation in translations_page:
                lang_code = translation.target_language.code
                if lang_code not in translations_by_language:
                    translations_by_language[lang_code] = {
                        'language_name': translation.target_language.name,
                        'language_code': lang_code,
                        'translations': []
                    }
                
                translations_by_language[lang_code]['translations'].append(
                    TranslationSerializer(translation).data
                )
            
            # Calculer les statistiques
            total_approved = Translation.objects.filter(string__file=file, is_approved=True).count()
            total_pending = total_translations - total_approved
            languages_count = Translation.objects.filter(string__file=file).values('target_language').distinct().count()
            
            response_data = {
                'file_info': {
                    'file_id': str(file.id),
                    'file_name': file.original_filename,
                    'file_type': file.file_type,
                    'total_strings': file.total_strings,
                    'detected_language': file.detected_language,
                    'detected_language_confidence': file.detected_language_confidence,
                    'uploaded_at': file.uploaded_at
                },
                'translations': translations_by_language,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_translations': total_translations,
                    'total_pages': (total_translations + page_size - 1) // page_size,
                    'has_next': end < total_translations,
                    'has_previous': page > 1
                },
                'statistics': {
                    'total_translations': total_translations,
                    'approved_translations': total_approved,
                    'pending_translations': total_pending,
                    'languages_count': languages_count,
                    'approval_rate': round((total_approved / total_translations * 100) if total_translations > 0 else 0, 2)
                }
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des traductions: {str(e)}")
            return Response({
                'error': 'Erreur lors de la récupération des traductions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =============================================================================
# APP: translations - Views (API pour traductions avec Google Translate)
# =============================================================================

# translations/views.py
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import models
from django.utils import timezone
from .models import Language, Translation, TranslationTask
from .serializers import (
    LanguageSerializer, TranslationSerializer, TranslationTaskSerializer,
    TranslationCorrectionSerializer, TranslationCorrectionRequestSerializer,
    FailedTranslationsFilterSerializer
)
from .pagination import StandardResultsSetPagination, LargeResultsSetPagination, SmallResultsSetPagination
from .filters import TranslationFilter, TranslationTaskFilter, LanguageFilter
from files.models import TranslationFile, TranslationString
from .tasks import translate_file_task, detect_file_language_task
import logging

logger = logging.getLogger(__name__)

class FailedTranslationsListView(generics.ListAPIView):
    """
    Liste des traductions échouées ou non approuvées pour correction manuelle
    """
    serializer_class = TranslationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SmallResultsSetPagination
    filterset_class = TranslationFilter
    search_fields = ['string__key', 'string__source_text', 'translated_text']
    ordering_fields = ['created_at', 'updated_at', 'confidence_score', 'is_approved']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Retourne les traductions qui nécessitent une correction manuelle"""
        queryset = Translation.objects.select_related('string', 'target_language').all()
        
        # Par défaut, montrer les traductions non approuvées ou avec faible confiance
        # Si des filtres spécifiques sont appliqués, ne pas appliquer le filtre par défaut
        has_specific_filters = any([
            self.request.query_params.get('file_id'),
            self.request.query_params.get('target_language'),
            self.request.query_params.get('is_approved'),
            self.request.query_params.get('confidence_min'),
            self.request.query_params.get('confidence_max'),
            self.request.query_params.get('search'),
            self.request.query_params.get('needs_review'),
            self.request.query_params.get('high_quality'),
            self.request.query_params.get('low_quality'),
        ])
        
        if not has_specific_filters:
            queryset = queryset.filter(
                Q(is_approved=False) | Q(confidence_score__lte=0.70)
            )
        
        return queryset

class TranslationCorrectionView(APIView):
    """
    Vue pour corriger manuellement une traduction
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, translation_id):
        """Récupérer une traduction spécifique pour correction"""
        try:
            translation = Translation.objects.select_related('string', 'target_language').get(id=translation_id)
            serializer = TranslationSerializer(translation)
            return Response(serializer.data)
        except Translation.DoesNotExist:
            return Response(
                {'error': 'Traduction non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def put(self, request, translation_id):
        """Corriger manuellement une traduction"""
        try:
            translation = Translation.objects.get(id=translation_id)
            
            # Valider les données de correction
            correction_serializer = TranslationCorrectionRequestSerializer(data=request.data)
            if not correction_serializer.is_valid():
                return Response(
                    correction_serializer.errors, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mettre à jour la traduction
            corrected_text = correction_serializer.validated_data['corrected_text']
            is_approved = correction_serializer.validated_data['is_approved']
            comment = correction_serializer.validated_data.get('comment', '')
            
            # Mettre à jour la traduction
            translation.translated_text = corrected_text
            translation.is_approved = is_approved
            translation.updated_at = timezone.now()
            translation.save()
            
            # Log de la correction
            logger.info(
                f"Traduction {translation_id} corrigée manuellement par {request.user.email}. "
                f"Texte: '{corrected_text[:50]}...' Approuvé: {is_approved}"
            )
            
            # Retourner la traduction mise à jour
            serializer = TranslationSerializer(translation)
            return Response({
                'message': 'Traduction corrigée avec succès',
                'translation': serializer.data
            })
            
        except Translation.DoesNotExist:
            return Response(
                {'error': 'Traduction non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur lors de la correction de traduction: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la correction'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BulkTranslationCorrectionView(APIView):
    """
    Vue pour corriger plusieurs traductions en une fois
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Corriger plusieurs traductions en une fois"""
        corrections = request.data.get('corrections', [])
        
        if not corrections:
            return Response(
                {'error': 'Aucune correction fournie'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        success_count = 0
        error_count = 0
        
        for correction_data in corrections:
            try:
                # Valider les données de correction
                correction_serializer = TranslationCorrectionRequestSerializer(data=correction_data)
                if not correction_serializer.is_valid():
                    results.append({
                        'translation_id': correction_data.get('translation_id'),
                        'success': False,
                        'error': correction_serializer.errors
                    })
                    error_count += 1
                    continue
                
                # Récupérer et mettre à jour la traduction
                translation_id = correction_serializer.validated_data['translation_id']
                translation = Translation.objects.get(id=translation_id)
                
                translation.translated_text = correction_serializer.validated_data['corrected_text']
                translation.is_approved = correction_serializer.validated_data['is_approved']
                translation.updated_at = timezone.now()
                translation.save()
                
                results.append({
                    'translation_id': translation_id,
                    'success': True,
                    'message': 'Traduction corrigée'
                })
                success_count += 1
                
            except Translation.DoesNotExist:
                results.append({
                    'translation_id': correction_data.get('translation_id'),
                    'success': False,
                    'error': 'Traduction non trouvée'
                })
                error_count += 1
            except Exception as e:
                results.append({
                    'translation_id': correction_data.get('translation_id'),
                    'success': False,
                    'error': str(e)
                })
                error_count += 1
        
        # Log du résultat
        logger.info(
            f"Correction en lot effectuée par {request.user.email}. "
            f"Succès: {success_count}, Erreurs: {error_count}"
        )
        
        return Response({
            'message': f'Correction en lot terminée. Succès: {success_count}, Erreurs: {error_count}',
            'results': results,
            'summary': {
                'total': len(corrections),
                'success': success_count,
                'errors': error_count
            }
        })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def translation_statistics(request):
    """
    Statistiques sur les traductions pour aider à identifier les problèmes
    """
    try:
        # Statistiques générales
        total_translations = Translation.objects.count()
        approved_translations = Translation.objects.filter(is_approved=True).count()
        failed_translations = Translation.objects.filter(is_approved=False).count()
        low_confidence_translations = Translation.objects.filter(confidence_score__lte=0.70).count()
        
        # Statistiques par langue
        language_stats = []
        languages = Language.objects.filter(is_active=True)
        for lang in languages:
            lang_translations = Translation.objects.filter(target_language=lang)
            lang_stats = {
                'language': lang.code,
                'language_name': lang.name,
                'total': lang_translations.count(),
                'approved': lang_translations.filter(is_approved=True).count(),
                'failed': lang_translations.filter(is_approved=False).count(),
                'low_confidence': lang_translations.filter(confidence_score__lte=0.70).count(),
                'avg_confidence': lang_translations.aggregate(avg_confidence=models.Avg('confidence_score'))['avg_confidence'] or 0.0
            }
            language_stats.append(lang_stats)
        
        # Statistiques par fichier
        file_stats = []
        files = TranslationFile.objects.all()
        for file in files:
            file_translations = Translation.objects.filter(string__file=file)
            file_stats.append({
                'file_id': file.id,
                'filename': file.original_filename,
                'total': file_translations.count(),
                'approved': file_translations.filter(is_approved=True).count(),
                'failed': file_translations.filter(is_approved=False).count(),
                'low_confidence': file_translations.filter(confidence_score__lte=0.70).count()
            })
        
        return Response({
            'general': {
                'total_translations': total_translations,
                'approved_translations': approved_translations,
                'failed_translations': failed_translations,
                'low_confidence_translations': low_confidence_translations,
                'approval_rate': (approved_translations / total_translations * 100) if total_translations > 0 else 0
            },
            'by_language': language_stats,
            'by_file': file_stats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {str(e)}")
        return Response(
            {'error': 'Erreur lors du calcul des statistiques'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
