# Builds the Grip website: python3 website/build.py  (no dependencies) -> website/index.html
# Pulls the locked wordmark, crimp mark and wireframe engine from ../brand so the site never drifts from the identity.
# Working copy also lives in the Eltio project files (eltio/grip/website/); keep the two in sync.
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.join(HERE, '..', 'brand')
LINE = '#4A74FF'  # mat blue
word = open(os.path.join(BRAND, 'grip-wordmark-blue.svg')).read()
word = re.sub(r'<metadata>.*?</metadata>', '', word, flags=re.S)
word = re.sub(r'\s+xmlns:c2pa="[^"]*"', '', word).replace(LINE, 'currentColor')
src = open(os.path.join(BRAND, 'build', 'page.html')).read()
js = src[src.index('<script>'):]
engine = js[js.index('(function () {') + len('(function () {'):js.index('  var heroSvg')]

# ---- v8 (19 Oct 2026): Elliot: "more interactive and UI friendly… a little preview of the app… 3D so you can play with it".
# One CSS 3D phone with the live app inside, sticky through a scroll walkthrough. v7 stays as site-v7.html for reference.
mark = open(os.path.join(BRAND, 'grip-mark-white.svg')).read()
mark = re.sub(r'<metadata>.*?</metadata>', '', mark, flags=re.S)
mark = re.sub(r'\s+xmlns:c2pa="[^"]*"', '', mark).replace('#F3F3F0', 'currentColor').replace('<svg ', '<svg aria-hidden="true" ')
v8 = open(os.path.join(HERE, 'site-v8.html')).read()
# REEL: the tracked climber stands in until Elliot's real clip arrives (then swap in a muted looping <video>).
REEL = '<svg aria-label="A climber tracked as lines and joints, with notes pinned to the moment"></svg>'
pose = open(os.path.join(HERE, 'pose.js')).read()  # hand-keyed heel hook, triangle and muscle-up (19 Oct 2026)
# Tally form id for the beta/coach signup (Elliot chose Tally, 20 Oct 2026). Empty = demo forms. Form needs hidden fields 'email' and 'type'.
TALLY = ''
v8 = v8.replace('{{TALLY}}', TALLY).replace('{{REEL}}', REEL).replace('{{POSE}}', pose).replace('{{ENGINE}}', engine).replace('{{WORD}}', word).replace('{{MARK}}', mark).replace('{{LINE}}', LINE)
assert '{{' not in v8
# doctype + charset so £ and × survive when served as a plain file on g-r-i-p.com (caught by the studio site thread, 19 Oct 2026)
# Go-live head (19 Oct 2026): tab icon, home-screen icon and share card for g-r-i-p.com. assets/og.png comes from og.py.
URL = 'https://g-r-i-p.com/'
DESC = 'Film a climb. Grip tracks your body and sends back the three things to fix, each pinned to the second it happened.'
# index uses relative paths (works on the preview artifact too); 404.html is served at any depth, so it uses root paths.
ICONS = ('<link rel="icon" href="{A}assets/favicon.svg" type="image/svg+xml"><link rel="icon" href="{A}assets/favicon-32.png" sizes="32x32" type="image/png">'
         '<link rel="apple-touch-icon" href="{A}assets/apple-touch-icon.png"><meta name="theme-color" content="#000000">')
SHARE = ('<link rel="canonical" href="' + URL + '">'
         '<meta property="og:type" content="website"><meta property="og:url" content="' + URL + '"><meta property="og:site_name" content="grip">'
         '<meta property="og:title" content="grip: film a climb, get three notes"><meta property="og:description" content="' + DESC + '">'
         '<meta property="og:image" content="' + URL + 'assets/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
         '<meta name="twitter:card" content="summary_large_image">')
v8 = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + ICONS.replace('{A}', '') + '\n' + SHARE + '\n' + v8 + '\n</html>\n'
open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(v8)
nf = open(os.path.join(HERE, '404.src.html')).read().replace('{{HEAD}}', ICONS.replace('{A}', '/')).replace('{{WORD}}', word)
assert '{{' not in nf
open(os.path.join(HERE, '404.html'), 'w', encoding='utf-8').write(nf)
print('v8 ok', len(v8), '404 ok', len(nf))
