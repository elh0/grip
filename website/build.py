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
v8 = v8.replace('{{REEL}}', REEL).replace('{{POSE}}', pose).replace('{{ENGINE}}', engine).replace('{{WORD}}', word).replace('{{MARK}}', mark).replace('{{LINE}}', LINE)
assert '{{' not in v8
# doctype + charset so £ and × survive when served as a plain file on g-r-i-p.com (caught by the studio site thread, 19 Oct 2026)
v8 = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + v8.replace('<title>grip</title>', '<title>grip</title>', 1) + '\n</html>\n'
open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(v8)
print('v8 ok', len(v8))
