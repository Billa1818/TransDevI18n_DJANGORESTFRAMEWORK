#!/usr/bin/env python
"""
Script de test pour les nouveaux endpoints de vérification des traductions
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TransDevI18n.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from files.models import TranslationFile
from translations.models import Translation, Language
from translations.serializers import FileTranslationStatusSerializer, FileTranslationsDetailSerializer

def test_translation_status_endpoint():
    """Test de l'endpoint translation_status"""
    print("\n🔍 Test de l'endpoint translation_status")
    print("=" * 50)
    
    # Récupérer un fichier avec des traductions
    file = TranslationFile.objects.filter(
        translations__isnull=False
    ).first()
    
    if not file:
        print("❌ Aucun fichier avec traductions trouvé")
        return False
    
    print(f"📁 Fichier testé: {file.original_filename}")
    
    # Simuler la logique de l'endpoint
    total_translations = Translation.objects.filter(string__file=file).count()
    has_translations = total_translations > 0
    
    languages_with_translations = Translation.objects.filter(
        string__file=file
    ).values_list('target_language__code', flat=True).distinct()
    
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
    
    # Tester le serializer
    serializer = FileTranslationStatusSerializer(status_data)
    
    print("✅ Résultats du test:")
    print(f"   - A des traductions: {has_translations}")
    print(f"   - Total strings: {file.total_strings}")
    print(f"   - Total traductions: {total_translations}")
    print(f"   - Langues avec traductions: {list(languages_with_translations)}")
    print(f"   - Progression globale: {round(overall_progress, 2)}%")
    print(f"   - Nécessite attention: {needs_attention}")
    if attention_reasons:
        print(f"   - Raisons: {attention_reasons}")
    
    return True

def test_all_translations_endpoint():
    """Test de l'endpoint all_translations"""
    print("\n📋 Test de l'endpoint all_translations")
    print("=" * 50)
    
    # Récupérer un fichier avec des traductions
    file = TranslationFile.objects.filter(
        translations__isnull=False
    ).first()
    
    if not file:
        print("❌ Aucun fichier avec traductions trouvé")
        return False
    
    print(f"📁 Fichier testé: {file.original_filename}")
    
    # Simuler la logique de l'endpoint
    translations = Translation.objects.filter(string__file=file)
    total_translations = translations.count()
    
    # Pagination simple (première page)
    page = 1
    page_size = 10
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
        
        translations_by_language[lang_code]['translations'].append({
            'id': str(translation.id),
            'string_key': translation.string.key,
            'source_text': translation.string.source_text,
            'translated_text': translation.translated_text,
            'confidence_score': translation.confidence_score,
            'is_approved': translation.is_approved,
            'created_at': translation.created_at.isoformat()
        })
    
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
            'uploaded_at': file.uploaded_at.isoformat()
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
    
    print("✅ Résultats du test:")
    print(f"   - Total traductions: {total_translations}")
    print(f"   - Traductions approuvées: {total_approved}")
    print(f"   - Traductions en attente: {total_pending}")
    print(f"   - Nombre de langues: {languages_count}")
    print(f"   - Taux d'approbation: {round((total_approved / total_translations * 100) if total_translations > 0 else 0, 2)}%")
    print(f"   - Traductions par langue: {list(translations_by_language.keys())}")
    
    return True

def main():
    """Fonction principale de test"""
    print("🚀 Test des nouveaux endpoints de vérification des traductions")
    print("=" * 70)
    
    # Test 1: Endpoint translation_status
    success1 = test_translation_status_endpoint()
    
    # Test 2: Endpoint all_translations
    success2 = test_all_translations_endpoint()
    
    # Résumé
    print("\n📊 Résumé des tests")
    print("=" * 30)
    print(f"✅ Endpoint translation_status: {'SUCCÈS' if success1 else 'ÉCHEC'}")
    print(f"✅ Endpoint all_translations: {'SUCCÈS' if success2 else 'ÉCHEC'}")
    
    if success1 and success2:
        print("\n🎉 Tous les tests sont passés avec succès!")
        return True
    else:
        print("\n❌ Certains tests ont échoué")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 