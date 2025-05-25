#!/usr/bin/env python3
"""
VC Workflow Automation - Background Worker
Render Background Worker Service
"""

import json
import os
import time
import logging
import traceback
import docx
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VCWorkflowWorker:
    """Background worker for VC workflow automation"""
    
    def __init__(self):
        self.config = self.load_config()
        self.drive_service = None
        self.docs_service = None
        self.gmail_service = None
        self.anthropic = None
        
        self.processed_docs_file = '/opt/render/project/data/processed_documents.json'
        self.last_check_file = '/opt/render/project/data/last_check.json'
        self.activity_stats_file = '/opt/render/project/data/activity_stats.json'
        
        # Create data directory
        os.makedirs('/opt/render/project/data', exist_ok=True)
        
        self.initialize_services()
    
    def load_config(self):
        """Load configuration from environment variables"""
        return {
            'GOOGLE_DRIVE_FOLDER_ID': os.environ.get('GOOGLE_DRIVE_FOLDER_ID'),
            'AFFINITY_API_KEY': os.environ.get('AFFINITY_API_KEY'),
            'AFFINITY_PIPELINE_ID': os.environ.get('AFFINITY_PIPELINE_ID'),
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
            'FROM_EMAIL': os.environ.get('FROM_EMAIL'),
            'FROM_NAME': os.environ.get('FROM_NAME'),
            'CHECK_INTERVAL_MINUTES': int(os.environ.get('CHECK_INTERVAL_MINUTES', 5))
        }
    
    def initialize_services(self):
        """Initialize all required services"""
        logger.info("Initializing VC Workflow Worker services...")
        
        try:
            # Initialize Anthropic with proxy-compatible setup
            if self.config['ANTHROPIC_API_KEY']:
                try:
                    import anthropic
                    import httpx
                    
                    # Create custom HTTP client that handles proxies properly
                    http_client = httpx.Client(
                        timeout=60.0,
                        follow_redirects=True
                    )
                    
                    # Initialize Anthropic with custom HTTP client
                    self.anthropic = anthropic.Anthropic(
                        api_key=self.config['ANTHROPIC_API_KEY'],
                        http_client=http_client
                    )
                    logger.info("✅ Anthropic AI service ready (with proxy support)")
                except Exception as e:
                    logger.error(f"❌ Anthropic initialization with httpx failed: {e}")
                    # Fallback to basic initialization
                    try:
                        import anthropic
                        self.anthropic = anthropic.Anthropic(
                            api_key=self.config['ANTHROPIC_API_KEY']
                        )
                        logger.info("✅ Anthropic AI service ready (basic)")
                    except Exception as e2:
                        logger.error(f"❌ Anthropic basic initialization also failed: {e2}")
                        self.anthropic = None
            else:
                logger.error("❌ ANTHROPIC_API_KEY not configured")
                self.anthropic = None
            
            # Initialize Google services
            creds_data = self.load_google_credentials()
            if creds_data:
                creds = Credentials(
                    token=creds_data['token'],
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data['token_uri'],
                    client_id=creds_data['client_id'],
                    client_secret=creds_data['client_secret'],
                    scopes=creds_data['scopes']
                )
                
                self.drive_service = build('drive', 'v3', credentials=creds)
                self.docs_service = build('docs', 'v1', credentials=creds)
                self.gmail_service = build('gmail', 'v1', credentials=creds)
                logger.info("✅ Google services ready (Drive, Docs, Gmail)")
            else:
                logger.warning("⚠️ Google credentials not found - OAuth setup required")
                
        except Exception as e:
            logger.error(f"❌ Error initializing services: {e}")
    
    def load_google_credentials(self):
        """Load Google OAuth credentials"""
        try:
            # First check environment variable
            env_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
            if env_creds:
                try:
                    creds_data = json.loads(env_creds)
                    logger.info("Found credentials in environment variable")
                    return creds_data
                except Exception as e:
                    logger.warning(f"Could not parse env credentials: {e}")
            
            # Check multiple possible file locations
            possible_paths = [
                '/tmp/google_drive_token.json',
                '/opt/render/project/data/google_drive_token.json',
                'google_drive_token.json'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        logger.info(f"Found credentials at: {path}")
                        return json.load(f)
            
            logger.warning("No Google credentials found - OAuth setup required via web interface")
            logger.info("Available environment variables:")
            for key in os.environ:
                if 'GOOGLE' in key:
                    value = os.environ[key]
                    logger.info(f"  {key}: {value[:20]}...")
            
            # Try using OAuth client credentials to create a simple test
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
            if client_id and client_secret:
                logger.info("Found OAuth client credentials - but need access token")
                logger.info("Visit web interface to complete OAuth and copy credentials")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load Google credentials: {e}")
            return None
    
    def get_last_check_time(self):
        """Get the last time we checked for new documents"""
        try:
            if os.path.exists(self.last_check_file):
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
        except Exception as e:
            logger.warning(f"Could not load last check time: {e}")
        
        # Default to 24 hours ago
        return datetime.utcnow() - timedelta(hours=24)
    
    def update_last_check_time(self):
        """Update the last check time to now"""
        try:
            current_time = datetime.utcnow()
            with open(self.last_check_file, 'w') as f:
                json.dump({'last_check': current_time.isoformat()}, f)
        except Exception as e:
            logger.error(f"Could not update last check time: {e}")
    
    def get_processed_documents(self):
        """Get list of already processed document IDs"""
        try:
            if os.path.exists(self.processed_docs_file):
                with open(self.processed_docs_file, 'r') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f"Could not load processed documents: {e}")
        
        return set()
    
    def mark_document_processed(self, doc_id):
        """Mark a document as processed"""
        try:
            processed_docs = self.get_processed_documents()
            processed_docs.add(doc_id)
            with open(self.processed_docs_file, 'w') as f:
                json.dump(list(processed_docs), f)
        except Exception as e:
            logger.error(f"Could not mark document as processed: {e}")
    
    def update_activity_stats(self, processed_count=0, deals_created=0):
        """Update activity statistics"""
        try:
            stats = {}
            if os.path.exists(self.activity_stats_file):
                with open(self.activity_stats_file, 'r') as f:
                    stats = json.load(f)
            
            today = datetime.utcnow().date().isoformat()
            
            if stats.get('date') != today:
                # Reset daily counters
                stats = {
                    'date': today,
                    'processed_today': 0,
                    'deals_created': 0
                }
            
            stats['processed_today'] += processed_count
            stats['deals_created'] += deals_created
            stats['last_check'] = datetime.utcnow().isoformat()
            
            with open(self.activity_stats_file, 'w') as f:
                json.dump(stats, f)
                
        except Exception as e:
            logger.error(f"Could not update activity stats: {e}")
    
    def get_new_documents(self):
        """Get new documents from Google Drive folder"""
        if not self.drive_service:
            logger.warning("Google Drive service not available")
            return []
        
        try:
            last_check = self.get_last_check_time()
            time_string = last_check.isoformat() + 'Z'
            
            # Query for new documents
            query = (
                f"'{self.config['GOOGLE_DRIVE_FOLDER_ID']}' in parents and "
                f"(mimeType='application/vnd.google-apps.document' or "
                f"mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and "
                f"createdTime > '{time_string}'"
            )
            
            results = self.drive_service.files().list(
                q=query,
                pageSize=50,
                fields="files(id,name,mimeType,createdTime,webViewLink)",
                orderBy="createdTime desc"
            ).execute()
            
            documents = results.get('files', [])
            
            # Filter out already processed documents
            processed_docs = self.get_processed_documents()
            new_docs = [doc for doc in documents if doc['id'] not in processed_docs]
            
            logger.info(f"Found {len(new_docs)} new documents to process")
            return new_docs
            
        except Exception as e:
            logger.error(f"Error fetching new documents: {e}")
            return []
    
    def extract_document_content(self, doc):
        """Extract content from a document"""
        try:
            if doc['mimeType'] == 'application/vnd.google-apps.document':
                # Google Doc
                document = self.docs_service.documents().get(documentId=doc['id']).execute()
                
                content = []
                body = document.get('body', {})
                
                for element in body.get('content', []):
                    if 'paragraph' in element:
                        paragraph = element['paragraph']
                        for text_element in paragraph.get('elements', []):
                            if 'textRun' in text_element:
                                content.append(text_element['textRun']['content'])
                
                return ''.join(content)
                
            elif doc['mimeType'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                # Word document - download and extract
                file_content = self.drive_service.files().get_media(fileId=doc['id']).execute()
                
                # Save temporarily
                temp_path = f"/tmp/{doc['id']}.docx"
                with open(temp_path, 'wb') as f:
                    f.write(file_content)
                
                # Extract text
                doc_obj = docx.Document(temp_path)
                text = '\n'.join([p.text for p in doc_obj.paragraphs])
                
                # Clean up
                os.remove(temp_path)
                
                return text
            
            else:
                logger.warning(f"Unsupported document type: {doc['mimeType']}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting content from {doc['name']}: {e}")
            return None
    
    def extract_founder_info(self, doc_title, doc_content):
        """Extract founder information using AI"""
        try:
            prompt = f"""Extract founder and company information from this meeting document.

Document Title: {doc_title}
Content: {doc_content}

Identify:
1. Who is the founder (exclude "Adarsh Bhatt" - he's the VC)
2. Founder's email address
3. Company name or domain
4. Key discussion points
5. Suggested next steps

Return JSON format:
{{
  "founder_name": "...",
  "founder_email": "...",
  "company_name": "...",
  "domain": "...",
  "key_points": [...],
  "next_steps": [...]
}}"""
            
            response = self.anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract JSON from response
            content = response.content[0].text.strip()
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
            else:
                logger.warning("Could not extract JSON from AI response")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting founder info: {e}")
            return None
    
    def create_affinity_deal(self, founder_info, meeting_content, doc_title):
        """Create deal in Affinity CRM"""
        try:
            auth = ('', self.config['AFFINITY_API_KEY'])
            headers = {'Content-Type': 'application/json'}
            base_url = "https://api.affinity.co"
            
            # Determine deal name
            if founder_info.get('domain') and '@gmail.com' not in founder_info.get('founder_email', ''):
                deal_name = founder_info['domain']
            else:
                deal_name = f"{founder_info['founder_name']}'s Deal"
            
            # Create organization
            org_data = {'name': deal_name}
            org_response = requests.post(f'{base_url}/organizations', 
                                       auth=auth, headers=headers, json=org_data)
            
            if org_response.status_code not in [200, 201]:
                logger.error(f"Organization creation failed: {org_response.status_code}")
                return None
            
            org = org_response.json()
            org_id = org.get('id')
            
            # Create deal
            deal_data = {
                'entity_id': org_id,
                'list_id': int(self.config['AFFINITY_PIPELINE_ID'])
            }
            
            deal_response = requests.post(f'{base_url}/lists/{self.config["AFFINITY_PIPELINE_ID"]}/list-entries',
                                        auth=auth, headers=headers, json=deal_data)
            
            if deal_response.status_code not in [200, 201]:
                logger.error(f"Deal creation failed: {deal_response.status_code}")
                return None
            
            deal = deal_response.json()
            
            # Create note with meeting content
            note_data = {
                'content': f"Meeting Notes - {doc_title}\\n\\n{meeting_content}",
                'organization_ids': [org_id]
            }
            
            note_response = requests.post(f'{base_url}/notes',
                                        auth=auth, headers=headers, json=note_data)
            
            return {
                'organization': org,
                'deal': deal,
                'note_created': note_response.status_code in [200, 201]
            }
            
        except Exception as e:
            logger.error(f"Error creating Affinity deal: {e}")
            return None
    
    def create_follow_up_email(self, founder_info, doc_title):
        """Create follow-up email draft"""
        try:
            # Generate email content
            email_prompt = f"""Write a professional follow-up email after a VC meeting.

CONTEXT:
- Founder: {founder_info['founder_name']}
- Email: {founder_info['founder_email']}
- Company: {founder_info.get('company_name', 'the company')}
- Meeting: {doc_title}

NEXT STEPS TO INCLUDE:
{chr(10).join(founder_info.get('next_steps', []))}

Write a warm, professional email from {self.config['FROM_NAME']} confirming the next steps and offering continued support.
"""
            
            response = self.anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=600,
                messages=[{"role": "user", "content": email_prompt}]
            )
            
            email_body = response.content[0].text.strip()
            
            # Create Gmail draft
            message = MIMEMultipart()
            message['to'] = founder_info['founder_email']
            message['subject'] = f"Great meeting you - {founder_info['founder_name']}"
            message['from'] = f"{self.config['FROM_NAME']} <{self.config['FROM_EMAIL']}>"
            
            body = MIMEText(email_body + f"\\n\\nBest regards,\\n{self.config['FROM_NAME']}", 'plain')
            message.attach(body)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            draft_body = {'message': {'raw': raw_message}}
            
            draft = self.gmail_service.users().drafts().create(userId='me', body=draft_body).execute()
            
            return draft.get('id')
            
        except Exception as e:
            logger.error(f"Error creating follow-up email: {e}")
            return None
    
    def process_document(self, doc):
        """Process a single document through the complete workflow"""
        logger.info(f"Processing document: {doc['name']}")
        
        try:
            # Extract content
            content = self.extract_document_content(doc)
            if not content:
                return False
            
            logger.info(f"Content extracted: {len(content)} characters")
            
            # Extract founder info
            founder_info = self.extract_founder_info(doc['name'], content)
            if not founder_info:
                return False
            
            logger.info(f"Founder identified: {founder_info.get('founder_name', 'Unknown')}")
            
            # Create Affinity deal
            affinity_result = self.create_affinity_deal(founder_info, content, doc['name'])
            if not affinity_result:
                return False
            
            logger.info(f"Deal created: {affinity_result['organization']['name']}")
            
            # Create email draft
            draft_id = self.create_follow_up_email(founder_info, doc['name'])
            if not draft_id:
                logger.warning("Email draft creation failed, but continuing...")
            else:
                logger.info(f"Email draft created: {draft_id}")
            
            # Mark as processed
            self.mark_document_processed(doc['id'])
            
            logger.info(f"✅ Document processed successfully: {founder_info['founder_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run_automation_cycle(self):
        """Run one complete automation cycle"""
        logger.info("Starting VC workflow automation cycle")
        
        # Check if services are initialized
        if not self.drive_service:
            logger.warning("Google Drive service not available - skipping cycle")
            return 0
        
        if not self.anthropic:
            logger.error("Anthropic service not available - skipping cycle")
            return 0
        
        # Get new documents
        new_docs = self.get_new_documents()
        
        if not new_docs:
            logger.info("No new documents found")
            self.update_last_check_time()
            self.update_activity_stats()
            return 0
        
        # Process each document
        processed_count = 0
        deals_created = 0
        
        for doc in new_docs:
            try:
                if self.process_document(doc):
                    processed_count += 1
                    deals_created += 1
                
                # Small delay between documents
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to process document {doc['name']}: {e}")
        
        # Update tracking
        self.update_last_check_time()
        self.update_activity_stats(processed_count, deals_created)
        
        logger.info(f"Automation cycle complete: {processed_count}/{len(new_docs)} documents processed")
        return processed_count
    
    def run_continuous(self):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous VC workflow monitoring (every {self.config['CHECK_INTERVAL_MINUTES']} minutes)")
        
        cycle_count = 0
        total_processed = 0
        
        while True:
            try:
                cycle_count += 1
                logger.info(f"Cycle #{cycle_count}: Checking for new documents...")
                
                processed_count = self.run_automation_cycle()
                total_processed += processed_count
                
                if processed_count > 0:
                    logger.info(f"🎉 Processed {processed_count} new document(s)!")
                
                logger.info(f"Waiting {self.config['CHECK_INTERVAL_MINUTES']} minutes until next check...")
                time.sleep(self.config['CHECK_INTERVAL_MINUTES'] * 60)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
                
            except Exception as e:
                logger.error(f"Error in automation cycle: {e}")
                logger.error(traceback.format_exc())
                # Wait before retrying
                time.sleep(60)

def main():
    """Main worker function"""
    logger.info("🚀 Starting VC Workflow Automation Worker")
    
    worker = VCWorkflowWorker()
    worker.run_continuous()

if __name__ == '__main__':
    main()
