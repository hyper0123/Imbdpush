import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb
env_api_key = os.getenv('TMDB_API_KEY')
if not env_api_key:
    print("ERROR: la variable TMDB_API_KEY no está definida")
    sys.exit(1)

tmdb = TMDb()
tmdb.api_key = env_api_key

# Patrones para parsing
extinf_pattern = re.compile(r'^#EXTINF:-1(.*),(.*)$')
year_pattern = re.compile(r'\s+(\d{4})$')

# Funciones auxiliares
def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = year_pattern.search(raw)
    if m:
        year = m.group(1)
        title = year_pattern.sub('', raw).strip()
        return title, year
    return raw, ''

def base_title(title_no_year: str) -> str:
    """Extrae título base eliminando números secuela al final"""
    return re.sub(r'\s+\d+$', '', title_no_year)

# Obtener datos de TMDb
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        tmdb.language = 'en-US'
        results = Movie().search(search_title)
        if not results:
            return None
        movie = results[0]
        poster_url = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
        title_en = movie.original_title or movie.title

        tmdb.language = 'es-ES'
        details = Movie().details(movie.id)
        genres = getattr(details, 'genres', []) or []
        genre_name = genres[0]['name'] if genres else ''

        return {'poster': poster_url, 'genre': genre_name, 'title_en': title_en}
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None

# Proceso principal de M3U con ordenamiento
def process_m3u(path: str, verbose: bool = False) -> None:
    # Leer todas las líneas
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Mantener cabecera hasta primera EXTINF
    header = []
    idx = 0
    while idx < len(lines) and not lines[idx].startswith('#EXTINF'):
        header.append(lines[idx])
        idx += 1

    # Parsear entradas en pares: extinf y URL
    entries = []
    while idx < len(lines):
        if lines[idx].startswith('#EXTINF'):
            ext_line = lines[idx].strip()
            url_line = lines[idx+1] if idx+1 < len(lines) else ''
            entries.append((ext_line, url_line))
            idx += 2
        else:
            # líneas sueltas
            header.append(lines[idx])
            idx += 1

    processed = []
    # Procesar cada entrada
    for ext_line, url_line in entries:
        m = extinf_pattern.match(ext_line)
        if not m:
            continue
        attrs, raw_title = m.group(1), m.group(2)
        # Extraer atributos
        orig_id = re.search(r'tvg-id="(.*?)"', attrs)
        orig_group = re.search(r'group-title="(.*?)"', attrs)
        orig_logo = re.search(r'tvg-logo="(.*?)"', attrs)
        orig_id = orig_id.group(1) if orig_id else ''
        orig_group = orig_group.group(1) if orig_group else ''
        orig_logo = orig_logo.group(1) if orig_logo else ''

        # Normalizar título y extraer año
        title_no_year, year = normalize_and_extract_year(raw_title)
        search_title = title_no_year
        # Fetch datos
        data = fetch_movie_data(search_title)
        if data:
            poster = data['poster']
            genre = data['genre'] or orig_group
            title_en = data['title_en']
        else:
            poster = orig_logo
            genre = orig_group
            title_en = title_no_year

        # Preparar display y attrs_new
        display = f"{title_no_year} ({year})" if year else title_no_year
        final_group = genre if not orig_group or orig_group.lower()=='undefined' else orig_group
        attrs_new = (
            f' tvg-name="{title_en}"'
            f' tvg-id="{orig_id}"'
            f' tvg-logo="{poster}"'
            f' group-title="{final_group}"'
        )
        new_ext = f"#EXTINF:-1{attrs_new},{display}"
        processed.append({'base': base_title(title_no_year), 'year': int(year) if year.isdigit() else 0,
                          'ext': new_ext, 'url': url_line.strip()})

    # Ordenar: por base title, luego año asc
    processed.sort(key=lambda x: (x['base'].lower(), x['year']))

    # Escribir de nuevo
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(header)
        f.write('#EXTM3U\n' if '#EXTM3U' not in ''.join(header) else '')
        for item in processed:
            f.write(item['ext'] + '\n')
            f.write(item['url'] + '\n')

if __name__ == '__main__':
    if len(sys.argv)<2:
        print("Uso: python fetch_logos.py <playlist.m3u> [--verbose]")
        sys.exit(1)
    process_m3u(sys.argv[1], verbose='--verbose' in sys.argv)
