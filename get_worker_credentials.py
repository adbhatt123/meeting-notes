#!/usr/bin/env python3
"""
Generate Google credentials for worker service
Run this locally to get credentials JSON for worker
"""

import json
import requests
import os

def create_worker_credentials():
    """Create credentials JSON for worker service"""
    
    print("🔐 Creating Worker Credentials")
    print("=" * 30)
    
    # Get auth code from user
    print("\n📋 Step 1: Get Authorization Code")
    print("1. Visit this URL in your browser:")
    
    oauth_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        "response_type=code&"
        "client_id=692564957219-7cu8hl61ohf8gjbembu5v6semrtugs16.apps.googleusercontent.com&"
        "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2F&"
        "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.compose+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.readonly+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdocuments.readonly&"
        "prompt=consent&access_type=offline"
    )
    
    print(oauth_url)
    print("\n2. Copy the authorization code from the redirect URL")
    print("3. Paste it below:")
    
    auth_code = input("\nAuthorization code: ").strip()
    
    if not auth_code:
        print("❌ No code provided")
        return
    
    # Exchange for tokens
    print("\n🔄 Exchanging code for tokens...")
    
    client_id = "692564957219-7cu8hl61ohf8gjbembu5v6semrtugs16.apps.googleusercontent.com"
    client_secret = "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"
    
    token_data = {
        'code': auth_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'http://localhost:8080/',
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        
        if response.status_code != 200:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(response.text)
            return
        
        tokens = response.json()
        
        # Create credentials JSON
        creds_json = {
            "token": tokens['access_token'],
            "refresh_token": tokens.get('refresh_token'),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": [
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/documents.readonly"
            ]
        }
        
        print("✅ Credentials created successfully!")
        print("\n📋 Add this to your worker environment variables:")
        print("Key: GOOGLE_CREDENTIALS_JSON")
        print("Value:")
        print(json.dumps(creds_json, indent=2))
        
        print("\n🚀 Steps:")
        print("1. Copy the JSON above")
        print("2. Go to Render → worker service → Environment")
        print("3. Add GOOGLE_CREDENTIALS_JSON with the JSON as value")
        print("4. Save changes")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    create_worker_credentials()