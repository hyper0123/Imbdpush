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

# Normalizar y extraer año del título raw
def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = YEAR_PATTERN.search(raw)
    if m:
        title = YEAR_PATTERN.sub('', raw).strip()
        return title, m.group(1)
    return raw, ''

# Ordenar sagas y otros
def sort_same_name(entries: list[tuple]) -> list[tuple]:
    def base_name(title: str) -> str:
        return re.sub(r'\s*\d+$', '', title).strip().lower()

    groups: dict[str, list] = {}
    for e in entries:
        bn = base_name(e[2])
        groups.setdefault(bn, []).append(e)

    saga_entries, other_entries = [], []
    for group in groups.values():
        if len(group) > 1:
            saga_entries.extend(sorted(group, key=lambda x: x[4]))
        else:
            other_entries.extend(group)
    other_entries.sort(key=lambda x: (x[2].lower(), x[4]))
    return saga_entries + other_entries

# Obtener datos de TMDb con corrección de año
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        # Obtener título original en inglés
        tmdb.language = 'en-US'
        results = Movie().search(search_title)
        if not results:
            return None
        movie = results[0]
        poster = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
        title_en = movie.original_title or movie.title

        # Obtener género y fecha en español
        tmdb.language = 'es-ES'
        details = Movie().details(movie.id)
        genres = getattr(details, 'genres', []) or []
        genre = genres[0]['name'] if genres else ''
        rd = getattr(details, 'release_date', '')
        real_year = rd.split('-')[0] if rd else ''

        return {'poster': poster, 'genre': genre, 'title_en': title_en, 'year': real_year}
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None

# Procesar archivo M3U
def process_m3u(path: str, verbose: bool = False) -> None:
    # Leer todas las líneas del archivo
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    header: list[str] = []
    entries: list[tuple] = []  # (attrs, url, title, raw_year_int, real_year_int)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF') and i + 1 < len(lines):
            m = EXTINF_LINE.match(line.strip())
            if m:
                attrs_block, raw = m.group(1), m.group(2)
                url = lines[i + 1]

                title, raw_year = normalize_and_extract_year(raw)
                if verbose:
                    print(f"Buscando '{title}' (raw year={raw_year})")

                data = fetch_movie_data(title)
                if data:
                    # Año real o raw si no hay real
                    final_year_str = data['year'] or raw_year
                    final_year = int(final_year_str) if final_year_str.isdigit() else 0

                    # Determinar group-title
                    orig_group_m = re.search(r'group-title="(.*?)"', attrs_block)
                    orig_group = orig_group_m.group(1) if orig_group_m else ''
                    group_final = data['genre'] if not orig_group or orig_group.lower() == 'undefined' else orig_group

                    # Extraer tvg-id
                    id_m = re.search(r'tvg-id="(.*?)"', attrs_block)
                    id_val = id_m.group(1) if id_m else ''

                    # Construir atributos nuevos con espacio antes de cada key
                    ext_attrs = (
                        f' tvg-name="{data["title_en"]}"'
                        f' tvg-id="{id_val}"'
                        f' tvg-logo="{data["poster"]}"'
                        f' group-title="{group_final}"'
                    )

                    entries.append((ext_attrs, url, title, int(raw_year or 0), final_year))
                    i += 2
                    continue
        # No es EXTINF o no procesable, guardar como header
        header.append(line)
        i += 1

    # Ordenar entradas: sagas primero, luego otros
    sorted_entries = sort_same_name(entries)

    # Escribir archivo de nuevo
    with open(path, 'w', encoding='utf-8') as f:
        # Cabecera intacta
        for hl in header:
            f.write(hl)
        # Entradas procesadas y ordenadas
        for attrs, url, title, _, year in sorted_entries:
            display = f"{title} ({year})"
            f.write(f"#EXTINF:-1{attrs},{display}\n")
            f.write(url)

# Punto de entrada
def main():
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=verbose_flag)

if __name__ == '__main__':
    main()
