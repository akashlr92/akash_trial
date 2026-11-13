#!/usr/bin/env python3
"""generate — build a video from a JSON scene file using FFmpeg.

Usage:
    python scripts/generate.py examples/short.json
    python scripts/generate.py examples/short.json -o exports/test.mp4

See README.md for the scene file format.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

FORMATS = {"vertical": (1080, 1920), "landscape": (1920, 1080), "square": (1080, 1080)}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
FADE = 0.3


def ff(*args):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit("ffmpeg failed:\n  " + " ".join(cmd))


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def fpath(p):
    """Escape a file path for use inside an ffmpeg filter."""
    return os.path.abspath(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def tts(text, voice, out):
    """Make a voiceover with edge-tts (free Microsoft voices, needs internet)."""
    exe = shutil.which("edge-tts")
    if not exe:
        sys.exit('Scene uses "say" but edge-tts is not installed. Run: pip install edge-tts')
    r = subprocess.run([exe, "--voice", voice, "--text", text, "--write-media", out])
    if r.returncode:
        sys.exit("edge-tts failed (it needs an internet connection).")


def render_scene(i, sc, cfg, tmp):
    W, H = cfg["size"]
    fps = cfg["fps"]

    # ---- audio (voiceover) ----
    audio = sc.get("audio")
    if sc.get("say"):
        audio = os.path.join(tmp, f"say{i}.mp3")
        tts(sc["say"], sc.get("voice", cfg["voice"]), audio)
    dur = float(sc.get("duration", 0))
    if audio:
        dur = max(dur, duration_of(audio) + 0.6)
    if dur <= 0:
        dur = 4.0
    frames = int(round(dur * fps))

    # ---- background ----
    bg = sc.get("background", cfg["background"])
    ext = os.path.splitext(bg)[1].lower()
    inputs = []
    if ext in IMAGE_EXT:
        inputs = ["-i", bg]
        if sc.get("zoom", True):   # slow "Ken Burns" zoom
            vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='min(zoom+0.0010,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s={W}x{H}:fps={fps}")
        else:
            vf = (f"loop=-1:1,fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H}")
    elif ext in VIDEO_EXT:
        inputs = ["-stream_loop", "-1", "-i", bg]
        vf = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    else:  # treat as a colour, e.g. "#1e1e2e" or "navy"
        color = bg.replace("#", "0x")
        inputs = ["-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={fps}"]
        vf = "null"
    vf += ",setsar=1"

    # ---- text ----
    text = sc.get("text")
    if text:
        size = int(sc.get("font_size", cfg["font_size"]))
        chars = max(8, int(W / (size * 0.55)))
        wrapped = "\n".join(textwrap.fill(p, chars) for p in text.split("\n"))
        tfile = os.path.join(tmp, f"text{i}.txt")
        with open(tfile, "w", encoding="utf-8") as f:
            f.write(wrapped)
        y = {"top": "h*0.12", "center": "(h-text_h)/2", "bottom": "h*0.78-text_h"}[
            sc.get("position", cfg["position"])]
        font = sc.get("font", cfg.get("font"))
        fontarg = f"fontfile='{fpath(font)}':" if font else ""
        color = sc.get("text_color", cfg["text_color"]).replace("#", "0x")
        dt = (f"drawtext={fontarg}textfile='{fpath(tfile)}':fontsize={size}:fontcolor={color}"
              f":line_spacing={size // 4}:x=(w-text_w)/2:y={y}"
              f":borderw={max(2, size // 16)}:bordercolor=black@0.8")
        if sc.get("box", cfg["box"]):
            dt += f":box=1:boxcolor=black@0.45:boxborderw={size // 2}"
        vf += "," + dt

    vf += f",fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE},format=yuv420p"

    # ---- audio input ----
    if audio:
        inputs += ["-i", audio]
        af = f"[1:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]"
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        af = "[1:a]anull[a]"

    out = os.path.join(tmp, f"scene{i:03d}.mp4")
    ff(*inputs, "-filter_complex", f"[0:v]{vf}[v];{af}", "-map", "[v]", "-map", "[a]",
       "-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-c:a", "aac", "-b:a", "192k", "-ar", "44100", out)
    print(f"  scene {i + 1}: {dur:.1f}s")
    return out, bool(audio)


def main():
    p = argparse.ArgumentParser(description="Generate a video from a JSON scene file")
    p.add_argument("spec", help="Scene file, e.g. examples/short.json")
    p.add_argument("-o", "--output", help="Override the output path")
    a = p.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it first (see README).")

    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    if not spec.get("scenes"):
        sys.exit("The scene file needs a non-empty \"scenes\" list.")

    # Paths inside the scene file are relative to the repo root (where you run the command).
    fmt = spec.get("format", "vertical")
    cfg = {
        "size": FORMATS[fmt] if fmt in FORMATS else tuple(map(int, fmt.lower().split("x"))),
        "fps": int(spec.get("fps", 30)),
        "background": spec.get("background", "#111827"),
        "font": spec.get("font"),
        "font_size": spec.get("font_size", 72 if fmt == "vertical" else 64),
        "text_color": spec.get("text_color", "white"),
        "position": spec.get("position", "center"),
        "box": spec.get("box", False),
        "voice": spec.get("voice", "en-US-AriaNeural"),
    }
    output = a.output or spec.get("output", "exports/output.mp4")
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    print(f"Rendering {len(spec['scenes'])} scenes at {cfg['size'][0]}x{cfg['size'][1]}…")
    with tempfile.TemporaryDirectory() as tmp:
        parts, voiced = [], False
        for i, sc in enumerate(spec["scenes"]):
            path, has_voice = render_scene(i, sc, cfg, tmp)
            parts.append(path)
            voiced |= has_voice

        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            f.writelines(f"file '{p}'\n" for p in parts)
        joined = os.path.join(tmp, "joined.mp4")
        ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)

        music = spec.get("music")
        if music:
            vol = float(spec.get("music_volume", 0.15))
            if voiced:  # music dips automatically under the voiceover
                fc = (f"[1:a]volume={vol}[m];[m][0:a]sidechaincompress=threshold=0.03:ratio=8"
                      f":attack=20:release=400[md];[0:a][md]amix=inputs=2:duration=first:normalize=0,"
                      f"afade=t=out:st={duration_of(joined) - 1.5:.2f}:d=1.5[a]")
            else:
                fc = (f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,"
                      f"afade=t=out:st={duration_of(joined) - 1.5:.2f}:d=1.5[a]")
            ff("-i", joined, "-stream_loop", "-1", "-i", music, "-filter_complex", fc,
               "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-shortest", output)
        else:
            ff("-i", joined, "-c", "copy", "-movflags", "+faststart", output)

    print(f"Done → {output} ({duration_of(output):.1f}s)")


if __name__ == "__main__":
    main()
