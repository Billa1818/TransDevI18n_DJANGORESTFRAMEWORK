import requests
import json

class APIClient:
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
    
    def register_user(self, username, email, password, password_confirm=None, first_name=None, last_name=None):
        """Inscription d'un nouvel utilisateur"""
        url = f"{self.base_url}/api/auth/register/"  # Assumant que l'endpoint d'inscription est différent
        data = {
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password_confirm or password,  # Utilise password_confirm
            "first_name": first_name,
            "last_name": last_name
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(include_auth=False), json=data)
            response.raise_for_status()
            print("✅ Inscription réussie:", response.json())
            return response.json()
        except requests.exceptions.HTTPError as e:
            print("❌ Erreur HTTP inscription:", e)
            self._print_error_details(response)
            return None
        except requests.exceptions.RequestException as e:
            print("❌ Erreur requête inscription:", e)
            return None
    
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
            tokens = response_data.get('data', {})  # Extraire l'objet 'data'
            self.access_token = tokens.get('access')
            self.refresh_token = tokens.get('refresh')
            
            print("✅ Connexion réussie!")
            print("📋 Réponse complète:", response_data)
            
            if self.access_token:
                print(f"🔑 Token d'accès reçu: {self.access_token[:50]}...")
            else:
                print("⚠️ Aucun token d'accès trouvé dans la réponse")
                print("🔍 Clés disponibles dans 'data':", list(tokens.keys()) if tokens else "Aucune")
            
            if self.refresh_token:
                print(f"🔄 Token de rafraîchissement reçu: {self.refresh_token[:50]}...")
            else:
                print("⚠️ Aucun token de rafraîchissement trouvé")
            
            return response_data
            
        except requests.exceptions.HTTPError as e:
            print("❌ Erreur HTTP connexion:", e)
            self._print_error_details(response)
            return None
        except requests.exceptions.RequestException as e:
            print("❌ Erreur requête connexion:", e)
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
            tokens = response_data.get('data', {})  # Extraire l'objet 'data'
            self.access_token = tokens.get('access')
            
            print("✅ Token rafraîchi avec succès!")
            return True
            
        except requests.exceptions.HTTPError as e:
            print("❌ Erreur HTTP refresh token:", e)
            self._print_error_details(response)
            return False
        except requests.exceptions.RequestException as e:
            print("❌ Erreur requête refresh token:", e)
            return False
    
    def make_authenticated_request(self, method, endpoint, data=None):
        """Effectue une requête authentifiée"""
        if not self.access_token:
            print("❌ Aucun token d'accès. Veuillez vous connecter d'abord.")
            return None
        
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers(include_auth=True)
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                print(f"❌ Méthode HTTP non supportée: {method}")
                return None
            
            # Si le token a expiré (401), essayer de le rafraîchir
            if response.status_code == 401:
                print("🔄 Token expiré, tentative de rafraîchissement...")
                if self.refresh_access_token():
                    # Réessayer la requête avec le nouveau token
                    headers = self.get_headers(include_auth=True)
                    if method.upper() == 'GET':
                        response = requests.get(url, headers=headers)
                    elif method.upper() == 'POST':
                        response = requests.post(url, headers=headers, json=data)
                    elif method.upper() == 'PUT':
                        response = requests.put(url, headers=headers, json=data)
                    elif method.upper() == 'DELETE':
                        response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            print(f"✅ Requête {method.upper()} réussie!")
            return response.json() if response.content else None
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ Erreur HTTP {method.upper()}:", e)
            self._print_error_details(response)
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur requête {method.upper()}:", e)
            return None
    
    def _print_error_details(self, response):
        """Affiche les détails d'erreur de la réponse"""
        try:
            error_details = response.json()
            print("Détails de l'erreur:", json.dumps(error_details, indent=2, ensure_ascii=False))
        except Exception:
            print("La réponse d'erreur n'est pas en JSON ou est vide.")
            print(f"Statut: {response.status_code}")
            print(f"Contenu: {response.text}")

# Exemple d'utilisation
if __name__ == "__main__":
    # Initialiser le client
    client = APIClient()
    
    # Données utilisateur
    user_data = {
        "username": "Billaduijkghkyu1818",
        "email": "billa1d8jukjhkjhpfoio18@gmail.com",
        "password": "Azqsdf12,",
        "password_confirm": "Azqsdf12,",  # Correspond maintenant au paramètre attendu
        "first_name": "John",
        "last_name": "Doe"
    }
    
    # 1. Inscription (si nécessaire)
    print("=== INSCRIPTION ===")
    client.register_user(**user_data)
    
    # 2. Connexion pour obtenir les tokens
    print("\n=== CONNEXION ===")
    client.login(user_data["email"], user_data["password"])
    
    # 3. Exemple de requêtes authentifiées
    print("\n=== REQUÊTES AUTHENTIFIÉES ===")
    
    # GET - Récupérer le profil utilisateur
    profile = client.make_authenticated_request('GET', '/api/auth/profile/')
    
   