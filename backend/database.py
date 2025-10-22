import sqlite3
import datetime
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "airline_bot.db"

def init_database():
    """Initialize the SQLite database with all required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Bookings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id TEXT PRIMARY KEY,
        user_id TEXT,
        flight_number TEXT NOT NULL,
        passenger_name TEXT NOT NULL,
        departure_date TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        seat_number TEXT,
        status TEXT DEFAULT 'confirmed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)
    
    # Messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        message TEXT NOT NULL,
        intent TEXT,
        confidence REAL,
        response TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Workflow states table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workflow_states (
        workflow_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        workflow_type TEXT NOT NULL,
        current_step TEXT NOT NULL,
        state_data TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Feedback table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        message_id INTEGER,
        rating INTEGER,
        comment TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES messages(message_id)
    )
    """)
    
    # Recommendations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        booking_id TEXT,
        recommendation_type TEXT NOT NULL,
        recommendation_data TEXT NOT NULL,
        accepted INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Policy documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
        policy_name TEXT NOT NULL,
        policy_type TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Cache table (for persistent cache)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cache (
        cache_key TEXT PRIMARY KEY,
        cache_value TEXT NOT NULL,
        expiry TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Insert sample bookings for testing
    sample_bookings = [
        ('BK001', 'user123', 'AA101', 'John Doe', '2025-11-15', 'JFK', 'LAX', '12A', 'confirmed'),
        ('BK002', 'user123', 'AA202', 'John Doe', '2025-11-20', 'LAX', 'ORD', '8B', 'confirmed'),
        ('BK003', 'user456', 'AA303', 'Jane Smith', '2025-11-18', 'MIA', 'SFO', '5C', 'confirmed'),
    ]
    
    cursor.executemany("""
    INSERT OR IGNORE INTO bookings 
    (booking_id, user_id, flight_number, passenger_name, departure_date, origin, destination, seat_number, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_bookings)
    
    # Insert sample policies
    sample_policies = [
        ('Cancellation Policy', 'cancellation', 
         'Flights can be cancelled up to 24 hours before departure for a full refund. Cancellations within 24 hours incur a $50 fee.'),
        ('Baggage Policy', 'baggage',
         'Each passenger is allowed 1 carry-on bag (22x14x9 inches) and 1 personal item. Checked bags cost $30 for the first bag, $40 for the second.'),
        ('Change Policy', 'change',
         'Flight changes are allowed up to 2 hours before departure. Change fees vary by ticket type: $0 for flexible tickets, $75 for standard tickets.')
    ]
    
    cursor.executemany("""
    INSERT OR IGNORE INTO policies (policy_name, policy_type, content)
    VALUES (?, ?, ?)
    """, sample_policies)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DATABASE_PATH}")

if __name__ == "__main__":
    init_database()