import sqlite3
from typing import Dict, Optional, List
from pathlib import Path
import random

DATABASE_PATH = Path(__file__).parent / "airline_bot.db"

class MockAirlineAPI:
    """Mock API simulating real airline backend systems"""
    
    def __init__(self):
        self.available_seats = {
            'AA101': ['12A', '12B', '15C', '20A', '20B'],
            'AA202': ['8B', '10A', '10B', '18C'],
            'AA303': ['5C', '7A', '7B', '14A']
        }
    
    def get_booking(self, booking_id: str, user_id: str = None) -> Optional[Dict]:
        """Retrieve booking information - optionally verify user ownership"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if user_id:
            # Verify booking belongs to user
            cursor.execute("""
            SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?
            """, (booking_id, user_id))
        else:
            # No user verification (backward compatibility, but discouraged)
            cursor.execute("""
            SELECT * FROM bookings WHERE booking_id = ?
            """, (booking_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_bookings(self, user_id: str) -> List[Dict]:
        """Get all bookings for a user"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM bookings 
        WHERE user_id = ? AND status = 'confirmed'
        ORDER BY departure_date DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def cancel_booking(self, booking_id: str) -> Dict:
        """Cancel a booking"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Check if booking exists
        cursor.execute("""
        SELECT status FROM bookings WHERE booking_id = ?
        """, (booking_id,))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {
                'success': False,
                'message': f'Booking {booking_id} not found'
            }
        
        if result[0] == 'cancelled':
            conn.close()
            return {
                'success': False,
                'message': f'Booking {booking_id} is already cancelled'
            }
        
        # Cancel the booking
        cursor.execute("""
        UPDATE bookings 
        SET status = 'cancelled'
        WHERE booking_id = ?
        """, (booking_id,))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'message': f'Booking {booking_id} has been cancelled successfully',
            'refund_amount': random.randint(200, 500)
        }
    
    def get_available_seats(self, flight_number: str) -> List[str]:
        """Get available seats for a flight"""
        return self.available_seats.get(flight_number, [])
    
    def change_flight(self, booking_id: str, new_flight_number: str, 
                      new_date: str) -> Dict:
        """Change flight details"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE bookings 
        SET flight_number = ?, departure_date = ?
        WHERE booking_id = ?
        """, (new_flight_number, new_date, booking_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return {
                'success': False,
                'message': f'Booking {booking_id} not found'
            }
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'message': f'Flight changed to {new_flight_number} on {new_date}',
            'change_fee': 75
        }
    
    def upgrade_seat(self, booking_id: str, new_seat: str) -> Dict:
        """Upgrade seat for a booking"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE bookings 
        SET seat_number = ?
        WHERE booking_id = ?
        """, (new_seat, booking_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return {
                'success': False,
                'message': f'Booking {booking_id} not found'
            }
        
        conn.commit()
        conn.close()
        
        upgrade_cost = random.randint(50, 150)
        
        return {
            'success': True,
            'message': f'Seat upgraded to {new_seat}',
            'upgrade_cost': upgrade_cost
        }
    
    def create_booking(self, booking_data: Dict) -> Dict:
        """Create a new booking"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Generate booking ID
        cursor.execute("SELECT COUNT(*) FROM bookings")
        count = cursor.fetchone()[0]
        booking_id = f"BK{count + 1:03d}"
        
        cursor.execute("""
        INSERT INTO bookings 
        (booking_id, user_id, flight_number, passenger_name, 
         departure_date, origin, destination, seat_number, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
        """, (
            booking_id,
            booking_data.get('user_id', 'user123'),
            booking_data['flight_number'],
            booking_data['passenger_name'],
            booking_data['departure_date'],
            booking_data['origin'],
            booking_data['destination'],
            booking_data.get('seat_number', 'TBD')
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'booking_id': booking_id,
            'message': 'Booking created successfully'
        }

# Singleton instance
_api_instance = None

def get_airline_api() -> MockAirlineAPI:
    """Get or create airline API instance"""
    global _api_instance
    if _api_instance is None:
        _api_instance = MockAirlineAPI()
    return _api_instance