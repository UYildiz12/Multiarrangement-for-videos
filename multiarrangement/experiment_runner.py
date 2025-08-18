def show_instructions_pygame(mode: str = "video", language: str = "en"):
    """Show instructions for video or audio mode in the selected language using pygame."""
    # Map instructions to media files (best guess)
    if language == "tr":
        if mode == "video":
            instructions = [
                ("Video benzerliği düzenleme deneyine hoş geldiniz.", "img1.PNG"),
                ("Gruplar halinde videolar göreceksiniz ve bunları benzerliğe göre düzenlemeniz gerekecek.", "similar.mp4"),
                ("Önce gruptaki tüm videoları izleyeceksiniz.", "Same.mkv"),
                ("Daha sonra video dairelerini sürükleyerek düzenleyin.", "drag.mp4"),
                ("Benzer videoları birbirine yakın, farklı olanları uzak yerleştirin.", "similar.mp4"),
                ("Herhangi bir daireye çift tıklayarak videoyu tekrar oynatabilirsiniz.", "Doubleclick.mp4"),
                ("Düzenlemeden memnun kaldığınızda 'Bitti'ye tıklayın.", "Done.mp4"),
                ("Bu talimatları geçmek için BOŞLUK tuşuna basın.", None)
            ]
        else:
            instructions = [
                ("Ses benzerliği düzenleme deneyine hoş geldiniz.", "img1.PNG"),
                ("Gruplar halinde sesler göreceksiniz ve bunları benzerliğe göre düzenlemeniz gerekecek.", "similar.mp4"),
                ("Önce gruptaki tüm sesleri dinleyeceksiniz.", "Same.mkv"),
                ("Daha sonra ses dairelerini sürükleyerek düzenleyin.", "drag.mp4"),
                ("Benzer sesleri birbirine yakın, farklı olanları uzak yerleştirin.", "similar.mp4"),
                ("Herhangi bir daireye çift tıklayarak sesi tekrar dinleyebilirsiniz.", "Doubleclick.mp4"),
                ("Düzenlemeden memnun kaldığınızda 'Bitti'ye tıklayın.", "Done.mp4"),
                ("Bu talimatları geçmek için BOŞLUK tuşuna basın.", None)
            ]
    else:
        if mode == "video":
            instructions = [
                ("Welcome to the video similarity arrangement experiment.", "img1.PNG"),
                ("You will see groups of videos that you need to arrange by similarity.", "similar.mp4"),
                ("First, you will watch all videos in the group.", "Same.mkv"),
                ("Then, arrange the video circles by dragging them.", "drag.mp4"),
                ("Place similar videos close together, dissimilar videos far apart.", "similar.mp4"),
                ("Double-click any circle to replay its video.", "Doubleclick.mp4"),
                ("Click 'Done' when you're satisfied with the arrangement.", "Done.mp4"),
                ("Press SPACE to continue through these instructions.", None)
            ]
        else:
            instructions = [
                ("Welcome to the audio similarity arrangement experiment.", "img1.PNG"),
                ("You will see groups of sounds that you need to arrange by similarity.", "similar.mp4"),
                ("First, you will listen to all sounds in the group.", "Same.mkv"),
                ("Then, arrange the sound circles by dragging them.", "drag.mp4"),
                ("Place similar sounds close together, dissimilar sounds far apart.", "similar.mp4"),
                ("Double-click any circle to replay its sound.", "Doubleclick.mp4"),
                ("Click 'Done' when you're satisfied with the arrangement.", "Done.mp4"),
                ("Press SPACE to continue through these instructions.", None)
            ]
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    font = pygame.font.Font(None, 48)
    clock = pygame.time.Clock()
    import textwrap
    import cv2
    for instruction, media in instructions:
        waiting = True
        show_media = (mode == "video")
        if show_media and media and media.lower().endswith(('.mp4', '.mkv')):
            # Play full video in loop until SPACE is pressed
            # Resolve instruction video path: prefer current file path, then ./demovids, then packaged demovids
            if os.path.exists(media):
                video_path = media
            else:
                local_demo = os.path.join('demovids', media)
                if os.path.exists(local_demo):
                    video_path = local_demo
                else:
                    pkg_demo = os.path.join(os.path.dirname(__file__), 'demovids', media)
                    video_path = pkg_demo
            cap = cv2.VideoCapture(video_path)
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                screen.fill((0, 0, 0))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (600, 600))
                frame_surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
                x = (screen.get_width() - 600) // 2
                y = 80
                screen.blit(frame_surface, (x, y))
                # Display instruction text
                lines = textwrap.wrap(instruction, width=50)
                total_height = len(lines) * font.get_height()
                start_y = (screen.get_height() - total_height) // 2 + 350
                for i, line in enumerate(lines):
                    text_surface = font.render(line, True, (255, 255, 255))
                    x_txt = (screen.get_width() - text_surface.get_width()) // 2
                    y_txt = start_y + i * font.get_height()
                    screen.blit(text_surface, (x_txt, y_txt))
                pygame.display.flip()
                clock.tick(30)
            cap.release()
        else:
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()
                screen.fill((0, 0, 0))
                # Display image if available (only for video mode)
                if show_media and media and media.lower().endswith(('.png', '.jpg', '.jpeg')):
                    try:
                        # Try to load image from package data directory first
                        import multiarrangement.data
                        data_dir = os.path.dirname(multiarrangement.data.__file__)
                        img_path = os.path.join(data_dir, media)
                        
                        # Fallback to current directory if not found in package data
                        if not os.path.exists(img_path):
                            img_path = media
                            
                        img = cv2.imread(img_path)
                        if img is not None:
                            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            img = cv2.resize(img, (600, 600))
                            img_surface = pygame.surfarray.make_surface(img.swapaxes(0, 1))
                            x = (screen.get_width() - 600) // 2
                            y = 80
                            screen.blit(img_surface, (x, y))
                    except Exception as e:
                        print(f"Could not load image {media}: {e}")
                        pass
                # Display instruction text
                lines = textwrap.wrap(instruction, width=50)
                total_height = len(lines) * font.get_height()
                if mode == "audio":
                    start_y = (screen.get_height() - total_height) // 2
                else:
                    start_y = (screen.get_height() - total_height) // 2 + 350
                for i, line in enumerate(lines):
                    text_surface = font.render(line, True, (255, 255, 255))
                    x_txt = (screen.get_width() - text_surface.get_width()) // 2
                    y_txt = start_y + i * font.get_height()
                    screen.blit(text_surface, (x_txt, y_txt))
                pygame.display.flip()
                clock.tick(60)
    pygame.display.quit()
"""
Experiment runner for multiarrangement experiments.

This module contains the main experiment logic refactored from the standalone script
to be callable as a library function.
"""

import cv2
import os
import random
import pygame
import sys
import numpy as np
import math
import threading
import pandas as pd
import textwrap
from pathlib import Path
from typing import List, Union, Optional
import tempfile
import subprocess

# Configuration Constants
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 1000
CIRCLE_RADIUS = 355
CIRCLE_THICKNESS = 4
DOUBLE_CLICK_TIMEOUT = 350  # milliseconds
BUTTON_SIZE = (80, 50)
LARGE_BUTTON_SIZE = (160, 100)
SCALE_FACTOR = 3.5  # Increased to make frames smaller
VIDEO_PREVIEW_SIZE = (1200, 800)
POPUP_VIDEO_SCALE = 2.0

# Supported file extensions
VIDEO_EXTENSIONS = ['.avi', '.mp4', '.mov', '.mkv', '.wmv']
AUDIO_EXTENSIONS = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
GRAY = (128, 128, 128)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# --- Initialize the mixer BEFORE pygame.init() to avoid audio device hiccups ---
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=1024)


def get_media_files(directory):
    """Get all supported media files from directory."""
    if not os.path.exists(directory):
        return []
    
    media_files = []
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
            media_files.append(f)
    return media_files

def is_audio_file(filename):
    """Check if file is an audio file."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in AUDIO_EXTENSIONS

def get_safe_fps(cap):
    """Get FPS with fallback to prevent division by zero."""
    fps = cap.get(cv2.CAP_PROP_FPS)
    return fps if fps > 0 else 30  # Default fallback

def is_circle_inside_circle(rect, circle_center, circle_radius):
    """
    Precise circle containment logic.
    Check if the red circle is NOT touching the inside of the white circle boundary.
    Invalid (returns False) when red circle touches the white circle from inside.
    """
    # Get center of the frame rectangle
    frame_center_x = rect.centerx
    frame_center_y = rect.centery
    
    # Calculate the ACTUAL radius of the drawn red circle (same as in rendering)
    drawn_circle_radius = max(30, int(rect.width / 3.0))  # Must match the drawing code
    
    # Calculate distance between centers
    distance = math.sqrt((frame_center_x - circle_center[0])**2 + 
                        (frame_center_y - circle_center[1])**2)
    
    # Allow circles to get very close but not actually touch
    tolerance = 16  # Require clearance from white circle boundary
    
    # Valid position: red circle must stay inside white circle boundary
    # Invalid when: distance + red_radius >= white_radius - tolerance (touching or overlapping)
    return distance + drawn_circle_radius < circle_radius - tolerance

def check_all_inside_improved(rects, circle_center, circle_radius):
    """Check if all frames are inside the circle using improved logic."""
    return all(is_circle_inside_circle(rect, circle_center, circle_radius) for rect in rects)

def create_audio_icon(height, width):
    """Create a visual icon for audio files using the provided audio icon image."""
    import cv2
    import os
    
    # Try to load the audio icon image - first try the new icon, then fallback to old
    # Probe common packaged locations
    base = os.path.dirname(__file__)
    # Prefer the canonical Audio.png used by the set-cover UI, then fall back
    candidates = [
        os.path.join(base, "Audio.png"),
        os.path.join(base, "test_audio_icon_new.png"),
        os.path.join(base, "data", "Audio.png"),
        os.path.join(base, "data", "test_audio_icon_new.png"),
        os.path.join(os.path.dirname(base), "Audio.png"),
        os.path.join(os.path.dirname(base), "test_audio_icon_new.png"),
    ]
    audio_icon_path = next((p for p in candidates if os.path.exists(p)), None)
    
    if audio_icon_path and os.path.exists(audio_icon_path):
        # Load the image
        icon_img = cv2.imread(audio_icon_path, cv2.IMREAD_COLOR)
        
        if icon_img is not None:
            # Resize to match the frame dimensions
            icon_img = cv2.resize(icon_img, (width, height))
            
            # Reverse white and black colors
            # Convert to RGB if needed (OpenCV loads as BGR)
            icon_img = cv2.cvtColor(icon_img, cv2.COLOR_BGR2RGB)
            
            # Create a mask for white pixels (close to white)
            white_mask = np.all(icon_img > [200, 200, 200], axis=2)
            # Create a mask for black pixels (close to black)  
            black_mask = np.all(icon_img < [50, 50, 50], axis=2)
            
            # Swap colors: white becomes black, black becomes white
            icon_img[white_mask] = [0, 0, 0]      # White -> Black
            icon_img[black_mask] = [255, 255, 255]  # Black -> White
            
            return icon_img
    
    # Fallback: create a simple audio icon if image not found
    print(f"Warning: Audio icon not found at {audio_icon_path}, using fallback icon")
    icon = np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)  # Dark background
    
    # Add simple speaker icon as fallback
    center_x, center_y = width // 2, height // 2
    
    # Draw speaker shape
    speaker_width = width // 8
    speaker_height = height // 6
    speaker_x = center_x - speaker_width
    speaker_y = center_y - speaker_height // 2
    
    # Speaker rectangle (white)
    icon[speaker_y:speaker_y + speaker_height, speaker_x:speaker_x + speaker_width] = [255, 255, 255]
    
    # Sound waves (white arcs)
    for i in range(3):
        radius = speaker_width + i * 15
        thickness = 2
        color = (255, 255, 255)  # White color
        # Draw partial circle for sound wave effect
        start_angle = -30
        end_angle = 30
        cv2.ellipse(icon, (center_x, center_y), (radius, radius), 0, start_angle, end_angle, color, thickness)
    
    return icon

# ---------- Audio playback that keeps fullscreen focus ----------

def ensure_mixer():
    """Make sure pygame.mixer is ready."""
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        except pygame.error as e:
            print(f"Warning: pygame.mixer init failed: {e}")

def play_audio(audio_path):
    """
    Play audio without opening any OS media player windows.
    Primary: pygame.mixer (non-blocking, keeps fullscreen).
    Fallback: ffplay -nodisp -autoexit hidden (for formats mixer can't decode).
    """
    import sys
    ensure_mixer()

    # Try in-process playback first (no window/focus change)
    try:
        if pygame.mixer.get_init():
            # Stop previous track cleanly if needed
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(200)
            pygame.mixer.music.load(audio_path)  # supports wav/ogg/mp3 on most builds
            pygame.mixer.music.play()
            return
    except pygame.error as e:
        print(f"pygame.mixer couldn't play {os.path.basename(audio_path)}: {e}")

    # Fallback: ffplay without display, hidden window so fullscreen isn't disturbed
    try:
        creationflags = 0
        startupinfo = None
        if sys.platform.startswith("win"):
            # CREATE_NO_WINDOW to avoid any console popping up
            creationflags = 0x08000000
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", audio_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
    except Exception as e:
        print(f"Fallback audio failed for {audio_path}. "
              f"Install FFmpeg (ffplay) or convert to WAV/OGG/MP3. Error: {e}")

# ----------------------------------------------------------------

def play_video(video_path):
    """Function plays video in a popup window that appears on top of borderless fullscreen"""
    # Handle audio files differently
    if is_audio_file(video_path):
        play_audio(video_path)
        return
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return  # Skip if video can't be opened
    
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = get_safe_fps(cap)
        delay = int(1000 / fps)
        
        # Create window that appears on top
        window_name = 'Video Player'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, int(width * POPUP_VIDEO_SCALE), int(height * POPUP_VIDEO_SCALE))
        
        # Try to bring window to front (works better with borderless than fullscreen)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(delay) & 0xFF
                if key == ord('q') or key == ord(' ') or key == 27:  # q, space, or ESC
                    break
            else:
                break
                
    finally:
        cap.release()
        cv2.destroyAllWindows()

def display_video(video_path, screen, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Again function takes a path and plays the video but on the same window"""
    # Handle audio files differently  
    if is_audio_file(video_path):
        return  # Audio files are skipped in show_set, so this shouldn't be called
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return  # Skip if video can't be opened
    
    try:
        fps = get_safe_fps(cap)
        delay = int(1000 / fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Clear to black background first
                screen.fill(BLACK)
                
                frame = cv2.resize(frame, VIDEO_PREVIEW_SIZE)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = pygame.surfarray.make_surface(np.rot90(frame))
                pos_x = (screen.get_width() - frame.get_width()) // 2
                pos_y = (screen.get_height() - frame.get_height()) // 2
                screen.blit(frame, (pos_x, pos_y))
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        safe_pygame_quit()
                        sys.exit(0)
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        return
                pygame.time.wait(delay)
            else:
                break
    finally:
        cap.release()

def show_set(batch, media_dir, screen, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Function takes a list and uses the videopaths to call on display_video"""
    # Clear screen to pure black before showing videos
    screen.fill(BLACK)
    pygame.display.flip()
    
    for media_path in batch:
        # Skip audio files - they can't be displayed as videos
        if is_audio_file(media_path):
            continue
        full_path = os.path.join(media_dir, media_path)
        display_video(full_path, screen, SCREEN_WIDTH, SCREEN_HEIGHT)

def get_first_frames(batch, media_dir, show_first_frames, frame_cache):
    """Function takes a list as an argument then returns every first frame that can be found by using the path from the list"""
    first_frames = []
    for media_file in batch:
        media_path = os.path.join(media_dir, media_file)
        
        # Check if we should show first frames or use placeholder
        if not show_first_frames:
            # Create question mark placeholder
            placeholder = np.full((480, 640, 3), (200, 200, 200), dtype=np.uint8)
            first_frames.append(placeholder)
            continue
            
        # Check cache first
        if media_path in frame_cache:
            first_frames.append(frame_cache[media_path])
            continue
            
        # Handle audio files
        if is_audio_file(media_file):
            # Create sound icon for audio files
            sound_icon = create_audio_icon(480, 640)
            frame_cache[media_path] = sound_icon
            first_frames.append(sound_icon)
            continue
            
        # Load video frame and cache if not in cache
        cap = cv2.VideoCapture(media_path)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Resize video frame to standard dimensions (same as audio icons)
                frame = cv2.resize(frame, (640, 480))  # width, height - match audio dimensions
                frame_cache[media_path] = frame  # Cache the frame
                first_frames.append(frame)
            else:
                # Add a black frame as fallback
                fallback = np.zeros((480, 640, 3), dtype=np.uint8)
                frame_cache[media_path] = fallback
                first_frames.append(fallback)
            cap.release()
        else:
            # Add a black frame as fallback
            fallback = np.zeros((480, 640, 3), dtype=np.uint8)
            frame_cache[media_path] = fallback
            first_frames.append(fallback)
    return first_frames

def save_results(df, output_dir, participant_id="participant"):
    """Save the experiment results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # Save distance matrix as CSV
    csv_path = output_path / f"{participant_id}_distances_{timestamp}.csv"
    df.to_csv(csv_path)
    print(f"Distance matrix saved to: {csv_path}")
    
    # Save distance matrix as Excel
    excel_path = output_path / f"{participant_id}_distances_{timestamp}.xlsx"
    df.to_excel(excel_path)
    print(f"Distance matrix saved to: {excel_path}")
    
    return str(csv_path)

def safe_pygame_quit():
    """Stop audio cleanly and quit pygame."""
    try:
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            try:
                pygame.mixer.quit()
            except Exception:
                pass
    except Exception:
        pass
    pygame.quit()

def run_multiarrangement_experiment(input_dir: str, batches, output_dir: str, 
                                show_first_frames: bool = True, fullscreen: bool = True, language: str = "en", instructions="default"):
    """
    Run the main multiarrangement experiment.
    
    Args:
        input_dir: Directory containing media files
        batches: List of batches or path to batch file
        output_dir: Directory to save results  
        show_first_frames: Whether to show video frames
        fullscreen: Whether to run in fullscreen mode
        
    Returns:
        Path to saved results file
    """
    
    # Handle batches input
    if isinstance(batches, (str, Path)):
        # Load from file
        with open(batches, 'r') as f:
            batch_list = [[int(num) for num in line.strip().replace('(', '').replace(')', '').split(', ')] for line in f]
    else:
        # Use provided list
        batch_list = batches
    
    # Validate batch configuration
    all_indices = set()
    for batch in batch_list:
        all_indices.update(batch)
    
    max_index = max(all_indices) if all_indices else -1
    expected_indices = set(range(max_index + 1))
    
    # Get media files and detect type
    media_files = get_media_files(input_dir)
    if not media_files:
        raise ValueError(f"No supported media files found in {input_dir}")

    # Detect mode automatically
    video_count = sum(1 for f in media_files if not is_audio_file(f))
    audio_count = len(media_files) - video_count
    if video_count > 0 and audio_count == 0:
        mode = "video"
    elif audio_count > 0 and video_count == 0:
        mode = "audio"
    else:
        mode = "video"
        print("Warning: Mixed media detected. Defaulting to video mode.")

    # Show instructions for detected mode and language
    if instructions is None:
        pass  # Skip instructions
    elif instructions == "default":
        show_instructions_pygame(mode=mode, language=language)
    elif isinstance(instructions, list):
        # Show custom instructions (text only, centered)
        pygame.init()
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        font = pygame.font.Font(None, 48)
        clock = pygame.time.Clock()
        import textwrap
        for instruction in instructions:
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()
                screen.fill((0, 0, 0))
                lines = textwrap.wrap(instruction, width=50)
                total_height = len(lines) * font.get_height()
                start_y = (screen.get_height() - total_height) // 2
                for i, line in enumerate(lines):
                    text_surface = font.render(line, True, (255, 255, 255))
                    x_txt = (screen.get_width() - text_surface.get_width()) // 2
                    y_txt = start_y + i * font.get_height()
                    screen.blit(text_surface, (x_txt, y_txt))
                pygame.display.flip()
                clock.tick(60)
        pygame.display.quit()
    
    # Validate that number of videos matches batch configuration
    n_media_files = len(media_files)
    n_unique_indices = len(all_indices)
    expected_max_index = n_media_files - 1  # Since indices should be 0-based
    
    print(f"🔍 Validation Check:")
    print(f"   Media files found: {n_media_files}")
    print(f"   Unique indices in batches: {n_unique_indices}")
    print(f"   Max index in batches: {max_index}")
    print(f"   Expected max index: {expected_max_index}")
    
    if max_index >= n_media_files:
        raise ValueError(f"Batch indices go up to {max_index} but only {n_media_files} media files found! "
                        f"Indices should be 0-{expected_max_index}")
    
    if n_unique_indices != n_media_files:
        missing_indices = expected_indices - all_indices
        extra_indices = all_indices - expected_indices
        
        error_msg = f"CRITICAL ERROR: Batch/Media mismatch!\n"
        error_msg += f"   Unique indices in batches: {n_unique_indices}\n"
        error_msg += f"   Media files found: {n_media_files}\n"
        
        if missing_indices:
            error_msg += f"   Missing indices: {sorted(missing_indices)}\n"
        if extra_indices:
            error_msg += f"   Extra indices: {sorted(extra_indices)}\n"
            
        error_msg += f"\nThis mismatch will cause crashes or incorrect results!"
        error_msg += f"\n\n💡 SOLUTION:"
        error_msg += f"\n   # Auto-detect correct number of videos:"
        error_msg += f"\n   n_stimuli = ml.auto_detect_stimuli('{input_dir}')"
        error_msg += f"\n   batches = ml.create_batches(n_videos, batch_size)"
        error_msg += f"\n\n   # Or create directly for {n_media_files} videos:"
        error_msg += f"\n   batches = ml.create_batches({n_media_files}, batch_size)"
        
        raise ValueError(error_msg)
    
    # Automatically detect media type
    video_count = sum(1 for f in media_files if not is_audio_file(f))
    audio_count = len(media_files) - video_count
    
    print(f"✅ Found {len(media_files)} media files ({video_count} videos, {audio_count} audio)")
    
    # Shuffle media files
    random.shuffle(media_files)
    
    media_names = [os.path.splitext(f)[0] for f in media_files]
    
    # Initialize pygame
    pygame.init()
    
    # Initialize screen
    global SCREEN_WIDTH, SCREEN_HEIGHT
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.NOFRAME)
        SCREEN_WIDTH = screen.get_width()
        SCREEN_HEIGHT = screen.get_height()
    else:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    
    pygame.display.set_caption("Multiarrangement Experiment")
    
    # Initialize DataFrame for distance matrix
    n_media = len(media_names)
    df = pd.DataFrame([[None for _ in range(n_media)] for _ in range(n_media)], 
                      index=media_names, columns=media_names)
    for i in range(n_media):
        df.iloc[i, i] = 0
    
    frame_cache = {}
    
    # Show instructions (simplified)
    font = pygame.font.Font(None, 66)
    message = "Press SPACE to start the experiment"
    
    show_instruction = True
    while show_instruction:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                safe_pygame_quit()
                return None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    show_instruction = False
        
        screen.fill(BLACK)
        text = font.render(message, True, WHITE)
        text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        screen.blit(text, text_rect)
        pygame.display.flip()
    
    # Process each batch
    for batch_indexes in batch_list:
        batch_media = [media_files[i] for i in batch_indexes]
        frame_names = []
        
        # PHASE 1: Show videos for this batch (NO BUTTON)
        print(f"📺 Showing videos for batch {batch_indexes}...")
        show_set(batch_media, input_dir, screen, SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Clear screen completely after video preview
        screen.fill(BLACK)
        pygame.display.flip()
        
        # Get first frames
        my_frames = get_first_frames(batch_media, input_dir, show_first_frames, frame_cache)
        
        # PHASE 2: Set up the arrangement interface (WITH BUTTON)
        print(f"🎯 Now arrange the videos by similarity...")
        screen.fill(BLACK)
        
        # Dynamic circle sizing for fullscreen
        circle_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        dynamic_radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 3
        circle_radius = dynamic_radius if fullscreen else CIRCLE_RADIUS
        circle_diameter = 2 * circle_radius
        big_circle_rect = pygame.Rect(circle_center[0] - circle_radius, circle_center[1] - circle_radius, 
                                     circle_diameter, circle_diameter)
        
        pygame.draw.circle(screen, BLACK, circle_center, circle_radius)
        pygame.draw.circle(screen, WHITE, circle_center, circle_radius, CIRCLE_THICKNESS)
        pygame.display.flip()
        
        # Create frame surfaces and arrange them in circle
        angle_step = 2 * math.pi / len(my_frames)
        frames = []
        rects = []
        frame_clicked = [False] * len(my_frames)
        
        for i, frame in enumerate(my_frames):
            # Process frame for display
            frame = frame[:, :, ::-1]  # BGR to RGB
            frame_surface = pygame.surfarray.make_surface(frame)       
            frame_surface = pygame.transform.flip(frame_surface, False, True)
            frame_surface = pygame.transform.scale(frame_surface, 
                                                  (int(frame_surface.get_width() // SCALE_FACTOR), 
                                                   int(frame_surface.get_height() // SCALE_FACTOR)))
            frame_surface = pygame.transform.rotate(frame_surface, -90)
            frame_width, frame_height = frame_surface.get_size()
            angle = i * angle_step
            
            # Calculate position around circle
            x = circle_center[0] + (circle_radius + frame_width - 50) * math.cos(angle) - frame_width / 2
            y = circle_center[1] - (circle_radius + frame_height - 50) * math.sin(angle) - frame_height / 2  
            
            # Create circular mask
            mask_surface = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
            pygame.draw.circle(mask_surface, (255, 255, 255, 128), 
                             (frame_width // 2, frame_height // 2), 
                             min(frame_width, frame_height) // 2)
            frame_surface.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            frame_surface.set_colorkey(BLACK)
            
            screen.blit(frame_surface, (x, y))
            frames.append(frame_surface)
            rects.append(pygame.Rect(x, y, frame_width, frame_height))
        
        # Main interaction loop
        dragging = False
        dragged_frame_index = None
        drag_offset_x = 0
        drag_offset_y = 0
        pygame.display.flip()
        running = True
        last_click_time = None
        
        # Button setup
        button_pos = (150, SCREEN_HEIGHT - 190)
        button_rect = pygame.Rect(button_pos, BUTTON_SIZE)
        button_font = pygame.font.Font(None, 24)
        
        while running:
            all_inside = check_all_inside_improved(rects, circle_center, circle_radius)
            all_clicked = all(frame_clicked)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    safe_pygame_quit()
                    return None
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        safe_pygame_quit()
                        return None
                elif event.type == pygame.MOUSEBUTTONDOWN and button_rect.collidepoint(event.pos):    
                    if all_inside and all_clicked:
                        # Calculate distances and save
                        centers = [rect.center for rect in rects]
                        for media_file in batch_media[:len(centers)]:
                            frame_name = os.path.splitext(media_file)[0]  
                            frame_names.append(frame_name)
                        
                        for i in range(len(centers)):
                            for j in range(i+1, len(centers)):
                                dx = centers[i][0] - centers[j][0]
                                dy = centers[i][1] - centers[j][1]
                                distance = np.sqrt(dx**2 + dy**2)
                                
                                if frame_names[i] in df.columns and frame_names[j] in df.index:
                                    if isinstance(df.loc[frame_names[i], frame_names[j]], list):
                                        df.loc[frame_names[i], frame_names[j]].append(distance)
                                        df.loc[frame_names[j], frame_names[i]].append(distance)
                                    else:
                                        df.loc[frame_names[i], frame_names[j]] = [distance]
                                        df.loc[frame_names[j], frame_names[i]] = [distance]
                        
                        # Calculate averages
                        for i in range(len(centers)):
                            for j in range(i+1, len(centers)):
                                if isinstance(df.loc[frame_names[i], frame_names[j]], list):
                                    avg_distance = np.mean(df.loc[frame_names[i], frame_names[j]])
                                    df.loc[frame_names[i], frame_names[j]] = avg_distance
                                    df.loc[frame_names[j], frame_names[i]] = avg_distance
                        
                        running = False
                        break
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    current_time = pygame.time.get_ticks()
                    if last_click_time is not None and current_time - last_click_time <= DOUBLE_CLICK_TIMEOUT:
                        # Double click - play video (or audio via play_video->play_audio)
                        for i in range(len(frames)):
                           if rects[i].collidepoint(event.pos):
                               frame_clicked[i] = True  
                               video_path = os.path.join(input_dir, batch_media[i])  
                               video_thread = threading.Thread(target=play_video, args=(video_path,))
                               video_thread.start()
                               break
                        last_click_time = current_time
                    else:
                        # Single click - start dragging
                        for i in range(len(frames)):
                            if rects[i].collidepoint(event.pos):
                                dragging = True
                                dragged_frame_index = i
                                drag_offset_x = event.pos[0] - rects[i].x
                                drag_offset_y = event.pos[1] - rects[i].y
                                last_click_time = current_time
                                break
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    dragging = False
                
                elif event.type == pygame.MOUSEMOTION:
                    if dragging:
                        rects[dragged_frame_index].x = event.pos[0] - drag_offset_x
                        rects[dragged_frame_index].y = event.pos[1] - drag_offset_y
            
            # Render everything
            screen.fill(BLACK)
            pygame.draw.circle(screen, BLACK, circle_center, circle_radius)
            pygame.draw.circle(screen, WHITE, circle_center, circle_radius, CIRCLE_THICKNESS)
            
            # Draw frames FIRST, then outlines ON TOP
            for i in range(len(frames)):
                # Draw the video frame first
                screen.blit(frames[i], rects[i].topleft)
                
                # Determine outline color based on click status and position
                if frame_clicked[i] and is_circle_inside_circle(rects[i], circle_center, circle_radius):
                    color = GREEN  # Clicked and valid position
                else:
                    color = RED    # Not clicked yet OR invalid position
                
                # Draw colored outline ON TOP of the video frame for visibility
                frame_circle_radius = max(35, int(rects[i].width / 2.5))  # Slightly smaller radius
                pygame.draw.circle(screen, color, rects[i].center, frame_circle_radius, 4)  # Thinner outline
            
            # Draw pairwise connection lines OVER the video circles while dragging
            if dragging and dragged_frame_index is not None:
                if is_circle_inside_circle(rects[dragged_frame_index], circle_center, circle_radius):
                    # Draw red lines from dragged frame to all other frames inside the circle
                    for i in range(len(frames)):
                        if i != dragged_frame_index and is_circle_inside_circle(rects[i], circle_center, circle_radius):
                            # Create semi-transparent surface for the line
                            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                            # Draw red line with opacity OVER the video circles
                            pygame.draw.line(s, RED + (115,), rects[dragged_frame_index].center, rects[i].center, 7)          
                            screen.blit(s, (0, 0))
            
            # Draw button
            button_color = GREEN if (all_inside and all_clicked) else RED
            pygame.draw.rect(screen, button_color, button_rect)
            button_text = button_font.render('Done', True, BLACK)
            screen.blit(button_text, button_text.get_rect(center=button_rect.center))
            
            pygame.display.flip()
    
    # Save results and cleanup
    try:
        result_file = save_results(df, output_dir)
        safe_pygame_quit()
        return result_file
    except Exception as e:
        print(f"Error saving results: {e}")
        safe_pygame_quit()
        return None
