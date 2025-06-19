import requests
import json
import time
from urllib.parse import urlencode

class NotificationAPIClient:
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
    
    # ==================== AUTHENTIFICATION ====================
    
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
    
    # ==================== GESTION DES NOTIFICATIONS - CRUD DE BASE ====================
    
    def get_notifications(self, **params):
        """
        Liste les notifications avec pagination et filtres
        Paramètres supportés: page, page_size, is_read, notification_type, 
        period, search, priority, created_after, ordering
        """
        url = f"{self.base_url}/api/notifications/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, operation="Liste des notifications")
    
    def create_notification(self, title, message, notification_type="system_notification", 
                          priority="medium", user_ids=None, metadata=None):
        """
        Crée une nouvelle notification
        """
        data = {
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority
        }
        
        if user_ids:
            data["user_ids"] = user_ids
        
        if metadata:
            data["metadata"] = metadata
        
        return self._make_authenticated_request('POST', '/api/notifications/', 
                                               data=data, operation="Création notification")
    
    def get_notification_details(self, notification_id):
        """Récupère une notification spécifique"""
        url = f"/api/notifications/{notification_id}/"
        return self._make_authenticated_request('GET', url, 
                                              operation=f"Détails notification {notification_id}")
    
    def update_notification(self, notification_id, **data):
        """Modifie une notification (PUT)"""
        url = f"/api/notifications/{notification_id}/"
        return self._make_authenticated_request('PUT', url, data=data,
                                              operation=f"Modification notification {notification_id}")
    
    def patch_notification(self, notification_id, **data):
        """Modifie partiellement une notification (PATCH)"""
        url = f"/api/notifications/{notification_id}/"
        return self._make_authenticated_request('PATCH', url, data=data,
                                              operation=f"Modification partielle notification {notification_id}")
    
    def delete_notification(self, notification_id):
        """Supprime une notification"""
        url = f"/api/notifications/{notification_id}/"
        return self._make_authenticated_request('DELETE', url,
                                              operation=f"Suppression notification {notification_id}")
    
    # ==================== NOTIFICATIONS SPÉCIALISÉES ====================
    
    def get_unread_notifications(self, **params):
        """Liste uniquement les notifications non lues"""
        url = f"{self.base_url}/api/notifications/unread/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, operation="Notifications non lues")
    
    def get_notifications_by_type(self, notification_type, **params):
        """Notifications par type"""
        url = f"{self.base_url}/api/notifications/type/{notification_type}/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, 
                                              operation=f"Notifications type {notification_type}")
    
    def search_notifications(self, search_term, **params):
        """Recherche dans les notifications"""
        params['search'] = search_term
        url = f"{self.base_url}/api/notifications/search/"
        if params:
            url += f"?{urlencode(params)}"
        
        return self._make_authenticated_request('GET', url, 
                                              operation=f"Recherche notifications: {search_term}")
    
    # ==================== ACTIONS SUR LES NOTIFICATIONS ====================
    
    def mark_notification_read(self, notification_id):
        """Marque une notification comme lue"""
        url = f"/api/notifications/{notification_id}/mark-read/"
        return self._make_authenticated_request('POST', url,
                                              operation=f"Marquer comme lue {notification_id}")
    
    def mark_all_notifications_read(self):
        """Marque toutes les notifications comme lues"""
        url = f"/api/notifications/mark-all-read/"
        return self._make_authenticated_request('POST', url,
                                              operation="Marquer toutes comme lues")
    
    def bulk_mark_notifications_read(self, notification_ids):
        """Marque plusieurs notifications comme lues"""
        data = {"notification_ids": notification_ids}
        url = f"/api/notifications/bulk-mark-read/"
        return self._make_authenticated_request('POST', url, data=data,
                                              operation="Marquage en lot comme lues")
    
    def bulk_delete_notifications(self, notification_ids):
        """Supprime plusieurs notifications"""
        data = {"notification_ids": notification_ids}
        url = f"/api/notifications/bulk-delete/"
        return self._make_authenticated_request('DELETE', url, data=data,
                                              operation="Suppression en lot")
    
    def delete_all_read_notifications(self):
        """Supprime toutes les notifications lues"""
        url = f"/api/notifications/delete-all-read/"
        return self._make_authenticated_request('DELETE', url,
                                              operation="Suppression toutes les lues")
    
    # ==================== STATISTIQUES ET INFORMATIONS ====================
    
    def get_notifications_summary(self):
        """Résumé des notifications"""
        url = f"/api/notifications/summary/"
        return self._make_authenticated_request('GET', url, operation="Résumé notifications")
    
    def get_notifications_stats(self):
        """Statistiques détaillées des notifications"""
        url = f"/api/notifications/stats/"
        return self._make_authenticated_request('GET', url, operation="Statistiques notifications")
    
    def get_unread_count(self):
        """Nombre de notifications non lues"""
        url = f"/api/notifications/count/"
        return self._make_authenticated_request('GET', url, operation="Compteur non lues")
    
    # ==================== PRÉFÉRENCES ====================
    
    def get_notification_preferences(self):
        """Récupère les préférences de notification"""
        url = f"/api/notifications/preferences/"
        return self._make_authenticated_request('GET', url, operation="Préférences notifications")
    
    def update_notification_preferences(self, **preferences):
        """Met à jour les préférences de notification"""
        url = f"/api/notifications/preferences/"
        return self._make_authenticated_request('PUT', url, data=preferences,
                                              operation="Mise à jour préférences")
    
    # ==================== MÉTHODES UTILITAIRES ====================
    
    def monitor_notifications(self, interval=5, duration=60):
        """Surveille les nouvelles notifications en temps réel"""
        print(f"🔄 Surveillance des notifications pendant {duration}s (vérification toutes les {interval}s)...")
        
        start_time = time.time()
        last_count = 0
        
        while time.time() - start_time < duration:
            try:
                count_result = self.get_unread_count()
                current_count = count_result.get('data', {}).get('unread_count', 0) if count_result else 0
                
                if current_count != last_count:
                    print(f"📊 Nouvelles notifications: {current_count} non lues")
                    
                    if current_count > last_count:
                        # Récupérer les dernières notifications
                        recent = self.get_unread_notifications(page_size=5, ordering='-created_at')
                        if recent and recent.get('data', {}).get('results'):
                            print("🔔 Dernières notifications:")
                            for notif in recent['data']['results'][:3]:
                                print(f"   📝 {notif.get('title', 'Sans titre')}: {notif.get('message', '')[:50]}...")
                    
                    last_count = current_count
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n⏹️ Surveillance interrompue par l'utilisateur")
                break
            except Exception as e:
                print(f"❌ Erreur surveillance: {e}")
                time.sleep(interval)
        
        print("✅ Surveillance terminée")
    
    def get_notifications_by_period(self, period="today"):
        """
        Récupère les notifications par période
        Périodes: today, yesterday, week, month, 3months
        """
        return self.get_notifications(period=period, ordering='-created_at')
    
    def get_notifications_by_priority(self, priority="high"):
        """
        Récupère les notifications par priorité
        Priorités: low, medium, high, urgent
        """
        return self.get_notifications(priority=priority, ordering='-created_at')
    
    # ==================== MÉTHODES INTERNES ====================
    
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
            if result:
                print("📋 Réponse:", json.dumps(result, indent=2, ensure_ascii=False))
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
        elif method.upper() == 'PATCH':
            return requests.patch(url, headers=headers, json=data)
        elif method.upper() == 'DELETE':
            return requests.delete(url, headers=headers, json=data if data else None)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {method}")
    
    def _print_error_details(self, response):
        """Affiche les détails d'erreur de la réponse"""
        try:
            error_details = response.json()
            print("📋 Détails de l'erreur:", json.dumps(error_details, indent=2, ensure_ascii=False))
        except Exception:
            print("La réponse d'erreur n'est pas en JSON ou est vide.")
            print(f"Statut: {response.status_code}")
            print(f"Contenu: {response.text}")

# ==================== EXEMPLE D'UTILISATION ====================

def test_notification_client():
    """Test complet du client de notifications"""
    client = NotificationAPIClient()
    
    print("=" * 70)
    print("🚀 TEST CLIENT NOTIFICATIONS")
    print("=" * 70)
    
    # 1. Connexion
    print("\n1️⃣ === CONNEXION ===")
    login_result = client.login("admin1@gmail.com", "Azqsdf12,")
    if not login_result:
        print("❌ Impossible de se connecter. Test interrompu.")
        return
    
    # 2. Profil utilisateur
    print("\n2️⃣ === PROFIL UTILISATEUR ===")
    client.get_profile()
    
    # 3. Statistiques initiales
    print("\n3️⃣ === STATISTIQUES INITIALES ===")
    #client.get_notifications_stats()
    #client.get_unread_count()
    
    # 4. Création de notifications de test
    print("\n4️⃣ === CRÉATION DE NOTIFICATIONS TEST ===")
    
    test_notifications = [
        {
            "title": "Message de bienvenue",
            "message": "Bienvenue sur notre plateforme!",
            "notification_type": "welcome",
            "priority": "medium"
        },
        {
            "title": "Notification urgente",
            "message": "Action requise: Veuillez vérifier votre profil",
            "notification_type": "system_notification",
            "priority": "high"
        },
        {
            "title": "Rappel quotidien",
            "message": "N'oubliez pas de compléter vos tâches du jour",
            "notification_type": "reminder",
            "priority": "low"
        }
    ]
    
    created_ids = []
    for notif_data in test_notifications:
        result = client.create_notification(**notif_data)
        if result and result.get('data', {}).get('id'):
            created_ids.append(result['data']['id'])
    
    print(f"📝 {len(created_ids)} notifications créées avec succès")
    
    # 5. Liste des notifications
    print("\n5️⃣ === LISTE DES NOTIFICATIONS ===")
    all_notifications = client.get_notifications(page_size=10, ordering='-created_at')
    
    # 6. Notifications non lues
    print("\n6️⃣ === NOTIFICATIONS NON LUES ===")
    unread_notifications = client.get_unread_notifications()
    
    # 7. Recherche de notifications
    print("\n7️⃣ === RECHERCHE DE NOTIFICATIONS ===")
    search_results = client.search_notifications("urgent")
    
    # 8. Notifications par type
    print("\n8️⃣ === NOTIFICATIONS PAR TYPE ===")
    system_notifications = client.get_notifications_by_type("system_notification")
    
    # 9. Notifications par priorité
    print("\n9️⃣ === NOTIFICATIONS HAUTE PRIORITÉ ===")
    high_priority = client.get_notifications_by_priority("high")
    
    # 10. Marquer comme lues
    print("\n🔟 === MARQUAGE COMME LUES ===")
    if created_ids:
        # Marquer une notification spécifique
        client.mark_notification_read(created_ids[0])
        
        # Marquer plusieurs en lot
        if len(created_ids) > 1:
            client.bulk_mark_notifications_read(created_ids[1:])
    
    # 11. Résumé et statistiques finales
    print("\n1️⃣1️⃣ === RÉSUMÉ FINAL ===")
    client.get_notifications_summary()
    client.get_unread_count()
    
    # 12. Préférences
    print("\n1️⃣2️⃣ === PRÉFÉRENCES ===")
    client.get_notification_preferences()
    
    # 13. Nettoyage (optionnel)
    print("\n1️⃣3️⃣ === NETTOYAGE (OPTIONNEL) ===")
    if created_ids:
        print(f"💡 Pour nettoyer, vous pouvez supprimer les notifications: {created_ids}")
        # Décommentez la ligne suivante pour supprimer les notifications de test
        # client.bulk_delete_notifications(created_ids)
    
    print("\n" + "=" * 70)
    print("✅ TEST CLIENT NOTIFICATIONS TERMINÉ!")
    print("=" * 70)

# Exécution du test
if __name__ == "__main__":
    test_notification_client()