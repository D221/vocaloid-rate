#!/bin/bash
echo "Setting up virtual environment..."
python3 -m venv venv

echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host localhost --port 8000 &
sleep 3
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8000
elif command -v open > /dev/null; then
    open http://localhost:8000
else
    echo "Could not open browser. Please navigate to http://localhost:8000 manually."
fi
wait