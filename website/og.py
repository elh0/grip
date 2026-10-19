# Renders the 1200x630 share card: python3 website/og.py -> website/assets/og.png (needs Playwright + Chromium; rerun only when the card changes).
import base64, os, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.join(HERE, '..', 'brand')
word = open(os.path.join(BRAND, 'grip-wordmark-blue.svg')).read()
word = re.sub(r'<metadata>.*?</metadata>', '', word, flags=re.S)
word = re.sub(r'\s+xmlns:c2pa="[^"]*"', '', word).replace('#4A74FF', 'currentColor')
icon = base64.b64encode(open(os.path.join(HERE, 'assets', 'favicon.svg'), 'rb').read()).decode()
# Chromium here can't reach Google Fonts, so fetch the two faces with curl and inline them.
def face(fam, q):
    css = subprocess.run(['curl', '-sS', '-A', 'Mozilla/5.0 Chrome/120', 'https://fonts.googleapis.com/css2?family=' + q + ':wght@400'], capture_output=True, text=True, check=True).stdout
    url = re.findall(r'url\((https://[^)]+)\)', css)[-1]
    data = subprocess.run(['curl', '-sS', url], capture_output=True, check=True).stdout
    return "@font-face{font-family:'" + fam + "';src:url(data:font/ttf;base64," + base64.b64encode(data).decode() + ")}"
fonts = '<style>' + face('Host Grotesk', 'Host+Grotesk') + face('DM Mono', 'DM+Mono') + '</style>'
card = open(os.path.join(HERE, 'og-card.html')).read().replace('</head>', fonts + '</head>').replace('{{WORD}}', word).replace('{{ICON}}', icon)
tmp = os.path.join(HERE, '.og-card.tmp.html'); open(tmp, 'w', encoding='utf-8').write(card)
js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:630}});"
      "await p.goto('file://" + tmp + "');await p.waitForTimeout(1500);await p.screenshot({path:'" + os.path.join(HERE, 'assets', 'og.png') + "'});await b.close();})();")
subprocess.run(['node', '-e', js], check=True)
os.remove(tmp)
print('og ok')
