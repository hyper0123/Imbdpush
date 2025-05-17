import os
import re
import sys
import requests
from tmdbv3api import TMDb, Movie

# Inicializar TMDb con API Key v3

tmdb = TMDb()
api_key = os.getenv('TMDB_API_KEY')
if not api_key:
    print("ERROR: TMDB_API_KEY no definida")
    sys.exit(1)

tmdb.api_key = api_key

# Patrones
year_pattern = re.compile(r"\s+(\d{4})$")
extinf_pattern = re.compile(r"^#EXTINF:[^,]*,(.*)")

# Función para extraer título y año raw
def normalize_title(raw):
    m = year_pattern.search(raw)
    if m:
        return raw[:m.start()].strip(), m.group(1)
    return raw.strip(), ''

# Función para obtener título en Español (Wikipedia langlinks)
def fetch_spanish_wiki_title(eng_title):
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        'action': 'query',
        'titles': eng_title,
        'prop': 'langlinks',
        'lllang': 'es',
        'format': 'json'
    }
    try:
        resp = requests.get(url, params=params, timeout=5).json()
        pages = resp.get('query', {}).get('pages', {})
        for page in pages.values():
            langlinks = page.get('langlinks')
            if langlinks:
                return langlinks[0]['*']
    except Exception:
        pass
    return None

# Función para obtener datos TMDb (género en español y logo)
def fetch_tmdb_info(title):
    search = Movie()
    results = search.search(title)
    if not results:
        return None
    m = results[0]
    # Detalles en español para género localizado
    try:
        details_es = Movie().details(m.id, language='es')
        genre = details_es.genres[0]['name'] if details_es.genres else ''
    except Exception:
        genre = ''
    logo_url = f"https://image.tmdb.org/t/p/w500{m.poster_path}" if getattr(m, 'poster_path', None) else ''
    return {'genre': genre or 'undefined', 'logo': logo_url}

# Procesar M3U
def process_m3u(path: str, verbose: bool = False):
    lines_out = []
    updated = False
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                # Extraer título raw tras la coma
                raw_title = extinf_pattern.match(line).group(1).strip()
                eng_name, year = normalize_title(raw_title)
                if verbose:
                    print(f"Original: '{raw_title}' -> Eng: '{eng_name}', Year: '{year}'")

                # Obtener info
                info = fetch_tmdb_info(eng_name)
                if not info:
                    lines_out.append(line)
                    continue

                # Traducir nombre
                es_title = fetch_spanish_wiki_title(eng_name)
                if es_title:
                    final_title = f"{es_title} ({year})" if year else es_title
                else:
                    final_title = f"{eng_name} ({year})" if year else eng_name

                # Construir línea EXTINF completa
                logo_attr  = info['logo']
                group_attr = info['genre']
                new_line = (f"#EXTINF:-1 tvg-name=\"{eng_name}\" tvg-id=\"\" "
                            f"tvg-logo=\"{logo_attr}\" group-title=\"{group_attr}\","  
                            f"{final_title}\n")
                lines_out.append(new_line)
                if verbose:
                    print(f" -> {new_line.strip()}")
                updated = True
            else:
                lines_out.append(line)
    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines_out)
        if verbose:
            print("Archivo actualizado con nuevos datos.")
    elif verbose:
        print("No se realizaron cambios.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    process_m3u(sys.argv[1], verbose='--verbose' in sys.argv)

