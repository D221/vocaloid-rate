@echo off
echo "Setting up virtual environment..."
python -m venv venv

echo "Activating virtual environment and installing dependencies..."
call .\venv\Scripts\activate.bat
pip install -r requirements.txt

echo "Starting Vocaloid Rater on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."
uvicorn app.main:app --host 127.0.0.1 --port 8000