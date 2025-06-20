# =============================================================================
# files/tasks.py (Tâches Celery)
# ============================================================================

"""
Objets Celery pour le traitement asynchrone des fichiers de traduction.
Supporte uniquement les formats .po et .json avec détection automatique de framework.
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
import json
import re
from .models import TranslationFile, TranslationString
from django.db import transaction
from django.utils import timezone

logger = get_task_logger(__name__)


def detect_framework_from_content(file_path, file_type, encoding='utf-8'):
    """
    Détecte automatiquement le framework utilisé basé sur le contenu du fichier
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read(5000)  # Lire les premiers 5KB pour l'analyse
            
        if file_type == 'po':
            return detect_framework_from_po(content)
        elif file_type == 'json':
            return detect_framework_from_json(content)
        else:
            return 'unknown'
            
    except Exception as e:
        logger.warning(f"Erreur lors de la détection de framework: {e}")
        return 'unknown'


def detect_framework_from_po(content):
    """
    Détecte le framework basé sur le contenu d'un fichier PO
    """
    # Patterns pour détecter différents frameworks
    patterns = {
        'django': [
            r'#: .*\.py',
            r'msgid "django"',
            r'msgstr "Django"',
            r'#: .*django.*',
            r'Project-Id-Version: Django',
            r'#: .*admin\.py',
            r'#: .*models\.py',
            r'#: .*views\.py',
            r'#: .*forms\.py',
            r'#: .*urls\.py',
            r'#: .*settings\.py',
            r'#: .*templates/',
            r'#: .*static/',
            r'msgid "Welcome to Django"',
            r'msgid "User"',
            r'msgid "Home"',
            r'msgid "Submit"',
            r'msgid "Logout"',
            r'msgid "Login"',
            r'msgid "Register"',
            r'msgid "Password"',
            r'msgid "Email"',
            r'msgid "Username"',
        ],
        'flask': [
            r'#: .*\.py',
            r'msgid "flask"',
            r'msgstr "Flask"',
            r'from flask_babel',
            r'Project-Id-Version: Flask',
            r'#: .*app\.py',
            r'#: .*routes\.py',
            r'#: .*__init__\.py',
        ],
        'vue': [
            r'msgid "vue"',
            r'msgstr "Vue"',
            r'#: .*\.vue',
            r'#: .*vue.*',
            r'Project-Id-Version: Vue',
            r'#: .*components/',
            r'#: .*pages/',
            r'#: .*store/',
        ],
        'react': [
            r'msgid "react"',
            r'msgstr "React"',
            r'#: .*\.jsx',
            r'#: .*\.tsx',
            r'#: .*react.*',
            r'Project-Id-Version: React',
            r'#: .*components/',
            r'#: .*pages/',
            r'#: .*src/',
        ],
        'angular': [
            r'msgid "angular"',
            r'msgstr "Angular"',
            r'#: .*\.ts',
            r'#: .*angular.*',
            r'Project-Id-Version: Angular',
            r'#: .*components/',
            r'#: .*services/',
            r'#: .*modules/',
        ],
        'laravel': [
            r'msgid "laravel"',
            r'msgstr "Laravel"',
            r'#: .*\.php',
            r'#: .*laravel.*',
            r'Project-Id-Version: Laravel',
            r'#: .*resources/',
            r'#: .*app/',
            r'#: .*routes/',
        ],
        'symfony': [
            r'msgid "symfony"',
            r'msgstr "Symfony"',
            r'#: .*symfony.*',
            r'Project-Id-Version: Symfony',
            r'#: .*src/',
            r'#: .*templates/',
            r'#: .*translations/',
        ],
        'wordpress': [
            r'msgid "wordpress"',
            r'msgstr "WordPress"',
            r'#: .*wordpress.*',
            r'#: .*wp-.*',
            r'Project-Id-Version: WordPress',
            r'#: .*wp-content/',
            r'#: .*wp-includes/',
            r'msgid "WordPress"',
        ],
        'joomla': [
            r'msgid "joomla"',
            r'msgstr "Joomla"',
            r'#: .*joomla.*',
            r'Project-Id-Version: Joomla',
            r'#: .*components/',
            r'#: .*modules/',
            r'#: .*plugins/',
        ],
        'drupal': [
            r'msgid "drupal"',
            r'msgstr "Drupal"',
            r'#: .*drupal.*',
            r'Project-Id-Version: Drupal',
            r'#: .*modules/',
            r'#: .*themes/',
            r'#: .*sites/',
        ],
    }
    
    # Compter les correspondances pour chaque framework
    framework_scores = {}
    
    for framework, pattern_list in patterns.items():
        score = 0
        for pattern in pattern_list:
            if re.search(pattern, content, re.IGNORECASE):
                score += 1
        if score > 0:
            framework_scores[framework] = score
    
    # Debug: afficher les scores pour le diagnostic
    if framework_scores:
        print(f"DEBUG - Scores des frameworks: {framework_scores}")
    
    # Retourner le framework avec le score le plus élevé
    if framework_scores:
        detected_framework = max(framework_scores, key=framework_scores.get)
        if framework_scores[detected_framework] >= 1:
            return detected_framework
    
    # Si aucun pattern spécifique n'est trouvé, essayer de détecter par contexte
    if re.search(r'#: .*\.py', content):
        # Si on a des références Python, c'est probablement Django ou Flask
        if re.search(r'Project-Id-Version: Django', content, re.IGNORECASE):
            return 'django'
        elif re.search(r'Project-Id-Version: Flask', content, re.IGNORECASE):
            return 'flask'
        else:
            # Par défaut, si on a des .py, c'est probablement Django
            return 'django'
    elif re.search(r'#: .*\.php', content):
        return 'php'
    elif re.search(r'#: .*\.js', content):
        return 'javascript'
    elif re.search(r'#: .*\.vue', content):
        return 'vue'
    elif re.search(r'#: .*\.ts', content):
        return 'typescript'
    
    return 'generic'


def detect_framework_from_json(content):
    """
    Détecte le framework basé sur le contenu d'un fichier JSON
    """
    try:
        # Essayer de parser le JSON
        data = json.loads(content)
        
        # Patterns pour détecter différents frameworks
        patterns = {
            'react': [
                r'react',
                r'jsx',
                r'tsx',
                r'create-react-app',
            ],
            'vue': [
                r'vue',
                r'vue-i18n',
                r'vuex',
            ],
            'angular': [
                r'angular',
                r'@angular',
                r'ngx-translate',
            ],
            'flutter': [
                r'flutter',
                r'flutter_localizations',
                r'@flutter',
            ],
            'react-native': [
                r'react-native',
                r'react_native',
                r'@react-native',
            ],
            'nextjs': [
                r'next',
                r'nextjs',
                r'@next',
            ],
            'nuxt': [
                r'nuxt',
                r'@nuxt',
            ],
            'svelte': [
                r'svelte',
                r'@svelte',
            ],
            'ember': [
                r'ember',
                r'@ember',
            ],
        }
        
        # Convertir le contenu en string pour la recherche
        content_str = json.dumps(data, ensure_ascii=False)
        
        # Compter les correspondances pour chaque framework
        framework_scores = {}
        
        for framework, pattern_list in patterns.items():
            score = 0
            for pattern in pattern_list:
                if re.search(pattern, content_str, re.IGNORECASE):
                    score += 1
            if score > 0:
                framework_scores[framework] = score
        
        # Retourner le framework avec le score le plus élevé
        if framework_scores:
            detected_framework = max(framework_scores, key=framework_scores.get)
            if framework_scores[detected_framework] >= 1:
                return detected_framework
        
        # Détection par structure de données
        if isinstance(data, dict):
            # Vérifier les clés communes
            if 'locale' in data or 'language' in data:
                return 'i18n'
            elif 'messages' in data or 'translations' in data:
                return 'translation'
            elif 'app' in data or 'application' in data:
                return 'application'
        
        return 'generic'
        
    except json.JSONDecodeError:
        # Si ce n'est pas du JSON valide, essayer de détecter par contenu brut
        if re.search(r'react', content, re.IGNORECASE):
            return 'react'
        elif re.search(r'vue', content, re.IGNORECASE):
            return 'vue'
        elif re.search(r'angular', content, re.IGNORECASE):
            return 'angular'
        elif re.search(r'flutter', content, re.IGNORECASE):
            return 'flutter'
        
        return 'unknown'


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
            
            # Détection automatique du framework
            detected_framework = detect_framework_from_content(file_path, file_type, encoding)
            translation_file.detected_framework = detected_framework
            translation_file.save()
            
            logger.info(f"Framework détecté: {detected_framework} pour le fichier {file_id}")
            
            if file_type == 'po':
                result = process_po_file(translation_file, file_path, encoding, self)
            elif file_type == 'json':
                result = process_json_file(translation_file, file_path, encoding, self)
            else:
                logger.error(f"Type de fichier non supporté: {file_type}")
                translation_file.status = 'error'
                translation_file.error_message = f'Type de fichier non supporté: {file_type}. Seuls les formats .po et .json sont autorisés.'
                translation_file.save()
                return {'status': 'error', 'message': f'Type de fichier non supporté: {file_type}. Seuls les formats .po et .json sont autorisés.'}
            
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
                    context=entry.msgstr or '',
                    line_number=entry.linenum,
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
        translated_strings = TranslationString.objects.filter(translations__isnull=False).distinct().count()
        
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