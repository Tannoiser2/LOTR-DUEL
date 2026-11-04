#!/usr/bin/env python3
"""Ricompone le 54 carte del modulo TTS in italiano.

Uso: python3 tools/componi_carte.py <cartella Mods/Images del modulo> <file .json del modulo>
- ritaglia ogni scansione sul bordo della carta e la porta a 480x744
- sulle 11 carte speciali copre il riquadro inglese con un cartiglio e scrive nome e testo in italiano
  (Cinzel per il nome, EB Garamond per il testo); le tabelle di Equilibrio e Potenza sono disegnate
  con quadratini e figurine, senza simboli di font
- salva assets/carte/<id>.webp, dorso_G.webp, dorso_B.webp
"""
import glob, json, os, re, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(R, 'assets', 'carte')
FONT = os.path.join(R, 'assets', 'font')
W, H = 480, 744

DATI = {}
for line in open(os.path.join(R, 'scripts', 'dati.gd'), encoding='utf-8'):
    m = re.match(r'\s*(\d+): (\{.*\}),\s*$', line)
    if m:
        DATI[int(m.group(1))] = json.loads(m.group(2))


def font(nome, size, peso=None):
    f = ImageFont.truetype(os.path.join(FONT, nome), size)
    if peso:
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
    return f


def ritaglia(im):
    """Taglia il bianco attorno alla scansione e porta la carta a W x H con angoli arrotondati."""
    im = im.convert('RGB')
    g = im.convert('L').point(lambda v: 0 if v > 236 else 255)
    box = g.getbbox() or (0, 0, im.width, im.height)
    im = im.crop(box).resize((W, H), Image.LANCZOS)
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=22, fill=255)
    im = im.convert('RGBA')
    im.putalpha(mask)
    return im


def cartiglio(im, lato):
    """Riquadro su cui scrivere, al posto di quello inglese."""
    x0, y0, x1, y1 = int(W * 0.165), int(H * 0.6), int(W * 0.835), int(H * 0.93)
    ombra = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ombra).rounded_rectangle([x0 + 3, y0 + 5, x1 + 3, y1 + 5], radius=14, fill=(0, 0, 0, 110))
    ombra = ombra.filter(ImageFilter.GaussianBlur(5))
    im.alpha_composite(ombra)
    pan = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(pan)
    if lato == 'G':
        fondo, bordo, bordo2 = (244, 236, 214, 255), (176, 134, 52, 255), (222, 190, 112, 255)
    else:
        fondo, bordo, bordo2 = (236, 233, 226, 255), (70, 78, 80, 255), (150, 60, 30, 255)
    d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=fondo, outline=bordo, width=3)
    d.rounded_rectangle([x0 + 6, y0 + 6, x1 - 6, y1 - 6], radius=10, outline=bordo2, width=1)
    im.alpha_composite(pan)
    # leggera luce in alto, su un livello a parte (disegnarla sul pannello lo renderebbe trasparente)
    luce = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(luce)
    for k in range(18):
        dl.line([(x0 + 8, y0 + 8 + k), (x1 - 8, y0 + 8 + k)], fill=(255, 255, 255, int(70 * (1 - k / 18))))
    im.alpha_composite(luce)
    return (int(W * 0.215), y0 + 9, int(W * 0.775), y1 - 9)


def a_capo(testo, f, larg, d):
    righe, cur = [], ''
    for p in testo.split():
        prova = (cur + ' ' + p).strip()
        if d.textlength(prova, font=f) <= larg:
            cur = prova
        else:
            righe.append(cur)
            cur = p
    if cur:
        righe.append(cur)
    return righe


# --- tabelle disegnate (Equilibrio e Potenza)

GRIGIO, ROSSO = (128, 118, 128), (200, 48, 32)


def quadretto(d, x, y, s, col):
    d.rectangle([x, y - s // 2, x + s, y + s // 2], fill=col, outline=(40, 30, 30), width=1)
    return x + s


def figurina(d, x, y, s, col):
    """Sagoma stilizzata della figura sul ponte."""
    w = int(s * 0.8)
    d.ellipse([x + w * 0.3, y - s * 0.62, x + w * 0.7, y - s * 0.22], fill=col, outline=(40, 30, 30))
    d.polygon([(x + w * 0.22, y + s * 0.5), (x + w * 0.78, y + s * 0.5), (x + w * 0.62, y - s * 0.2), (x + w * 0.38, y - s * 0.2)], fill=col, outline=(40, 30, 30))
    return x + w


def freccia(d, x, y, s, col=(60, 40, 30)):
    d.line([(x, y), (x + s - 6, y)], fill=col, width=3)
    d.polygon([(x + s, y), (x + s - 9, y - 6), (x + s - 9, y + 6)], fill=col)
    return x + s


def riga_tabella(d, x, y, elementi, f, s):
    for e in elementi:
        if e == 'G':
            x = quadretto(d, x, y, s, GRIGIO) + 4
        elif e == 'B':
            x = quadretto(d, x, y, s, ROSSO) + 4
        elif e == 'g':
            x = figurina(d, x, y, s + 4, GRIGIO) + 4
        elif e == 'b':
            x = figurina(d, x, y, s + 4, ROSSO) + 4
        elif e == '->':
            x = freccia(d, x + 3, y, 22) + 6
        elif isinstance(e, tuple):
            x = e[0]
        else:
            d.text((x + 2, y), e, font=f, fill=(40, 30, 25), anchor='lm')
            x += d.textlength(e, font=f) + 6
    return x


TABELLE = {
    'equilibrio': [['G', '>', 'B', '->', 'G', '+1'], ['G', '=', 'B', '->', 'G', '+1 /', 'B', '−1'], ['G', '<', 'B', '->', 'G', '+2 /', 'B', '−1']],
    'potenza': [['b', '>', 'g', '->', 'B', '+1'], ['b', '=', 'g', '->', 'B', '+1 /', 'G', '−1'], ['b', '<', 'g', '->', 'B', '+2 /', 'G', '−1']],
}
TESTO_BREVE = {
    'equilibrio': 'Sposta i segnalini energia in base alla loro posizione:',
    'potenza': 'Le figure sul ponte decidono come si sposta l’energia:',
}


def scrivi(im, c):
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = cartiglio(im, c['lato'])
    d = ImageDraw.Draw(im)
    larg = x1 - x0
    nome = c['nome']
    fn = font('Cinzel.ttf', 26, 700)
    while d.textlength(nome, font=fn) > larg and fn.size > 15:
        fn = font('Cinzel.ttf', fn.size - 1, 700)
    col_t = (92, 58, 14) if c['lato'] == 'G' else (120, 30, 14)
    d.text(((x0 + x1) / 2, y0 + 8), nome, font=fn, fill=col_t, anchor='mt')
    top = y0 + 8 + fn.size + 6
    testo = TESTO_BREVE.get(c['spec'], c['testo']).replace("'", '’')
    tab = TABELLE.get(c['spec'])
    spazio = y1 - top - (3 * 34 if tab else 0)
    size = 22
    while True:
        ft = font('EBGaramond.ttf', size, 500)
        righe = a_capo(testo, ft, larg, d)
        alt = len(righe) * int(size * 1.12)
        if alt <= spazio or size <= 14:
            break
        size -= 1
    y = top + (spazio - alt) / 2 if not tab else top
    for r in righe:
        d.text(((x0 + x1) / 2, y), r, font=ft, fill=(38, 30, 26), anchor='mt')
        y += int(size * 1.12)
    if tab:
        fr = font('EBGaramond.ttf', 21, 600)
        y += 16
        for el in tab:
            # centra la riga: prima la misura su un'immagine di prova
            prova = Image.new('RGBA', (W, 60))
            fine = riga_tabella(ImageDraw.Draw(prova), 0, 30, el, fr, 17)
            riga_tabella(d, (x0 + x1 - fine) / 2, y, el, fr, 17)
            y += 29


def ripristina_cornice(im, orig):
    """Il cartiglio passa sotto la cornice: ai lati si rimettono i pixel originali della cornice
    (cerchi, rombi, pietra), lasciando coperti solo il riquadro bianco e il testo inglese."""
    a, b = im.load(), orig.load()
    for y in range(int(H * 0.59), int(H * 0.94)):
        for x in list(range(int(W * 0.15), int(W * 0.21))) + list(range(int(W * 0.78), int(W * 0.85))):
            r, g, bb, al = b[x, y]
            chiaro = min(r, g, bb) > 175 and max(r, g, bb) - min(r, g, bb) < 50
            scuro = max(r, g, bb) < 95
            if not chiaro and not scuro:
                a[x, y] = (r, g, bb, al)


def main():
    imgs, tts = sys.argv[1], sys.argv[2]
    mod = json.load(open(tts, encoding='utf-8'))
    file_per = {os.path.basename(p): p for p in glob.glob(os.path.join(imgs, '*'))}

    def trova(url):
        k = re.search(r'ugc/\d+/(\w+)/', url).group(1)
        for nome, p in file_per.items():
            if k in nome:
                return p
        raise SystemExit('immagine mancante ' + url)

    os.makedirs(OUT, exist_ok=True)
    dorsi = {}
    for o in mod['ObjectStates']:
        if o['Name'] != 'Deck':
            continue
        for c in o['ContainedObjects']:
            dk = list(c['CustomDeck'].values())[0]
            cid = c['CardID'] // 100
            im = ritaglia(Image.open(trova(dk['FaceURL'])))
            info = DATI[cid]
            if info['spec'] and info['spec'] != 'trance':
                orig = im.copy()
                scrivi(im, info)
                ripristina_cornice(im, orig)
            im.save(os.path.join(OUT, f'{cid}.webp'), quality=88)
            dorsi[info['lato']] = dk['BackURL']
    for lato, url in dorsi.items():
        ritaglia(Image.open(trova(url))).save(os.path.join(OUT, f'dorso_{lato}.webp'), quality=88)
    print('carte scritte in', OUT)


if __name__ == '__main__':
    main()
