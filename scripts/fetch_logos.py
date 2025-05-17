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

# Función para extraer título y año raw def normalize_title(raw):
    m = year_pattern.search(raw)
    if m:
        title = raw[:m.start()].strip()
        year = m.group(1)
    else:
        title, year = raw.strip(), ''
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
    # Buscar en TMDb (inglés)
    results = Movie().search(title)
    if not results:
        return None
    m = results[0]
    details = Movie().details(m.id)
    # género
    genre = details.genres[0]['name'] if details.genres else ''
    # logo
    logo = f"https://image.tmdb.org/t/p/w500{m.poster_path}" if m.poster_path else ''
    return {'genre': genre, 'logo': logo}

# Procesar M3U
def process_m3u(path, verbose=False):
    output = []
    updated = False
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                # separar extinf y raw title
                extinf, raw = extinf_pattern.match(line).groups()
                title_raw = raw.strip()
                # extraer tvg-logo actual
                orig_logo = logo_pattern.search(line).group(1)
                # continuar solo si no hay logo
                if not orig_logo:
                    # normalizar title y año
                    eng_name, year = normalize_title(title_raw)
                    # info tmdb
                    info = fetch_tmdb_info(eng_name)
                    if not info:
                        output.append(line)
                        continue
                    # traducción wiki
                    es_title = fetch_spanish_wiki_title(eng_name)
                    final_title = f"{es_title} ({year})" if es_title and year else (f"{es_title}" if es_title else (f"{eng_name} ({year})" if year else eng_name))
                    # preparar campos
                    group = info['genre'] or 'undefined'
                    logo_attr = f'tvg-logo="{info["logo"]}"'
                    # reconstruir línea
                    new = extinf
                    new += f',"'  # dummy to align patterns
                    # reemplazar atributos
                    new = re.sub(tvg_name_pattern, f'tvg-name="{eng_name}"', line)
                    new = re.sub(logo_pattern, logo_attr, new)
                    new = re.sub(group_pattern, f'group-title="{group}"', new)
                    # reemplazar texto tras coma
                    prefix = new.split(',', 1)[0]
                    new_line = f"{prefix},{final_title}\n"
                    output.append(new_line)
                    updated = True
                else:
                    output.append(line)
            else:
                output.append(line)
    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(output)
    elif verbose:
        print("No changes.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <playlist.m3u> [--verbose]")
        sys.exit(1)
    process_m3u(sys.argv[1], verbose='--verbose' in sys.argv)
