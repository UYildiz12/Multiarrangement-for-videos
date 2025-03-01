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

"""
Important: To be able to run this code you have replace the paths of the videos and images with the current 
paths to those videos & images. All required content is already in the zip file. You might also need to 
install the libraries of cv2, pygame, numpy and pandas
depending on whether your enviroment already has those libraries
"""    
pygame.init()
dir_path = os.path.join(os.path.dirname(__file__), "58videos")
avi_files = [f for f in os.listdir(dir_path) if f.endswith('.avi')]
video_names = [os.path.splitext(avi_file)[0] for avi_file in avi_files]
# Inıtialization for rdms
df = pd.DataFrame(columns=video_names, index=video_names)
np.fill_diagonal(df.values, 0)
#Initalizations for dragging 
dragged_frame = None
drag_offset_x = 0
drag_offset_y = 0
screen_width, screen_height = 1400, 1000 
screen = pygame.display.set_mode((screen_width, screen_height))
button_color = (0, 255, 0)  
button_color2 = (0, 255, 0)  
button_pos = (150, screen.get_height() + 120)  
button_size = (80, 50) 
button_font = pygame.font.Font(None, 24) 
button_text = button_font.render('Done', True, (0, 0, 0))  
button_rect = pygame.Rect(button_pos, button_size)

#Function simply takes a path and plays the video at that path using opencv library in a new popup window       
def play_video(video_path):
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    delay = int(1000 / fps)
    cv2.namedWindow('Video', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Video', width*2, height*2)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            cv2.imshow('Video', frame)
            if cv2.waitKey(delay) & 0xFF == ord('q'):
                break
        else:
            break
    cap.release()
    cv2.destroyAllWindows()
#Again function takes a path and plays the video but on the same window
def display_video(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    delay = int(1000 / fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (1200, 800))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = pygame.surfarray.make_surface(np.rot90(frame))
            pos_x = (screen.get_width() - frame.get_width()) // 2
            pos_y = (screen.get_height() - frame.get_height()) // 2
            screen.blit(frame, (pos_x, pos_y))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    cap.release()
                    return
            pygame.time.wait(delay)
        else:
            break
    cap.release()
#Function takes a list and uses the videopaths to call on display_video
def show_set(batch):
    for video_path in batch:
        video_path = os.path.join(dir_path, video_path)
        display_video(video_path)

#Function takes a list as an argument then returns every first frame that can be found by using the path from the list
def get_first_frames(batch):
    first_frames = []
    for video_file in batch:
        video_path = os.path.join(dir_path, video_file)
        cap = cv2.VideoCapture(video_path)
        ret , frame = cap.read()
        first_frames.append(frame)
    return first_frames

screen = pygame.display.set_mode((1400, 1000 ))
font = pygame.font.Font(None, 66)
random.shuffle(avi_files)
scale_factor=2.5
messages = [
    "Deneyimize hoş geldiniz. Bundan sonra devam etmek için boşluk tuşuna basın.",
    "Sizden gruplar halinde çeşitli eylemleri gösteren videolar izleyip, birbirlerine ne kadar benzediklerine göre ekrandaki pozisyonlarını belirlemenizi isteyeceğiz.",
    "Öncelikle, bloktaki her eylem için bir video izleyeceksiniz. Tüm videoları izledikten sonra, aşağıdaki örnekte olduğu gibi, gördüğünüz eylemleri temsil eden küçük daireler göreceksiniz:",
    "İzlediğiniz videoları temsil eden her daireyi büyük beyaz dairenin içine sürükleyip bırakmanız istenecek.",
    "Dairelere çift tıklayarak videoları tekrar izleyebilirsiniz. Deneydeki aşamaları tamamlayabilmek için her videoyu en az bir kez tekrar izlemelisiniz.",
    "Temsil edilen videoları beyaz daireye yerleştirirken eylemler örtüşebilir. Eylemlerin son derece benzer olduğunu düşünüyorsanız, dairelerin merkezlerini birbirine çok yakın yerleştirmelisiniz.",
    "Eylemlerin örtüşmek zorunda olmadığını unutmayın, daireleri tasvir edilen eylemlerin ne kadar benzer olduğunu düşündüğünüze göre yerleştirmelisiniz. Merkezden olan mesafenin önemli olduğunu unutmayın.",
    "Lütfen eylemlerin yerini ve diğer eylemlere olan mesafesini dikkatlice inceleyin. Seçiminizden emin olmak için her eylemi gerektiği kadar çok kez görüntülemenizi şiddetle tavsiye ederiz."
]

red_circle = pygame.image.load(os.path.join(os.path.dirname(__file__), 'img1.PNG'))
red_circle= pygame.transform.scale(red_circle, (280, 280))
pressed=False
#Introductory slides, 
for i, message in enumerate(messages):
    lines = textwrap.wrap(message, width=35)
    text_surfaces = [font.render(line, True, (255, 255, 255)) for line in lines]

    show_screen = True
    while show_screen:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    show_screen = False
        screen.fill((0, 0, 0))

        total_height = sum(text_surface.get_height() for text_surface in text_surfaces)

        start_y = (1000 - total_height) // 2

        for j, text_surface in enumerate(text_surfaces):
            x = (1400 - text_surface.get_width()) // 2
            y = start_y + j * text_surface.get_height() -220

            screen.blit(text_surface, (x, y))
        if i == 2:
            image_rect = red_circle.get_rect()
            image_rect.center = (1400 // 2, (start_y + total_height + image_rect.height+350) // 2)
            screen.blit(red_circle, image_rect)
        if i == 3:
            cap = cv2.VideoCapture(os.path.join(os.path.dirname(__file__), 'demovids', 'drag.mp4'))  
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps)
            while pressed==False:  
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if pressed==True:
                    break
                else:
                    while(cap.isOpened()):
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.resize(frame, (650, 500))
                            frame = cv2.flip(frame, 1)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = pygame.surfarray.make_surface(np.rot90(frame))
                            pos_x = (screen.get_width() - frame.get_width()) // 2
                            pos_y = (screen.get_height() - frame.get_height()+400) // 2
                            screen.blit(frame, (pos_x, pos_y))
                            pygame.display.flip()
                            for event in pygame.event.get():
                                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                                    pressed=True
                                    cap.release()
                                    show_screen=False
                                    break  
                            
                            
                            if pressed==True:
                                break
                            pygame.time.wait(delay)
                        else:
                            break 
                        if pressed==True:
                            break
        pressed=False
        if i == 4:
            cap = cv2.VideoCapture(os.path.join(os.path.dirname(__file__), 'demovids', 'Doubleclick.mp4'))  
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps)
            while pressed==False:
                print("heyo")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if pressed==True:
                    break
                else:
                    while(cap.isOpened()):
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.resize(frame, (650, 500))
                            frame = cv2.flip(frame, 1)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = pygame.surfarray.make_surface(np.rot90(frame))
                            pos_x = (screen.get_width() - frame.get_width()) // 2
                            pos_y = (screen.get_height() - frame.get_height()+400) // 2
                            screen.blit(frame, (pos_x, pos_y))
                            pygame.display.flip()
                            for event in pygame.event.get():
                                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                                    pressed=True
                                    cap.release()
                                    show_screen=False
                                    break  
                            
                            
                            if pressed==True:
                                break
                            pygame.time.wait(delay)
                        else:
                            break 
                        if pressed==True:
                            break
        pressed=False            
        if i == 5:
            cap = cv2.VideoCapture(os.path.join(os.path.dirname(__file__), 'demovids', 'Same.mkv'))  
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps)
            while pressed==False:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if pressed==True:
                    break
                else:
                    while(cap.isOpened()):
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.resize(frame, (650, 500))
                            frame = cv2.flip(frame, 1)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = pygame.surfarray.make_surface(np.rot90(frame))
                            pos_x = (screen.get_width() - frame.get_width()) // 2
                            pos_y = (screen.get_height() - frame.get_height()+400) // 2
                            screen.blit(frame, (pos_x, pos_y))
                            pygame.display.flip()
                            for event in pygame.event.get():
                                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                                    pressed=True
                                    cap.release()
                                    show_screen=False
                                    break  
                            
                            
                            if pressed==True:
                                break
                            pygame.time.wait(delay)
                        else:
                            break 
                        if pressed==True:
                            break
        pressed=False            
        if i == 6:
            cap = cv2.VideoCapture(os.path.join(os.path.dirname(__file__), 'demovids', 'similar.mp4'))  
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps)
            while pressed==False:
                print("heyo")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if pressed==True:
                    break
                else:
                    while(cap.isOpened()):
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.resize(frame, (650, 500))
                            frame = cv2.flip(frame, 1)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = pygame.surfarray.make_surface(np.rot90(frame))
                            pos_x = (screen.get_width() - frame.get_width()) // 2
                            pos_y = (screen.get_height() - frame.get_height()+400) // 2
                            screen.blit(frame, (pos_x, pos_y))
                            pygame.display.flip()
                            for event in pygame.event.get():
                                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                                    pressed=True
                                    cap.release()
                                    show_screen=False
                                    break  
                            
                            
                            if pressed==True:
                                break
                            pygame.time.wait(delay)
                        else:
                            break 
                        if pressed==True:
                            break
        pressed=False            
        if i == 7:
            cap = cv2.VideoCapture(os.path.join(os.path.dirname(__file__), 'demovids', 'Done.mp4'))  
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps)
            while pressed==False:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if pressed==True:
                    break
                else:
                    while(cap.isOpened()):
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.resize(frame, (650, 500))
                            frame = cv2.flip(frame, 1)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = pygame.surfarray.make_surface(np.rot90(frame))
                            pos_x = (screen.get_width() - frame.get_width()) // 2
                            pos_y = (screen.get_height() - frame.get_height()+400) // 2
                            screen.blit(frame, (pos_x, pos_y))
                            pygame.display.flip()
                            for event in pygame.event.get():
                                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                                    pressed=True
                                    cap.release()
                                    show_screen=False
                                    break  
                            
                            
                            if pressed==True:
                                break
                            pygame.time.wait(delay)
                        else:
                            break 
                        if pressed==True:
                            break
        pygame.display.update()
#Get the indexes of the batches that we saved earlier
with open(os.path.join(os.path.dirname(__file__), 'batches58.txt'), 'r') as f:
    batches = [[int(num) for num in line.strip().replace('(', '').replace(')', '').split(', ')] for line in f]

   
# This is the interactive part of the task where the batches are derived from an optimized list of indexes. 
# Each time you run the script, the avi files are randomized. 
# The algorithm we use aims to minimize the number of batches, thereby ensuring the minimum number of recalculated distances. 
# This refers to instances where videos appear with any other video in more than one batch.
# The videos that will have recalculated distances are randomized in every block.


for batch_indexes in batches:
    batch_videos = [avi_files[i] for i in batch_indexes]
    frame_names = []
    show_set(batch_videos)
    #Use previous function to get the first frames of the batch
    my_frames=get_first_frames(batch_videos)
    screen.fill((0, 0, 0))
    #Drawing the circle
    circle_radius = 355
    circle_thickness = 4  
    circle_color = (255, 255, 255)
    circle_center = (700, 500)  
    circle_diameter = 2 * circle_radius
    big_circle_rect = pygame.Rect(circle_center[0] - circle_radius, circle_center[1] - circle_radius, circle_diameter, circle_diameter)
    pygame.draw.circle(screen, (0, 0, 0), circle_center, circle_radius)
    pygame.draw.circle(screen, circle_color, circle_center, circle_radius, circle_thickness)
    pygame.display.flip()
    angle_step = 2 * math.pi / len(my_frames)
    frames = []
    rects = []
    frame_clicked = [False] * len(my_frames) 

    for i, frame in enumerate(my_frames):
        # Reverses the color channels of the frame. You can ignore this this is because of an issue with opencv
        frame = frame[:, :, ::-1]
        frame_surface = pygame.surfarray.make_surface(frame)       
        frame_surface = pygame.transform.flip(frame_surface, False, True)
        frame_surface = pygame.transform.scale(frame_surface, (int(frame_surface.get_width() // scale_factor), int(frame_surface.get_height() // scale_factor)))
        frame_surface = pygame.transform.rotate(frame_surface, -90)
        frame_width, frame_height = frame_surface.get_size()
        angle = i * angle_step
        # Calculates coordinates for moving the frame
        x = circle_center[0] + (circle_radius + frame_width - 50) * math.cos(angle) - frame_width / 2
        y = circle_center[1] - (circle_radius + frame_height - 50) * math.sin(angle) - frame_height / 2  
        # A mask is used here to create a circle pygame AFAIK itself doesn't support direct circle objects so we have to use a small workaround
        mask_surface = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
        pygame.draw.circle(mask_surface, (255, 255, 255, 128), (frame_width // 2, frame_height // 2), min(frame_width, frame_height) // 2)
        frame_surface.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        frame_surface.set_colorkey((0, 0, 0))
        screen.blit(frame_surface, (x, y))
        frames.append(frame_surface)
        rects.append(pygame.Rect(x, y, frame_width, frame_height))

    dragging = False
    dragged_frame_index = None
    drag_offset_x = 0
    drag_offset_y = 0
    pygame.display.flip()
    running=True
    last_click_time = None
    #Double clicks are registered if within 350ms
    double_click_time_limit = 350  
    while running==True:
        button_surface = pygame.Surface((80, 50), pygame.SRCALPHA)
        button_surface.fill((128, 128, 128, 128))  
        pygame.draw.rect(button_surface, (255, 255, 255, 128), button_surface.get_rect(), 2)
        button_text = button_font.render('Done', True, (0, 0, 0)) 
        button_surface.blit(button_text, button_text.get_rect(center=button_surface.get_rect().center))
        shadow_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, (0, 0, 0, 64), button_rect.move(4, 4)) 
        button_pos = (150, screen.get_height() - 190)
        button_rect.topleft = button_pos
        screen.blit(shadow_surface, (0, 0))
        screen.blit(button_surface, button_pos)
        screen.blit(shadow_surface, (0, 0))
        screen.blit(button_surface, (150, screen.get_height() + 140) )
        all_inside = all(big_circle_rect.contains(rect) for rect in rects) # Checks whether the positions of all the small red circles are inside the big white circle
        all_clicked = all(frame_clicked) #Checks whether all the small red circles have been clicked so the script the done button will unlock
        if all_inside and all_clicked:  
            button_color = (0, 255, 0, 128)  #Turns green
        else:
            button_color = (255, 0, 0, 128)  #Is red. It is initialized as red but this makes it dynamic
        button_surface_large = pygame.Surface((160, 100), pygame.SRCALPHA)
        button_surface_large.fill(button_color)
        pygame.draw.rect(button_surface_large, (255, 255, 255, 128), button_surface_large.get_rect(), 4)  
        button_text_large = pygame.font.Font(None, 48).render('Done', True, (0, 0, 0))
        button_surface_large.blit(button_text_large, button_text_large.get_rect(center=button_surface_large.get_rect().center))
    
        button_surface = pygame.transform.smoothscale(button_surface_large, (80, 50))
    
        screen.blit(shadow_surface, (0, 0))
        screen.blit(button_surface, button_pos)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN and button_rect.collidepoint(event.pos):    
                if all_inside and all_clicked:
                    #All objects inside the big circle
                    centers = [rect.center for rect in rects]
                    for avi_file in batch_videos[:len(centers)]:
                        frame_name = os.path.splitext(avi_file)[0]  
                        frame_names.append(frame_name)
                    for i in range(len(centers)):
                        for j in range(i+1, len(centers)):
                            dx = centers[i][0] - centers[j][0]
                            dy = centers[i][1] - centers[j][1]
                            distance = np.sqrt(dx**2 + dy**2)
                            if frame_names[i] in df.columns and frame_names[j] in df.index:
                                # If the cell already has a value, append to the list
                                if isinstance(df.loc[frame_names[i], frame_names[j]], list):
                                    df.loc[frame_names[i], frame_names[j]].append(distance)
                                    df.loc[frame_names[j], frame_names[i]].append(distance)
                                # If the cell is empty, create a new list
                                else:
                                    df.loc[frame_names[i], frame_names[j]] = [distance]
                                    df.loc[frame_names[j], frame_names[i]] = [distance]
                    # Calculate the average of distances
                    for i in range(len(centers)):
                        for j in range(i+1, len(centers)):
                            if isinstance(df.loc[frame_names[i], frame_names[j]], list):
                                avg_distance = np.mean(df.loc[frame_names[i], frame_names[j]])
                                df.loc[frame_names[i], frame_names[j]] = avg_distance
                                df.loc[frame_names[j], frame_names[i]] = avg_distance
                    running=False
                    break
                else:
                    print('Not all objects are inside the big circle.')

            if event.type == pygame.MOUSEBUTTONDOWN:
                current_time = pygame.time.get_ticks()
                #There is a last click and it is in 350ms from the current click
                if last_click_time is not None and current_time - last_click_time <= double_click_time_limit:
                    for i in range(len(frames)):
                       if rects[i].collidepoint(event.pos):
                           frame_clicked[i] = True  
                           video_path = os.path.join(dir_path, batch_videos[i])  
                           video_thread = threading.Thread(target=play_video, args=(video_path,))
                           video_thread.start()
                           break
                    last_click_time = current_time
                else:
                    
                    print("Mouse button down event detected.")
                    for i in range(len(frames)):
                        if rects[i].collidepoint(event.pos):
                            print("A frame was clicked.")
                            dragging = True
                            dragged_frame_index = i
                            drag_offset_x = event.pos[0] - rects[i].x
                            drag_offset_y = event.pos[1] - rects[i].y
                            last_click_time = current_time
                            break
            elif event.type == pygame.MOUSEBUTTONUP:
                print("Mouse button up event detected.")
                dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    print("Mouse motion event detected while dragging.")
                    rects[dragged_frame_index].x = event.pos[0] - drag_offset_x
                    rects[dragged_frame_index].y = event.pos[1] - drag_offset_y
                    
            
        screen.fill((0, 0, 0))
        pygame.draw.circle(screen, (0, 0, 0), circle_center, circle_radius)
        pygame.draw.circle(screen, circle_color, circle_center, circle_radius, circle_thickness)
    
        pygame.draw.rect(screen, button_color, button_rect)
        screen.blit(button_text, button_text.get_rect(center=button_rect.center))

        for i in range(len(frames)):
            # Set the color of the circle around the frame to green if the frame is clicked, otherwise red
            color = (0, 255, 0) if frame_clicked[i] else (255, 0, 0)  
            pygame.draw.circle(screen, color, rects[i].center, rects[i].width // 2.5, 3)  
            # Draw the frame on the screen
            screen.blit(frames[i], rects[i].topleft)
        if dragging and big_circle_rect.contains(rects[dragged_frame_index]):
            for i in range(len(frames)):
                if i != dragged_frame_index and big_circle_rect.contains(rects[i]):
                    s = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
                    # Draw a line from the center of the dragged frame to the center of the current frame
                    pygame.draw.line(s, (255, 0, 0, 115), rects[dragged_frame_index].center, rects[i].center, 7)          
                    screen.blit(s, (0, 0))
        pygame.display.flip()
        
      
pygame.quit()
