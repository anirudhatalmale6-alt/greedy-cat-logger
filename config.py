"""Configuration for Greedy Cat Result Logger"""

# All possible food items in the game
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
]

# Display names and emoji for the GUI
FOOD_DISPLAY = {
    "tomato":  {"emoji": "🍅", "color": "#FF6347", "name": "Tomato"},
    "corn":    {"emoji": "🌽", "color": "#FFD700", "name": "Corn"},
    "chicken": {"emoji": "🐔", "color": "#FFA500", "name": "Chicken"},
    "cow":     {"emoji": "🐄", "color": "#8B4513", "name": "Cow"},
    "carrot":  {"emoji": "🥕", "color": "#FF8C00", "name": "Carrot"},
    "fish":    {"emoji": "🐟", "color": "#4169E1", "name": "Fish"},
    "salad":   {"emoji": "🥗", "color": "#32CD32", "name": "Salad"},
    "pizza":   {"emoji": "🍕", "color": "#FF4500", "name": "Pizza"},
    "shrimp":  {"emoji": "🦐", "color": "#FF69B4", "name": "Shrimp"},
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
}

# Screen capture settings
CAPTURE_INTERVAL_MS = 2000  # Check screen every 2 seconds
RESULT_REGION = None  # Will be set during calibration (x, y, width, height)

# Detection settings
MATCH_THRESHOLD = 0.75  # OpenCV template matching threshold

# File paths
CSV_FILENAME = "greedy_cat_results.csv"
EXCEL_FILENAME = "greedy_cat_results.xlsx"
TEMPLATES_DIR = "templates"
