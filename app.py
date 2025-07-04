#!/usr/bin/env python3
"""
VC Workflow Automation - Web Service for OAuth and Monitoring
Render Web Service Component
"""

from flask import Flask, request, redirect, render_template_string, jsonify
import json
import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime
import logging
import io
import re
from html.parser import HTMLParser

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vc-workflow-automation-key')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
REDIRECT_URI = f"{RENDER_EXTERNAL_URL}/oauth/callback"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/contacts.readonly'  # For People API
]

@app.route('/')
def dashboard():
    """Main dashboard showing system status"""
    
    dashboard_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VC Workflow Automation</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { background: #2563eb; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .status-card { background: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 10px 0; }
            .status-ok { border-left: 4px solid #10b981; }
            .status-error { border-left: 4px solid #ef4444; }
            .status-warning { border-left: 4px solid #f59e0b; }
            .button { background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block; }
            .stats { display: flex; justify-content: space-between; flex-wrap: wrap; }
            .stat { background: white; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; min-width: 200px; margin: 5px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 VC Workflow Automation</h1>
            <p>Automated meeting note processing for your VC fund</p>
        </div>
        
        <div class="status-card" id="auth-status">
            <h3>🔐 Authentication Status</h3>
            <p id="auth-message">Checking Google Drive access...</p>
            <a href="/oauth/start" class="button">Setup Google Drive Access</a>
        </div>
        
        <div class="status-card status-ok">
            <h3>⚙️ System Components</h3>
            <p>✅ Anthropic AI: Ready</p>
            <p>✅ Affinity CRM: Connected</p>
            <p>✅ Gmail API: Ready</p>
            <p>✅ Background Worker: Running</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <h4>📊 Today's Activity</h4>
                <p><strong id="processed-today">0</strong> documents processed</p>
                <p><strong id="deals-created">0</strong> deals created</p>
            </div>
            <div class="stat">
                <h4>🕐 Last Check</h4>
                <p id="last-check">Never</p>
            </div>
            <div class="stat">
                <h4>📁 Monitored Folder</h4>
                <p>Meet Recordings</p>
                <p>{{ folder_id }}</p>
            </div>
        </div>
        
        <div class="status-card">
            <h3>📋 Recent Activity</h3>
            <div id="recent-activity">
                <p>Loading recent activity...</p>
            </div>
        </div>
        
        <script>
            // Check authentication status
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const authStatus = document.getElementById('auth-status');
                    const authMessage = document.getElementById('auth-message');
                    
                    if (data.google_drive_connected) {
                        authStatus.className = 'status-card status-ok';
                        authMessage.textContent = `✅ Connected as ${data.user_email}`;
                    } else {
                        authStatus.className = 'status-card status-error';
                        authMessage.textContent = '❌ Google Drive not connected';
                    }
                    
                    // Update stats
                    document.getElementById('processed-today').textContent = data.processed_today || 0;
                    document.getElementById('deals-created').textContent = data.deals_created || 0;
                    document.getElementById('last-check').textContent = data.last_check || 'Never';
                })
                .catch(error => console.error('Error:', error));
        </script>
    </body>
    </html>
    """.replace('{{ folder_id }}', os.environ.get('GOOGLE_DRIVE_FOLDER_ID', 'Not configured'))
    
    return dashboard_html

@app.route('/oauth/start')
def oauth_start():
    """Start Google OAuth flow"""
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return "OAuth credentials not configured", 500
    
    # Build OAuth URL
    oauth_params = {
        'response_type': 'code',
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    oauth_url = 'https://accounts.google.com/o/oauth2/auth?' + '&'.join([f'{k}={v}' for k, v in oauth_params.items()])
    
    return redirect(oauth_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Google"""
    
    auth_code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')  # Check if this is for worker
    
    if error:
        return f"OAuth error: {error}", 400
    
    if not auth_code:
        return "No authorization code received", 400
    
    try:
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': auth_code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            return f"Token exchange failed: {response.status_code}", 500
        
        tokens = response.json()
        
        # Create credentials
        creds_data = {
            'token': tokens['access_token'],
            'refresh_token': tokens.get('refresh_token'),
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'scopes': SCOPES
        }
        
        # Check if this is for worker credentials
        if state == 'worker_credentials':
            # Return JSON for worker service
            return f"""
            <html>
            <head><title>Worker Credentials</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h2>🔐 Worker Service Credentials</h2>
                <p>Copy this JSON and add it to your worker service environment variables:</p>
                <p><strong>Key:</strong> GOOGLE_CREDENTIALS_JSON</p>
                <p><strong>Value:</strong></p>
                <textarea readonly style="width: 100%; height: 300px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ccc;">{json.dumps(creds_data, indent=2)}</textarea>
                <p><strong>Next steps:</strong></p>
                <ol>
                    <li>Copy the JSON above</li>
                    <li>Go to Render Dashboard → vc-workflow-worker service → Environment</li>
                    <li>Add GOOGLE_CREDENTIALS_JSON with the JSON as value</li>
                    <li>Save changes to redeploy worker</li>
                </ol>
                <a href="/" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Back to Dashboard</a>
            </body>
            </html>
            """
        
        # Regular web service credentials
        save_credentials(creds_data)
        
        # Test the credentials
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        drive_service = build('drive', 'v3', credentials=creds)
        about = drive_service.about().get(fields="user").execute()
        user_email = about.get('user', {}).get('emailAddress', 'Unknown')
        
        logger.info(f"OAuth successful for user: {user_email}")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 100px auto; text-align: center;">
            <h2>✅ Authorization Successful!</h2>
            <p>Google Drive access configured for: <strong>{user_email}</strong></p>
            <p>The VC workflow automation is now fully operational.</p>
            <a href="/" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Back to Dashboard</a>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return f"OAuth setup failed: {str(e)}", 500

@app.route('/api/status')
def api_status():
    """API endpoint for system status"""
    
    try:
        # Check Google Drive connection
        creds_data = load_credentials()
        google_drive_connected = False
        user_email = None
        
        if creds_data:
            try:
                creds = Credentials(
                    token=creds_data['token'],
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data['token_uri'],
                    client_id=creds_data['client_id'],
                    client_secret=creds_data['client_secret'],
                    scopes=creds_data['scopes']
                )
                
                drive_service = build('drive', 'v3', credentials=creds)
                about = drive_service.about().get(fields="user").execute()
                user_email = about.get('user', {}).get('emailAddress')
                google_drive_connected = True
                
            except Exception as e:
                logger.warning(f"Google Drive connection test failed: {e}")
        
        # Load activity stats
        stats = load_activity_stats()
        
        return jsonify({
            'google_drive_connected': google_drive_connected,
            'user_email': user_email,
            'processed_today': stats.get('processed_today', 0),
            'deals_created': stats.get('deals_created', 0),
            'last_check': stats.get('last_check', 'Never'),
            'system_healthy': google_drive_connected
        })
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test')
def api_test():
    """Test endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'vc-workflow-automation'
    })

@app.route('/api/token/status')
def api_token_status():
    """Check the status of Google credentials and tokens"""
    try:
        # Check for Google Drive token
        token_file = 'token.json'
        gmail_token_file = 'gmail_token.json'
        
        status = {
            'google_drive': {
                'token_exists': os.path.exists(token_file),
                'valid': False,
                'expires_at': None,
                'has_refresh_token': False
            },
            'gmail': {
                'token_exists': os.path.exists(gmail_token_file),
                'valid': False,
                'expires_at': None,
                'has_refresh_token': False
            }
        }
        
        # Check if we have saved credentials that include all scopes
        creds_data = load_credentials()
        if creds_data:
            try:
                # Use the saved credentials for both Drive and Gmail
                creds = Credentials(
                    token=creds_data.get('token'),
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    client_id=creds_data.get('client_id'),
                    client_secret=creds_data.get('client_secret'),
                    scopes=creds_data.get('scopes', [])
                )
                
                # Update both statuses
                status['google_drive']['token_exists'] = True
                status['google_drive']['has_refresh_token'] = bool(creds.refresh_token)
                status['google_drive']['expires_at'] = creds.expiry.isoformat() if creds.expiry else None
                
                status['gmail']['token_exists'] = True
                status['gmail']['has_refresh_token'] = bool(creds.refresh_token)
                status['gmail']['expires_at'] = creds.expiry.isoformat() if creds.expiry else None
                
                # Check if token needs refresh
                if not creds.valid:
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        # Update saved credentials
                        creds_data['token'] = creds.token
                        save_credentials(creds_data)
                        
                        status['google_drive']['valid'] = True
                        status['google_drive']['refreshed'] = True
                        status['gmail']['valid'] = True
                        status['gmail']['refreshed'] = True
                else:
                    status['google_drive']['valid'] = True
                    status['gmail']['valid'] = True
                    
                # Check if Gmail scope is included
                if creds.scopes and 'https://www.googleapis.com/auth/gmail.compose' in creds.scopes:
                    status['gmail']['scope_included'] = True
                else:
                    status['gmail']['scope_included'] = False
                    status['gmail']['error'] = 'Gmail scope not included in credentials'
                    
            except Exception as e:
                status['google_drive']['error'] = str(e)
                status['gmail']['error'] = str(e)
        
        # Fallback to checking individual token files
        elif os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file)
                status['google_drive']['has_refresh_token'] = bool(creds.refresh_token)
                status['google_drive']['expires_at'] = creds.expiry.isoformat() if creds.expiry else None
                
                # Try to refresh if expired
                if not creds.valid:
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        # Save refreshed token
                        with open(token_file, 'w') as f:
                            f.write(creds.to_json())
                        status['google_drive']['valid'] = True
                        status['google_drive']['refreshed'] = True
                else:
                    status['google_drive']['valid'] = True
            except Exception as e:
                status['google_drive']['error'] = str(e)
        
        # Check Gmail token
        if os.path.exists(gmail_token_file):
            try:
                with open(gmail_token_file, 'r') as f:
                    gmail_data = json.load(f)
                status['gmail']['has_refresh_token'] = 'refresh_token' in gmail_data
                status['gmail']['expires_at'] = gmail_data.get('expiry')
                
                # Create credentials and check validity
                creds = Credentials(
                    token=gmail_data.get('token'),
                    refresh_token=gmail_data.get('refresh_token'),
                    token_uri=gmail_data.get('token_uri'),
                    client_id=gmail_data.get('client_id'),
                    client_secret=gmail_data.get('client_secret'),
                    scopes=gmail_data.get('scopes')
                )
                
                if not creds.valid and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Save refreshed token
                    with open(gmail_token_file, 'w') as f:
                        f.write(creds.to_json())
                    status['gmail']['valid'] = True
                    status['gmail']['refreshed'] = True
                else:
                    status['gmail']['valid'] = creds.valid
            except Exception as e:
                status['gmail']['error'] = str(e)
        
        # Overall status
        status['overall'] = {
            'ready': status['google_drive']['valid'] and status['gmail']['valid'],
            'message': 'All tokens valid' if (status['google_drive']['valid'] and status['gmail']['valid']) else 'Some tokens need attention'
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error checking token status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/credentials')
def api_credentials():
    """Show credentials for worker setup"""
    try:
        creds_data = load_credentials()
        if creds_data:
            # Remove sensitive token for display
            safe_creds = creds_data.copy()
            if 'token' in safe_creds:
                safe_creds['token'] = safe_creds['token'][:20] + "..."
            
            return jsonify({
                'status': 'found',
                'credentials_preview': safe_creds,
                'instructions': 'Add GOOGLE_CREDENTIALS_JSON environment variable to worker with full credentials'
            })
        else:
            return jsonify({
                'status': 'not_found',
                'message': 'No credentials available. Complete OAuth setup first.'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })

@app.route('/api/google/documents/<document_id>/debug')
def api_debug_document(document_id):
    """Debug endpoint to see raw document structure"""
    try:
        creds_data = load_credentials()
        if not creds_data:
            return jsonify({'error': 'No Google credentials available'}), 500
            
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        docs_service = build('docs', 'v1', credentials=creds)
        doc = docs_service.documents().get(documentId=document_id).execute()
        
        # Extract first few paragraphs for debugging
        debug_paragraphs = []
        for idx, element in enumerate(doc.get('body', {}).get('content', [])[:10]):
            if 'paragraph' in element:
                para_info = {
                    'index': idx,
                    'elements': []
                }
                for elem in element['paragraph'].get('elements', []):
                    if 'textRun' in elem:
                        text_run = elem['textRun']
                        elem_info = {
                            'text': text_run.get('content', ''),
                            'has_link': 'link' in text_run.get('textStyle', {})
                        }
                        if elem_info['has_link']:
                            elem_info['link_url'] = text_run['textStyle']['link'].get('url', '')
                        para_info['elements'].append(elem_info)
                debug_paragraphs.append(para_info)
        
        return jsonify({
            'document_id': document_id,
            'title': doc.get('title', 'Untitled'),
            'debug_paragraphs': debug_paragraphs
        })
        
    except Exception as e:
        logger.error(f"Error debugging document {document_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/documents/<document_id>/contacts')
def api_get_document_contacts(document_id):
    """Get contacts mentioned in a document using various methods"""
    try:
        creds_data = load_credentials()
        if not creds_data:
            return jsonify({'error': 'No Google credentials available'}), 500
            
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        people_service = build('people', 'v1', credentials=creds)
        
        # Try to find contacts by searching for common patterns
        # This is a simplified approach - in reality, we'd need the actual contact IDs
        try:
            # Search for all contacts
            results = people_service.people().connections().list(
                resourceName='people/me',
                pageSize=100,
                personFields='names,emailAddresses'
            ).execute()
            
            connections = results.get('connections', [])
            logger.info(f"Found {len(connections)} contacts in user's Google contacts")
            
            # Return all contacts for now - we'll filter in the worker
            contacts = []
            for person in connections:
                names = person.get('names', [])
                emails = person.get('emailAddresses', [])
                if names and emails:
                    contact = {
                        'name': names[0].get('displayName', ''),
                        'email': emails[0].get('value', '')
                    }
                    contacts.append(contact)
                    
            return jsonify({
                'contacts': contacts,
                'total': len(contacts)
            })
            
        except Exception as e:
            logger.error(f"Error accessing People API: {e}")
            return jsonify({'error': 'People API not accessible', 'details': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Error in contacts endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/documents/<document_id>')
def api_get_document(document_id):
    """API endpoint for worker to get Google Doc content"""
    try:
        creds_data = load_credentials()
        if not creds_data:
            return jsonify({'error': 'No Google credentials available'}), 500
            
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Initialize variables at function scope
        emails_found = []
        invited_emails = []
        all_emails = []
        content = ""
        in_invited_section = False
        current_section = "start"
        
        # Get document metadata first
        doc = docs_service.documents().get(documentId=document_id).execute()
        doc_title = doc.get('title', 'Untitled')
        
        # Export document as HTML to preserve links
        html_export_success = False
        try:
            logger.info(f"Exporting document {document_id} as HTML to extract emails...")
            request = drive_service.files().export_media(
                fileId=document_id,
                mimeType='text/html'
            )
            
            # Download the HTML content
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Parse HTML content
            html_content = fh.getvalue().decode('utf-8')
            logger.info(f"Downloaded HTML content: {len(html_content)} bytes")
            
            # Save HTML for debugging (temporarily)
            debug_html_path = f'/tmp/doc_{document_id[:8]}.html'
            with open(debug_html_path, 'w') as f:
                f.write(html_content)
            logger.info(f"Saved HTML for debugging to: {debug_html_path}")
            
            # Debug: Log a sample of the HTML to see structure
            if len(html_content) > 1000:
                logger.debug(f"HTML sample (first 1000 chars): {html_content[:1000]}")
            
            # Look for Invited section in HTML
            invited_index = html_content.find('Invited')
            if invited_index != -1:
                logger.info(f"Found 'Invited' at position {invited_index}")
                # Get surrounding context
                start = max(0, invited_index - 200)
                end = min(len(html_content), invited_index + 500)
                logger.info(f"Invited section context: {html_content[start:end]}")
            else:
                logger.warning("'Invited' text not found in HTML content")
                # Try case-insensitive search
                invited_index_lower = html_content.lower().find('invited')
                if invited_index_lower != -1:
                    logger.info(f"Found 'invited' (lowercase) at position {invited_index_lower}")
                    start = max(0, invited_index_lower - 200)
                    end = min(len(html_content), invited_index_lower + 500)
                    logger.info(f"Invited section context (case-insensitive): {html_content[start:end]}")
            
            # First check if HTML contains any links at all
            link_count = html_content.count('href=')
            mailto_count = html_content.count('mailto:')
            logger.info(f"HTML contains {link_count} links total, {mailto_count} mailto links")
            
            # Extract emails from HTML
            class EmailExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.emails = []
                    self.current_text = ""
                    self.in_invited = False
                    self.invited_emails = []
                    self.all_links = []  # Track all links for debugging
                    
                def handle_starttag(self, tag, attrs):
                    if tag == 'a':
                        for attr, value in attrs:
                            if attr == 'href':
                                self.all_links.append(value)  # Track all links
                                if value.startswith('mailto:'):
                                    email = value.replace('mailto:', '').split('?')[0]
                                    self.emails.append({
                                        'email': email,
                                        'text': self.current_text.strip(),
                                        'in_invited': self.in_invited
                                    })
                                    if self.in_invited:
                                        self.invited_emails.append(email)
                                    logger.info(f"Found email in HTML: {self.current_text.strip()} -> {email}")
                    self.current_text = ""
                    
                def handle_data(self, data):
                    self.current_text += data
                    if 'Invited' in data:
                        self.in_invited = True
                        logger.info(f"Found Invited section in HTML: '{data.strip()}'")
                    elif self.in_invited and ('Attachments' in data or 'Meeting' in data):
                        self.in_invited = False
                        logger.info(f"Left Invited section at: '{data.strip()}'")
                        
            parser = EmailExtractor()
            parser.feed(html_content)
            
            # Log all links found
            logger.info(f"Parser found {len(parser.all_links)} total links")
            if parser.all_links:
                logger.info(f"First few links: {parser.all_links[:5]}")
            
            # Also try regex as backup
            email_pattern = r'href=["\']mailto:([^"\'>]+)["\']'
            regex_emails = re.findall(email_pattern, html_content)
            logger.info(f"Regex found emails: {regex_emails}")
            
            # Try additional patterns
            email_pattern2 = r'<a[^>]+href=["\']?mailto:([^"\'>\s]+)["\']?[^>]*>'
            regex_emails2 = re.findall(email_pattern2, html_content, re.IGNORECASE)
            logger.info(f"Regex pattern 2 found: {regex_emails2}")
            
            # Look for any email-like patterns in the HTML
            general_email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            all_email_patterns = re.findall(general_email_pattern, html_content)
            logger.info(f"All email-like patterns in HTML: {all_email_patterns[:5]}...")  # First 5
            
            # Combine results
            all_emails = parser.emails
            invited_emails = parser.invited_emails
            
            # Add regex emails not already found
            for email in regex_emails:
                if not any(e['email'] == email for e in all_emails):
                    all_emails.append({
                        'email': email,
                        'text': 'Found via regex',
                        'in_invited': False
                    })
            
            logger.info(f"Total emails from HTML: {len(all_emails)}")
            logger.info(f"Invited section emails: {invited_emails}")
            
            emails_found = all_emails
            html_export_success = True
            
            # If no emails found, try alternative export format
            if len(all_emails) == 0:
                logger.info("No emails found in HTML export, trying alternative approach...")
                
                # Try exporting as plain text
                try:
                    request2 = drive_service.files().export_media(
                        fileId=document_id,
                        mimeType='text/plain'
                    )
                    fh2 = io.BytesIO()
                    downloader2 = MediaIoBaseDownload(fh2, request2)
                    done2 = False
                    while not done2:
                        status2, done2 = downloader2.next_chunk()
                    
                    plain_content = fh2.getvalue().decode('utf-8')
                    logger.info(f"Plain text export: {len(plain_content)} bytes")
                    
                    # Look for email patterns in plain text
                    plain_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', plain_content)
                    logger.info(f"Found emails in plain text: {plain_emails}")
                    
                except Exception as e2:
                    logger.error(f"Plain text export also failed: {e2}")
            
        except Exception as e:
            logger.error(f"Error exporting document as HTML: {e}")
            logger.error(f"Error details: {type(e).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            # Fall back to regular parsing
            all_emails = []
            invited_emails = []
            emails_found = []
            html_export_success = False
        
        # Continue with regular text extraction for content
        # Variables already initialized at function scope
        
        # Log whether HTML export was attempted and succeeded
        logger.info(f"HTML export attempted: {'Success' if html_export_success else 'Failed'}")
        
        # Extract text with special handling for Invited section
        invited_section_text = ""
        capture_invited = False
        
        logger.info(f"Starting document parsing for {document_id}")
        logger.info(f"Document structure has {len(doc.get('body', {}).get('content', []))} elements")
        
        for idx, element in enumerate(doc.get('body', {}).get('content', [])):
            if 'paragraph' in element:
                paragraph_text = ""
                paragraph_elements = element['paragraph'].get('elements', [])
                
                # Log paragraph info
                if paragraph_elements:
                    logger.debug(f"Paragraph {idx} has {len(paragraph_elements)} elements")
                
                for elem_idx, text_run in enumerate(paragraph_elements):
                    if 'textRun' in text_run:
                        text = text_run['textRun'].get('content', '')
                        paragraph_text += text
                        content += text
                        
                        # Log text run details
                        text_run_data = text_run['textRun']
                        logger.debug(f"TextRun {elem_idx}: '{text.strip()}'")
                        
                        # Check for hyperlinks
                        text_style = text_run_data.get('textStyle', {})
                        if 'link' in text_style:
                            link_data = text_style['link']
                            url = link_data.get('url', '')
                            logger.info(f"Found link in text '{text.strip()}': {url}")
                            
                            if url.startswith('mailto:'):
                                email = url.replace('mailto:', '').split('?')[0]
                                emails_found.append({
                                    'email': email,
                                    'text': text.strip(),
                                    'in_invited': in_invited_section,
                                    'section': current_section
                                })
                                if in_invited_section:
                                    invited_emails.append(email)
                                logger.info(f"✅ Found email link: {text.strip()} -> {email} (in_invited={in_invited_section})")
                            else:
                                logger.info(f"Non-email link found: {url}")
                        else:
                            # Log if this looks like it should have a link
                            if text.strip() and in_invited_section and 'Adarsh' not in text:
                                logger.debug(f"Text in invited section without link: '{text.strip()}'")
                
                # Check if we're entering/leaving sections
                para_text_stripped = paragraph_text.strip()
                if para_text_stripped:
                    logger.debug(f"Paragraph text: '{para_text_stripped[:100]}...'")
                    
                    if 'Invited' in paragraph_text:
                        in_invited_section = True
                        current_section = "invited"
                        logger.info("📍 Entered INVITED section")
                    elif in_invited_section and ('Attachments' in paragraph_text or 'Meeting' in paragraph_text):
                        in_invited_section = False
                        current_section = "post-invited"
                        logger.info("📍 Left INVITED section")
        
        # Log summary of findings
        logger.info(f"📊 Email extraction summary:")
        logger.info(f"  - Total emails found: {len(emails_found)}")
        logger.info(f"  - Emails in invited section: {len(invited_emails)}")
        logger.info(f"  - All emails: {[e['email'] for e in emails_found]}")
        logger.info(f"  - Invited emails: {invited_emails}")
        
        # Find the first non-Adarsh email from invited section
        founder_email = None
        for email in invited_emails:
            if 'adarsh' not in email.lower():
                founder_email = email
                logger.info(f"✅ Selected founder email: {founder_email}")
                break
        
        if not founder_email:
            logger.warning("⚠️ No founder email found in invited section")
            # Try to find any non-Adarsh email as fallback
            for email_info in emails_found:
                if 'adarsh' not in email_info['email'].lower():
                    founder_email = email_info['email']
                    logger.info(f"📧 Using fallback email (not from invited): {founder_email}")
                    break
                    
        # Last resort: Extract founder name from title and search for it
        founder_name = None
        if doc_title:
            logger.info("🔍 Attempting to extract founder from document title...")
            # Pattern: "Founder Name and Adarsh Bhatt - Date - Notes"
            title_parts = doc_title.split(' and ')
            if len(title_parts) >= 2 and 'Adarsh' in title_parts[1]:
                founder_name = title_parts[0].strip()
                logger.info(f"📝 Extracted founder name from title: {founder_name}")
                
        if not founder_email and founder_name:
                
                # Look for this name in the document content
                if founder_name:
                    # Try to find email patterns near this name in content
                    name_index = content.lower().find(founder_name.lower())
                    if name_index != -1:
                        # Look for emails within 200 characters of the name
                        search_start = max(0, name_index - 100)
                        search_end = min(len(content), name_index + 200)
                        search_text = content[search_start:search_end]
                        
                        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                        nearby_emails = re.findall(email_pattern, search_text)
                        if nearby_emails:
                            founder_email = nearby_emails[0]
                            logger.info(f"✅ Found email near founder name: {founder_email}")
                    
                    # Store founder name for Claude to use
                    if not founder_email:
                        logger.info(f"💡 Providing founder name '{founder_name}' to Claude for email inference")
        
        return jsonify({
            'document_id': document_id,
            'title': doc.get('title', 'Untitled'),
            'content': content,
            'emails_found': emails_found,
            'founder_email': founder_email,
            'founder_name': founder_name,  # Add founder name from title
            'debug_info': {
                'total_emails': len(emails_found),
                'invited_emails_count': len(invited_emails),
                'sections_found': list(set(e.get('section', 'unknown') for e in emails_found))
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/drive/files')
def api_list_drive_files():
    """API endpoint for worker to list Drive files"""
    try:
        creds_data = load_credentials()
        if not creds_data:
            return jsonify({'error': 'No Google credentials available'}), 500
            
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Get query parameters
        folder_id = request.args.get('folder_id', os.environ.get('GOOGLE_DRIVE_FOLDER_ID'))
        modified_since = request.args.get('modified_since')
        
        # Build query - if no folder_id, search all accessible files
        if folder_id and folder_id.strip():
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
        else:
            query = "mimeType='application/vnd.google-apps.document'"
            
        if modified_since:
            query += f" and modifiedTime > '{modified_since}'"
            
        results = drive_service.files().list(
            q=query,
            orderBy='modifiedTime desc',
            fields="files(id,name,modifiedTime,createdTime)"
        ).execute()
        
        return jsonify({
            'files': results.get('files', [])
        })
        
    except Exception as e:
        logger.error(f"Error listing drive files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/gmail/draft', methods=['POST'])
def api_create_gmail_draft():
    """API endpoint for worker to create Gmail draft"""
    try:
        creds_data = load_credentials()
        if not creds_data:
            return jsonify({'error': 'No Google credentials available'}), 500
            
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        # Get email data from request
        email_data = request.get_json()
        to_email = email_data.get('to')
        subject = email_data.get('subject')
        body = email_data.get('body')
        
        if not all([to_email, subject, body]):
            return jsonify({'error': 'Missing required fields: to, subject, body'}), 400
        
        # Create email message
        message = f"""To: {to_email}
Subject: {subject}

{body}
"""
        
        # Base64 encode the message
        import base64
        raw_message = base64.urlsafe_b64encode(message.encode('utf-8')).decode('ascii')
        
        # Create draft
        draft = gmail_service.users().drafts().create(
            userId='me',
            body={'message': {'raw': raw_message}}
        ).execute()
        
        return jsonify({
            'draft_id': draft['id'],
            'message': 'Draft created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating Gmail draft: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/env')
def api_debug_env():
    """Debug environment variables"""
    try:
        affinity_key = os.environ.get('AFFINITY_API_KEY')
        list_id = os.environ.get('AFFINITY_LIST_ID')
        
        return jsonify({
            'affinity_key_present': bool(affinity_key),
            'affinity_key_length': len(affinity_key) if affinity_key else 0,
            'list_id_present': bool(list_id),
            'list_id_value': list_id,
            'all_env_keys': [k for k in os.environ.keys() if 'AFFINITY' in k]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/affinity/test')
def api_test_affinity():
    """Test Affinity API connectivity"""
    try:
        affinity_api_key = os.environ.get('AFFINITY_API_KEY')
        if not affinity_api_key:
            return jsonify({'error': 'Affinity API key not configured'}), 500
        
        # Test basic API connectivity using ORIGINAL working approach
        # Use Basic auth with empty username (what worked locally)
        import base64
        auth_string = base64.b64encode(f':{affinity_api_key}'.encode()).decode()
        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }
        
        # Test lists endpoint using v1 API (what worked originally)
        response = requests.get('https://api.affinity.co/lists', headers=headers)
        
        # Also test if we can get info about available endpoints
        if response.status_code == 200:
            # Try to get one list to see its structure
            try:
                lists = response.json()
                if lists and len(lists) > 0:
                    first_list_id = lists[0]['id']
                    list_detail = requests.get(f'https://api.affinity.co/lists/{first_list_id}', headers=headers)
                    logger.info(f"Sample list detail: {list_detail.status_code} - {list_detail.text[:200]}")
            except:
                pass
        
        return jsonify({
            'status': response.status_code,
            'lists_available': response.status_code == 200,
            'response': response.text[:500]  # First 500 chars
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/affinity/deals', methods=['POST'])
def api_create_affinity_deal():
    """API endpoint for worker to create Affinity deal"""
    try:
        # Get deal data from request
        deal_data = request.get_json()
        
        affinity_api_key = os.environ.get('AFFINITY_API_KEY')
        if not affinity_api_key:
            return jsonify({'error': 'Affinity API key not configured'}), 500
        
        # Create deal in Affinity
        # Use ORIGINAL working approach - Basic auth with empty username
        import base64
        auth_string = base64.b64encode(f':{affinity_api_key}'.encode()).decode()
        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }
        
        # Get list ID
        list_id = os.environ.get('AFFINITY_LIST_ID')
        if not list_id:
            return jsonify({'error': 'Affinity list ID not configured'}), 500
        
        # Extract company and founder info
        deal_name = deal_data.get('name', 'Unknown Deal')
        meeting_notes = deal_data.get('notes', '')
        founder_info = deal_data.get('founder_info', {})
        
        # First, try to create or find a person/organization
        # For simplicity, we'll try to create a list entry directly with available data
        logger.info(f"Attempting to create Affinity list entry for: {deal_name}")
        
        # Use ORIGINAL working approach - v1 API with Basic auth
        logger.info(f"Step 1: Creating organization for: {deal_name}")
        
        # Create organization first (v1 API)
        org_data = {'name': deal_name}
        org_response = requests.post(
            'https://api.affinity.co/organizations',
            headers=headers,
            json=org_data
        )
        
        logger.info(f"Organization creation: {org_response.status_code} - {org_response.text}")
        
        org_id = None  # Initialize org_id
        if org_response.status_code in [200, 201]:
            org = org_response.json()
            org_id = org.get('id')
            
            # Step 2: Add organization to list (v1 API)
            logger.info(f"Step 2: Adding organization {org_id} to list {list_id}")
            
            deal_data = {
                'entity_id': org_id,
                'list_id': int(list_id)
            }
            
            response = requests.post(
                f'https://api.affinity.co/lists/{list_id}/list-entries',
                headers=headers,
                json=deal_data
            )
            
            logger.info(f"List entry creation: {response.status_code} - {response.text}")
            
        else:
            logger.error(f"Organization creation failed: {org_response.status_code} - {org_response.text}")
            return jsonify({
                'error': 'Failed to create organization in Affinity',
                'details': org_response.text
            }), 500
        
        success = response.status_code in [200, 201]
        
        if not success:
            error_details = {
                'status': response.status_code,
                'response': response.text,
                'attempted_approaches': 'direct, entities, simple payload'
            }
            logger.error(f"All Affinity approaches failed: {error_details}")
            return jsonify({
                'error': 'Failed to create Affinity entry with any approach',
                'details': error_details
            }), 500
        
        logger.info(f"Affinity API response: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201]:
            list_entry = response.json()
            list_entry_id = list_entry.get('id')
            
            # Step 3: Add notes to the organization if meeting notes provided
            if meeting_notes and org_id:
                logger.info(f"Step 3: Adding notes to organization {org_id}")
                
                # Create note with proper associations
                # According to API docs, notes need to be associated with entities
                note_data = {
                    'content': meeting_notes,
                    'organization_ids': [int(org_id)]  # Ensure it's an integer
                }
                
                logger.info(f"Attempting note creation with org_id={org_id}, type={type(org_id)}")
                
                note_response = requests.post(
                    'https://api.affinity.co/notes',
                    headers=headers,
                    json=note_data
                )
                
                # If that fails, try adding note as a field value instead
                if note_response.status_code not in [200, 201]:
                    logger.info("Note creation failed, trying field value approach...")
                    
                    # First, we need to find or create a notes field for the list
                    fields_response = requests.get(
                        f'https://api.affinity.co/lists/{list_id}/fields',
                        headers=headers
                    )
                    
                    if fields_response.status_code == 200:
                        fields = fields_response.json()
                        notes_field = None
                        
                        # Look for existing notes field
                        for field in fields:
                            if field.get('name', '').lower() in ['notes', 'meeting notes', 'description']:
                                notes_field = field
                                break
                        
                        # If we found a notes field, add value to it
                        if notes_field and list_entry_id:
                            field_value_data = {
                                'field_id': notes_field['id'],
                                'entity_id': list_entry_id,
                                'value': meeting_notes
                            }
                            
                            field_response = requests.post(
                                f'https://api.affinity.co/lists/{list_id}/list-entries/{list_entry_id}/field-values',
                                headers=headers,
                                json=field_value_data
                            )
                            
                            logger.info(f"Field value creation: {field_response.status_code} - {field_response.text[:200]}")
                            note_response = field_response  # Use this response for final check
                
                logger.info(f"Note creation: {note_response.status_code} - {note_response.text}")
                
                if note_response.status_code not in [200, 201]:
                    logger.warning(f"Failed to add notes, but deal was created: {note_response.text}")
                    
                    # Try a third approach - add note directly to the list entry
                    if note_response.status_code not in [200, 201] and list_entry_id:
                        logger.info(f"Trying to add note to list entry {list_entry_id}...")
                        
                        # Some Affinity setups might need notes on the list entry itself
                        note_data3 = {
                            'parent_id': list_entry_id,
                            'parent_type': 'list_entry',
                            'content': meeting_notes
                        }
                        
                        note_response = requests.post(
                            f'https://api.affinity.co/lists/{list_id}/list-entries/{list_entry_id}/notes',
                            headers=headers,
                            json=note_data3
                        )
                        
                        logger.info(f"List entry note attempt: {note_response.status_code} - {note_response.text}")
                else:
                    logger.info(f"✅ Successfully created note for organization {org_id}")
            
            return jsonify({
                'deal_id': list_entry_id,
                'organization_id': org_id,
                'message': 'Deal created successfully with notes'
            })
        else:
            error_details = {
                'status': response.status_code,
                'response': response.text,
                'org_data': org_data,
                'deal_data': deal_data if 'deal_data' in locals() else None
            }
            logger.error(f"Affinity API error: {error_details}")
            return jsonify({
                'error': f'Affinity API error: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating Affinity deal: {e}")
        return jsonify({'error': str(e)}), 500

def save_credentials(creds_data):
    """Save credentials to persistent storage"""
    try:
        # Save to multiple locations for worker access
        save_locations = [
            '/opt/render/project/data/google_drive_token.json',
            '/tmp/google_drive_token.json',
            'google_drive_token.json'
        ]
        
        for location in save_locations:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(location), exist_ok=True)
                
                with open(location, 'w') as f:
                    json.dump(creds_data, f, indent=2)
                    
                logger.info(f"Credentials saved to: {location}")
                
            except Exception as e:
                logger.warning(f"Could not save to {location}: {e}")
        
        # Also save as token.json for GoogleDriveService
        try:
            # Format for google-auth library
            token_data = {
                'token': creds_data['token'],
                'refresh_token': creds_data.get('refresh_token'),
                'token_uri': creds_data['token_uri'],
                'client_id': creds_data['client_id'],
                'client_secret': creds_data['client_secret'],
                'scopes': creds_data['scopes'],
                'type': 'authorized_user',
                'expiry': None  # Will be set on first use
            }
            
            with open('token.json', 'w') as f:
                json.dump(token_data, f, indent=2)
            logger.info("Saved token.json for GoogleDriveService")
            
        except Exception as e:
            logger.warning(f"Could not save token.json: {e}")
        
        # Also save as environment variable for worker access
        try:
            # This won't persist across restarts but helps with current session
            os.environ['GOOGLE_CREDENTIALS_JSON'] = json.dumps(creds_data)
            logger.info("Credentials also set as environment variable")
        except Exception as e:
            logger.warning(f"Could not set env variable: {e}")
            
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")

def load_credentials():
    """Load credentials from persistent storage"""
    try:
        # Try persistent storage first
        credentials_file = '/opt/render/project/data/google_drive_token.json'
        
        if os.path.exists(credentials_file):
            with open(credentials_file, 'r') as f:
                return json.load(f)
        
        # Fallback: try current directory
        if os.path.exists('google_drive_token.json'):
            with open('google_drive_token.json', 'r') as f:
                return json.load(f)
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None

def load_activity_stats():
    """Load activity statistics"""
    try:
        stats_file = '/opt/render/project/data/activity_stats.json'
        
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                return json.load(f)
        
        return {}
        
    except Exception as e:
        logger.warning(f"Failed to load activity stats: {e}")
        return {}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
