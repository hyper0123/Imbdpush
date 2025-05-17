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
        # Quita sufijo numérico (p.ej. '2', '3') al final
        return re.sub(r'\s*\d+$', '', title).strip()

    # Agrupar por base name
    groups: dict[str, list] = {}
    for e in entries:
        bn = base_name(e[2])  # title_no_year is at index 2
        groups.setdefault(bn, []).append(e)

    # Construir resultado ordenado\    sorted_entries: list[tuple] = []
    for bn, group in groups.items():
        if len(group) > 1:
            # Ordenar por año ascendente
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

# Función principal de procesamiento
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
                orig_id = re.search(r'tvg-id="(.*?)"', attrs)
                orig_logo = re.search(r'tvg-logo="(.*?)"', attrs)
                orig_group = re.search(r'group-title="(.*?)"', attrs)
                id_val = orig_id.group(1) if orig_id else ''
                logo_val = orig_logo.group(1) if orig_logo else ''
                group_val = orig_group.group(1) if orig_group else ''

                # Obtener título y año
                title_no_year, year = normalize_and_extract_year(raw_title)
                search_title = title_no_year
                if verbose:
                    print(f"Procesando raw='{raw_title}', search='{search_title}', grupo original='{group_val}'")

                data = fetch_movie_data(search_title)
                if data:
                    poster = data['poster']
                    genre = data['genre'] or group_val
                    title_en = data['title_en']
                    display = f"{title_no_year} ({year})" if year else title_no_year

                    # Determinar group-title final
                    final_group = genre if not group_val or group_val.lower() == 'undefined' else group_val

                    # Construir nueva línea EXTINF
                    attrs_new = (
                        f' tvg-name="{title_en}"'
                        f' tvg-id="{id_val}"'
                        f' tvg-logo="{poster}"'
                        f' group-title="{final_group}"'
                    )
                    extinf_line = f"#EXTINF:-1{attrs_new},{display}\n"
                    entries.append((extinf_line, url_line, title_no_year, year))
                    i += 2
                    continue
        # Si no es entrada válida, conservar en header
        header_lines.append(line)
        i += 1

    # Ordenar entradas que comparten nombre base
    entries = sort_same_name(entries)

    # Escribir archivo de nuevo\    with open(path, 'w', encoding='utf-8') as f:
        for hl in header_lines:
            f.write(hl)
        for extinf, url, *_ in entries:
            f.write(extinf)
            f.write(url)

def main():
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=verbose_flag)

if __name__ == '__main__':
    main()
