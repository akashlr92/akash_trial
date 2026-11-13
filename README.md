# Video Generation Workspace

Write a video as a list of scenes in a JSON file, run one command, and get a finished MP4. It works for YouTube (16:9), Shorts/Reels/TikTok (9:16) or square (1:1). Each scene can have text, a background (colour, image or video clip), a voiceover and background music.

## Setup

1. Install **FFmpeg**
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
2. Install **Python 3.8+**.
3. *(Optional, for AI voiceover)* `pip install edge-tts`. This uses free Microsoft voices and needs internet.

## Make a video

```bash
python scripts/generate.py examples/short.json
```

The video is saved to the `output` path set in the file (here `exports/short.mp4`). To use a different path, add `-o exports/test.mp4`.

Copy one of the files in `examples/` and edit it to make your own. Paths inside the file are relative to the repo folder.

## Scene file format

```json
{
  "output": "exports/my-video.mp4",
  "format": "vertical",
  "background": "#111827",
  "music": "assets/music/bg.mp3",
  "music_volume": 0.15,
  "voice": "en-US-AriaNeural",
  "position": "center",
  "box": true,
  "scenes": [
    { "text": "Big hook here", "duration": 3, "background": "#7c3aed" },
    { "text": "Point one", "say": "This sentence is spoken aloud.", "background": "assets/images/photo.jpg" },
    { "text": "Point two", "audio": "assets/voice/my-recording.mp3", "background": "footage/broll/clip.mp4" }
  ]
}
```

**Video settings** (all optional):

| Key | What it does | Default |
|---|---|---|
| `format` | `vertical` (1080×1920), `landscape` (1920×1080), `square`, or custom like `"1280x720"` | `vertical` |
| `output` | Where to save | `exports/output.mp4` |
| `fps` | Frames per second | `30` |
| `background` | Default scene background | dark grey |
| `music`, `music_volume` | Background track (loops to fit, fades out, and dips under voiceover) | none, `0.15` |
| `voice` | edge-tts voice for `say` (run `edge-tts --list-voices` to see all) | `en-US-AriaNeural` |
| `font`, `font_size`, `text_color` | Text style (`font` = path to a .ttf in `assets/fonts/`) | system sans, 72/64, white |
| `position` | Text placement: `top`, `center`, `bottom` | `center` |
| `box` | Dark box behind text for readability | `false` |

**Per-scene keys:**

| Key | What it does |
|---|---|
| `text` | On-screen text (wraps automatically; use `\n` for line breaks) |
| `duration` | Seconds. If the scene has voiceover, it stretches to fit the voice. Default 4 |
| `background` | Colour (`"#ff0000"`, `"navy"`), image (slow zoom effect) or video clip (loops and crops to fit) |
| `zoom` | `false` turns off the slow zoom on images |
| `say` | Text to speak with AI voice (needs edge-tts) |
| `audio` | Your own voice recording for this scene instead |
| Any video setting | `voice`, `font_size`, `text_color`, `position`, `box` and `font` can be overridden per scene |

## Folders

| Folder | Put here |
|---|---|
| `examples/` | Example scene files to copy |
| `assets/images/`, `footage/broll/` | Backgrounds (images, video clips) |
| `assets/music/`, `assets/voice/`, `assets/sfx/` | Music, voice recordings, sound effects |
| `assets/fonts/` | Custom `.ttf` fonts |
| `exports/` | Finished videos |

Video and audio files are **ignored by Git** (they're too big for it), so back them up separately.

## Extra editing tools

`scripts/vedit.py` handles quick edits on any video, including generated ones: trim, join, vertical crop, burn subtitles, loudness, watermark, speed, thumbnail and compress. Run `python scripts/vedit.py -h` to see them all. For example:

```bash
python scripts/vedit.py thumbnail exports/short.mp4 assets/images/thumb.jpg --time 2
python scripts/vedit.py watermark exports/short.mp4 assets/images/logo.png exports/short-logo.mp4
```
