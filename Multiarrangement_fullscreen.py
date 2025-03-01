import pygame
import sys
import random
import os
import cv2
import numpy as np
import pandas as pd
import math
import time
from tkinter import Tk, simpledialog
import tkinter as tk

# Initialize pygame
pygame.init()

# Get the participant number using tkinter
root = Tk()
root.withdraw()
participant_number = simpledialog.askstring("Input", "Enter participant number:")
root.destroy()

# Set up fullscreen display
infoObject = pygame.display.Info()
screen_width, screen_height = infoObject.current_w, infoObject.current_h
screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
pygame.display.set_caption("Video Arrangement Task - Fullscreen Mode")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)

# Parameters
circle_radius = 40  # Radius of video circles
center_x, center_y = screen_width // 2, screen_height // 2
arena_radius = min(screen_width, screen_height) // 2 - circle_radius - 50  # Arena radius

# Load batch data
batches_file = 'batches_25videos_batchsize8.txt'  # Adjust based on your actual file
batches = []

try:
    with open(batches_file, 'r') as f:
        for line in f:
            batch = [int(x.strip()) for x in line.split(',')]
            batches.append(batch)
    print(f"Loaded {len(batches)} batches from {batches_file}")
except FileNotFoundError:
    print(f"Error: {batches_file} not found. Please generate batches first.")
    pygame.quit()
    sys.exit()

# Function to load videos
def load_video(video_index):
    video_path = f"58videos/{video_index}.mp4"  # Adjust path based on your folder structure
    if not os.path.exists(video_path):
        print(f"Error: Video file {video_path} not found.")
        return None
    return video_path

# Create video circles for the current batch
def create_video_circles(batch):
    circles = []
    angle_increment = 2 * math.pi / len(batch)
    
    for i, video_index in enumerate(batch):
        angle = i * angle_increment
        x = center_x + arena_radius * math.cos(angle)
        y = center_y + arena_radius * math.sin(angle)
        circles.append({
            'index': video_index,
            'x': x,
            'y': y,
            'radius': circle_radius,
            'dragging': False,
            'video_path': load_video(video_index)
        })
    return circles

# Function to play video
def play_video(video_path):
    if video_path is None:
        return
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return
    
    # Get video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Calculate position to center the video
    video_x = center_x - frame_width // 2
    video_y = center_y - frame_height // 2
    
    playing = True
    while playing and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop the video
            continue
        
        # Convert frame to pygame surface
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = np.rot90(frame)
        frame = pygame.surfarray.make_surface(frame)
        
        # Draw the frame
        screen.fill(BLACK)
        screen.blit(frame, (video_x, video_y))
        pygame.display.flip()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                playing = False
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_SPACE:
                    playing = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                playing = False
        
        pygame.time.delay(30)  # ~30 FPS
    
    cap.release()

# Function to calculate distances between circles
def calculate_distances(circles):
    distances = {}
    for i, circle1 in enumerate(circles):
        for j, circle2 in enumerate(circles):
            if i < j:  # Only calculate once per pair
                idx1, idx2 = circle1['index'], circle2['index']
                dist = math.sqrt((circle1['x'] - circle2['x'])**2 + (circle1['y'] - circle2['y'])**2)
                distances[(min(idx1, idx2), max(idx1, idx2))] = dist
    return distances

# Draw circles on screen
def draw_circles(circles, selected=None):
    screen.fill(BLACK)
    
    # Draw arena circle
    pygame.draw.circle(screen, WHITE, (center_x, center_y), arena_radius, 2)
    
    # Draw instruction text
    font = pygame.font.Font(None, 36)
    text = font.render("Arrange videos by similarity - closer = more similar", True, WHITE)
    screen.blit(text, (center_x - text.get_width() // 2, 30))
    
    text2 = font.render("Double-click to play a video, ESC to finish arrangement", True, WHITE)
    screen.blit(text2, (center_x - text2.get_width() // 2, 70))
    
    # Draw video circles
    for circle in circles:
        color = BLUE if circle != selected else RED
        pygame.draw.circle(screen, color, (int(circle['x']), int(circle['y'])), circle['radius'])
        
        # Draw video index
        font = pygame.font.Font(None, 30)
        text = font.render(str(circle['index']), True, WHITE)
        screen.blit(text, (int(circle['x']) - text.get_width() // 2, int(circle['y']) - text.get_height() // 2))
    
    pygame.display.flip()

# Show instructions
def show_instructions():
    screen.fill(BLACK)
    
    font = pygame.font.Font(None, 48)
    title = font.render("Video Arrangement Task", True, WHITE)
    screen.blit(title, (center_x - title.get_width() // 2, 100))
    
    font = pygame.font.Font(None, 36)
    instructions = [
        "You will see video thumbnails arranged in a circle.",
        "Your task is to rearrange them based on similarity:",
        "- Place similar videos close together",
        "- Place different videos far apart",
        "",
        "- Double-click a video to play it",
        "- Drag videos to reposition them",
        "- Press ESC when you're satisfied with the arrangement",
        "",
        "Press any key to start"
    ]
    
    y_pos = 200
    for line in instructions:
        text = font.render(line, True, WHITE)
        screen.blit(text, (center_x - text.get_width() // 2, y_pos))
        y_pos += 40
    
    pygame.display.flip()
    
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                waiting = False

# Main function
def main():
    show_instructions()
    
    # Create directory for participant data
    if not os.path.exists("Participantdata"):
        os.makedirs("Participantdata")
    
    all_distances = {}
    
    # Process each batch
    for batch_num, batch in enumerate(batches):
        # Show batch info
        screen.fill(BLACK)
        font = pygame.font.Font(None, 48)
        text = font.render(f"Batch {batch_num + 1} of {len(batches)}", True, WHITE)
        screen.blit(text, (center_x - text.get_width() // 2, center_y - 50))
        
        font = pygame.font.Font(None, 36)
        text2 = font.render("Press any key to continue", True, WHITE)
        screen.blit(text2, (center_x - text2.get_width() // 2, center_y + 50))
        pygame.display.flip()
        
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    waiting = False
        
        circles = create_video_circles(batch)
        selected_circle = None
        dragging = False
        last_click_time = 0
        double_click_threshold = 300  # ms
        
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        mouse_x, mouse_y = event.pos
                        current_time = pygame.time.get_ticks()
                        
                        for circle in circles:
                            dx = mouse_x - circle['x']
                            dy = mouse_y - circle['y']
                            distance = math.sqrt(dx*dx + dy*dy)
                            
                            if distance <= circle['radius']:
                                if current_time - last_click_time < double_click_threshold:
                                    # Double click - play the video
                                    play_video(circle['video_path'])
                                else:
                                    # Single click - prepare for dragging
                                    selected_circle = circle
                                    dragging = True
                                last_click_time = current_time
                                break
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        dragging = False
                        selected_circle = None
                
                elif event.type == pygame.MOUSEMOTION:
                    if dragging and selected_circle:
                        mouse_x, mouse_y = event.pos
                        
                        # Calculate distance from center
                        dx = mouse_x - center_x
                        dy = mouse_y - center_y
                        dist_from_center = math.sqrt(dx*dx + dy*dy)
                        
                        # Keep inside arena
                        if dist_from_center > arena_radius - circle_radius:
                            # Normalize and scale
                            scale = (arena_radius - circle_radius) / dist_from_center
                            selected_circle['x'] = center_x + dx * scale
                            selected_circle['y'] = center_y + dy * scale
                        else:
                            selected_circle['x'] = mouse_x
                            selected_circle['y'] = mouse_y
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Calculate distances and end this batch
                        batch_distances = calculate_distances(circles)
                        all_distances.update(batch_distances)
                        running = False
            
            draw_circles(circles, selected_circle)
    
    # Save results
    save_results(all_distances, participant_number)
    
    # Show completion message
    screen.fill(BLACK)
    font = pygame.font.Font(None, 48)
    text = font.render("Thank you for participating!", True, WHITE)
    screen.blit(text, (center_x - text.get_width() // 2, center_y - 50))
    
    font = pygame.font.Font(None, 36)
    text2 = font.render("Press any key to exit", True, WHITE)
    screen.blit(text2, (center_x - text2.get_width() // 2, center_y + 50))
    pygame.display.flip()
    
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                waiting = False
            if event.type == pygame.KEYDOWN:
                waiting = False
    
    pygame.quit()
    sys.exit()

# Function to save results
def save_results(distances, participant_id):
    # Create a dataframe from the distances
    pairs = []
    dist_values = []
    
    for (idx1, idx2), dist in distances.items():
        pairs.append(f"{idx1}-{idx2}")
        dist_values.append(dist)
    
    df = pd.DataFrame({
        'Pair': pairs,
        'Distance': dist_values
    })
    
    # Save to Excel
    filename = f"Participantdata/participant_{participant_id}_results.xlsx"
    df.to_excel(filename, index=False)
    print(f"Results saved to {filename}")
    
    # Create and save RDM (Representational Dissimilarity Matrix)
    # Determine max index
    max_idx = 0
    for (idx1, idx2) in distances.keys():
        max_idx = max(max_idx, idx1, idx2)
    
    # Create matrix (initialized with NaN)
    rdm_size = max_idx + 1
    rdm = np.full((rdm_size, rdm_size), np.nan)
    
    # Fill in distances
    for (idx1, idx2), dist in distances.items():
        rdm[idx1, idx2] = dist
        rdm[idx2, idx1] = dist  # Mirror
    
    # Set diagonal to 0 (distance to self)
    np.fill_diagonal(rdm, 0)
    
    # Save RDM
    rdm_filename = f"Participantdata/participant_{participant_id}_rdm.npy"
    np.save(rdm_filename, rdm)
    print(f"RDM saved to {rdm_filename}")

if __name__ == "__main__":
    main() 