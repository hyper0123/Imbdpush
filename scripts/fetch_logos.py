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
extinf_pattern = re.compile(r"^(#EXTINF:[^,]*,)(.*)")
logo_pattern = re.compile(r'tvg-logo="(.*?)"')
group_pattern = re.compile(r'group-title=".*?"')
tvg_name_pattern = re.compile(r'tvg-name=".*?"')

# Función para extraer título y año raw
def normalize_title(raw):
    """
    Separa el título y el año de `raw`:
    'Zootopia 2016' -> ('Zootopia', '2016')
    """
    m = year_pattern.search(raw)
    if m:
        title = raw[:m.start()].strip()
        year = m.group(1)
    else:
        title = raw.strip()
        year = ''
    return title, year

# Función para traducir título vía Wikipedia ES
def fetch_spanish_wiki_title(eng_title):
    url = "https://es.wikipedia.org/w/api.php"
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': eng_title,
        'format': 'json',
        'srlimit': 1
    }
    try:
        resp = requests.get(url, params=params, timeout=5).json()
        hits = resp.get('query', {}).get('search', [])
        if hits:
            return hits[0]['title']
    except Exception:
        pass
    return None

# Función para obtener datos TMDb
def fetch_tmdb_info(title):
    results = Movie().search(title)
    if not results:
        return None
    m = results[0]
    try:
        details = Movie().details(m.id)
    except Exception:
        details = None

    genre = ''
    if details and getattr(details, 'genres', None):
        genre = details.genres[0]['name']
    logo = f"https://image.tmdb.org/t/p/w500{m.poster_path}" if m.poster_path else ''
    return {'genre': genre, 'logo': logo}

# Procesar M3U
def process_m3u(path, verbose=False):
    output = []
    updated = False

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                extinf_match = extinf_pattern.match(line)
                if not extinf_match:
                    output.append(line)
                    continue
                extinf_prefix, raw = extinf_match.groups()
                title_raw = raw.strip()

                logo_match = logo_pattern.search(line)
                orig_logo = logo_match.group(1) if logo_match else None

                if verbose:
                    print(f"Procesando: raw_title='{title_raw}', orig_logo='{orig_logo}'")

                if not orig_logo:
                    eng_name, year = normalize_title(title_raw)
                    info = fetch_tmdb_info(eng_name)
                    if not info:
                        output.append(line)
                        continue

                    es_title = fetch_spanish_wiki_title(eng_name)
                    if es_title:
                        final_title = f"{es_title} ({year})" if year else es_title
                    else:
                        final_title = f"{eng_name} ({year})" if year else eng_name

                    group = info['genre'] or 'undefined'
                    logo_attr = f'tvg-logo="{info["logo"]}"'

                    # Reconstruir línea
                    line = line.replace('tvg-name=""', f'tvg-name="{eng_name}"')
                    line = re.sub(logo_pattern, logo_attr, line)
                    line = re.sub(group_pattern, f'group-title="{group}"', line)

                    prefix = line.split(',', 1)[0]
                    line = f"{prefix},{final_title}\n"

                    if verbose:
                        print(f" -> tvg-name='{eng_name}', group='{group}', final_title='{final_title}'")
                    updated = True
            output.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(output)
    elif verbose:
        print("No changes.")

# Entrada principal
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    process_m3u(sys.argv[1], verbose='--verbose' in sys.argv)
