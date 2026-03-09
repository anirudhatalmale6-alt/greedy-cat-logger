"""
Test the GUI with sample data to verify it works correctly.
Generates random results and launches the GUI.
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FOOD_ITEMS
from logger import ResultLogger
from gui import StatsGUI


def generate_sample_data(logger, num_results=75):
    """Generate sample results to populate the GUI."""
    # Weighted distribution (some items appear more often)
    weights = {
        "tomato": 15,
        "corn": 10,
        "chicken": 3,
        "cow": 8,
        "carrot": 12,
        "fish": 5,
        "salad": 12,
        "pizza": 15,
        "shrimp": 7,
    }

    items = []
    for food, weight in weights.items():
        items.extend([food] * weight)

    for i in range(num_results):
        food = random.choice(items)
        logger.add_result(food, round_number=871900 + i, confidence=random.uniform(0.8, 0.99))
        time.sleep(0.01)  # Small delay for timestamps


def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    logger = ResultLogger(output_dir=output_dir)

    if logger.total_rounds == 0:
        print("Generating 75 sample results...")
        generate_sample_data(logger, 75)
        print(f"Generated {logger.total_rounds} results")

    logger.save_excel()
    print(f"Excel saved to {logger.excel_path}")

    print("Launching GUI...")
    gui = StatsGUI(logger)
    gui.run()


if __name__ == "__main__":
    main()
