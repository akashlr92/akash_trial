#!/usr/bin/env python3
"""Synthesise a simple soundtrack for the stadium scene (needs numpy).

    python make_audio.py out.wav
"""
import sys
import wave
import numpy as np

SR, DUR = 44100, 20.0
t = np.arange(int(SR * DUR)) / SR
rng = np.random.default_rng(3)


def smooth(a, b, x):
    u = np.clip((x - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


def lowpass(x, k):          # cheap one-pole-ish smoothing via moving average
    return np.convolve(x, np.ones(k) / k, mode="same")


# warm pad: D minor -> F major -> D major lift at the title
def chord(freqs, env):
    s = sum(np.sin(2 * np.pi * f * t + i) + 0.4 * np.sin(2 * np.pi * f * 2.003 * t) for i, f in enumerate(freqs))
    return s / len(freqs) * env

pad = (chord([73.4, 146.8, 220.0, 293.7, 349.2], smooth(0, 3, t) * (1 - smooth(8.5, 10, t)))
       + chord([87.3, 174.6, 261.6, 349.2, 440.0], smooth(8.5, 10, t) * (1 - smooth(15.5, 17, t)))
       + chord([73.4, 146.8, 220.0, 293.7, 370.0, 587.3], smooth(15.5, 17, t)))
pad *= 0.20 * (1 + 0.08 * np.sin(2 * np.pi * 0.4 * t))
pad *= 1 + 0.7 * smooth(5, 9.5, t)                      # build towards the hit

# crowd: filtered noise, murmur -> roar after the hit
noise = rng.standard_normal(t.size)
crowd = lowpass(noise, 24) - lowpass(noise, 300)
level = 0.10 + 0.08 * smooth(6, 9.4, t) + 0.55 * smooth(9.55, 11.0, t) * (1 - 0.45 * smooth(13, 16, t))
crowd *= level * (1 + 0.15 * np.sin(2 * np.pi * 0.23 * t + 1) + 0.1 * np.sin(2 * np.pi * 0.61 * t))


def burst(at, decay, sig):
    d = t - at
    return np.where(d >= 0, np.exp(-np.maximum(d, 0) * decay), 0) * sig

# bat on ball
hit = burst(9.5, 55, rng.standard_normal(t.size) * 0.8 + np.sin(2 * np.pi * 950 * t)) * 0.7
hit += burst(9.5, 9, np.sin(2 * np.pi * 70 * t)) * 0.5

# whoosh as the ball flies
whoosh = lowpass(rng.standard_normal(t.size), 60) * smooth(9.5, 10.2, t) * (1 - smooth(11, 14.5, t)) * 0.9

# fireworks: thump + crackle
fw = np.zeros_like(t)
for at in (14.6, 15.3, 15.9, 16.6, 17.4, 18.1):
    fw += burst(at, 5, np.sin(2 * np.pi * 52 * t * (1 - 0.1 * np.clip(t - at, 0, 1)))) * 0.75
    fw += burst(at, 14, lowpass(rng.standard_normal(t.size), 6)) * 0.5
    crack = (rng.random(t.size) > 0.9993) * rng.standard_normal(t.size)
    fw += burst(at + 0.25, 2.2, np.convolve(crack, np.exp(-np.arange(200) / 25), mode="same")) * 0.35

mix = pad + crowd + hit + whoosh + fw
mix *= smooth(0, 1.2, t) * (1 - smooth(18.8, 20, t))
mix = np.tanh(mix * 1.1) * 0.85
stereo = np.stack([mix, np.roll(mix, 180)], axis=1)       # tiny delay for width

out = sys.argv[1] if len(sys.argv) > 1 else "stadium.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((stereo * 32767).astype("<i2").tobytes())
print("Saved", out)
