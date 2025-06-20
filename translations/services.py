# =============================================================================
# APP: translations - Services (Google Translate avec contrôle d'intégrité complet)
# =============================================================================

# translations/services.py
from googletrans import Translator
from django.conf import settings
import logging
import time
import random
import re

logger = logging.getLogger(__name__)

class GoogleTranslateService:
    """Service de traduction utilisant Google Translate avec contrôle d'intégrité renforcé"""
    
    def __init__(self):
        self.translator = Translator()
        self.max_retries = 3
        self.retry_delay = 2  # secondes
        
        # Liste blanche étendue de noms propres/sigles à ne jamais traduire
        self.WHITELIST = {
            'Django', 'HTML', 'API', 'JSON', 'React', 'GitHub', 'JavaScript', 'CSS',
            'SQL', 'HTTP', 'HTTPS', 'URL', 'XML', 'YAML', 'npm', 'Node.js', 'Vue.js',
            'Angular', 'Bootstrap', 'jQuery', 'PHP', 'Python', 'Java', 'C++', 'C#',
            'iOS', 'Android', 'Windows', 'Linux', 'macOS', 'Ubuntu', 'MySQL', 'PostgreSQL',
            'MongoDB', 'Redis', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'Google Cloud',
            'Firebase', 'Stripe', 'PayPal', 'OAuth', 'JWT', 'REST', 'GraphQL', 'WebSocket'
        }
        
        # Ponctuation française nécessitant un espace insécable
        self.FRENCH_PUNCTUATION = [':', ';', '!', '?', '»']
        self.FRENCH_PUNCT_OPEN = ['«']
        self.INSECABLE = '\u00A0'  # Espace insécable
        
        # Patterns pour dates, prix, unités, emails, URLs
        self.DATE_PATTERNS = [
            r'\d{1,2}/\d{1,2}/\d{4}', r'\d{4}-\d{2}-\d{2}', r'\d{1,2} \w+ \d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}', r'\d{1,2}\.\d{1,2}\.\d{4}'
        ]
        self.PRICE_PATTERNS = [
            r'\d+[,\.]\d+\s?[€$£¥]', r'[€$£¥]\s?\d+[,\.]\d+', r'\d+[,\.]\d+\s?USD',
            r'\d+[,\.]\d+\s?EUR', r'\d+\s?[€$£¥]', r'[€$£¥]\s?\d+'
        ]
        self.UNIT_PATTERNS = [
            r'\d+\s?(kg|g|mg|l|ml|cm|m|km|°C|°F|%)', r'\d+[,\.]\d+\s?(kg|g|mg|l|ml|cm|m|km)'
        ]
        self.EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        self.URL_PATTERN = r'https?://[^\s<>"{}|\\^`\[\]]+'
        
        # Symboles et caractères spéciaux
        self.SPECIAL_CHARS = ['…', '–', '—', '©', '®', '™', '°', '±', '×', '÷', '∞', '≠', '≤', '≥']
        self.WHITESPACE_CHARS = ['\n', '\t', '\r']
        
    def _extract_po_variables(self, text):
        """Extrait toutes les variables Django ET les variables simples {var}"""
        # Variables Django %(var)s - COMPLÈTES avec parenthèses et type
        django_vars_full = re.findall(r'%\([a-zA-Z0-9_]+\)[sdfluxXeEfFgG%]', text)
        # Variables Django %(var)s - noms seulement pour vérification
        django_vars_names = re.findall(r'%\(([a-zA-Z0-9_]+)\)[sdfluxXeEfFgG%]', text)
        # Anciens formats %s, %d, %f avec position
        old_formats = re.findall(r'%[sdfluxXeEfFgG%]', text)
        # Formats positionnels %1$s, %2$d, etc.
        positional_formats = re.findall(r'%\d+\$[sdfluxXeEfFgG]', text)
        
        # Variables simples {var} dans les .po
        simple_vars_full = re.findall(r'{\s*[a-zA-Z0-9_\.]+\s*}', text)
        simple_vars_names = re.findall(r'{\s*([a-zA-Z0-9_\.]+)\s*}', text)
        
        return (django_vars_full, django_vars_names, old_formats, positional_formats,
                simple_vars_full, simple_vars_names)

    
    def _extract_json_variables(self, text):
        """Extrait toutes les variables i18next ET les variables simples {var}"""
        # Variables i18next {{var}} - COMPLÈTES
        i18next_simple_full = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*}}', text)
        # Variables i18next {{var}} - noms seulement
        i18next_simple_names = re.findall(r'{{\s*([a-zA-Z0-9_\.]+)\s*}}', text)
        # Variables i18next avec formatage {{var, format}} - COMPLÈTES
        i18next_formatted_full = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*,\s*[a-zA-Z0-9_]+\s*}}', text)
        # Variables i18next avec paramètres {{var, format, param}} - COMPLÈTES
        i18next_param_full = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*,\s*[a-zA-Z0-9_]+\s*,\s*[^}]+\s*}}', text)
        
        # Variables simples {var} (très courantes)
        simple_vars_full = re.findall(r'{\s*[a-zA-Z0-9_\.]+\s*}', text)
        simple_vars_names = re.findall(r'{\s*([a-zA-Z0-9_\.]+)\s*}', text)
        
        return (i18next_simple_full, i18next_simple_names, i18next_formatted_full, 
                i18next_param_full, simple_vars_full, simple_vars_names)

    
    def _extract_html_tags(self, text):
        """Extrait toutes les balises HTML avec leurs attributs"""
        # Balises ouvrantes avec attributs
        opening_tags = re.findall(r'<([a-zA-Z0-9]+)(?:\s+[^>]*)>', text)
        # Balises fermantes
        closing_tags = re.findall(r'</([a-zA-Z0-9]+)>', text)
        # Balises auto-fermantes
        self_closing = re.findall(r'<([a-zA-Z0-9]+)(?:\s+[^>]*)?/>', text)
        # Balises complètes pour vérification exacte
        full_tags = re.findall(r'<[^>]+>', text)
        return opening_tags, closing_tags, self_closing, full_tags
    
    def _check_case_preservation(self, source_vars, translated_vars):
        """Vérifie que la casse des variables est préservée"""
        errors = []
        for i, (src_var, trans_var) in enumerate(zip(source_vars, translated_vars)):
            if src_var != trans_var:
                if src_var.lower() == trans_var.lower():
                    errors.append(f"Casse modifiée pour la variable #{i+1}: '{src_var}' → '{trans_var}'")
                else:
                    errors.append(f"Variable #{i+1} complètement changée: '{src_var}' → '{trans_var}'")
        return errors
    
    def _check_french_punctuation(self, source, translated):
        """Vérifie les espaces insécables avant la ponctuation française"""
        errors = []
        for punct in self.FRENCH_PUNCTUATION:
            # Vérifier espace insécable avant
            if self.INSECABLE + punct in source and self.INSECABLE + punct not in translated:
                errors.append(f"Espace insécable manquant avant '{punct}'")
            # Vérifier qu'on n'a pas ajouté d'espace normal à la place
            if ' ' + punct in translated and self.INSECABLE + punct in source:
                errors.append(f"Espace normal utilisé au lieu d'insécable avant '{punct}'")
        
        for punct in self.FRENCH_PUNCT_OPEN:
            # Vérifier espace insécable après
            if punct + self.INSECABLE in source and punct + self.INSECABLE not in translated:
                errors.append(f"Espace insécable manquant après '{punct}'")
        
        return errors
    
    def _check_special_elements(self, source, translated):
        """Vérifie la préservation des éléments spéciaux"""
        errors = []
        
        # Caractères spéciaux
        for char in self.SPECIAL_CHARS + self.WHITESPACE_CHARS:
            source_count = source.count(char)
            translated_count = translated.count(char)
            if source_count != translated_count:
                errors.append(f"Caractère spécial '{repr(char)}' : {source_count} → {translated_count}")
        
        # Noms propres et sigles
        for word in self.WHITELIST:
            if word in source and word not in translated:
                errors.append(f"Nom propre/sigle '{word}' manquant")
            source_count = source.count(word)
            translated_count = translated.count(word)
            if source_count != translated_count:
                errors.append(f"Nom propre/sigle '{word}' : {source_count} occurrence(s) → {translated_count}")
        
        # Formats de date, prix, unités
        all_patterns = self.DATE_PATTERNS + self.PRICE_PATTERNS + self.UNIT_PATTERNS
        for pattern in all_patterns:
            source_matches = re.findall(pattern, source)
            translated_matches = re.findall(pattern, translated)
            if source_matches != translated_matches:
                errors.append(f"Format manquant/modifié - Pattern: {pattern}")
        
        # Emails et URLs
        for pattern, name in [(self.EMAIL_PATTERN, 'email'), (self.URL_PATTERN, 'URL')]:
            source_matches = re.findall(pattern, source)
            translated_matches = re.findall(pattern, translated)
            if source_matches != translated_matches:
                errors.append(f"Format {name} manquant/modifié")
        
        return errors

    def _check_po_integrity(self, source, translated):
        """Contrôle d'intégrité complet pour fichiers .po Django avec TOLÉRANCE ZÉRO"""
        errors = []
        
        # 1. Variables Django + simples - Extraction complète
        (src_django_full, src_django_names, src_old, src_pos, src_simple, src_simple_names) = self._extract_po_variables(source)
        (trans_django_full, trans_django_names, trans_old, trans_pos, trans_simple, trans_simple_names) = self._extract_po_variables(translated)
        
        # Variables Django %(var)s - DOIVENT être EXACTEMENT identiques
        if sorted(src_django_full) != sorted(trans_django_full):
            errors.append(f"Variables Django %(var)s modifiées: {src_django_full} → {trans_django_full}")
        
        # Variables simples {var} - DOIVENT être EXACTEMENT identiques
        if sorted(src_simple) != sorted(trans_simple):
            errors.append(f"Variables simples {{var}} modifiées: {src_simple} → {trans_simple}")
        
        # Anciens formats - DOIVENT être EXACTEMENT identiques
        if sorted(src_old) != sorted(trans_old):
            errors.append(f"Formats anciens (%s, %d) modifiés: {src_old} → {trans_old}")
        
        # Formats positionnels - DOIVENT être EXACTEMENT identiques
        if sorted(src_pos) != sorted(trans_pos):
            errors.append(f"Formats positionnels (%1$s) modifiés: {src_pos} → {trans_pos}")
        
        # 2. Balises HTML - DOIVENT être EXACTEMENT identiques
        src_open, src_close, src_self, src_full_html = self._extract_html_tags(source)
        trans_open, trans_close, trans_self, trans_full_html = self._extract_html_tags(translated)
        
        if sorted(src_full_html) != sorted(trans_full_html):
            errors.append(f"Balises HTML modifiées: {src_full_html} → {trans_full_html}")
        
        # 3. Ponctuation française
        errors.extend(self._check_french_punctuation(source, translated))
        
        # 4. Éléments spéciaux
        errors.extend(self._check_special_elements(source, translated))
        
        return (len(errors) == 0), "; ".join(errors)



    def _check_json_integrity(self, source, translated):
        """Contrôle d'intégrité complet pour fichiers .json i18next avec TOLÉRANCE ZÉRO"""
        errors = []
        
        # 1. Variables i18next - Extraction complète
        (src_simple, src_names, src_formatted, src_param, src_simple_vars, src_simple_names) = self._extract_json_variables(source)
        (trans_simple, trans_names, trans_formatted, trans_param, trans_simple_vars, trans_simple_names) = self._extract_json_variables(translated)
        
        # Variables i18next {{var}} - DOIVENT être EXACTEMENT identiques
        if sorted(src_simple) != sorted(trans_simple):
            errors.append(f"Variables i18next {{var}} modifiées: {src_simple} → {trans_simple}")
        
        # Variables formatées {{var, format}} - DOIVENT être EXACTEMENT identiques
        if sorted(src_formatted) != sorted(trans_formatted):
            errors.append(f"Variables formatées modifiées: {src_formatted} → {trans_formatted}")
        
        # Variables paramétrées {{var, format, param}} - DOIVENT être EXACTEMENT identiques
        if sorted(src_param) != sorted(trans_param):
            errors.append(f"Variables paramétrées modifiées: {src_param} → {trans_param}")
        
        # Variables simples {var} - DOIVENT être EXACTEMENT identiques
        if sorted(src_simple_vars) != sorted(trans_simple_vars):
            errors.append(f"Variables simples {{var}} modifiées: {src_simple_vars} → {trans_simple_vars}")
        
        # 2. Balises HTML - DOIVENT être EXACTEMENT identiques
        src_open, src_close, src_self, src_full = self._extract_html_tags(source)
        trans_open, trans_close, trans_self, trans_full = self._extract_html_tags(translated)
        
        if sorted(src_full) != sorted(trans_full):
            errors.append(f"Balises HTML modifiées: {src_full} → {trans_full}")
        
        # 3. Clés JSON (ne pas traduire les clés dans les messages d'erreur)
        json_keys = re.findall(r'"([a-zA-Z0-9_\.]+)"\s*:', source)
        if json_keys:
            for key in json_keys:
                if key in source and key not in translated:
                    errors.append(f"Clé JSON '{key}' manquante (ne pas traduire les clés)")
        
        # 4. Suffixes pluriels (*plural, _plural)
        plural_suffixes = re.findall(r'([a-zA-Z0-9_]+)(\*plural|_plural)', source)
        for base, suffix in plural_suffixes:
            if base + suffix not in translated:
                errors.append(f"Suffixe pluriel '{base}{suffix}' manquant")
        
        # 5. Éléments spéciaux
        errors.extend(self._check_special_elements(source, translated))
        
        return (len(errors) == 0), "; ".join(errors)

    
    def _mask_variables(self, text, file_type=None):
        """
        Remplace TOUTES les variables par des jetons INVISIBLES pour Google Translate.
        SOLUTION: Utiliser des mots anglais courants que GT ne touchera jamais.
        """
        mapping = {}
        masked = text
        
        if file_type == 'po':
            # 1. Variables Django %(var)s - PRIORITÉ ABSOLUE
            django_vars = re.findall(r'%\([a-zA-Z0-9_]+\)[sdfluxXeEfFgG%]', text)
            for i, var in enumerate(django_vars):
                # Utiliser des mots anglais que Google Translate ne touchera JAMAIS
                token = f'DJANGOVAR{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)  # Remplacer seulement la première occurrence
            
            # 2. Anciens formats %s, %d, %f
            old_formats = re.findall(r'%[sdfluxXeEfFgG%]', masked)  # Sur le texte déjà masqué
            for i, var in enumerate(old_formats):
                token = f'OLDFORMAT{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
            
            # 3. Formats positionnels %1$s, %2$d
            pos_formats = re.findall(r'%\d+\$[sdfluxXeEfFgG]', masked)
            for i, var in enumerate(pos_formats):
                token = f'POSFORMAT{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
            
            # 4. Variables simples {var}
            simple_vars = re.findall(r'{\s*[a-zA-Z0-9_\.]+\s*}', masked)
            for i, var in enumerate(simple_vars):
                token = f'SIMPLEVAR{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
                
        elif file_type == 'json':
            # 1. Variables i18next {{var, format, param}} (les plus complexes d'abord)
            param_vars = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*,\s*[a-zA-Z0-9_]+\s*,\s*[^}]+\s*}}', text)
            for i, var in enumerate(param_vars):
                token = f'I18NEXTPARAM{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
            
            # 2. Variables i18next {{var, format}}
            formatted_vars = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*,\s*[a-zA-Z0-9_]+\s*}}', masked)
            for i, var in enumerate(formatted_vars):
                token = f'I18NEXTFORMAT{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
            
            # 3. Variables i18next simples {{var}}
            i18next_vars = re.findall(r'{{\s*[a-zA-Z0-9_\.]+\s*}}', masked)
            for i, var in enumerate(i18next_vars):
                token = f'I18NEXTVAR{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
            
            # 4. Variables simples {var}
            simple_vars = re.findall(r'{\s*[a-zA-Z0-9_\.]+\s*}', masked)
            for i, var in enumerate(simple_vars):
                token = f'JSONVAR{i:03d}PLACEHOLDER'
                mapping[token] = var
                masked = masked.replace(var, token, 1)
        
        # 5. Balises HTML (tous types de fichiers)
        html_tags = re.findall(r'<[^>]+>', masked)
        for i, tag in enumerate(html_tags):
            token = f'HTMLTAG{i:03d}PLACEHOLDER'
            mapping[token] = tag
            masked = masked.replace(tag, token, 1)
        
        # 6. Noms propres de la whitelist
        for i, word in enumerate(self.WHITELIST):
            if word in masked:
                token = f'WHITELIST{i:03d}PLACEHOLDER'
                if token not in mapping:  # Éviter les doublons
                    mapping[token] = word
                    # Remplacer mot entier seulement (avec word boundaries)
                    masked = re.sub(r'\b' + re.escape(word) + r'\b', token, masked)
        
        return masked, mapping


    def _unmask_variables(self, text, mapping):
        """
        Remplace les jetons par les variables d'origine.
        """
        for token, var in mapping.items():
            text = text.replace(token, var)
        return text

    def translate_text(self, text, target_language, source_language='auto', file_type=None):
        """
        Traduit un texte vers la langue cible avec retry en cas d'erreur
        file_type: 'po' ou 'json' pour appliquer le contrôle d'intégrité et le masquage
        """
        logger.info(f"Traduction: '{text[:50]}...' vers {target_language} (source: {source_language})")
        if not text or not text.strip():
            logger.warning("Texte vide fourni pour traduction")
            return {
                'text': '',
                'confidence': 0.0,
                'error': 'Texte vide'
            }
        # Masquage des variables dynamiques
        masked_text, mapping = self._mask_variables(text, file_type)
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    delay = self.retry_delay + random.uniform(0, 1)
                    logger.info(f"Tentative {attempt + 1}/{self.max_retries} après {delay:.1f}s de délai")
                    time.sleep(delay)
                result = self.translator.translate(
                    masked_text, 
                    dest=target_language, 
                    src=source_language
                )
                logger.info(f"Résultat brut de Google Translate (tentative {attempt + 1}): {result}")
                if result is None:
                    logger.warning(f"Google Translate a retourné None (tentative {attempt + 1})")
                    if attempt == self.max_retries - 1:
                        return {
                            'text': text,  # Retourner le texte original comme fallback
                            'confidence': 0.0,
                            'error': 'Résultat de traduction None après tous les essais - texte original conservé'
                        }
                    continue
                if not hasattr(result, 'text') or not result.text:
                    logger.warning(f"Google Translate n'a pas retourné de texte traduit (tentative {attempt + 1})")
                    if attempt == self.max_retries - 1:
                        return {
                            'text': text,  # Retourner le texte original comme fallback
                            'confidence': 0.0,
                            'error': 'Texte traduit manquant après tous les essais - texte original conservé'
                        }
                    continue
                if not result.text.strip():
                    logger.warning(f"Google Translate a retourné un texte vide (tentative {attempt + 1})")
                    if attempt == self.max_retries - 1:
                        return {
                            'text': text,  # Retourner le texte original comme fallback
                            'confidence': 0.0,
                            'error': 'Texte traduit vide après tous les essais - texte original conservé'
                        }
                    continue
                confidence = getattr(result, 'confidence', 0.0)
                detected_lang = getattr(result, 'src', source_language)
                # Démasquage des variables dynamiques
                unmasked_text = self._unmask_variables(result.text, mapping)
                # === Contrôle d'intégrité ===
                integrity_ok, integrity_msg = True, ''
                if file_type == 'po':
                    integrity_ok, integrity_msg = self._check_po_integrity(text, unmasked_text)
                elif file_type == 'json':
                    integrity_ok, integrity_msg = self._check_json_integrity(text, unmasked_text)
                if not integrity_ok:
                    logger.warning(f"Contrôle d'intégrité échoué: {integrity_msg}")
                    return {
                        'text': text,  # On conserve le texte original
                        'confidence': 0.0,
                        'error': f'Contrôle d\'intégrité échoué: {integrity_msg} - texte original conservé'
                    }
                logger.info(f"Traduction réussie (tentative {attempt + 1}): '{unmasked_text[:50]}...' (confiance: {confidence})")
                return {
                    'text': unmasked_text,
                    'confidence': confidence,
                    'detected_language': detected_lang,
                    'error': None
                }
            except TypeError as e:
                if "'NoneType' object is not iterable" in str(e):
                    logger.error(f"Erreur googletrans connue (tentative {attempt + 1}): '{text[:50]}...'")
                    if attempt == self.max_retries - 1:
                        return {
                            'text': text,
                            'confidence': 0.0,
                            'error': 'Erreur googletrans après tous les essais - texte original conservé'
                        }
                    continue
                else:
                    raise e
            except Exception as e:
                logger.error(f"Erreur lors de la traduction (tentative {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    return {
                        'text': text,
                        'confidence': 0.0,
                        'error': f'Erreur de traduction après tous les essais: {str(e)} - texte original conservé'
                    }
                continue
        return {
            'text': text,
            'confidence': 0.0,
            'error': 'Échec de toutes les tentatives de traduction - texte original conservé'
        }
    
    def get_supported_languages(self):
        """Retourne la liste des langues supportées par Google Translate"""
        supported_languages = {
            'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic',
            'hy': 'Armenian', 'az': 'Azerbaijani', 'eu': 'Basque', 'be': 'Belarusian',
            'bn': 'Bengali', 'bs': 'Bosnian', 'bg': 'Bulgarian', 'ca': 'Catalan',
            'ceb': 'Cebuano', 'zh': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)',
            'co': 'Corsican', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish',
            'nl': 'Dutch', 'en': 'English', 'eo': 'Esperanto', 'et': 'Estonian',
            'fi': 'Finnish', 'fr': 'French', 'fy': 'Frisian', 'gl': 'Galician',
            'ka': 'Georgian', 'de': 'German', 'el': 'Greek', 'gu': 'Gujarati',
            'ht': 'Haitian Creole', 'ha': 'Hausa', 'haw': 'Hawaiian', 'he': 'Hebrew',
            'hi': 'Hindi', 'hmn': 'Hmong', 'hu': 'Hungarian', 'is': 'Icelandic',
            'ig': 'Igbo', 'id': 'Indonesian', 'ga': 'Irish', 'it': 'Italian',
            'ja': 'Japanese', 'jv': 'Javanese', 'kn': 'Kannada', 'kk': 'Kazakh',
            'km': 'Khmer', 'ko': 'Korean', 'ku': 'Kurdish', 'ky': 'Kyrgyz',
            'lo': 'Lao', 'la': 'Latin', 'lv': 'Latvian', 'lt': 'Lithuanian',
            'lb': 'Luxembourgish', 'mk': 'Macedonian', 'mg': 'Malagasy', 'ms': 'Malay',
            'ml': 'Malayalam', 'mt': 'Maltese', 'mi': 'Maori', 'mr': 'Marathi',
            'mn': 'Mongolian', 'my': 'Myanmar (Burmese)', 'ne': 'Nepali', 'no': 'Norwegian',
            'ny': 'Nyanja (Chichewa)', 'or': 'Odia (Oriya)', 'ps': 'Pashto', 'fa': 'Persian',
            'pl': 'Polish', 'pt': 'Portuguese', 'pa': 'Punjabi', 'ro': 'Romanian',
            'ru': 'Russian', 'sm': 'Samoan', 'gd': 'Scots Gaelic', 'sr': 'Serbian',
            'st': 'Sesotho', 'sn': 'Shona', 'sd': 'Sindhi', 'si': 'Sinhala (Sinhalese)',
            'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali', 'es': 'Spanish',
            'su': 'Sundanese', 'sw': 'Swahili', 'sv': 'Swedish', 'tg': 'Tajik',
            'ta': 'Tamil', 'tt': 'Tatar', 'te': 'Telugu', 'th': 'Thai',
            'tr': 'Turkish', 'tk': 'Turkmen', 'uk': 'Ukrainian', 'ur': 'Urdu',
            'ug': 'Uyghur', 'uz': 'Uzbek', 've': 'Venda', 'vi': 'Vietnamese',
            'cy': 'Welsh', 'xh': 'Xhosa', 'yi': 'Yiddish', 'yo': 'Yoruba', 'zu': 'Zulu'
        }
        return supported_languages
    
    def detect_language(self, text):
        """Détecte la langue d'un texte avec retry en cas d'erreur"""
        logger.info(f"Détection de langue pour: '{text[:50]}...'")
        
        if not text or not text.strip():
            logger.warning("Texte vide fourni pour détection de langue")
            return {
                'language': None,
                'confidence': 0.0,
                'error': 'Texte vide'
            }
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    delay = self.retry_delay + random.uniform(0, 1)
                    logger.info(f"Détection - tentative {attempt + 1}/{self.max_retries} après {delay:.1f}s de délai")
                    time.sleep(delay)
                
                result = self.translator.detect(text)
                
                logger.info(f"Résultat brut de détection (tentative {attempt + 1}): {result}")
                
                if result is None:
                    logger.warning(f"Google Translate a retourné None pour la détection (tentative {attempt + 1})")
                    if attempt == self.max_retries - 1:
                        return {
                            'language': None,
                            'confidence': 0.0,
                            'error': 'Résultat de détection None après tous les essais'
                        }
                    continue
                
                if not hasattr(result, 'lang') or not result.lang:
                    logger.warning(f"Google Translate n'a pas retourné de langue détectée (tentative {attempt + 1})")
                    if attempt == self.max_retries - 1:
                        return {
                            'language': None,
                            'confidence': 0.0,
                            'error': 'Langue détectée manquante après tous les essais'
                        }
                    continue
                
                confidence = getattr(result, 'confidence', 0.70)
                
                logger.info(f"Détection réussie (tentative {attempt + 1}): {result.lang} (confiance: {confidence})")
                
                return {
                    'language': result.lang,
                    'confidence': confidence,
                    'error': None
                }
                
            except TypeError as e:
                if "'NoneType' object is not iterable" in str(e):
                    logger.error(f"Erreur googletrans connue pour la détection (tentative {attempt + 1}): '{text[:50]}...'")
                    if attempt == self.max_retries - 1:
                        return {
                            'language': None,
                            'confidence': 0.0,
                            'error': 'Erreur googletrans après tous les essais'
                        }
                    continue
                else:
                    raise e
                    
            except Exception as e:
                logger.error(f"Erreur lors de la détection de langue (tentative {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    return {
                        'language': None,
                        'confidence': 0.0,
                        'error': f'Erreur de détection après tous les essais: {str(e)}'
                    }
                continue
        
        return {
            'language': None,
            'confidence': 0.0,
            'error': 'Échec de toutes les tentatives de détection'
        }

# Instance globale du service
google_translate_service = GoogleTranslateService()