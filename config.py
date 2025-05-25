import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Config:
    # Google APIs
    GOOGLE_CREDENTIALS_PATH: str = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')
    GOOGLE_DRIVE_FOLDER_NAME: str = os.getenv('GOOGLE_DRIVE_FOLDER_NAME', 'Meeting Notes')
    
    # Affinity CRM
    AFFINITY_API_KEY: str = os.getenv('AFFINITY_API_KEY', '')
    AFFINITY_PIPELINE_ID: str = os.getenv('AFFINITY_PIPELINE_ID', '')
    AFFINITY_BASE_URL: str = 'https://api.affinity.co'
    
    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv('ANTHROPIC_API_KEY', '')
    
    # Email settings
    FROM_EMAIL: str = os.getenv('FROM_EMAIL', '')
    FROM_NAME: str = os.getenv('FROM_NAME', 'VC Team')
    
    # Application settings
    CHECK_INTERVAL_MINUTES: int = int(os.getenv('CHECK_INTERVAL_MINUTES', '15'))
    PROCESSED_DOCS_FILE: str = os.getenv('PROCESSED_DOCS_FILE', 'processed_docs.json')
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate that all required environment variables are set."""
        errors = []
        
        required_vars = [
            ('GOOGLE_DRIVE_FOLDER_ID', cls.GOOGLE_DRIVE_FOLDER_ID),
            ('AFFINITY_API_KEY', cls.AFFINITY_API_KEY),
            ('AFFINITY_PIPELINE_ID', cls.AFFINITY_PIPELINE_ID),
            ('ANTHROPIC_API_KEY', cls.ANTHROPIC_API_KEY),
            ('FROM_EMAIL', cls.FROM_EMAIL),
        ]
        
        for var_name, var_value in required_vars:
            if not var_value:
                errors.append(f"Missing required environment variable: {var_name}")
        
        if not os.path.exists(cls.GOOGLE_CREDENTIALS_PATH):
            errors.append(f"Google credentials file not found: {cls.GOOGLE_CREDENTIALS_PATH}")
        
        return errors

config = Config()