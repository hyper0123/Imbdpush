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
EXTINF_LINE = re.compile(r'^#EXTINF:-1(.*),(.*)$')
YEAR_PATTERN = re.compile(r'\s+(\d{4})$')

# Función para extraer año y título

def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = YEAR_PATTERN.search(raw)
    if m:
        year = m.group(1)
        title = YEAR_PATTERN.sub('', raw).strip()
        return title, year
    return raw, ''

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

# Procesar playlist M3U

def process_m3u(path: str, verbose: bool = False) -> None:
    updated = False
    output_lines: list[str] = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                m = EXTINF_LINE.match(line.strip())
                if m:
                    attrs, raw_title = m.group(1), m.group(2)
                    orig_id_match = re.search(r'tvg-id="(.*?)"', attrs)
                    orig_logo_match = re.search(r'tvg-logo="(.*?)"', attrs)
                    orig_group_match = re.search(r'group-title="(.*?)"', attrs)

                    orig_id = orig_id_match.group(1) if orig_id_match else ''
                    orig_logo = orig_logo_match.group(1) if orig_logo_match else ''
                    orig_group = orig_group_match.group(1) if orig_group_match else ''

                    # Normalizar título y extraer año
                    title_no_year, year = normalize_and_extract_year(raw_title)
                    search_title = title_no_year
                    if verbose:
                        print(f"Procesando raw='{raw_title}', search='{search_title}', grupo original='{orig_group}'")

                    # Obtener datos de TMDb
                    data = fetch_movie_data(search_title)
                    if data:
                        poster = data['poster']
                        genre = data['genre'] or orig_group
                        title_en = data['title_en']
                        display = f"{title_no_year} ({year})" if year else title_no_year

                        # Determinar group-title final
                        if not orig_group or orig_group.lower() == 'undefined':
                            final_group = genre
                        else:
                            final_group = orig_group

                        attrs_new = (
                            f' tvg-name="{title_en}"'
                            f' tvg-id="{orig_id}"'
                            f' tvg-logo="{poster}"'
                            f' group-title="{final_group}"'
                        )
                        new_line = f"#EXTINF:-1{attrs_new},{display}\n"
                        output_lines.append(new_line)
                        if verbose:
                            print(f" -> Nueva línea: {new_line.strip()}")
                        updated = True
                        continue
            output_lines.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
    elif verbose:
        print("No hubo cambios.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose_flag)
