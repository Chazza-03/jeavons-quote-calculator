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


def main():
    # Header
    st.markdown('<div class="main-header">🚚 Jeavons Eurotir Quote Calculator</div>', unsafe_allow_html=True)
    
    # Check if API key is set
    if not os.getenv('OPENAI_API_KEY'):
        st.error("⚠️ OPENAI_API_KEY not found. Please set it in the environment variables.")
        st.info("""
        **To set up your API key:**
        1. Go to Streamlit Cloud
        2. Navigate to your app settings
        3. Add OPENAI_API_KEY in the Secrets section
        """)
        return
    
    # Create two columns for email input and quote results
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📧 Email Input")
        
        email_subject = st.text_input(
            "Email Subject*",
            value="Quote result",  # Default value added here
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
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.info("Please check your input and try again. If the problem persists, contact support.")
    
    with col2:
        st.subheader("💰 Quote Breakdown")
        
        # Display quote results if they exist in session state
        if "quote_result" in st.session_state:
            display_quote_result(st.session_state.quote_result)
        else:
            st.info("👈 Enter email content and click 'Generate Quote' to see the quote breakdown here.")

def display_quote_result(result):
    """Display the quote results in the right column"""
    
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
    
    # Create tabs for different sections (only Quote Breakdown and Extracted Information)
    tab1, tab2 = st.tabs(["💰 Breakdown", "🔍 Extracted Data"])
    
    with tab1:
        # Create a nice table for the quote breakdown
        breakdown = quote_data["quote_breakdown"]
        total_amount = breakdown["Total"]
        
        # Display each line item - FIXED: Handle string values properly
        for item, amount in breakdown.items():
            if item == "Total":
                st.markdown("---")
                # Handle both string and numeric totals
                if isinstance(amount, (int, float)):
                    st.markdown(f"### **Total: £{amount:.2f}**")
                else:
                    st.markdown(f"### **Total: {amount}**")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(item)
                with col2:
                    # Handle both string and numeric amounts
                    if isinstance(amount, (int, float)):
                        st.write(f"£{amount:.2f}")
                    else:
                        st.write(str(amount))
    
    with tab2:
        # Display what the AI extracted
        st.json(extracted_info)
        
        st.info("This shows the raw data extracted by AI from the email content.")

if __name__ == "__main__":
    main()
