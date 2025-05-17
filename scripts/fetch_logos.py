import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb
api_key = os.getenv('TMDB_API_KEY')
if not api_key:
    print("ERROR: la variable TMDB_API_KEY no está definida")
    sys.exit(1)

tmdb = TMDb()
tmdb.api_key = api_key

# Patrones para parsing
EXTINF_LINE = re.compile(r'^#EXTINF:-1(.*),(.*)$')
YEAR_PATTERN = re.compile(r'\s+(\d{4})$')


def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    """
    Separa el título del año si existe al final (4 dígitos).
    Devuelve (título_sin_año, año) o (raw, '').
    """
    m = YEAR_PATTERN.search(raw)
    if m:
        year = m.group(1)
        title = YEAR_PATTERN.sub('', raw).strip()
        return title, year
    return raw, ''


def fetch_movie_data(search_title: str):
    """Busca película en TMDb, devuelve dict con poster URL, primer género (es), título original."""
    try:
        results = Movie().search(search_title)
        if not results:
            return None
        movie = results[0]
        # Datos básicos
        movie_id = movie.id
        poster_path = movie.poster_path
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ''
        title_en = getattr(movie, 'original_title', movie.title)
        # Obtener géneros en español
        details_es = Movie().details(movie_id, language='es-ES')
        genres = getattr(details_es, 'genres', []) or []
        genre_name = genres[0]['name'] if genres else ''
        return {
            'poster': poster_url,
            'genre': genre_name,
            'title_en': title_en
        }
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None


def process_m3u(path: str, verbose: bool = False) -> None:
    updated = False
    lines_out = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                m = EXTINF_LINE.match(line.strip())
                if m:
                    attrs, raw_title = m.group(1), m.group(2)
                    # Extraer id, logo del bloque attrs
                    id_match = re.search(r'tvg-id="(.*?)"', attrs)
                    logo_match = re.search(r'tvg-logo="(.*?)"', attrs)
                    orig_id = id_match.group(1) if id_match else ''
                    raw_logo = logo_match.group(1) if logo_match else ''

                    # Normalizar título y año
                    title_no_year, year = normalize_and_extract_year(raw_title)
                    search_title = title_no_year
                    if verbose:
                        print(f"Buscando: raw='{raw_title}', search='{search_title}'")

                    # Obtener datos TMDb
                    data = fetch_movie_data(search_title)
                    if data:
                        new_logo = data['poster']
                        genre = data['genre']
                        title_en = data['title_en']
                        # Construir nueva línea EXTINF
                        display = f"{title_no_year} ({year})" if year else title_no_year
                        attrs_new = (
                            f' tvg-name="{title_en}"'
                            f' tvg-id="{orig_id}"'
                            f' tvg-logo="{new_logo}"'
                            f' group-title="{genre}"'
                        )
                        new_line = f"#EXTINF:-1{attrs_new},{display}\n"
                        lines_out.append(new_line)
                        if verbose:
                            print(f" -> Nueva línea: {new_line.strip()}")
                        updated = True
                        continue  # skip original line
            lines_out.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines_out)
    elif verbose:
        print("No hubo cambios.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose_flag)
