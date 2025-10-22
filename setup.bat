@echo off
echo Setting up Airline Customer Service Bot...

:: Create virtual environment
python -m venv venv

:: Activate virtual environment
call venv\Scripts\activate

:: Upgrade pip
python -m pip install --upgrade pip

:: Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

:: Install frontend dependencies
cd frontend
pip install -r requirements.txt
cd ..

:: Initialize database
cd backend
python database.py
cd ..

echo Setup complete!
echo.
echo To run the application:
echo 1. Backend: cd backend ^&^& uvicorn main:app --reload
echo 2. Frontend: cd frontend ^&^& streamlit run app.py
pause