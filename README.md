# Sub TTS Dub 🎬🗣️

A Python tool that adds real-time text-to-speech dubbing to movies using subtitle files. Watch your favorite foreign films with AI-generated voice dubbing synchronized to the original subtitles!

## Features

- 🎬 **Real-time video playback** with MPV media player
- 🗣️ **Text-to-speech dubbing** using Google TTS
- 🌍 **Automatic language detection** from subtitle content
- ⚡ **Two playback modes**: Pre-cache all audio or generate on-demand
- 🎮 **Interactive controls** for playback, seeking, and audio management
- 📄 **SRT subtitle support** with proper timing synchronization
- 🔊 **Audio mixing** - original video audio + TTS dubbing
- ⚙️ **Configurable voice speed** (0.5x to 2.0x)

## Installation

### Prerequisites

- Python 3.12 or higher
- MPV media player installed on your system

### Install with uv (recommended)

```bash
git clone <repository-url>
cd sub_tts_dub
uv sync
```

### Install with pip

```bash
git clone <repository-url>
cd sub_tts_dub
pip install -e .
```

## Usage

### Basic Usage

The script will automatically look for a `.srt` subtitle file with the same name as the movie file in the same directory.

```bash
python dub.py "path/to/movie.mp4"
```

### Advanced Options

You can also specify a path to a different subtitle file.

```bash
python dub.py "path/to/movie.mp4" --subs "path/to/different_subtitles.srt"
```

```bash
# Pre-cache all TTS audio (slower startup, instant seeking)
python dub.py "movie.mp4" --precache

# Adjust voice speed (0.5 = slower, 2.0 = faster)
python dub.py "movie.mp4" --speed 1.5

# Combine options
python dub.py "movie.mp4" --subs "subs.srt" --precache --speed 0.8
```

## Playback Modes

### On-Demand Mode (Default)
- ⚡ **Fast startup** - begins playback immediately
- 🔄 **Dynamic generation** - TTS audio created as needed
- ⚠️ **Seeking limitation** - may lag when jumping to new positions

### Pre-cache Mode (`--precache`)
- 🐌 **Slower startup** - generates all TTS audio first
- ⚡ **Instant seeking** - all audio pre-generated
- 💾 **Higher memory usage** - stores all audio files temporarily

## Controls

During playback, use these keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Space` | Pause/Resume video (MPV native) |
| `s` | Stop dubbing script |
| `q` | Quit application |
| `m` | Mute/Unmute TTS audio |
| `←/→` | Seek backward/forward (MPV native) |
| `+/-` | Adjust volume (MPV native) |
| `v` | Toggle subtitle visibility (MPV native) |
| `j/J` | Cycle subtitle tracks (MPV native) |
| `u` | Toggle subtitle style override (MPV native) |

## How It Works

1. **Subtitle Loading**: Reads SRT subtitle files with proper encoding
2. **Language Detection**: Automatically detects subtitle language for optimal TTS
3. **Video Playback**: Uses MPV for robust video playback with native controls
4. **TTS Generation**: Creates speech audio using Google Text-to-Speech
5. **Synchronization**: Matches TTS playback to subtitle timing
6. **Audio Mixing**: Plays TTS alongside original video audio

## Dependencies

- **mpv**: Video playback engine
- **pysrt**: SRT subtitle file parsing
- **gtts**: Google Text-to-Speech API
- **pygame**: Audio playback for TTS
- **langdetect**: Automatic language detection
- **pynput**: Keyboard input handling
- **beautifulsoup4**: HTML parsing utilities
- **requests**: HTTP requests for TTS API

## File Structure

```
sub_tts_dub/
├── dub.py              # Main application script
├── pyproject.toml      # Project configuration and dependencies
├── README.md           # This file
├── .gitignore          # Git ignore rules
└── uv.lock            # Dependency lock file
```

## Supported Formats

- **Video**: Any format supported by MPV (MP4, MKV, AVI, etc.)
- **Subtitles**: SRT format with UTF-8 encoding
- **Languages**: Any language supported by Google TTS

## Troubleshooting

### Common Issues

**"Video file not found"**
- Ensure the video file path is correct and the file exists

**"Subtitle file not found"**
- Verify the SRT file path and ensure it's in UTF-8 encoding

**"Failed to initialize audio"**
- Check that your system has audio output available
- Try restarting the application

**"Language detection failed"**
- The tool will default to English if detection fails
- Ensure your subtitle file contains readable text

### Performance Tips

- Use `--precache` for movies you'll watch multiple times
- Use on-demand mode for quick previews or one-time viewing
- Adjust `--speed` to match your preferred listening pace
- Close other audio applications to avoid conflicts

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is open source. Please check the license file for details.

---

**Note**: This tool requires an internet connection for Google TTS API calls. Generated audio files are temporarily stored and cleaned up automatically after playback.