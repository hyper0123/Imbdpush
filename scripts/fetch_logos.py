import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb
tmdb = TMDb()
tmdb.api_key = os.getenv('TMDB_API_KEY')

# Patrón para cualquier línea EXTINF
def is_extinf(line):
    return line.strip().startswith('#EXTINF:')

# Extrae el valor de un atributo tvg-logo
LOGO_RE = re.compile(r'tvg-logo="(.*?)"')


def fetch_logo_url(title):
    """Busca en TMDb el primer resultado de la película y devuelve la URL del póster"""
    search = Movie()
    results = search.search(title)
    if results:
        poster = results[0].poster_path
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"
    return None


def process_m3u(path):
    updated = False
    lines_out = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if is_extinf(line):
                # Obtener logo actual y título (texto tras la coma)
                logo_match = LOGO_RE.search(line)
                if logo_match and logo_match.group(1) == '':
                    title = line.split(',', 1)[1].strip()
                    new_logo = fetch_logo_url(title)
                    if new_logo:
                        # Reemplaza tvg-logo="" con la URL nueva
                        line = LOGO_RE.sub(f'tvg-logo="{new_logo}"', line)
                        updated = True
            lines_out.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines_out)
        print(f"✅ Insertados nuevos logos en {path}")
    else:
        print(f"⚠️ No se encontraron entradas sin logo en {path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u>")
        sys.exit(1)
    process_m3u(sys.argv[1])
