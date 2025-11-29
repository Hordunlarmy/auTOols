# Google Maps Public Edit Automation

A Python program to **programmatically submit public edits** to Google Maps locations using browser automation. This tool can suggest name changes, address updates, and other modifications to public locations on Google Maps.

## Features

- **Automated browser-based editing** - Uses Selenium to interact with Google Maps
- Submit name changes for public locations
- Submit address updates
- Support for batch processing multiple locations
- Both headless and visible browser modes
- Command-line interface for automation

## ⚠️ Important Notes

This tool submits **public edits** through browser automation. The edits:
- Go through Google's review process
- May require Google account sign-in
- Are subject to Google's moderation guidelines
- Take time to be approved and appear

## Quick Start

### 1. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows
```

### 2. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright and browser
playwright install chromium
```

### 3. Run Your First Edit

```bash
# Submit a public edit (no API key needed!)
python google_maps_edit_bot.py --search "Location Name" --name "New Name"

# Example:
python google_maps_edit_bot.py --search "Starbucks Seattle" --name "Starbucks Coffee"
```

## Setup

### Complete Setup Steps

1. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browser**
   ```bash
   playwright install chromium
   ```

   This downloads Chromium to `~/.cache/ms-playwright/chromium-1091/` (outside your project folder)

### What Gets Installed

- **Dependencies**: Installed in `venv/` (already in `.gitignore`)
- **Browser**: Downloaded to `~/.cache/ms-playwright/` by Playwright
- No system-wide installations required!

## Usage

### Submit a Public Edit (Recommended Method)

Use the browser automation bot to submit public edits:

```bash
# Suggest a name change
python google_maps_edit_bot.py --search "Starbucks Seattle" --name "Starbucks Coffee - Downtown"

# Suggest an address change
python google_maps_edit_bot.py --search "Target Store" --address "123 Main Street, Seattle, WA 98101"

# Suggest both name and address changes
python google_maps_edit_bot.py --search "Coffee Shop" --name "Better Coffee" --address "456 Oak Ave, Seattle, WA"

# Run in headless mode (invisible browser)
python google_maps_edit_bot.py --search "McDonald's" --name "McDonald's Restaurant" --headless
```

### Alternative: Use Places API (Query Only)

The original `google_maps_editor.py` can find locations using the Places API:

```bash
# Requires GOOGLE_MAPS_API_KEY in .env
python google_maps_editor.py find "Starbucks Seattle"
```

## How It Works

### Browser Automation Method (Recommended)

The `google_maps_edit_bot.py` uses **Playwright** to:
1. Launch Chromium browser (installed locally)
2. Navigate to Google Maps
3. Search for the specified location
4. Automatically open the "Suggest an edit" dialog
5. Fill in the new information (name, address, etc.)
6. Submit the edit programmatically

### Important Considerations

1. **Sign-in Required**: Some locations may require you to be signed into Google
2. **Rate Limiting**: Too many rapid edits may trigger Google's anti-spam measures
3. **CAPTCHA**: You may encounter CAPTCHAs if submitting too many edits
4. **Review Process**: All edits go through Google's moderation
5. **Manual Intervention**: Some edits may require manual confirmation in the browser

## Examples

### Basic Public Edit Submission

```bash
# Submit a name change
python google_maps_edit_bot.py --search "Pizza Restaurant" --name "Mario's Pizza Palace"

# Submit multiple changes at once
python google_maps_edit_bot.py --search "Grocery Store" --name "Fresh Market" --address "789 Elm Street, City, State"
```

### Using as a Module

```python
from google_maps_edit_bot import GoogleMapsEditBot

# Initialize bot
bot = GoogleMapsEditBot(headless=False)

try:
    # Search for location
    if bot.search_location("Coffee Shop Downtown"):
        bot.open_suggest_edit()
        bot.submit_name_change("Best Coffee Shop")
finally:
    bot.close()
```

### Batch Processing

See `automated_edit_example.py` for an example of processing multiple locations:

```bash
python automated_edit_example.py
```

## Project Structure

```
MapMod/
├── venv/                       # Virtual environment (auto-created, gitignored)
├── google_maps_edit_bot.py    # Browser automation bot (for public edits) ⭐
├── google_maps_editor.py       # Places API client (for querying)
├── automated_edit_example.py   # Batch editing example
├── example.py                  # API usage examples
├── config.py                   # Configuration loader
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
└── USAGE_GUIDE.md             # Detailed usage instructions
```

**Note**: The browser is installed in `~/.cache/ms-playwright/` by Playwright automatically.

## Requirements

### For Public Edits (google_maps_edit_bot.py)
- Python 3.7+
- Chrome browser installed
- Valid internet connection
- (Optional) Google account for some locations

### For Querying (google_maps_editor.py)
- Google Maps API key with Places API enabled
- Valid internet connection

## Troubleshooting

### Browser Automation Issues

**Playwright browser not found:**
```bash
# Reinstall the browser
playwright install chromium
```

**"Suggest an edit" button not found:**
- Google Maps UI may have changed
- Sign into Google account in the browser that opens
- Manually click "Suggest an edit" when prompted

**CAPTCHA appearing:**
- Slow down edit submission rate
- Don't run in headless mode
- Add delays between edits

### API Key Issues (for google_maps_editor.py only)
- Ensure your API key has the Places API enabled
- Check that billing is enabled for your Google Cloud project
- Verify the key is correctly set in `.env` file

## License

MIT License

## Disclaimer

This tool prepares edit suggestions. Actual changes to Google Maps locations may require approval through Google's review process and may have additional verification requirements for certain types of businesses.

