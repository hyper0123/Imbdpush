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

# Patrones\NEXTINF_LINE = re.compile(r'^#EXTINF:-1(.*),(.*)$')
YEAR_PATTERN = re.compile(r'\s+(\d{4})$')

# Normalizar y extraer año
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
    for bn, group in groups.items():
        if len(group) > 1:
            saga_entries.extend(sorted(group, key=lambda x: x[4]))
        else:
            other_entries.extend(group)
    other_entries.sort(key=lambda x: (x[2].lower(), x[4]))
    return saga_entries + other_entries

# Obtener datos de TMDb
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        tmdb.language = 'en-US'
        results = Movie().search(search_title)
        if not results:
            return None
        movie = results[0]
        poster = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
        title_en = movie.original_title or movie.title

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

# Procesar M3U
def process_m3u(path: str, verbose: bool = False) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    header: list[str] = []
    entries: list[tuple] = []  # (attrs, url, title, raw_year, final_year)
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
                    print(f"Buscando '{title}' raw_year={raw_year}")
                data = fetch_movie_data(title)
                if data:
                    real_year = data['year'] or raw_year
                    final_year = int(real_year) if real_year.isdigit() else 0
                    orig_group_match = re.search(r'group-title="(.*?)"', attrs_block)
                    orig_group = orig_group_match.group(1) if orig_group_match else ''
                    group_final = data['genre'] if not orig_group or orig_group.lower() == 'undefined' else orig_group
                    # Extraer id
                    id_match = re.search(r'tvg-id="(.*?)"', attrs_block)
                    id_val = id_match.group(1) if id_match else ''
                    # Construir atributos nuevos
                    ext_attrs = (
                        f' tvg-name="{data["title_en"]}"'
                        f' tvg-id="{id_val}"'
                        f' tvg-logo="{data["poster"]}"'
                        f' group-title="{group_final}"'
                    )
                    entries.append((ext_attrs, url, title, int(raw_year or 0), final_year))
                    i += 2
                    continue
        header.append(line)
        i += 1

    # Ordenar y escribir
    sorted_entries = sort_same_name(entries)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(header)
        for attrs, url, title, _, year in sorted_entries:
            display = f"{title} ({year})"
            f.write(f"#EXTINF:-1{attrs},{display}\n")
            f.write(url)

if __name__ == '__main__':
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=verbose_flag)
