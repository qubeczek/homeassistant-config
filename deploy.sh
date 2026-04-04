#!/bin/bash
# Skrypt deployujący konfigurację na produkcję (H:\)
# Kopiuje pliki .py, .md, .json, .yaml z:
#   - bieżącego katalogu (bez rekursji)
#   - custom_components/ (rekursywnie)
#   - include/ (rekursywnie)
# Kopiuje tylko pliki, które się różnią od wersji na produkcji.

SRC="d:/priv/dom/SDI/homeassistant-config"
DST="h:"
EXTENSIONS=("*.py" "*.md" "*.json" "*.yaml")
COUNTFILE=$(mktemp)
echo 0 > "$COUNTFILE"

copy_if_changed() {
    local src_file="$1"
    local dst_file="$2"
    local label="$3"

    if [ -f "$dst_file" ] && diff -q "$src_file" "$dst_file" > /dev/null 2>&1; then
        return
    fi

    local dst_dir
    dst_dir=$(dirname "$dst_file")
    mkdir -p "$dst_dir"

    if cp "$src_file" "$dst_file"; then
        echo "  KOPIOWANO: $label"
        echo $(( $(cat "$COUNTFILE") + 1 )) > "$COUNTFILE"
    else
        echo "  BŁĄD:      $label"
    fi
}

echo "=== Deploy na produkcję: $DST ==="

# Pliki z katalogu głównego (bez rekursji)
for ext in "${EXTENSIONS[@]}"; do
    for f in "$SRC"/$ext; do
        [ -f "$f" ] || continue
        base=$(basename "$f")
        if [ "$base" = "secrets.yaml" ]; then
            continue
        fi
        copy_if_changed "$f" "$DST/$base" "$base"
    done
done

# Pliki z custom_components i include (rekursywnie)
for dir in custom_components include; do
    if [ ! -d "$SRC/$dir" ]; then
        continue
    fi
    for ext in "${EXTENSIONS[@]}"; do
        find "$SRC/$dir" -name "$ext" -type f | while read -r f; do
            rel="${f#$SRC/}"
            copy_if_changed "$f" "$DST/$rel" "$rel"
        done
    done
done

COPIED=$(cat "$COUNTFILE")
rm -f "$COUNTFILE"

echo ""
if [ "$COPIED" -eq 0 ]; then
    echo "Brak zmian — produkcja jest aktualna."
else
    echo "Skopiowano $COPIED plik(ów)."
fi
echo "=== Deploy zakończony ==="
