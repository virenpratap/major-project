import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-fallback-secret-key')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///alumni.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # NVIDIA AI
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY', '')
    NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
    NVIDIA_MODEL = 'nvidia/nemotron-3-super-120b-a12b'

    # Encryption
    FERNET_KEY = os.getenv('FERNET_KEY', '')

    # Storage
    STORAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage')

    # Rate limiting
    LLM_RATE_LIMIT = 10  # requests per minute
    LLM_RATE_WINDOW = 60  # seconds
