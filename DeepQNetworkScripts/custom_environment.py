# Import Dependencies
import torch # PyToch library for building and training neural networks
from torch import nn
from torch.optim import AdamW
import numpy as np # for numerical calculations
from collections import namedtuple, deque # provides useful data structures may not need
import random # for random sampling 
from mss import mss # for grabbing a screen shot of a monitor 
import pydirectinput # for mouse and keyboard input on windows
import cv2 as cv # for image and video processing
import pytesseract # OCR tool for reading text from images
from matplotlib import pyplot as plt
import matplotlib.patches as patches
import time
from gymnasium import Env
from gymnasium.spaces import Box, Discrete
from gymnasium.utils.env_checker import check_env  # Import the environment checker
import math
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class PacMan(Env):
    def __init__(self):
        super().__init__()
        
        # Define spaces
        self.observation_space = Box(low=0, high=255, shape=(6,50,80), dtype=np.uint8)
        self.action_space = Discrete(4) # number of possible actions
        
        # Define capture locations
        self.cap = mss()
        self.game_location = {'top':50, 'left':-2280, 'width':1400, 'height':1300}# defines game viewing location
        self.lives_location = {'top':1070, 'left':-902, 'width':600, 'height':200} # defines lives location
        self.frame_stack = deque(maxlen=6) # stack frames to provide a sense of motion
        #self.score_location = {'top':380, 'left':-920, 'width':600, 'height':80} # defines score location
        #self.done_location = {'top':508, 'left':-1810, 'width':450, 'height':80} 
            
        # Define lives
        self.previous_lives = 2
        self.current_lives = self.previous_lives
        self.previous_score = 0
        self.time_alive = 0
        self.last_life = 2
        self.survival_reward_factor = 0.1
        
        # Define pellet count
        self.pellet_address = 0x7268 # ROM memory address
        self.file_path = "pellet_count.txt" # file to store value
        self.previous_pellet_count = self.read_pellet_count_from_file()
        

        # Define templates for tracking
        self.ghost_template = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\ghost_template.png', 0)
        self.ghost_template2 = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\ghost_template3.png', 0)
        self.ghost_template3 = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\ghost_template4.png', 0)
        self.pacman_life_template = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_life_icon.png', 0)
        self.pacman_template_left = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_template_left.png', 0)
        self.pacman_template_right = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_template_right.png', 0)
        self.pacman_template_up = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_template_up.png', 0)
        self.pacman_template_down = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_template_down.png', 0)
        self.pacman_template_closed = cv.imread('C:\\Users\\John Wesley\\Docs\\PacMan\\PacManGame\\Images\\pacman_template_closed.png', 0)
        
    # Observation of the state of the environment
    def get_observation(self):
        # Get screen capture of game
        raw = np.array(self.cap.grab(self.game_location))[:,:,:3]
        # Grayscale
        gray = cv.cvtColor(raw, cv.COLOR_BGR2GRAY)
        # Resize
        resized = cv.resize(gray, (80,50))
        # Add channels first
        channel = np.reshape(resized, (1,50,80))
        return channel
    
    def get_stacked_observation(self):
        # Stack the frames in the deque and convert to the required shape
        return np.concatenate(list(self.frame_stack), axis=0)
    
    # Get number of lives left
    def get_lives(self):   
        # Capture the area where the lives are displayed
        lives_cap = np.array(self.cap.grab(self.lives_location))[:,:,:3]
        # Convert to grayscale
        lives_gray = cv.cvtColor(lives_cap, cv.COLOR_BGR2GRAY)
        # Perform template matching
        result = cv.matchTemplate(lives_gray, self.pacman_life_template, cv.TM_CCORR_NORMED)
        locations = np.where(result >= 0.8) # find areas that have values at or above threshold value
        lives_value = len(list(zip(*locations[::-1])))
        
        # Determine number of lives
        if lives_value == 684:
            num_lives = 2 
        elif lives_value == 344:
            num_lives = 1
        else:
            num_lives = 0
            
        return num_lives
    
    # Get game over
    def get_done(self):
        # Get the number of lives left 
        num_lives = self.get_lives()
        return num_lives == 0 # return bool
    
    # Get pellet count
    def read_pellet_count_from_file(self):
        try:
            with open(self.file_path, "r") as file:
                return int(file.read().strip())
        except (FileNotFoundError, ValueError):
            return 0
        
    # Resets the environment to its initial state
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # restart the game
        pydirectinput.click(x=-890, y=374) # Select game window
        pydirectinput.press('f1') # Start state 1 save
        # Reset pellet count
        self.previous_pellet_count = self.read_pellet_count_from_file()
        # Reset frame stack
        self.frame_stack.clear() # Delete all items from Deque
        # Update deque with reset state
        for _ in range(6):
            initial_frame = self.get_observation()
            self.frame_stack.append(initial_frame)
            
        return self.get_stacked_observation(), {}
    
    # Rendering method to see what the computer sees
    def render(self):
        frame = self.render_positions()
        cv.imshow('Game', frame)
        if cv.waitKey(1) & 0xFF == ord('q'):
            self.close()
            
    # Closes rendering window        
    def close(self):
        cv.destroyAllWindows()
    
    # Find character locations on screen            
    def get_character_positions(self):
        # Capture the area where the lives are displayed
        screen_capture = np.array(self.cap.grab(self.game_location))[:,:,:3]
        cv.imwrite('game_capture.png', screen_capture)
        # Convert to grayscale
        gray_screen = cv.cvtColor(screen_capture, cv.COLOR_BGR2GRAY)
        
        # Match the templates to find Pac-Man and Ghosts
        result_left = cv.matchTemplate(gray_screen, self.pacman_template_left, cv.TM_CCOEFF_NORMED)
        result_right = cv.matchTemplate(gray_screen, self.pacman_template_right, cv.TM_CCOEFF_NORMED)
        result_up = cv.matchTemplate(gray_screen, self.pacman_template_up, cv.TM_CCOEFF_NORMED)
        result_down = cv.matchTemplate(gray_screen, self.pacman_template_down, cv.TM_CCOEFF_NORMED)
        result_closed = cv.matchTemplate(gray_screen, self.pacman_template_closed, cv.TM_CCOEFF_NORMED)
        result_ghost = cv.matchTemplate(gray_screen, self.ghost_template, cv.TM_CCOEFF_NORMED)
        result_ghost2 = cv.matchTemplate(gray_screen, self.ghost_template2, cv.TM_CCOEFF_NORMED)
        result_ghost3 = cv.matchTemplate(gray_screen, self.ghost_template3, cv.TM_CCOEFF_NORMED)
        
        # Locate pacman
        pacman_threshold = 0.6 # Adjust this value based on testing
        locations_left = np.where(result_left >= pacman_threshold)
        locations_right = np.where(result_right >= pacman_threshold)
        locations_up = np.where(result_up >= pacman_threshold)
        locations_down = np.where(result_down >= pacman_threshold)
        locations_closed = np.where(result_closed >= pacman_threshold)
        
        # Locate ghosts
        ghost_threshold = 0.5
        location_ghost = np.where(result_ghost >= ghost_threshold)
        location_ghost2 = np.where(result_ghost2 >= ghost_threshold)
        location_ghost3 = np.where(result_ghost3 >= ghost_threshold)
        
        # Pack locations
        pacman_combined_locations = list(zip(*locations_left[::-1])) + list(zip(*locations_right[::-1])) + list(zip(*locations_up[::-1])) + list(zip(*locations_down[::-1])) + list(zip(*locations_closed[::-1]))
        ghost_position = list(zip(*location_ghost[::-1])) + list(zip(*location_ghost2[::-1]))  + list(zip(*location_ghost3[::-1]))

        return ghost_position, pacman_combined_locations, screen_capture
 # Find ghosts by color
    def find_ghosts_by_color(self, image):
        # Convert image to HSV color space
        hsv_image = cv.cvtColor(image, cv.COLOR_BGR2HSV)
        
        # Define range of colors to search
        ghost_colors = {
            'blinky': {'lower': np.array([0, 100, 100]), 'upper': np.array([10, 255, 255])},  # Red
            'pinky': {'lower': np.array([160, 100, 100]), 'upper': np.array([170, 255, 255])}, # Pink
            'inky': {'lower': np.array([85, 100, 100]), 'upper': np.array([95, 255, 255])},   # Cyan
            'clyde': {'lower': np.array([15, 100, 100]), 'upper': np.array([25, 255, 255])}
        }
        
        ghost_positions = {}
        total_ghosts = 0
        # Iterate over each ghost color and find position
        for ghost, color_range in ghost_colors.items():
            # Create mask for color
            mask = cv.inRange(hsv_image, color_range['lower'], color_range['upper'])
            # Find contours
            contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            positions = []
            # Iterate over each contour
            for contour in contours:
                # Calculate bounding box
                x, y, w, h = cv.boundingRect(contour)
                positions.append((x+w//2, y+h//2)) # Center of the ghost
            ghost_positions[ghost] = positions
            #print(f"{len(positions)} {ghost}(s) found")
            
            total_ghosts += len(positions)

        #print(f"{total_ghosts} total ghost(s) found")
        return ghost_positions
       
    # Method to see character detection    
    def render_positions(self):
        # Get character positions
        ghost_position, pacman_combined_locations, screen_capture = self.get_character_positions()

        screen_capture = np.ascontiguousarray(screen_capture) # convert captured image to OpenCV compatability
        
        # Draw rectangles around matched Pac-Man locations using OpenCV
        for loc in pacman_combined_locations:
            top_left = loc
            bottom_right = (top_left[0] + self.pacman_template_right.shape[1], top_left[1] + self.pacman_template_right.shape[0])
            # Create a rectangle patch and add it to the plot
            cv.rectangle(screen_capture, top_left, bottom_right, (255, 0, 0), 2)
            
        # Draw rectangles around matched Ghost locations using OpenCV
        for loc in ghost_position:
            top_left = loc
            bottom_right = (top_left[0] + self.ghost_template.shape[1], top_left[1] + self.ghost_template.shape[0])
            # Create a rectangle patch and add it to the plot
            cv.rectangle(screen_capture, top_left, bottom_right, (0, 0, 255), 2)

        # cv.imshow('Test Render positions', screen_capture)
        # cv.waitKey(0)
        # cv.destroyAllWindows()
        return screen_capture
    
    def calculate_distance (self, pacman_pos, ghost_pos):
        # Unpack positions
        pacman_x, pacman_y = pacman_pos
        ghost_x, ghost_y = ghost_pos
        return math.sqrt((ghost_x - pacman_x) ** 2 + (ghost_y - pacman_y) ** 2)
    
    # Calculate reward for eating pellets
    def get_pellet_reward(self, current_pellet_count):
        if current_pellet_count < self.previous_pellet_count:
            reward = 10 
            self.previous_pellet_count = current_pellet_count
        else:
            reward = 0
        reward = self.normalize_reward(reward)    
        return reward
    
    def ghost_avoidance_reward(self, screen_image):
        ghost_positions = self.find_ghosts_by_color(screen_image)
        _, pacman_combined_locations, _ = self.get_character_positions()
        if pacman_combined_locations:
            pacman_pos = pacman_combined_locations[0]
        else:
            pacman_pos = (0, 0)
        safe_distance = 360
        avoidance_reward = 0
        
        for ghost, posiitons in ghost_positions.items():
           for ghost_pos in posiitons:
               distance = self.calculate_distance(pacman_pos, ghost_pos)
               if distance > safe_distance:
                   avoidance_reward += 20 / len(ghost_positions)
               else:
                   avoidance_reward -= 5
        avoidance_reward = self.normalize_reward(avoidance_reward)
        return avoidance_reward
    
    def normalize_reward(self, reward, min_reward=-1.0, max_reward=1.0):
        return np.clip(reward, min_reward, max_reward)
      
    # def ghost_avoidance_reward(self):
    #     ghost_positions, pacman_combined_locations, _ = self.get_character_positions()
    #     if pacman_combined_locations:
    #         pacman_pos = pacman_combined_locations[0]
    #     else:
    #         pacman_pos = (0, 0)
    #     safe_distance = 260
    #     avoidance_reward = 0
        
    #     for ghost_index, ghost_pos in enumerate(ghost_positions):
    #         distance = self.calculate_distance(pacman_pos, ghost_pos)
    #         #print(f"Ghost {ghost_index + 1} Position: {ghost_pos}, Distance: {distance}")
    #         if distance > safe_distance:
    #             avoidance_reward += (distance - safe_distance)
    #         else:
    #             avoidance_reward -= (safe_distance - distance) * 2
    #     return avoidance_reward
    
    # Method that is called to do something in the game

    def step(self, action):
        action_map = {
            0: 'left',   # Move Left
            1: 'right',  # Move Right
            2: 'up',     # Move Up
            3: 'down',   # Move Down
        }
        
        pydirectinput.press(action_map[action])
        
        # Reward for eating pellets 
        current_pellet_count = self.read_pellet_count_from_file()
        pellet_reward = self.get_pellet_reward(current_pellet_count)
        
        # Reward for avoiding ghosts
        raw = np.array(self.cap.grab(self.game_location))[:,:,:3]
        avoidance_reward = self.ghost_avoidance_reward(raw)
        
        # Bonus reward for staying alive      
        current_lives = self.get_lives()
        if current_lives < self.last_life:
            self.time_alive = 0
            self.last_life = current_lives
        self.time_alive += 1
        survival_reward = self.survival_reward_factor * (1.1 ** self.time_alive)
        survival_reward = self.normalize_reward(survival_reward)
        #survival_reward = self.time_alive * 1.01 
        
        # Penalize only when a life is lost (and only once per life loss)
        life_penalty = 0
        if current_lives < self.previous_lives:
            life_penalty = self.normalize_reward(-40)
            self.previous_lives = current_lives # update previous lives 
           
        reward = avoidance_reward + survival_reward + pellet_reward + life_penalty
        
        done = self.get_done()
        
        # Get the next observation
        new_frame = self.get_observation()
        self.frame_stack.append(new_frame)
        stacked_observation = self.get_stacked_observation()
        
        return stacked_observation, reward, done, False, {}
    

class DinoGame(Env):
    def __init__(self):
        
        super().__init__()
        # options = Options()
        # options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        # self.driver = webdriver.Chrome(options=options)
        self.observation_space = Box(low=0, high=255, shape=(6,50,200), dtype=np.uint8)
        self.action_space = Discrete(3) # number of possible actions
        self.cap = mss()
        # self.game_location = {'top':910, 'left':-2250, 'width':1200, 'height':370} # defines viewing area
        # self.done_location = {'top':240, 'left':-2230, 'width':1800, 'height':300} # defines 'GAME OVER' location    
        # self.obstacle_location = {'top':910, 'left':-1910, 'width':1200, 'height':300} # defines obstacle viewing location
        # self.obstacle_height_location = {'top':910, 'left':-1910, 'width':1200, 'height':340}
        self.game_location = {'top':460, 'left':-2100, 'width':1000, 'height':200}
        self.done_location = {'top':340, 'left':-1630, 'width':700, 'height':100} # defines 'GAME OVER' location    
        self.obstacle_location = {'top':420, 'left':-1810, 'width':300, 'height':200}
        self.frame_stack = deque(maxlen=6) # stack frames to provide a sense of motion; DQN benefits from this
        
            # Initialize other variables
        self.past_rewards = []  # To store past rewards for normalization
        self.reward_sum = 0
        self.reward_count = 0

    # observation of the state of the environment
    def get_observation(self):
        # Get screen capture of game
        raw = np.array(self.cap.grab(self.game_location))[:,:,:3]
        #Grayscale
        gray = cv.cvtColor(raw, cv.COLOR_BGR2GRAY)
        # Resize
        resized = cv.resize(gray, (200,50))
        # Add channels first
        channel = np.reshape(resized, (1,50,200))
        return channel
    
    def get_stacked_observation(self):
        # stack the frames in the deque and convert to the required shape
        return np.concatenate(list(self.frame_stack), axis=0)
   
    # Get the done text using OCR
    def get_done(self):
        # Get done screen
        done_cap = np.array(self.cap.grab(self.done_location))[:,:,:3]
        
        # Apply OCR
        done = False
        res = pytesseract.image_to_string(done_cap)[:4]
        if res == "GAME" or res == 'GAM': # NOTE: doesn't recognize 'OVER'
            done = True
        return done
    
    # Resets the environment to its initial state
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # self.driver.execute_script("Runner.instance_.setSpeed(15);")
        time.sleep(0.3)
        pydirectinput.click(x=-1385, y=527)
        pydirectinput.press('up')
        # Reset the frame stack
        self.frame_stack.clear()
        for _ in range(6):
            initial_frame = self.get_observation()
            self.frame_stack.append(initial_frame)
        return self.get_stacked_observation(), {}
    
    
    # Detect objects
    def is_obstacle_nearby(self):
        # Capture current frame
        current_frame = np.array(self.cap.grab(self.obstacle_location))[:,:,:3]
        
        # Define a threshold for detecting obstacles
        obstacle_threshold = 200
        obstacle_detected = np.sum(current_frame < obstacle_threshold) > 500
        return obstacle_detected
    # def get_obstacle_height(self):
    #     # Capture current frame
    #     current_frame = np.array(self.cap.grab(self.obstacle_height_location))[:,:,:3]
    #     gray = cv.cvtColor(current_frame, cv.COLOR_BGR2GRAY)
    #     edges = cv.Canny(gray, threshold1=100, threshold2=200)
        
    #     contours, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        
    #     obstacle_height = 0
    #     for contour in contours:
    #         x, y, w, h = cv.boundingRect(contour)
    #         if h > obstacle_height:
    #             obstacle_height = h
    #     return obstacle_height
    # def classify_obstacle_by_height(self, height):
    #     if height == 152 or height == 233:
    #         return "pterodactyl"
    #     elif height == 229 or height == 340:
    #         return "cactus"
    #     else:
    #         return "unkown"
        
    def normalize_reward(self, reward):
        self.past_rewards.append(reward)
        self.reward_sum += reward
        self.reward_count += 1

        mean_reward = self.reward_sum / self.reward_count
        std_reward = (sum((r - mean_reward) ** 2 for r in self.past_rewards) / (self.reward_count + 1)) ** 0.5

        normalized_reward = (reward - mean_reward) / (std_reward + 1e-8)
        return normalized_reward
    
    # method to take an action as an input and applies it to the environment
    def step(self, action):
        #               Jump        Duck      No Action
        action_map = {0:'up', 1:'down', 2:'no_op'}
        total_reward = 0 
        
        # Check if obstacle is nearby before performing action
        obstacle_nearby = self.is_obstacle_nearby()
        # height = self.get_obstacle_height()
        # obstacle_type = self.classify_obstacle_by_height(height)
        
        # Perform the action
        if action != 2:
            pydirectinput.press(action_map[action])
            
        # Checking whether the game is done
        done = self.get_done()

        # Reward - we get a point for every frame we are alive
        reward = 2
        total_reward += reward
        
        # if not done:
        #     if obstacle_nearby:
        #         if action == 0 and obstacle_type == "cactus":
        #             total_reward += 70 # Large reward for jumping over an obstacle that was a cactus
        #         elif action == 1 and obstacle_type == "pterodactyl": # Reward for ducking after jumping
        #             total_reward += 70
        #         # reward for action and not dying even if obstacle is not identified
        #         elif action == 0:
        #             total_reward += 20 # small reward for jumping when an obstacle is nearby
        #         elif action == 1:
        #             total_reward += 20 # small reward for ducking when an obstacle is nearby
        #         else:
        #             total_reward -= 15 # Penalty for doing nothing when an obstacle is nearby
        #     else:
        #         if action == 2: # Doing nothing when its safe
        #             total_reward += 30 # Small reward for doing nothing when safe
        # else:
        #     total_reward -= 60 # Penalty for dying
        if not done:
            if obstacle_nearby:
                if action == 0:
                    total_reward += 70 # Large reward for jumping over an obstacle that was a cactus
                elif action == 1: # Reward for ducking after jumping
                    total_reward += 70
                # reward for action and not dying even if obstacle is not identified
                elif action == 0:
                    total_reward += 20 # small reward for jumping when an obstacle is nearby
                elif action == 1:
                    total_reward += 20 # small reward for ducking when an obstacle is nearby
                else:
                    total_reward -= 15 # Penalty for doing nothing when an obstacle is nearby
            else:
                if action == 2: # Doing nothing when its safe
                    total_reward += 30 # Small reward for doing nothing when safe
        else:
            total_reward -= 60 # Penalty for dying
            
        normalized_reward = self.normalize_reward(total_reward)       
        # Get the latest frame
        new_frame = self.get_observation()
        # Update frame stack
        self.frame_stack.append(new_frame)
        # Get stacked observation for the next state
        stacked_observation = self.get_stacked_observation()
        
        return stacked_observation, normalized_reward, done, False, {}