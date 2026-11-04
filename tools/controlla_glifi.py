#!/usr/bin/env python3
"""Controlla che ogni carattere usato nei testi del gioco esista nei font (niente quadratini).

Uso: python3 tools/controlla_glifi.py
Legge le stringhe di scripts/*.gd e le confronta con i glifi di ogni font in assets/font/.
Esce con errore se manca anche un solo carattere in un font usato per i testi.
"""
import glob, os, re, sys
from fontTools.ttLib import TTFont

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
testi = []
for f in glob.glob(R + '/scripts/*.gd'):
    src = open(f, encoding='utf-8').read()
    testi += re.findall(r'"""(.*?)"""', src, re.S)
    src = re.sub(r'"""(.*?)"""', '', src, flags=re.S)
    testi += re.findall(r'"((?:[^"\\]|\\.)*)"', src)
caratteri = set(''.join(testi)) - set('\n\t\r')
errori = 0
for font in sorted(glob.glob(R + '/assets/font/*.ttf')):
    cmap = TTFont(font).getBestCmap()
    manca = sorted(ch for ch in caratteri if ord(ch) not in cmap and ord(ch) > 31)
    nome = os.path.basename(font)
    if manca:
        print(f'{nome}: mancano {"".join(manca)!r}')
        errori += 1
    else:
        print(f'{nome}: tutti i {len(caratteri)} caratteri presenti')
sys.exit(1 if errori else 0)
