from django.http import JsonResponse
from django.urls import resolve
from adminTransdevi18n.models import ClientKey

class ClientKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs exemptées totalement (pas besoin de clé même hors navigateur)
        self.free_exempt_urls = [

            #  URLs de l'App  Administration auth par session
            
            
        ]

        # URLs spéciales : clé obligatoire hors navigateur
        self.browser_allowed_urls = [
            'token_obtain_pair',
            'token_refresh',
            'register',
            'login',
            'logout',
            'oauth_providers',
            'oauth_login',
            'password_reset',
            'password_reset_confirm',
            'validate_reset_token'

            
            
        ]

    def __call__(self, request):
        path = request.path
        
        # Exclure l'admin (facultatif)
        if path.startswith('/admin/'):
            return self.get_response(request)

        try:
            match = resolve(path)
            url_name = match.url_name
        except Exception:
            url_name = None

        # Cas 1 : URLs exemptées totalement (libres)
        if url_name in self.free_exempt_urls:
            return self.get_response(request)

        # Cas 2 : URLs spéciales "user-register/login/logout"
        if url_name in self.browser_allowed_urls:
            if self.is_browser_request(request):
                # Requête venant d'un navigateur -> OK sans clé
                return self.get_response(request)
            else:
                # Requête non navigateur -> clé obligatoire
                client_key = request.headers.get('X-Client-Key')
                if not client_key:
                    return JsonResponse({'detail': 'Clé client manquante.'}, status=401)
                try:
                    client = ClientKey.objects.get(key=client_key, is_active=True)
                except ClientKey.DoesNotExist:
                    return JsonResponse({'detail': 'Clé client invalide ou inactive.'}, status=403)
                request.client_key = client
                return self.get_response(request)

        # Cas 3 : Pour toutes les autres URLs

        # Autoriser les requêtes GET sans clé, comme avant
        if request.method == 'GET':
            return self.get_response(request)

        # Autoriser toutes les requêtes provenant d'un navigateur classique
        if self.is_browser_request(request):
            return self.get_response(request)

        # Exiger la clé client pour les autres requêtes (API, scripts, etc.)
        client_key = request.headers.get('X-Client-Key')
        if not client_key:
            return JsonResponse({'detail': 'Clé client manquante.'}, status=401)
        try:
            client = ClientKey.objects.get(key=client_key, is_active=True)
        except ClientKey.DoesNotExist:
            return JsonResponse({'detail': 'Clé client invalide ou inactive.'}, status=403)
        request.client_key = client
        return self.get_response(request)

    def is_browser_request(self, request):
        """
        Détecte si la requête provient d'un navigateur web classique.
        On s’appuie sur le header User-Agent qui contient des signatures de navigateurs.
        """
        user_agent = request.headers.get('User-Agent', '').lower()
        if not user_agent:
            return False

        browsers_signatures = [
            'mozilla',  
            'chrome',
            'safari',
            'firefox',
            'edge',
            'opera',
            'msie', 
            'trident',  
        ]

        return any(signature in user_agent for signature in browsers_signatures)
