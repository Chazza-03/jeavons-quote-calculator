# quote_calculator.py
import csv
import re
import os
from config import PRICING_CSV, ZONES_CSV, SURCHARGES_CSV, SERVICE_MAPPING
from ai_extractor import AIQuoteExtractor

def load_csv_data(file_path):
    """Load CSV data from file"""
    data = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    except FileNotFoundError:
        print(f"Warning: {file_path} not found")
    return data

class RoadHaulageQuoteCalculator:
    def __init__(self):
        self.extractor = AIQuoteExtractor()
        self.pricing_data = load_csv_data(PRICING_CSV)
        self.zones_data = load_csv_data(ZONES_CSV)
        self.surcharges_data = load_csv_data(SURCHARGES_CSV)
    
    def calculate_quote(self, email_subject, email_body):
        """
        Main function to calculate quote from email content
        """
        #print("Extracting information from email...")
        extracted_info = self.extractor.extract_quote_info(email_subject, email_body)
        
        #print("Calculating quote...")
        quote_result = self._calculate_pricing(extracted_info)
        
        return {
            "extracted_info": extracted_info,
            "quote_result": quote_result
        }
    
    def _calculate_pricing(self, info):
        """Calculate pricing based on extracted information"""
        try:
            # Validate essential information
            if not info.get('from_address'):
                return {"error": "Missing pickup address"}
            
            if not info.get('quantity') or info['quantity'] == 0:
                return {"error": "Missing or invalid quantity"}
            
            # Extract volume_m3 if provided - handle both string and float
            volume_m3 = info.get('volume_m3')
           # print(f"DEBUG: Raw volume_m3 from AI: {volume_m3} (type: {type(volume_m3)})")
            
            if volume_m3:
                try:
                    if isinstance(volume_m3, str):
                        # Extract numeric value from string like "13.550 M3"
                        volume_match = re.search(r'(\d+\.?\d*)', volume_m3)
                        if volume_match:
                            volume_m3 = float(volume_match.group(1))
                            #print(f"DEBUG: Extracted volume from string: {volume_m3}m³")
                        else:
                            volume_m3 = None
                    elif isinstance(volume_m3, (int, float)):
                        volume_m3 = float(volume_m3)
                        #print(f"DEBUG: Using numeric volume: {volume_m3}m³")
                except (ValueError, TypeError) as e:
                    #print(f"DEBUG: Error parsing volume: {e}")
                    volume_m3 = None
            else:
                volume_m3 = None
            
            # FIX: Use PICKUP address (FROM address) for zone determination
            pickup_address = info.get('from_address', '')
            postcode = self._extract_postcode(pickup_address)
            if not postcode:
                return {"error": f"Could not extract postcode from pickup address: {pickup_address}"}
            
            zone_info = self._find_zone_by_postcode(postcode)
            if not zone_info:
                return {"error": f"Service not available for postcode: {postcode}"}
            
            zone, service_level = zone_info
            
            service_type = info.get('service_type', 'E')
            service_code = SERVICE_MAPPING.get(service_type, 'E')
            
            if service_code not in service_level:
                service_code = 'ND'  # Default to Economy
            
            weight_kg = self._parse_weight(info.get('total_weight', '0 kg'))
            quantity = info.get('quantity', 1)
            
            # Use the higher of actual weight or volume weight (pass volume_m3)
            billable_weight = self._calculate_billable_weight(weight_kg, quantity, info.get('dimensions', []), volume_m3)
            
            base_price = self._find_base_price(billable_weight, zone, service_code)
            if isinstance(base_price, str) and base_price == "P.O.A":
                return {"error": "Price on application - please contact us"}
            
            surcharges = self._calculate_surcharges(info, base_price, zone, quantity)
            
            total_price = base_price + surcharges['total']
            
            # NEW: Organize output in requested format
            quote_breakdown = {
                "Actual weight": f"{weight_kg} kg",
                "Billed for": f"{round(billable_weight, 2)} kg / Zone {zone} / {service_code}",
                "Collection & Delivery": round(base_price, 2),
                "Fuel Surcharge (8% of freight)": round(base_price * 0.08, 2),
                "Airway bill printing": self._get_surcharge_amount('Airway Bill Printing'),
                f"Cargo identification labels ({quantity} @ £0.30)": round(quantity * 0.30, 2)
            }
            
            # Calculate other surcharges (everything except the main ones above)
            other_surcharges_total = surcharges['total'] - (
                quote_breakdown["Fuel Surcharge (8% of freight)"] +
                quote_breakdown["Airway bill printing"] +
                quote_breakdown[f"Cargo identification labels ({quantity} @ £0.30)"]
            )
            
            quote_breakdown["Other surcharges"] = round(other_surcharges_total, 2)
            quote_breakdown["Total"] = round(total_price, 2)
            
            
            
            # Other details moved to separate section
            other_details = {
                "quantity": quantity,
                "weight_kg": round(billable_weight, 2),
                "service_type": service_code,
                "zone": zone,
                "from_address": info.get('from_address', ''),
                "to_address": info.get('to_address', ''),
                "delivery_date": info.get('delivery_date', ''),
                "volume_m3": volume_m3,
                "notes": "This is an automated quote. Final price subject to confirmation.",
                "surcharge_details": surcharges['breakdown']  # Keep detailed breakdown available
            }
            
            return {
                "success": True,
                "quote_breakdown": quote_breakdown,
                "other_details": other_details
            }
            
        except Exception as e:
            return {"error": f"Calculation error: {str(e)}"}
    
    def _extract_postcode(self, address):
        """Extract UK postcode from address"""
        if not address:
            return None
        
        # First try standard UK postcode pattern
        pattern = r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}'
        matches = re.findall(pattern, address, re.IGNORECASE)
        if matches:
            return matches[0]
        
        # Enhanced: Handle partial postcodes like "CO7" by looking them up in zones
        address_upper = address.upper().strip()
        
        # Check if it's just a postcode prefix (like "CO7")
        if re.match(r'^[A-Z]{1,2}\d{1,2}[A-Z]?$', address_upper):
            # This is likely a postcode prefix, find the most common postcode for this prefix
            for row in self.zones_data:
                zone_prefix = row['Postcode_Prefix'].strip().upper()
                # Handle simple prefix matches
                if address_upper.startswith(zone_prefix.split()[0]) or zone_prefix.startswith(address_upper):
                    # Return a sample postcode for this prefix (you might want to customize this)
                    sample_postcodes = {
                        'CO7': 'CO7 7AB', 'CO': 'CO1 1AB',
                        'B': 'B1 1AB', 'BHX': 'B26 3QJ',
                        'BH': 'BH1 1AB', 'AB': 'AB1 1AB',
                        # Add more mappings as needed
                    }
                    for prefix, sample in sample_postcodes.items():
                        if address_upper.startswith(prefix):
                            return sample
                    return f"{address_upper} 1AB"  # Fallback
        
        # Enhanced airport code detection (for pickup addresses that might be airports)
        airport_mappings = {
            'BHX': 'B26 3QJ',  # Birmingham Airport
            'LHR': 'TW6 1EW',  # Heathrow Airport
            'LGW': 'RH6 0NP',  # Gatwick Airport
            'MAN': 'M90 1QX',  # Manchester Airport
            'STN': 'CM24 1RW', # Stansted Airport
            'EDI': 'EH12 9DN', # Edinburgh Airport
            'GLA': 'PA3 2SW',  # Glasgow Airport,
            'CO7': 'CO7 7AB',  # Colchester area
        }
        
        # Check for airport codes or postcode prefixes in the address
        for code, postcode in airport_mappings.items():
            if code in address_upper:
                return postcode
        
        # Try common location names
        location_mappings = {
            'BIRMINGHAM AIRPORT': 'B26 3QJ',
            'HEATHROW AIRPORT': 'TW6 1EW',
            'GATWICK AIRPORT': 'RH6 0NP',
            'MANCHESTER AIRPORT': 'M90 1QX',
            'STANSTED AIRPORT': 'CM24 1RW',
            'EDINBURGH AIRPORT': 'EH12 9DN',
            'GLASGOW AIRPORT': 'PA3 2SW',
            'COLCHESTER': 'CO1 1AB',  # For CO7 area
        }
        
        for location_name, postcode in location_mappings.items():
            if location_name in address_upper:
                return postcode
        
        return None
    
    def _find_zone_by_postcode(self, postcode):
        """Find zone for a given postcode"""
        if not postcode:
            return None
        
        # Clean the postcode and extract prefix
        postcode_clean = postcode.upper().replace(' ', '')
        prefix_match = re.match(r'^[A-Z]{1,2}', postcode_clean)
        if not prefix_match:
            return None
        
        prefix = prefix_match.group(0)
        #print(f"DEBUG: Looking up zone for postcode: {postcode}, prefix: {prefix}")
        
        # First, try exact prefix matches
        for row in self.zones_data:
            zone_prefix = row['Postcode_Prefix'].strip().upper()
            
            # Handle special cases with ranges first
            if '-' in zone_prefix or '+' in zone_prefix:
                base_part = zone_prefix.split()[0] if ' ' in zone_prefix else zone_prefix
                base_match = re.match(r'^[A-Z]+', base_part)
                if base_match:
                    base = base_match.group(0)
                    if prefix.startswith(base):
                        # Handle ranges like "GU26-35" or "PA20+"
                        if '-' in zone_prefix:
                            try:
                                range_part = zone_prefix.split('-')[1]
                                prefix_num_match = re.search(r'\d+', postcode_clean.replace(base, ''))
                                if prefix_num_match:
                                    prefix_num = int(prefix_num_match.group())
                                    if '-' in range_part:
                                        range_start, range_end = map(int, range_part.split('-'))
                                        if range_start <= prefix_num <= range_end:
                                            #print(f"DEBUG: Found zone {row['Zone']} for {postcode} (range match)")
                                            return row['Zone'], row['Service_Level']
                                    else:
                                        # Single number
                                        if prefix_num == int(range_part):
                                            #print(f"DEBUG: Found zone {row['Zone']} for {postcode} (exact number match)")
                                            return row['Zone'], row['Service_Level']
                            except:
                                continue
                        elif '+' in zone_prefix:
                            try:
                                min_num = int(zone_prefix.split('+')[0].replace(base, ''))
                                prefix_num_match = re.search(r'\d+', postcode_clean.replace(base, ''))
                                if prefix_num_match:
                                    prefix_num = int(prefix_num_match.group())
                                    if prefix_num >= min_num:
                                        #print(f"DEBUG: Found zone {row['Zone']} for {postcode} (+ range match)")
                                        return row['Zone'], row['Service_Level']
                            except:
                                continue
            
            # Handle simple prefix matches (like "BN", "B", "AB", etc.)
            elif prefix == zone_prefix:
                #print(f"DEBUG: Found zone {row['Zone']} for {postcode} (exact prefix match)")
                return row['Zone'], row['Service_Level']
            
            # Handle cases like "GU (REST)" - match the base prefix
            elif ' ' in zone_prefix and '(' in zone_prefix:
                base_prefix = zone_prefix.split()[0]
                if prefix == base_prefix:
                    #print(f"DEBUG: Found zone {row['Zone']} for {postcode} (rest match)")
                    return row['Zone'], row['Service_Level']
        
        #print(f"DEBUG: No zone found for postcode: {postcode}")
        return None
    
    def _parse_weight(self, weight_str):
        """Parse weight string to kg - extract the actual weight mentioned"""
        if not weight_str:
            return 0
        
        # Look for the total weight mentioned in the email
        weight_str = str(weight_str).lower()
        
        # Try to extract the total weight (looking for patterns like "76.73 kgs")
        total_match = re.search(r'total.*?weight.*?(\d+\.?\d*)\s*(kg|kgs|kilogram)', weight_str)
        if total_match:
            return float(total_match.group(1))
        
        # Fallback to simple number extraction
        match = re.search(r'(\d+\.?\d*)', weight_str)
        if not match:
            return 0
        return float(match.group(1))
    
    def _calculate_billable_weight(self, weight_kg, quantity, dimensions, volume_m3=None):
        """Calculate billable weight - use the higher of actual weight or volume weight"""
        #print(f"\n=== BILLABLE WEIGHT CALCULATION ===")
        #print(f"Input - Actual weight: {weight_kg}kg, Quantity: {quantity}")
        #print(f"Dimensions: {dimensions}")
        #print(f"Provided volume: {volume_m3}m³" if volume_m3 else "No provided volume")
        
        # Use extracted weight only
        actual_weight_kg = weight_kg
        #print(f"1. ACTUAL WEIGHT: {actual_weight_kg}kg")
        
        # Calculate volume weight (pass volume_m3 if available)
        volume_weight_kg = self._calculate_volume_weight(dimensions, quantity, volume_m3)
        
        # Use the higher of actual weight or volume weight
        billable_weight = max(actual_weight_kg, volume_weight_kg)
        
        #print(f"2. VOLUME WEIGHT: {volume_weight_kg:.2f}kg")
        #print(f"3. BILLABLE WEIGHT: {billable_weight:.2f}kg (max of actual and volume weight)")
        
        return billable_weight
    
    def _calculate_volume_weight(self, dimensions, quantity, volume_m3=None):
        """Calculate weight based on volume (1m³ = 333kg) - prioritize provided volume over dimensions"""
        total_volume_m3 = 0
        
        #print(f"   DEBUG: volume_m3 parameter = {volume_m3} (type: {type(volume_m3)})")
        
        # PRIORITY 1: Use provided volume_m3 if available and valid
        if volume_m3 is not None and volume_m3 != "":
            try:
                # Ensure volume_m3 is a float
                if isinstance(volume_m3, str):
                    # Extract numeric value from string
                    volume_match = re.search(r'(\d+\.?\d*)', volume_m3)
                    if volume_match:
                        volume_m3 = float(volume_match.group(1))
                    else:
                        volume_m3 = 0
                elif isinstance(volume_m3, (int, float)) and volume_m3 > 0:
                    total_volume_m3 = float(volume_m3)
                    #print(f"   Using provided volume: {total_volume_m3:.3f}m³")
                else:
                    volume_m3 = 0
            except (ValueError, TypeError):
                volume_m3 = 0
        
        # Only proceed to other methods if we don't have a valid volume
        if total_volume_m3 <= 0:
            # PRIORITY 2: Calculate from dimensions if no volume provided
            if dimensions:
                #print(f"   Calculating volume from dimensions:")
                for i, dim in enumerate(dimensions):
                    if isinstance(dim, str):
                        matches = re.findall(r'\d+', dim)
                        if len(matches) >= 3:
                            l, w, h = map(int, matches[:3])
                            volume_m3 = (l/100) * (w/100) * (h/100)  # cm to m
                            total_volume_m3 += volume_m3
                            print(f"     Item {i+1}: {l}x{w}x{h}cm = {volume_m3:.3f}m³")
                
                # CRITICAL FIX: Multiply by quantity to account for all items
                if total_volume_m3 > 0:
                    # If we have multiple different dimensions, we've already summed them
                    # If we have one dimension repeated multiple times, multiply by quantity
                    if len(dimensions) == 1 and quantity > 1:
                        total_volume_m3 = total_volume_m3 * quantity
                        #print(f"   Multiplied by {quantity} items: {total_volume_m3:.3f}m³ total")
            
            # PRIORITY 3: Default to standard pallet calculation
            else:
                # No dimensions provided - assume standard pallet (120x80x120cm = 1.152m³)
                standard_pallet_volume = 1.2 * 0.8 * 1.2  # 1.152m³
                total_volume_m3 = standard_pallet_volume * quantity
                #print(f"   No volume/dimensions - assuming {quantity} standard pallets: {total_volume_m3:.3f}m³")
        
        volume_weight_kg = total_volume_m3 * 333  # 1m³ = 333kg
        #print(f"   Total volume: {total_volume_m3:.3f}m³ × 333kg/m³ = {volume_weight_kg:.2f}kg")
        return volume_weight_kg

    
    def _find_base_price(self, weight, zone, service):
        """Find base price from pricing table - always round weight UP to next bracket"""
        if not self.pricing_data:
            return 0
            
        # Get all weight tiers and sort them
        weight_tiers = []
        for row in self.pricing_data:
            try:
                weight_tiers.append(float(row['Weight_KG']))
            except (ValueError, KeyError):
                continue
                
        if not weight_tiers:
            return 0
            
        # Sort the weight tiers
        weight_tiers.sort()
        
        # Find the smallest tier that is >= the actual weight
        # If weight exceeds all tiers, use the largest tier
        tier = None
        for wt in weight_tiers:
            if wt >= weight:
                tier = wt
                break
        
        # If weight is larger than all tiers, use the largest available tier
        if tier is None:
            tier = max(weight_tiers)
        
        #print(f"DEBUG: Weight {weight}kg -> using tier {tier}kg")
        
        # Find the price for this tier, zone, and service
        for row in self.pricing_data:
            try:
                if (float(row['Weight_KG']) == tier and 
                    row['Zone'] == zone and 
                    row['Service'] == service):
                    if row['Price_GBP'] == 'P.O.A':
                        return "P.O.A"
                    return float(row['Price_GBP'])
            except (ValueError, KeyError):
                continue
        
        return 0
    
    def _calculate_surcharges(self, info, base_price, zone, quantity):
        """Calculate all applicable surcharges"""
        surcharges = {
            'total': 0,
            'breakdown': {}
        }
        
        # ALWAYS ADD: Airway Bill Printing (1 per order)
        airway_bill_charge = self._get_surcharge_amount('Airway Bill Printing')
        surcharges['total'] += airway_bill_charge
        surcharges['breakdown']['Airway Bill Printing'] = airway_bill_charge
        
        # ALWAYS ADD: Cargo Identification Labels (1 per item)
        cargo_labels_charge = self._get_surcharge_amount('Cargo Identification Labels')
        total_cargo_labels_charge = cargo_labels_charge * quantity
        surcharges['total'] += total_cargo_labels_charge
        surcharges['breakdown'][f'Cargo Identification Labels ({quantity} items)'] = total_cargo_labels_charge
        
        # Tail lift
        if info.get('tail_lift_needed'):
            charge = self._get_surcharge_amount('Tail-lift')
            surcharges['total'] += charge
            surcharges['breakdown']['Tail Lift'] = charge
        
        # Moffett delivery
        if info.get('moffett_delivery') and quantity >= 8:
            charge = self._get_surcharge_amount('Moffat')
            surcharges['total'] += charge
            surcharges['breakdown']['Moffett Delivery'] = charge
        
        # Time-based surcharges
        if info.get('delivery_time') in ['AM', 'PM']:
            charge = self._get_surcharge_amount('AM or PM')
            surcharges['total'] += charge
            surcharges['breakdown'][f'{info["delivery_time"]} Delivery'] = charge
        
        # ADR surcharge
        if info.get('adr_surcharge'):
            charge = self._get_surcharge_amount('ADR')
            surcharges['total'] += charge
            surcharges['breakdown']['ADR Surcharge'] = charge
        
        # London charge
        if zone in ['5', '6']:  # London zones
            charge = self._get_surcharge_amount('London')
            surcharges['total'] += charge
            surcharges['breakdown']['London Surcharge'] = charge
        
        # Fuel surcharge (8%)
        fuel_surcharge = base_price * 0.08
        surcharges['total'] += fuel_surcharge
        surcharges['breakdown']['Fuel Surcharge'] = round(fuel_surcharge, 2)
        
        return surcharges
    
    def _get_surcharge_amount(self, surcharge_type):
        """Get surcharge amount from surcharges table"""
        for row in self.surcharges_data:
            if surcharge_type.lower() in row['Surcharge_Type'].lower():
                try:
                    return float(row['Amount_GBP'])
                except:
                    return 0
        return 0

# Simplified interface
def calculate_road_haulage_quote(email_subject, email_body):
    """One-line function to get a quote"""
    calculator = RoadHaulageQuoteCalculator()
    return calculator.calculate_quote(email_subject, email_body)