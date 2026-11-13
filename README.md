# Video Editing Workspace

A simple folder layout plus a one-file command-line tool (`scripts/vedit.py`) for common video edits, built on FFmpeg.

## Setup

1. Install **FFmpeg**
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
2. Install **Python 3.8+** (no extra packages needed).
3. Check it works: `python scripts/vedit.py -h`

## Folders

| Folder | Put here |
|---|---|
| `footage/raw/` | Original camera / screen recordings |
| `footage/broll/` | B-roll clips |
| `assets/music/`, `assets/sfx/` | Background music, sound effects |
| `assets/images/`, `assets/fonts/` | Logos, overlays, thumbnails, fonts |
| `subtitles/` | `.srt` caption files |
| `projects/` | Editor project files (DaVinci Resolve, Premiere, CapCut…) |
| `exports/` | Finished videos |

Video, audio and export files are **ignored by Git** (they're too big for it). Back up footage separately, e.g. on Google Drive or an external disk.

## Commands

Timestamps can be seconds (`65`) or `HH:MM:SS` (`00:01:05`).

```bash
V="python scripts/vedit.py"

$V info footage/raw/clip.mp4                                   # duration, resolution, codecs
$V trim footage/raw/clip.mp4 exports/cut.mp4 --start 00:00:05 --end 00:01:30
$V concat exports/full.mp4 intro.mp4 main.mp4 outro.mp4        # join clips in order
$V vertical exports/full.mp4 exports/short.mp4                 # 9:16 for Shorts/Reels (blurred background)
$V vertical exports/full.mp4 exports/short.mp4 --mode crop     # 9:16, crop the center instead
$V music exports/full.mp4 assets/music/bg.mp3 exports/m.mp4 --volume 0.15 --duck   # music lowers when you speak
$V subtitles exports/full.mp4 subtitles/full.srt exports/sub.mp4                   # burn captions in
$V normalize exports/full.mp4 exports/loud.mp4                 # even out volume (-14 LUFS, YouTube standard)
$V watermark exports/full.mp4 assets/images/logo.png exports/w.mp4 --pos br --width 200
$V speed exports/full.mp4 exports/fast.mp4 1.5                 # 1.5x speed (0.5 = slow motion)
$V thumbnail exports/full.mp4 assets/images/thumb.jpg --time 00:00:12
$V compress exports/full.mp4 exports/small.mp4 --height 720    # smaller file for sharing
$V audio footage/raw/clip.mp4 exports/voice.mp3                # extract audio
```

Add `--fast` to `trim` or `concat` to skip re-encoding. It runs almost instantly, but cuts snap to the nearest keyframe and the clips you join must share the same format.

Run `python scripts/vedit.py <command> -h` to see every option.

### Typical YouTube → Shorts workflow

```bash
$V trim footage/raw/rec.mp4 exports/1-cut.mp4 --start 30 --end 08:45
$V normalize exports/1-cut.mp4 exports/2-loud.mp4
$V music exports/2-loud.mp4 assets/music/bg.mp3 exports/3-final.mp4 --duck
$V trim exports/3-final.mp4 exports/short-raw.mp4 --start 02:10 --end 02:55
$V vertical exports/short-raw.mp4 exports/short.mp4
$V subtitles exports/short.mp4 subtitles/short.srt exports/short-final.mp4 --size 14 --margin 120
```
