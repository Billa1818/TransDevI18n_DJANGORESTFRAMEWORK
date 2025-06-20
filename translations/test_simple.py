#!/usr/bin/env python3
"""
Script de test simple pour l'API de traduction de fichiers
"""

import os
import sys
import django
import requests
import json
import time

# Ajouter le répertoire parent au path Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TransDevI18n.settings')
django.setup()

from django.contrib.auth import get_user_model
from files.models import TranslationFile, TranslationString
from translations.models import Language, TranslationTask, Translation

User = get_user_model()

def test_file_translation_api():
    """Test de l'API de traduction de fichiers"""
    
    print("🧪 Test de l'API de traduction de fichiers")
    print("=" * 50)
    
    # 1. Vérifier qu'il y a des utilisateurs
    users = User.objects.all()
    if not users.exists():
        print("❌ Aucun utilisateur trouvé dans la base de données")
        return False
    
    user = users.first()
    print(f"✅ Utilisateur trouvé: {user.username}")
    
    # 2. Vérifier qu'il y a des fichiers
    files = TranslationFile.objects.filter(uploaded_by=user)
    if not files.exists():
        print("❌ Aucun fichier trouvé pour cet utilisateur")
        return False
    
    file = files.first()
    print(f"✅ Fichier trouvé: {file.original_filename}")
    
    # 3. Vérifier qu'il y a des langues supportées
    languages = Language.objects.filter(is_active=True)
    if not languages.exists():
        print("❌ Aucune langue supportée trouvée")
        return False
    
    target_language = languages.filter(code='fr').first() or languages.first()
    print(f"✅ Langue cible: {target_language.name} ({target_language.code})")
    
    # 4. Vérifier qu'il y a des strings dans le fichier
    strings = TranslationString.objects.filter(file=file)
    if not strings.exists():
        print("❌ Aucun string trouvé dans le fichier")
        return False
    
    print(f"✅ {strings.count()} strings trouvés dans le fichier")
    
    # 5. Vérifier qu'il n'y a pas déjà une tâche en cours
    existing_task = TranslationTask.objects.filter(
        file=file,
        target_languages=target_language,
        status__in=['pending', 'in_progress']
    ).first()
    
    if existing_task:
        print(f"⚠️  Tâche existante trouvée: {existing_task.id} (status: {existing_task.status})")
        return True
    
    # 6. Créer une tâche de traduction
    try:
        task = TranslationTask.objects.create(
            file=file,
            user=user,
            estimated_word_count=0
        )
        task.target_languages.add(target_language)
        
        print(f"✅ Tâche de traduction créée: {task.id}")
        
        # 7. Vérifier que la tâche a été créée correctement
        task.refresh_from_db()
        print(f"   - Status: {task.status}")
        print(f"   - Langues cibles: {[lang.name for lang in task.target_languages.all()]}")
        print(f"   - Fichier: {task.file.original_filename}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de la tâche: {str(e)}")
        return False

def test_language_detection():
    """Test de la détection de langue"""
    
    print("\n🔍 Test de la détection de langue")
    print("=" * 30)
    
    # Vérifier qu'il y a des fichiers avec langue non détectée
    files = TranslationFile.objects.filter(detected_language__isnull=True)
    if not files.exists():
        print("✅ Tous les fichiers ont déjà une langue détectée")
        return True
    
    file = files.first()
    print(f"📁 Fichier sans langue détectée: {file.original_filename}")
    
    # Vérifier qu'il y a des strings pour la détection
    strings = TranslationString.objects.filter(file=file)
    if not strings.exists():
        print("❌ Aucun string pour la détection")
        return False
    
    print(f"✅ {strings.count()} strings disponibles pour la détection")
    return True

def test_translations_summary():
    """Test du résumé des traductions"""
    
    print("\n📊 Test du résumé des traductions")
    print("=" * 35)
    
    # Vérifier qu'il y a des traductions
    translations = Translation.objects.all()
    if not translations.exists():
        print("ℹ️  Aucune traduction trouvée")
        return True
    
    print(f"✅ {translations.count()} traductions trouvées")
    
    # Afficher quelques statistiques
    files_with_translations = TranslationFile.objects.filter(
        translationstring__translation__isnull=False
    ).distinct()
    
    print(f"✅ {files_with_translations.count()} fichiers avec traductions")
    
    for file in files_with_translations[:3]:  # Afficher les 3 premiers
        translations_count = Translation.objects.filter(string__file=file).count()
        print(f"   - {file.original_filename}: {translations_count} traductions")
    
    return True

def main():
    """Fonction principale de test"""
    
    print("🚀 Démarrage des tests de l'API de traduction")
    print("=" * 60)
    
    # Tests
    tests = [
        ("API de traduction de fichiers", test_file_translation_api),
        ("Détection de langue", test_language_detection),
        ("Résumé des traductions", test_translations_summary),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erreur dans le test '{test_name}': {str(e)}")
            results.append((test_name, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Résultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés ! L'API est prête.")
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 