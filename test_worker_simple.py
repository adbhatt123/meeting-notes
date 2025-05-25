#!/usr/bin/env python3
"""
Simple test worker to verify basic functionality
"""

import os
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_setup():
    """Test basic environment and imports"""
    
    logger.info("🚀 Testing Basic Worker Setup")
    
    # Test environment variables
    required_vars = [
        'ANTHROPIC_API_KEY',
        'AFFINITY_API_KEY', 
        'GOOGLE_DRIVE_FOLDER_ID'
    ]
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"✅ {var}: {'*' * 10}...{value[-4:]}")
        else:
            logger.error(f"❌ {var}: Not set")
    
    # Test Anthropic import
    try:
        import anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("✅ Anthropic client created successfully")
        else:
            logger.error("❌ No Anthropic API key")
    except Exception as e:
        logger.error(f"❌ Anthropic error: {e}")
    
    # Test Google imports
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        logger.info("✅ Google API imports successful")
    except Exception as e:
        logger.error(f"❌ Google API import error: {e}")
    
    # Test other imports
    try:
        import requests
        import docx
        logger.info("✅ Other dependencies imported")
    except Exception as e:
        logger.error(f"❌ Dependency error: {e}")

def main():
    """Main test function"""
    
    logger.info("🧪 Simple Worker Test Starting")
    
    for cycle in range(3):
        logger.info(f"Cycle #{cycle + 1}: Running basic tests...")
        test_basic_setup()
        logger.info("⏳ Waiting 30 seconds...")
        time.sleep(30)
    
    logger.info("🎉 Simple worker test complete")

if __name__ == '__main__':
    main()