import requests
import json
import time
import os
from urllib.parse import urlencode

class TranslationAPIClient:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.client_key = "2852de38650241abb839e5a04a6014bd"
    
    def get_headers(self, include_auth=True):
        """Retourne les en-têtes avec ou sans authentification JWT"""
        headers = {
            "Content-Type": "application/json",
            "X-Client-Key": self.client_key
        }
        
        if include_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers
    
    def get_file_headers(self, include_auth=True):
        """Headers pour l'upload de fichiers (sans Content-Type)"""
        headers = {
            "X-Client-Key": self.client_key
        }
        
        if include_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers
    
    # ==================== AUTHENTIFICATION ====================
    
    def register_user(self, username, email, password, password_confirm=None, first_name=None, last_name=None):
        """Inscription d'un nouvel utilisateur"""
        url = f"{self.base_url}/api/auth/register/"
        data = {
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password_confirm or password,
            "first_name": first_name,
            "last_name": last_name
        }
        
        return self._make_request('POST', url, data, include_auth=False, operation="Inscription")
    
    def login(self, email, password):
        """Connexion et récupération des tokens JWT"""
        url = f"{self.base_url}/api/auth/token/"
        data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(include_auth=False), json=data)
            response.raise_for_status()
            
            response_data = response.json()
            tokens = response_data.get('data', {})
            self.access_token = tokens.get('access')
            self.refresh_token = tokens.get('refresh')
            
            print("✅ Connexion réussie!")
            print("📋 Réponse complète:", json.dumps(response_data, indent=2, ensure_ascii=False))
            
            if self.access_token:
                print(f"🔑 Token d'accès reçu: {self.access_token[:50]}...")
            if self.refresh_token:
                print(f"🔄 Token de rafraîchissement reçu: {self.refresh_token[:50]}...")
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            print("❌ Erreur connexion:", e)
            return None
    
    def refresh_access_token(self):
        """Rafraîchit le token d'accès"""
        if not self.refresh_token:
            print("❌ Aucun refresh token disponible")
            return False
        
        url = f"{self.base_url}/api/auth/token/refresh/"
        data = {"refresh": self.refresh_token}
        
        try:
            response = requests.post(url, headers=self.get_headers(include_auth=False), json=data)
            response.raise_for_status()
            
            response_data = response.json()
            tokens = response_data.get('data', {})
            self.access_token = tokens.get('access')
            
            print("✅ Token rafraîchi avec succès!")
            return True
            
        except requests.exceptions.RequestException as e:
            print("❌ Erreur refresh token:", e)
            return False
    
    def get_profile(self):
        """Récupère le profil utilisateur"""
        return self._make_authenticated_request('GET', '/api/auth/profile/', operation="Profil utilisateur")
    
    # ==================== GESTION DES FICHIERS ====================
    
    def get_files(self, **params):
        """
        Liste des fichiers avec filtres
        Paramètres supportés: page, page_size, status, file_type, filename,
        uploaded_after, uploaded_before, file_size_min, file_size_max,
        framework, has_strings, search, ordering
        """
        url = f"{self.base_url}/api/files/files/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, operation="Liste des fichiers")
    
    def upload_file(self, file_path):
        """Upload d'un fichier de traduction - VERSION CORRIGÉE"""
        url = f"{self.base_url}/api/files/files/"
        
        if not os.path.exists(file_path):
            print(f"❌ Fichier non trouvé: {file_path}")
            return None
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                headers = self.get_file_headers(include_auth=True)
                
                print(f"📤 Upload du fichier: {file_path}")
                print(f"📊 Taille du fichier: {os.path.getsize(file_path)} bytes")
                
                response = requests.post(url, headers=headers, files=files)
                
                # Debug: Afficher le statut et le contenu brut
                print(f"🔍 Status Code: {response.status_code}")
                print(f"🔍 Response Headers: {dict(response.headers)}")
                print(f"🔍 Response Content: {response.text}")
                
                response.raise_for_status()
                
                # Gérer les réponses vides ou non-JSON
                result = None
                if response.content.strip():
                    try:
                        result = response.json()
                    except json.JSONDecodeError:
                        print("⚠️ Réponse non-JSON reçue")
                        result = {"status": "uploaded", "message": "Upload réussi", "raw_response": response.text}
                else:
                    print("⚠️ Réponse vide reçue")
                    result = {"status": "uploaded", "message": "Upload réussi (réponse vide)"}
                
                print("✅ Upload réussi!")
                if result:
                    print("📋 Réponse:", json.dumps(result, indent=2, ensure_ascii=False))
                
                return result
                
        except requests.exceptions.RequestException as e:
            print("❌ Erreur upload:", e)
            if hasattr(e, 'response') and e.response is not None:
                self._print_error_details(e.response)
            return None
    
    def get_file_details(self, file_id):
        """Détails d'un fichier spécifique"""
        url = f"{self.base_url}/api/files/files/{file_id}/"
        return self._make_authenticated_request('GET', url, operation=f"Détails fichier {file_id}")
    
    def get_file_progress(self, file_id):
        """Progrès de traitement d'un fichier"""
        url = f"{self.base_url}/api/files/files/{file_id}/progress/"
        return self._make_authenticated_request('GET', url, operation=f"Progrès fichier {file_id}")
    
    def get_file_download_url(self, file_id):
        """Lien de téléchargement d'un fichier"""
        url = f"{self.base_url}/api/files/files/{file_id}/download/"
        return self._make_authenticated_request('GET', url, operation=f"Download URL fichier {file_id}")
    
    def get_files_statistics(self):
        """Statistiques globales des fichiers"""
        url = f"{self.base_url}/api/files/files/statistics/"
        return self._make_authenticated_request('GET', url, operation="Statistiques des fichiers")
    
    # ==================== GESTION DES CHAÎNES ====================
    
    def get_strings(self, **params):
        """
        Liste des chaînes de traduction avec filtres
        Paramètres: page, page_size, file, file_name, file_type, key,
        source_text, context, is_translated, is_fuzzy, is_plural,
        line_number, line_number_min, line_number_max, has_translations,
        search, ordering
        """
        url = f"{self.base_url}/api/files/strings/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, operation="Liste des chaînes")
    
    def get_string_details(self, string_id):
        """Détails d'une chaîne spécifique"""
        url = f"{self.base_url}/api/files/strings/{string_id}/"
        return self._make_authenticated_request('GET', url, operation=f"Détails chaîne {string_id}")
    
    def get_strings_by_file(self, file_id, **params):
        """Chaînes d'un fichier spécifique"""
        params['file_id'] = file_id
        url = f"{self.base_url}/api/files/strings/by_file/?{urlencode(params)}"
        return self._make_authenticated_request('GET', url, operation=f"Chaînes du fichier {file_id}")
    
    def get_strings_statistics(self):
        """Statistiques globales des chaînes"""
        url = f"{self.base_url}/api/files/strings/statistics/"
        return self._make_authenticated_request('GET', url, operation="Statistiques des chaînes")
    
    # ==================== MÉTHODES UTILITAIRES ====================
    
    def monitor_file_progress(self, file_id, max_attempts=30, interval=2):
        """Surveille le progrès de traitement d'un fichier"""
        print(f"🔄 Surveillance du progrès pour le fichier {file_id}...")
        
        for attempt in range(max_attempts):
            progress_data = self.get_file_progress(file_id)
            
            if not progress_data:
                print("❌ Impossible de récupérer le progrès")
                return False
            
            status = progress_data.get('status')
            progress = progress_data.get('progress', 0)
            
            print(f"📊 Tentative {attempt + 1}: Status={status}, Progrès={progress}%")
            
            if status == 'completed':
                print("✅ Traitement terminé!")
                return True
            elif status == 'error':
                print(f"❌ Erreur de traitement: {progress_data.get('error', 'Erreur inconnue')}")
                return False
            
            time.sleep(interval)
        
        print("⏰ Timeout: Surveillance interrompue")
        return False
    
    def _make_authenticated_request(self, method, url, data=None, operation="Requête"):
        """Effectue une requête authentifiée avec gestion du refresh token"""
        if not self.access_token:
            print("❌ Aucun token d'accès. Veuillez vous connecter d'abord.")
            return None
        
        # Si l'URL ne commence pas par http, l'ajouter
        if not url.startswith('http'):
            if url.startswith('/'):
                url = f"{self.base_url}{url}"
            else:
                url = f"{self.base_url}/{url}"
        
        headers = self.get_headers(include_auth=True)
        
        try:
            response = self._execute_request(method, url, headers, data)
            
            # Si le token a expiré (401), essayer de le rafraîchir
            if response.status_code == 401:
                print("🔄 Token expiré, tentative de rafraîchissement...")
                if self.refresh_access_token():
                    headers = self.get_headers(include_auth=True)
                    response = self._execute_request(method, url, headers, data)
            
            response.raise_for_status()
            
            # Gestion des réponses vides (DELETE 204)
            if response.status_code == 204:
                print(f"✅ {operation} réussi(e) (204 No Content)")
                return {"status": "success", "message": "Opération réussie"}
            
            result = response.json() if response.content else None
            print(f"✅ {operation} réussi(e)!")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur {operation}:", e)
            if hasattr(e, 'response') and e.response is not None:
                self._print_error_details(e.response)
            return None
    
    def _execute_request(self, method, url, headers, data):
        """Exécute la requête HTTP selon la méthode"""
        if method.upper() == 'GET':
            return requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            return requests.post(url, headers=headers, json=data)
        elif method.upper() == 'PUT':
            return requests.put(url, headers=headers, json=data)
        elif method.upper() == 'DELETE':
            return requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {method}")
    
    def _make_request(self, method, url, data=None, include_auth=True, operation="Requête"):
        """Méthode générique pour les requêtes"""
        try:
            headers = self.get_headers(include_auth=include_auth)
            response = self._execute_request(method, url, headers, data)
            response.raise_for_status()
            
            result = response.json() if response.content else None
            print(f"✅ {operation} réussi(e)!")
            if result:
                print("📋 Réponse:", json.dumps(result, indent=2, ensure_ascii=False))
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur {operation}:", e)
            if hasattr(e, 'response') and e.response is not None:
                self._print_error_details(e.response)
            return None
    
    def _print_error_details(self, response):
        """Affiche les détails d'erreur de la réponse"""
        try:
            error_details = response.json()
            print("📋 Détails de l'erreur:", json.dumps(error_details, indent=2, ensure_ascii=False))
        except Exception:
            print("La réponse d'erreur n'est pas en JSON ou est vide.")
            print(f"Statut: {response.status_code}")
            print(f"Contenu: {response.text}")

# ==================== TEST AVEC DJANGO_TRANSLATION.PO - VERSION CORRIGÉE ====================

def test_django_translation():
    """Test avec le fichier django_translation.po spécifique - VERSION CORRIGÉE"""
    client = TranslationAPIClient()
    
    # Chemin fixe du fichier
    django_po_path = "/home/billa/Téléchargements/django_translation.po"
    
    # Données utilisateur pour les tests
    user_data = {
        "username": "o_tesdddstDDer_2025",
        "email": "d_tcesddtdceddr@exDDample.com",
        "password": "DjangoTest123!",
        "password_confirm": "DjangoTest123!",
        "first_name": "Django",
        "last_name": "Tester"
    }
    
    print("=" * 70)
    print("🚀 TEST AVEC DJANGO_TRANSLATION.PO - VERSION CORRIGÉE")
    print("=" * 70)
    
    # 1. Vérifier que le fichier existe
    if not os.path.exists(django_po_path):
        print(f"❌ Fichier non trouvé: {django_po_path}")
        print("💡 Vérifiez que le fichier existe dans le répertoire spécifié")
        return
    
    print(f"✅ Fichier trouvé: {django_po_path}")
    print(f"📊 Taille du fichier: {os.path.getsize(django_po_path)} bytes")
    
    # 2. Inscription (optionnelle si l'utilisateur existe déjà)
    print("\n1️⃣ === INSCRIPTION UTILISATEUR ===")
    registration_result = client.register_user(**user_data)
    if registration_result:
        print("✅ Inscription réussie!")
    else:
        print("⚠️ Inscription échouée (utilisateur existe peut-être déjà)")
    
    # 3. Connexion
    print("\n2️⃣ === CONNEXION ===")
    login_result = client.login("Billa1818@gmail.com","1234")
    if not login_result:
        print("❌ Impossible de se connecter. Test interrompu.")
        return
    
    # 4. Profil utilisateur
    print("\n3️⃣ === PROFIL UTILISATEUR ===")
    client.get_profile()
    
    # 5. État initial des fichiers
    print("\n4️⃣ === ÉTAT INITIAL DES FICHIERS ===")
    initial_files = client.get_files()
    if initial_files:
        print(f"📁 Nombre de fichiers existants: {initial_files.get('count', 0)}")
    
    # 6. Upload du fichier django_translation.po - LOGIQUE CORRIGÉE
    print("\n5️⃣ === UPLOAD DU FICHIER DJANGO_TRANSLATION.PO ===")
    uploaded_file = client.upload_file(django_po_path)
    
    # Nouvelle logique pour gérer l'upload
    file_id = None
    
    if uploaded_file is not None:
        print("✅ Upload traité avec succès!")
        
        # Essayer de récupérer l'ID depuis la réponse
        if isinstance(uploaded_file, dict):
            file_data = uploaded_file.get('data', {})
            file_id = file_data.get('id')
            
            if not file_id:
                # Si pas d'ID dans data, chercher dans la racine
                file_id = uploaded_file.get('id')
        
        # Si on n'a toujours pas d'ID, récupérer la liste des fichiers
        if not file_id:
            print("🔍 Récupération de l'ID via la liste des fichiers...")
            files_list = client.get_files(ordering='-uploaded_at', page_size=1)
            if files_list and files_list.get('results'):
                latest_file = files_list['results'][0]
                file_id = latest_file.get('id')
                print(f"🆔 ID du fichier le plus récent: {file_id}")
        
        if file_id:
            print(f"🆔 ID du fichier à utiliser: {file_id}")
        else:
            print("⚠️ Impossible de récupérer l'ID du fichier, mais continuons les tests généraux...")
    else:
        print("❌ Échec de l'upload.")
        print("🔄 Tentative de récupération du dernier fichier uploadé...")
        
        # Essayer de récupérer quand même le dernier fichier
        files_list = client.get_files(ordering='-uploaded_at', page_size=1)
        if files_list and files_list.get('results'):
            latest_file = files_list['results'][0]
            file_id = latest_file.get('id')
            print(f"🆔 Utilisation du fichier le plus récent: {file_id}")
    
    # Continuer les tests si on a un file_id
    if file_id:
        # 7. Surveillance du traitement
        print("\n6️⃣ === SURVEILLANCE DU TRAITEMENT ===")
        processing_success = client.monitor_file_progress(file_id, max_attempts=15, interval=2)
        
        if not processing_success:
            print("⚠️ Le traitement n'est pas terminé, mais continuons les tests...")
        
        # 8. Détails du fichier traité
        print("\n7️⃣ === DÉTAILS DU FICHIER TRAITÉ ===")
        file_details = client.get_file_details(file_id)
        
        if file_details:
            data = file_details.get('data', {})
            print(f"📄 Nom: {data.get('filename')}")
            print(f"📊 Statut: {data.get('status')}")
            print(f"🔢 Nombre de chaînes: {data.get('string_count', 0)}")
            print(f"🌐 Framework: {data.get('framework')}")
            print(f"📅 Date d'upload: {data.get('uploaded_at')}")
        
        # 9. Analyse des chaînes du fichier
        print("\n8️⃣ === ANALYSE DES CHAÎNES ===")
        file_strings = client.get_strings_by_file(file_id, page_size=10)
        
        if file_strings:
            strings_data = file_strings.get('results', [])
            print(f"🔤 Premières chaînes trouvées: {len(strings_data)}")
            
            for i, string_data in enumerate(strings_data[:5], 1):
                print(f"\n🔸 Chaîne {i}:")
                print(f"   🗝️ Clé: {string_data.get('key', 'N/A')}")
                print(f"   📝 Texte source: {string_data.get('source_text', 'N/A')[:100]}...")
                print(f"   ✅ Traduite: {string_data.get('is_translated', False)}")
                print(f"   📍 Ligne: {string_data.get('line_number', 'N/A')}")
        
        # 14. URL de téléchargement
        print("\n1️⃣3️⃣ === URL DE TÉLÉCHARGEMENT ===")
        download_url = client.get_file_download_url(file_id)
    
    # Tests généraux (pas besoin de file_id spécifique)
    
    # 10. Statistiques des chaînes
    print("\n9️⃣ === STATISTIQUES DES CHAÎNES ===")
    strings_stats = client.get_strings_statistics()
    
    # 11. Recherche de chaînes spécifiques
    print("\n🔟 === RECHERCHE DE CHAÎNES SPÉCIFIQUES ===")
    
    # Rechercher des chaînes communes dans Django
    search_terms = ['login', 'password', 'email', 'user', 'error', 'admin']
    
    for term in search_terms:
        print(f"\n🔍 Recherche de '{term}':")
        search_result = client.get_strings(search=term, page_size=3)
        if search_result and search_result.get('results'):
            print(f"   ✅ {len(search_result['results'])} résultat(s) trouvé(s)")
            for result in search_result['results'][:2]:
                print(f"   📝 {result.get('source_text', '')[:80]}...")
        else:
            print(f"   ❌ Aucun résultat pour '{term}'")
    
    # 12. Chaînes non traduites
    print("\n1️⃣1️⃣ === CHAÎNES NON TRADUITES ===")
    untranslated = client.get_strings(is_translated=False, page_size=5)
    if untranslated and untranslated.get('results'):
        print(f"🔴 {len(untranslated['results'])} chaînes non traduites trouvées")
        for string_data in untranslated['results']:
            print(f"   📝 {string_data.get('source_text', '')[:80]}...")
    
    # 13. Chaînes traduites
    print("\n1️⃣2️⃣ === CHAÎNES TRADUITES ===")
    translated = client.get_strings(is_translated=True, page_size=5)
    if translated and translated.get('results'):
        print(f"🟢 {len(translated['results'])} chaînes traduites trouvées")
        for string_data in translated['results']:
            print(f"   📝 {string_data.get('source_text', '')[:80]}...")
    
    # 15. Statistiques finales
    print("\n1️⃣4️⃣ === STATISTIQUES FINALES ===")
    client.get_files_statistics()
    
    print("\n" + "=" * 70)
    print("✅ TEST AVEC DJANGO_TRANSLATION.PO TERMINÉ!")
    print("=" * 70)
    
    return file_id

# Exécution du test
if __name__ == "__main__":
    test_django_translation()