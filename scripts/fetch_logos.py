import os
import re
import sys
from tmdbv3api import TMDb, Movie

# --- Configuración TMDb ---
tmdb = TMDb()
api_key = os.getenv('TMDB_API_KEY')
if not api_key:
    print("ERROR: la variable TMDB_API_KEY no está definida")
    sys.exit(1)
tmdb.api_key = api_key

movie_api = Movie()

# --- Patrones de texto ---
LOGO_PATTERN = re.compile(r'tvg-logo=".*?"')
EXTINF_PATTERN = re.compile(r'^(#EXTINF:-1)(.*),(.*)$')
YEAR_PATTERN = re.compile(r'\s+(\d{4})$')

def normalize_title(raw_title: str) -> (str, str):
    """
    Separa el título puro y el año (si está al final).
    Ej: "Zootopia 2010" -> ("Zootopia", "2010")
    """
    m = YEAR_PATTERN.search(raw_title)
    if m:
        year = m.group(1)
        title = raw_title[:m.start()].strip()
    else:
        title = raw_title.strip()
        year = ''
    return title, year

def get_movie_info(title: str) -> dict | None:
    """
    Busca la primera coincidencia de 'title' en TMDb,
    devuelve dict con:
      - id: TMDb ID
      - title_en: título original en inglés
      - title_es: título en español (o inglés si no hay)
      - genre_es: primer género en español (o 'Undefined')
    """
    # búsqueda en inglés para asegurar coincidencia
    tmdb.language = 'en-US'
    results = movie_api.search(title)
    if not results:
        return None
    m = results[0]
    movie_id = m.id

    # Detalles en inglés
    details_en = movie_api.details(movie_id)
    title_en = details_en.title or title

    # Detalles en español (títulos y géneros)
    tmdb.language = 'es-ES'
    details_es = movie_api.details(movie_id)
    title_es = details_es.title or title_en
    genres = details_es.genres or []
    genre_es = genres[0]['name'] if genres else 'Undefined'

    return {
        'id': movie_id,
        'title_en': title_en,
        'title_es': title_es,
        'genre_es': genre_es
    }

def fetch_logo_url(search_title: str) -> str | None:
    """
    Busca póster en TMDb usando 'search_title' (en español).
    """
    tmdb.language = 'es-ES'
    try:
        results = movie_api.search(search_title)
        if results and results[0].poster_path:
            return f"https://image.tmdb.org/t/p/w500{results[0].poster_path}"
    except Exception as e:
        print(f"Error al buscar logo '{search_title}': {e}")
    return None

def process_m3u(path: str, verbose: bool = False):
    updated = False
    lines = open(path, 'r', encoding='utf-8').read().splitlines()
    out = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF'):
            m = EXTINF_PATTERN.match(line)
            if m:
                prefix, attrs, raw_title = m.groups()
                # extraer campos existentes
                # attrs puede contener tvg-name, tvg-id, tvg-logo, group-title
                # vamos a regenerar attrs completo
                pure_title, year = normalize_title(raw_title)
                info = get_movie_info(pure_title)
                if info:
                    # construir nuevos campos
                    tvg_name = info['title_en']
                    tvg_id = info['id']
                    # título para búsqueda en fetch_logo
                    search_title_es = info['title_es']
                    new_logo = fetch_logo_url(search_title_es) or ''
                    genre = info['genre_es']
                    # título display: español + (año)
                    display_title = f"{info['title_es']}" + (f" ({year})" if year else "")
                    # reconstruir línea EXTINF
                    new_attrs = (
                        f' tvg-name="{tvg_name}"'
                        f' tvg-id="{tvg_id}"'
                        f' tvg-logo="{new_logo}"'
                        f' group-title="{genre}"'
                    )
                    new_line = f"{prefix}{new_attrs},{display_title}"
                    if verbose:
                        print(f"[{pure_title}] → {new_line}")
                    line = new_line
                    updated = True
        out.append(line)
        # la línea URL debe conservarse
        if line.startswith('#EXTINF'):
            i += 1
            if i < len(lines):
                out.append(lines[i])
        i += 1

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(out) + "\n")
    elif verbose:
        print("No se encontraron cambios para aplicar.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose_flag)
