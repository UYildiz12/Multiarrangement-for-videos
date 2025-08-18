"""
Base interface class for multiarrangement experiments.
"""

import pygame
import sys
import math
import threading
import textwrap
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
from abc import ABC, abstractmethod

from ..core.experiment import MultiarrangementExperiment
from ..utils.video_processing import VideoProcessor


class BaseInterface(ABC):
    """Base class for multiarrangement experiment interfaces."""
    
    def __init__(self, experiment: MultiarrangementExperiment):
        """
        Initialize the interface.
        
        Args:
            experiment: MultiarrangementExperiment instance
        """
        self.experiment = experiment
        self.video_processor = VideoProcessor()
        
        # Initialize pygame
        pygame.init()
        
        # Interface state
        self.running = True
        self.current_batch_videos = []
        self.video_positions = {}
        self.video_clicked = {}
        self.video_thumbnails = {}
        self.dragging = False
        self.dragged_video = None
        self.drag_offset = (0, 0)
        
        # UI components
        self.screen = None
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.large_font = pygame.font.Font(None, 48)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 255, 0)
        self.BLUE = (0, 0, 255)
        self.GRAY = (128, 128, 128)
        
        # Double-click detection
        self.last_click_time = 0
        self.double_click_threshold = 350  # milliseconds
        # Optional custom instructions (list of strings); None -> show defaults
        self.custom_instructions = None
        
    @abstractmethod
    def setup_display(self) -> None:
        """Setup the display configuration."""
        pass
        
    @abstractmethod
    def draw_interface(self) -> None:
        """Draw the main interface."""
        pass
        
    @abstractmethod
    def handle_events(self) -> None:
        """Handle pygame events."""
        pass
        
    def show_instructions(self, mode: str = "video", language: str = "en") -> None:
        """
        Show experiment instructions for video or audio mode, in English or Turkish.
        Args:
            mode: "video" or "audio"
            language: "en" (English) or "tr" (Turkish)
        """
        # Prefer experiment-provided mode/language when available
        try:
            mode = getattr(self.experiment, "mode", mode)
        except Exception:
            pass
        try:
            language = getattr(self.experiment, "language", language)
        except Exception:
            pass
        # If custom instructions supplied, show them and return
        if isinstance(self.custom_instructions, list):
            for instruction in self.custom_instructions:
                self.show_instruction_screen(instruction)
            return
        if language == "tr":
            if mode == "video":
                instructions = [
                    "Video benzerliği düzenleme deneyine hoş geldiniz.",
                    "Gruplar halinde videolar göreceksiniz ve bunları benzerliğe göre düzenlemeniz gerekecek.",
                    "Önce gruptaki tüm videoları izleyeceksiniz.",
                    "Daha sonra video dairelerini sürükleyerek düzenleyin.",
                    "Benzer videoları birbirine yakın, farklı olanları uzak yerleştirin.",
                    "Herhangi bir daireye çift tıklayarak videoyu tekrar oynatabilirsiniz.",
                    "Düzenlemeden memnun kaldığınızda 'Bitti'ye tıklayın.",
                    "Bu talimatları geçmek için BOŞLUK tuşuna basın."
                ]
            else:  # audio
                instructions = [
                    "Ses benzerliği düzenleme deneyine hoş geldiniz.",
                    "Gruplar halinde sesler göreceksiniz ve bunları benzerliğe göre düzenlemeniz gerekecek.",
                    "Önce gruptaki tüm sesleri dinleyeceksiniz.",
                    "Daha sonra ses dairelerini sürükleyerek düzenleyin.",
                    "Benzer sesleri birbirine yakın, farklı olanları uzak yerleştirin.",
                    "Herhangi bir daireye çift tıklayarak sesi tekrar dinleyebilirsiniz.",
                    "Düzenlemeden memnun kaldığınızda 'Bitti'ye tıklayın.",
                    "Bu talimatları geçmek için BOŞLUK tuşuna basın."
                ]
        else:
            if mode == "video":
                instructions = [
                    "Welcome to the video similarity arrangement experiment.",
                    "You will see groups of videos that you need to arrange by similarity.",
                    "First, you will watch all videos in the group.",
                    "Then, arrange the video circles by dragging them.",
                    "Place similar videos close together, dissimilar videos far apart.",
                    "Double-click any circle to replay its video.",
                    "Click 'Done' when you're satisfied with the arrangement.",
                    "Press SPACE to continue through these instructions."
                ]
            else:  # audio
                instructions = [
                    "Welcome to the audio similarity arrangement experiment.",
                    "You will see groups of sounds that you need to arrange by similarity.",
                    "First, you will listen to all sounds in the group.",
                    "Then, arrange the sound circles by dragging them.",
                    "Place similar sounds close together, dissimilar sounds far apart.",
                    "Double-click any circle to replay its sound.",
                    "Click 'Done' when you're satisfied with the arrangement.",
                    "Press SPACE to continue through these instructions."
                ]
        for instruction in instructions:
            self.show_instruction_screen(instruction)
            
    def show_instruction_screen(self, message: str) -> None:
        """Show a single instruction screen."""
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
                        
            self.screen.fill(self.BLACK)
            
            # Wrap text and display
            lines = textwrap.wrap(message, width=50)
            total_height = len(lines) * self.font.get_height()
            start_y = (self.screen.get_height() - total_height) // 2
            
            for i, line in enumerate(lines):
                text_surface = self.font.render(line, True, self.WHITE)
                x = (self.screen.get_width() - text_surface.get_width()) // 2
                y = start_y + i * self.font.get_height()
                self.screen.blit(text_surface, (x, y))
                
            pygame.display.flip()
            self.clock.tick(60)
            
    def show_videos_preview(self) -> None:
        """Show all videos in the current batch."""
        for video_filename in self.current_batch_videos:
            video_path = self.experiment.get_video_path(video_filename)
            self.video_processor.display_video_in_pygame(
                video_path, 
                self.screen,
                (0, 0),
                self.screen.get_size()
            )
            
    def load_current_batch(self) -> None:
        """Load the current batch of videos."""
        self.current_batch_videos = self.experiment.get_current_batch_videos()
        
        if not self.current_batch_videos:
            self.running = False
            return
            
        # Reset state for new batch
        self.video_positions = {}
        self.video_clicked = {}
        
        # Initialize clicked state
        for video in self.current_batch_videos:
            video_name = Path(video).stem
            self.video_clicked[video_name] = False
        
        # Precompute and cache circular thumbnail surfaces once per batch to avoid per-frame decoding
        self.video_thumbnails = {}
        for video in self.current_batch_videos:
            video_name = Path(video).stem
            try:
                video_path = self.experiment.get_video_path(video)
                suffix = Path(video_path).suffix.lower()
                if suffix in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                    # Use a robust search for the packaged audio icon. Prefer icons bundled
                    # inside the installed package; fallback to repo root during dev.
                    diameter = 70
                    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
                    root = Path(__file__).parent.parent
                    # Candidate locations (installed package and dev repo)
                    candidates = [
                        root / "Audio.png",
                        root / "test_audio_icon_new.png",
                        root / "data" / "Audio.png",
                        root / "data" / "test_audio_icon_new.png",
                        root.parent / "Audio.png",  # repo root (dev)
                        root.parent / "test_audio_icon_new.png",  # repo root (dev)
                    ]
                    icon_path = next((p for p in candidates if p.exists()), None)
                    try:
                        if icon_path is None:
                            raise FileNotFoundError("Audio icon not found in package")
                        icon = pygame.image.load(str(icon_path))
                        icon = pygame.transform.smoothscale(icon, (diameter, diameter))
                        surface.blit(icon, (0, 0))
                    except Exception:
                        # Draw simple placeholder if icon missing
                        pygame.draw.circle(surface, self.GRAY, (diameter//2, diameter//2), diameter//2)
                    try:
                        surface = surface.convert_alpha()
                    except Exception:
                        pass
                    self.video_thumbnails[video_name] = surface
                else:
                    # Video thumbnail from first frame
                    first_frame = self.video_processor.get_first_frame(video_path)
                    surface = self.video_processor.create_circular_frame_surface(first_frame, 35)
                    try:
                        surface = surface.convert_alpha()
                    except Exception:
                        pass
                    self.video_thumbnails[video_name] = surface
            except Exception:
                # Cache None to indicate fallback drawing
                self.video_thumbnails[video_name] = None
            
    def arrange_videos_in_circle(self, center: Tuple[int, int], radius: int) -> None:
        """Arrange video thumbnails in a circle around the center."""
        num_videos = len(self.current_batch_videos)
        angle_step = 2 * math.pi / num_videos
        
        for i, video_filename in enumerate(self.current_batch_videos):
            video_name = Path(video_filename).stem
            angle = i * angle_step
            
            x = center[0] + (radius + 100) * math.cos(angle)
            y = center[1] - (radius + 100) * math.sin(angle)
            
            self.video_positions[video_name] = (x, y)
            
    def handle_double_click(self, pos: Tuple[int, int]) -> bool:
        """Handle double-click events to play videos.

        Returns True if a double-click was detected and handled.
        """
        current_time = pygame.time.get_ticks()
        handled = False
        if current_time - self.last_click_time <= self.double_click_threshold:
            # Find which video was clicked
            for i, video_filename in enumerate(self.current_batch_videos):
                video_name = Path(video_filename).stem
                if video_name in self.video_positions:
                    video_pos = self.video_positions[video_name]
                    distance = math.sqrt((pos[0] - video_pos[0])**2 + (pos[1] - video_pos[1])**2)
                    if distance <= 40:  # Within circle radius
                        # Mark as clicked and play video
                        self.video_clicked[video_name] = True
                        video_path = self.experiment.get_video_path(video_filename)
                        # Detect audio vs video by extension
                        suffix = Path(video_path).suffix.lower()
                        if suffix in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                            # Play audio without blocking the UI
                            self.video_processor.play_audio_nonblocking(video_path)
                        else:
                            # Play video within current Pygame screen (no minimize)
                            self.video_processor.display_video_in_pygame(
                                video_path,
                                self.screen,
                                (0, 0),
                                self.screen.get_size()
                            )
                        handled = True
                        break
        # Update last click timestamp after processing
        self.last_click_time = current_time
        return handled
        
    def handle_drag_start(self, pos: Tuple[int, int]) -> None:
        """Handle start of dragging operation."""
        for video_filename in self.current_batch_videos:
            video_name = Path(video_filename).stem
            
            if video_name in self.video_positions:
                video_pos = self.video_positions[video_name]
                distance = math.sqrt((pos[0] - video_pos[0])**2 + (pos[1] - video_pos[1])**2)
                
                if distance <= 40:  # Within circle radius
                    self.dragging = True
                    self.dragged_video = video_name
                    self.drag_offset = (pos[0] - video_pos[0], pos[1] - video_pos[1])
                    break
                    
    def handle_drag_motion(self, pos: Tuple[int, int]) -> None:
        """Handle dragging motion."""
        if self.dragging and self.dragged_video:
            new_x = pos[0] - self.drag_offset[0]
            new_y = pos[1] - self.drag_offset[1]
            self.video_positions[self.dragged_video] = (new_x, new_y)
            
    def handle_drag_end(self) -> None:
        """Handle end of dragging operation."""
        self.dragging = False
        self.dragged_video = None
        self.drag_offset = (0, 0)
        
    def check_completion_criteria(self, arena_center: Tuple[int, int], arena_radius: int) -> bool:
        """Check if the completion criteria are met."""
        # All videos must be clicked (watched)
        all_clicked = all(self.video_clicked.values())
        
        # All videos must be within the arena with proper clearance
        all_in_arena = True
        tolerance = 8  # Require 8 pixels of clearance from white circle boundary (more punishing)
        circle_radius = 35  # Radius of the video circles
        
        for video_name, pos in self.video_positions.items():
            distance = math.sqrt((pos[0] - arena_center[0])**2 + (pos[1] - arena_center[1])**2)
            if distance + circle_radius >= arena_radius - tolerance:  # Touching or overlapping boundary
                all_in_arena = False
                break
                
        return all_clicked and all_in_arena
        
    def draw_video_circles(self) -> None:
        """Draw video thumbnail circles."""
        for video_filename in self.current_batch_videos:
            video_name = Path(video_filename).stem
            
            if video_name in self.video_positions:
                pos = self.video_positions[video_name]
                
                # Choose color based on whether video was clicked AND in valid position
                tolerance = 8  # Require 8 pixels of clearance from white circle boundary (more punishing)
                circle_radius = 35  # Radius of the video circles
                
                # Check if position is valid (inside arena with clearance)
                distance = math.sqrt((pos[0] - self.arena_center[0])**2 + (pos[1] - self.arena_center[1])**2)
                in_valid_position = distance + circle_radius < self.arena_radius - tolerance
                
                # Green if clicked AND in valid position, red otherwise
                color = self.GREEN if (self.video_clicked[video_name] and in_valid_position) else self.RED
                
                # Draw cached video thumbnail if available; else fallback
                frame_surface = self.video_thumbnails.get(video_name)
                if frame_surface is not None:
                    frame_rect = frame_surface.get_rect()
                    frame_rect.center = (int(pos[0]), int(pos[1]))
                    self.screen.blit(frame_surface, frame_rect)
                else:
                    # Fallback: draw a simple circle with text
                    pygame.draw.circle(self.screen, self.GRAY, (int(pos[0]), int(pos[1])), 35)
                    
                    # Draw video number
                    text = self.font.render(str(self.current_batch_videos.index(video_filename) + 1), 
                                          True, self.WHITE)
                    text_rect = text.get_rect()
                    text_rect.center = (int(pos[0]), int(pos[1]))
                    self.screen.blit(text, text_rect)
                
                # Draw colored outline ON TOP of video content (more visible)
                pygame.draw.circle(self.screen, color, (int(pos[0]), int(pos[1])), 35, 4)
                    
    def draw_connections_while_dragging(self, arena_center: Tuple[int, int], arena_radius: int) -> None:
        """Draw connection lines while dragging within arena."""
        if not self.dragging or not self.dragged_video:
            return
            
        dragged_pos = self.video_positions[self.dragged_video]
        
        # Check if dragged video is in arena
        distance_to_center = math.sqrt(
            (dragged_pos[0] - arena_center[0])**2 + 
            (dragged_pos[1] - arena_center[1])**2
        )
        
        if distance_to_center <= arena_radius - 40:
            # Draw lines to other videos in arena
            for video_name, pos in self.video_positions.items():
                if video_name != self.dragged_video:
                    other_distance = math.sqrt(
                        (pos[0] - arena_center[0])**2 + 
                        (pos[1] - arena_center[1])**2
                    )
                    
                    if other_distance <= arena_radius - 40:
                        pygame.draw.line(self.screen, (255, 0, 0, 128), 
                                       (int(dragged_pos[0]), int(dragged_pos[1])),
                                       (int(pos[0]), int(pos[1])), 3)
                                       
    def finish_batch(self) -> None:
        """Finish the current batch and record results."""
        # Record the arrangement
        positions_for_recording = {}
        for video_filename in self.current_batch_videos:
            video_name = Path(video_filename).stem
            if video_name in self.video_positions:
                positions_for_recording[video_name] = self.video_positions[video_name]
                
        self.experiment.record_arrangement(positions_for_recording)
        
        # Advance to next batch
        has_next = self.experiment.advance_to_next_batch()
        
        if not has_next:
            # Experiment complete
            self.experiment.save_results()
            self.show_completion_message()
            self.running = False
        else:
            # Load next batch
            self.load_current_batch()
            
    def show_completion_message(self) -> None:
        """Show experiment completion message."""
        message = "Experiment completed! Thank you for participating."
        
        waiting = True
        start_time = pygame.time.get_ticks()
        
        while waiting and pygame.time.get_ticks() - start_time < 3000:  # Show for 3 seconds
            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
                    waiting = False
                    
            self.screen.fill(self.BLACK)
            
            text_surface = self.large_font.render(message, True, self.GREEN)
            text_rect = text_surface.get_rect()
            text_rect.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
            self.screen.blit(text_surface, text_rect)
            
            pygame.display.flip()
            self.clock.tick(60)
            
    def run(self) -> None:
        """Main interface loop."""
        self.setup_display()
        # Show default or custom instructions
        self.show_instructions()
        self.load_current_batch()
        
        while self.running:
            self.handle_events()
            self.draw_interface()
            pygame.display.flip()
            self.clock.tick(60)
            
        pygame.quit()


class MultiarrangementInterface(BaseInterface):
    """Windowed interface for multiarrangement experiments."""
    
    def __init__(self, experiment: MultiarrangementExperiment):
        super().__init__(experiment)
        self.screen_width = 1400
        self.screen_height = 1000
        self.arena_center = (700, 500)
        self.arena_radius = 355
        
    def setup_display(self) -> None:
        """Setup windowed display."""
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Multiarrangement Video Similarity Experiment")
        
    def draw_interface(self) -> None:
        """Draw the windowed interface."""
        self.screen.fill(self.BLACK)
        
        # Draw arena circle
        pygame.draw.circle(self.screen, self.WHITE, self.arena_center, self.arena_radius, 4)
        
        # Draw progress indicator
        current, total = self.experiment.get_progress()
        progress_text = f"Batch {current} of {total}"
        text_surface = self.font.render(progress_text, True, self.WHITE)
        self.screen.blit(text_surface, (20, 20))
        
        # Draw video circles
        self.draw_video_circles()
        
        # Draw connections while dragging
        self.draw_connections_while_dragging(self.arena_center, self.arena_radius)
        
        # Draw done button
        self.draw_done_button()
        
    def draw_done_button(self) -> None:
        """Draw the done button."""
        button_rect = pygame.Rect(50, self.screen_height - 100, 100, 50)
        
        # Check if completion criteria are met
        can_complete = self.check_completion_criteria(self.arena_center, self.arena_radius)
        button_color = self.GREEN if can_complete else self.RED
        
        pygame.draw.rect(self.screen, button_color, button_rect)
        pygame.draw.rect(self.screen, self.WHITE, button_rect, 2)
        
        text_surface = self.font.render("Done", True, self.WHITE)
        text_rect = text_surface.get_rect()
        text_rect.center = button_rect.center
        self.screen.blit(text_surface, text_rect)
        
        # Store button rect for click detection
        self.done_button_rect = button_rect
        
    def handle_events(self) -> None:
        """Handle pygame events for windowed interface."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    pos = event.pos if hasattr(event, 'pos') else pygame.mouse.get_pos()
                    
                    # Check done button
                    if hasattr(self, 'done_button_rect') and self.done_button_rect.collidepoint(pos):
                        if self.check_completion_criteria(self.arena_center, self.arena_radius):
                            self.finish_batch()
                        continue
                    
                    # Handle double-click for video playback
                    handled = self.handle_double_click(pos)
                    
                    # Start dragging if not double-click
                    if not handled:
                        self.handle_drag_start(pos)
                        
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    self.handle_drag_end()
                    
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    pos = event.pos if hasattr(event, 'pos') else pygame.mouse.get_pos()
                    self.handle_drag_motion(pos)
                    
        # Arrange videos initially if not positioned
        if not self.video_positions and self.current_batch_videos:
            self.arrange_videos_in_circle(self.arena_center, self.arena_radius)
