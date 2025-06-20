import sqlite3
import re

DB_PATH = '../db.sqlite3'  # Adapter le chemin si besoin

# Règles d'intégrité pour .po
PO_VAR_PATTERN = re.compile(r'%\(([a-zA-Z0-9_]+)\)s')
PO_OLD_FMT = ['%d', '%s', '%f']
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
SPECIAL_CHARS = ['…', '–', '©', '®', '\n', '\t']

# Règles d'intégrité pour .json
JSON_VAR_PATTERN = re.compile(r'{{\s*([a-zA-Z0-9_]+)\s*}}')


def check_po_integrity(source, translated):
    errors = []
    # Variables dynamiques
    for var in PO_VAR_PATTERN.findall(source):
        if f'%({var})s' not in translated:
            errors.append(f"Variable %({var})s manquante ou modifiée")
    # Anciens formats
    for fmt in PO_OLD_FMT:
        if fmt in source and fmt not in translated:
            errors.append(f"Format {fmt} manquant")
    # Balises HTML
    for tag in HTML_TAG_PATTERN.findall(source):
        if tag not in translated:
            errors.append(f"Balise {tag} manquante")
    # Caractères spéciaux
    for char in SPECIAL_CHARS:
        if char in source and char not in translated:
            errors.append(f"Caractère spécial '{char}' manquant")
    return errors

def check_json_integrity(source, translated):
    errors = []
    for var in JSON_VAR_PATTERN.findall(source):
        if f'{{{{{var}}}}}' not in translated:
            errors.append(f"Variable {{{{{var}}}}} manquante ou modifiée")
    for tag in HTML_TAG_PATTERN.findall(source):
        if tag not in translated:
            errors.append(f"Balise {tag} manquante")
    for char in SPECIAL_CHARS:
        if char in source and char not in translated:
            errors.append(f"Caractère spécial '{char}' manquant")
    return errors

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT source_text, (SELECT translated_text FROM translations_translation WHERE translations_translation.string_id=files_translationstring.id LIMIT 1) as translated
        FROM files_translationstring LIMIT 50;
    """)
    rows = cur.fetchall()
    print("\nVérification d'intégrité sur les 50 premiers couples source/traduction:\n")
    for idx, (source, translated) in enumerate(rows, 1):
        if not source or not translated:
            continue
        # Heuristique simple : .po si %(var)s, .json si {{var}}
        if '%(' in source:
            errors = check_po_integrity(source, translated)
            typ = '.po'
        elif '{{' in source:
            errors = check_json_integrity(source, translated)
            typ = '.json'
        else:
            errors = []
            typ = 'autre'
        if errors:
            print(f"[{idx}] Problème détecté ({typ}):\n  Source: {source}\n  Traduction: {translated}\n  Erreurs: {errors}\n")
    print("Vérification terminée.")

if __name__ == '__main__':
    main() 