import re
from typing import Dict, List, Tuple, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class NLUModule:
    """Natural Language Understanding module using rules and embeddings"""
    
    def __init__(self):
        # Initialize embedding model (lightweight model for quick startup)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Define intents with example phrases
        self.intents = {
            'book_flight': [
                "I want to book a flight",
                "Book a flight for me",
                "I need to make a reservation",
                "Can I book a ticket"
            ],
            'cancel_booking': [
                "Cancel my booking",
                "I want to cancel my flight",
                "Cancel reservation",
                "I need to cancel my ticket"
            ],
            'check_status': [
                "What's my booking status",
                "Check my reservation",
                "Show my flight details",
                "Flight status"
            ],
            'change_flight': [
                "Change my flight",
                "Reschedule my booking",
                "I want to modify my reservation",
                "Can I change my flight date"
            ],
            'seat_upgrade': [
                "Upgrade my seat",
                "I want a better seat",
                "Can I get business class",
                "Upgrade to first class"
            ],
            'baggage_info': [
                "Baggage policy",
                "How much luggage can I bring",
                "Baggage allowance",
                "What about checked bags"
            ],
            'cancellation_policy': [
                "What's your cancellation policy",
                "Can I get a refund",
                "Cancellation rules",
                "How do I cancel"
            ],
            'pet_travel': [
                "Can I bring my pet",
                "Are pets allowed on flights",
                "Pet travel policy",
                "Flying with a dog"
            ],
            'children_policy': [
                "Do children need their own seat",
                "Infant seating policy",
                "Can children sit on my lap",
                "Special seats for children"
            ],
            'complaints': [
                "I want to file a complaint",
                "I had a bad experience",
                "Complain about service",
                "Report an issue"
            ],
            'damaged_bag': [
                "My bag is damaged",
                "Luggage arrived broken",
                "Damaged baggage claim",
                "Suitcase is torn"
            ],
            'missing_bag': [
                "My bag is missing",
                "Lost luggage",
                "Cannot find my suitcase",
                "Baggage didn't arrive"
            ],
            'discounts': [
                "Any discounts available",
                "Do you have deals",
                "Promo codes",
                "Special offers"
            ],
            'fare_check': [
                "How much is a ticket",
                "Check fare to Miami",
                "Ticket prices",
                "Cost of flight"
            ],
            'flights_info': [
                "Flight schedule",
                "Available flights to Delhi",
                "What time does the flight depart",
                "Flight information"
            ],
            'insurance': [
                "Travel insurance",
                "Flight insurance policy",
                "Trip protection",
                "Insurance coverage"
            ],
            'medical_policy': [
                "Medical certificate requirements",
                "Can I fly if I'm sick",
                "Health requirements",
                "Medication policy"
            ],
            'prohibited_items': [
                "What items are prohibited",
                "Banned items list",
                "What cannot I bring",
                "Restricted items"
            ],
            'sports_music_gear': [
                "Can I bring sports equipment",
                "Guitar on flight",
                "Ski equipment policy",
                "Musical instrument policy"
            ],
            'general_faq': [
                "What are your policies",
                "Tell me about your rules",
                "What's allowed on flights",
                "General information"
            ],
            'greeting': [
                "Hello",
                "Hi",
                "Hey there",
                "Good morning"
            ],
            'help': [
                "Help me",
                "What can you do",
                "I need assistance",
                "How does this work"
            ]
        }
        
        # Pre-compute embeddings for intent examples
        self.intent_embeddings = {}
        for intent, examples in self.intents.items():
            embeddings = self.model.encode(examples)
            self.intent_embeddings[intent] = embeddings
    
    def extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities/slots from the message"""
        entities = {}
        
        # Skip entity extraction for questions and informational queries
        message_lower = message.lower()
        question_patterns = [
            'is there', 'are there', 'do you', 'can i', 'can you', 
            'what is', 'what are', 'how much', 'how many', 'when',
            'tell me', 'show me', 'explain', 'policy', 'allowed',
            'file', 'complaint', 'complain', 'damaged', 'missing', 'lost',
            'discount', 'deal', 'offer', 'fare', 'price', 'cost',
            'schedule', 'insurance', 'medical', 'prohibited', 'banned',
            'sport', 'music', 'instrument', 'equipment', 'need to file',
            'want to file', 'i have', 'report'
        ]
        
        # If message starts with or contains question patterns, don't extract entities
        if any(pattern in message_lower for pattern in question_patterns):
            # This is likely a question, not booking data
            return entities
        
        # First, check if this is comma-separated input
        if ',' in message:
            # Split by comma and clean each part
            parts = [p.strip() for p in message.split(',')]
            
            # City name to airport code mapping
            city_to_code = {
                # Indian Cities
                'Chennai': 'MAA',
                'Delhi': 'DEL',
                'Mumbai': 'BOM',
                'Bangalore': 'BLR',
                'Bengaluru': 'BLR',
                'Banglore': 'BLR',
                'Coimbatore': 'CJB',
                'Kolkata': 'CCU',
                'Hyderabad': 'HYD',
                'Pune': 'PNQ',
                # US Cities
                'Newyork': 'JFK',
                'New York': 'JFK',
                'California': 'LAX',  # Default CA to LAX
                'Lasvegas': 'LAS',
                'Las Vegas': 'LAS',
                'Los Angeles': 'LAX',
                'Losangeles': 'LAX',
                'San Francisco': 'SFO',
                'Sanfrancisco': 'SFO',
                'Chicago': 'ORD',
                'Miami': 'MIA',
                'Boston': 'BOS',
                'Seattle': 'SEA',
                'Atlanta': 'ATL',
                'Dallas': 'DFW',
                'Houston': 'IAH',
                'Washington': 'DCA',
                'Philadelphia': 'PHL',
                'Phoenix': 'PHX',
                'Denver': 'DEN'
            }
            
            # Categorize each part
            dates = []
            airports = []
            names = []
            
            for part in parts:
                part_clean = part.strip()
                part_upper = part_clean.upper()
                
                # Check if it's a date
                if re.match(r'\d{4}-\d{2}-\d{2}', part_clean):
                    dates.append(part_clean)
                # Check if it's an airport code (2-3 letters)
                elif len(part_clean) <= 3 and part_clean.isalpha():
                    airports.append(part_upper)
                # Check if it's a city name that we recognize
                elif part_clean.title() in city_to_code:
                    airports.append(city_to_code[part_clean.title()])
                # Otherwise, it's likely a passenger name
                elif part_clean and part_clean[0].isupper() and part_clean.replace(' ', '').isalpha():
                    names.append(part_clean.title())
            
            # Assign to entities
            if dates:
                entities['date'] = dates[0]
            if len(airports) >= 2:
                entities['origin'] = airports[0]
                entities['destination'] = airports[1]
            elif len(airports) == 1:
                entities['origin'] = airports[0]
            if names:
                entities['passenger_name'] = names[0]
        
        # Extract booking ID (format: BK + 3 digits)
        booking_pattern = r'\b(BK\d{3})\b'
        booking_match = re.search(booking_pattern, message, re.IGNORECASE)
        if booking_match:
            entities['booking_id'] = booking_match.group(1).upper()
        
        # Extract flight number (format: 2 letters + 3 digits)
        flight_pattern = r'\b([A-Z]{2}\d{3})\b'
        flight_match = re.search(flight_pattern, message, re.IGNORECASE)
        if flight_match:
            entities['flight_number'] = flight_match.group(1).upper()
        
        # Extract dates if not already found (multiple formats)
        if 'date' not in entities:
            date_pattern = r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b'
            date_match = re.search(date_pattern, message)
            if date_match:
                entities['date'] = date_match.group(1)
        
        # Extract passenger name from keywords if not already found
        if 'passenger_name' not in entities:
            name_keywords = ['passenger', 'name', 'traveler', 'for']
            for keyword in name_keywords:
                pattern = rf'{keyword}\s+(?:is\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
                name_match = re.search(pattern, message, re.IGNORECASE)
                if name_match:
                    entities['passenger_name'] = name_match.group(1).title()
                    break
        
        # Extract airport codes if not already found from comma-separated
        if 'origin' not in entities or 'destination' not in entities:
            # Look for patterns like "from X to Y" or "X to Y"
            to_from_pattern = r'(?:from\s+)?([A-Z]{2,3}|[A-Z][a-z]+)\s+(?:to|→)\s+([A-Z]{2,3}|[A-Z][a-z]+)'
            match = re.search(to_from_pattern, message, re.IGNORECASE)
            if match:
                origin_str = match.group(1).upper()
                dest_str = match.group(2).upper()
                
                # Map city names if needed
                city_to_code = {
                    'CHENNAI': 'MAA',
                    'DELHI': 'DEL',
                    'MUMBAI': 'BOM',
                    'BANGALORE': 'BLR',
                    'BENGALURU': 'BLR',
                    'BANGLORE': 'BLR',
                    'COIMBATORE': 'CJB',
                    'KOLKATA': 'CCU',
                    'HYDERABAD': 'HYD',
                    'PUNE': 'PNQ',
                    'NEWYORK': 'JFK',
                    'NEW YORK': 'JFK',
                    'CALIFORNIA': 'LAX',
                    'LASVEGAS': 'LAS',
                    'LAS VEGAS': 'LAS',
                    'LOS ANGELES': 'LAX',
                    'LOSANGELES': 'LAX',
                    'SAN FRANCISCO': 'SFO',
                    'SANFRANCISCO': 'SFO',
                    'CHICAGO': 'ORD',
                    'MIAMI': 'MIA',
                    'BOSTON': 'BOS',
                    'SEATTLE': 'SEA',
                    'ATLANTA': 'ATL',
                    'DALLAS': 'DFW',
                    'HOUSTON': 'IAH',
                    'WASHINGTON': 'DCA',
                    'PHILADELPHIA': 'PHL',
                    'PHOENIX': 'PHX',
                    'DENVER': 'DEN'
                }
                
                entities['origin'] = city_to_code.get(origin_str, origin_str) if len(origin_str) > 3 else origin_str
                entities['destination'] = city_to_code.get(dest_str, dest_str) if len(dest_str) > 3 else dest_str
        
        # Last resort: extract any 2-3 letter uppercase words as potential airports
        if 'origin' not in entities or 'destination' not in entities:
            airport_pattern = r'\b([A-Z]{2,3})\b'
            potential_airports = re.findall(airport_pattern, message.upper())
            
            valid_airports = []
            for code in potential_airports:
                if not any(char.isdigit() for char in code):
                    if code not in ['TO', 'FROM', 'ON', 'AT', 'FOR', 'AND', 'THE', 'OR']:
                        valid_airports.append(code)
            
            if len(valid_airports) >= 2:
                if 'origin' not in entities:
                    entities['origin'] = valid_airports[0]
                if 'destination' not in entities:
                    entities['destination'] = valid_airports[1]
            elif len(valid_airports) == 1:
                if 'origin' not in entities:
                    entities['origin'] = valid_airports[0]
        
        return entities
    
    def classify_intent(self, message: str) -> Tuple[str, float]:
        """Classify intent using embedding similarity"""
        # Encode the input message
        message_embedding = self.model.encode([message])[0]
        
        # Calculate similarity with all intents
        intent_scores = {}
        for intent, embeddings in self.intent_embeddings.items():
            similarities = cosine_similarity([message_embedding], embeddings)[0]
            intent_scores[intent] = float(np.max(similarities))
        
        # Get the intent with highest score
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
        
        # Apply rule-based overrides for high-confidence patterns
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['cancel', 'cancellation', 'refund']):
            if 'policy' in message_lower or 'rule' in message_lower:
                return 'cancellation_policy', min(confidence + 0.2, 1.0)
            elif any(word in message_lower for word in ['cancel my', 'cancel booking', 'cancel flight']):
                return 'cancel_booking', min(confidence + 0.2, 1.0)
        
        if 'baggage' in message_lower or 'luggage' in message_lower:
            return 'baggage_info', min(confidence + 0.2, 1.0)
        
        if any(word in message_lower for word in ['status', 'check my', 'show my']):
            return 'check_status', min(confidence + 0.15, 1.0)
        
        # Detect pet travel questions
        if any(word in message_lower for word in ['pet', 'dog', 'cat', 'animal']):
            if any(word in message_lower for word in ['allow', 'travel', 'bring', 'flight', 'fly', 'policy']):
                return 'pet_travel', min(confidence + 0.25, 1.0)
        
        # Detect children/infant policy questions
        if any(word in message_lower for word in ['child', 'children', 'infant', 'baby', 'kid', 'toddler']):
            if any(word in message_lower for word in ['seat', 'policy', 'age', 'travel', 'fly', 'allow']):
                return 'children_policy', min(confidence + 0.25, 1.0)
        
        # Detect complaints
        if any(word in message_lower for word in ['complaint', 'complain', 'unhappy', 'dissatisfied', 'issue', 'problem']):
            if any(word in message_lower for word in ['file', 'report', 'submit', 'had', 'service', 'experience']):
                return 'complaints', min(confidence + 0.25, 1.0)
        
        # Detect damaged bag
        if any(word in message_lower for word in ['damage', 'damaged', 'broken', 'torn']):
            if any(word in message_lower for word in ['bag', 'luggage', 'suitcase', 'baggage']):
                return 'damaged_bag', min(confidence + 0.25, 1.0)
        
        # Detect missing bag
        if any(word in message_lower for word in ['missing', 'lost', 'cannot find', 'didnt receive']):
            if any(word in message_lower for word in ['bag', 'luggage', 'suitcase', 'baggage']):
                return 'missing_bag', min(confidence + 0.25, 1.0)
        
        # Detect discounts
        if any(word in message_lower for word in ['discount', 'deal', 'offer', 'promo', 'coupon', 'sale']):
            return 'discounts', min(confidence + 0.2, 1.0)
        
        # Detect fare check
        if any(word in message_lower for word in ['fare', 'price', 'cost', 'how much', 'ticket price']):
            if not any(word in message_lower for word in ['change', 'cancel']):
                return 'fare_check', min(confidence + 0.2, 1.0)
        
        # Detect flights info
        if any(word in message_lower for word in ['flight', 'schedule', 'departure', 'arrival', 'timing']):
            if any(word in message_lower for word in ['info', 'information', 'schedule', 'when', 'time', 'available']):
                return 'flights_info', min(confidence + 0.2, 1.0)
        
        # Detect insurance
        if any(word in message_lower for word in ['insurance', 'coverage', 'protect', 'travel protection']):
            return 'insurance', min(confidence + 0.25, 1.0)
        
        # Detect medical policy
        if any(word in message_lower for word in ['medical', 'health', 'doctor', 'sick', 'illness', 'medication']):
            if any(word in message_lower for word in ['policy', 'certificate', 'requirement', 'need', 'fly']):
                return 'medical_policy', min(confidence + 0.25, 1.0)
        
        # Detect prohibited items
        if any(word in message_lower for word in ['prohibited', 'banned', 'not allowed', 'restricted', 'forbidden']):
            if any(word in message_lower for word in ['item', 'bring', 'carry', 'pack']):
                return 'prohibited_items', min(confidence + 0.25, 1.0)
        
        # Detect sports/music gear
        if any(word in message_lower for word in ['sport', 'sports', 'music', 'instrument', 'guitar', 'ski', 'surfboard', 'golf', 'bicycle']):
            if any(word in message_lower for word in ['equipment', 'gear', 'bag', 'bring', 'carry', 'policy']):
                return 'sports_music_gear', min(confidence + 0.25, 1.0)
        
        # Detect general policy/FAQ questions
        if any(word in message_lower for word in ['policy', 'rule', 'regulation', 'allow', 'permitted']):
            if not any(word in message_lower for word in ['cancel', 'refund', 'baggage', 'luggage']):
                return 'general_faq', min(confidence + 0.15, 1.0)
        
        # Detect change flight intent
        if any(phrase in message_lower for phrase in ['change', 'modify', 'reschedule', 'switch date', 'change date', 'new date']):
            if any(word in message_lower for word in ['flight', 'date', 'booking', 'reservation']):
                return 'change_flight', min(confidence + 0.25, 1.0)
        
        # Detect book flight intent
        if any(phrase in message_lower for phrase in ['book', 'new flight', 'reservation', 'need to book', 'want to book']):
            if not any(word in message_lower for word in ['cancel', 'change', 'modify', 'check']):
                return 'book_flight', min(confidence + 0.2, 1.0)
        
        return best_intent, confidence
    
    def process(self, message: str) -> Dict[str, Any]:
        """Process a message and return intent, entities, and confidence"""
        intent, confidence = self.classify_intent(message)
        entities = self.extract_entities(message)
        
        return {
            'intent': intent,
            'confidence': confidence,
            'entities': entities,
            'original_message': message
        }

# Singleton instance
_nlu_instance = None

def get_nlu_module() -> NLUModule:
    """Get or create NLU module instance"""
    global _nlu_instance
    if _nlu_instance is None:
        _nlu_instance = NLUModule()
    return _nlu_instance