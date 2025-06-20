#!/usr/bin/env python3
"""
Script de test pour vérifier le fonctionnement de Celery
"""

import os
import sys
import django
import time

# Ajouter le répertoire parent au path Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TransDevI18n.settings')
django.setup()

from django.contrib.auth import get_user_model
from files.models import TranslationFile, TranslationString
from translations.models import Language, TranslationTask, Translation
from translations.tasks import translate_file_task, detect_file_language_task
from celery.result import AsyncResult

User = get_user_model()

def test_celery_connection():
    """Test de la connexion Celery"""
    print("🔌 Test de la connexion Celery")
    print("=" * 40)
    
    try:
        # Test simple avec une tâche
        result = translate_file_task.delay(999, 'fr')  # ID inexistant pour test
        print(f"✅ Tâche envoyée avec succès: {result.id}")
        
        # Vérifier le statut
        time.sleep(2)
        status = result.status
        print(f"📊 Statut de la tâche: {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion Celery: {str(e)}")
        return False

def test_task_creation():
    """Test de création d'une tâche de traduction"""
    print("\n📝 Test de création de tâche")
    print("=" * 30)
    
    try:
        # Vérifier qu'il y a des utilisateurs et fichiers
        users = User.objects.all()
        if not users.exists():
            print("❌ Aucun utilisateur trouvé")
            return False
        
        files = TranslationFile.objects.all()
        if not files.exists():
            print("❌ Aucun fichier trouvé")
            return False
        
        languages = Language.objects.filter(is_active=True)
        if not languages.exists():
            print("❌ Aucune langue trouvée")
            return False
        
        user = users.first()
        file = files.first()
        language = languages.first()
        
        print(f"✅ Utilisateur: {user.username}")
        print(f"✅ Fichier: {file.original_filename}")
        print(f"✅ Langue: {language.name}")
        
        # Créer une tâche
        task = TranslationTask.objects.create(
            file=file,
            user=user,
            estimated_word_count=0
        )
        task.target_languages.add(language)
        
        print(f"✅ Tâche créée: {task.id}")
        print(f"   - Status: {task.status}")
        print(f"   - Fichier: {task.file.original_filename}")
        print(f"   - Langues: {[lang.name for lang in task.target_languages.all()]}")
        
        return task
        
    except Exception as e:
        print(f"❌ Erreur lors de la création: {str(e)}")
        return False

def test_task_execution():
    """Test d'exécution d'une tâche"""
    print("\n⚡ Test d'exécution de tâche")
    print("=" * 35)
    
    try:
        # Créer une tâche
        task = test_task_creation()
        if not task:
            return False
        
        # Lancer la tâche
        print(f"🚀 Lancement de la tâche {task.id}...")
        result = translate_file_task.delay(task.id, 'fr')
        
        print(f"✅ Tâche lancée: {result.id}")
        print(f"   - Task ID: {result.id}")
        print(f"   - Status initial: {result.status}")
        
        # Attendre et vérifier le statut
        for i in range(10):  # Attendre max 10 secondes
            time.sleep(1)
            status = result.status
            print(f"   - Status après {i+1}s: {status}")
            
            if status in ['SUCCESS', 'FAILURE']:
                break
        
        # Vérifier le résultat
        if result.status == 'SUCCESS':
            print("✅ Tâche exécutée avec succès!")
            return True
        elif result.status == 'FAILURE':
            print("❌ Tâche échouée")
            print(f"   - Erreur: {result.result}")
            return False
        else:
            print(f"⚠️  Tâche toujours en cours: {result.status}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution: {str(e)}")
        return False

def test_redis_connection():
    """Test de la connexion Redis"""
    print("\n🔴 Test de la connexion Redis")
    print("=" * 35)
    
    try:
        import redis
        
        # Test de connexion Redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Connexion Redis réussie")
        
        # Vérifier les queues
        queues = r.lrange('celery', 0, -1)
        print(f"📊 Messages dans la queue: {len(queues)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur Redis: {str(e)}")
        return False

def main():
    """Fonction principale de test"""
    
    print("🚀 Tests de diagnostic Celery")
    print("=" * 60)
    
    # Tests
    tests = [
        ("Connexion Redis", test_redis_connection),
        ("Connexion Celery", test_celery_connection),
        ("Création de tâche", lambda: test_task_creation() is not False),
        ("Exécution de tâche", test_task_execution),
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
        print("🎉 Tous les tests sont passés ! Celery fonctionne correctement.")
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")
        
        if not results[0][1]:  # Redis échoué
            print("\n🔧 Solutions possibles:")
            print("   1. Démarrer Redis: sudo systemctl start redis")
            print("   2. Vérifier que Redis écoute sur localhost:6379")
        
        if not results[1][1]:  # Celery échoué
            print("\n🔧 Solutions possibles:")
            print("   1. Redémarrer le worker: celery -A TransDevI18n worker --loglevel=info")
            print("   2. Vérifier la configuration Celery dans settings.py")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 