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
        elif mode == "image":
            instructions = [
                ("Welcome to the image similarity arrangement experiment.", "img1.PNG"),
                ("You will see groups of images that you need to arrange by similarity.", "similar.mp4"),
                ("First, you will view all images in the group.", "Same.mkv"),
                ("Then, arrange the image circles by dragging them.", "drag.mp4"),
                ("Place similar images close together, dissimilar images far apart.", "similar.mp4"),
                ("Double-click any circle to view the image again.", "Doubleclick.mp4"),
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
    from .utils.file_utils import resolve_packaged_file, resolve_packaged_dir
    for instruction, media in instructions:
        waiting = True
        show_media = (mode == "video")
        if show_media and media and media.lower().endswith(('.mp4', '.mkv')):
            # Play full video in loop until SPACE is pressed
            # Resolve instruction video path robustly
            try:
                video_path = str(resolve_packaged_file('demovids', media))
            except FileNotFoundError:
                # Final fallback: relative paths if running from repo
                if os.path.exists(media):
                    video_path = media
                elif os.path.exists(os.path.join('demovids', media)):
                    video_path = os.path.join('demovids', media)
                else:
                    video_path = os.path.join(os.path.dirname(__file__), 'demovids', media)
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
                        # Resolve packaged image path (robust to data_files placement)
                        img_path = str(resolve_packaged_file('data', media))
                        if not os.path.exists(img_path):
                            # Try demovids as some images may live next to videos
                            img_path = str(resolve_packaged_file('demovids', media))
                            
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
                # Center text for audio and image modes; video uses lower offset
                if mode in ("audio", "image"):
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
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp']

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
        if ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS or ext in IMAGE_EXTENSIONS:
            media_files.append(f)
    return media_files

def is_audio_file(filename):
    """Check if file is an audio file."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in AUDIO_EXTENSIONS

def is_image_file(filename):
    """Check if file is an image file."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS

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
    """Show a preview of each stimulus in the batch (videos or images)."""
    # Clear screen to pure black before showing videos
    screen.fill(BLACK)
    pygame.display.flip()
    
    for media_path in batch:
        full_path = os.path.join(media_dir, media_path)
        # Skip audio files - can't display in video slot; audio will be previewed by icon later
        if is_audio_file(media_path):
            continue
        if is_image_file(media_path):
            display_image(full_path, screen, SCREEN_WIDTH, SCREEN_HEIGHT)
        else:
            display_video(full_path, screen, SCREEN_WIDTH, SCREEN_HEIGHT)

def get_first_frames(batch, media_dir, show_first_frames, frame_cache):
    """Return thumbnail frames for each stimulus in the batch.

    - Videos: first frame
    - Images: the image itself
    - Audio: audio icon
    """
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
        
        # Images
        if is_image_file(media_file):
            img = cv2.imread(media_path)
            if img is not None:
                img = cv2.resize(img, (640, 480))
                frame_cache[media_path] = img
                first_frames.append(img)
                continue
            # Fall through to black placeholder if failed

        # Videos: load first frame
        cap = cv2.VideoCapture(media_path)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (640, 480))
                frame_cache[media_path] = frame
                first_frames.append(frame)
            else:
                fallback = np.zeros((480, 640, 3), dtype=np.uint8)
                frame_cache[media_path] = fallback
                first_frames.append(fallback)
            cap.release()
        else:
            fallback = np.zeros((480, 640, 3), dtype=np.uint8)
            frame_cache[media_path] = fallback
            first_frames.append(fallback)
    return first_frames

def display_image(image_path, screen, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Display a still image centered on the screen; exit on SPACE/ESC."""
    if not os.path.exists(image_path):
        return
    img = cv2.imread(image_path)
    if img is None:
        return
    # Fit inside preview size maintaining aspect ratio
    target_w, target_h = VIDEO_PREVIEW_SIZE
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    img = cv2.cvtColor(cv2.resize(img, (new_w, new_h)), cv2.COLOR_BGR2RGB)
    surf = pygame.surfarray.make_surface(np.rot90(img))
    pos_x = (screen.get_width() - surf.get_width()) // 2
    pos_y = (screen.get_height() - surf.get_height()) // 2
    waiting = True
    while waiting:
        screen.fill(BLACK)
        screen.blit(surf, (pos_x, pos_y))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                safe_pygame_quit(); sys.exit(0)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                waiting = False

def confirm_mixed_prompt(n_vid: int, n_img: int, n_aud: int) -> bool:
    """Show a simple pygame prompt to confirm running with mixed media.

    Returns True to proceed, False to abort.
    """
    pygame.init()
    # Use a small centered window to avoid conflicts with later fullscreen
    screen = pygame.display.set_mode((800, 320))
    font = pygame.font.Font(None, 36)
    title = pygame.font.Font(None, 44)
    text = [
        "Mixed media detected in the input directory:",
        f" - Videos: {n_vid} | Images: {n_img} | Audio: {n_aud}",
        "Proceed with a mixed set? (Y = continue, N/ESC = cancel)"
    ]
    proceed = None
    while proceed is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                proceed = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_n, pygame.K_ESCAPE):
                    proceed = False
                elif event.key in (pygame.K_y, pygame.K_RETURN, pygame.K_SPACE):
                    proceed = True
        screen.fill((0,0,0))
        y = 50
        screen.blit(title.render(text[0], True, (255,255,255)), (40, y)); y += 60
        screen.blit(font.render(text[1], True, (200,200,200)), (40, y)); y += 60
        screen.blit(font.render(text[2], True, (255,255,0)), (40, y))
        pygame.display.flip()
        pygame.time.wait(30)
    pygame.display.quit()
    return bool(proceed)

def save_results(df, output_dir, participant_id="participant", timestamp: Optional[str] = None):
    """Save the experiment results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not timestamp:
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

def run_multiarrangement_experiment(
    input_dir: str,
    batches,
    output_dir: str,
    *,
    show_first_frames: bool = True,
    fullscreen: bool = True,
    language: str = "en",
    instructions = "default",
    # Fusion controls (set‑cover)
    setcover_weight_mode: str = 'max',
    setcover_weight_alpha: float = 2.0,
    rng_seed: int = None,
    use_inverse_mds: bool = False,
    inverse_mds_max_iter: int = 15,
    inverse_mds_step_c: float = 0.3,
    inverse_mds_tol: float = 1e-4,
    max_adjacent_overlap: Optional[int] = None,
    # Robust weighting options for set‑cover fusion
    robust_method: Optional[str] = None,  # 'winsor' | 'huber' | None
    robust_winsor_high: float = 0.98,
    robust_huber_c: float = 0.9,
):
    """
    Run the main multiarrangement experiment.
    
    Args:
        input_dir: Directory containing media files
        batches: List of batches or path to batch file
        output_dir: Directory to save results  
        show_first_frames: Whether to show video frames
        fullscreen: Whether to run in fullscreen mode
        setcover_weight_mode: 'max' (per‑trial max‑norm), 'rms' (RMS‑matched), or 'k2012' (raw‑distance weights with RMS‑matched numerator)
        
    Returns:
        Path to saved results file
    """
    
    # Seed RNG for reproducibility (shuffle, seating jitter, etc.)
    try:
        import os as _os
        if rng_seed is None:
            rng_seed = int.from_bytes(_os.urandom(8), 'little')
        random.seed(int(rng_seed))
        try:
            import numpy as _np
            _np.random.seed(int(rng_seed) & 0x7fffffff)
        except Exception:
            pass
    except Exception:
        pass

    # Handle batches input
    if isinstance(batches, (str, Path)):
        # Load from file
        with open(batches, 'r') as f:
            batch_list = [[int(num) for num in line.strip().replace('(', '').replace(')', '').split(', ')] for line in f]
    else:
        # Use provided list
        batch_list = batches

    # Optional: reorder to reduce adjacent overlap (interleaving)
    def _reorder_min_adjacent_overlap(bl: list[list[int]], max_overlap: int) -> list[list[int]]:
        if not bl:
            return bl
        rem = bl[:]
        ordered = [rem.pop(0)]
        last = set(ordered[-1])
        while rem:
            # pick batch with minimal overlap with last; tie-breaker: smaller overlap then shorter length
            best_i = None
            best_score = None
            for idx, cand in enumerate(rem):
                ov = len(last & set(cand))
                score = (ov, len(cand))
                if best_score is None or score < best_score:
                    best_score = score; best_i = idx
            chosen = rem.pop(best_i)
            ordered.append(chosen)
            last = set(chosen)
        # If the best effort still violates the max_overlap, it's unavoidable under given batches
        return ordered

    if isinstance(max_adjacent_overlap, int):
        try:
            batch_list = _reorder_min_adjacent_overlap(batch_list, max_adjacent_overlap)
        except Exception:
            pass
    
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

    # Detect mode automatically (video/image/audio)
    vid = sum(1 for f in media_files if (os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS))
    aud = sum(1 for f in media_files if (os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS))
    img = sum(1 for f in media_files if (os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS))
    kinds = sum(1 for c in (vid, aud, img) if c > 0)
    if kinds == 0:
        raise ValueError("No supported media in directory.")
    if kinds > 1:
        # Ask for confirmation before proceeding with mixed directory
        if not confirm_mixed_prompt(vid, img, aud):
            print("User declined to run with mixed media.")
            return None
    # Choose instruction mode by dominant or single type
    if img > 0 and vid == 0 and aud == 0:
        mode = "image"
    elif vid > 0 and aud == 0 and img == 0:
        mode = "video"
    elif aud > 0 and vid == 0 and img == 0:
        mode = "audio"
    else:
        # Mixed: prefer video instructions when videos exist, else image
        mode = "video" if vid > 0 else ("image" if img > 0 else "audio")

    # Convenience flag for image-only behavior tweaks
    image_only_mode = (mode == "image")

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
    
    print(f"✅ Found {len(media_files)} media files ({vid} videos, {img} images, {aud} audio)")
    
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
    
    # Initialize accumulation buffers for weighted fusion
    n_media = len(media_names)
    name_to_idx = {name: i for i, name in enumerate(media_names)}
    # Num and W per Ma.md/README: per-trial max-normalized distances; weights = (d/max)^alpha
    Num = np.zeros((n_media, n_media), dtype=float)
    W = np.zeros((n_media, n_media), dtype=float)
    # For optional inverse-MDS, keep trial arrangements
    trial_arrangements = []  # list of (subset_indices, positions_by_index)
    
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
    trial_logs = []  # per-trial subset indices and positions
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
        # In image-only mode, do not require double-clicks; treat all as viewed.
        frame_clicked = [True] * len(my_frames) if image_only_mode else [False] * len(my_frames)
        
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
            # In image-only mode, do not require clicks at all; in mixed, images also do not require clicks
            def is_image_idx(i: int) -> bool:
                return os.path.splitext(batch_media[i])[1].lower() in IMAGE_EXTENSIONS
            all_clicked = all(frame_clicked[i] or is_image_idx(i) for i in range(len(frames)))
            
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
                        # Calculate distances for this trial
                        centers = [rect.center for rect in rects]
                        # Build names and indices for items in this batch
                        frame_names = []
                        frame_indices = []
                        for media_file in batch_media[:len(centers)]:
                            name = os.path.splitext(media_file)[0]
                            frame_names.append(name)
                            frame_indices.append(name_to_idx[name])

                        # Compute pairwise distances and per-trial max
                        m = len(centers)
                        if m >= 2:
                            dists = np.zeros((m, m), dtype=float)
                            maxd = 0.0
                            for i in range(m):
                                xi, yi = centers[i]
                                for j in range(i+1, m):
                                    xj, yj = centers[j]
                                    dij = float(np.hypot(xi - xj, yi - yj))
                                    dists[i, j] = dists[j, i] = dij
                                    if dij > maxd:
                                        maxd = dij
                            # Per-trial normalization and weighted accumulation
                            if setcover_weight_mode == 'max':
                                if maxd <= 1e-12:
                                    norm = 0.0
                                else:
                                    norm = 1.0 / maxd
                                alpha = float(setcover_weight_alpha)
                                for i in range(m):
                                    gi = frame_indices[i]
                                    for j in range(i+1, m):
                                        gj = frame_indices[j]
                                        dnorm = dists[i, j] * norm
                                        # Optional robust weighting (winsor or huber)
                                        if robust_method == 'winsor':
                                            hi = float(robust_winsor_high)
                                            if hi > 0.0:
                                                dnorm = min(dnorm, hi)
                                            w = dnorm ** alpha
                                        elif robust_method == 'huber':
                                            c = float(robust_huber_c)
                                            if dnorm <= 0.0:
                                                w = 0.0
                                            else:
                                                wfactor = 1.0 if dnorm <= c else (c / dnorm)
                                                w = (dnorm ** alpha) * wfactor
                                        else:
                                            w = dnorm ** alpha
                                        # accumulate symmetric
                                        Num[gi, gj] += w * dnorm
                                        Num[gj, gi] += w * dnorm
                                        W[gi, gj] += w
                                        W[gj, gi] += w
                            # Per-trial log
                            positions_by_index = {int(frame_indices[i]): [float(centers[i][0]), float(centers[i][1])] for i in range(m)}
                            trial_logs.append({
                                "subset": [int(x) for x in frame_indices],
                                "positions": positions_by_index,
                            })

                            # Record trial for optional inverse-MDS refinement
                            if use_inverse_mds:
                                positions_by_index = {frame_indices[i]: (float(centers[i][0]), float(centers[i][1])) for i in range(m)}
                                trial_arrangements.append((list(frame_indices), positions_by_index))

                        running = False
                        break
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    current_time = pygame.time.get_ticks()
                    if last_click_time is not None and current_time - last_click_time <= DOUBLE_CLICK_TIMEOUT:
                        # Double click behavior
                        # - Image-only: ignore double clicks completely (no popups, no state change)
                        # - Audio/Video: allow replay (mark clicked for video/audio)
                        if not image_only_mode:
                            for i in range(len(frames)):
                                if rects[i].collidepoint(event.pos):
                                    # For images, do nothing on double-click (no popups, no state change)
                                    if is_image_idx(i):
                                        break
                                    frame_clicked[i] = True
                                    media_path_clicked = os.path.join(input_dir, batch_media[i])
                                    video_thread = threading.Thread(target=play_video, args=(media_path_clicked,))
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
                
                # Determine outline color based on click status and position.
                # Images never require clicks (even in mixed sets); only position matters for them.
                considered_clicked = True if (image_only_mode or is_image_idx(i)) else frame_clicked[i]
                if considered_clicked and is_circle_inside_circle(rects[i], circle_center, circle_radius):
                    color = GREEN  # Clicked and valid position
                else:
                    color = RED    # Not clicked yet OR invalid position
                
                # Draw colored outline ON TOP of the video frame for visibility
                frame_circle_radius = max(35, int(rects[i].width / 2.5))  # Slightly smaller radius
                pygame.draw.circle(screen, color, rects[i].center, frame_circle_radius, 4)  # Thinner outline
            
            # Draw pairwise connection lines OVER the video circles while dragging
            if dragging and dragged_frame_index is not None:
                if is_circle_inside_circle(rects[dragged_frame_index], circle_center, circle_radius):
                    # Draw lines from dragged frame to all other frames inside the circle
                    # Line thickness and opacity scale with proximity
                    for i in range(len(frames)):
                        if i != dragged_frame_index and is_circle_inside_circle(rects[i], circle_center, circle_radius):
                            # Calculate distance between dragged frame and this frame
                            dragged_center = rects[dragged_frame_index].center
                            other_center = rects[i].center
                            distance = math.sqrt((dragged_center[0] - other_center[0])**2 + (dragged_center[1] - other_center[1])**2)
                            
                            # Scale thickness and opacity with proximity (closer = thicker/more opaque)
                            max_possible_distance = circle_radius * 2
                            proximity_factor = max(0, 1 - (distance / max_possible_distance))
                            
                            thickness = int(1 + proximity_factor * 7)  # 1 to 8
                            opacity = int(50 + proximity_factor * 205)  # 50 to 255
                            
                            # Create semi-transparent surface for the line
                            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                            # Draw red line with variable opacity
                            pygame.draw.line(s, RED + (opacity,), dragged_center, other_center, thickness)          
                            screen.blit(s, (0, 0))
            
            # Draw button
            button_color = GREEN if (all_inside and all_clicked) else RED
            pygame.draw.rect(screen, button_color, button_rect)
            button_text = button_font.render('Done', True, BLACK)
            screen.blit(button_text, button_text.get_rect(center=button_rect.center))
            
            pygame.display.flip()
    
    # Compute fused D_hat using requested weight mode
    if setcover_weight_mode == 'max':
        with np.errstate(divide='ignore', invalid='ignore'):
            D_hat = np.divide(Num, W, out=np.zeros_like(Num), where=W > 0)
        np.fill_diagonal(D_hat, 0.0)
    elif setcover_weight_mode in ('rms', 'k2012'):
        try:
            from .adaptive.lift_weakest import estimate_rdm_weighted_average, TrialArrangement
            trials = []
            for t in trial_logs:
                subset = list(map(int, t["subset"]))
                positions = {int(k): (float(v[0]), float(v[1])) for k, v in t["positions"].items()}
                trials.append(TrialArrangement(subset=subset, positions=positions))
            D_hat, W_est = estimate_rdm_weighted_average(
                n_media,
                trials,
                alpha=float(setcover_weight_alpha),
                robust_method=robust_method,
                robust_winsor_high=float(robust_winsor_high),
                robust_huber_c=float(robust_huber_c),
                weight_mode=('k2012' if setcover_weight_mode == 'k2012' else 'rms'),
            )
            np.fill_diagonal(D_hat, 0.0)
            W = W_est
        except Exception as e:
            print(f"Warning: RMS-weighted fusion failed, falling back to max-normalized: {e}")
            with np.errstate(divide='ignore', invalid='ignore'):
                D_hat = np.divide(Num, W, out=np.zeros_like(Num), where=W > 0)
            np.fill_diagonal(D_hat, 0.0)
    else:
        print(f"Warning: Unknown setcover_weight_mode='{setcover_weight_mode}', using 'max'.")
        with np.errstate(divide='ignore', invalid='ignore'):
            D_hat = np.divide(Num, W, out=np.zeros_like(Num), where=W > 0)
        np.fill_diagonal(D_hat, 0.0)

    # Final RMS renormalization for 'max' mode (single end-of-run rescale)
    try:
        if setcover_weight_mode == 'max':
            iu = np.triu_indices_from(D_hat, k=1)
            rms = float(np.sqrt(np.mean(D_hat[iu] * D_hat[iu]))) if iu[0].size else 0.0
            if rms > 1e-12:
                D_hat *= (1.0 / rms)
                np.fill_diagonal(D_hat, 0.0)
    except Exception:
        pass

    # Optional inverse-MDS refinement over collected trials
    if use_inverse_mds and trial_arrangements:
        try:
            # Reuse adaptive utilities
            from .adaptive.lift_weakest import refine_rdm_inverse_mds, TrialArrangement
            trials = [TrialArrangement(subset=sub, positions=pos) for (sub, pos) in trial_arrangements]
            D_hat = refine_rdm_inverse_mds(
                D_hat,
                trials,
                max_iter=int(inverse_mds_max_iter),
                tol=float(inverse_mds_tol),
                step_c=float(inverse_mds_step_c),
            )
            np.fill_diagonal(D_hat, 0.0)
        except Exception as e:
            print(f"Warning: inverse-MDS refinement failed: {e}")

    # Create DataFrame for saving/compatibility
    df = pd.DataFrame(D_hat, index=media_names, columns=media_names)

    # Save results and reproducibility metadata, then cleanup
    try:
        # Share a single timestamp across artifacts
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        participant_id = "participant"
        result_file = save_results(df, output_dir, participant_id=participant_id, timestamp=timestamp)

        # Compute schedule coverage diagnostics
        # Degrees per item
        deg = [0] * n_media
        for b in batch_list:
            for idx in b:
                if 0 <= idx < n_media:
                    deg[idx] += 1
        # Pair coverage
        pair_counts = {}
        for b in batch_list:
            bb = list(sorted(set(int(x) for x in b if 0 <= x < n_media)))
            for a in range(len(bb)):
                for c in range(a+1, len(bb)):
                    i, j = bb[a], bb[c]
                    key = (i, j) if i < j else (j, i)
                    pair_counts[key] = pair_counts.get(key, 0) + 1
        total_pairs = n_media * (n_media - 1) // 2
        pairs_covered = len(pair_counts)
        coverage_complete = (pairs_covered == total_pairs)
        lambda_max = max(pair_counts.values()) if pair_counts else 0
        # Histograms
        from collections import Counter
        deg_hist = dict(sorted(Counter(deg).items()))
        cov_hist = dict(sorted(Counter(pair_counts.values()).items()))

        meta = {
            "mode": "set-cover",
            "timestamp": timestamp,
            "input_dir": str(input_dir),
            "n_items": int(n_media),
            "labels": list(media_names),
            "batches": [[int(x) for x in batch] for batch in batch_list],
            "n_batches": int(len(batch_list)),
            "batch_sizes": [int(len(b)) for b in batch_list],
            "interleaving_max_adjacent_overlap": max_adjacent_overlap,
            "fusion": {
                "alpha": float(setcover_weight_alpha),
                "weight_mode": str(setcover_weight_mode),
                "robust_method": robust_method,
                "robust_winsor_high": float(robust_winsor_high),
                "robust_huber_c": float(robust_huber_c),
                "inverse_mds": bool(use_inverse_mds),
                "inverse_mds_max_iter": int(inverse_mds_max_iter),
                "inverse_mds_step_c": float(inverse_mds_step_c),
                "inverse_mds_tol": float(inverse_mds_tol),
            },
            "trials": trial_logs,
            "coverage": {
                "total_pairs": int(total_pairs),
                "pairs_covered": int(pairs_covered),
                "coverage_complete": bool(coverage_complete),
                "lambda_max": int(lambda_max),
                "deg_hist": deg_hist,
                "pair_coverage_hist": cov_hist,
            },
            "artifacts": {
                "csv": result_file,
                # Excel path mirrors CSV name
                "excel": str(Path(result_file).with_suffix('.xlsx')),
            },
            "notes": [
                "UI used randomized seating jitter; distances depend on participant actions.",
            ],
            "rng_seed": int(rng_seed) if rng_seed is not None else None,
        }
        try:
            meta_path = Path(output_dir) / f"{participant_id}_meta_{timestamp}.json"
            import json
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)
            print(f"Metadata saved to: {meta_path}")
        except Exception as e:
            print(f"Warning: failed to write metadata JSON: {e}")

        safe_pygame_quit()
        return result_file
    except Exception as e:
        print(f"Error saving results: {e}")
        safe_pygame_quit()
        return None
