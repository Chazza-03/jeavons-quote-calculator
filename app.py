# app.py
import streamlit as st
import os
from dotenv import load_dotenv
from quote_calculator import calculate_road_haulage_quote

# Load environment variables
load_dotenv()

# Configure the page
st.set_page_config(
    page_title="Jeavons Eurotir Quote Calculator",
    page_icon="🚚",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .quote-section {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Surcharges configuration
SURCHARGES = {
    "tail_lift": {
        "name": "Tail-lift per consignment",
        "price": 12.50,
        "description": "Required for deliveries without loading dock"
    },
    "moffat_delivery": {
        "name": "Moffat Delivery",
        "price": 108.00,
        "description": "Service available only for 8 pallets & above"
    },
    "am_pm_delivery": {
        "name": "AM or PM deliveries Next Day",
        "price": 20.00,
        "description": "Specific time window delivery (AM or PM)"
    },
    "timed_delivery": {
        "name": "Timed deliveries Next Day",
        "price": 40.00,
        "description": "Specific timed delivery"
    },
    "london_charge": {
        "name": "London & Suburb Charge",
        "price": 20.00,
        "description": "These postcodes will attract the London & Suburb Charge"
    },
    "cargo_labels": {
        "name": "Cargo Identification Labels",
        "price": 0.30,
        "description": "Per label",
        "quantity_based": True
    },
    "airway_bill": {
        "name": "Airway Bill Printing",
        "price": 3.50,
        "description": "Documentation fee"
    },
    "adr_surcharge": {
        "name": "ADR Surcharge",
        "price": 35.00,
        "description": "For dangerous goods"
    }
}

def calculate_template_quote(base_price, selected_surcharges, cargo_label_quantity=1):
    """Calculate quote based on template inputs"""
    fuel_surcharge_rate = 0.08  # 8%
    vat_rate = 0.20  # 20%
    
    # Calculate fuel surcharge
    fuel_surcharge = base_price * fuel_surcharge_rate
    
    # Calculate other surcharges
    other_surcharges = 0
    surcharge_details = {}
    
    for surcharge_key, surcharge_data in selected_surcharges.items():
        surcharge_config = SURCHARGES[surcharge_key]
        
        if surcharge_key == "cargo_labels" and surcharge_data["selected"]:
            # Use the quantity from the main input
            quantity = cargo_label_quantity
            amount = quantity * surcharge_config["price"]
            surcharge_details[surcharge_config["name"]] = f"£{amount:.2f} ({quantity} labels)"
            other_surcharges += amount
        elif surcharge_data["selected"]:
            amount = surcharge_config["price"]
            surcharge_details[surcharge_config["name"]] = f"£{amount:.2f}"
            other_surcharges += amount
    
    # Calculate totals
    subtotal = base_price + fuel_surcharge + other_surcharges
    vat_amount = subtotal * vat_rate
    total = subtotal + vat_amount
    
    return {
        "base_price": base_price,
        "fuel_surcharge": fuel_surcharge,
        "other_surcharges": other_surcharges,
        "surcharge_details": surcharge_details,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total
    }

def main():
    # Header
    st.markdown('<div class="main-header">🚚 Jeavons Eurotir Quote Calculator</div>', unsafe_allow_html=True)
    
    # Check if API key is set (only needed for quote request)
    if not os.getenv('OPENAI_API_KEY'):
        st.error("⚠️ OPENAI_API_KEY not found. Please set it in the environment variables.")
        st.info("""
        **To set up your API key:**
        1. Go to Streamlit Cloud
        2. Navigate to your app settings
        3. Add OPENAI_API_KEY in the Secrets section
        """)
    
    # Quote type selection
    quote_type = st.radio(
        "Select Quote Type:",
        ["Quote Request", "Quote Template"],
        horizontal=True,
        help="Choose between analyzing email requests or creating manual quotes"
    )
    
    if quote_type == "Quote Request":
        render_quote_request()
    else:
        render_quote_template()

def render_quote_request():
    """Render the quote request interface for Uniexpress"""
    
    # Check if API key is available
    if not os.getenv('OPENAI_API_KEY'):
        st.warning("⚠️ Quote Request functionality requires OPENAI_API_KEY to be set")
        return
    
    # Create two columns for email input and quote results
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📧 Email Input")
        
        email_subject = st.text_input(
            "Email Subject*",
            value="Quote Request",
            placeholder="e.g., Urgent quote request for 5 pallets to BHX",
            help="Enter the email subject line"
        )
        
        email_body = st.text_area(
            "Email Body*",
            height=400,
            placeholder="Paste the full email content here...\n\nExample:\nWe need to ship 5 pallets from our Colchester warehouse to Birmingham Airport (BHX). Each pallet is 120x80x120cm and weighs approximately 500kg. Total volume is 13.550 M3. We need next day delivery.",
            help="Paste the complete email content"
        )
        
        # Generate quote button in the left column
        if st.button("🚀 Generate Quote", type="primary", use_container_width=True):
            if not email_subject or not email_body.strip():
                st.error("Please enter both email subject and body")
                return
            
            # Store the result in session state to display in the right column
            with st.spinner("🤖 AI is analyzing the email and calculating your quote..."):
                try:
                    st.session_state.quote_result = calculate_road_haulage_quote(email_subject, email_body)
                    st.session_state.quote_type = "request"
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.info("Please check your input and try again. If the problem persists, contact support.")
    
    with col2:
        st.subheader("💰 Quote Breakdown")
        
        # Display quote results if they exist in session state
        if "quote_result" in st.session_state and st.session_state.get("quote_type") == "request":
            display_quote_request_result(st.session_state.quote_result)
        else:
            st.info("👈 Enter email content and click 'Generate Quote' to see the quote breakdown here.")

def render_quote_template():
    """Render the quote template interface"""
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📋 Quote Template")
        
        # Base price input
        base_price = st.number_input(
            "Base Price (£)*",
            min_value=0.0,
            step=10.0,
            value=100.0,
            help="Enter the base price for the service"
        )
        
        # Quantity input for cargo labels (moved here)
        cargo_label_quantity = st.number_input(
            "Quantity of Items*",
            min_value=1,
            value=1,
            help="Number of items"
        )
        
        st.markdown("---")
        st.subheader("➕ Additional Surcharges")
        
        # Surcharges checklist (demurrage removed)
        selected_surcharges = {}
        
        for key, config in SURCHARGES.items():
            # Skip demurrage surcharge
            if key == "demurrage":
                continue
                
            col_a, col_b = st.columns([3, 2])
            
            with col_a:
                selected = st.checkbox(
                    config["name"],
                    help=config["description"]
                )
            
            with col_b:
                if config.get("quantity_based"):
                    # For cargo labels, we'll use the quantity from above
                    st.write(f"£{config['price']:.2f} each")
                    selected_surcharges[key] = {
                        "selected": selected
                    }
                else:
                    st.write(f"£{config['price']:.2f}")
                    selected_surcharges[key] = {
                        "selected": selected
                    }
        
        # Generate template quote button
        if st.button("📄 Create Quote", type="primary", use_container_width=True):
            if base_price <= 0:
                st.error("Please enter a valid base price")
                return
            
            # Calculate the quote
            quote_result = calculate_template_quote(base_price, selected_surcharges, cargo_label_quantity)
            st.session_state.template_quote = quote_result
            st.session_state.quote_type = "template"
            
            # Show success message
            st.success("✅ Quote created successfully!")
    
    with col2:
        st.subheader("💰 Quote Breakdown")
        
        # Display template quote results
        if "template_quote" in st.session_state and st.session_state.get("quote_type") == "template":
            display_template_quote_result(st.session_state.template_quote)
        else:
            st.info("👈 Configure your quote and click 'Create Quote' to see the breakdown here.")

def display_quote_request_result(result):
    """Display the quote request results"""
    
    if "error" in result:
        st.markdown('<div class="error-box">', unsafe_allow_html=True)
        st.error(f"**Calculation Error:** {result['error']}")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    quote_data = result["quote_result"]
    extracted_info = result["extracted_info"]
    
    if not quote_data.get("success", False):
        st.error("Quote calculation failed")
        return
    
    # Success message
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    st.success("✅ Quote Generated Successfully!")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create tabs for different sections
    tab1, tab2 = st.tabs(["💰 Breakdown", "🔍 Extracted Data"])
    
    with tab1:
        # Create a nice table for the quote breakdown
        breakdown = quote_data["quote_breakdown"]
        total_amount = breakdown["Total"]
        
        # Display each line item
        for item, amount in breakdown.items():
            if item == "Total":
                st.markdown("---")
                if isinstance(amount, (int, float)):
                    st.markdown(f"### **Total: £{amount:.2f}**")
                else:
                    st.markdown(f"### **Total: {amount}**")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(item)
                with col2:
                    if isinstance(amount, (int, float)):
                        st.write(f"£{amount:.2f}")
                    else:
                        st.write(str(amount))
    
    with tab2:
        # Display what the AI extracted
        st.json(extracted_info)
        st.info("This shows the raw data extracted by AI from the email content.")

def display_template_quote_result(quote):
    """Display the template quote results"""
    
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    st.success("✅ Quote Created Successfully!")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create a clean breakdown
    st.markdown("### 📊 Cost Breakdown")
    
    # Base price and fuel surcharge
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Collection & delivery", f"£{quote['base_price']:.2f}")
    
    with col2:
        st.metric("Fuel Surcharge (8%)", f"£{quote['fuel_surcharge']:.2f}")
    
    # Other surcharges
    if quote['surcharge_details']:
        st.markdown("#### Additional Surcharges")
        for surcharge_name, amount in quote['surcharge_details'].items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(surcharge_name)
            with col2:
                st.write(amount)
    
    # Totals
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Subtotal (ex. VAT)", f"£{quote['subtotal']:.2f}")
    
    with col2:
        st.metric("VAT (20%)", f"£{quote['vat_amount']:.2f}")
    
    st.markdown("---")
    st.markdown(f"## **Total (inc. VAT): £{quote['total']:.2f}**")
    
    # Optional: Add copy button for the quote
    st.copy_button(
        label="📥 Copy Quote Summary",
        data=f"""

Collection & delivery: £{quote['base_price']:.2f}
Fuel Surcharge (8%): £{quote['fuel_surcharge']:.2f}

Additional Surcharges:
{chr(10).join([f"- {name}: {amount}" for name, amount in quote['surcharge_details'].items()]) if quote['surcharge_details'] else "None"}

Subtotal (ex. VAT): £{quote['subtotal']:.2f}


        """,
        file_name="jeavons_quote.txt",
        mime="text/plain"
    )

if __name__ == "__main__":
    main()
