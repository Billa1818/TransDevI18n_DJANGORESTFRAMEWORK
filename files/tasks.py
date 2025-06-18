# =============================================================================
# files/tasks.py (Tâches Celery)
# ============================================================================

"""
Ojbets Celery pour le traitement asynchrone des fichiers de traduction.

"""

from celery import shared_task
from celery.utils.log import get_task_logger
from celery.exceptions import Retry, WorkerLostError
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
import os
import chardet
import time
from .models import TranslationFile
from django.db import transaction
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_translation_file(self, file_id):
    """Traite un fichier de traduction de manière asynchrone"""
    
    translation_file = None
    
    try:
        from .models import TranslationFile, TranslationString
        
        # Récupérer le fichier avec gestion d'erreurs
        try:
            translation_file = TranslationFile.objects.get(id=file_id)
        except TranslationFile.DoesNotExist:
            logger.error(f"Fichier {file_id} introuvable")
            return {'status': 'error', 'message': 'Fichier introuvable'}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du fichier {file_id}: {e}")
            return {'status': 'error', 'message': f'Erreur de base de données: {str(e)}'}
        
        # Vérifier que le fichier n'est pas déjà en cours de traitement par une autre tâche
        if translation_file.status == 'processing' and translation_file.task_id != self.request.id:
            logger.warning(f"Fichier {file_id} déjà en cours de traitement par une autre tâche")
            return {'status': 'error', 'message': 'Fichier déjà en cours de traitement'}
        
        # Marquer comme en cours de traitement
        try:
            with transaction.atomic():
                translation_file.status = 'processing'
                translation_file.task_id = self.request.id
                translation_file.error_message = ''
                translation_file.save()
        except IntegrityError as e:
            logger.error(f"Erreur d'intégrité lors de la mise à jour du statut: {e}")
            return {'status': 'error', 'message': 'Erreur de mise à jour du statut'}
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")
            return {'status': 'error', 'message': f'Erreur de base de données: {str(e)}'}
        
        # Vérifier l'existence du fichier
        if not translation_file.file_path:
            logger.error(f"Chemin de fichier manquant pour {file_id}")
            translation_file.status = 'error'
            translation_file.error_message = 'Chemin de fichier manquant'
            translation_file.save()
            return {'status': 'error', 'message': 'Chemin de fichier manquant'}
        
        try:
            file_path = translation_file.file_path.path
        except (ValueError, AttributeError) as e:
            logger.error(f"Chemin de fichier invalide pour {file_id}: {e}")
            translation_file.status = 'error'
            translation_file.error_message = 'Chemin de fichier invalide'
            translation_file.save()
            return {'status': 'error', 'message': 'Chemin de fichier invalide'}
        
        # Vérifier que le fichier existe physiquement
        if not os.path.exists(file_path):
            logger.error(f"Fichier physique introuvable: {file_path}")
            translation_file.status = 'error'
            translation_file.error_message = 'Fichier physique introuvable'
            translation_file.save()
            return {'status': 'error', 'message': 'Fichier physique introuvable'}
        
        # Vérifier la taille du fichier
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(f"Fichier vide: {file_path}")
                translation_file.status = 'error'
                translation_file.error_message = 'Fichier vide'
                translation_file.save()
                return {'status': 'error', 'message': 'Fichier vide'}
            
            # Limite de taille (ex: 100MB)
            MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
            if file_size > MAX_FILE_SIZE:
                logger.error(f"Fichier trop volumineux: {file_size} bytes")
                translation_file.status = 'error'
                translation_file.error_message = 'Fichier trop volumineux'
                translation_file.save()
                return {'status': 'error', 'message': 'Fichier trop volumineux'}
                
        except OSError as e:
            logger.error(f"Erreur lors de la vérification de la taille du fichier: {e}")
            translation_file.status = 'error'
            translation_file.error_message = 'Erreur lors de la vérification du fichier'
            translation_file.save()
            return {'status': 'error', 'message': 'Erreur lors de la vérification du fichier'}
        
        # Détection de l'encodage du fichier
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Lire les premiers 10KB pour détecter l'encodage
                encoding_result = chardet.detect(raw_data)
                encoding = encoding_result.get('encoding', 'utf-8')
                confidence = encoding_result.get('confidence', 0)
                
                # Si la confiance est trop faible, utiliser utf-8 par défaut
                if confidence < 0.7:
                    encoding = 'utf-8'
                    logger.warning(f"Encodage détecté avec faible confiance, utilisation d'UTF-8 par défaut")
                
                logger.info(f"Encodage détecté: {encoding} (confiance: {confidence})")
                
        except Exception as e:
            logger.warning(f"Erreur lors de la détection d'encodage, utilisation d'UTF-8: {e}")
            encoding = 'utf-8'
        
        # Lecture et analyse du fichier selon son type
        try:
            file_type = translation_file.file_type.lower()
            
            if file_type == 'po':
                result = process_po_file(translation_file, file_path, encoding, self)
            elif file_type == 'json':
                result = process_json_file(translation_file, file_path, encoding, self)
            elif file_type == 'xml':
                result = process_xml_file(translation_file, file_path, encoding, self)
            elif file_type == 'csv':
                result = process_csv_file(translation_file, file_path, encoding, self)
            elif file_type in ['php', 'properties']:
                result = process_php_file(translation_file, file_path, encoding, self)
            elif file_type in ['yaml', 'yml']:
                result = process_yaml_file(translation_file, file_path, encoding, self)
            elif file_type == 'arb':
                result = process_arb_file(translation_file, file_path, encoding, self)
            elif file_type == 'ts':
                result = process_ts_file(translation_file, file_path, encoding, self)
            else:
                logger.error(f"Type de fichier non supporté: {file_type}")
                translation_file.status = 'error'
                translation_file.error_message = f'Type de fichier non supporté: {file_type}'
                translation_file.save()
                return {'status': 'error', 'message': f'Type de fichier non supporté: {file_type}'}
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du fichier {file_id}: {e}")
            if translation_file:
                translation_file.status = 'error'
                translation_file.error_message = f'Erreur de traitement: {str(e)}'
                translation_file.save()
            return {'status': 'error', 'message': f'Erreur de traitement: {str(e)}'}
    
    except Exception as e:
        logger.error(f"Erreur critique lors du traitement du fichier {file_id}: {e}")
        if translation_file:
            try:
                translation_file.status = 'error'
                translation_file.error_message = f'Erreur critique: {str(e)}'
                translation_file.save()
            except Exception as save_error:
                logger.error(f"Impossible de sauvegarder l'erreur: {save_error}")
        
        # Relancer l'exception pour que Celery puisse gérer les tentatives
        if self.request.retries < self.max_retries:
            logger.info(f"Tentative {self.request.retries + 1}/{self.max_retries + 1} pour le fichier {file_id}")
            raise self.retry(countdown=60)
        
        return {'status': 'error', 'message': f'Erreur critique après {self.max_retries + 1} tentatives'}


def process_po_file(translation_file, file_path, encoding, task):
    """Traite un fichier PO (gettext)"""
    from .models import TranslationString
    import polib
    
    try:
        # Charger le fichier PO
        po = polib.pofile(file_path, encoding=encoding)
        
        total_entries = len(po)
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Fichier PO vide ou invalide'
            translation_file.save()
            return {'status': 'error', 'message': 'Fichier PO vide ou invalide'}
        
        logger.info(f"Traitement de {total_entries} entrées PO")
        created_strings = 0
        
        # Traitement par lots pour optimiser les performances
        batch_size = 100
        strings_to_create = []
        
        for i, entry in enumerate(po):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                # Créer l'objet TranslationString avec les bons noms de champs
                translation_string = TranslationString(
                    file=translation_file,
                    key=entry.msgid[:500] if entry.msgid else '',  # Limiter la taille
                    source_text=entry.msgid,
                    # CORRECTION: Utiliser un champ existant pour le texte traduit
                    # Option 1: Si vous voulez stocker msgstr dans context
                    context=entry.msgstr or '',
                    # Option 2: Ou créer un champ dédié dans votre modèle
                    line_number=entry.linenum,
                    is_translated=bool(entry.msgstr and not entry.fuzzy),
                    is_fuzzy=entry.fuzzy,
                    is_plural=bool(entry.msgid_plural),
                    comment='\n'.join(entry.comment.split('\n')[:5]) if entry.comment else ''
                )
                
                strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de l'entrée {i}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement PO terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except ImportError:
        error_msg = 'Bibliothèque polib non disponible'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier PO: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    

def process_json_file(translation_file, file_path, encoding, task):
    """Traite un fichier JSON de traduction"""
    from .models import TranslationString
    import json
    
    try:
        # Charger le fichier JSON
        with open(file_path, 'r', encoding=encoding) as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            translation_file.status = 'error'
            translation_file.error_message = 'Format JSON invalide: doit être un objet'
            translation_file.save()
            return {'status': 'error', 'message': 'Format JSON invalide'}
        
        # Aplatir la structure JSON si nécessaire
        flat_data = flatten_json(data)
        total_entries = len(flat_data)
        
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Fichier JSON vide'
            translation_file.save()
            return {'status': 'error', 'message': 'Fichier JSON vide'}
        
        logger.info(f"Traitement de {total_entries} entrées JSON")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(flat_data.items()):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                # Traiter seulement les valeurs string
                if isinstance(value, str):
                    translation_string = TranslationString(
                        file=translation_file,
                        key=key[:500],
                        source_text=value,
                        context='',  # Vide par défaut pour JSON
                        line_number=i + 1,
                        is_translated=False,
                        is_fuzzy=False,
                        is_plural=False
                    )
                    
                    strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de la clé {key}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement JSON terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',  
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except json.JSONDecodeError as e:
        error_msg = f'Erreur de format JSON: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier JSON: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}


def process_xml_file(translation_file, file_path, encoding, task):
    """Traite un fichier XML de traduction (format Android strings.xml)"""
    from .models import TranslationString
    import xml.etree.ElementTree as ET
    
    try:
        # Parser le fichier XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Chercher les éléments string
        string_elements = root.findall('.//string')
        total_entries = len(string_elements)
        
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Aucun élément <string> trouvé dans le fichier XML'
            translation_file.save()
            return {'status': 'error', 'message': 'Aucun élément string trouvé'}
        
        logger.info(f"Traitement de {total_entries} éléments XML string")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, element in enumerate(string_elements):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                key = element.get('name', f'string_{i}')
                value = element.text or ''
                
                translation_string = TranslationString(
                    file=translation_file,
                    key=key[:500],
                    source_text=value,
                    context='',
                    line_number=i + 1,
                    is_translated=False,
                    is_fuzzy=False,
                    is_plural=False
                )
                
                strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de l'élément {i}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement XML terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except ET.ParseError as e:
        error_msg = f'Erreur de format XML: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier XML: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}


def process_csv_file(translation_file, file_path, encoding, task):
    """Traite un fichier CSV de traduction"""
    from .models import TranslationString
    import csv
    
    try:
        # Ouvrir et lire le fichier CSV
        with open(file_path, 'r', encoding=encoding) as f:
            # Détecter le délimiteur
            sample = f.read(1024)
            f.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Vérifier les colonnes requises
            required_columns = ['key', 'source_text']
            if not all(col in reader.fieldnames for col in required_columns):
                translation_file.status = 'error'
                translation_file.error_message = f'Colonnes requises manquantes: {required_columns}'
                translation_file.save()
                return {'status': 'error', 'message': 'Colonnes requises manquantes'}
            
            # Compter le nombre total de lignes
            rows = list(reader)
            total_entries = len(rows)
            
            if total_entries == 0:
                translation_file.status = 'error'
                translation_file.error_message = 'Fichier CSV vide'
                translation_file.save()
                return {'status': 'error', 'message': 'Fichier CSV vide'}
            
            logger.info(f"Traitement de {total_entries} lignes CSV")
            created_strings = 0
            
            batch_size = 100
            strings_to_create = []
            
            for i, row in enumerate(rows):
                try:
                    # Mise à jour du progrès
                    if i % 10 == 0:
                        progress = int((i / total_entries) * 100)
                        task.update_state(
                            state='PROGRESS',
                            meta={
                                'current': i,
                                'total': total_entries,
                                'strings_created': created_strings,
                                'progress': progress
                            }
                        )
                    
                    key = row.get('key', '').strip()
                    source_text = row.get('source_text', '').strip()
                    
                    if not key or not source_text:
                        continue  # Ignorer les lignes vides
                    
                    # Utiliser context pour stocker le texte traduit s'il existe
                    translated_text = row.get('translated_text', '').strip()
                    context_value = row.get('context', '').strip()
                    
                    # Si on a du texte traduit, on l'utilise comme context, sinon on garde le context original
                    final_context = translated_text if translated_text else context_value
                    
                    translation_string = TranslationString(
                        file=translation_file,
                        key=key[:500],
                        source_text=source_text,
                        context=final_context,
                        line_number=i + 2,  # +2 car ligne 1 = headers
                        is_translated=bool(translated_text),
                        is_fuzzy=row.get('is_fuzzy', '').lower() == 'true',
                        is_plural=row.get('is_plural', '').lower() == 'true'
                    )
                    
                    strings_to_create.append(translation_string)
                    
                    # Créer par lots
                    if len(strings_to_create) >= batch_size:
                        created_count = bulk_create_strings(strings_to_create, translation_file)
                        created_strings += created_count
                        strings_to_create = []
                    
                except Exception as e:
                    logger.warning(f"Erreur lors du traitement de la ligne {i}: {e}")
                    continue
            
            # Créer les dernières chaînes restantes
            if strings_to_create:
                created_count = bulk_create_strings(strings_to_create, translation_file)
                created_strings += created_count
            
            # Finaliser le traitement
            with transaction.atomic():
                translation_file.status = 'completed'
                translation_file.total_strings = created_strings
                translation_file.error_message = ''
                translation_file.save()
            
            logger.info(f"Traitement CSV terminé: {created_strings} chaînes créées")
            return {
                'status': 'success',
                'message': f'{created_strings} chaînes de traduction créées',
                'total_strings': created_strings
            }
            
    except UnicodeDecodeError as e:
        error_msg = f'Erreur d\'encodage CSV: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier CSV: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}


def process_php_file(translation_file, file_path, encoding, task):
    """Traite un fichier PHP de traduction (format Laravel/array PHP)"""
    from .models import TranslationString
    import re
    
    try:
        # Lire le fichier PHP
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        # Pattern pour extraire les clés/valeurs des arrays PHP
        # Supporte: 'key' => 'value', "key" => "value", 'key' => "value", etc.
        pattern = r"['\"]([^'\"]+)['\"][\s]*=>[\s]*['\"]([^'\"]*)['\"]"
        matches = re.findall(pattern, content)
        
        total_entries = len(matches)
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Aucune traduction trouvée dans le fichier PHP'
            translation_file.save()
            return {'status': 'error', 'message': 'Aucune traduction trouvée'}
        
        logger.info(f"Traitement de {total_entries} entrées PHP")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(matches):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                translation_string = TranslationString(
                    file=translation_file,
                    key=key[:500],
                    source_text=value,
                    context='',
                    line_number=i + 1,
                    is_translated=False,
                    is_fuzzy=False,
                    is_plural=False
                )
                
                strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de l'entrée PHP {i}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement PHP terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier PHP: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}



def process_yaml_file(translation_file, file_path, encoding, task):
    """Traite un fichier YAML/YML de traduction"""
    from .models import TranslationString
    
    try:
        import yaml
        
        # Charger le fichier YAML
        with open(file_path, 'r', encoding=encoding) as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            translation_file.status = 'error'
            translation_file.error_message = 'Format YAML invalide: doit être un objet'
            translation_file.save()
            return {'status': 'error', 'message': 'Format YAML invalide'}
        
        # Aplatir la structure YAML
        flat_data = flatten_json(data)
        total_entries = len(flat_data)
        
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Fichier YAML vide'
            translation_file.save()
            return {'status': 'error', 'message': 'Fichier YAML vide'}
        
        logger.info(f"Traitement de {total_entries} entrées YAML")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(flat_data.items()):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                # Traiter seulement les valeurs string
                if isinstance(value, str):
                    translation_string = TranslationString(
                        file=translation_file,
                        key=key[:500],
                        source_text=value,
                        context='',
                        line_number=i + 1,
                        is_translated=False,
                        is_fuzzy=False,
                        is_plural=False
                    )
                    
                    strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de la clé YAML {key}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement YAML terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except ImportError:
        error_msg = 'Bibliothèque PyYAML non disponible'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except yaml.YAMLError as e:
        error_msg = f'Erreur de format YAML: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier YAML: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    

def process_arb_file(translation_file, file_path, encoding, task):
    """Traite un fichier ARB (Application Resource Bundle) Flutter"""
    from .models import TranslationString
    import json
    
    try:
        # Charger le fichier ARB (c'est du JSON avec une structure spécifique)
        with open(file_path, 'r', encoding=encoding) as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            translation_file.status = 'error'
            translation_file.error_message = 'Format ARB invalide: doit être un objet'
            translation_file.save()
            return {'status': 'error', 'message': 'Format ARB invalide'}
        
        # Filtrer les clés de métadonnées ARB (qui commencent par @)
        translation_entries = {k: v for k, v in data.items() 
                             if not k.startswith('@') and isinstance(v, str)}
        
        total_entries = len(translation_entries)
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Aucune traduction trouvée dans le fichier ARB'
            translation_file.save()
            return {'status': 'error', 'message': 'Aucune traduction trouvée'}
        
        logger.info(f"Traitement de {total_entries} entrées ARB")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(translation_entries.items()):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                # Récupérer les métadonnées pour cette clé si elles existent
                metadata_key = f"@{key}"
                metadata = data.get(metadata_key, {})
                context = metadata.get('description', '') if isinstance(metadata, dict) else ''
                
                translation_string = TranslationString(
                    file=translation_file,
                    key=key[:500],
                    source_text=value,
                    context=context,
                    line_number=i + 1,
                    is_translated=False,
                    is_fuzzy=False,
                    is_plural=False
                )
                
                strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de l'entrée ARB {key}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement ARB terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except json.JSONDecodeError as e:
        error_msg = f'Erreur de format ARB/JSON: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier ARB: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}



def process_properties_file(translation_file, file_path, encoding, task):
    """Traite un fichier Properties (Java/Android)"""
    from .models import TranslationString
    
    try:
        # Lire le fichier properties
        with open(file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
        
        translation_entries = {}
        line_numbers = {}
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Ignorer les lignes vides et les commentaires
            if not line or line.startswith('#') or line.startswith('!'):
                continue
            
            # Chercher le pattern key=value ou key:value
            if '=' in line:
                key, value = line.split('=', 1)
            elif ':' in line:
                key, value = line.split(':', 1)
            else:
                continue
            
            key = key.strip()
            value = value.strip()
            
            if key and value:
                translation_entries[key] = value
                line_numbers[key] = line_num
        
        total_entries = len(translation_entries)
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Aucune propriété trouvée dans le fichier'
            translation_file.save()
            return {'status': 'error', 'message': 'Aucune propriété trouvée'}
        
        logger.info(f"Traitement de {total_entries} propriétés")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(translation_entries.items()):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                translation_string = TranslationString(
                    file=translation_file,
                    key=key[:500],
                    source_text=value,
                    context='',
                    line_number=line_numbers.get(key, i + 1),
                    is_translated=False,
                    is_fuzzy=False,
                    is_plural=False
                )
                
                strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de la propriété {key}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement Properties terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier Properties: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}
    


def process_ts_file(translation_file, file_path, encoding, task):
    """Traite un fichier TypeScript de traduction (format i18next ou similaire)"""
    from .models import TranslationString
    import re
    import json
    
    try:
        # Lire le fichier TypeScript
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        # Extraire l'objet de traduction du fichier TS
        # Pattern pour capturer export default { ... } ou export const translations = { ... }
        patterns = [
            r'export\s+default\s+({.*?});',
            r'export\s+const\s+\w+\s*=\s*({.*?});',
            r'const\s+\w+\s*=\s*({.*?});'
        ]
        
        translation_object = None
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                try:
                    # Essayer de parser comme JSON (approximatif pour TS)
                    json_str = matches[0]
                    # Remplacer les clés non quotées par des clés quotées
                    json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                    # Remplacer les apostrophes par des guillemets
                    json_str = json_str.replace("'", '"')
                    
                    translation_object = json.loads(json_str)
                    break
                except json.JSONDecodeError:
                    continue
        
        if not translation_object:
            translation_file.status = 'error'
            translation_file.error_message = 'Impossible d\'extraire l\'objet de traduction du fichier TS'
            translation_file.save()
            return {'status': 'error', 'message': 'Objet de traduction non trouvé'}
        
        # Aplatir la structure
        flat_data = flatten_json(translation_object)
        total_entries = len(flat_data)
        
        if total_entries == 0:
            translation_file.status = 'error'
            translation_file.error_message = 'Aucune traduction trouvée dans le fichier TS'
            translation_file.save()
            return {'status': 'error', 'message': 'Aucune traduction trouvée'}
        
        logger.info(f"Traitement de {total_entries} entrées TypeScript")
        created_strings = 0
        
        batch_size = 100
        strings_to_create = []
        
        for i, (key, value) in enumerate(flat_data.items()):
            try:
                # Mise à jour du progrès
                if i % 10 == 0:
                    progress = int((i / total_entries) * 100)
                    task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': total_entries,
                            'strings_created': created_strings,
                            'progress': progress
                        }
                    )
                
                # Traiter seulement les valeurs string
                if isinstance(value, str):
                    translation_string = TranslationString(
                        file=translation_file,
                        key=key[:500],
                        source_text=value,
                        context='',  # Champ context vide car pas de traduction dans les fichiers TS source
                        line_number=i + 1,
                        is_translated=False,
                        is_fuzzy=False,
                        is_plural=False
                    )
                    
                    strings_to_create.append(translation_string)
                
                # Créer par lots
                if len(strings_to_create) >= batch_size:
                    created_count = bulk_create_strings(strings_to_create, translation_file)
                    created_strings += created_count
                    strings_to_create = []
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de la clé TS {key}: {e}")
                continue
        
        # Créer les dernières chaînes restantes
        if strings_to_create:
            created_count = bulk_create_strings(strings_to_create, translation_file)
            created_strings += created_count
        
        # Finaliser le traitement
        with transaction.atomic():
            translation_file.status = 'completed'
            translation_file.total_strings = created_strings
            translation_file.error_message = ''
            translation_file.save()
        
        logger.info(f"Traitement TypeScript terminé: {created_strings} chaînes créées")
        return {
            'status': 'success',
            'message': f'{created_strings} chaînes de traduction créées',
            'total_strings': created_strings
        }
        
    except Exception as e:
        error_msg = f'Erreur lors du traitement du fichier TypeScript: {str(e)}'
        logger.error(error_msg)
        translation_file.status = 'error'
        translation_file.error_message = error_msg
        translation_file.save()
        return {'status': 'error', 'message': error_msg}




def bulk_create_strings(strings_to_create, translation_file):
    """Crée les chaînes de traduction par lots avec gestion d'erreurs"""
    from .models import TranslationString
    
    try:
        with transaction.atomic():
            created_objects = TranslationString.objects.bulk_create(
                strings_to_create,
                ignore_conflicts=True,  # Ignorer les doublons
                batch_size=100
            )
            return len(created_objects)
    
    except IntegrityError as e:
        logger.error(f"Erreur d'intégrité lors de la création en lot: {e}")
        # Tenter de créer un par un en cas d'erreur
        created_count = 0
        for string_obj in strings_to_create:
            try:
                string_obj.save()
                created_count += 1
            except Exception as individual_error:
                logger.warning(f"Impossible de créer la chaîne {string_obj.key}: {individual_error}")
                continue
        return created_count
    
    except Exception as e:
        logger.error(f"Erreur lors de la création en lot: {e}")
        return 0


def flatten_json(data, parent_key='', separator='.'):
    """Aplatit une structure JSON imbriquée"""
    items = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            
            if isinstance(value, dict):
                items.extend(flatten_json(value, new_key, separator).items())
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, (dict, list)):
                        items.extend(flatten_json(item, f"{new_key}[{i}]", separator).items())
                    else:
                        items.append((f"{new_key}[{i}]", str(item)))
            else:
                items.append((new_key, value))
    
    return dict(items)


@shared_task(bind=True)
def cleanup_old_files(self):
    """Tâche de nettoyage des anciens fichiers"""
    from .models import TranslationFile
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Supprimer les fichiers de plus de 30 jours
        cutoff_date = timezone.now() - timedelta(days=30)
        old_files = TranslationFile.objects.filter(uploaded_at__lt=cutoff_date)
        
        deleted_count = 0
        for file_obj in old_files:
            try:
                # Supprimer le fichier physique
                if file_obj.file_path:
                    file_obj.file_path.delete(save=False)
                
                # Supprimer l'enregistrement
                file_obj.delete()
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du fichier {file_obj.id}: {e}")
                continue
        
        logger.info(f"Nettoyage terminé: {deleted_count} fichiers supprimés")
        return {'status': 'success', 'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {e}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def generate_translation_stats(self):
    """Génère des statistiques globales de traduction"""
    from .models import TranslationFile, TranslationString
    from django.db.models import Count, Q
    
    try:
        # Statistiques des fichiers
        total_files = TranslationFile.objects.count()
        completed_files = TranslationFile.objects.filter(status='completed').count()
        
        # Statistiques des chaînes
        total_strings = TranslationString.objects.count()
        translated_strings = TranslationString.objects.filter(is_translated=True).count()
        
        # Calcul du pourcentage
        translation_percentage = 0
        if total_strings > 0:
            translation_percentage = (translated_strings / total_strings) * 100
        
        stats = {
            'total_files': total_files,
            'completed_files': completed_files,
            'total_strings': total_strings,
            'translated_strings': translated_strings,
            'translation_percentage': round(translation_percentage, 2),
            'generated_at': timezone.now().isoformat()
        }
        
        logger.info(f"Statistiques générées: {stats}")
        return {'status': 'success', 'stats': stats}
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération des statistiques: {e}")
        return {'status': 'error', 'message': str(e)}