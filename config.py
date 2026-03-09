"""Configuration for Greedy Cat Result Logger"""

# All possible food items in the game (10 items)
FOOD_ITEMS = [
    "tomato",
    "corn",
    "chicken",
    "cow",
    "carrot",
    "fish",
    "salad",
    "pizza",
    "shrimp",
    "pepper",
]

# Display names and emoji for the GUI
FOOD_DISPLAY = {
    "tomato":  {"emoji": "\U0001f345", "color": "#FF6347", "name": "Tomato"},
    "corn":    {"emoji": "\U0001f33d", "color": "#FFD700", "name": "Corn"},
    "chicken": {"emoji": "\U0001f414", "color": "#FFA500", "name": "Chicken"},
    "cow":     {"emoji": "\U0001f404", "color": "#8B4513", "name": "Cow"},
    "carrot":  {"emoji": "\U0001f955", "color": "#FF8C00", "name": "Carrot"},
    "fish":    {"emoji": "\U0001f41f", "color": "#4169E1", "name": "Fish"},
    "salad":   {"emoji": "\U0001f957", "color": "#32CD32", "name": "Salad"},
    "pizza":   {"emoji": "\U0001f355", "color": "#FF4500", "name": "Pizza"},
    "shrimp":  {"emoji": "\U0001f990", "color": "#FF69B4", "name": "Shrimp"},
    "pepper":  {"emoji": "\U0001fad1", "color": "#DC143C", "name": "Pepper"},
}

# Multipliers from the game wheel
FOOD_MULTIPLIER = {
    "tomato":  5,
    "corn":    5,
    "chicken": 45,
    "cow":     15,
    "carrot":  5,
    "fish":    25,
    "salad":   5,
    "pizza":   5,
    "shrimp":  10,
    "pepper":  5,
}

# Screen capture settings
CAPTURE_INTERVAL_MS = 2000  # Check screen every 2 seconds
RESULT_REGION = None  # Will be set during calibration (x, y, width, height)

# Detection settings
MATCH_THRESHOLD = 0.42  # OpenCV template matching threshold

# File paths
CSV_FILENAME = "greedy_cat_results.csv"
EXCEL_FILENAME = "greedy_cat_results.xlsx"
TEMPLATES_DIR = "templates"
