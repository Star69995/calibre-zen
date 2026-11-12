#!/bin/sh
# Photograph the app for the website, in English and Hebrew, light and dark,
# and write site/img/<lang>/<state>-<mode>.webp. See scripts/site_shots.py.
#
#   CALIBRE_ZEN_CALIBRE_DEBUG=<calibre-debug> scripts/site-shots.sh <library>
#
# Needs a calibre binary of the same version as src/calibre/constants.py, as
# ./zen-test does. Raw PNGs are kept under .calibre-zen/shots/site/.
set -eu
# pwd -W: Git Bash's C:/ form, which a Windows calibre understands; plain pwd elsewhere.
here=$(cd "$(dirname "$0")/.." && { pwd -W 2>/dev/null || pwd; })
lib=${1:?usage: site-shots.sh <library folder>}
debug=${CALIBRE_ZEN_CALIBRE_DEBUG:-calibre-debug}
raw="$here/.calibre-zen/shots/site"
for lang in en he; do
    for mode in light dark; do
        out="$raw/$lang-$mode"
        cfg="$raw/config-$lang-$mode"
        rm -rf "$out" "$cfg" && mkdir -p "$out" "$cfg"
        CALIBRE_DEVELOP_FROM="$here/src" CALIBRE_CONFIG_DIRECTORY="$cfg" CALIBRE_OVERRIDE_LANG="$lang" \
            QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR="${QT_QPA_FONTDIR:-C:/Windows/Fonts}" QT_SCALE_FACTOR=1.5 \
            "$debug" -e "$here/scripts/site_shots.py" -- "$lib" "$out" "$lang" "$mode" || true
        # The GUI leaves with os._exit(), whose status says nothing; the pictures do.
        [ -f "$out/find.png" ] || { echo "no shots for $lang $mode" >&2; exit 1; }
        mkdir -p "$here/site/img/$lang"
        "$debug" -c "
import glob, os
from PIL import Image
for f in glob.glob(os.path.join(r'$out', '*.png')):
    name = os.path.splitext(os.path.basename(f))[0]
    Image.open(f).convert('RGB').save(os.path.join(r'$here/site/img/$lang', f'{name}-$mode.webp'), quality=82, method=6)
    print('webp', '$lang', name, '$mode')
"
    done
done
