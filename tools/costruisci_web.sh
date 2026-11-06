#!/bin/bash
# Esporta la TV (Godot web) in build/web e ci copia accanto la pagina dei telefoni con le carte e i font.
# Uso: tools/costruisci_web.sh [comando godot]
set -e
cd "$(dirname "$0")/.."
GODOT=${1:-godot}
mkdir -p build/web
find build/web -mindepth 1 -delete
$GODOT --headless --path . --import >/dev/null 2>&1 || true
$GODOT --headless --path . --export-release "Web" build/web/index.html
test -f build/web/index.pck
cp -r web/telefono.html web/js web/css build/web/
mkdir -p build/web/img/carte build/web/font
cp assets/carte/*.webp build/web/img/carte/
cp assets/font/*.ttf build/web/font/
# numero di versione (data e ora) per non far usare al browser i file vecchi
V=$(date -u +%Y%m%d%H%M)
sed -i "s#js/telefono.js#js/telefono.js?v=$V#; s#css/telefono.css#css/telefono.css?v=$V#" build/web/telefono.html
sed -i "s#js/ponte.js#js/ponte.js?v=$V#" build/web/index.html
touch build/web/.nojekyll
echo "Pronto in build/web"
