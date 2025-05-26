#!/usr/bin/env python3
"""
VC Workflow Automation - Clean Background Worker
Uses web service APIs instead of direct Google API calls
"""

import json
import os
import time
import logging
import traceback
import requests
from datetime import datetime, timedelta
import anthropic
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VCWorkflowWorker:
    """Simplified background worker using web service APIs"""
    
    def __init__(self):
        self.config = self.load_config()
        self.web_service_url = self.config.get('WEB_SERVICE_URL', 'https://vc-workflow-web.onrender.com')
        
        # Initialize Anthropic with proxy support
        http_client = httpx.Client(timeout=60.0, follow_redirects=True)
        self.anthropic = anthropic.Anthropic(
            api_key=self.config['ANTHROPIC_API_KEY'],
            http_client=http_client
        )
        
        self.processed_docs_file = '/opt/render/project/data/processed_documents.json'
        self.last_check_file = '/opt/render/project/data/last_check.json'
        self.activity_stats_file = '/opt/render/project/data/activity_stats.json'
        
        # Create data directory
        os.makedirs('/opt/render/project/data', exist_ok=True)
        
        logger.info("✅ Simplified worker initialized - using web service APIs")
    
    def load_config(self):
        """Load configuration from environment variables"""
        config = {
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
            'AFFINITY_API_KEY': os.environ.get('AFFINITY_API_KEY'),
            'AFFINITY_LIST_ID': os.environ.get('AFFINITY_LIST_ID'),
            'GOOGLE_DRIVE_FOLDER_ID': os.environ.get('GOOGLE_DRIVE_FOLDER_ID'),
            'CHECK_INTERVAL_MINUTES': int(os.environ.get('CHECK_INTERVAL_MINUTES', 60)),
            'WEB_SERVICE_URL': os.environ.get('WEB_SERVICE_URL', 'https://vc-workflow-web.onrender.com')
        }
        
        missing = [k for k, v in config.items() if not v and k != 'WEB_SERVICE_URL']
        if missing:
            logger.error(f"Missing environment variables: {missing}")
            raise ValueError(f"Missing required environment variables: {missing}")
        
        return config
    
    def web_api_call(self, endpoint, method='GET', data=None, params=None):
        """Make API call to web service"""
        url = f"{self.web_service_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Web API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Web API call failed for {endpoint}: {e}")
            return None
    
    def run_check_cycle(self):
        """Run one check cycle"""
        logger.info("🔄 Starting check cycle...")
        
        try:
            # Simple test - just get status
            status = self.web_api_call('/api/status')
            if status:
                logger.info(f"✅ Web service connected. Google Drive: {status.get('google_drive_connected', False)}")
            else:
                logger.error("❌ Web service not accessible")
            
            # Update last check time
            data = {
                'last_check': datetime.utcnow().isoformat() + 'Z'
            }
            try:
                with open(self.last_check_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving last check: {e}")
            
            logger.info(f"✅ Check cycle completed.")
            
        except Exception as e:
            logger.error(f"Error in check cycle: {e}")
            logger.error(traceback.format_exc())
    
    def run(self):
        """Main worker loop"""
        logger.info("🚀 VC Workflow Worker starting...")
        logger.info(f"📊 Check interval: {self.config['CHECK_INTERVAL_MINUTES']} minutes")
        logger.info(f"🌐 Web service URL: {self.web_service_url}")
        
        while True:
            try:
                self.run_check_cycle()
                
                # Wait for next check
                sleep_seconds = self.config['CHECK_INTERVAL_MINUTES'] * 60
                logger.info(f"😴 Sleeping for {self.config['CHECK_INTERVAL_MINUTES']} minutes...")
                time.sleep(sleep_seconds)
                
            except KeyboardInterrupt:
                logger.info("👋 Worker stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    """Main entry point"""
    try:
        worker = VCWorkflowWorker()
        worker.run()
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    main()