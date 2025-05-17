import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb
tmdb = TMDb()
api_key = os.getenv('TMDB_API_KEY')
if not api_key:
    print("ERROR: la variable TMDB_API_KEY no está definida")
    sys.exit(1)

tmdb.api_key = api_key

# Patrones de procesamiento
LOGO_PATTERN = re.compile(r'tvg-logo="(.*?)"')
TITLE_SPLIT = re.compile(r'#EXTINF:[^,]*,(.*)')
YEAR_PATTERN = re.compile(r'\s+\d{4}$')

def normalize_title(raw_title: str) -> str:
    """
    Elimina un año (4 dígitos) al final del título, si existe.
    Ej: "Zootopia 2010" -> "Zootopia"
    """
    return YEAR_PATTERN.sub('', raw_title).strip()

def fetch_logo_url(title: str) -> str | None:
    """
    Busca en TMDb el primer resultado y devuelve la URL del póster.
    """
    try:
        results = Movie().search(title)
        if results:
            poster_path = results[0].poster_path
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"Error buscando '{title}': {e}")
    return None

def process_m3u(path: str, verbose: bool = False) -> None:
    """
    Procesa el archivo M3U, reemplaza logos vacíos y escribe cambios.
    """
    updated = False
    output_lines: list[str] = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                logo_match = LOGO_PATTERN.search(line)
                title_match = TITLE_SPLIT.search(line)
                raw_title = title_match.group(1).strip() if title_match else ''
                search_title = normalize_title(raw_title)
                orig_logo = logo_match.group(1) if logo_match else None

                if verbose:
                    print(f"Procesando: raw_title='{raw_title}', search_title='{search_title}', orig_logo='{orig_logo}'")

                if not orig_logo:
                    new_logo = fetch_logo_url(search_title)
                    if new_logo:
                        line = LOGO_PATTERN.sub(f'tvg-logo=\"{new_logo}\"', line)
                        if verbose:
                            print(f" -> Nuevo logo: {new_logo}")
                        updated = True
            output_lines.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
    elif verbose:
        print("No se encontraron entradas sin logo o no hubo cambios.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u> [--verbose]")
        sys.exit(1)
    verbose = '--verbose' in sys.argv
    process_m3u(sys.argv[1], verbose)
