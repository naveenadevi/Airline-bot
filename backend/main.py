from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
from datetime import datetime
import uuid

from nlu import get_nlu_module
from workflow import get_workflow_engine
from database import init_database, DATABASE_PATH

# Initialize FastAPI app
app = FastAPI(title="Airline Customer Service Bot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class MessageRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class MessageResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    recommendations: List[Dict[str, Any]]
    timestamp: str

class FeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    message_id: Optional[int] = None
    rating: int
    comment: Optional[str] = None

class AnalyticsResponse(BaseModel):
    total_messages: int
    total_sessions: int
    intent_distribution: Dict[str, int]
    average_confidence: float
    feedback_stats: Dict[str, Any]

# Initialize components
nlu_module = None
workflow_engine = None

@app.on_event("startup")
async def startup_event():
    """Initialize database and components on startup"""
    global nlu_module, workflow_engine
    
    # Initialize database
    init_database()
    
    # Initialize NLU module
    print("Loading NLU module...")
    nlu_module = get_nlu_module()
    
    # Initialize workflow engine
    workflow_engine = get_workflow_engine()
    
    print("Server initialized successfully!")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Airline Customer Service Bot API",
        "version": "1.0.0"
    }

@app.post("/api/message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Main endpoint to process user messages
    
    Flow:
    1. Receive message from frontend
    2. Send to NLU for intent classification
    3. Store message in database
    4. Trigger workflow engine
    5. Get recommendations
    6. Return response
    """
    try:
        # Process with NLU
        nlu_result = nlu_module.process(request.message)
        
        # Save message to database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO messages 
        (user_id, session_id, message, intent, confidence)
        VALUES (?, ?, ?, ?, ?)
        """, (
            request.user_id,
            request.session_id,
            request.message,
            nlu_result['intent'],
            nlu_result['confidence']
        ))
        
        message_id = cursor.lastrowid
        conn.commit()
        
        # Process with workflow engine
        workflow_result = workflow_engine.process_message(
            nlu_result,
            request.user_id,
            request.session_id
        )
        
        # Update message with response
        cursor.execute("""
        UPDATE messages 
        SET response = ?
        WHERE message_id = ?
        """, (workflow_result['response'], message_id))
        
        conn.commit()
        conn.close()
        
        return MessageResponse(
            response=workflow_result['response'],
            intent=nlu_result['intent'],
            confidence=nlu_result['confidence'],
            recommendations=workflow_result.get('recommendations', []),
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO feedback 
        (user_id, session_id, message_id, rating, comment)
        VALUES (?, ?, ?, ?, ?)
        """, (
            request.user_id,
            request.session_id,
            request.message_id,
            request.rating,
            request.comment
        ))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Feedback submitted"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bookings/{user_id}")
async def get_user_bookings(user_id: str):
    """Get all bookings for a user"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM bookings 
        WHERE user_id = ?
        ORDER BY departure_date DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    """Get system analytics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        total_messages = cursor.fetchone()['count']
        
        # Total sessions
        cursor.execute("SELECT COUNT(DISTINCT session_id) as count FROM messages")
        total_sessions = cursor.fetchone()['count']
        
        # Intent distribution
        cursor.execute("""
        SELECT intent, COUNT(*) as count 
        FROM messages 
        WHERE intent IS NOT NULL
        GROUP BY intent
        """)
        intent_rows = cursor.fetchall()
        intent_distribution = {row['intent']: row['count'] for row in intent_rows}
        
        # Average confidence
        cursor.execute("SELECT AVG(confidence) as avg_conf FROM messages WHERE confidence IS NOT NULL")
        avg_conf_row = cursor.fetchone()
        average_confidence = avg_conf_row['avg_conf'] or 0.0
        
        # Feedback stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total_feedback,
            AVG(rating) as avg_rating,
            COUNT(CASE WHEN rating >= 4 THEN 1 END) as positive_feedback
        FROM feedback
        """)
        feedback_row = cursor.fetchone()
        feedback_stats = dict(feedback_row)
        
        conn.close()
        
        return AnalyticsResponse(
            total_messages=total_messages,
            total_sessions=total_sessions,
            intent_distribution=intent_distribution,
            average_confidence=round(average_confidence, 3),
            feedback_stats=feedback_stats
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    cache = workflow_engine.cache
    return cache.get_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)