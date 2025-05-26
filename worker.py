#!/usr/bin/env python3
"""
VC Workflow Automation - Full Background Worker
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
    
    def get_new_documents(self):
        """Get new documents from Google Drive via web service"""
        logger.info("📋 Checking for new documents...")
        
        # Get last check time
        last_check = self.load_last_check()
        logger.info(f"📅 Last check time: {last_check}")
        
        params = {
            'folder_id': self.config['GOOGLE_DRIVE_FOLDER_ID']
        }
        
        if last_check:
            params['modified_since'] = last_check
            logger.info(f"🔍 Looking for documents modified since: {last_check}")
        else:
            logger.info(f"🔍 Looking for ALL documents (no last check time)")
        
        # Call web service API
        result = self.web_api_call('/api/google/drive/files', params=params)
        
        if result is None:
            logger.error("Failed to get documents from web service")
            return []
        
        files = result.get('files', [])
        logger.info(f"📄 Found {len(files)} documents to check")
        
        # Filter documents - check if new or modified since last processing
        processed_docs = self.load_processed_documents()
        new_files = []
        
        for file_info in files:
            doc_id = file_info['id']
            doc_modified = file_info.get('modifiedTime', '')
            
            # Check if document is new or has been modified since last processing
            if doc_id not in processed_docs:
                new_files.append(file_info)
                logger.info(f"📄 New document: {file_info['name']}")
            else:
                # Check if document was modified after it was processed
                processed_info = processed_docs[doc_id]
                processed_at = processed_info.get('processed_at', '')
                
                if doc_modified > processed_at:
                    new_files.append(file_info)
                    logger.info(f"📝 Updated document: {file_info['name']} (modified: {doc_modified}, processed: {processed_at})")
        
        logger.info(f"📄 {len(new_files)} new/updated documents to process")
        return new_files
    
    def get_document_content(self, document_id):
        """Get document content via web service"""
        result = self.web_api_call(f'/api/google/documents/{document_id}')
        
        if result is None:
            logger.error(f"Failed to get document content for {document_id}")
            return None
        
        # Log what we received
        logger.info(f"📄 Document API response:")
        logger.info(f"  - Title: {result.get('title', 'Untitled')}")
        logger.info(f"  - Content length: {len(result.get('content', ''))} chars")
        logger.info(f"  - Founder email: {result.get('founder_email', 'NOT FOUND')}")
        logger.info(f"  - Total emails found: {len(result.get('emails_found', []))}")
        
        if result.get('debug_info'):
            logger.info(f"  - Debug info: {result['debug_info']}")
        
        # Log all emails found
        emails = result.get('emails_found', [])
        if emails:
            logger.info("  - All emails found:")
            for email_info in emails:
                logger.info(f"    * {email_info.get('text', 'No text')} -> {email_info.get('email')} (invited: {email_info.get('in_invited', False)})")
        
        return {
            'title': result.get('title', 'Untitled'),
            'content': result.get('content', ''),
            'founder_email': result.get('founder_email'),  # Email extracted from Invited section
            'emails_found': result.get('emails_found', []),
            'founder_name': result.get('founder_name')  # Founder name from title
        }
    
    def extract_founder_info(self, content, document_title, doc_data):
        """Extract founder information using Anthropic Claude"""
        logger.info("🤖 Extracting founder information with Claude...")
        
        try:
            extracted_email = doc_data.get('founder_email', 'Not found')
            extracted_name = doc_data.get('founder_name', '')
            
            # Build context for Claude
            email_context = ""
            if extracted_email and extracted_email != 'Not found':
                email_context = f"The founder's email is: {extracted_email}"
            elif extracted_name:
                email_context = f"The founder's name (from document title) is: {extracted_name}. Please look for their email in the document content or infer it from common patterns (firstname@company.com, etc.)"
            else:
                email_context = "No email was found automatically. Please extract it from the document content."
            
            prompt = f"""
Analyze this VC meeting note and extract key information about the founder and company.

IMPORTANT EMAIL EXTRACTION:
{email_context}

Additional context:
- The founder is the first person in the "Invited" section who is NOT "Adarsh Bhatt"
- If you can't find an email directly, look for:
  - Email patterns in the document (founder@company.com)
  - Company domain mentioned and combine with founder's first name
  - Any email signatures or contact information

Document Title: {document_title}

Meeting Notes:
{content}

Please extract the following information in JSON format:
{{
    "founder_name": "Full name of the founder",
    "founder_email": "Email address (must be found or inferred from the document)",
    "company_name": "Name of the company/startup",
    "industry": "Industry or sector",
    "stage": "Funding stage (seed, series A, etc.)",
    "summary": "Brief 2-3 sentence summary of the company and meeting",
    "next_steps": "Any mentioned next steps or follow-ups"
}}

Only include information that is explicitly mentioned in the notes. Use null for missing information.
"""
            
            message = self.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            response_text = message.content[0].text
            
            # Try to extract JSON from response
            try:
                # Find JSON in response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx != 0:
                    json_str = response_text[start_idx:end_idx]
                    founder_info = json.loads(json_str)
                    logger.info(f"✅ Extracted info for: {founder_info.get('founder_name', 'Unknown')}")
                    
                    # Log email extraction result
                    founder_email = founder_info.get('founder_email')
                    if founder_email:
                        logger.info(f"📧 Found founder email: {founder_email}")
                    else:
                        logger.warning("⚠️ No founder email found in extraction")
                        # Use the email from document extraction if Claude didn't find one
                        if doc_data.get('founder_email'):
                            founder_info['founder_email'] = doc_data['founder_email']
                            logger.info(f"📧 Using email from document extraction: {doc_data['founder_email']}")
                    
                    return founder_info
                else:
                    logger.error("No JSON found in Claude response")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Claude response: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return None
    
    def create_affinity_deal(self, founder_info, document_title, document_content):
        """Create deal in Affinity via web service"""
        logger.info("💼 Creating Affinity deal...")
        
        try:
            # Prepare deal data
            company_name = founder_info.get('company_name', 'Unknown Company')
            founder_name = founder_info.get('founder_name', 'Unknown Founder')
            founder_email = founder_info.get('founder_email', '')
            
            # Determine deal name based on email domain
            deal_name = company_name  # Default to company name
            
            if founder_email:
                # Extract domain from email
                email_domain = founder_email.split('@')[-1].lower()
                
                # Check if it's a corporate email (not gmail, yahoo, outlook, etc.)
                personal_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 
                                   'icloud.com', 'me.com', 'mac.com', 'live.com', 'msn.com',
                                   'aol.com', 'protonmail.com', 'proton.me']
                
                if email_domain not in personal_domains:
                    # Use domain as company name (capitalize first letter)
                    domain_name = email_domain.split('.')[0]
                    deal_name = domain_name.capitalize()
                    logger.info(f"Using corporate domain for deal name: {deal_name}")
                else:
                    # Personal email - use founder's name
                    deal_name = f"{founder_name}'s Company"
                    logger.info(f"Using founder name format for deal: {deal_name}")
            else:
                # No email - use founder's name format
                deal_name = f"{founder_name}'s Company"
                logger.info(f"No email found, using founder name format: {deal_name}")
            
            # Prepare meeting notes for Affinity
            meeting_notes = self._format_meeting_notes(founder_info, document_content)
            
            deal_data = {
                'name': deal_name,
                'stage': 'Prospecting',
                'entity_id': None,  # Will be created if needed
                'notes': meeting_notes,
                'founder_info': founder_info  # Pass full info for notes creation
            }
            
            # Call web service API
            result = self.web_api_call('/api/affinity/deals', method='POST', data=deal_data)
            
            if result is None:
                logger.error("Failed to create Affinity deal")
                return None
            
            deal_id = result.get('deal_id')
            logger.info(f"✅ Created Affinity deal: {deal_id} with name: {deal_name}")
            return deal_id
            
        except Exception as e:
            logger.error(f"Error creating Affinity deal: {e}")
            return None
    
    def _format_meeting_notes(self, founder_info, document_content):
        """Format meeting notes for Affinity"""
        notes = f"""Meeting Notes - {datetime.utcnow().strftime('%Y-%m-%d')}

Founder: {founder_info.get('founder_name', 'Unknown')}
Email: {founder_info.get('founder_email', 'Not provided')}
Company: {founder_info.get('company_name', 'Unknown')}
Industry: {founder_info.get('industry', 'Not specified')}
Stage: {founder_info.get('stage', 'Not specified')}

=== SUMMARY ===
{founder_info.get('summary', 'No summary available')}

=== NEXT STEPS ===
{founder_info.get('next_steps', 'No next steps defined')}

=== FULL MEETING NOTES ===
{document_content}
"""
        return notes
    
    def generate_follow_up_email(self, founder_info):
        """Generate follow-up email using Claude"""
        logger.info("📧 Generating follow-up email...")
        
        try:
            founder_name = founder_info.get('founder_name', 'there')
            company_name = founder_info.get('company_name', 'your company')
            summary = founder_info.get('summary', 'our recent conversation')
            
            prompt = f"""
Write a professional follow-up email to a founder after a VC meeting.

Founder: {founder_name}
Company: {company_name}
Meeting Summary: {summary}

Please write a warm, professional follow-up email that:
1. Thanks them for their time
2. References something specific from the conversation
3. Expresses continued interest
4. Suggests next steps
5. Keeps it concise (3-4 paragraphs max)

Format as a proper email with subject line.
"""
            
            message = self.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            email_content = message.content[0].text
            logger.info("✅ Generated follow-up email")
            return email_content
            
        except Exception as e:
            logger.error(f"Error generating email: {e}")
            return None
    
    def create_gmail_draft(self, email_content, founder_email):
        """Create Gmail draft via web service"""
        if not founder_email:
            logger.warning("No founder email provided, skipping Gmail draft")
            return None
            
        logger.info("📧 Creating Gmail draft...")
        
        try:
            # Parse email content for subject and body
            lines = email_content.split('\n')
            subject_line = None
            body_lines = []
            
            for i, line in enumerate(lines):
                if line.lower().startswith('subject:'):
                    subject_line = line[8:].strip()
                elif subject_line is not None:
                    body_lines.append(line)
            
            if not subject_line:
                subject_line = "Following up on our conversation"
            
            body = '\n'.join(body_lines).strip()
            
            # Prepare email data
            email_data = {
                'to': founder_email,
                'subject': subject_line,
                'body': body
            }
            
            # Call web service API
            result = self.web_api_call('/api/google/gmail/draft', method='POST', data=email_data)
            
            if result is None:
                logger.error("Failed to create Gmail draft")
                return None
            
            draft_id = result.get('draft_id')
            logger.info(f"✅ Created Gmail draft: {draft_id}")
            return draft_id
            
        except Exception as e:
            logger.error(f"Error creating Gmail draft: {e}")
            return None
    
    def process_document(self, file_info):
        """Process a single document"""
        doc_id = file_info['id']
        doc_name = file_info['name']
        
        logger.info(f"🔄 Processing document: {doc_name}")
        
        try:
            # Get document content
            doc_data = self.get_document_content(doc_id)
            if not doc_data:
                logger.error(f"Failed to get content for {doc_name}")
                return False
            
            content = doc_data['content']
            title = doc_data['title']
            
            if not content or len(content.strip()) < 100:
                logger.warning(f"Document {doc_name} has insufficient content")
                return False
            
            # Log the founder email we're passing to Claude
            logger.info(f"🔍 Passing to Claude: founder_email = {doc_data.get('founder_email', 'None')}")
            
            # Extract founder information
            founder_info = self.extract_founder_info(content, title, doc_data)
            if not founder_info:
                logger.error(f"Failed to extract founder info from {doc_name}")
                return False
            
            # Create Affinity deal
            deal_id = self.create_affinity_deal(founder_info, title, content)
            
            # Generate and create email draft
            email_content = self.generate_follow_up_email(founder_info)
            draft_id = None
            if email_content:
                founder_email = founder_info.get('founder_email')
                draft_id = self.create_gmail_draft(email_content, founder_email)
            
            # Mark as processed
            self.mark_document_processed(doc_id, {
                'document_name': doc_name,
                'founder_name': founder_info.get('founder_name'),
                'company_name': founder_info.get('company_name'),
                'affinity_deal_id': deal_id,
                'gmail_draft_id': draft_id
            })
            
            logger.info(f"✅ Successfully processed: {doc_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {doc_name}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run_check_cycle(self):
        """Run one check cycle"""
        logger.info("🔄 Starting check cycle...")
        
        try:
            # Get new documents
            new_documents = self.get_new_documents()
            
            processed_count = 0
            
            for file_info in new_documents:
                if self.process_document(file_info):
                    processed_count += 1
                
                # Small delay between documents
                time.sleep(5)
            
            # Update last check time
            self.save_last_check()
            
            # Update activity stats
            self.update_activity_stats(processed_count)
            
            logger.info(f"✅ Check cycle completed. Processed {processed_count} documents.")
            
        except Exception as e:
            logger.error(f"Error in check cycle: {e}")
            logger.error(traceback.format_exc())
    
    def load_processed_documents(self):
        """Load list of processed document IDs"""
        try:
            if os.path.exists(self.processed_docs_file):
                with open(self.processed_docs_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading processed documents: {e}")
            return {}
    
    def mark_document_processed(self, doc_id, metadata):
        """Mark document as processed"""
        try:
            processed_docs = self.load_processed_documents()
            # Include the current processing timestamp
            metadata['processed_at'] = datetime.utcnow().isoformat() + 'Z'
            processed_docs[doc_id] = metadata
            
            with open(self.processed_docs_file, 'w') as f:
                json.dump(processed_docs, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error marking document processed: {e}")
    
    def load_last_check(self):
        """Load last check timestamp"""
        try:
            if os.path.exists(self.last_check_file):
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                    return data.get('last_check')
            else:
                # First run: start from 1 hour ago to avoid processing all historical docs
                one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
                logger.info(f"🆕 First run: setting last_check to 1 hour ago: {one_hour_ago}")
                return one_hour_ago
        except Exception as e:
            logger.error(f"Error loading last check: {e}")
            # Fallback: 1 hour ago
            return (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
    
    def save_last_check(self):
        """Save current timestamp as last check"""
        try:
            data = {
                'last_check': datetime.utcnow().isoformat() + 'Z'
            }
            with open(self.last_check_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving last check: {e}")
    
    def update_activity_stats(self, processed_count):
        """Update activity statistics"""
        try:
            stats = {
                'last_check': datetime.utcnow().isoformat(),
                'processed_today': processed_count,
                'deals_created': processed_count  # Simplified
            }
            
            with open(self.activity_stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating activity stats: {e}")
    
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
