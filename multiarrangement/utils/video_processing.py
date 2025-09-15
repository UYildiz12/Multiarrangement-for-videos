"""
Video processing utilities for multiarrangement experiments.
"""

import cv2
import numpy as np
import pygame
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Union


class VideoProcessor:
    """Handles video processing operations for multiarrangement experiments."""
    
    def __init__(self):
        """Initialize the video processor."""
        self.scale_factor = 2.5
        
    def get_first_frame(self, video_path: Union[str, Path]) -> np.ndarray:
        """
        Extract the first frame from a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            First frame as numpy array
            
        Raises:
            ValueError: If video cannot be opened or has no frames
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Support images as single-frame videos
        image_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        if video_path.suffix.lower() in image_exts:
            frame = cv2.imread(str(video_path), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError(f"Cannot read image file: {video_path}")
            return frame

        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise ValueError(f"Cannot read first frame from: {video_path}")

        return frame

    def load_image(self, image_path: Union[str, Path]) -> np.ndarray:
        """Load an image file into an array (BGR)."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        return img
        
    def get_first_frames_batch(self, video_paths: List[Union[str, Path]]) -> List[np.ndarray]:
        """
        Extract first frames from multiple video files.
        
        Args:
            video_paths: List of paths to video files
            
        Returns:
            List of first frames as numpy arrays
        """
        frames = []
        
        for video_path in video_paths:
            try:
                frame = self.get_first_frame(video_path)
                frames.append(frame)
            except (FileNotFoundError, ValueError) as e:
                print(f"Warning: Could not process {video_path}: {e}")
                # Create a placeholder black frame
                frames.append(np.zeros((480, 640, 3), dtype=np.uint8))
                
        return frames
        
    def frame_to_pygame_surface(self, frame: np.ndarray, size: Optional[Tuple[int, int]] = None) -> pygame.Surface:
        """
        Convert OpenCV frame to pygame surface.
        
        Args:
            frame: OpenCV frame (BGR format)
            size: Optional target size (width, height)
            
        Returns:
            Pygame surface
        """
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create pygame surface
        surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        
        # Resize if requested
        if size:
            surface = pygame.transform.scale(surface, size)
            
        return surface
        
    def create_circular_frame_surface(self, frame: np.ndarray, radius: int) -> pygame.Surface:
        """
        Create a circular pygame surface from a video frame.
        
        Args:
            frame: OpenCV frame
            radius: Radius of the circular frame
            
        Returns:
            Circular pygame surface with transparency
        """
        # Scale frame
        scaled_size = (
            int(frame.shape[1] // self.scale_factor),
            int(frame.shape[0] // self.scale_factor)
        )
        
        # Convert to pygame surface
        frame_surface = self.frame_to_pygame_surface(frame, scaled_size)
        
        # Keep original orientation (avoid 90-degree rotation)
        
        # Create circular mask
        diameter = radius * 2
        mask_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(mask_surface, (255, 255, 255, 128), (radius, radius), radius)
        
        # Apply mask to frame
        final_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        
        # Scale frame to fit circle
        frame_scaled = pygame.transform.scale(frame_surface, (diameter, diameter))
        
        # Blit frame and apply circular mask
        final_surface.blit(frame_scaled, (0, 0))
        final_surface.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        return final_surface

    def display_image_in_pygame(self, image_path: Union[str, Path], screen: pygame.Surface,
                                 position: Tuple[int, int], size: Tuple[int, int]) -> None:
        """Display an image in the given pygame surface until SPACE/ESC."""
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"Image file not found: {image_path}")
            return
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"Cannot open image: {image_path}")
            return
        try:
            img = cv2.resize(img, size)
            surf = self.frame_to_pygame_surface(img)
            waiting = True
            while waiting:
                # Clear to black and blit
                screen.fill((0, 0, 0))
                screen.blit(surf, position)
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                        waiting = False
        finally:
            pass
        
    def play_video_popup(self, video_path: Union[str, Path]) -> None:
        """
        Play a video in a popup window using OpenCV.
        
        Args:
            video_path: Path to the video file
        """
        video_path = Path(video_path)

        if not video_path.exists():
            print(f"Video file not found: {video_path}")
            return

        # Check if it's an audio file
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}
        if video_path.suffix.lower() in audio_extensions:
            # Handle audio files with improved playback
            self._play_audio_file(video_path)
            return
        # If it's an image, show it in a popup window and wait for key
        image_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        if video_path.suffix.lower() in image_exts:
            img = cv2.imread(str(video_path), cv2.IMREAD_COLOR)
            if img is None:
                print(f"Cannot open image: {video_path}")
                return
            window_name = f'Image: {video_path.name}'
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            h, w = img.shape[:2]
            cv2.resizeWindow(window_name, max(200, w), max(200, h))
            cv2.imshow(window_name, img)
            cv2.waitKey(0)
            try:
                cv2.destroyWindow(window_name)
            except Exception:
                pass
            return
            
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"Cannot open video: {video_path}")
            return
            
        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        delay = int(1000 / fps) if fps > 0 else 33
        
        # Create window
        window_name = f'Video: {video_path.name}'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, width * 2, height * 2)
        # Match set-cover behavior: keep window on top
        try:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        except Exception:
            pass
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                
                if not ret:
                    break
                    
                cv2.imshow(window_name, frame)
                
                # Exit on 'q', SPACE, or ESC key, or window close
                key = cv2.waitKey(delay) & 0xFF
                if key in (ord('q'), 32, 27):
                    break
                    
                # Check if window was closed
                try:
                    cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                except cv2.error:
                    break
                    
        finally:
            cap.release()
            cv2.destroyWindow(window_name)

    def play_audio_inplace(self, audio_path: Union[str, Path]) -> None:
        """Play audio using pygame.mixer within the same window (no app switch)."""
        import pygame
        import time
        from pathlib import Path
        audio_path = Path(audio_path)
        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}")
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.stop()
            pygame.mixer.music.unload() if hasattr(pygame.mixer.music, 'unload') else None
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            # Blocking loop (kept for compatibility)
            while pygame.mixer.music.get_busy():
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                        pygame.mixer.music.stop()
                        return
                time.sleep(0.01)
        except Exception as e:
            print(f"Audio playback error, falling back: {e}")
            self._play_audio_file(audio_path)
            
    def play_audio_nonblocking(self, audio_path: Union[str, Path]) -> None:
        """Start audio playback without blocking the UI (pygame.mixer)."""
        import pygame
        from pathlib import Path
        audio_path = Path(audio_path)
        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}")
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            # Stop any currently playing audio, then start new one
            try:
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, 'unload'):
                    pygame.mixer.music.unload()
            except Exception:
                pass
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Audio nonblocking playback error, falling back: {e}")
            # Fallback to OS player thread (non-blocking for UI)
            self._play_audio_file(audio_path)

    def _play_audio_file(self, audio_path: Path) -> None:
        """Play audio file until it finishes naturally."""
        import subprocess
        import platform
        import threading
        import time
        import wave
        import contextlib
        import os
        
        def get_audio_duration(audio_path):
            """Get audio duration in seconds."""
            try:
                if str(audio_path).lower().endswith('.wav'):
                    with contextlib.closing(wave.open(str(audio_path), 'r')) as f:
                        frames = f.getnframes()
                        rate = f.getframerate()
                        duration = frames / float(rate)
                        return duration
                else:
                    # For other formats, estimate based on file size
                    file_size = os.path.getsize(audio_path)
                    # Rough estimate: 1MB ≈ 1 minute for compressed audio
                    estimated_duration = (file_size / (1024 * 1024)) * 60
                    return max(estimated_duration, 3)  # Minimum 3 seconds
            except:
                return 5  # Default fallback
        
        def play_audio():
            try:
                system = platform.system()
                if system == "Windows":
                    # Use Windows Media Player in background
                    subprocess.run(["start", "/min", "wmplayer", str(audio_path)], shell=True)
                    # Wait for actual audio duration
                    duration = get_audio_duration(audio_path)
                    time.sleep(duration + 1)  # Add 1 second buffer
                    # Close the player
                    subprocess.run(["taskkill", "/f", "/im", "wmplayer.exe"], shell=True, stderr=subprocess.DEVNULL)
                elif system == "Darwin":  # macOS
                    # Use afplay which plays until completion
                    subprocess.run(["afplay", str(audio_path)])
                elif system == "Linux":
                    # Use aplay or paplay which play until completion
                    try:
                        subprocess.run(["paplay", str(audio_path)])
                    except FileNotFoundError:
                        subprocess.run(["aplay", str(audio_path)])
                else:
                    print(f"Cannot play audio on {system}. Please play {audio_path} manually.")
            except Exception as e:
                print(f"Error playing audio {audio_path}: {e}")
                print(f"🔊 Audio file: {audio_path.name}")
        
        # Run audio playback in a separate thread
        audio_thread = threading.Thread(target=play_audio)
        audio_thread.daemon = True
        audio_thread.start()
            
    def play_video_threaded(self, video_path: Union[str, Path]) -> None:
        """
        Play a video in a separate thread to avoid blocking the main interface.
        
        Args:
            video_path: Path to the video file
        """
        thread = threading.Thread(target=self.play_video_popup, args=(video_path,))
        thread.daemon = True
        thread.start()
        
    def display_video_in_pygame(self, video_path: Union[str, Path], screen: pygame.Surface, 
                               position: Tuple[int, int], size: Tuple[int, int]) -> None:
        """
        Display a video frame in a pygame surface.
        
        Args:
            video_path: Path to the video file
            screen: Pygame screen surface
            position: (x, y) position to display the video
            size: (width, height) size of the video display
        """
        video_path = Path(video_path)

        if not video_path.exists():
            print(f"Video file not found: {video_path}")
            return

        image_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        if video_path.suffix.lower() in image_exts:
            # Display a static image until ESC/SPACE/QUIT
            img = cv2.imread(str(video_path), cv2.IMREAD_COLOR)
            if img is None:
                print(f"Cannot open image: {video_path}")
                return
            frame_resized = cv2.resize(img, size)
            frame_surface = self.frame_to_pygame_surface(frame_resized)
            clock = pygame.time.Clock()
            while True:
                screen.blit(frame_surface, position)
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                            return
                clock.tick(30)
            
        # Video playback path
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            print(f"Cannot open video: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        delay = int(1000 / fps) if fps > 0 else 33

        try:
            while cap.isOpened():
                ret, frame = cap.read()

                if not ret:
                    # Loop video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                # Resize and convert frame
                frame_resized = cv2.resize(frame, size)
                frame_surface = self.frame_to_pygame_surface(frame_resized)

                # Display frame
                screen.blit(frame_surface, position)
                pygame.display.flip()

                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE or event.key == pygame.K_SPACE:
                            return

                pygame.time.wait(delay)

        finally:
            cap.release()
            
    def get_video_info(self, video_path: Union[str, Path]) -> dict:
        """
        Get information about a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video information
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
            
        try:
            info = {
                'filename': video_path.name,
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS),
                'codec': int(cap.get(cv2.CAP_PROP_FOURCC))
            }
            
            return info
            
        finally:
            cap.release()
