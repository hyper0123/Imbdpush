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

# Función para extraer título sin año y año
def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = YEAR_PATTERN.search(raw)
    if m:
        year = m.group(1)
        title = YEAR_PATTERN.sub('', raw).strip()
        return title, year
    return raw, ''

# Función para ordenar entradas con mismo base name
def sort_same_name(entries: list[tuple]) -> list[tuple]:
    """
    Ordena grupos de películas con mismo base name por año ascendente.
    entries: lista de tuplas (extinf_line, url_line, title_no_year, year)
    """
    def base_name(title: str) -> str:
        return re.sub(r'\s*\d+$', '', title).strip()

    groups: dict[str, list] = {}
    for e in entries:
        bn = base_name(e[2])
        groups.setdefault(bn, []).append(e)

    sorted_entries: list[tuple] = []
    for _, group in groups.items():
        if len(group) > 1:
            sorted_group = sorted(group, key=lambda x: int(x[3] or 0))
            sorted_entries.extend(sorted_group)
        else:
            sorted_entries.extend(group)
    return sorted_entries

# Función para obtener datos de TMDb
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

# Función principal
def process_m3u(path: str, verbose: bool = False) -> None:
    # Leer líneas del archivo
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    header_lines: list[str] = []
    entries: list[tuple] = []  # (extinf_line, url_line, title_no_year, year)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF') and i + 1 < len(lines):
            m = EXTINF_LINE.match(line.strip())
            if m:
                attrs, raw_title = m.group(1), m.group(2)
                url_line = lines[i + 1]

                # Extraer atributos originales
                id_match = re.search(r'tvg-id="(.*?)"', attrs)
                logo_match = re.search(r'tvg-logo="(.*?)"', attrs)
                group_match = re.search(r'group-title="(.*?)"', attrs)
                orig_id = id_match.group(1) if id_match else ''
                orig_group = group_match.group(1) if group_match else ''

                # Normalizar y extraer año
                title_no_year, year = normalize_and_extract_year(raw_title)
                search_title = title_no_year
                if verbose:
                    print(f"Procesando raw='{raw_title}', search='{search_title}', grupo original='{orig_group}'")

                data = fetch_movie_data(search_title)
                if data:
                    poster = data['poster']
                    genre = data['genre'] or orig_group
                    title_en = data['title_en']
                    display = f"{title_no_year} ({year})" if year else title_no_year

                    # Determinar group-title final
                    final_group = genre if not orig_group or orig_group.lower() == 'undefined' else orig_group

                    # Construir nueva línea EXTINF
                    attrs_new = (
                        f' tvg-name="{title_en}"'
                        f' tvg-id="{orig_id}"'
                        f' tvg-logo="{poster}"'
                        f' group-title="{final_group}"'
                    )
                    extinf_line = f"#EXTINF:-1{attrs_new},{display}\n"
                    entries.append((extinf_line, url_line, title_no_year, year))
                    i += 2
                    continue
        # Si no es EXTINF
        header_lines.append(line)
        i += 1

    # Ordenar entradas con mismo nombre base
    entries = sort_same_name(entries)

    # Escribir de nuevo
    with open(path, 'w', encoding='utf-8') as f:
        for hl in header_lines:
            f.write(hl)
        for extinf, url_line, *_ in entries:
            f.write(extinf)
            f.write(url_line)

# Entry point
def main():
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=verbose_flag)

if __name__ == '__main__':
    main()
