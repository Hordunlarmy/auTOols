# Terminal-Themed PDF CV/Portfolio

A Python script that generates a terminal-themed PDF CV/Portfolio.

## Setup

1. Install Poetry (if not already installed):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies:

   ```bash
   poetry install
   ```

3. Generate the PDF:

   ```bash
   poetry run python generate_pdf.py
   ```

   Or use the script entry point:

   ```bash
   poetry run generate-cv
   ```

## Customization

Edit `generate_pdf.py` and `info.json` to customize:

- Personal information (name, email, location, etc.)
- Skills and technologies
- Projects and experience
- Education and contact information

The generated PDF will be saved as `portfolio-cv.pdf` in the same directory.
