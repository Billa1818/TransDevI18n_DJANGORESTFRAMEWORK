# =============================================================================
# Commande Django pour peupler les langues supportées
# =============================================================================

from django.core.management.base import BaseCommand
from translations.models import Language
from translations.services import google_translate_service

class Command(BaseCommand):
    help = 'Peuple la base de données avec les langues supportées par Google Translate'

    def handle(self, *args, **options):
        self.stdout.write('Début du peuplement des langues...')
        
        # Récupérer les langues supportées
        supported_languages = google_translate_service.get_supported_languages()
        
        created_count = 0
        updated_count = 0
        
        for code, name in supported_languages.items():
            # Créer ou mettre à jour la langue
            language, created = Language.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'native_name': name,  # Pour l'instant, on utilise le même nom
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Créée: {code} - {name}')
            else:
                # Mettre à jour le nom si nécessaire
                if language.name != name:
                    language.name = name
                    language.save()
                    updated_count += 1
                    self.stdout.write(f'  ↻ Mise à jour: {code} - {name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Peuplement terminé ! {created_count} langues créées, {updated_count} mises à jour.'
            )
        ) 