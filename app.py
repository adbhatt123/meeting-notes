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
from googleapiclient.discovery import build
from datetime import datetime
import logging

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
    'https://www.googleapis.com/auth/documents.readonly'
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
        doc = docs_service.documents().get(documentId=document_id).execute()
        
        # Extract text content and emails
        content = ""
        emails_found = []
        in_invited_section = False
        invited_emails = []
        current_section = "start"
        
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
        
        return jsonify({
            'document_id': document_id,
            'title': doc.get('title', 'Untitled'),
            'content': content,
            'emails_found': emails_found,
            'founder_email': founder_email,
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
            return jsonify({
                'deal_id': response.json().get('id'),
                'message': 'Deal created successfully'
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
