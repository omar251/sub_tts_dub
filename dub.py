import os
import time
import mpv
import pysrt
import tempfile
import threading
import argparse
import shutil
import difflib
import re
import unicodedata
import readchar
import pygame
import asyncio
import edge_tts
from gtts import gTTS
from langdetect import detect
from pynput import keyboard

# Global flags and locks
stop_flag = threading.Event()
pause_flag = threading.Event()
current_tts_thread = None
tts_lock = threading.Lock()


def normalize_name(name):
    """Normalize string for better matching."""
    # Remove potential prefixes like 'cmovies-' or 'www.website.com-'
    name = re.sub(r'^\w+[-_.]', '', name)
    # Remove accents (diacritics)
    nfkd_form = unicodedata.normalize('NFKD', name)
    name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Lowercase, remove non-alphanumeric, and collapse whitespace
    name = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
    return name


async def list_voices():
    """List all available Edge TTS voices."""
    print("🗣️ Available Edge TTS Voices:")
    voices = await edge_tts.list_voices()
    voices = sorted(voices, key=lambda voice: voice["ShortName"])
    for voice in voices:
        print(f"  - {voice['ShortName']}: {voice['Gender']}, {voice['Locale']}")


def interactive_subtitle_selection(scored_srt_files):
    """An interactive menu to select a subtitle file."""
    selected_index = 0

    # Add "None" option
    options = scored_srt_files + [("None of the above (play without subtitles)", 0)]

    while True:
        # Clear console and print menu
        os.system('cls' if os.name == 'nt' else 'clear')
        print("📖 Multiple subtitle files found. Use arrow keys to select, Enter to confirm.")

        for i, (filename, score) in enumerate(options):
            if "None of the above" in filename:
                print("-" * 30) # Separator
                prefix = "> " if i == selected_index else "  "
                print(f"{prefix}{filename}")
            else:
                recommendation = "(best match)" if i == 0 else ""
                prefix = "> " if i == selected_index else "  "
                print(f"{prefix}{i+1}: {filename} (score: {score:.2f}) {recommendation}")

        key = readchar.readkey()

        if key == readchar.key.UP:
            selected_index = (selected_index - 1) % len(options)
        elif key == readchar.key.DOWN:
            selected_index = (selected_index + 1) % len(options)
        elif key == readchar.key.ENTER:
            chosen_file, _ = options[selected_index]
            if "None of the above" in chosen_file:
                return None
            return chosen_file
        elif key in ('q', 'Q', readchar.key.CTRL_C):
            print("❌ Selection cancelled. Exiting.")
            return "CANCEL"


def control_loop():
    """Keyboard controls for playback"""
    def on_press(key):
        global current_tts_thread
        try:
            if key == keyboard.Key.space:  # Pause/Resume
                return  # Let MPV handle space for pause/resume

            elif key.char == "s":  # Stop
                stop_flag.set()
                print("⏹ Stopped")

            elif key.char == "q":  # Quit
                stop_flag.set()
                print("👋 Quit")
                return False

            elif key.char == "m":  # Mute TTS
                pygame.mixer.music.set_volume(0 if pygame.mixer.music.get_volume() > 0 else 1)
                print("🔇 TTS Muted" if pygame.mixer.music.get_volume() == 0 else "🔊 TTS Unmuted")

        except AttributeError:
            pass  # Let MPV handle arrow keys and other special keys

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


def play_tts_audio(filename):
    """Play TTS audio using pygame"""
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
    except Exception as e:
        print(f"⚠️ Failed to play TTS audio: {e}")


def generate_tts(subs, lang, temp_dir, pre_cache, voice_speed=1.0, tts_engine='google', voice='en-US-AriaNeural'):
    """Generate TTS files with configurable speed"""
    audio_files = [None] * len(subs)

    if tts_engine == 'edge':
        # Edge TTS uses a different speed format (+x% or -x%)
        rate_str = f"{int((voice_speed - 1) * 100):+}%"

        async def generate_all_edge():
            total = len(subs)
            print(f"🗣️ Pre-generating Edge TTS for all subtitles with voice '{voice}'...")

            tasks = []
            for i, sub in enumerate(subs):
                text = sub.text.replace("\n", " ").strip()
                if not text:
                    continue
                filename = os.path.join(temp_dir, f"sub_{i+1}.mp3")
                if not os.path.exists(filename):
                    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
                    tasks.append((communicate.save(filename), i))

            for i, task_tuple in enumerate(asyncio.as_completed([t[0] for t in tasks])):
                await task_tuple
                original_index = tasks[i][1]
                audio_files[original_index] = os.path.join(temp_dir, f"sub_{original_index+1}.mp3")
                progress = int(((i + 1) / total) * 100)
                print(f"\r🔄 Generating audio {i+1}/{total} ({progress}%) ", end="", flush=True)

        if pre_cache:
            asyncio.run(generate_all_edge())
            print("\n✅ All subtitles cached as audio files.")
        else:
            print("⚡ On-demand Edge TTS mode.")

    elif tts_engine == 'google':
        if pre_cache:
            print("🗣️ Pre-generating Google TTS for all subtitles...")
            total = len(subs)
            for i, sub in enumerate(subs, 1):
                if stop_flag.is_set():
                    break

                text = sub.text.replace("\n", " ").strip()
                if not text:
                    continue

                filename = os.path.join(temp_dir, f"sub_{i}.mp3")
                if not os.path.exists(filename):
                    try:
                        tts = gTTS(text=text, lang=lang, slow=(voice_speed < 1.0))
                        tts.save(filename)
                    except Exception as e:
                        print(f"\n⚠️ Failed to generate TTS for sub {i}: {e}")
                        continue
                audio_files[i - 1] = filename
                progress = int((i / total) * 100)
                print(f"\r🔄 Generating audio {i}/{total} ({progress}%) ", end="", flush=True)
            print("\n✅ All subtitles cached as audio files.")
        else:
            print("⚡ On-demand Google TTS mode.")

    return audio_files

def cleanup_temp_files(temp_dir):
    """Clean up temporary files"""
    try:
        shutil.rmtree(temp_dir)
        print("🧹 Cleaned up temporary files.")
    except Exception as e:
        print(f"⚠️ Could not clean up temp files: {e}")


def play_video_with_tts(video_path, srt_path, pre_cache, voice_speed=1.0, tts_engine='google', voice='en-US-AriaNeural'):
    global current_tts_thread


    # Validate video file exists
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return

    # If srt_path is not provided, search for it
    if not srt_path:
        print("🔍 Subtitle file not specified, searching for one...")
        video_dir = os.path.dirname(video_path)
        if not video_dir:
            video_dir = "."

        srt_files = [f for f in os.listdir(video_dir) if f.lower().endswith('.srt')]

        if not srt_files:
            print(f"❌ No .srt files found in the directory: {video_dir}")
            return

        if len(srt_files) == 1:
            srt_path = os.path.join(video_dir, srt_files[0])
            print(f"✅ Automatically selected the only subtitle file found: {srt_path}")
        else:
            movie_base_name, _ = os.path.splitext(os.path.basename(video_path))
            normalized_movie_name = normalize_name(movie_base_name)

            # Score and sort subtitles
            scored_srt_files = []
            for srt_filename in srt_files:
                srt_base_name, _ = os.path.splitext(srt_filename)
                normalized_srt_name = normalize_name(srt_base_name)
                score = difflib.SequenceMatcher(None, normalized_movie_name, normalized_srt_name).ratio()
                scored_srt_files.append((srt_filename, score))

            # Sort by score, descending
            scored_srt_files.sort(key=lambda x: x[1], reverse=True)

            chosen_file = interactive_subtitle_selection(scored_srt_files)

            if chosen_file == "CANCEL":
                return # Exit if selection was cancelled
            elif chosen_file is None:
                srt_path = None
                print("✅ Playing video without subtitles as requested.")
            else:
                srt_path = os.path.join(video_dir, chosen_file)
                print(f"✅ You selected: {srt_path}")

    # --- Subtitle-dependent section ---
    subs = None
    if srt_path:
        if not os.path.exists(srt_path):
            print(f"❌ Subtitle file not found: {srt_path}")
            return

        try:
            subs = pysrt.open(srt_path, encoding='utf-8')
            if not subs:
                print("❌ No subtitles found in file")
                return
            print(f"📄 Loaded {len(subs)} subtitles")
        except Exception as e:
            print(f"❌ Failed to load subtitles: {e}")
            return

        # Detect language
        sample_text = " ".join(sub.text for sub in subs[:min(10, len(subs))])
        try:
            lang = detect(sample_text)
            print(f"🌍 Detected subtitle language: {lang}")
        except Exception as e:
            print(f"⚠️ Language detection failed, defaulting to 'en': {e}")
            lang = 'en'

    # Initialize pygame for audio only if subs are loaded
    if subs:
        try:
            pygame.mixer.init()
            print("🔊 Audio system initialized")
        except Exception as e:
            print(f"❌ Failed to initialize audio: {e}")
            return

    # Temp folder for generated TTS
    temp_dir = tempfile.mkdtemp(prefix='movie_dub_')
    print(f"📁 Using temp directory: {temp_dir}")

    try:
        audio_files = []
        if subs:
            # Pre-cache (or not)
            audio_files = generate_tts(subs, lang, temp_dir, pre_cache, voice_speed, tts_engine, voice)
            if stop_flag.is_set():
                return

        # Setup MPV
        print("🎬 Initializing MPV...")
        player = mpv.MPV(
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=True,  # Show on-screen controls
            ytdl=True  # Enable youtube-dl if needed
        )

        # Load and play video
        print("▶️ Starting video playback...")
        player.play(video_path)
        player.wait_until_playing()

        # Start keyboard control in separate thread
        threading.Thread(target=control_loop, daemon=True).start()

        if subs:
            print("🔊 Speaking subtitles with Google TTS in sync with video...")
            print("📝 Subtitles should also display on screen")
        else:
            print("▶️ Playing video without dubbing.")

        print("🎮 Controls:")
        print("   space = pause/resume (MPV native)")
        print("   s = stop script")
        print("   q = quit")
        if subs: print("   m = mute/unmute TTS")
        print("   ←/→ = seek (MPV native)")
        print("   +/- = volume (MPV native)")
        print("   v = toggle subtitle visibility (MPV native)")
        print("   j/J = cycle subtitle tracks (MPV native)")
        print("   u = toggle subtitle style override (MPV native)")

        last_index = -1  # last spoken subtitle

        while not stop_flag.is_set() and not player.eof_reached:
            if subs:
                try:
                    # Get current playback position
                    current_time = player.time_pos
                    if current_time is None:
                        time.sleep(0.05)
                        continue

                    current_time_ms = int(current_time * 1000)  # Convert to milliseconds

                    # Find which subtitle matches current video time
                    for i, sub in enumerate(subs):
                        if sub.start.ordinal <= current_time_ms <= sub.end.ordinal:
                            if i != last_index:
                                filename = audio_files[i]

                                # Generate on-demand if needed
                                if filename is None:
                                    text = sub.text.replace("\n", " ").strip()
                                    if not text:
                                        last_index = i
                                        break

                                    filename = os.path.join(temp_dir, f"sub_{i+1}.mp3")
                                    try:
                                        if tts_engine == 'edge':
                                            rate_str = f"{int((voice_speed - 1) * 100):+}%"
                                            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
                                            asyncio.run(communicate.save(filename))
                                        else: # google
                                            tts = gTTS(text=text, lang=lang, slow=(voice_speed < 1.0))
                                            tts.save(filename)

                                        audio_files[i] = filename
                                    except Exception as e:
                                        print(f"\n⚠️ Failed to generate TTS on-demand: {e}")
                                        last_index = i
                                        break

                                # Play TTS audio
                                with tts_lock:
                                    pygame.mixer.music.stop()  # Stop previous TTS
                                    play_tts_audio(filename)

                                # Show current subtitle
                                print(f"\r🎬 [{i+1}/{len(subs)}] {sub.text[:50]}{'...' if len(sub.text) > 50 else ''}",
                                      end="", flush=True)

                                last_index = i
                            break

                    time.sleep(0.05)

                except Exception as e:
                    if "property unavailable" not in str(e):
                        print(f"\n⚠️ Playback error: {e}")
                    time.sleep(0.1)
            else:
                # If no subs, just wait
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n⏹ Interrupted by user, exiting.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        stop_flag.set()
        try:
            if subs:
                pygame.mixer.quit()
            if 'player' in locals():
                player.terminate()
        except:
            pass
        cleanup_temp_files(temp_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🎬 Movie dubbing with subtitles + TTS (MPV version)")
    parser.add_argument("movie", nargs='?', default=None, help="Path to the movie file")
    parser.add_argument("--subs", help="Path to subtitle file (.srt). If not provided, it will look for a .srt file with the same name as the movie.")
    parser.add_argument("--precache", action="store_true",
                        help="Pre-generate all TTS (slower startup, instant rewind)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="TTS voice speed (0.5-2.0 for Google, +/-%% for Edge)")
    parser.add_argument("--tts-engine", choices=['google', 'edge'], default='google',
                        help="Select the TTS engine")
    parser.add_argument("--voice", default="en-US-AriaNeural",
                        help="Specify the voice for Edge TTS")
    parser.add_argument("--list-voices", action="store_true",
                        help="List available Edge TTS voices and exit")

    args = parser.parse_args()

    if args.list_voices:
        asyncio.run(list_voices())
        exit(0)

    if not args.movie:
        parser.error("the following arguments are required: movie")

    if args.tts_engine == 'google' and (args.speed < 0.5 or args.speed > 2.0):
        print("⚠️ Google TTS speed must be between 0.5 and 2.0")
        exit(1)

    play_video_with_tts(args.movie, args.subs, args.precache, args.speed, args.tts_engine, args.voice)
