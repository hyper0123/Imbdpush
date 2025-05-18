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

# Normaliza y extrae año raw
def normalize_and_extract_year(raw: str) -> tuple[str, str]:
    m = YEAR_PATTERN.search(raw)
    if m:
        return YEAR_PATTERN.sub('', raw).strip(), m.group(1)
    return raw, ''

# Ordena grupos con mismo basename
def sort_same_name(entries: list[tuple]) -> list[tuple]:
    def base_name(title: str) -> str:
        return re.sub(r'\s*\d+$', '', title).strip().lower()
    groups = {}
    for e in entries:
        bn = base_name(e[2])
        groups.setdefault(bn, []).append(e)
    # Sagas primero: grupos>1
    saga_entries, other_entries = [], []
    for bn, group in groups.items():
        if len(group) > 1:
            # orden por año
            saga_entries.extend(sorted(group, key=lambda x: x[4]))
        else:
            other_entries.extend(group)
    # mantener orden relativo de otros
    return saga_entries + sorted(other_entries, key=lambda x: (x[2].lower(), x[4]))

# Busca datos en TMDb y corrige título y año
def fetch_movie_data(search_title: str) -> dict | None:
    try:
        # Inglés para título original
tmdb.language = 'en-US'
        results = Movie().search(search_title)
        if not results:
            return None
        movie = results[0]
        # URL póster
        poster = f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if movie.poster_path else ''
        title_en = movie.original_title or movie.title
        # Español para géneros y fecha
        tmdb.language = 'es-ES'
        details = Movie().details(movie.id)
        genres = getattr(details, 'genres', []) or []
        genre = genres[0]['name'] if genres else ''
        # Extraer año real de release_date
        rd = getattr(details, 'release_date', '')
        real_year = rd.split('-')[0] if rd else ''
        return {'poster': poster, 'genre': genre, 'title_en': title_en, 'year': real_year}
    except Exception as e:
        print(f"Error TMDb al buscar '{search_title}': {e}")
        return None

# Procesa M3U
def process_m3u(path: str, verbose: bool = False) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header, entries = [], []  # entries: (extinf_attrs, url, raw_tny, raw_yr, real_yr)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF') and i+1 < len(lines):
            m = EXTINF_LINE.match(line.strip())
            if m:
                attrs, raw = m.group(1), m.group(2)
                url = lines[i+1]
                title_no_year, raw_year = normalize_and_extract_year(raw)
                if verbose:
                    print(f"Buscando '{title_no_year}' (raw '{raw}'), orig_year={raw_year}")
                data = fetch_movie_data(title_no_year)
                if data:
                    # elegir año corregido o raw si no disponible
t = data['year'] or raw_year
                    # construir attrs nuevos, corrigiendo group solo si undefined
                    orig_group = re.search(r'group-title="(.*?)"', attrs)
                    orig_group = orig_group.group(1) if orig_group else ''
                    grp = data['genre'] if not orig_group or orig_group.lower()=='undefined' else orig_group
                    ext_attrs = (
                        f' tvg-name="{data["title_en"]}"'
                        f' tvg-id="{re.search(r\\'tvg-id=\\"(.*?)\\"\\', attrs).group(1) or ""}"'
                        f' tvg-logo="{data["poster"]}"'
                        f' group-title="{grp}"'
                    )
                    entries.append((ext_attrs, url, title_no_year, int(raw_year or 0), int(t or 0)))
                    i += 2
                    continue
        header.append(line)
        i += 1
    # ordenar entries
    sorted_entries = sort_same_name(entries)
    # escribir fichero
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(header)
        for attrs, url, title, _, real in sorted_entries:
            disp = f"{title} ({real})"
            f.write(f"#EXTINF:-1{attrs},{disp}\n")
            f.write(url)

if __name__ == '__main__':
    v = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=v)
