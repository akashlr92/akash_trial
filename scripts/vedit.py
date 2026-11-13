#!/usr/bin/env python3
"""vedit — simple video editing commands built on FFmpeg.

Run `python scripts/vedit.py -h` or `python scripts/vedit.py <command> -h` for help.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ff(*args):
    run(["ffmpeg", "-hide_banner", "-y", *args])


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def esc_filter_path(path):
    # Escape a file path for use inside an ffmpeg filter argument
    return path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


# ---------------- commands ----------------

def cmd_info(a):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                          "-of", "json", a.input], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    fmt = d["format"]
    print(f"File:     {a.input}")
    print(f"Duration: {float(fmt.get('duration', 0)):.2f}s   Size: {int(fmt.get('size', 0)) / 1e6:.1f} MB")
    for s in d["streams"]:
        if s["codec_type"] == "video":
            print(f"Video:    {s['codec_name']} {s['width']}x{s['height']} @ {s.get('r_frame_rate')} fps")
        elif s["codec_type"] == "audio":
            print(f"Audio:    {s['codec_name']} {s.get('sample_rate')} Hz, {s.get('channels')} ch")


def cmd_trim(a):
    args = ["-ss", a.start] + (["-to", a.end] if a.end else []) + ["-i", a.input]
    if a.fast:
        ff(*args, "-c", "copy", a.output)
    else:
        ff(*args, *ENC, a.output)


def cmd_concat(a):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in a.inputs:
            f.write(f"file '{os.path.abspath(p)}'\n")
        lst = f.name
    try:
        if a.fast:
            ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", a.output)
        else:
            ff("-f", "concat", "-safe", "0", "-i", lst, *ENC, a.output)
    finally:
        os.unlink(lst)


def cmd_vertical(a):
    # 9:16 for Shorts/Reels/TikTok
    w, h = 1080, 1920
    if a.mode == "crop":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    else:  # blur: fit video in the middle over a blurred, zoomed copy
        vf = (f"split[bg][fg];"
              f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2[bg];"
              f"[fg]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    ff("-i", a.input, "-filter_complex", vf, *ENC, a.output)


def cmd_music(a):
    vol = a.volume
    if has_audio(a.input):
        if a.duck:
            fc = (f"[1:a]volume={vol}[m];[m][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
                  f"[0:a][md]amix=inputs=2:duration=first:normalize=0[a]")
        else:
            fc = f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        fc = f"[1:a]volume={vol}[a]"
    ff("-i", a.input, "-stream_loop", "-1", "-i", a.music, "-filter_complex", fc,
       "-map", "0:v", "-map", "[a]", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", a.output)


def cmd_subtitles(a):
    style = f"FontSize={a.size},Outline=2,Shadow=0,MarginV={a.margin}"
    vf = f"subtitles='{esc_filter_path(a.srt)}':force_style='{style}'"
    ff("-i", a.input, "-vf", vf, *ENC, a.output)


def cmd_normalize(a):
    # EBU R128 loudness normalisation (-14 LUFS is YouTube/Spotify's target)
    ff("-i", a.input, "-af", f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11", "-c:v", "copy",
       "-c:a", "aac", "-b:a", "192k", a.output)


def cmd_thumbnail(a):
    ff("-ss", a.time, "-i", a.input, "-frames:v", "1", "-q:v", "2", a.output)


def cmd_compress(a):
    vf = f"scale=-2:{a.height}" if a.height else "null"
    ff("-i", a.input, "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", a.output)


def cmd_audio(a):
    ff("-i", a.input, "-vn", a.output)


def cmd_speed(a):
    s = a.factor
    atempo = []
    t = s
    while t > 2.0:
        atempo.append("atempo=2.0"); t /= 2.0
    while t < 0.5:
        atempo.append("atempo=0.5"); t /= 0.5
    atempo.append(f"atempo={t}")
    args = ["-i", a.input, "-filter:v", f"setpts=PTS/{s}"]
    if has_audio(a.input):
        args += ["-filter:a", ",".join(atempo)]
    ff(*args, *ENC, a.output)


def cmd_watermark(a):
    pos = {"tl": "20:20", "tr": "W-w-20:20", "bl": "20:H-h-20", "br": "W-w-20:H-h-20"}[a.pos]
    fc = (f"[1:v]scale={a.width}:-1,format=rgba,colorchannelmixer=aa={a.opacity}[wm];"
          f"[0:v][wm]overlay={pos}")
    ff("-i", a.input, "-i", a.image, "-filter_complex", fc, *ENC, a.output)


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it first (see README).")

    p = argparse.ArgumentParser(prog="vedit", description="Simple FFmpeg-based video editing commands")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="Show duration, resolution, codecs")
    s.add_argument("input"); s.set_defaults(fn=cmd_info)

    s = sub.add_parser("trim", help="Cut a clip between two timestamps (e.g. 00:01:05)")
    s.add_argument("input"); s.add_argument("output")
    s.add_argument("--start", default="0"); s.add_argument("--end")
    s.add_argument("--fast", action="store_true", help="No re-encode (cuts snap to keyframes)")
    s.set_defaults(fn=cmd_trim)

    s = sub.add_parser("concat", help="Join clips in order")
    s.add_argument("output"); s.add_argument("inputs", nargs="+")
    s.add_argument("--fast", action="store_true", help="No re-encode (clips must share codec/size)")
    s.set_defaults(fn=cmd_concat)

    s = sub.add_parser("vertical", help="Convert to 1080x1920 for Shorts/Reels/TikTok")
    s.add_argument("input"); s.add_argument("output")
    s.add_argument("--mode", choices=["blur", "crop"], default="blur")
    s.set_defaults(fn=cmd_vertical)

    s = sub.add_parser("music", help="Add background music (loops to fit video)")
    s.add_argument("input"); s.add_argument("music"); s.add_argument("output")
    s.add_argument("--volume", type=float, default=0.15)
    s.add_argument("--duck", action="store_true", help="Lower music automatically while someone speaks")
    s.set_defaults(fn=cmd_music)

    s = sub.add_parser("subtitles", help="Burn an .srt file into the video")
    s.add_argument("input"); s.add_argument("srt"); s.add_argument("output")
    s.add_argument("--size", type=int, default=18); s.add_argument("--margin", type=int, default=40)
    s.set_defaults(fn=cmd_subtitles)

    s = sub.add_parser("normalize", help="Even out loudness (default -14 LUFS)")
    s.add_argument("input"); s.add_argument("output")
    s.add_argument("--lufs", type=float, default=-14); s.set_defaults(fn=cmd_normalize)

    s = sub.add_parser("thumbnail", help="Grab a still frame as an image")
    s.add_argument("input"); s.add_argument("output"); s.add_argument("--time", default="00:00:01")
    s.set_defaults(fn=cmd_thumbnail)

    s = sub.add_parser("compress", help="Shrink file size")
    s.add_argument("input"); s.add_argument("output")
    s.add_argument("--crf", type=int, default=26, help="Higher = smaller/lower quality (18-30)")
    s.add_argument("--height", type=int, help="Resize, e.g. 720"); s.set_defaults(fn=cmd_compress)

    s = sub.add_parser("audio", help="Extract audio (output extension sets format: .mp3/.wav/.m4a)")
    s.add_argument("input"); s.add_argument("output"); s.set_defaults(fn=cmd_audio)

    s = sub.add_parser("speed", help="Speed up / slow down (e.g. 1.5 or 0.5)")
    s.add_argument("input"); s.add_argument("output"); s.add_argument("factor", type=float)
    s.set_defaults(fn=cmd_speed)

    s = sub.add_parser("watermark", help="Overlay a logo image")
    s.add_argument("input"); s.add_argument("image"); s.add_argument("output")
    s.add_argument("--pos", choices=["tl", "tr", "bl", "br"], default="br")
    s.add_argument("--width", type=int, default=200, help="Logo width in pixels")
    s.add_argument("--opacity", type=float, default=0.8)
    s.set_defaults(fn=cmd_watermark)

    a = p.parse_args()
    try:
        a.fn(a)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffmpeg failed (exit {e.returncode})")


if __name__ == "__main__":
    main()
