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
    vars = [title]
    # reemplazar ' and ' por ' & '
    if ' and ' in title.lower():
        vars.append(re.sub(r' and ', ' & ', title, flags=re.IGNORECASE))
    # asegurar espacio antes del año
    vars.append(re.sub(r"(\D)(\d{4})$", r"\1 \2", title))
    # caracteres especiales
    vars.append(title.replace('%', '%25'))
    return list(dict.fromkeys(vars))

# Obtener datos de TMDb con fallback fuzzy
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        tmdb.language = 'en-US'
        # probar variaciones
        for variant in generate_variations(search_title):
            results = Movie().search(variant)
            if results:
                movie = results[0]
                poster = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
                title_en = movie.original_title or movie.title
                # géneros
                tmdb.language = 'es-ES'
                details = Movie().details(movie.id)
                genres = getattr(details, 'genres', []) or []
                genre_name = genres[0]['name'] if genres else ''
                return {'poster': poster, 'genre': genre_name, 'title_en': title_en}
        return None
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None

# Procesar playlist
 def process_m3u(path: str, verbose: bool = False) -> None:
    lines = open(path, 'r', encoding='utf-8').readlines()
    header, entries = [], []

    # Parseo inicial
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF') and i+1 < len(lines):
            m = EXTINF_LINE.match(line.strip())
            if m:
                attrs, raw_title = m.groups()
                url_line = lines[i+1]
                # extraer campos
                orig_id = re.search(r'tvg-id="(.*?)"', attrs)
                orig_group = re.search(r'group-title="(.*?)"', attrs)
                id_val = orig_id.group(1) if orig_id else ''
                group_val = orig_group.group(1) if orig_group else ''
                # normalizar y extraer año
                title_no_year, year = normalize_and_extract_year(raw_title)
                if verbose:
                    print(f"Procesando: '{raw_title}' -> '{title_no_year}', año='{year}', grupo orig='{group_val}'")
                data = fetch_movie_data(title_no_year)
                # fallback al raw completo si no
                if not data:
                    data = fetch_movie_data(raw_title)
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

    # Agrupar por base_name
    def base_name(t): return re.sub(r"\s+\d+$", '', t).strip()
    counts = {}
    for e in entries:
        bn = base_name(e['title'])
        counts[bn] = counts.get(bn, 0) + 1

    # Ordenar entradas: sagas primero, luego resto
    saga_entries = []
    other_entries = []
    for e in entries:
        bn = base_name(e['title'])
        if counts[bn] > 1:
            saga_entries.append(e)
        else:
            other_entries.append(e)
    # ordenar sagas y otros por base_name/ year
    saga_entries = sorted(saga_entries, key=lambda x: (base_name(x['title']), int(x['year'] or 0)))
    other_entries = sorted(other_entries, key=lambda x: x['title_en'])

    # Reescritura
    with open(path, 'w', encoding='utf-8') as f:
        for h in header:
            f.write(h)
        # escribir sagas bajo grupo Sagas
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
        # luego resto manteniendo grupo original
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
