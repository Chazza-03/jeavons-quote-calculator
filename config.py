# config.py
import os

# CSV file paths - updated for new structure
PRICING_CSV = 'data/quotesheet1.csv'
ZONES_CSV = 'data/quotesheet2.csv'
SURCHARGES_CSV = 'data/quotesheet3.csv'

# AI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# Use a more widely available model
AI_MODEL = "gpt-5-nano"  

# Service Mapping
SERVICE_MAPPING = {
    'E': 'Economy',
    'ND': 'Next Day',
    'Next Day': 'ND',
    'Economy': 'E'
}
