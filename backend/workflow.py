import sqlite3
import json
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from airline_api import get_airline_api
from recommendations import get_recommendation_engine
from cache import get_cache

DATABASE_PATH = Path(__file__).parent / "airline_bot.db"

class WorkflowEngine:
    """Manages stateful workflows for multi-step conversations"""
    
    def __init__(self):
        self.airline_api = get_airline_api()
        self.rec_engine = get_recommendation_engine()
        self.cache = get_cache()
    
    def validate_date(self, date_str: str) -> tuple[bool, str]:
        """Comprehensive date validation"""
        from datetime import datetime as dt, timedelta
        
        try:
            # Parse the date
            date_obj = dt.strptime(date_str, '%Y-%m-%d')
            
            # Check if date is in the future
            today = dt.now().date()
            if date_obj.date() <= today:
                return False, (
                    f"⚠️ The date {date_str} is in the past!\n\n"
                    f"Today is {today.strftime('%Y-%m-%d')}. Please provide a future date."
                )
            
            # Check if date is too far in future (more than 1 year)
            max_future = today + timedelta(days=365)
            if date_obj.date() > max_future:
                return False, (
                    f"⚠️ The date {date_str} is too far in the future!\n\n"
                    f"We can only book flights up to {max_future.strftime('%Y-%m-%d')}."
                )
            
            return True, ""
            
        except ValueError:
            # Check for specific invalid date issues
            try:
                parts = date_str.split('-')
                if len(parts) != 3:
                    return False, "⚠️ Invalid date format! Use YYYY-MM-DD (e.g., 2025-12-25)."
                
                year_str, month_str, day_str = parts
                year, month, day = int(year_str), int(month_str), int(day_str)
                
                # Check year
                if year < 2025 or year > 2100:
                    return False, f"⚠️ Invalid year: {year}\nUse a year between 2025-2100."
                
                # Check month
                if month < 1 or month > 12:
                    return False, f"⚠️ Invalid month: {month}\nMonth must be 01-12."
                
                # Days in each month
                days_in_month = {
                    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
                    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
                }
                
                month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                
                max_days = days_in_month.get(month, 31)
                if day < 1 or day > max_days:
                    return False, (
                        f"⚠️ Invalid day: {day} for {month_names[month]}\n\n"
                        f"{month_names[month]} has only {max_days} days!"
                    )
                
                # Leap year check for Feb 29
                if month == 2 and day == 29:
                    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                    if not is_leap:
                        return False, f"⚠️ {year} is not a leap year!\nFeb {year} has only 28 days."
                
            except (ValueError, IndexError):
                pass
            
            return False, "⚠️ Invalid date! Use YYYY-MM-DD (e.g., 2025-12-25)."
    
    def validate_passenger_name(self, name: str) -> tuple[bool, str]:
        """Validate passenger name"""
        if not name or len(name.strip()) == 0:
            return False, "⚠️ Passenger name is required!"
        
        name = name.strip()
        
        if len(name) < 2:
            return False, "⚠️ Name too short! Please provide a valid name."
        
        if len(name) > 50:
            return False, "⚠️ Name too long! Max 50 characters."
        
        # Check valid characters
        import re
        if not re.match(r"^[A-Za-z\s\-']+$", name):
            return False, "⚠️ Invalid name! Use only letters, spaces, hyphens, apostrophes."
        
        return True, ""
    
    def validate_airport_code(self, code: str, field_name: str = "Airport") -> tuple[bool, str]:
        """Validate airport code"""
        if not code or len(code.strip()) == 0:
            return False, f"⚠️ {field_name} is required!"
        
        code = code.upper().strip()
        
        if len(code) < 2 or len(code) > 3:
            return False, f"⚠️ Invalid {field_name.lower()}: {code}\nUse 2-3 letter codes."
        
        if not code.isalpha():
            return False, f"⚠️ Invalid {field_name.lower()}: {code}\nUse only letters."
        
        return True, ""
    
    def get_workflow_state(self, session_id: str, user_id: str) -> Optional[Dict]:
        """Get active workflow state for a session"""
        # Check cache first
        cache_key = f"workflow:{session_id}"
        cached_state = self.cache.get(cache_key)
        if cached_state:
            return cached_state
        
        # Check database
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM workflow_states 
        WHERE session_id = ? AND user_id = ? AND status = 'active'
        ORDER BY updated_at DESC LIMIT 1
        """, (session_id, user_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            state = dict(row)
            state['state_data'] = json.loads(state['state_data']) if state['state_data'] else {}
            # Cache it
            self.cache.set(cache_key, state, ttl_seconds=600)
            return state
        
        return None
    
    def save_workflow_state(self, workflow_id: str, session_id: str, 
                           user_id: str, workflow_type: str, 
                           current_step: str, state_data: Dict, 
                           status: str = 'active'):
        """Save workflow state to database"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT OR REPLACE INTO workflow_states 
        (workflow_id, user_id, session_id, workflow_type, 
         current_step, state_data, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            workflow_id,
            user_id,
            session_id,
            workflow_type,
            current_step,
            json.dumps(state_data),
            status
        ))
        
        conn.commit()
        conn.close()
        
        # Update cache
        cache_key = f"workflow:{session_id}"
        self.cache.set(cache_key, {
            'workflow_id': workflow_id,
            'user_id': user_id,
            'session_id': session_id,
            'workflow_type': workflow_type,
            'current_step': current_step,
            'state_data': state_data,
            'status': status
        }, ttl_seconds=600)
    
    def complete_workflow(self, workflow_id: str, session_id: str):
        """Mark workflow as completed and clear cache"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE workflow_states 
        SET status = 'completed', updated_at = CURRENT_TIMESTAMP
        WHERE workflow_id = ?
        """, (workflow_id,))
        
        conn.commit()
        conn.close()
        
        # Clear cache
        cache_key = f"workflow:{session_id}"
        self.cache.delete(cache_key)
    
    def process_booking_check(self, nlu_result: Dict, user_id: str, 
                             session_id: str) -> Dict:
        """Process booking status check workflow"""
        entities = nlu_result.get('entities', {})
        booking_id = entities.get('booking_id')
        
        # Check for existing workflow
        workflow = self.get_workflow_state(session_id, user_id)
        
        # If in another workflow and user provides new booking ID, auto-switch
        if workflow and workflow.get('workflow_type') != 'check_status' and booking_id:
            self.complete_workflow(workflow['workflow_id'], session_id)
            workflow = None
        
        if not booking_id:
            # No booking ID provided, show all bookings
            bookings = self.airline_api.get_user_bookings(user_id)
            
            if not bookings:
                return {
                    'response': "I don't see any active bookings for you. Would you like to book a new flight? Just let me know your departure city, destination, and preferred date!",
                    'recommendations': []
                }
            
            if len(bookings) == 1:
                # Only one booking, show it directly
                booking = bookings[0]
                
                # Create workflow for follow-up actions
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='check_status',
                    current_step='showing_details',
                    state_data={'booking_id': booking['booking_id']}
                )
                
                return {
                    'response': (
                        f"Here's your booking:\n\n"
                        f"🎫 **Booking {booking['booking_id']}**\n"
                        f"✈️ Flight: {booking['flight_number']}\n"
                        f"👤 Passenger: {booking['passenger_name']}\n"
                        f"📅 Date: {booking['departure_date']}\n"
                        f"🛫 Route: {booking['origin']} → {booking['destination']}\n"
                        f"💺 Seat: {booking['seat_number']}\n"
                        f"📊 Status: {booking['status'].upper()}\n\n"
                        f"Would you like to:\n"
                        f"• Cancel this booking?\n"
                        f"• Change your flight date?\n"
                        f"• Upgrade your seat?\n"
                        f"• Or is everything looking good?"
                    ),
                    'recommendations': self.rec_engine.get_recommendations('check_status', booking)
                }
            
            # Multiple bookings - list them
            booking_list = []
            for b in bookings:
                booking_list.append(
                    f"🎫 **{b['booking_id']}** - Flight {b['flight_number']} "
                    f"({b['origin']} → {b['destination']}) on {b['departure_date']}"
                )
            
            return {
                'response': (
                    f"You have {len(bookings)} active bookings:\n\n" + 
                    "\n".join(booking_list) + 
                    "\n\nWhich one would you like to check? Just tell me the booking ID, or I can help you with something else!"
                ),
                'recommendations': []
            }
        
        # Specific booking requested
        booking = self.airline_api.get_booking(booking_id, user_id)
        
        if not booking:
            # Check if user has any bookings
            user_bookings = self.airline_api.get_user_bookings(user_id)
            if not user_bookings:
                return {
                    'response': (
                        f"⚠️ I couldn't find booking {booking_id}.\n\n"
                        f"You don't have any bookings in our system yet. "
                        f"Would you like to book a new flight?"
                    ),
                    'recommendations': [{'text': 'Book a flight', 'type': 'book_flight'}]
                }
            else:
                return {
                    'response': (
                        f"⚠️ I couldn't find booking {booking_id} under your account.\n\n"
                        f"This booking ID either doesn't exist or doesn't belong to you. "
                        f"Would you like me to show your bookings?"
                    ),
                    'recommendations': [{'text': 'Show my bookings', 'type': 'check_status'}]
                }
        
        # Create workflow for follow-up actions
        workflow_id = str(uuid.uuid4())
        self.save_workflow_state(
            workflow_id=workflow_id,
            session_id=session_id,
            user_id=user_id,
            workflow_type='check_status',
            current_step='showing_details',
            state_data={'booking_id': booking_id}
        )
        
        response = (
            f"Here are the details for **{booking_id}**:\n\n"
            f"✈️ Flight: {booking['flight_number']}\n"
            f"👤 Passenger: {booking['passenger_name']}\n"
            f"📅 Date: {booking['departure_date']}\n"
            f"🛫 Route: {booking['origin']} → {booking['destination']}\n"
            f"💺 Seat: {booking['seat_number']}\n"
            f"📊 Status: {booking['status'].upper()}\n\n"
            f"What would you like to do?\n"
            f"• Cancel this booking?\n"
            f"• Change the flight date?\n"
            f"• Upgrade your seat?\n"
            f"• Check baggage allowance?"
        )
        
        recommendations = self.rec_engine.get_recommendations('check_status', booking)
        
        return {
            'response': response,
            'recommendations': recommendations
        }
    
    def process_cancellation(self, nlu_result: Dict, user_id: str, 
                           session_id: str) -> Dict:
        """Process booking cancellation workflow"""
        entities = nlu_result.get('entities', {})
        booking_id = entities.get('booking_id')
        message = nlu_result.get('original_message', '').lower()
        
        # Check for existing workflow
        workflow = self.get_workflow_state(session_id, user_id)
        
        if not workflow or workflow.get('workflow_type') != 'cancel_booking':
            # Start new cancellation workflow
            if not booking_id:
                # No booking ID provided - create workflow waiting for ID
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='cancel_booking',
                    current_step='waiting_for_id',
                    state_data={}
                )
                
                return {
                    'response': "I can help you cancel your booking. Which booking would you like to cancel? Please provide your booking ID (e.g., BK001), or I can show you all your bookings if you'd like!",
                    'recommendations': []
                }
            
            # Booking ID provided immediately - get details and ask for confirmation
            booking = self.airline_api.get_booking(booking_id, user_id)
            if not booking:
                return {
                    'response': f"I couldn't find booking {booking_id}. Could you check the booking ID again? Or type 'show my bookings' to see all your reservations.",
                    'recommendations': []
                }
            
            # Create workflow at confirmation step
            workflow_id = str(uuid.uuid4())
            self.save_workflow_state(
                workflow_id=workflow_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type='cancel_booking',
                current_step='confirm',
                state_data={'booking_id': booking_id}
            )
            
            # Get cancellation policy
            policies = self.rec_engine.get_policy_recommendations('cancel_booking')
            policy_text = policies[0]['content'] if policies else "Standard cancellation fees may apply."
            
            return {
                'response': (
                    f"I found your booking:\n\n"
                    f"✈️ Flight {booking['flight_number']} on {booking['departure_date']}\n"
                    f"🛫 Route: {booking['origin']} → {booking['destination']}\n"
                    f"💺 Seat: {booking['seat_number']}\n\n"
                    f"📋 **Cancellation Policy**: {policy_text}\n\n"
                    f"Are you sure you want to cancel? Reply **'yes'** to confirm or **'no'** if you'd like to keep it. "
                    f"You can also ask me about changing the flight instead!"
                ),
                'recommendations': []
            }
        
        # Continue existing workflow
        state_data = workflow.get('state_data', {})
        current_step = workflow.get('current_step')
        
        # Step 1: Waiting for booking ID
        if current_step == 'waiting_for_id':
            # Check if user wants to see all bookings
            if 'show' in message or 'all' in message or 'list' in message:
                bookings = self.airline_api.get_user_bookings(user_id)
                if not bookings:
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return {
                        'response': "You don't have any active bookings. Would you like to book a new flight?",
                        'recommendations': []
                    }
                
                booking_list = []
                for b in bookings:
                    booking_list.append(
                        f"🎫 **{b['booking_id']}** - Flight {b['flight_number']} "
                        f"({b['origin']} → {b['destination']}) on {b['departure_date']}"
                    )
                
                return {
                    'response': (
                        "Here are your bookings:\n\n" + 
                        "\n".join(booking_list) + 
                        "\n\nWhich one would you like to cancel? Just tell me the booking ID."
                    ),
                    'recommendations': []
                }
            
            if booking_id:
                booking = self.airline_api.get_booking(booking_id, user_id)
                if not booking:
                    return {
                        'response': f"I couldn't find booking {booking_id}. Could you please double-check the booking ID? Or type 'show all' to see your bookings.",
                        'recommendations': []
                    }
                
                # Update workflow to confirmation step
                self.save_workflow_state(
                    workflow_id=workflow['workflow_id'],
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='cancel_booking',
                    current_step='confirm',
                    state_data={'booking_id': booking_id}
                )
                
                # Get cancellation policy
                policies = self.rec_engine.get_policy_recommendations('cancel_booking')
                policy_text = policies[0]['content'] if policies else "Standard cancellation fees may apply."
                
                return {
                    'response': (
                        f"Got it! Here's your booking:\n\n"
                        f"✈️ Flight {booking['flight_number']} on {booking['departure_date']}\n"
                        f"🛫 Route: {booking['origin']} → {booking['destination']}\n"
                        f"💺 Seat: {booking['seat_number']}\n\n"
                        f"📋 **Cancellation Policy**: {policy_text}\n\n"
                        f"Are you sure you want to cancel? Reply **'yes'** to proceed or **'no'** to keep it. "
                        f"You can also ask about changing the flight date instead!"
                    ),
                    'recommendations': []
                }
            else:
                return {
                    'response': "I need your booking ID to proceed. Please provide it (e.g., BK001), or I can 'show all' your bookings if that helps!",
                    'recommendations': []
                }
        
        # Step 2: Waiting for confirmation
        if current_step == 'confirm':
            # Check if user wants to change instead
            if 'change' in message or 'modify' in message or 'reschedule' in message:
                booking_id = state_data.get('booking_id')
                
                # Switch to change flight workflow
                self.save_workflow_state(
                    workflow_id=workflow['workflow_id'],
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='change_flight',
                    current_step='waiting_for_new_date',
                    state_data={'booking_id': booking_id}
                )
                
                return {
                    'response': (
                        f"Great! Let's change your flight instead of canceling it. "
                        f"What's your preferred new date? Please provide it in YYYY-MM-DD format (e.g., 2025-12-01)."
                    ),
                    'recommendations': []
                }
            
            # Check for policy questions
            if 'policy' in message or 'fee' in message or 'refund' in message or 'cost' in message:
                policies = self.rec_engine.get_policy_recommendations('cancel_booking')
                policy_text = policies[0]['content'] if policies else "Standard cancellation fees may apply."
                return {
                    'response': (
                        f"📋 **Cancellation Policy**:\n{policy_text}\n\n"
                        f"Do you still want to proceed with cancellation? Reply 'yes' or 'no'."
                    ),
                    'recommendations': []
                }
            
            if 'yes' in message or 'confirm' in message or 'sure' in message or 'proceed' in message:
                booking_id = state_data.get('booking_id')
                result = self.airline_api.cancel_booking(booking_id)
                
                self.complete_workflow(workflow['workflow_id'], session_id)
                
                if result['success']:
                    return {
                        'response': (
                            f"✅ All done! Your booking {booking_id} has been cancelled successfully.\n\n"
                            f"💰 Refund amount: ${result.get('refund_amount', 0)}\n"
                            f"⏰ Your refund will be processed within 5-7 business days.\n\n"
                            f"You'll receive a confirmation email shortly. Is there anything else I can help you with? "
                            f"Maybe book a new flight or check other bookings?"
                        ),
                        'recommendations': []
                    }
                else:
                    return {
                        'response': (
                            f"❌ Oops! {result['message']}\n\n"
                            f"Would you like to try again, or can I help you with something else?"
                        ),
                        'recommendations': []
                    }
            
            elif 'no' in message or 'nevermind' in message or 'keep' in message or 'don\'t' in message or 'cancel' in message:
                self.complete_workflow(workflow['workflow_id'], session_id)
                return {
                    'response': (
                        "No problem! I've kept your booking active. 👍\n\n"
                        "Is there anything else I can help you with? Maybe:\n"
                        "• Change your flight date?\n"
                        "• Upgrade your seat?\n"
                        "• Check baggage allowance?"
                    ),
                    'recommendations': []
                }
            
            else:
                return {
                    'response': (
                        "I didn't quite catch that. To cancel the booking, reply **'yes'**. "
                        "To keep it, reply **'no'**. Or if you'd like to change the flight instead, just say 'change flight'!"
                    ),
                    'recommendations': []
                }
        
        # Fallback
        return {
            'response': "I'm not sure what happened. Let's start over. What would you like to do?",
            'recommendations': []
        }
    
    def process_change_flight(self, nlu_result: Dict, user_id: str, 
                            session_id: str) -> Dict:
        """Process flight change workflow"""
        entities = nlu_result.get('entities', {})
        booking_id = entities.get('booking_id')
        new_date = entities.get('date')
        message = nlu_result.get('original_message', '').lower()
        
        workflow = self.get_workflow_state(session_id, user_id)
        
        # If in different workflow and user provides booking ID, auto-switch
        if workflow and workflow.get('workflow_type') != 'change_flight' and booking_id:
            self.complete_workflow(workflow['workflow_id'], session_id)
            workflow = None
        
        if not workflow or workflow.get('workflow_type') != 'change_flight':
            # Start new change flight workflow
            if not booking_id:
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='change_flight',
                    current_step='waiting_for_id',
                    state_data={}
                )
                
                return {
                    'response': "I can help you change your flight! Which booking would you like to modify? Please provide your booking ID (e.g., BK001).",
                    'recommendations': []
                }
            
            # Booking ID provided
            booking = self.airline_api.get_booking(booking_id, user_id)
            if not booking:
                # Check if user has any bookings
                user_bookings = self.airline_api.get_user_bookings(user_id)
                if not user_bookings:
                    return {
                        'response': (
                            f"⚠️ I couldn't find booking {booking_id}.\n\n"
                            f"You don't have any bookings yet. Would you like to book a flight first?"
                        ),
                        'recommendations': [{'text': 'Book a flight', 'type': 'book_flight'}]
                    }
                else:
                    return {
                        'response': (
                            f"⚠️ I couldn't find booking {booking_id} under your account.\n\n"
                            f"Please check the booking ID or view your bookings to find the right one."
                        ),
                        'recommendations': [{'text': 'Show my bookings', 'type': 'check_status'}]
                    }
            
            workflow_id = str(uuid.uuid4())
            self.save_workflow_state(
                workflow_id=workflow_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type='change_flight',
                current_step='waiting_for_new_date',
                state_data={'booking_id': booking_id}
            )
            
            # Get change policy
            policies = self.rec_engine.get_policy_recommendations('change_flight')
            policy_text = policies[0]['content'] if policies else "Change fees apply based on ticket type."
            
            return {
                'response': (
                    f"Perfect! Your current booking:\n\n"
                    f"✈️ Flight {booking['flight_number']} on {booking['departure_date']}\n"
                    f"🛫 Route: {booking['origin']} → {booking['destination']}\n\n"
                    f"📋 **Change Policy**: {policy_text}\n\n"
                    f"What's your preferred new date? Please provide it in YYYY-MM-DD format (e.g., 2025-12-01)."
                ),
                'recommendations': []
            }
        
        # Continue existing workflow
        state_data = workflow.get('state_data', {})
        current_step = workflow.get('current_step')
        
        if current_step == 'waiting_for_id':
            if booking_id:
                booking = self.airline_api.get_booking(booking_id, user_id)
                if not booking:
                    return {
                        'response': f"I couldn't find booking {booking_id}. Could you double-check the booking ID?",
                        'recommendations': []
                    }
                
                self.save_workflow_state(
                    workflow_id=workflow['workflow_id'],
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='change_flight',
                    current_step='waiting_for_new_date',
                    state_data={'booking_id': booking_id}
                )
                
                policies = self.rec_engine.get_policy_recommendations('change_flight')
                policy_text = policies[0]['content'] if policies else "Change fees apply."
                
                return {
                    'response': (
                        f"Got it! Current booking:\n\n"
                        f"✈️ Flight {booking['flight_number']} on {booking['departure_date']}\n"
                        f"🛫 Route: {booking['origin']} → {booking['destination']}\n\n"
                        f"📋 {policy_text}\n\n"
                        f"What's your new preferred date? (Format: YYYY-MM-DD)"
                    ),
                    'recommendations': []
                }
            else:
                return {
                    'response': "I need your booking ID. Please provide it (e.g., BK001).",
                    'recommendations': []
                }
        
        if current_step == 'waiting_for_new_date':
            if new_date:
                # Use comprehensive date validation
                is_valid, error_msg = self.validate_date(new_date)
                if not is_valid:
                    return {
                        'response': error_msg,
                        'recommendations': []
                    }
                
                booking_id = state_data.get('booking_id')
                booking = self.airline_api.get_booking(booking_id, user_id)
                
                # Check if booking is cancelled
                if not booking or booking.get('status') == 'cancelled':
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return {
                        'response': (
                            f"⚠️ Booking {booking_id} has been cancelled and cannot be modified.\n\n"
                            f"Would you like to:\n"
                            f"• Check your other bookings?\n"
                            f"• Book a new flight?"
                        ),
                        'recommendations': []
                    }
                
                result = self.airline_api.change_flight(booking_id, booking['flight_number'], new_date)
                
                self.complete_workflow(workflow['workflow_id'], session_id)
                
                if result['success']:
                    return {
                        'response': (
                            f"✅ Perfect! Your flight has been changed!\n\n"
                            f"📋 Booking: {booking_id}\n"
                            f"✈️ Flight: {booking['flight_number']}\n"
                            f"📅 New date: {new_date}\n"
                            f"🛫 Route: {booking['origin']} → {booking['destination']}\n"
                            f"💵 Change fee: ${result.get('change_fee', 0)}\n\n"
                            f"You'll receive a confirmation email with your updated itinerary. "
                            f"Anything else I can help with?"
                        ),
                        'recommendations': []
                    }
                else:
                    return {
                        'response': f"❌ {result['message']}\n\nWould you like to try a different date?",
                        'recommendations': []
                    }
            else:
                return {
                    'response': (
                        f"I need the new date for your flight.\n\n"
                        f"📅 Please provide it in YYYY-MM-DD format\n"
                        f"Example: 2025-12-15\n\n"
                        f"💡 Make sure the date is in the future!"
                    ),
                    'recommendations': []
                }
        
        return {
            'response': "Something went wrong. Let's start over. What would you like to do?",
            'recommendations': []
        }
    
    def process_seat_upgrade(self, nlu_result: Dict, user_id: str, 
                           session_id: str) -> Dict:
        """Process seat upgrade workflow"""
        entities = nlu_result.get('entities', {})
        booking_id = entities.get('booking_id')
        message = nlu_result.get('original_message', '').lower()
        
        workflow = self.get_workflow_state(session_id, user_id)
        
        if not workflow or workflow.get('workflow_type') != 'seat_upgrade':
            if not booking_id:
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='seat_upgrade',
                    current_step='waiting_for_id',
                    state_data={}
                )
                
                return {
                    'response': "I can help you upgrade your seat! Which booking would you like to upgrade? Please provide your booking ID (e.g., BK001).",
                    'recommendations': []
                }
            
            booking = self.airline_api.get_booking(booking_id, user_id)
            if not booking:
                return {
                    'response': f"I couldn't find booking {booking_id}. Please check and try again.",
                    'recommendations': []
                }
            
            # Get available seats
            available_seats = self.airline_api.get_available_seats(booking['flight_number'])
            
            workflow_id = str(uuid.uuid4())
            self.save_workflow_state(
                workflow_id=workflow_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type='seat_upgrade',
                current_step='waiting_for_seat_choice',
                state_data={'booking_id': booking_id, 'available_seats': available_seats}
            )
            
            seat_list = ", ".join(available_seats) if available_seats else "None available"
            
            return {
                'response': (
                    f"Great! Your current seat is **{booking['seat_number']}**.\n\n"
                    f"Available seats for upgrade: {seat_list}\n\n"
                    f"Which seat would you like? Or ask me about the difference between Economy, Premium Economy, and Business Class!"
                ),
                'recommendations': self.rec_engine.get_seat_upgrade_recommendations(booking)
            }
        
        # Continue workflow
        state_data = workflow.get('state_data', {})
        current_step = workflow.get('current_step')
        
        if current_step == 'waiting_for_id':
            if booking_id:
                booking = self.airline_api.get_booking(booking_id, user_id)
                if not booking:
                    return {
                        'response': f"I couldn't find that booking. Could you check the ID?",
                        'recommendations': []
                    }
                
                available_seats = self.airline_api.get_available_seats(booking['flight_number'])
                
                self.save_workflow_state(
                    workflow_id=workflow['workflow_id'],
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='seat_upgrade',
                    current_step='waiting_for_seat_choice',
                    state_data={'booking_id': booking_id, 'available_seats': available_seats}
                )
                
                seat_list = ", ".join(available_seats) if available_seats else "None available"
                
                return {
                    'response': (
                        f"Current seat: **{booking['seat_number']}**\n\n"
                        f"Available: {seat_list}\n\n"
                        f"Which would you like?"
                    ),
                    'recommendations': []
                }
        
        if current_step == 'waiting_for_seat_choice':
            # Extract seat from message
            import re
            seat_pattern = r'\b(\d{1,2}[A-F])\b'
            seat_match = re.search(seat_pattern, message.upper())
            
            if seat_match:
                new_seat = seat_match.group(1)
                available_seats = state_data.get('available_seats', [])
                
                if new_seat not in available_seats:
                    return {
                        'response': f"Sorry, seat {new_seat} isn't available. Available seats are: {', '.join(available_seats)}. Which would you prefer?",
                        'recommendations': []
                    }
                
                booking_id = state_data.get('booking_id')
                result = self.airline_api.upgrade_seat(booking_id, new_seat)
                
                self.complete_workflow(workflow['workflow_id'], session_id)
                
                if result['success']:
                    return {
                        'response': (
                            f"✅ Awesome! Your seat has been upgraded to **{new_seat}**!\n\n"
                            f"💵 Upgrade cost: ${result.get('upgrade_cost', 0)}\n\n"
                            f"You're all set! Anything else I can help with?"
                        ),
                        'recommendations': []
                    }
                else:
                    return {
                        'response': f"❌ {result['message']}\n\nWould you like to try another seat?",
                        'recommendations': []
                    }
            else:
                return {
                    'response': "Please specify a seat number (e.g., 12A, 5C). Which seat would you like?",
                    'recommendations': []
                }
        
        return {
            'response': "Something went wrong. What would you like to do?",
            'recommendations': []
        }
    
    def handle_irrelevant_query(self, message: str) -> Dict:
        """Handle irrelevant or out-of-scope queries"""
        message_lower = message.lower()
        
        # Check for common irrelevant patterns
        irrelevant_patterns = [
            'weather', 'news', 'joke', 'story', 'recipe', 'game',
            'calculate', 'math', 'translate', 'define', 'wikipedia',
            'sports', 'movie', 'music', 'restaurant', 'hotel'
        ]
        
        is_irrelevant = any(pattern in message_lower for pattern in irrelevant_patterns)
        
        if is_irrelevant:
            return {
                'response': (
                    "I appreciate your question, but I'm specifically designed to help with airline services! 😊\n\n"
                    "I can help you with:\n"
                    "✈️ Booking and managing flights\n"
                    "🎫 Checking booking status\n"
                    "❌ Canceling or changing flights\n"
                    "💺 Seat upgrades\n"
                    "🧳 Baggage information\n"
                    "📋 Policy details\n\n"
                    "What can I help you with today regarding your flight?"
                ),
                'recommendations': []
            }
        
        return None
    
    def process_book_flight(self, nlu_result: Dict, user_id: str, 
                           session_id: str) -> Dict:
        """Process flight booking workflow"""
        entities = nlu_result.get('entities', {})
        message = nlu_result.get('original_message', '')
        
        # Check if user is asking a question instead of providing data
        message_lower = message.lower()
        question_indicators = [
            'is there', 'are there', 'do you', 'can i', 'can you',
            'what is', 'what are', 'how much', 'how many', 'tell me',
            'policy', 'allowed', 'special', 'children', 'infant', 'pet',
            'file', 'complaint', 'complain', 'damaged', 'missing', 'lost',
            'discount', 'deal', 'fare', 'price', 'schedule', 'insurance',
            'medical', 'prohibited', 'sport', 'music', 'instrument'
        ]
        
        # If this looks like a question, route to appropriate handler
        if any(indicator in message_lower for indicator in question_indicators):
            # Re-process the message with NLU to get the right intent
            from nlu import get_nlu_module
            nlu = get_nlu_module()
            new_result = nlu.process(message)
            
            # If it's an informational intent, handle it directly
            new_intent = new_result.get('intent')
            informational_intents = ['pet_travel', 'children_policy', 'baggage_info', 'cancellation_policy', 
                                    'general_faq', 'complaints', 'damaged_bag', 'missing_bag', 'discounts',
                                    'fare_check', 'flights_info', 'insurance', 'medical_policy', 
                                    'prohibited_items', 'sports_music_gear']
            
            if new_intent in informational_intents:
                # Route to appropriate handler
                handler_map = {
                    'children_policy': self.process_children_policy,
                    'pet_travel': self.process_pet_travel,
                    'baggage_info': self.process_baggage_info,
                    'cancellation_policy': self.process_cancellation_policy,
                    'complaints': self.process_complaints,
                    'damaged_bag': self.process_damaged_bag,
                    'missing_bag': self.process_missing_bag,
                    'discounts': self.process_discounts,
                    'fare_check': self.process_fare_check,
                    'flights_info': self.process_flights_info,
                    'insurance': self.process_insurance,
                    'medical_policy': self.process_medical_policy,
                    'prohibited_items': self.process_prohibited_items,
                    'sports_music_gear': self.process_sports_music_gear,
                    'general_faq': self.process_general_faq
                }
                handler = handler_map.get(new_intent)
                if handler:
                    return handler(new_result, user_id, session_id)
        
        workflow = self.get_workflow_state(session_id, user_id)
        
        # Start new booking workflow
        if not workflow or workflow.get('workflow_type') != 'book_flight':
            workflow_id = str(uuid.uuid4())
            self.save_workflow_state(
                workflow_id=workflow_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={}
            )
            
            return {
                'response': (
                    "Great! Let me help you book a new flight. ✈️\n\n"
                    "I'll need the following information:\n"
                    "📍 Departure city (e.g., JFK, LAX)\n"
                    "📍 Destination city (e.g., ORD, MIA)\n"
                    "📅 Travel date (YYYY-MM-DD format)\n"
                    "👤 Passenger name\n\n"
                    "You can provide them all at once or one at a time!"
                ),
                'recommendations': []
            }
        
        # Continue existing workflow
        state_data = workflow.get('state_data', {})
        current_step = workflow.get('current_step')
        
        # Extract information from message
        origin = entities.get('origin') or state_data.get('origin')
        destination = entities.get('destination') or state_data.get('destination')
        date = entities.get('date') or state_data.get('date')
        passenger_name = entities.get('passenger_name') or state_data.get('passenger_name')
        
        # Update state_data with any new information
        if origin:
            state_data['origin'] = origin
        if destination:
            state_data['destination'] = destination
        if date:
            state_data['date'] = date
        if passenger_name:
            state_data['passenger_name'] = passenger_name
        
        # Check what's still missing
        missing = []
        if not state_data.get('origin'):
            missing.append("departure city")
        if not state_data.get('destination'):
            missing.append("destination city")
        if not state_data.get('date'):
            missing.append("travel date")
        if not state_data.get('passenger_name'):
            missing.append("passenger name")
        
        if missing:
            # Save current state
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data=state_data
            )
            
            # Build response showing what we have and what we need
            response = "Thanks! "
            if state_data:
                response += "Here's what I have so far:\n"
                if state_data.get('origin'):
                    response += f"✅ From: {state_data['origin']}\n"
                if state_data.get('destination'):
                    response += f"✅ To: {state_data['destination']}\n"
                if state_data.get('date'):
                    response += f"✅ Date: {state_data['date']}\n"
                if state_data.get('passenger_name'):
                    response += f"✅ Passenger: {state_data['passenger_name']}\n"
                response += "\n"
            
            response += f"I still need: {', '.join(missing)}\n\n"
            response += "Please provide the missing information."
            
            return {
                'response': response,
                'recommendations': []
            }
        
        # All information collected - validate before creating booking
        
        # Validate date
        is_valid_date, date_error = self.validate_date(state_data['date'])
        if not is_valid_date:
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={**state_data, 'date': None}  # Clear invalid date
            )
            return {
                'response': date_error + "\n\nPlease provide a valid date.",
                'recommendations': []
            }
        
        # Validate passenger name
        is_valid_name, name_error = self.validate_passenger_name(state_data['passenger_name'])
        if not is_valid_name:
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={**state_data, 'passenger_name': None}  # Clear invalid name
            )
            return {
                'response': name_error + "\n\nPlease provide a valid passenger name.",
                'recommendations': []
            }
        
        # Validate origin
        is_valid_origin, origin_error = self.validate_airport_code(state_data['origin'], "Departure city")
        if not is_valid_origin:
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={**state_data, 'origin': None}
            )
            return {
                'response': origin_error + "\n\nPlease provide a valid departure city.",
                'recommendations': []
            }
        
        # Validate destination
        is_valid_dest, dest_error = self.validate_airport_code(state_data['destination'], "Destination city")
        if not is_valid_dest:
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={**state_data, 'destination': None}
            )
            return {
                'response': dest_error + "\n\nPlease provide a valid destination city.",
                'recommendations': []
            }
        
        # Check if origin and destination are the same
        if state_data['origin'].upper() == state_data['destination'].upper():
            self.save_workflow_state(
                workflow_id=workflow['workflow_id'],
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={**state_data, 'origin': None, 'destination': None}
            )
            return {
                'response': (
                    f"⚠️ Origin and destination cannot be the same!\n\n"
                    f"You selected {state_data['origin']} for both. "
                    f"Please provide different departure and destination cities."
                ),
                'recommendations': []
            }
        
        # Create booking
        booking_result = self.airline_api.create_booking({
            'user_id': user_id,
            'flight_number': 'AA999',  # Mock flight number
            'passenger_name': state_data['passenger_name'],
            'departure_date': state_data['date'],
            'origin': state_data['origin'],
            'destination': state_data['destination'],
            'seat_number': 'TBD'
        })
        
        self.complete_workflow(workflow['workflow_id'], session_id)
        
        if booking_result.get('success'):
            return {
                'response': (
                    f"✅ Perfect! Your flight has been booked!\n\n"
                    f"📋 Booking ID: {booking_result['booking_id']}\n"
                    f"✈️ Flight: AA999\n"
                    f"👤 Passenger: {state_data['passenger_name']}\n"
                    f"📅 Date: {state_data['date']}\n"
                    f"🛫 Route: {state_data['origin']} → {state_data['destination']}\n\n"
                    f"You'll receive a confirmation email shortly. "
                    f"Is there anything else I can help you with?"
                ),
                'recommendations': []
            }
        else:
            return {
                'response': (
                    f"❌ Sorry, there was an error creating your booking.\n\n"
                    f"Please try again or contact customer support."
                ),
                'recommendations': []
            }
    
    def process_children_policy(self, nlu_result: Dict, user_id: str, 
                               session_id: str) -> Dict:
        """Process children/infant seating policy questions"""
        children_policy = """
👶 **Children & Infant Seating Policy**

**Infants (Under 2 years):**
• 🆓 Can travel on parent's lap for free (domestic)
• 💺 May purchase a seat at child fare if preferred
• 🎫 Must have their own ticket
• ⚠️ Maximum 1 lap infant per adult
• 📝 Proof of age may be required

**Children (2-11 years):**
• 💺 Must have their own purchased seat
• 👨‍👩‍👧 No unaccompanied minor under age 5
• 🎯 Ages 5-14: Unaccompanied minor service available ($150)
• 🪑 No special seat requirements - regular seats

**Car Seats & Boosters:**
• ✅ FAA-approved car seats allowed for children under 40 lbs
• 💺 Must fit in aircraft seat (max 16" wide)
• 🔒 Must be properly secured
• 🆓 No extra charge if child has own seat

**Seating Together:**
• 👨‍👩‍👧‍👦 We try to seat families together
• 📞 Call to request adjacent seats
• 🎫 Select seats during booking for best choice

**Special Accommodations:**
• 🍼 Bottle warming available on request
• 🚼 Changing tables in lavatories
• 🎮 Kids entertainment available on most flights

Would you like to know anything else about traveling with children?
"""
        
        return {
            'response': children_policy,
            'recommendations': []
        }
    
    def process_complaints(self, nlu_result: Dict, user_id: str, 
                          session_id: str) -> Dict:
        """Process customer complaints"""
        return {
            'response': (
                "📝 **File a Complaint**\n\n"
                "I'm sorry to hear you had a negative experience. Your feedback is important to us.\n\n"
                "**To file a complaint, please provide:**\n"
                "• Your booking ID (if applicable)\n"
                "• Date and flight number\n"
                "• Description of the issue\n"
                "• What resolution you're seeking\n\n"
                "**Contact Options:**\n"
                "• 📞 Call: 1-800-JETBLUE (538-2583)\n"
                "• 📧 Email: customer.relations@jetblue.com\n"
                "• 💬 Online form: jetblue.com/contact-us\n\n"
                "We typically respond within 24-48 hours.\n\n"
                "Is there anything else I can help you with today?"
            ),
            'recommendations': []
        }
    
    def process_damaged_bag(self, nlu_result: Dict, user_id: str,
                           session_id: str) -> Dict:
        """Process damaged baggage claims"""
        return {
            'response': (
                "💼 **Damaged Baggage Claim**\n\n"
                "I'm sorry your baggage was damaged. Here's what to do:\n\n"
                "**Immediate Steps:**\n"
                "• 🚨 Report damage BEFORE leaving the airport\n"
                "• 📋 Go to the Baggage Service Office\n"
                "• 📸 Take photos of the damage\n"
                "• 🎫 Keep your baggage claim tag\n\n"
                "**Required Information:**\n"
                "• Booking ID or ticket number\n"
                "• Baggage claim tag number\n"
                "• Description of damage\n"
                "• Photos of damaged items\n\n"
                "**Claim Process:**\n"
                "• File within 24 hours for domestic, 7 days for international\n"
                "• We'll assess repair vs. replacement\n"
                "• Reimbursement up to $3,500 per passenger\n\n"
                "**Contact:**\n"
                "📞 Baggage Service: 1-866-538-5438\n\n"
                "Would you like help with anything else?"
            ),
            'recommendations': []
        }
    
    def process_missing_bag(self, nlu_result: Dict, user_id: str,
                           session_id: str) -> Dict:
        """Process missing/lost baggage reports"""
        return {
            'response': (
                "🧳 **Missing Baggage Report**\n\n"
                "I understand how stressful this is. Let's locate your bag:\n\n"
                "**Immediate Steps:**\n"
                "• 🚨 Report missing bag BEFORE leaving airport\n"
                "• 📋 File report at Baggage Service Office\n"
                "• 🎫 Provide your baggage claim tag\n"
                "• 📝 Get file reference number\n\n"
                "**We'll Need:**\n"
                "• Booking ID or ticket number\n"
                "• Baggage claim tag number\n"
                "• Bag description (color, brand, size)\n"
                "• Contents description\n"
                "• Delivery address\n\n"
                "**What Happens Next:**\n"
                "• 🔍 We search our system worldwide\n"
                "• 📱 Updates via text/email\n"
                "• 🚚 Free delivery once found (usually 24-48hrs)\n"
                "• 💵 Interim expense reimbursement available\n\n"
                "**Track Your Bag:**\n"
                "🌐 jetblue.com/travel/baggage-tracking\n"
                "📞 Baggage Services: 1-866-538-5438\n\n"
                "Anything else I can help with?"
            ),
            'recommendations': []
        }
    
    def process_discounts(self, nlu_result: Dict, user_id: str,
                         session_id: str) -> Dict:
        """Process discount and deals inquiries"""
        return {
            'response': (
                "💰 **Discounts & Deals**\n\n"
                "**Current Offers:**\n"
                "• ✈️ TrueBlue Members: Earn points on every flight\n"
                "• 🎫 Blue Basic: Our lowest fares\n"
                "• 📧 Email Alerts: Get deal notifications\n\n"
                "**Special Discounts:**\n"
                "• 🎖️ Military: 5% off for active duty & veterans\n"
                "• 👨‍✈️ First Responders: Special rates available\n"
                "• 👶 Infants: Free lap seating under 2 years\n"
                "• 🎓 Student: Check student universe for deals\n\n"
                "**How to Save:**\n"
                "• 📅 Book Tuesday-Thursday for best prices\n"
                "• 🗓️ Fly Tuesday, Wednesday, Saturday\n"
                "• 📆 Book 3-4 weeks in advance\n"
                "• 🔔 Set fare alerts on our website\n\n"
                "**Loyalty Program:**\n"
                "Join TrueBlue (free!):\n"
                "• Earn 3 points per $1 spent\n"
                "• Points never expire\n"
                "• No blackout dates\n"
                "• Family pooling available\n\n"
                "**Check Deals:**\n"
                "🌐 jetblue.com/deals\n\n"
                "Ready to book a flight?"
            ),
            'recommendations': [{'text': 'Book a flight', 'type': 'book_flight'}]
        }
    
    def process_fare_check(self, nlu_result: Dict, user_id: str,
                          session_id: str) -> Dict:
        """Process fare and price inquiries"""
        return {
            'response': (
                "💵 **Fare Information**\n\n"
                "**Fare Types:**\n\n"
                "**Blue Basic** (Economy Light)\n"
                "• Lowest price\n"
                "• 1 personal item only\n"
                "• No seat selection\n"
                "• Board last\n"
                "• No changes allowed\n\n"
                "**Blue** (Standard Economy)\n"
                "• 1 carry-on + 1 personal item\n"
                "• Free seat selection\n"
                "• Changes allowed (fee applies)\n"
                "• Earn full TrueBlue points\n\n"
                "**Blue Plus** (Economy with perks)\n"
                "• Everything in Blue, plus:\n"
                "• 1 free checked bag\n"
                "• Preferred seating\n"
                "• Early boarding\n"
                "• Bonus TrueBlue points\n\n"
                "**Blue Extra** (Extra Legroom)\n"
                "• 5+ inches extra legroom\n"
                "• Priority boarding\n"
                "• Fast track security (select airports)\n\n"
                "**Mint** (Business Class)\n"
                "• Lie-flat seats\n"
                "• 2 checked bags free\n"
                "• Gourmet meals\n"
                "• Priority everything\n\n"
                "**Get Exact Prices:**\n"
                "Fares vary by:\n"
                "• Route & distance\n"
                "• Date & time\n"
                "• Booking timing\n"
                "• Seat availability\n\n"
                "💡 **Tip:** Book early for best prices!\n\n"
                "Would you like to search for specific flights?"
            ),
            'recommendations': [{'text': 'Book a flight', 'type': 'book_flight'}]
        }
    
    def process_flights_info(self, nlu_result: Dict, user_id: str,
                            session_id: str) -> Dict:
        """Process flight schedule and information requests"""
        return {
            'response': (
                "✈️ **Flight Information**\n\n"
                "**JetBlue Route Network:**\n"
                "• 🇺🇸 100+ destinations in USA\n"
                "• 🌎 Caribbean & Latin America\n"
                "• 🗽 Major hubs: New York (JFK), Boston, Fort Lauderdale\n\n"
                "**Flight Features:**\n"
                "• 📺 Free entertainment on all flights\n"
                "• 🥤 Complimentary snacks & beverages\n"
                "• 📶 Wi-Fi available (fee applies)\n"
                "• 🔌 Power outlets at every seat\n\n"
                "**Check Flight Status:**\n"
                "• 🌐 jetblue.com/flight-status\n"
                "• 📱 JetBlue mobile app\n"
                "• 📞 Call: 1-800-JETBLUE\n\n"
                "**Typical Check-in Times:**\n"
                "• ⏰ Domestic: 2 hours before\n"
                "• 🌍 International: 3 hours before\n"
                "• 🚪 Boarding: 30-45 minutes before departure\n\n"
                "**Need Specific Info?**\n"
                "I can help you:\n"
                "• Check your booking status\n"
                "• Search available flights\n"
                "• Book a new flight\n\n"
                "What would you like to do?"
            ),
            'recommendations': [
                {'text': 'Check booking', 'type': 'check_status'},
                {'text': 'Book flight', 'type': 'book_flight'}
            ]
        }
    
    def process_insurance(self, nlu_result: Dict, user_id: str,
                         session_id: str) -> Dict:
        """Process travel insurance inquiries"""
        return {
            'response': (
                "🛡️ **Travel Insurance & Protection**\n\n"
                "**JetBlue Coverage Options:**\n\n"
                "**Trip Protection** ($29-89 per person)\n"
                "• ✅ Trip cancellation coverage\n"
                "• ✅ Trip interruption\n"
                "• ✅ Travel delays (6+ hours)\n"
                "• ✅ Baggage delay/loss\n"
                "• ✅ Emergency medical\n"
                "• ✅ 24/7 travel assistance\n\n"
                "**What's Covered:**\n"
                "• 🏥 Illness or injury\n"
                "• 🏠 Home emergency\n"
                "• 🌪️ Severe weather\n"
                "• ⚠️ Mandatory evacuations\n"
                "• 💼 Work-related obligations\n\n"
                "**When to Buy:**\n"
                "• 📅 Purchase within 24 hours of booking for full coverage\n"
                "• ⏰ Can add up to departure date (limited coverage)\n\n"
                "**JetBlue's Built-in Flexibility:**\n"
                "• 🔄 24-hour risk-free booking\n"
                "• ✈️ Flight changes allowed (fee may apply)\n"
                "• 💳 TrueBlue points bookings: Cancel anytime\n\n"
                "**Coverage Limits:**\n"
                "• Trip cost: Up to $10,000\n"
                "• Medical: Up to $50,000\n"
                "• Baggage: Up to $500\n\n"
                "**Purchase Insurance:**\n"
                "• During booking process\n"
                "• jetblue.com/insurance\n"
                "• Or manage trips section\n\n"
                "Would you like to book a flight?"
            ),
            'recommendations': [{'text': 'Book flight', 'type': 'book_flight'}]
        }
    
    def process_medical_policy(self, nlu_result: Dict, user_id: str,
                              session_id: str) -> Dict:
        """Process medical and health policy questions"""
        return {
            'response': (
                "🏥 **Medical & Health Policies**\n\n"
                "**Flying When Sick:**\n"
                "• 🤧 Mild cold/congestion: Generally OK\n"
                "• 🤒 Fever/infectious disease: Wait until recovered\n"
                "• 🏥 Recent surgery: Doctor's clearance needed\n"
                "• 🤰 Pregnancy: Can fly until 36 weeks\n\n"
                "**Medical Certificates Required:**\n"
                "• ✈️ Recent surgery (within 10 days)\n"
                "• 🏥 Serious medical condition\n"
                "• 🤰 Pregnancy after 36 weeks\n"
                "• 🧑‍⚕️ Traveling with medical equipment\n\n"
                "**Carrying Medications:**\n"
                "• ✅ Bring in original containers\n"
                "• 📝 Keep prescription label visible\n"
                "• 💊 Carry-on recommended (not checked)\n"
                "• 💉 Needles: Medical certificate helpful\n"
                "• 🧴 Liquids over 3.4oz: Medical exemption\n\n"
                "**Medical Equipment:**\n"
                "• 🦽 Wheelchairs: Free transport\n"
                "• 🧑‍🦯 Assistive devices: No charge\n"
                "• 💨 Portable oxygen: Advance notice required\n"
                "• 💉 Diabetes supplies: Allowed in carry-on\n\n"
                "**Oxygen & Respiratory:**\n"
                "• ✅ FAA-approved portable oxygen concentrators\n"
                "• ❌ Compressed gas cylinders not allowed\n"
                "• 📞 Call 48 hours ahead: 1-800-JETBLUE\n\n"
                "**Special Assistance:**\n"
                "Request when booking:\n"
                "• Wheelchair service\n"
                "• Priority boarding\n"
                "• Medical clearance\n"
                "• Seating accommodations\n\n"
                "**Need Help?**\n"
                "📞 Special Assistance: 1-800-538-2583\n"
                "🌐 jetblue.com/accessibility\n\n"
                "Anything else I can help with?"
            ),
            'recommendations': []
        }
    
    def process_prohibited_items(self, nlu_result: Dict, user_id: str,
                                session_id: str) -> Dict:
        """Process prohibited items questions"""
        return {
            'response': (
                "🚫 **Prohibited & Restricted Items**\n\n"
                "**Absolutely Prohibited (Carry-on & Checked):**\n"
                "• 💣 Explosives & fireworks\n"
                "• 🧨 Flammable liquids/gases\n"
                "• ☢️ Radioactive materials\n"
                "• ☠️ Toxic/poisonous substances\n"
                "• 🔫 Firearms (unless declared & unloaded)\n"
                "• 🔪 Large knives & weapons\n\n"
                "**Carry-On Restrictions:**\n"
                "❌ **NOT Allowed in Carry-On:**\n"
                "• Sharp objects over 4 inches\n"
                "• Baseball bats, golf clubs\n"
                "• Tools over 7 inches\n"
                "• Self-defense sprays\n"
                "• Liquids over 3.4oz (except medical)\n\n"
                "**✅ Allowed in Checked Bags ONLY:**\n"
                "• Tools & sporting equipment\n"
                "• Liquids over 3.4oz\n"
                "• Declared firearms (unloaded, locked)\n\n"
                "**Special Items:**\n"
                "• 🔋 Spare lithium batteries: Carry-on only\n"
                "• 💻 Laptops/tablets: Carry-on recommended\n"
                "• 🎮 Gaming devices: Allowed\n"
                "• 📱 Phone chargers: Allowed\n"
                "• 🪒 Razors: Disposable OK, straight razor NO\n\n"
                "**Liquid Rules (3-1-1):**\n"
                "• 3.4 ounces (100ml) per container\n"
                "• 1 quart-sized clear bag\n"
                "• 1 bag per passenger\n\n"
                "**Exceptions:**\n"
                "• Baby formula/food\n"
                "• Medications\n"
                "• Breast milk\n\n"
                "**Smart Luggage:**\n"
                "• 🔋 Battery must be removable\n"
                "• Remove battery for checked bags\n\n"
                "**When in Doubt:**\n"
                "📞 Call: 1-800-JETBLUE\n"
                "🌐 jetblue.com/prohibited-items\n"
                "🛂 Check TSA.gov for complete list\n\n"
                "Need help with anything else?"
            ),
            'recommendations': []
        }
    
    def process_sports_music_gear(self, nlu_result: Dict, user_id: str,
                                 session_id: str) -> Dict:
        """Process sports equipment and musical instruments questions"""
        return {
            'response': (
                "🎸 **Sports Equipment & Musical Instruments**\n\n"
                "**Musical Instruments:**\n\n"
                "**Small Instruments (Carry-On):**\n"
                "• 🎸 Guitar, violin, trumpet (if fits overhead)\n"
                "• 📏 Max: 22\" x 14\" x 9\"\n"
                "• 🎫 Counts as your carry-on item\n"
                "• 💺 Can buy seat for larger instruments\n\n"
                "**Large Instruments (Checked):**\n"
                "• 🎹 Keyboard, cello, etc.\n"
                "• 💵 Fee: $150 each way\n"
                "• 📦 Must be in hard case\n"
                "• 📏 Size limits apply\n\n"
                "**Sports Equipment:**\n\n"
                "**Checked Sports Gear ($50-75 each):**\n"
                "• ⛳ Golf clubs (1 bag)\n"
                "• 🎿 Skis & snowboards (1 set)\n"
                "• 🏄 Surfboards (under 100 linear inches)\n"
                "• 🚴 Bicycles (in box/bag)\n"
                "• 🏒 Hockey equipment\n"
                "• 🏊 Diving equipment\n\n"
                "**Special Handling:**\n"
                "• ⛳ Golf: Soft/hard case, clubs secured\n"
                "• 🎿 Ski: Max 2 pairs per bag\n"
                "• 🚴 Bike: Pedals removed, handlebars turned\n"
                "• 🏄 Surfboard: Wrapped and padded\n\n"
                "**Size & Weight:**\n"
                "• 📏 Max 80 linear inches (L+W+H)\n"
                "• ⚖️ Max 50 lbs (additional fees if heavier)\n"
                "• 📦 Must be properly packaged\n\n"
                "**Fees (One Way):**\n"
                "• 🎸 Small instrument carry-on: Free\n"
                "• 🎹 Large instrument checked: $150\n"
                "• ⛳ Sports equipment (1st): $50\n"
                "• ⛳ Sports equipment (2nd): $75\n\n"
                "**Book Equipment Transport:**\n"
                "• 📞 Call when booking: 1-800-JETBLUE\n"
                "• 🌐 Or add during online check-in\n"
                "• ⏰ At least 48 hours advance notice\n\n"
                "**Protection Tips:**\n"
                "• 📦 Use hard cases when possible\n"
                "• 🏷️ Label with name & phone\n"
                "• 📸 Take photos before checking\n"
                "• 💼 Consider travel insurance\n\n"
                "Need help booking a flight?"
            ),
            'recommendations': [{'text': 'Book flight', 'type': 'book_flight'}]
        }
    
    def process_general_faq(self, nlu_result: Dict, user_id: str, 
                           session_id: str) -> Dict:
        """Process general FAQ questions"""
        message = nlu_result.get('original_message', '').lower()
        
        # Try to determine which FAQ they're asking about
        if any(word in message for word in ['seat', 'sitting']):
            return self.process_children_policy(nlu_result, user_id, session_id)
        elif any(word in message for word in ['pet', 'animal']):
            return self.process_pet_travel(nlu_result, user_id, session_id)
        elif any(word in message for word in ['bag', 'luggage']):
            return self.process_baggage_info(nlu_result, user_id, session_id)
        else:
            # General response
            return {
                'response': (
                    "I can help you with information about:\n\n"
                    "✈️ **Flight Operations:**\n"
                    "• Check booking status\n"
                    "• Change or cancel flights\n"
                    "• Seat upgrades\n\n"
                    "📋 **Policies:**\n"
                    "• Pet travel\n"
                    "• Baggage allowance\n"
                    "• Cancellation policy\n"
                    "• Children & infant seating\n\n"
                    "🎫 **Bookings:**\n"
                    "• Book new flights\n"
                    "• Modify existing bookings\n\n"
                    "What would you like to know more about?"
                ),
                'recommendations': []
            }
    
    def process_pet_travel(self, nlu_result: Dict, user_id: str, 
                          session_id: str) -> Dict:
        """Process pet travel policy requests"""
        # JetBlue Pet Travel Policy (from problem statement)
        pet_policy = """
🐾 **Pet Travel Policy**

**Small Pets in Cabin:**
• ✅ Small cats and dogs allowed in cabin
• 💰 Fee: $125 each way
• 📦 Must fit in carrier under seat (17"L x 12.5"W x 8.5"H)
• 🎫 Maximum 4 pets per flight
• ⚠️ Must be at least 4 months old
• 📝 Reservation required - call JetBlue to book

**Not Allowed:**
• ❌ Pets in cargo/checked baggage
• ❌ Emotional support animals (except trained service animals)
• ❌ Pets on flights over 6 hours

**Requirements:**
• Health certificate from vet (within 30 days)
• Pet must remain in carrier entire flight
• Only 1 pet per carrier
• Carrier counts as your carry-on item

**Service Animals:**
• ✅ Trained service dogs allowed free of charge
• Must provide documentation

Would you like to know anything else about traveling with pets?
"""
        
        return {
            'response': pet_policy,
            'recommendations': []
        }
    
    def process_baggage_info(self, nlu_result: Dict, user_id: str, 
                           session_id: str) -> Dict:
        """Process baggage information requests"""
        message = nlu_result.get('original_message', '').lower()
        
        # Get baggage policy
        policies = self.rec_engine.get_policy_recommendations('baggage_info')
        
        if policies:
            policy = policies[0]
            
            # Create workflow for follow-up questions
            workflow = self.get_workflow_state(session_id, user_id)
            if not workflow or workflow.get('workflow_type') != 'baggage_info':
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='baggage_info',
                    current_step='showing_policy',
                    state_data={}
                )
            
            response = (
                f"**{policy['policy_name']}** 🧳\n\n"
                f"{policy['content']}\n\n"
            )
            
            # Check for specific questions
            if 'carry' in message or 'cabin' in message:
                response += "For carry-on bags: Maximum dimensions are 22x14x9 inches (56x36x23 cm).\n\n"
            elif 'check' in message or 'luggage' in message:
                response += "For checked bags: Each bag must weigh less than 50 lbs (23 kg).\n\n"
            elif 'cost' in message or 'fee' in message or 'price' in message:
                response += "Checked bag fees: $30 for first bag, $40 for second bag.\n\n"
            elif 'prohibited' in message or 'restricted' in message or 'not allowed' in message:
                response += (
                    "⚠️ **Prohibited items** include:\n"
                    "• Flammable materials\n"
                    "• Sharp objects in carry-on\n"
                    "• Liquids over 3.4oz in carry-on\n\n"
                )
            
            response += (
                "Do you have any specific questions about:\n"
                "• Carry-on allowance?\n"
                "• Checked baggage fees?\n"
                "• Prohibited items?\n"
                "• Excess baggage?\n"
                "Or would you like help with something else?"
            )
            
            return {
                'response': response,
                'recommendations': []
            }
        
        return {
            'response': (
                "Let me get you the baggage information...\n\n"
                "What specifically would you like to know about baggage?"
            ),
            'recommendations': []
        }
    
    def process_message(self, nlu_result: Dict, user_id: str, 
                       session_id: str) -> Dict:
        """Main workflow processing function"""
        intent = nlu_result.get('intent')
        message = nlu_result.get('original_message', '')
        
        # First check if this is an irrelevant query
        irrelevant_response = self.handle_irrelevant_query(message)
        if irrelevant_response:
            return irrelevant_response
        
        # Check for active workflows first
        workflow = self.get_workflow_state(session_id, user_id)
        
        if workflow and workflow.get('status') == 'active':
            workflow_type = workflow['workflow_type']
            current_step = workflow.get('current_step')
            entities = nlu_result.get('entities', {})
            
            # Check if user provided data relevant to current workflow
            relevant_data_provided = False
            if workflow_type == 'change_flight' and current_step == 'waiting_for_new_date':
                if entities.get('date') or any(char.isdigit() for char in message):
                    relevant_data_provided = True
            elif workflow_type == 'cancel_booking' and current_step == 'confirm':
                if any(word in message.lower() for word in ['yes', 'no', 'confirm', 'cancel']):
                    relevant_data_provided = True
            elif workflow_type == 'book_flight' and current_step == 'collecting_details':
                # Check if user provided any booking-related data
                if (entities.get('origin') or entities.get('destination') or 
                    entities.get('date') or entities.get('passenger_name') or
                    any(char.isdigit() for char in message)):
                    relevant_data_provided = True
            elif 'waiting_for_id' in current_step and entities.get('booking_id'):
                relevant_data_provided = True
            
            # Allow immediate exit to book_flight if user explicitly asks
            if intent == 'book_flight':
                if any(phrase in message.lower() for phrase in ['book a new', 'book new', 'new flight', 'need to book']):
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return self.process_message(nlu_result, user_id, session_id)
            
            # Check if user is responding to "continue or switch?" question
            if any(word in message.lower() for word in ['switch', 'change to', 'do', 'start']):
                # User wants to switch - complete old workflow and start new one
                self.complete_workflow(workflow['workflow_id'], session_id)
                
                # Determine which intent they want to switch to
                if intent in ['cancel_booking', 'check_status', 'change_flight', 'seat_upgrade', 'book_flight']:
                    return self.process_message(nlu_result, user_id, session_id)
                # If no clear intent, use the context
                elif 'cancel' in message.lower():
                    nlu_result['intent'] = 'cancel_booking'
                    return self.process_cancellation(nlu_result, user_id, session_id)
                elif 'change' in message.lower() or 'modify' in message.lower():
                    nlu_result['intent'] = 'change_flight'
                    return self.process_change_flight(nlu_result, user_id, session_id)
                elif 'upgrade' in message.lower() or 'seat' in message.lower():
                    nlu_result['intent'] = 'seat_upgrade'
                    return self.process_seat_upgrade(nlu_result, user_id, session_id)
                elif 'book' in message.lower():
                    nlu_result['intent'] = 'book_flight'
                    return self.process_book_flight(nlu_result, user_id, session_id)
            
            # Check if user wants to continue current workflow
            if any(word in message.lower() for word in ['continue', 'yes', 'proceed', 'go ahead']):
                # Continue with current workflow
                if workflow_type == 'cancel_booking':
                    return self.process_cancellation(nlu_result, user_id, session_id)
                elif workflow_type == 'change_flight':
                    return self.process_change_flight(nlu_result, user_id, session_id)
                elif workflow_type == 'seat_upgrade':
                    return self.process_seat_upgrade(nlu_result, user_id, session_id)
                elif workflow_type == 'check_status':
                    return self.process_booking_check(nlu_result, user_id, session_id)
            
            # If user provided relevant data, continue current workflow instead of switching
            if relevant_data_provided:
                if workflow_type == 'cancel_booking':
                    return self.process_cancellation(nlu_result, user_id, session_id)
                elif workflow_type == 'change_flight':
                    return self.process_change_flight(nlu_result, user_id, session_id)
                elif workflow_type == 'seat_upgrade':
                    return self.process_seat_upgrade(nlu_result, user_id, session_id)
                elif workflow_type == 'book_flight':
                    return self.process_book_flight(nlu_result, user_id, session_id)
            
            # Handle context switching - user wants to do something else mid-workflow
            if intent in ['cancel_booking', 'check_status', 'change_flight', 'seat_upgrade']:
                if intent != workflow_type and intent + '_' not in workflow_type:
                    # Check if user has booking ID or clear intent - auto switch
                    has_booking_id = entities.get('booking_id') is not None
                    clear_switch_phrase = any(phrase in message.lower() for phrase in [
                        'instead', 'rather', 'actually', 'no ', 'change to', 'switch to',
                        'i want to', 'i need to', 'let me', 'help me'
                    ])
                    
                    if has_booking_id or clear_switch_phrase:
                        # Auto-switch without asking
                        self.complete_workflow(workflow['workflow_id'], session_id)
                        return self.process_message(nlu_result, user_id, session_id)
                    
                    # Only ask if truly ambiguous
                    # User is trying to switch workflows - ask for confirmation
                    return {
                        'response': (
                            f"I see you're currently in the middle of a {workflow_type.replace('_', ' ')} process. "
                            f"Would you like to:\n"
                            f"• Continue with {workflow_type.replace('_', ' ')}?\n"
                            f"• Switch to {intent.replace('_', ' ')}?\n\n"
                            f"Just let me know what you'd prefer!"
                        ),
                        'recommendations': []
                    }
            
            # For informational queries (pet, baggage, children policy, FAQ), answer immediately without workflow switching
            if intent in ['pet_travel', 'children_policy', 'general_faq', 'baggage_info', 'cancellation_policy',
                         'complaints', 'damaged_bag', 'missing_bag', 'discounts', 'fare_check', 'flights_info',
                         'insurance', 'medical_policy', 'prohibited_items', 'sports_music_gear']:
                # These don't need workflows - answer directly
                return self.process_message(nlu_result, user_id, session_id)
            
            # Check if user wants to exit workflow
            message_lower = message.lower()
            if any(word in message_lower for word in ['exit', 'quit', 'stop', 'cancel this', 'start over', 'forget it']):
                self.complete_workflow(workflow['workflow_id'], session_id)
                return {
                    'response': (
                        "No problem! I've cancelled the current process. 👍\n\n"
                        "What would you like to do now? I can help you with:\n"
                        "• Check booking status\n"
                        "• Cancel a booking\n"
                        "• Change flight dates\n"
                        "• Upgrade seats\n"
                        "• Get policy information"
                    ),
                    'recommendations': []
                }
            
            # Continue with active workflow
            if workflow_type == 'cancel_booking':
                return self.process_cancellation(nlu_result, user_id, session_id)
            elif workflow_type == 'change_flight':
                return self.process_change_flight(nlu_result, user_id, session_id)
            elif workflow_type == 'seat_upgrade':
                return self.process_seat_upgrade(nlu_result, user_id, session_id)
            elif workflow_type == 'check_status':
                # Handle follow-up actions after showing booking details
                if 'cancel' in message_lower:
                    booking_id = workflow['state_data'].get('booking_id')
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    # Create new cancellation workflow
                    return self.process_cancellation(
                        {**nlu_result, 'entities': {'booking_id': booking_id}},
                        user_id,
                        session_id
                    )
                elif 'change' in message_lower or 'modify' in message_lower:
                    booking_id = workflow['state_data'].get('booking_id')
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return self.process_change_flight(
                        {**nlu_result, 'entities': {'booking_id': booking_id}},
                        user_id,
                        session_id
                    )
                elif 'upgrade' in message_lower or 'seat' in message_lower:
                    booking_id = workflow['state_data'].get('booking_id')
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return self.process_seat_upgrade(
                        {**nlu_result, 'entities': {'booking_id': booking_id}},
                        user_id,
                        session_id
                    )
                elif 'baggage' in message_lower or 'luggage' in message_lower:
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return self.process_baggage_info(nlu_result, user_id, session_id)
                elif any(word in message_lower for word in ['fine', 'good', 'okay', 'thanks', 'all set']):
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return {
                        'response': (
                            "Great! I'm glad everything looks good. ✈️\n\n"
                            "If you need anything else before your flight, just let me know. "
                            "Have a wonderful trip! 🌟"
                        ),
                        'recommendations': []
                    }
            elif workflow_type == 'baggage_info':
                # Handle follow-up baggage questions
                if 'carry' in message_lower or 'cabin' in message_lower:
                    return {
                        'response': (
                            "✈️ **Carry-on Allowance**:\n\n"
                            "• 1 carry-on bag (22x14x9 inches / 56x36x23 cm)\n"
                            "• 1 personal item (purse, laptop bag, etc.)\n"
                            "• Must fit in overhead bin or under seat\n\n"
                            "Anything else you'd like to know about baggage?"
                        ),
                        'recommendations': []
                    }
                elif 'check' in message_lower or 'luggage' in message_lower:
                    return {
                        'response': (
                            "🧳 **Checked Baggage**:\n\n"
                            "• First bag: $30\n"
                            "• Second bag: $40\n"
                            "• Maximum weight: 50 lbs (23 kg) per bag\n"
                            "• Maximum dimensions: 62 inches (158 cm) total\n\n"
                            "Need help with anything else?"
                        ),
                        'recommendations': []
                    }
                elif 'prohibited' in message_lower or 'not allowed' in message_lower:
                    return {
                        'response': (
                            "⚠️ **Prohibited/Restricted Items**:\n\n"
                            "**Cannot carry at all:**\n"
                            "• Explosives, flammable items\n"
                            "• Weapons (except when checked and declared)\n\n"
                            "**Carry-on restrictions:**\n"
                            "• Liquids over 3.4oz (100ml)\n"
                            "• Sharp objects (scissors, knives)\n"
                            "• Tools\n\n"
                            "These items may be allowed in checked baggage with restrictions.\n\n"
                            "Any other questions?"
                        ),
                        'recommendations': []
                    }
                elif 'excess' in message_lower or 'overweight' in message_lower or 'extra' in message_lower:
                    return {
                        'response': (
                            "💼 **Excess Baggage Fees**:\n\n"
                            "• Third+ bag: $150 per bag\n"
                            "• Overweight (50-70 lbs): $100 per bag\n"
                            "• Oversized (63-80 inches): $200 per bag\n\n"
                            "Tip: Consider shipping heavy items if you have many bags!\n\n"
                            "What else can I help with?"
                        ),
                        'recommendations': []
                    }
                elif any(word in message_lower for word in ['thanks', 'that\'s all', 'nothing', 'no']):
                    self.complete_workflow(workflow['workflow_id'], session_id)
                    return {
                        'response': (
                            "Perfect! If you have any other questions about baggage or your flight, "
                            "feel free to ask anytime. Have a great trip! ✈️"
                        ),
                        'recommendations': []
                    }
        
        # Process based on intent (no active workflow)
        if intent == 'check_status':
            return self.process_booking_check(nlu_result, user_id, session_id)
        
        elif intent == 'cancel_booking':
            return self.process_cancellation(nlu_result, user_id, session_id)
        
        elif intent == 'change_flight':
            return self.process_change_flight(nlu_result, user_id, session_id)
        
        elif intent == 'seat_upgrade':
            return self.process_seat_upgrade(nlu_result, user_id, session_id)
        
        elif intent == 'book_flight':
            return self.process_book_flight(nlu_result, user_id, session_id)
        
        elif intent == 'cancellation_policy':
            policies = self.rec_engine.get_policy_recommendations('cancellation_policy')
            if policies:
                policy = policies[0]
                
                # Create workflow for follow-up
                workflow_id = str(uuid.uuid4())
                self.save_workflow_state(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    user_id=user_id,
                    workflow_type='policy_inquiry',
                    current_step='showing_policy',
                    state_data={'policy_type': 'cancellation'}
                )
                
                return {
                    'response': (
                        f"**{policy['policy_name']}** 📋\n\n"
                        f"{policy['content']}\n\n"
                        f"Would you like to:\n"
                        f"• Cancel an existing booking?\n"
                        f"• Check another policy?\n"
                        f"• Or is there something else I can help with?"
                    ),
                    'recommendations': []
                }
            return {
                'response': "Let me get that information for you...",
                'recommendations': []
            }
        
        elif intent == 'baggage_info':
            return self.process_baggage_info(nlu_result, user_id, session_id)
        
        elif intent == 'pet_travel':
            return self.process_pet_travel(nlu_result, user_id, session_id)
        
        elif intent == 'children_policy':
            return self.process_children_policy(nlu_result, user_id, session_id)
        
        elif intent == 'complaints':
            return self.process_complaints(nlu_result, user_id, session_id)
        
        elif intent == 'damaged_bag':
            return self.process_damaged_bag(nlu_result, user_id, session_id)
        
        elif intent == 'missing_bag':
            return self.process_missing_bag(nlu_result, user_id, session_id)
        
        elif intent == 'discounts':
            return self.process_discounts(nlu_result, user_id, session_id)
        
        elif intent == 'fare_check':
            return self.process_fare_check(nlu_result, user_id, session_id)
        
        elif intent == 'flights_info':
            return self.process_flights_info(nlu_result, user_id, session_id)
        
        elif intent == 'insurance':
            return self.process_insurance(nlu_result, user_id, session_id)
        
        elif intent == 'medical_policy':
            return self.process_medical_policy(nlu_result, user_id, session_id)
        
        elif intent == 'prohibited_items':
            return self.process_prohibited_items(nlu_result, user_id, session_id)
        
        elif intent == 'sports_music_gear':
            return self.process_sports_music_gear(nlu_result, user_id, session_id)
        
        elif intent == 'general_faq':
            return self.process_general_faq(nlu_result, user_id, session_id)
        
        elif intent == 'greeting':
            # Check if user has bookings for personalized greeting
            bookings = self.airline_api.get_user_bookings(user_id)
            
            if bookings:
                greeting_msg = (
                    f"Hello! 👋 Welcome back!\n\n"
                    f"I can see you have {len(bookings)} active booking(s). "
                    f"I'm here to help you with:\n"
                    f"• Check your booking details\n"
                    f"• Cancel or modify bookings\n"
                    f"• Seat upgrades\n"
                    f"• Baggage information\n"
                    f"• Policy questions\n\n"
                    f"What would you like to do today?"
                )
            else:
                greeting_msg = (
                    "Hello! 👋 Welcome to our airline customer service.\n\n"
                    "I'm here to assist you with:\n"
                    "• Checking booking status\n"
                    "• Canceling bookings\n"
                    "• Changing flights\n"
                    "• Seat upgrades\n"
                    "• Baggage and policy information\n\n"
                    "How can I help you today?"
                )
            
            return {
                'response': greeting_msg,
                'recommendations': []
            }
        
        elif intent == 'help':
            return {
                'response': (
                    "I'm here to help! Here's what I can do for you:\n\n"
                    "📋 **Check Bookings**: Say 'check my booking' or 'show booking BK001'\n"
                    "❌ **Cancel**: Say 'cancel my booking' or 'cancel BK001'\n"
                    "🔄 **Change Flight**: Say 'change my flight' or 'modify booking'\n"
                    "💺 **Seat Upgrade**: Say 'upgrade my seat' or 'change seat'\n"
                    "🧳 **Baggage Info**: Ask 'baggage policy' or 'luggage allowance'\n"
                    "📋 **Policies**: Ask about 'cancellation policy', 'change fees', etc.\n\n"
                    "Just talk to me naturally - I'll understand! What would you like to do?"
                ),
                'recommendations': []
            }
        
        elif intent == 'book_flight':
            # Clear any existing workflow first
            if workflow:
                self.complete_workflow(workflow['workflow_id'], session_id)
            
            # Create new booking workflow
            workflow_id = str(uuid.uuid4())
            self.save_workflow_state(
                workflow_id=workflow_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type='book_flight',
                current_step='collecting_details',
                state_data={}
            )
            
            return {
                'response': (
                    "I'd love to help you book a flight! ✈️\n\n"
                    "To get started, I'll need a few details:\n"
                    "• Where are you flying from? (e.g., JFK, LAX)\n"
                    "• Where are you going?\n"
                    "• What date would you like to travel?\n"
                    "• Passenger name?\n\n"
                    "You can tell me all at once or one at a time!"
                ),
                'recommendations': []
            }
        
        else:
            # Unknown intent - provide helpful guidance
            return {
                'response': (
                    "I'm not quite sure what you're asking about. Let me help you! 😊\n\n"
                    "I can assist with:\n"
                    "✈️ **Flight Management**: Check, cancel, or change bookings\n"
                    "💺 **Seat Upgrades**: Get better seats\n"
                    "🧳 **Baggage Info**: Allowances and fees\n"
                    "📋 **Policies**: Cancellation, changes, refunds\n\n"
                    "What would you like help with today?"
                ),
                'recommendations': []
            }

# Singleton instance
_workflow_engine_instance = None

def get_workflow_engine() -> WorkflowEngine:
    """Get or create workflow engine instance"""
    global _workflow_engine_instance
    if _workflow_engine_instance is None:
        _workflow_engine_instance = WorkflowEngine()
    return _workflow_engine_instance