"""
Fullscreen interface for multiarrangement experiments.
"""

import pygame
import sys
from .interface import BaseInterface
from ..core.experiment import MultiarrangementExperiment


class FullscreenInterface(BaseInterface):
    """Fullscreen interface for multiarrangement experiments."""
    
    def __init__(self, experiment: MultiarrangementExperiment):
        super().__init__(experiment)
        
        # Get screen dimensions
        info_object = pygame.display.Info()
        self.screen_width = info_object.current_w
        self.screen_height = info_object.current_h
        
        # Calculate arena parameters based on screen size
        self.arena_center = (self.screen_width // 2, self.screen_height // 2)
        self.arena_radius = min(self.screen_width, self.screen_height) // 2 - 100
        
    def setup_display(self) -> None:
        """Setup fullscreen display."""
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height), 
            pygame.FULLSCREEN
        )
        pygame.display.set_caption("Multiarrangement Video Similarity Experiment - Fullscreen")
        
    def draw_interface(self) -> None:
        """Draw the fullscreen interface."""
        self.screen.fill(self.BLACK)
        
        # Draw arena circle
        pygame.draw.circle(self.screen, self.WHITE, self.arena_center, self.arena_radius, 4)
        
        # Draw progress indicator (top-left)
        current, total = self.experiment.get_progress()
        progress_text = f"Batch {current} of {total}"
        text_surface = self.font.render(progress_text, True, self.WHITE)
        self.screen.blit(text_surface, (30, 30))
        
        # Draw instruction text (top-center)
        instruction = "Drag videos to arrange by similarity. Double-click to replay. Press ESC to exit."
        instruction_surface = self.font.render(instruction, True, self.WHITE)
        instruction_rect = instruction_surface.get_rect()
        instruction_rect.centerx = self.screen_width // 2
        instruction_rect.y = 30
        self.screen.blit(instruction_surface, instruction_rect)
        
        # Draw video circles
        self.draw_video_circles()
        
        # Draw connections while dragging
        self.draw_connections_while_dragging(self.arena_center, self.arena_radius)
        
        # Draw done button (bottom-left)
        self.draw_done_button()
        
    def draw_done_button(self) -> None:
        """Draw the done button for fullscreen interface."""
        button_width = 120
        button_height = 60
        button_x = 50
        button_y = self.screen_height - button_height - 50
        
        button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
        
        # Check if completion criteria are met
        can_complete = self.check_completion_criteria(self.arena_center, self.arena_radius)
        
        # Create semi-transparent button
        button_surface = pygame.Surface((button_width, button_height), pygame.SRCALPHA)
        
        if can_complete:
            button_color = (*self.GREEN, 180)
            border_color = self.GREEN
        else:
            button_color = (*self.RED, 180)
            border_color = self.RED
            
        button_surface.fill(button_color)
        pygame.draw.rect(button_surface, border_color, button_surface.get_rect(), 3)
        
        # Add button text
        text_surface = self.large_font.render("Done", True, self.WHITE)
        text_rect = text_surface.get_rect()
        text_rect.center = (button_width // 2, button_height // 2)
        button_surface.blit(text_surface, text_rect)
        
        # Blit button to screen
        self.screen.blit(button_surface, button_rect)
        
        # Store button rect for click detection
        self.done_button_rect = button_rect
        
    def handle_events(self) -> None:
        """Handle pygame events for fullscreen interface."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_F11:
                    # Toggle fullscreen (though we start in fullscreen)
                    pass
                    
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    pos = pygame.mouse.get_pos()
                    
                    # Check done button
                    if hasattr(self, 'done_button_rect') and self.done_button_rect.collidepoint(pos):
                        if self.check_completion_criteria(self.arena_center, self.arena_radius):
                            self.finish_batch()
                        continue
                    
                    # Handle double-click for video playback
                    self.handle_double_click(pos)
                    
                    # Start dragging if not double-click
                    if pygame.time.get_ticks() - self.last_click_time > self.double_click_threshold:
                        self.handle_drag_start(pos)
                        
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    self.handle_drag_end()
                    
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    pos = pygame.mouse.get_pos()
                    self.handle_drag_motion(pos)
                    
        # Arrange videos initially if not positioned
        if not self.video_positions and self.current_batch_videos:
            self.arrange_videos_in_circle(self.arena_center, self.arena_radius)
            
    def show_instructions(self) -> None:
        """Show fullscreen-optimized instructions."""
        instructions = [
            "Welcome to the video similarity arrangement experiment.",
            "You will arrange videos based on their similarity in a circular arena.",
            "First, you'll watch each video in the group.",
            "Then, drag the video circles to arrange them by similarity.",
            "Similar videos should be placed close together.",
            "Dissimilar videos should be placed far apart.",
            "Double-click any circle to replay its video.",
            "All videos must be watched and placed within the white circle.",
            "Click the 'Done' button when satisfied with your arrangement.",
            "Press SPACE to continue, ESC to exit."
        ]
        
        for instruction in instructions:
            self.show_instruction_screen(instruction)
            
    def show_instruction_screen(self, message: str) -> None:
        """Show instruction screen optimized for fullscreen."""
        import textwrap
        
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
            
            # Wrap text for fullscreen display
            max_width = self.screen_width // 20  # Adjust for screen width
            lines = textwrap.wrap(message, width=max_width)
            
            # Calculate text positioning
            line_height = self.large_font.get_height()
            total_height = len(lines) * line_height
            start_y = (self.screen_height - total_height) // 2
            
            for i, line in enumerate(lines):
                text_surface = self.large_font.render(line, True, self.WHITE)
                text_rect = text_surface.get_rect()
                text_rect.centerx = self.screen_width // 2
                text_rect.y = start_y + i * line_height
                self.screen.blit(text_surface, text_rect)
                
            # Show continue instruction
            continue_text = "Press SPACE to continue, ESC to exit"
            continue_surface = self.font.render(continue_text, True, self.GRAY)
            continue_rect = continue_surface.get_rect()
            continue_rect.centerx = self.screen_width // 2
            continue_rect.y = self.screen_height - 100
            self.screen.blit(continue_surface, continue_rect)
                
            pygame.display.flip()
            self.clock.tick(60)
            
    def show_completion_message(self) -> None:
        """Show completion message optimized for fullscreen."""
        message = "Experiment completed!"
        subtitle = "Thank you for your participation."
        
        waiting = True
        start_time = pygame.time.get_ticks()
        
        while waiting and pygame.time.get_ticks() - start_time < 5000:  # Show for 5 seconds
            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
                    waiting = False
                    
            self.screen.fill(self.BLACK)
            
            # Main message
            text_surface = pygame.font.Font(None, 72).render(message, True, self.GREEN)
            text_rect = text_surface.get_rect()
            text_rect.centerx = self.screen_width // 2
            text_rect.centery = self.screen_height // 2 - 50
            self.screen.blit(text_surface, text_rect)
            
            # Subtitle
            subtitle_surface = self.large_font.render(subtitle, True, self.WHITE)
            subtitle_rect = subtitle_surface.get_rect()
            subtitle_rect.centerx = self.screen_width // 2
            subtitle_rect.centery = self.screen_height // 2 + 50
            self.screen.blit(subtitle_surface, subtitle_rect)
            
            pygame.display.flip()
            self.clock.tick(60)
