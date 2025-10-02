# config.py
import os
from pathlib import Path

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent

# CSV file paths - use absolute paths for Streamlit
PRICING_CSV = BASE_DIR / 'data' / 'QuoteSheet1.csv'
ZONES_CSV = BASE_DIR / 'data' / 'QuoteSheet2.csv'
SURCHARGES_CSV = BASE_DIR / 'data' / 'QuoteSheet3.csv'

# AI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
AI_MODEL = "gpt-5-nano"  # Make sure this model is available to you

# Service Mapping
SERVICE_MAPPING = {
    'E': 'Economy',
    'ND': 'Next Day',
    'Next Day': 'ND',
    'Economy': 'E'
}

# Debug function to check file existence
def check_files():
    """Check if required files exist"""
    files = {
        'Pricing CSV': PRICING_CSV,
        'Zones CSV': ZONES_CSV,
        'Surcharges CSV': SURCHARGES_CSV
    }
    
    for name, path in files.items():
        exists = path.exists()
        print(f"{name}: {path} - {'EXISTS' if exists else 'MISSING'}")
    
    return all(path.exists() for path in files.values())
