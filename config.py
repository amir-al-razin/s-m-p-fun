import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys and Services
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

# Server Settings
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
ENV = os.getenv("ENV", "development")

# Log Configuration
IS_DEVELOPMENT = ENV.lower() == "development"
