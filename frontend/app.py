import streamlit as st
import requests
import uuid
from datetime import datetime
from typing import List, Dict

# Configuration
API_URL = "http://localhost:8000"

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.user_id = "user123"  # Default user
    st.session_state.input_key = 0  # For clearing input

def send_message(message: str) -> Dict:
    """Send message to backend API"""
    try:
        response = requests.post(
            f"{API_URL}/api/message",
            json={
                "user_id": st.session_state.user_id,
                "session_id": st.session_state.session_id,
                "message": message
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {
            'response': f"⚠️ Error: {str(e)}",
            'intent': 'error',
            'confidence': 0,
            'recommendations': []
        }

def submit_feedback(rating: int, comment: str = ""):
    """Submit feedback to backend"""
    try:
        response = requests.post(
            f"{API_URL}/api/feedback",
            json={
                "user_id": st.session_state.user_id,
                "session_id": st.session_state.session_id,
                "rating": rating,
                "comment": comment
            }
        )
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Error submitting feedback: {str(e)}")
        return False

def get_bookings() -> List[Dict]:
    """Get user bookings from backend"""
    try:
        response = requests.get(
            f"{API_URL}/api/bookings/{st.session_state.user_id}"
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching bookings: {str(e)}")
        return []

def get_analytics() -> Dict:
    """Get system analytics"""
    try:
        response = requests.get(f"{API_URL}/api/analytics")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching analytics: {str(e)}")
        return {}

# Page configuration
st.set_page_config(
    page_title="Airline Customer Service Bot",
    page_icon="✈️",
    layout="wide"
)

# Custom CSS for chat-like interface
st.markdown("""
<style>
    /* Hide default Streamlit elements for cleaner UI */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Chat container */
    .chat-container {
        height: 500px;
        overflow-y: auto;
        padding: 20px;
        background-color: #f8f9fa;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    
    /* Message styles */
    .chat-message {
        padding: 12px 16px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 75%;
        word-wrap: break-word;
        animation: fadeIn 0.3s;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: auto;
        margin-right: 0;
        float: right;
        clear: both;
        box-shadow: 0 2px 5px rgba(102, 126, 234, 0.3);
    }
    
    .bot-message {
        background-color: white;
        color: #2d3748;
        margin-right: auto;
        margin-left: 0;
        float: left;
        clear: both;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    
    .message-row {
        display: flex;
        margin-bottom: 15px;
        clear: both;
    }
    
    .user-row {
        justify-content: flex-end;
    }
    
    .bot-row {
        justify-content: flex-start;
    }
    
    /* Avatar styles */
    .avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        margin: 0 10px;
        flex-shrink: 0;
    }
    
    .user-avatar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        order: 2;
    }
    
    .bot-avatar {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        order: 1;
    }
    
    /* Recommendation cards - ENHANCED */
    .recommendation-card {
        padding: 14px 16px;
        border-radius: 10px;
        background: linear-gradient(135deg, #e0f2ff 0%, #dbeafe 100%);
        margin: 10px 0;
        border-left: 4px solid #3b82f6;
        font-size: 14px;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
    }
    
    .recommendation-card:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 8px rgba(59, 130, 246, 0.2);
    }
    
    .recommendation-type {
        font-size: 11px;
        color: #3b82f6;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    
    .recommendation-content {
        color: #1e40af;
        font-size: 13px;
        line-height: 1.5;
    }
    
    .recommendation-price {
        color: #059669;
        font-weight: 600;
        margin-top: 4px;
        font-size: 13px;
    }
    
    /* Quick action buttons */
    .stButton>button {
        border-radius: 20px;
        border: 2px solid #667eea;
        background-color: white;
        color: #667eea;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #667eea;
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }
    
    /* Input area */
    .stTextInput>div>div>input {
        border-radius: 25px;
        border: 2px solid #e2e8f0;
        padding: 12px 20px;
    }
    
    .stTextInput>div>div>input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Metadata badge */
    .metadata-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        margin: 4px 2px;
        background-color: #edf2f7;
        color: #4a5568;
    }
    
    /* Timestamp */
    .timestamp {
        font-size: 11px;
        color: #a0aec0;
        margin-top: 4px;
    }
    
    /* Clear floats */
    .clearfix::after {
        content: "";
        display: table;
        clear: both;
    }
    
    /* Recommendations section header */
    .recommendations-header {
        font-size: 13px;
        font-weight: 600;
        color: #3b82f6;
        margin: 12px 0 8px 0;
        display: flex;
        align-items: center;
        gap: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("✈️ Airline Assistant")
    st.markdown("---")
    
    # User selection
    st.subheader("👤 User Profile")
    user_options = ["user123", "user456", "new_user"]
    st.session_state.user_id = st.selectbox(
        "Select User",
        user_options,
        index=0
    )
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Navigate",
        ["💬 Chat", "📋 My Bookings", "📊 Analytics"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.input_key += 1
        st.rerun()
    
    with st.expander("💡 Sample Commands"):
        st.markdown("""
        **Try these:**
        - Check my booking BK001
        - Cancel booking BK002
        - What's your cancellation policy?
        - Tell me about baggage rules
        - Show me my bookings
        - Change my flight
        - Upgrade my seat
        """)
    
    st.markdown("---")
    st.caption(f"Session: {st.session_state.session_id[:8]}...")

# Main content area
if page == "💬 Chat":
    st.title("💬 Customer Service Chat")
    
    # Chat display area
    chat_container = st.container()
    
    with chat_container:
        if len(st.session_state.messages) == 0:
            # Welcome message
            st.markdown("""
            <div style="text-align: center; padding: 40px; color: #718096;">
                <h2>👋 Welcome to Airline Customer Service!</h2>
                <p>I'm here to help with your bookings, cancellations, policy questions, and more.</p>
                <p style="margin-top: 20px; font-size: 14px;">💡 Try a quick action below or type your question!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Display chat messages
            for idx, msg in enumerate(st.session_state.messages):
                timestamp = datetime.now().strftime("%I:%M %p")
                
                if msg['role'] == 'user':
                    st.markdown(f"""
                    <div class="message-row user-row">
                        <div class="chat-message user-message">
                            {msg['content']}
                            <div class="timestamp">{timestamp}</div>
                        </div>
                        <div class="avatar user-avatar">👤</div>
                    </div>
                    <div class="clearfix"></div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="message-row bot-row">
                        <div class="avatar bot-avatar">🤖</div>
                        <div class="chat-message bot-message">
                            {msg['content']}
                            <div class="timestamp">{timestamp}</div>
                        </div>
                    </div>
                    <div class="clearfix"></div>
                    """, unsafe_allow_html=True)
                    
                    # Show recommendations - IMPROVED DISPLAY
                    if 'recommendations' in msg and msg['recommendations']:
                        st.markdown("""
                        <div class="recommendations-header">
                            💡 Recommendations for you:
                        </div>
                        """, unsafe_allow_html=True)
                        
                        for rec_idx, rec in enumerate(msg['recommendations']):
                            rec_type = rec.get('type', 'info')
                            
                            # Build recommendation card content
                            rec_html = '<div class="recommendation-card">'
                            
                            # Add type label
                            if rec_type:
                                type_label = rec_type.replace('_', ' ').title()
                                rec_html += f'<div class="recommendation-type">🏷️ {type_label}</div>'
                            
                            # Add main content based on type
                            if rec_type == 'policy':
                                policy_name = rec.get('policy_name', 'Policy')
                                content = rec.get('content', '')
                                rec_html += f'<div class="recommendation-content"><strong>{policy_name}</strong><br>{content}</div>'
                            
                            elif rec_type == 'seat_upgrade':
                                description = rec.get('description', '')
                                rec_html += f'<div class="recommendation-content">✈️ {description}</div>'
                            
                            elif rec_type == 'additional_service':
                                service = rec.get('service', '')
                                price = rec.get('price', 0)
                                description = rec.get('description', '')
                                rec_html += f'<div class="recommendation-content">➕ {description if description else service}</div>'
                                if price:
                                    rec_html += f'<div class="recommendation-price">💵 ${price}</div>'
                            
                            else:
                                # Generic recommendation display
                                description = rec.get('description') or rec.get('content') or rec.get('service') or str(rec)
                                rec_html += f'<div class="recommendation-content">{description}</div>'
                            
                            rec_html += '</div>'
                            
                            st.markdown(rec_html, unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Show metadata in expandable section
                    if 'metadata' in msg:
                        with st.expander("ℹ️ Details", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                intent = msg['metadata'].get('intent', 'N/A')
                                st.markdown(f"**Intent:** `{intent}`")
                            with col2:
                                confidence = msg['metadata'].get('confidence', 0)
                                st.markdown(f"**Confidence:** `{confidence:.1%}`")
    
    # Input area at the bottom
    st.markdown("---")
    
    # Quick suggestion buttons
    st.markdown("**💡 Quick Suggestions:**")
    col1, col2, col3, col4 = st.columns(4)
    
    quick_action_selected = None
    
    with col1:
        if st.button("📋 Check Status", key="quick_check"):
            quick_action_selected = "Check my booking status"
    
    with col2:
        if st.button("❌ Cancel", key="quick_cancel"):
            quick_action_selected = "I want to cancel a booking"
    
    with col3:
        if st.button("📜 Policies", key="quick_policy"):
            quick_action_selected = "What's your cancellation policy?"
    
    with col4:
        if st.button("💼 Baggage", key="quick_baggage"):
            quick_action_selected = "Tell me about baggage allowance"
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Text input with send button
    col1, col2 = st.columns([6, 1])
    
    with col1:
        user_input = st.text_input(
            "Message",
            key=f"user_input_{st.session_state.input_key}",
            label_visibility="collapsed",
            placeholder="Type your message here... (e.g., 'Check booking BK001')"
        )
    
    with col2:
        send_clicked = st.button("Send 📤", type="primary", use_container_width=True)
    
    # Handle message sending
    message_to_send = None
    
    if quick_action_selected:
        message_to_send = quick_action_selected
    elif send_clicked and user_input and user_input.strip():
        message_to_send = user_input.strip()
    
    if message_to_send:
        # Add user message
        st.session_state.messages.append({
            'role': 'user',
            'content': message_to_send
        })
        
        # Get bot response
        with st.spinner('🤖 Thinking...'):
            result = send_message(message_to_send)
            
            # Add bot response
            st.session_state.messages.append({
                'role': 'bot',
                'content': result['response'],
                'metadata': {
                    'intent': result['intent'],
                    'confidence': result['confidence']
                },
                'recommendations': result.get('recommendations', [])
            })
        
        # Clear input by incrementing key
        st.session_state.input_key += 1
        st.rerun()
    
    # Feedback section (only show if there are messages)
    if len(st.session_state.messages) >= 2:
        st.markdown("---")
        with st.expander("📝 Rate Your Experience"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                rating = st.slider(
                    "How satisfied are you?",
                    min_value=1,
                    max_value=5,
                    value=5,
                    help="1 = Poor, 5 = Excellent"
                )
            
            with col2:
                if st.button("Submit", key="feedback_submit", use_container_width=True):
                    if submit_feedback(rating):
                        st.success("✅ Thanks for your feedback!")

elif page == "📋 My Bookings":
    st.title("📋 My Bookings")
    
    bookings = get_bookings()
    
    if not bookings:
        st.info("📭 You don't have any bookings yet.")
        st.markdown("**Want to book a flight?** Head to the chat and say *'I want to book a flight'*!")
    else:
        st.success(f"Found {len(bookings)} booking(s)")
        
        for booking in bookings:
            status_color = "🟢" if booking['status'] == 'confirmed' else "🔴"
            
            with st.expander(
                f"{status_color} {booking['booking_id']} - Flight {booking['flight_number']} "
                f"({booking['status'].upper()})",
                expanded=False
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**✈️ Flight:** {booking['flight_number']}")
                    st.markdown(f"**👤 Passenger:** {booking['passenger_name']}")
                    st.markdown(f"**📅 Date:** {booking['departure_date']}")
                
                with col2:
                    st.markdown(f"**🛫 Route:** {booking['origin']} → {booking['destination']}")
                    st.markdown(f"**💺 Seat:** {booking['seat_number']}")
                    st.markdown(f"**📊 Status:** {booking['status'].upper()}")
                
                st.markdown("---")
                st.markdown("**Quick Actions:**")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔍 Check Details", key=f"details_{booking['booking_id']}"):
                        st.info(f"💬 Go to chat and say: 'Check booking {booking['booking_id']}'")
                
                with col2:
                    if booking['status'] == 'confirmed':
                        if st.button("❌ Cancel", key=f"cancel_{booking['booking_id']}"):
                            st.warning(f"💬 Go to chat and say: 'Cancel booking {booking['booking_id']}'")
                
                with col3:
                    if st.button("✏️ Modify", key=f"modify_{booking['booking_id']}"):
                        st.info(f"💬 Go to chat and say: 'Change flight {booking['booking_id']}'")

elif page == "📊 Analytics":
    st.title("📊 System Analytics")
    
    analytics = get_analytics()
    
    if analytics:
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📨 Total Messages", analytics.get('total_messages', 0))
        
        with col2:
            st.metric("💬 Total Sessions", analytics.get('total_sessions', 0))
        
        with col3:
            avg_conf = analytics.get('average_confidence', 0)
            st.metric("🎯 Avg Confidence", f"{avg_conf:.1%}")
        
        with col4:
            feedback_stats = analytics.get('feedback_stats', {})
            total_feedback = feedback_stats.get('total_feedback', 0)
            st.metric("⭐ Total Feedback", total_feedback)
        
        st.markdown("---")
        
        # Intent distribution
        st.subheader("📊 Intent Distribution")
        intent_dist = analytics.get('intent_distribution', {})
        
        if intent_dist:
            import pandas as pd
            df = pd.DataFrame(
                list(intent_dist.items()),
                columns=['Intent', 'Count']
            ).sort_values('Count', ascending=False)
            
            st.bar_chart(df.set_index('Intent'))
            
            # Show top intents
            st.markdown("**Top 3 Intents:**")
            for idx, row in df.head(3).iterrows():
                st.markdown(f"- **{row['Intent']}**: {row['Count']} messages")
        else:
            st.info("🔭 No intent data available yet. Start chatting to see analytics!")
        
        # Feedback stats
        if total_feedback > 0:
            st.markdown("---")
            st.subheader("⭐ Feedback Statistics")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_rating = feedback_stats.get('avg_rating', 0)
                st.metric("Average Rating", f"⭐ {avg_rating:.2f}/5")
            
            with col2:
                positive = feedback_stats.get('positive_feedback', 0)
                st.metric("Positive Feedback", f"👍 {positive}")
            
            with col3:
                if total_feedback > 0:
                    satisfaction = (positive / total_feedback) * 100
                    st.metric("Satisfaction Rate", f"😊 {satisfaction:.1f}%")
    else:
        st.warning("⚠️ Unable to load analytics data. Make sure the backend is running!")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #a0aec0; font-size: 12px; padding: 20px;'>"
    "✈️ Airline Customer Service Bot | Powered by FastAPI + Streamlit + Machine Learning<br>"
    "Made with ❤️ for seamless customer support"
    "</div>",
    unsafe_allow_html=True
)