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

# Patrones
EXTINF_LINE = re.compile(r'^#EXTINF:-1(.*),(.*)$')
YEAR_PATTERN = re.compile(r'\s+(\d{4})$')

# Función para extraer título sin año y año
def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = YEAR_PATTERN.search(raw)
    if m:
        return raw[:m.start()].strip(), m.group(1)
    return raw.strip(), ''

# Función fuzzy para correcciones básicas
def generate_variations(title: str) -> list[str]:
    variations = [title]
    # reemplazar ' and ' por ' & '
    if re.search(r' and ', title, re.IGNORECASE):
        variations.append(re.sub(r' and ', ' & ', title, flags=re.IGNORECASE))
    # asegurar espacio antes del año
    variations.append(re.sub(r"(\D)(\d{4})$", r"\1 \2", title))
    return list(dict.fromkeys(variations))

# Obtener datos de TMDb con fallback fuzzy
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        tmdb.language = 'en-US'
        for variant in generate_variations(search_title):
            results = Movie().search(variant)
            if results:
                movie = results[0]
                poster = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
                title_en = movie.original_title or movie.title
                tmdb.language = 'es-ES'
                details = Movie().details(movie.id)
                genres = getattr(details, 'genres', []) or []
                genre_name = genres[0]['name'] if genres else ''
                return {'poster': poster, 'genre': genre_name, 'title_en': title_en}
        return None
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None

# Función para ordenar sagas y demás
def sort_and_group(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    # Identificar sagas (mismo base_name múltiples veces)
    def base_name(t: str) -> str:
        return re.sub(r"\s+\d+$", '', t).strip()

    counts = {}
    for e in entries:
        bn = base_name(e['title'])
        counts[bn] = counts.get(bn, 0) + 1

    saga_entries = []
    other_entries = []
    for e in entries:
        if counts[base_name(e['title'])] > 1:
            saga_entries.append(e)
        else:
            other_entries.append(e)

    saga_entries.sort(key=lambda x: (base_name(x['title']), int(x['year'] or 0)))
    other_entries.sort(key=lambda x: x['title_en'])

    return saga_entries, other_entries

# Función principal
def process_m3u(path: str, verbose: bool = False) -> None:
    lines = open(path, 'r', encoding='utf-8').readlines()
    header = []
    entries = []  # dicts con keys: title, year, id, poster, genre, title_en, url

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF') and i + 1 < len(lines):
            m = EXTINF_LINE.match(line.strip())
            if m:
                attrs, raw_title = m.groups()
                url_line = lines[i + 1]
                id_match = re.search(r'tvg-id="(.*?)"', attrs)
                group_match = re.search(r'group-title="(.*?)"', attrs)
                id_val = id_match.group(1) if id_match else ''
                group_val = group_match.group(1) if group_match else ''
                title_no_year, year = normalize_and_extract_year(raw_title)
                if verbose:
                    print(f"Procesando: '{raw_title}' -> '{title_no_year}', año='{year}', grupo='{group_val}'")
                data = fetch_movie_data(title_no_year) or fetch_movie_data(raw_title)
                if data:
                    entries.append({
                        'title': title_no_year,
                        'year': year,
                        'id': id_val,
                        'poster': data['poster'],
                        'genre': data['genre'] or group_val,
                        'title_en': data['title_en'],
                        'url': url_line
                    })
                    i += 2
                    continue
        header.append(line)
        i += 1

    saga_entries, other_entries = sort_and_group(entries)

    with open(path, 'w', encoding='utf-8') as f:
        for h in header:
            f.write(h)
        # Primero sagas
        for e in saga_entries:
            display = f"{e['title']} ({e['year']})" if e['year'] else e['title']
            attrs = (
                f' tvg-name="{e['title_en']}"'
                f' tvg-id="{e['id']}"'
                f' tvg-logo="{e['poster']}"'
                f' group-title="Sagas"'
            )
            f.write(f"#EXTINF:-1{attrs},{display}\n")
            f.write(e['url'])
        # Luego los demás
        for e in other_entries:
            display = f"{e['title']} ({e['year']})" if e['year'] else e['title']
            attrs = (
                f' tvg-name="{e['title_en']}"'
                f' tvg-id="{e['id']}"'
                f' tvg-logo="{e['poster']}"'
                f' group-title="{e['genre']}"'
            )
            f.write(f"#EXTINF:-1{attrs},{display}\n")
            f.write(e['url'])

if __name__ == '__main__':
    verbose = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose)
