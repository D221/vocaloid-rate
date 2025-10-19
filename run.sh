#!/bin/bash
echo "Setting up virtual environment..."
python3 -m venv venv

echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host localhost --port 8000