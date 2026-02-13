import sys
import os

# Add the project root to the Python path so 'app' can be imported
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.main import app  # noqa: F401
