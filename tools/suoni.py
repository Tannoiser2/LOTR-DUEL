#!/usr/bin/env python3
"""Prepara i suoni del gioco in assets/audio/ (ogg mono).

Uso: python3 tools/suoni.py <cartella ogg dell'Oculus Audio Pack>
Le voci e alcuni effetti vengono dall'Oculus Audio Pack (Meta, CC BY 4.0, va citato nei crediti):
- il Balrog: voci di giganti, orchi e troll abbassate di tono, con eco di caverna e un brontolio grave
- Gandalf: voci maschili (sforzo, dolore, urlo) appena abbassate
Fulmine, schiocco della frusta, crepitio del fuoco e brontolio della lava sono sintetizzati qui.
Serve ffmpeg.
"""
import os, subprocess, sys, tempfile
import numpy as np

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(R, 'assets', 'audio')
SR = 44100


def ff(args):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + args, check=True)


def sorgente(cartella, nome):
    return os.path.join(cartella, nome + '.ogg')


def elabora(src, dst, tono=1.0, filtri='', volume=1.0):
    """Cambia tono (rallentando come un nastro), aggiunge i filtri e normalizza."""
    catena = []
    if tono != 1.0:
        catena.append(f'asetrate={int(SR * tono)},aresample={SR}')
    if filtri:
        catena.append(filtri)
    catena.append(f'volume={volume}')
    catena.append('loudnorm=I=-16:TP=-1.5:LRA=11')
    ff(['-i', src, '-ac', '1', '-af', ','.join(catena), '-ar', str(SR), '-c:a', 'libvorbis', '-q:a', '4', dst])


def scrivi(dst, x):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp = f.name
    import wave
    with wave.open(tmp, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    ff(['-i', tmp, '-c:a', 'libvorbis', '-q:a', '4', dst])
    os.remove(tmp)


def passa_basso(x, f):
    a = np.exp(-2 * np.pi * f / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def rumore_marrone(n, rng):
    b = np.cumsum(rng.standard_normal(n))
    b -= np.convolve(b, np.ones(2000) / 2000, mode='same')
    return b / (np.max(np.abs(b)) + 1e-9)


def fulmine(rng):
    """Schiocco secco e rombo che rotola."""
    n = int(SR * 2.6)
    t = np.arange(n) / SR
    crack = rng.standard_normal(n) * np.exp(-t * 28)
    crack += rng.standard_normal(n) * np.exp(-np.maximum(t - 0.05, 0) * 18) * (t > 0.05) * 0.6
    rombo = rumore_marrone(n, rng) * (1 - np.exp(-t * 12)) * np.exp(-t * 1.6)
    rombo *= 1 + 0.5 * np.sin(2 * np.pi * 3.1 * t) * np.exp(-t)
    return crack * 0.9 + passa_basso(rombo, 300) * 3.0


def schiocco(rng):
    """Lo schiocco della frusta: fruscio che sale e un colpo secco."""
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    fr = rng.standard_normal(n) * np.clip(t / 0.35, 0, 1) ** 3 * (t < 0.36)
    fr = fr - passa_basso(fr, 900)
    k = (t >= 0.36)
    crack = rng.standard_normal(n) * np.exp(-(t - 0.36) * 60) * k
    eco = np.roll(crack, int(SR * 0.09)) * 0.35 + np.roll(crack, int(SR * 0.21)) * 0.15
    return fr * 0.5 + crack + eco


def fuoco(rng, secondi=1.6):
    """Vampata: soffio grave e crepitio."""
    n = int(SR * secondi)
    t = np.arange(n) / SR
    inv = np.clip(t / 0.15, 0, 1) * np.exp(-np.maximum(t - 0.15, 0) * 2.2)
    soffio = passa_basso(rng.standard_normal(n), 700) * inv * 4
    crep = np.zeros(n)
    for _ in range(int(60 * secondi)):
        i = rng.integers(0, n - 400)
        crep[i:i + 400] += rng.standard_normal(400) * np.exp(-np.arange(400) / 40) * rng.uniform(0.2, 1)
    return soffio + crep * inv * 0.5


def lava(rng, secondi=24.0):
    """Brontolio continuo della lava, che si ripete senza stacchi."""
    n = int(SR * secondi)
    t = np.arange(n) / SR
    b = passa_basso(rumore_marrone(n, rng), 180)
    mod = 0.7 + 0.3 * np.sin(2 * np.pi * t / secondi * 3) * np.sin(2 * np.pi * t / secondi * 7 + 1)
    bolle = np.zeros(n)
    for _ in range(int(secondi * 3)):
        i = rng.integers(0, n - 6000)
        f = rng.uniform(60, 140)
        tt = np.arange(6000) / SR
        bolle[i:i + 6000] += np.sin(2 * np.pi * f * tt * (1 + tt * 2)) * np.exp(-tt * 18) * rng.uniform(0.2, 0.6)
    x = b * mod + bolle * 0.4
    # dissolvenza incrociata tra fine e inizio, per il ciclo senza stacchi
    m = int(SR * 1.5)
    w = np.linspace(0, 1, m)
    x[:m] = x[:m] * w + x[-m:] * (1 - w)
    return x[:-m]


def main():
    src = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    S = lambda n: sorgente(src, n)
    caverna = 'aecho=0.8:0.75:70|160|320:0.4|0.25|0.12,lowpass=f=5000'
    balrog = 'lowpass=f=3200,acompressor=threshold=0.2:ratio=6,' + caverna
    corto = ',atrim=0:3.6,afade=t=out:st=2.6:d=1'
    # il Balrog
    for i, n in enumerate(['CREAHmn_GiantEffort_OS_01', 'CREAHmn_OgreEffort_OS_01', 'CREAHmn_TrollEffort_OS_01'], 1):
        elabora(S(n), f'{OUT}/balrog_ruggito_{i}.ogg', 0.6, balrog + corto)
    elabora(S('CREAHmn_GiantDeathScream_OS_01'), f'{OUT}/balrog_ruggito_forte.ogg', 0.62, balrog)
    for i, n in enumerate(['CREAHmn_GiantHurt_OS_01', 'CREAHmn_GiantHurt_OS_02', 'CREAHmn_OgreHurt_OS_01', 'CREAHmn_TrollHurt_OS_02'], 1):
        elabora(S(n), f'{OUT}/balrog_dolore_{i}.ogg', 0.66, balrog + corto)
    elabora(S('CREAHmn_OgreDeathScream_OS_01'), f'{OUT}/balrog_caduta.ogg', 0.55,
            balrog + ',aecho=0.8:0.6:500|900:0.4|0.25')
    elabora(S('CREAHmn_GiantLaugh_OS_01'), f'{OUT}/balrog_vittoria.ogg', 0.62, balrog)
    # Gandalf
    for i, n in enumerate(['VOXEfrt_Male01Effort_OS_01', 'VOXEfrt_Male02Effort_OS_01'], 1):
        elabora(S(n), f'{OUT}/gandalf_sforzo_{i}.ogg', 0.9, 'aecho=0.8:0.5:60:0.2')
    for i, n in enumerate(['VOXMale_Male01Hurt_OS_01', 'VOXMale_Male01Hurt_OS_02', 'VOXMale_Male02Hurt_OS_01'], 1):
        elabora(S(n), f'{OUT}/gandalf_dolore_{i}.ogg', 0.9, 'aecho=0.8:0.5:60:0.2')
    elabora(S('VOXMale_Male01DeathScream_OS_01'), f'{OUT}/gandalf_caduta.ogg', 0.9,
            'aecho=0.8:0.6:400|800:0.4|0.25')
    # effetti
    elabora(S('MAGSpel_MagicSpell_OS_01'), f'{OUT}/magia_1.ogg', 1.0, caverna, 0.8)
    elabora(S('MAGSpel_MagicSpell_OS_02'), f'{OUT}/magia_2.ogg', 0.85, caverna, 0.8)
    elabora(S('DSGNImpt_ImpactCreepyReverb_OS_01'), f'{OUT}/impatto.ogg', 0.8)
    elabora(S('FGHTImpt_PunchHardest_OS_01'), f'{OUT}/colpo.ogg', 0.7, caverna)
    elabora(S('METLImpt_HammerAnvil_OS_01'), f'{OUT}/parata.ogg', 1.0, caverna, 0.7)
    elabora(S('WHSH_WhooshMedium_OS_01'), f'{OUT}/soffio_1.ogg', 0.75)
    elabora(S('SWSH_Swoosh_OS_02'), f'{OUT}/carta.ogg', 1.1, '', 0.5)
    elabora(S('FEETHmn_ShoeConcreteLand_OS_01'), f'{OUT}/passo.ogg', 0.7, caverna)
    elabora(S('MUSCStngr_VictoryOrchestral_OS_01'), f'{OUT}/musica_vittoria.ogg')
    elabora(S('MUSCStngr_LossOrchestral_OS_01'), f'{OUT}/musica_sconfitta.ogg')
    elabora(S('DSGNDron_DroneCreepy_OS_01'), f'{OUT}/drone.ogg', 0.8, 'lowpass=f=2000', 0.6)
    rng = np.random.default_rng(11)
    scrivi(f'{OUT}/fulmine.ogg', fulmine(rng))
    scrivi(f'{OUT}/frusta.ogg', schiocco(rng))
    scrivi(f'{OUT}/fuoco.ogg', fuoco(rng))
    scrivi(f'{OUT}/lava.ogg', lava(rng))
    print('suoni scritti in', OUT)


if __name__ == '__main__':
    main()
