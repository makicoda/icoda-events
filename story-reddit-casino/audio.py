"""Synthesize a soundtrack for a scene from its cues, then mux it into the video.

    python render.py scenes/pilot-tabloid.html --cues out/tabloid.cues.json
    python audio.py out/tabloid.cues.json --style tabloid --video out/x.mp4 --out out/x_sound.mp4

Everything is generated here (numpy/scipy): no stock music, so no licence questions, and every SFX lands on the
frame its cue came from. Each style = a music bed (tempo, harmony, drums) + a mapping from cue types to SFX.
"""
import argparse, json, pathlib, subprocess

import imageio_ffmpeg
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
FF = imageio_ffmpeg.get_ffmpeg_exe()
rng = np.random.default_rng(11)


# ---------------------------------------------------------------- primitives
def tt(d): return np.arange(int(d * SR)) / SR
def midi(n): return 440.0 * 2 ** ((n - 69) / 12)
def env(d, a=0.005, k=6.0):
    """attack a seconds, then exponential decay to ~e^-k by the end"""
    t = tt(d); e = np.exp(-k * t / d)
    na = max(1, int(a * SR)); e[:na] *= np.linspace(0, 1, na)
    return e
def sine(f, d, ph=0): return np.sin(2 * np.pi * np.cumsum(np.broadcast_to(f, (int(d * SR),))) / SR + ph)
def saw(f, d):
    p = np.cumsum(np.broadcast_to(f, (int(d * SR),))) / SR
    return 2 * (p - np.floor(p + 0.5))
def noise(d): return rng.uniform(-1, 1, int(d * SR))
def filt(x, kind, f, order=2):
    sos = signal.butter(order, f, btype=kind, fs=SR, output='sos')
    return signal.sosfilt(sos, x)
def sweep_bp(x, f0, f1, q=1.5, steps=48):
    """band-pass whose centre glides f0→f1 (processed in short blocks, filter state carried over)"""
    out = np.zeros_like(x); n = len(x); edges = np.linspace(0, n, steps + 1).astype(int); zi = None
    for i in range(steps):
        fc = f0 * (f1 / f0) ** (i / max(1, steps - 1)); bw = fc / q
        sos = signal.butter(2, [max(30, fc - bw / 2), min(SR / 2 - 100, fc + bw / 2)], btype='band', fs=SR, output='sos')
        if zi is None: zi = signal.sosfilt_zi(sos) * 0
        out[edges[i]:edges[i + 1]], zi = signal.sosfilt(sos, x[edges[i]:edges[i + 1]], zi=zi)
    return out
def reverb_ir(d=1.6, decay=4.0, bright=6000):
    ir = filt(noise(d), 'lowpass', bright) * np.exp(-decay * tt(d) / d)
    ir[0] = 1.0
    return ir / np.abs(ir).sum() * 6

class Mix:
    def __init__(self, dur):
        self.n = int(dur * SR) + SR; self.L = np.zeros(self.n); self.R = np.zeros(self.n)
    def add(self, x, t, gain=1.0, pan=0.0):
        i = int(t * SR)
        if i >= self.n or len(x) == 0: return
        x = x[: self.n - i] * gain
        self.L[i:i + len(x)] += x * np.sqrt(0.5 * (1 - pan)); self.R[i:i + len(x)] += x * np.sqrt(0.5 * (1 + pan))
    def bus(self): return np.stack([self.L, self.R])

def verb(st, ir, wet):
    return st * (1 - wet) + np.stack([signal.fftconvolve(c, ir)[: st.shape[1]] for c in st]) * wet


# ---------------------------------------------------------------- instruments & drums
def kick2(d=0.45, f0=150, f1=45, drive=1.6):
    t = tt(d); f = f1 + (f0 - f1) * np.exp(-t / 0.035)
    body = np.tanh(drive * sine(f, d) * np.exp(-t / 0.22))
    click = np.zeros_like(body); c = filt(noise(0.004), 'highpass', 3000) * 0.4; click[:len(c)] = c
    return body + click
def snare(d=0.22, tone=190):
    return filt(noise(d), 'bandpass', [1400, 7000]) * env(d, 0.001, 9) * 0.9 + sine(tone, d) * env(d, 0.001, 14) * 0.5
def hat(d=0.05, open_=False):
    d = 0.22 if open_ else d
    return filt(noise(d), 'highpass', 7500) * env(d, 0.0005, 7 if open_ else 10)
def rim(d=0.06):
    return filt(noise(d), 'bandpass', [1800, 3200]) * env(d, 0.0005, 12) + sine(1700, d) * env(d, 0.0005, 18) * 0.3
def pad(notes, d, cutoff=900, detune=0.006, a=1.2):
    x = sum(saw(midi(n) * (1 + k * detune), d) for n in notes for k in (-1, 0, 1)) / (3 * len(notes))
    e = np.minimum(1, tt(d) / a) * np.minimum(1, (d - tt(d)) / 0.8)
    return filt(x, 'lowpass', cutoff, 2) * e
def pluck_bass(n, d=0.3, cutoff=700, k=5):
    x = saw(midi(n), d) * 0.7 + sine(midi(n), d) * 0.6
    return filt(x, 'lowpass', cutoff) * env(d, 0.003, k)
def kalimba(n, d=0.9):
    f = midi(n)
    return (sine(f, d) + 0.25 * sine(f * 2.76, d) * env(d, 0.001, 18) + 0.12 * sine(f * 5.4, d) * env(d, 0.001, 30)) * env(d, 0.002, 6)
def epiano(notes, d=1.4):
    out = 0
    for n in notes:
        f = midi(n); t = tt(d); idx = 1.8 * np.exp(-t / 0.25)
        out = out + np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) * env(d, 0.004, 4)
    return out / len(notes)
def brass(notes, d=0.5):
    x = sum(saw(midi(n) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * tt(d))), d) for n in notes) / len(notes)
    e = env(d, 0.012, 4.5)
    return filt(x, 'lowpass', 2600) * e
def timp(d=0.9, f=70):
    t = tt(d); return sine(f * (1 + 0.15 * np.exp(-t / 0.05)), d) * env(d, 0.002, 5) + filt(noise(d), 'lowpass', 400) * env(d, 0.001, 20) * 0.4


# ---------------------------------------------------------------- SFX
def key_click():
    d = 0.03; c = filt(noise(d), 'bandpass', [1800 + rng.uniform(-300, 600), 6000]) * env(d, 0.0003, 14)
    return c + sine(rng.uniform(380, 520), d) * env(d, 0.0003, 20) * 0.15
def beep(f, d=0.05, sq=True):
    x = np.sign(sine(f, d)) * 0.5 if sq else sine(f, d)
    return filt(x, 'lowpass', 5000) * env(d, 0.002, 4)
def whoosh(d=0.3, f0=300, f1=5000):
    x = sweep_bp(noise(d), f0, f1, q=1.2); e = np.sin(np.pi * tt(d) / d) ** 1.5
    return x * e * 2.2
def glitch(d=0.14):
    x = noise(d); hold = 1 + rng.integers(4, 30)  # sample-and-hold bitcrush
    x = np.repeat(x[::hold], hold)[: int(d * SR)]
    x = np.round(x * 6) / 6
    return filt(x, 'bandpass', [300, 6000]) * env(d, 0.001, 3) * 0.8 + kick2(d, 120, 50) * 0.5
def slap(big=True):
    d = 0.35
    body = kick2(d, 110, 55, 2.2) * (0.9 if big else 0.6)
    smack = filt(noise(0.09), 'bandpass', [900, 4500]) * env(0.09, 0.0005, 8) * (1.3 if big else 0.9)
    out = body.copy(); out[: len(smack)] += smack
    return out
def scribble(d=0.5):
    x = filt(noise(d), 'bandpass', [2500, 6500]); lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 17 * tt(d))
    return x * lfo * np.minimum(1, tt(d) / 0.03) * np.minimum(1, (d - tt(d)) / 0.08) * 0.8
def pop(f0=600, f1=1300, d=0.07):
    t = tt(d); return sine(f0 + (f1 - f0) * t / d, d) * env(d, 0.001, 6)
def roller(d=0.5):
    x = filt(noise(d), 'lowpass', 2600) * 0.6 + filt(noise(d), 'bandpass', [150, 400]) * 0.5
    e = np.minimum(1, tt(d) / 0.02) * np.exp(-2.2 * tt(d) / d)
    clicks = np.zeros(int(d * SR))
    for k in np.arange(0, d, 1 / 12):
        c = filt(noise(0.012), 'bandpass', [1500, 5000]) * env(0.012, 0.0003, 10) * 0.5
        i = int(k * SR); clicks[i:i + len(c)] += c[: len(clicks) - i]
    return x * e + clicks
def paper_slide(d=0.4):
    return sweep_bp(noise(d), 700, 2600, q=1.0) * np.sin(np.pi * tt(d) / d) * 1.6
def mouse_click():
    a = filt(noise(0.012), 'bandpass', [2000, 7000]) * env(0.012, 0.0002, 10)
    out = np.zeros(int(0.09 * SR)); out[: len(a)] += a; out[int(0.07 * SR): int(0.07 * SR) + len(a)] += a * 0.6
    return filt(out, 'lowpass', 6000) * 0.5
def shimmer(notes, d=2.2):
    return sum(sine(midi(n), d) * env(d, 0.01, 5) for n in notes) / len(notes)


# ---------------------------------------------------------------- styles
GRID = None   # (bpm, offset) declared by the scene via M.music(); overrides each style's default tempo

def grid(bpm, offset, dur):
    if GRID: bpm, offset = GRID
    b = 60 / bpm; return b, np.arange(offset, dur, b)

def style_terminal(cues, dur):
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(84, 0.15, dur)
    first_cut = next((c['t'] for c in cues if c['type'] == 'cut'), 3.0)
    end_t = next((c['t'] for c in cues if c['type'] == 'logo'), dur - 3)
    # A-minor drone that opens up over the piece
    mus.add(pad([45, 52, 57], dur + 1, cutoff=500, a=2.0), 0, 0.55)
    mus.add(pad([57, 60, 64], dur - first_cut + 1, cutoff=1200, a=1.5), first_cut, 0.25)
    for i, t in enumerate(beats):
        if first_cut - 0.05 <= t < end_t:
            mus.add(kick2(0.4, 130, 42), t, 0.75)
            for k in range(2):                    # 8th-note sidechained sub pulse
                mus.add(pluck_bass(33, b / 2 * 0.95, 380), t + k * b / 2, 0.55)
            for k in range(4):
                mus.add(hat(0.03), t + k * b / 4, 0.10 + 0.06 * (k % 2), pan=0.3)
        if first_cut <= t < end_t and i % 2 == 0:  # quiet data arpeggio
            for k, n in enumerate([69, 72, 76, 81]):
                mus.add(beep(midi(n), 0.06, sq=False), t + k * b / 4, 0.05, pan=-0.4 + 0.25 * k)
    mus.add(shimmer([69, 76, 81, 88], 3.0), end_t, 0.25)
    for c in cues:
        t, ty = c['t'], c['type']
        if ty == 'type':
            for k in range(c['n']):
                sfx.add(key_click(), t + k / c['cps'] + rng.uniform(-0.006, 0.006), 0.45, pan=rng.uniform(-0.3, 0.3))
        elif ty == 'decode':
            for k in np.arange(0, c['d'], 0.035):
                sfx.add(beep(rng.choice([880, 1175, 1320, 1568, 1760, 2093]), 0.03), t + k, 0.12, pan=rng.uniform(-0.5, 0.5))
        elif ty == 'bar':
            n = c.get('n', 24)
            for k in range(n):
                sfx.add(beep(midi(64 + k // 3), 0.025, sq=False), t + k * c['d'] / n, 0.10)
        elif ty == 'open': sfx.add(pop(1400, 500, 0.09), t, 0.35)
        elif ty == 'blip': sfx.add(beep(1568, 0.06), t, 0.25)
        elif ty == 'confirm': sfx.add(np.concatenate([beep(1320, 0.05), beep(1760, 0.07)]), t, 0.22)
        elif ty == 'cut': sfx.add(glitch(), t - 0.04, 0.8)
        elif ty == 'logo': sfx.add(kick2(0.8, 90, 38) * 0.8, t, 0.7)
        elif ty == 'enter':
            sfx.add(key_click() * 2, t, 0.7); sfx.add(shimmer([81, 88, 93], 1.4), t + 0.05, 0.3)
        elif ty == 'click': sfx.add(mouse_click(), t, 0.6)
    return mus, sfx, dict(ir=reverb_ir(1.2, 5, 5000), wet_m=0.18, wet_s=0.10, music_gain=0.9)

def style_tabloid(cues, dur):
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(120, 0.0, dur)
    end_t = next((c['t'] for c in cues if c['type'] == 'logo'), dur - 3)
    bassline = [36, 36, 39, 36, 43, 36, 41, 39]  # C minor, 8ths
    # sustained C-minor organ bed so the groove never drops to silence between hits; rings through the end card
    mus.add(pad([48, 55, 60, 63], dur + 0.5, cutoff=1600, detune=0.004, a=0.3), 0, 0.30)
    mus.add(pad([67, 72, 75], end_t, cutoff=2400, detune=0.003, a=0.6), 0, 0.10)
    for i, t in enumerate(beats):
        if t >= end_t: break
        bar_pos = i % 4
        mus.add(kick2(0.35, 160, 48, 2.0), t, 0.9 if bar_pos in (0, 2) else 0.0)
        if bar_pos in (1, 3): mus.add(snare(), t, 0.55, pan=0.05)
        for k in range(2):
            mus.add(hat(0.045), t + k * b / 2, 0.16, pan=-0.25)
            mus.add(pluck_bass(bassline[(i * 2 + k) % 8], b / 2 * 0.98, 900, k=2.5), t + k * b / 2, 0.45)
        if i % 8 == 7: mus.add(hat(open_=True), t + b / 2, 0.14, pan=0.25)
    # final hit: brass + timpani on the end card, then ring out
    mus.add(brass([48, 55, 60, 63], 1.4), end_t, 0.55); mus.add(timp(1.6, 65), end_t, 0.7)
    for c in cues:
        t, ty = c['t'], c['type']
        if ty == 'sting':
            sfx.add(brass([60, 67, 72, 75], 0.55), t, 0.6); sfx.add(brass([63, 70, 75, 79], 0.7), t + 0.28, 0.6); sfx.add(timp(1.0, 73), t, 0.6)
        elif ty == 'slap': sfx.add(slap(c.get('big', True)), t, 0.85, pan=rng.uniform(-0.15, 0.15))
        elif ty == 'whip': sfx.add(whoosh(0.32, 250, 6000), t - 0.06, 0.7, pan=0.0)
        elif ty == 'scribble': sfx.add(scribble(c.get('d', 0.5)), t, 0.35)
        elif ty == 'pop': sfx.add(pop(), t, 0.25, pan=rng.uniform(-0.4, 0.4))
        elif ty == 'click': sfx.add(mouse_click(), t, 0.7)
    return mus, sfx, dict(ir=reverb_ir(0.9, 6, 7000), wet_m=0.12, wet_s=0.16, music_gain=0.75)

def style_riso(cues, dur):
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(90, 0.0, dur)
    end_t = next((c['t'] for c in cues if c['type'] == 'logo'), dur - 3)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 65]]  # Cmaj7 Am7 Fmaj7 G7
    melody = [76, None, 79, 76, 74, None, 72, 74, 76, None, 72, None, 69, 72, None, 74]
    for i, t in enumerate(beats):
        bar, pos = i // 4, i % 4
        if pos == 0: mus.add(epiano(chords[bar % 4], b * 4), t, 0.32)
        if t < end_t:
            if pos in (0, 2): mus.add(kick2(0.4, 110, 45, 1.2), t + (0.04 if pos == 2 else 0), 0.55)
            if pos in (1, 3): mus.add(rim(), t, 0.35, pan=0.15)
            mus.add(hat(0.04), t + b / 2, 0.08, pan=-0.3)
            for k in range(2):
                n = melody[(i * 2 + k) % 16]
                if n and t > 0.5: mus.add(kalimba(n, 0.8), t + k * b / 2, 0.16, pan=0.25)
    crackle = np.zeros(int((dur + 1) * SR))
    for _ in range(int(dur * 18)):
        i = rng.integers(0, len(crackle) - 200); crackle[i:i + 60] += filt(noise(60 / SR), 'highpass', 3000) * rng.uniform(0.1, 0.6)
    mus.add(crackle + filt(noise(dur + 1), 'lowpass', 1200) * 0.02, 0, 0.5)
    mus.add(kalimba(84, 2.0), end_t + 0.3, 0.3); mus.add(kalimba(88, 2.0), end_t + 0.45, 0.25)
    for c in cues:
        t, ty = c['t'], c['type']
        if ty == 'print': sfx.add(roller(max(0.3, c.get('d', 0.5))), t, 0.45, pan=rng.uniform(-0.2, 0.2))
        elif ty == 'stamp': sfx.add(slap(True) * 0.8, t, 0.7)
        elif ty == 'sheet': sfx.add(paper_slide(0.42), t - 0.05, 0.7)
        elif ty == 'dots': sfx.add(pop(300, 700, 0.12), t, 0.3)
        elif ty == 'scribble': sfx.add(scribble(c.get('d', 0.6)), t, 0.4)
        elif ty == 'click': sfx.add(mouse_click(), t, 0.7)
    return mus, sfx, dict(ir=reverb_ir(1.4, 4.5, 4500), wet_m=0.22, wet_s=0.08, music_gain=0.85)


def style_keynote(cues, dur):
    """Product-reveal mood: warm D-major pad, a soft heartbeat pulse, glassy chimes; swipes left fall, swipes right rise."""
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(100, 0.0, dur)
    T = {c['type']: c['t'] for c in cues}
    fades = [c['t'] + 0.25 for c in cues if c['type'] == 'fade']
    match_t = T.get('match', dur * 0.55); end_t = T.get('logo', dur - 3.5)
    # chord changes land on the scene changes (dips to black)
    marks = [0] + fades + [dur + 1]
    prog = [[50, 57, 62, 66], [47, 54, 59, 62], [43, 55, 59, 62], [45, 57, 61, 64], [43, 55, 59, 62], [50, 57, 62, 66, 69]]
    for i in range(len(marks) - 1):
        a, z = marks[i], marks[i + 1]; ch = prog[min(i, len(prog) - 1)]
        mus.add(pad(ch, z - a + 0.6, cutoff=1300 if a < match_t else 2200, detune=0.003, a=0.5), a, 0.45)
        mus.add(sum(sine(midi(n + 12), z - a + 0.6) for n in ch[:3]) / 3 * np.minimum(1, tt(z - a + 0.6) / 0.6), a, 0.08)
    for i, t in enumerate(beats):
        if t >= end_t + 1.5: break
        mus.add(sine(midi(38), 0.22) * env(0.22, 0.004, 5), t, 0.35 if i % 2 == 0 else 0.2)   # heartbeat sub
        if t >= fades[1] if len(fades) > 1 else False:
            for k in range(4): mus.add(hat(0.025), t + k * b / 4, 0.05 + 0.03 * (k % 2), pan=0.35)
    for c in cues:
        t, ty = c['t'], c['type']
        if ty == 'reveal':
            sw = filt(noise(1.4), 'lowpass', 900) * np.minimum(1, tt(1.4) / 1.1) * np.exp(-tt(1.4) * 0.5) * 0.5
            sfx.add(sw + sine(midi(26), 1.4) * env(1.4, 0.6, 3) * 0.6, t, 0.6)
        elif ty == 'swipeL':
            sfx.add(whoosh(0.28, 2200, 380) * 0.6, t - 0.04, 0.55, pan=-0.5); sfx.add(sine(midi(43), 0.3) * env(0.3, 0.003, 7), t + 0.05, 0.35)
        elif ty == 'swipeR':
            sfx.add(whoosh(0.32, 400, 3200) * 0.6, t - 0.04, 0.6, pan=0.5); sfx.add(beep(midi(86), 0.12, sq=False), t + 0.2, 0.18, pan=0.4)
        elif ty == 'photo': sfx.add(mouse_click(), t, 0.5)
        elif ty == 'match':
            for k, n in enumerate([74, 78, 81, 86, 90]):
                sfx.add(kalimba(n, 1.6) * 0.9, t + k * 0.07, 0.22, pan=-0.4 + 0.2 * k)
            sfx.add(kick2(1.0, 80, 34, 1.0), t, 0.5)
        elif ty == 'tile': sfx.add(beep(midi(81), 0.05, sq=False), t, 0.12)
        elif ty == 'logo': sfx.add(shimmer([62, 69, 74, 78], 2.6), t, 0.22)
        elif ty == 'click': sfx.add(mouse_click(), t, 0.7)
    return mus, sfx, dict(ir=reverb_ir(2.2, 3.5, 5000), wet_m=0.25, wet_s=0.2, music_gain=0.8)

def style_clean(cues, dur):
    """ICODA light: bright modern tech-pop. Fmaj7-Am7-Dm7-C, one chord per bar, plucked arpeggios, airy pad,
    four-on-the-floor that only starts at the 'drop' cue (or the first cut), whooshes landing on every cut."""
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(88, 0.0, dur)
    drop = next((c['t'] for c in cues if c['type'] == 'drop'), next((c['t'] for c in cues if c['type'] == 'cut' and c['t'] > 0.5), 0))
    end_t = next((c['t'] for c in cues if c['type'] == 'logo'), dur - 3)
    chords = [[53, 57, 60, 64], [57, 60, 64, 67], [50, 53, 57, 60], [48, 52, 55, 60]]
    roots = [41, 45, 38, 36]
    for i, t in enumerate(beats):
        bar, pos = i // 4, i % 4
        ch = chords[bar % 4]
        if pos == 0:
            mus.add(pad(ch, b * 4 + 0.4, cutoff=1500 if t < drop else 2600, detune=0.004, a=0.25), t, 0.32)
        live = drop - 0.01 <= t < end_t
        for k in range(4):                                    # 16th-note pluck arpeggio, quieter before the drop
            n = ch[(k + pos * 2) % 4] + 12
            x = filt(saw(midi(n), 0.16) * 0.6 + sine(midi(n), 0.16), 'lowpass', 2800) * env(0.16, 0.002, 7)
            mus.add(x, t + k * b / 4, (0.11 if live else 0.06), pan=-0.3 + 0.2 * k)
        if live:
            mus.add(kick2(0.4, 140, 45, 1.6), t, 0.8)
            if pos in (1, 3):
                mus.add(snare(0.2, 210) * 0.7, t, 0.42, pan=0.05)
                mus.add(filt(noise(0.12), 'bandpass', [900, 2500]) * env(0.12, 0.001, 8) * 0.5, t, 0.42, pan=-0.05)
            for k in range(2): mus.add(hat(0.035), t + k * b / 2 + b / 4, 0.12, pan=0.3)
            for k in range(2): mus.add(pluck_bass(roots[bar % 4], b / 2 * 0.95, 700, k=3), t + k * b / 2, 0.42)
    mus.add(shimmer([65, 72, 77, 84], 3.2), end_t, 0.22)
    mus.add(pad([41, 53, 60, 64, 69], max(0.5, dur - end_t + 0.5), cutoff=2000, a=0.4), end_t, 0.3)
    for c in cues:
        t, ty = c['t'], c['type']
        if ty == 'cut' and t > 0.2: sfx.add(whoosh(0.34, 400, 4200), t - 0.24, 0.42)   # whoosh peaks on the beat
        elif ty == 'drop':
            sfx.add(kick2(0.9, 90, 36, 1.2), t, 0.8); sfx.add(filt(noise(0.9), 'lowpass', 900) * env(0.9, 0.002, 4) * 0.4, t, 0.8)
        elif ty == 'card': sfx.add(whoosh(0.4, 900, 2200) * 0.5, t, 0.22, pan=0.2)
        elif ty == 'pop': sfx.add(pop(700, 1400, 0.06), t, 0.14, pan=rng.uniform(-0.4, 0.4))
        elif ty == 'count':
            d = c.get('d', 1.0)
            for k in np.arange(0, d * 0.8, 0.045):
                sfx.add(beep(2400 + k * 900, 0.012, sq=False), t + k, 0.035 * (1 - k / d), pan=0.2)
        elif ty == 'draw':
            d = c.get('d', 1.0); sfx.add(sweep_bp(noise(d), 600, 1800, q=2) * np.sin(np.pi * tt(d) / d), t, 0.12)
        elif ty == 'type':
            for k in range(c['n']): sfx.add(key_click(), t + k / c['cps'], 0.25, pan=rng.uniform(-0.3, 0.3))
        elif ty == 'burst':
            sfx.add(whoosh(0.9, 200, 6000) * 0.8, t - 0.1, 0.7); sfx.add(kick2(0.9, 70, 32, 1.4) * 0.8, t, 0.7)
        elif ty == 'logo': sfx.add(kick2(0.8, 80, 34, 1.0), t, 0.5)
        elif ty == 'click': sfx.add(mouse_click(), t, 0.7)
    return mus, sfx, dict(ir=reverb_ir(1.6, 4.0, 6000), wet_m=0.2, wet_s=0.12, music_gain=0.8)

def bloop(n, d=0.11):
    """soft digital blip: a sine that drops into pitch fast, with a quiet fifth on top"""
    t = tt(d); f = midi(n) * (1 + 0.55 * np.exp(-t / 0.012))
    return (sine(f, d) + 0.25 * sine(f * 1.5, d)) * env(d, 0.001, 7)

def ui_tone(n, d=0.22, bend=0.0, bright=4200):
    """one rounded UI note: sine + soft octave, optional pitch bend (semitones over the note), lowpassed"""
    t = tt(d); f = midi(n) * 2 ** (bend * t / d / 12)
    x = sine(f, d) + 0.18 * sine(f * 2, d) * env(d, 0.001, 9)
    return filt(x, 'lowpass', bright) * env(d, 0.004, 5)

def chime_pos():
    """'connected' — two notes up a fourth, bright, a little shimmer on top (USB-in / call-join family)"""
    out = np.zeros(int(0.9 * SR)); a = ui_tone(81, 0.22, bright=6000); b = ui_tone(86, 0.5, bright=6500)
    i = int(0.085 * SR); out[:len(a)] += a; out[i:i + len(b)] += b * 1.05
    sh = shimmer([93, 98], 0.6) * 0.18; out[i:i + len(sh)] += sh
    return out

def chime_neg():
    """'disconnected' — two notes down, the second sagging in pitch, darker, with a soft low thunk (USB-out / call-end)"""
    out = np.zeros(int(0.9 * SR)); a = ui_tone(79, 0.2, bright=3200); b = ui_tone(72, 0.42, bend=-0.6, bright=2400)
    i = int(0.11 * SR); out[:len(a)] += a; out[i:i + len(b)] += b
    th = kick2(0.3, 120, 60, 0.8) * 0.35; out[i:i + len(th)] += th
    return out

def style_ambient(cues, dur):
    """Article explainers (silent by default, sound on demand): warm D-major pad that changes chord on every
    'step', an airy texture, and — from the first step — a quiet sub pulse, an 8th-note digital pluck arpeggio
    and whisper ticks. Pops become rate-limited bloops walking up a pentatonic scale; steps get a soft whoosh
    and a kalimba chime; 'sparkle' is a bright arpeggio; 'logo' resolves to the home chord."""
    mus, sfx = Mix(dur), Mix(dur)
    b, beats = grid(84, 0.0, dur)
    steps = sorted(c['t'] for c in cues if c['type'] == 'step')
    end_t = next((c['t'] for c in cues if c['type'] == 'logo'), dur - 4)
    first = steps[0] if steps else 0.0
    home, intro_ch = [50, 57, 62, 66, 69], [50, 57, 62, 64, 69]                  # Dadd9 / Dsus2
    prog = [[50, 57, 62, 66, 69], [47, 54, 59, 62, 66], [43, 50, 55, 59, 62], [45, 52, 57, 61, 64]]  # D Bm G A
    marks = [0.0] + steps + [end_t]
    chords = [intro_ch] + [prog[i % 4] for i in range(len(steps))] + [home]
    def chord_at(t):
        i = max(k for k, m in enumerate(marks) if m <= t + 1e-6)
        return chords[min(i, len(chords) - 1)]
    for i, a in enumerate(marks):
        z = marks[i + 1] if i + 1 < len(marks) else dur + 0.5
        L = z - a + 1.2; ch = chords[i]
        mus.add(pad(ch, L, cutoff=1150 + 900 * i / max(1, len(marks) - 1), detune=0.004, a=0.9), a, 0.13)   # pads sit far back (owner, Oct 2026)
        glass = sum(sine(midi(n + 12), L) for n in ch[1:4]) / 3
        mus.add(glass * np.minimum(1, tt(L) / 1.0) * np.minimum(1, (L - tt(L)) / 1.0), a, 0.03)
    air = filt(noise(dur + 1), 'bandpass', [2500, 7500]) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * tt(dur + 1)))
    mus.add(air, 0, 0.018)
    for i, t in enumerate(beats):
        if t < first - 0.01 or t >= end_t - 0.01: continue
        ch = chord_at(t)
        mus.add(sine(midi(ch[0] - 12), 0.28) * env(0.28, 0.004, 5), t, 0.20)                 # soft sub pulse
        for k in range(2):                                                                    # digital pluck arpeggio
            n = ch[(i * 2 + k) % len(ch)] + 12
            x = filt(sine(midi(n), 0.24) * 0.8 + saw(midi(n), 0.24) * 0.3, 'lowpass', 4200) * env(0.24, 0.002, 7)
            mus.add(x, t + k * b / 2, 0.085, pan=-0.35 + 0.7 * (((i * 2 + k) % 4) / 3))
        for k in range(4): mus.add(hat(0.018), t + k * b / 4, 0.028 + 0.014 * (k % 2), pan=0.3)   # whisper ticks
    mus.add(shimmer([74, 78, 81, 86], 3.4), end_t + 0.35, 0.16)
    scale = [74, 76, 78, 81, 83, 86, 88, 90]
    last_pop, last_draw, pi = -1.0, -1.0, 0
    for c in sorted(cues, key=lambda c: c['t']):
        t, ty = c['t'], c['type']
        if ty == 'pop':
            if t - last_pop < 0.085: continue                                                  # 60 nodes must not become a rattle
            last_pop = t; sfx.add(bloop(scale[pi % len(scale)]), t, 0.085, pan=rng.uniform(-0.45, 0.45)); pi += 1
        elif ty == 'draw':
            if t - last_draw < 0.6: continue
            last_draw = t; d = min(1.2, c.get('d', 0.8))
            sfx.add(sweep_bp(noise(d), 900, 3000, q=2.5) * np.sin(np.pi * tt(d) / d), t, 0.035, pan=rng.uniform(-0.3, 0.3))
        elif ty == 'step':
            sfx.add(whoosh(0.6, 450, 3200) * 0.5, t - 0.32, 0.15)
            top = chord_at(t + 0.05)
            sfx.add(kalimba(top[2] + 24, 1.4), t + 0.02, 0.09, pan=-0.2); sfx.add(kalimba(top[4] + 12, 1.4), t + 0.14, 0.07, pan=0.2)
        elif ty == 'intro':
            sw = filt(noise(1.8), 'lowpass', 1400) * np.minimum(1, tt(1.8) / 1.3) * np.exp(-tt(1.8) * 0.8)
            sfx.add(sw, t, 0.08)
            for k, n in enumerate([69, 74, 78, 81]): sfx.add(kalimba(n, 1.6), t + 0.25 + k * 0.13, 0.08, pan=-0.3 + 0.2 * k)
        elif ty == 'sparkle':
            for k, n in enumerate([81, 86, 90, 93, 98]): sfx.add(kalimba(n, 1.5), t + k * 0.06, 0.09, pan=-0.4 + 0.2 * k)
            sfx.add(shimmer([86, 93, 98], 1.8), t, 0.06)
        elif ty == 'card': sfx.add(whoosh(0.45, 900, 2400) * 0.4, t, 0.10, pan=0.2)
        elif ty == 'type':
            for k in range(c['n']): sfx.add(key_click(), t + k / c['cps'], 0.10, pan=rng.uniform(-0.3, 0.3))
        elif ty == 'pos': sfx.add(chime_pos(), t, 0.15 * c.get('level', 1.0), pan=c.get('pan', 0.15))   # good news: up
        elif ty == 'neg': sfx.add(chime_neg(), t, 0.15 * c.get('level', 1.0), pan=c.get('pan', -0.15))  # bad news: down
        elif ty == 'logo':
            sfx.add(kick2(1.0, 70, 34, 0.9) * 0.6, t + 0.3, 0.30)
            for k, n in enumerate([62, 69, 74, 78]): sfx.add(kalimba(n, 2.0), t + 0.9 + k * 0.09, 0.07, pan=-0.3 + 0.2 * k)
    return mus, sfx, dict(ir=reverb_ir(2.2, 3.8, 5500), wet_m=0.3, wet_s=0.26, music_gain=0.85)

STYLES = {'clean': style_clean, 'terminal': style_terminal, 'tabloid': style_tabloid, 'riso': style_riso, 'keynote': style_keynote,
          'ambient': style_ambient}


# ---------------------------------------------------------------- licensed tracks
def load_track(path, dur):
    """decode any audio file to 48 kHz stereo float, trimmed/padded to dur"""
    raw = subprocess.run([FF, '-v', 'error', '-i', str(path), '-f', 's16le', '-ac', '2', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).reshape(-1, 2).T.astype(float) / 32768
    n = int(dur * SR)
    return x[:, :n] if x.shape[1] >= n else np.pad(x, ((0, 0), (0, n - x.shape[1])))

def analyze(path, start=0.0, length=60.0):
    """estimate (bpm, offset of the first beat) from low-frequency onsets; put them into M.music({track, bpm, offset})"""
    x = load_track(path, start + length).mean(0)[int(start * SR):]
    hop = 512; lo = filt(x, 'lowpass', 160, 4)
    e = np.array([np.sum(lo[i:i + hop] ** 2) for i in range(0, len(lo) - hop, hop)])
    on = np.maximum(0, np.diff(np.log(e + 1e-9))); on -= on.mean()
    fr = SR / hop
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    lags = np.arange(len(ac)) / fr
    ok = (lags > 60 / 180) & (lags < 60 / 70)
    period = lags[ok][np.argmax(ac[ok])]
    best, off = -1e9, 0.0
    for o in np.arange(0, period, 1 / fr):          # the phase that collects the most onset energy
        idx = (np.arange(o, len(on) / fr, period) * fr).astype(int)
        sc = on[idx[idx < len(on)]].sum()
        if sc > best: best, off = sc, o
    return round(60 / period, 2), round(start + off, 3)


# ---------------------------------------------------------------- build & mux
def build(data, style=None, track=None):
    """data = {duration, cues, music}; returns stereo float. SFX are always synthesized from the cues;
    the bed is the synth style, or a licensed track if one is given (SFX sit a little lower under it)."""
    global GRID
    dur, cues, mu = data['duration'], data['cues'], (data.get('music') or {})
    style = style or mu.get('style') or 'clean'
    track = track or mu.get('track')
    GRID = (mu['bpm'], mu.get('offset', 0)) if mu.get('bpm') else None
    mus, sfx, p = STYLES[style](cues, dur)
    s = verb(sfx.bus(), p['ir'], p['wet_s'])
    if track:
        m = load_track(track, dur + 1) * 0.9; s = s * 0.7
    else:
        m = verb(mus.bus(), p['ir'], p['wet_m']) * p['music_gain']
    n = int(dur * SR)
    m = m[:, :n] if m.shape[1] >= n else np.pad(m, ((0, 0), (0, n - m.shape[1])))
    out = m + s[:, :n]
    fade = int(0.6 * SR); out[:, -fade:] *= np.linspace(1, 0, fade)          # clean tail
    return np.tanh(out / max(1e-9, np.abs(out).max()) * 1.4) * 0.89        # gentle master saturation / limiter

def write_wav(out, path):
    wavfile.write(path, SR, (out.T * 32767).astype(np.int16)); return path

def render(cues_path, style, wav_path, track=None):
    return write_wav(build(json.loads(pathlib.Path(cues_path).read_text()), style, track), wav_path)


def mux(video, wav, out, abr='192k', lufs=-14):
    # -14 LUFS integrated is what Meta/YouTube normalise to; true peak kept under -1.5 dBTP
    subprocess.run([FF, '-y', '-v', 'error', '-i', str(video), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', f'loudnorm=I={lufs}:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', abr, '-ar', '48000', '-shortest',
                    '-movflags', '+faststart', str(out)], check=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='render.py scores every video itself; this CLI re-scores and analyses tracks')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build'); b.add_argument('cues'); b.add_argument('--style', choices=list(STYLES)); b.add_argument('--track')
    b.add_argument('--wav'); b.add_argument('--video'); b.add_argument('--out')
    an = sub.add_parser('analyze'); an.add_argument('track'); an.add_argument('--start', type=float, default=0)
    a = ap.parse_args()
    if a.cmd == 'analyze':
        bpm, off = analyze(a.track, a.start)
        print(f"bpm {bpm}  offset {off}  ->  M.music({{ track: '{a.track}', bpm: {bpm}, offset: {off} }})")
    else:
        wav = a.wav or str(pathlib.Path(a.cues).with_suffix('').with_suffix('.wav'))
        render(a.cues, a.style, wav, a.track); print(wav)
        if a.video: mux(a.video, wav, a.out); print(a.out)
