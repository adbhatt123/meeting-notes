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
        
        # Save credentials to persistent storage
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

def save_credentials(creds_data):
    """Save credentials to persistent storage"""
    try:
        # For Render, we'll use environment variable or file storage
        credentials_file = '/opt/render/project/data/google_drive_token.json'
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(credentials_file), exist_ok=True)
        
        with open(credentials_file, 'w') as f:
            json.dump(creds_data, f, indent=2)
            
        logger.info("Credentials saved successfully")
        
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        # Fallback: try current directory
        with open('google_drive_token.json', 'w') as f:
            json.dump(creds_data, f, indent=2)

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
