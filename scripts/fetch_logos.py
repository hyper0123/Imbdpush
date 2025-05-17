import os
import re
import sys
from tmdbv3api import TMDb, Movie, TMDbException

# Inicializar TMDb
tmdb = TMDb()
api_key = os.getenv('TMDB_API_KEY')
if not api_key:
    print("ERROR: la variable TMDB_API_KEY no está definida")
    sys.exit(1)

tmdb.api_key = api_key

# Expresión para líneas EXTINF
MOVIE_LINE_RE = re.compile(
    r'(#EXTINF:-1\s+tvg-name="(?P<name>.*?)"\s+tvg-id="(?P<id>.*?)"\s+tvg-logo="(?P<logo>.*?)"\s+group-title="(?P<group>.*?)",(?P<title>.*))'
)


def fetch_logo_url(title):
    try:
        search = Movie()
        results = search.search(title)
        if results:
            poster = results[0].poster_path
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"
    except TMDbException as e:
        print(f"TMDbException buscando '{title}': {e}")
    return None


def process_m3u(path, verbose=False):
    updated = False
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            match = MOVIE_LINE_RE.match(line)
            if match:
                title = match.group('title')
                orig_logo = match.group('logo')
                if verbose:
                    print(f"Procesando: {title}, logo actual: '{orig_logo}'")
                if not orig_logo:
                    new_logo = fetch_logo_url(title)
                    if new_logo:
                        line = re.sub(r'tvg-logo=".*?"', f'tvg-logo="{new_logo}"', line)
                        if verbose:
                            print(f" -> Nuevo logo: {new_logo}")
                        updated = True
            lines.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    elif verbose:
        print("No se encontraron entradas sin logo o no hubo cambios.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose_flag = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose=verbose_flag)
