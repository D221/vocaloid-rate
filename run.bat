@echo off
echo "Setting up virtual environment..."
python -m venv venv

echo "Activating virtual environment and installing dependencies..."
call .\venv\Scripts\activate.bat
pip install -r requirements.txt

uvicorn app.main:app --host localhost --port 8000