# Greedy Cat Result Logger

Real-time game result tracking & statistics for the Greedy Cat game running on Android emulators (LDPlayer/BlueStacks).

## Features

- **Auto-Detection**: Monitors the emulator screen and detects result icons using OpenCV template matching
- **Manual Mode**: Click to add results manually if auto-detection isn't set up
- **Live Statistics**: Shows counts, percentages, hot/cold items, streaks
- **Recent Results**: Visual icon strip showing the last 30 results
- **Result History**: Full log with round numbers and timestamps
- **Export**: Save to CSV and formatted Excel files
- **Continuous Monitoring**: Runs all day, scanning every 2 seconds

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Or run in manual-only mode (no screen detection needed)
python main.py --manual
```

## Setup for Auto-Detection

1. Take screenshots of each food icon from the game
2. Save them as `templates/tomato.png`, `templates/carrot.png`, etc.
3. Or use the extraction tool: `python extract_templates.py <screenshot.png>`
4. Set the capture region in the GUI to match your emulator's Result row position

## Detected Items

| Item | Emoji | Multiplier |
|------|-------|-----------|
| Tomato | 🍅 | x5 |
| Corn | 🌽 | x5 |
| Chicken | 🐔 | x45 |
| Cow | 🐄 | x15 |
| Carrot | 🥕 | x5 |
| Fish | 🐟 | x25 |
| Salad | 🥗 | x5 |
| Pizza | 🍕 | x5 |
| Shrimp | 🦐 | x10 |

## Files

- `main.py` - Main entry point
- `gui.py` - Statistics GUI window
- `detector.py` - OpenCV icon detection engine
- `capture.py` - Screen capture module
- `logger.py` - CSV/Excel result logging
- `config.py` - Configuration settings
- `extract_templates.py` - Template extraction tool
- `setup_templates.py` - Create placeholder templates

## Requirements

- Python 3.8+
- Windows (for screen capture from emulator)
- LDPlayer or BlueStacks emulator
