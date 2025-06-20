# =============================================================================
# APP: translations - Tasks (Tâches pour traductions de fichiers uniquement)
# =============================================================================

# translations/tasks.py
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Translation, TranslationTask, Language
from .services import google_translate_service
from files.models import TranslationFile, TranslationString
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def translate_file_task(self, task_id, target_language_code):
    """
    Tâche pour traduire tous les strings d'un fichier
    """
    try:
        try:
            task = TranslationTask.objects.get(id=task_id)
        except TranslationTask.DoesNotExist:
            logger.error(f"Tâche de traduction {task_id} non trouvée")
            return {'status': 'failed', 'error': 'Tâche non trouvée'}

        file = task.file
        target_language = Language.objects.get(code=target_language_code)
        
        # Mettre à jour le statut
        task.status = 'in_progress'
        task.started_at = timezone.now()
        task.save()
        
        # Récupérer tous les strings du fichier
        strings = TranslationString.objects.filter(file=file)
        total_strings = strings.count()
        
        if total_strings == 0:
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()
            return {'status': 'completed', 'message': 'Aucun string à traduire'}
        
        # Configuration des batches
        BATCH_SIZE = 10  # Nombre de chaînes par batch
        BATCH_PAUSE = 5  # Pause en secondes entre les batches
        
        # Traduire chaque string par batches
        translated_count = 0
        actual_word_count = 0
        
        for i, string in enumerate(strings):
            # Vérifier si la traduction existe déjà
            existing_translation = Translation.objects.filter(
                string=string,
                target_language=target_language
            ).first()
            
            if existing_translation:
                translated_count += 1
                continue
            
            try:
                # Détecter la langue source si pas encore détectée
                source_language = 'auto'
                if file.detected_language:
                    source_language = file.detected_language
                
                logger.info(f"Traduction du string {string.id}: '{string.source_text[:50]}...' vers {target_language_code}")
                
                # Traduire le texte
                result = google_translate_service.translate_text(
                    string.source_text,
                    target_language_code,
                    source_language
                )
                
                logger.info(f"Résultat de traduction pour string {string.id}: {result}")
                
                # Vérifier que le résultat n'est pas None
                if result is None:
                    logger.warning(f"Résultat de traduction None pour string {string.id}")
                    continue
                
                # Vérifier que le résultat est un dictionnaire
                if not isinstance(result, dict):
                    logger.error(f"Résultat de traduction invalide pour string {string.id}: {type(result)} - {result}")
                    continue
                
                if result.get('error'):
                    logger.warning(f"Erreur de traduction pour string {string.id}: {result['error']}")
                    continue
                
                # Vérifier que le texte traduit existe
                if not result.get('text'):
                    logger.warning(f"Texte traduit vide pour string {string.id}")
                    continue
                
                # Si il y a une erreur mais que le texte est conservé, créer quand même la traduction
                if result.get('error') and result.get('text') == string.source_text:
                    logger.warning(f"Erreur de traduction pour string {string.id}: {result['error']} - texte original conservé")
                    # Créer quand même la traduction avec le texte original
                    with transaction.atomic():
                        translation = Translation.objects.create(
                            string=string,
                            target_language=target_language,
                            translated_text=result['text'],
                            confidence_score=0.0,  # Confiance à 0 car erreur
                            is_approved=False  # Pas approuvé car erreur
                        )
                    
                    logger.info(f"Traduction avec texte original créée pour string {string.id}")
                    translated_count += 1
                    actual_word_count += len(string.source_text.split())
                    
                    # Mettre à jour la progression
                    progress = (i + 1) / total_strings * 100
                    task.progress = progress
                    task.actual_word_count = actual_word_count
                    task.save()
                    
                    # Mettre à jour la tâche Celery
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i + 1,
                            'total': total_strings,
                            'progress': progress
                        }
                    )
                    continue
                
                # Si il y a une erreur et pas de texte, passer au suivant
                if result.get('error'):
                    logger.warning(f"Erreur de traduction pour string {string.id}: {result['error']}")
                    continue
                
                # Créer la traduction
                with transaction.atomic():
                    translation = Translation.objects.create(
                        string=string,
                        target_language=target_language,
                        translated_text=result['text'],
                        confidence_score=result.get('confidence', 0.0),
                        is_approved=True
                    )
                
                logger.info(f"Traduction créée avec succès pour string {string.id}")
                translated_count += 1
                actual_word_count += len(string.source_text.split())
                
                # Mettre à jour la progression
                progress = (i + 1) / total_strings * 100
                task.progress = progress
                task.actual_word_count = actual_word_count
                task.save()
                
                # Mettre à jour la tâche Celery
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': total_strings,
                        'progress': progress
                    }
                )
                
            except Exception as e:
                logger.error(f"Erreur lors de la traduction du string {string.id}: {str(e)}", exc_info=True)
                continue
            
            # Pause après chaque batch pour éviter les limitations
            if (i + 1) % BATCH_SIZE == 0 and i < total_strings - 1:
                logger.info(f"Batch terminé ({i + 1}/{total_strings}). Pause de {BATCH_PAUSE} secondes...")
                time.sleep(BATCH_PAUSE)
                logger.info("Reprise de la traduction...")
        
        # Finaliser la tâche
        task.status = 'completed'
        task.progress = 100.0
        task.completed_at = timezone.now()
        task.save()
        
        return {
            'status': 'completed',
            'translated_count': translated_count,
            'total_strings': total_strings,
            'actual_word_count': actual_word_count
        }
        
    except Exception as e:
        logger.error(f"Erreur dans la tâche de traduction de fichier: {str(e)}")
        
        # Marquer la tâche comme échouée
        try:
            task = TranslationTask.objects.get(id=task_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
        except:
            pass
        
        raise

@shared_task
def detect_file_language_task(file_id):
    """
    Tâche pour détecter automatiquement la langue d'un fichier
    """
    try:
        file = TranslationFile.objects.get(id=file_id)
        
        # Récupérer quelques strings pour la détection
        sample_strings = TranslationString.objects.filter(file=file)[:10]
        
        if not sample_strings:
            return {'error': 'Aucun string trouvé dans le fichier'}
        
        # Concaténer les textes pour la détection
        combined_text = ' '.join([s.source_text for s in sample_strings])
        
        # Détecter la langue
        result = google_translate_service.detect_language(combined_text)
        
        if result['error']:
            return {'error': result['error']}
        
        # Mettre à jour le fichier
        file.detected_language = result['language']
        file.detected_language_confidence = result['confidence']
        file.save()
        
        return {
            'detected_language': result['language'],
            'confidence': result['confidence']
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la détection de langue: {str(e)}")
        return {'error': str(e)} 