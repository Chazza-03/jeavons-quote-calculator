# ai_extractor.py
import openai
import re
import json
from config import OPENAI_API_KEY, AI_MODEL
import os
from dotenv import load_dotenv

class AIQuoteExtractor:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = openai.OpenAI(api_key=api_key)
    
    def extract_quote_info(self, email_subject, email_body):
        """
        Extract quote information using AI
        """
        prompt = self._create_extraction_prompt(email_subject, email_body)
        
        try:
            response = self.client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,  
                response_format={"type": "json_object"}
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            return self._validate_and_clean_data(extracted_data)
            
        except Exception as e:
            print(f"AI extraction error: {e}")
            return self._fallback_extraction(email_subject, email_body)
    
    def _create_extraction_prompt(self, subject, body):
        return f"""
        You are a logistics expert for Jeavons Eurotir, a UK road haulage company.
        Extract the following information from the email for a quote calculation:
        
        EMAIL SUBJECT: {subject}
        EMAIL BODY: {body}
        
        Extract these SPECIFIC details as JSON:
        {{
            "freight_type": "pallets/crates/boxes/etc (infer from context)",
            "quantity": number of items (extract number),
            "total_weight": "weight with units (kg/tonnes/lbs), may be GW",
            "dimensions": ["dimension strings if mentioned"],
            "volume_m3": "volume in cubic meters if mentioned (e.g., 13.550 M3, or cbm)",
            "from_address": "pickup location address or collection: town, Postcode",
            "to_address": "delivery destination address (include airport codes like BHX, LHR, etc as part of address)", 
            "delivery_date": "requested delivery date",
            "service_type": "ND (Next Day) or E (Economy) - Default to ND if Economy not determined",
            
            // OPTIONAL fields (set to false/empty if not mentioned)
            "tail_lift_needed": boolean,
            "moffett_delivery": boolean,
            "delivery_time": "AM/PM/None",
            "labeling_required": boolean,
            "awb_printing": boolean,
            "adr_surcharge": boolean,
            "special_requirements": "any special notes"
        }}
        
        IMPORTANT RULES:
        - If delivery mentions airport codes (BHX, LHR, LGW, MAN, STN, EDI, GLA), include them in to_address
        - BHX = Birmingham Airport, LHR = Heathrow, LGW = Gatwick, MAN = Manchester
        - Service_type: ND for urgent/next-day, E for standard/economy
        - Extract postcodes from addresses when possible
        - Convert all weights to kg in the format "X kg"
        - Extract volume in cubic meters (m³) if mentioned (look for patterns like "13.550 M3", "10m³", "5 cubic meters")
        - Be precise with numbers and addresses
        - Return empty strings/arrays/false for missing information
        """
    
    def _validate_and_clean_data(self, data):
        """Clean and validate extracted data"""
        # Ensure required fields exist
        required_fields = ['freight_type', 'quantity', 'total_weight', 'from_address', 'to_address']
        for field in required_fields:
            if field not in data:
                data[field] = ""
        
        # Clean numeric fields
        if data.get('quantity'):
            data['quantity'] = self._extract_number(data['quantity'])
        
        # Clean weight format
        if data.get('total_weight'):
            data['total_weight'] = self._standardize_weight(data['total_weight'])
        
        # Clean volume field
        if data.get('volume_m3'):
            try:
                volume_str = str(data['volume_m3'])
                volume_match = re.search(r'(\d+\.?\d*)', volume_str)
                if volume_match:
                    data['volume_m3'] = float(volume_match.group(1))
                else:
                    data['volume_m3'] = None
            except (ValueError, TypeError):
                data['volume_m3'] = None
        else:
            data['volume_m3'] = None
        
        # Enhance dimensions handling for multiple items
        if data.get('dimensions') and data.get('quantity', 1) > 1:
            if len(data['dimensions']) == 1 and data['quantity'] > 1:
                single_dimension = data['dimensions'][0]
                data['dimensions'] = [single_dimension] * data['quantity']
                print(f"DEBUG: Duplicated dimension '{single_dimension}' for {data['quantity']} items")
        
        # Enhance address extraction and validate postcodes
        data['to_address'] = self._enhance_address_extraction(data.get('to_address', ''), data.get('special_requirements', ''))
        data['from_address'] = self._enhance_address_extraction(data.get('from_address', ''), data.get('special_requirements', ''))
        
        # Debug postcode extraction
        from_postcode = self._extract_postcode(data.get('from_address', ''))
        to_postcode = self._extract_postcode(data.get('to_address', ''))
        
        if from_postcode:
            print(f"DEBUG: From address postcode: {from_postcode}")
        if to_postcode:
            print(f"DEBUG: To address postcode: {to_postcode}")
        
        return data

    def _validate_uk_postcode(self, postcode):
        """
        Validate UK postcode format
        """
        if not postcode:
            return False
        
        # Basic UK postcode pattern
        uk_postcode_pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$'
        return re.match(uk_postcode_pattern, postcode.strip().upper()) is not None

    def _extract_postcode(self, address):
        """
        Extract postcode from address string
        """
        if not address:
            return None
        
        # UK postcode regex pattern
        postcode_patterns = [
            r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}',  # Standard format
            r'[A-Z]{1,2}[0-9]{1,2} ?[0-9]?[A-Z]{2}',      # Variant format
        ]
        
        for pattern in postcode_patterns:
            matches = re.findall(pattern, address.upper())
            if matches:
                for match in matches:
                    if self._validate_uk_postcode(match):
                        return match
        
        return None
    
    def _extract_number(self, text):
        """Extract first number from text"""
        match = re.search(r'(\d+)', str(text))
        return int(match.group(1)) if match else 0
    
    def _standardize_weight(self, weight_text):
        """Convert weight to kg format"""
        weight_text = str(weight_text).lower()
        
        # Extract number
        match = re.search(r'(\d+\.?\d*)', weight_text)
        if not match:
            return "0 kg"
        
        weight = float(match.group(1))
        
        # Convert to kg
        if 'ton' in weight_text:
            weight *= 1000
        elif 'lb' in weight_text or 'pound' in weight_text:
            weight *= 0.453592
        
        return f"{weight} kg"
    
    def _enhance_address_extraction(self, address, special_requirements):
        """Enhance address extraction by looking for airport codes and validating postcodes"""
        if address and address.strip():
            # Extract and validate postcode from the address
            postcode = self._extract_postcode(address)
            if postcode:
                print(f"DEBUG: Valid postcode found: {postcode}")
            return address
        
        # Look for airport codes in special requirements or infer from context
        text_to_search = special_requirements.lower() if special_requirements else ""
        
        airport_mappings = {
            'bhx': 'Birmingham Airport (BHX), B26 3QJ',
            'lhr': 'Heathrow Airport (LHR), TW6 1EW', 
            'lgw': 'Gatwick Airport (LGW), RH6 0NP',
            'man': 'Manchester Airport (MAN), M90 1QX',
            'stn': 'Stansted Airport (STN), CM24 1RW',
            'edi': 'Edinburgh Airport (EDI), EH12 9DN',
            'gla': 'Glasgow Airport (GLA), PA3 2SW'
        }
        
        for code, full_address in airport_mappings.items():
            if code in text_to_search:
                return full_address
        
        return ""
    
    def _fallback_extraction(self, subject, body):
        """Fallback method if AI extraction fails"""
        print("Using fallback extraction method")
        
        # Extract from address postcode if available
        from_address = ""
        from_postcode_match = re.search(r'(\b[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}\b)', body.upper())
        if from_postcode_match:
            from_postcode = from_postcode_match.group(1)
            from_address = f"Newport, {from_postcode}"  # Or extract full address context
        
        # Rest of the fallback method remains the same...
        to_address = ""
        
        # Look for airport codes in the email body
        airport_codes = ['BHX', 'LHR', 'LGW', 'MAN', 'STN', 'EDI', 'GLA']
        for code in airport_codes:
            if code in body:
                airport_mapping = {
                    'BHX': 'Birmingham Airport (BHX), B26 3QJ',
                    'LHR': 'Heathrow Airport (LHR), TW6 1EW',
                    'LGW': 'Gatwick Airport (LGW), RH6 0NP', 
                    'MAN': 'Manchester Airport (MAN), M90 1QX',
                    'STN': 'Stansted Airport (STN), CM24 1RW',
                    'EDI': 'Edinburgh Airport (EDI), EH12 9DN',
                    'GLA': 'Glasgow Airport (GLA), PA3 2SW'
                }
                to_address = airport_mapping.get(code, f"{code} Airport")
                break
        
        # Extract quantity
        quantity_match = re.search(r'(\d+)\s*pallet', body.lower())
        quantity = int(quantity_match.group(1)) if quantity_match else 0
        
        # Extract weight
        weight_match = re.search(r'(\d+)\s*kg', body.lower())
        weight = f"{weight_match.group(1)} kg" if weight_match else "0 kg"
        
        # Extract volume
        volume_m3 = None
        volume_patterns = [
            r'(\d+\.?\d*)\s*m³',
            r'(\d+\.?\d*)\s*m3',
            r'(\d+\.?\d*)\s*m\^3',
            r'(\d+\.?\d*)\s*cubic meter',
            r'(\d+\.?\d*)\s*M3',
            r'(\d+\.?\d*)\s*M³'
        ]
        
        for pattern in volume_patterns:
            volume_match = re.search(pattern, body, re.IGNORECASE)
            if volume_match:
                try:
                    volume_m3 = float(volume_match.group(1))
                    break
                except ValueError:
                    continue
        
        return {
            "freight_type": "pallets",
            "quantity": quantity,
            "total_weight": weight,
            "dimensions": [],
            "volume_m3": volume_m3,
            "from_address": from_address,  # Now includes postcode if found
            "to_address": to_address,
            "delivery_date": "",
            "service_type": "ND",
            "tail_lift_needed": False,
            "moffett_delivery": False,
            "delivery_time": None,
            "labeling_required": False,
            "awb_printing": False,
            "adr_surcharge": False,
            "special_requirements": ""
        }
