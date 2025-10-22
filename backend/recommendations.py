import sqlite3
from typing import Dict, List
from pathlib import Path
import random

DATABASE_PATH = Path(__file__).parent / "airline_bot.db"

class RecommendationEngine:
    """Generate personalized recommendations for users"""
    
    def __init__(self):
        self.seat_upgrades = {
            'economy': ['Premium Economy - Extra legroom for $50', 
                       'Business Class - Full service for $200'],
            'premium_economy': ['Business Class - Full service for $150'],
        }
        
        self.additional_services = [
            {'service': 'Priority Boarding', 'price': 25},
            {'service': 'Extra Baggage', 'price': 40},
            {'service': 'Travel Insurance', 'price': 35},
            {'service': 'Airport Lounge Access', 'price': 60},
            {'service': 'In-flight WiFi', 'price': 15},
        ]
    
    def get_seat_upgrade_recommendations(self, booking: Dict) -> List[Dict]:
        """Recommend seat upgrades based on current booking"""
        recommendations = []
        
        # Determine current class based on seat
        seat = booking.get('seat_number', '')
        current_class = 'economy'
        
        if seat:
            row = int(''.join(filter(str.isdigit, seat)))
            if row <= 5:
                current_class = 'business'
            elif row <= 10:
                current_class = 'premium_economy'
        
        # Get upgrade options
        upgrades = self.seat_upgrades.get(current_class, [])
        
        for upgrade in upgrades:
            recommendations.append({
                'type': 'seat_upgrade',
                'description': upgrade,
                'booking_id': booking['booking_id']
            })
        
        return recommendations
    
    def get_service_recommendations(self, booking: Dict) -> List[Dict]:
        """Recommend additional services"""
        recommendations = []
        
        # Randomly select 2-3 services to recommend
        selected_services = random.sample(
            self.additional_services, 
            k=min(3, len(self.additional_services))
        )
        
        for service in selected_services:
            recommendations.append({
                'type': 'additional_service',
                'service': service['service'],
                'price': service['price'],
                'description': f"Add {service['service']} for ${service['price']}",
                'booking_id': booking['booking_id']
            })
        
        return recommendations
    
    def get_policy_recommendations(self, intent: str) -> List[Dict]:
        """Recommend relevant policies based on intent"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        policy_map = {
            'cancel_booking': 'cancellation',
            'cancellation_policy': 'cancellation',
            'baggage_info': 'baggage',
            'change_flight': 'change'
        }
        
        policy_type = policy_map.get(intent)
        recommendations = []
        
        if policy_type:
            cursor.execute("""
            SELECT * FROM policies WHERE policy_type = ?
            """, (policy_type,))
            
            rows = cursor.fetchall()
            for row in rows:
                recommendations.append({
                    'type': 'policy',
                    'policy_name': row['policy_name'],
                    'content': row['content']
                })
        
        conn.close()
        return recommendations
    
    def get_recommendations(self, intent: str, booking: Dict = None) -> List[Dict]:
        """Get all relevant recommendations"""
        recommendations = []
        
        # Add policy recommendations
        policy_recs = self.get_policy_recommendations(intent)
        recommendations.extend(policy_recs)
        
        # Add booking-specific recommendations
        if booking:
            if intent in ['check_status', 'seat_upgrade']:
                seat_recs = self.get_seat_upgrade_recommendations(booking)
                recommendations.extend(seat_recs[:2])  # Limit to 2
            
            if intent == 'check_status':
                service_recs = self.get_service_recommendations(booking)
                recommendations.extend(service_recs[:2])  # Limit to 2
        
        return recommendations
    
    def save_recommendation(self, user_id: str, booking_id: str, 
                           recommendation: Dict) -> int:
        """Save recommendation to database"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO recommendations 
        (user_id, booking_id, recommendation_type, recommendation_data)
        VALUES (?, ?, ?, ?)
        """, (
            user_id,
            booking_id,
            recommendation['type'],
            str(recommendation)
        ))
        
        recommendation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return recommendation_id

# Singleton instance
_rec_engine_instance = None

def get_recommendation_engine() -> RecommendationEngine:
    """Get or create recommendation engine instance"""
    global _rec_engine_instance
    if _rec_engine_instance is None:
        _rec_engine_instance = RecommendationEngine()
    return _rec_engine_instance