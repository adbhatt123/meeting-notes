# 🚀 VC Workflow Automation

**✅ PRODUCTION READY - Successfully tested with real meeting documents**

Automates the end-to-end VC workflow: monitors Google Drive for new meeting notes, extracts founder information using AI, creates/updates deals in Affinity CRM, and drafts personalized follow-up emails.

## 🎉 Proven Results

**Successfully tested today with real meeting documents:**
- ✅ **Processed**: Arjun Mehta's actual meeting notes
- ✅ **Created**: Multiple deals in Affinity CRM (vinciprojects.co)
- ✅ **Generated**: Personalized follow-up emails with next steps
- ✅ **Implemented**: All business rules working correctly
- ✅ **Ready**: For immediate production deployment

## Features

🤖 **AI-Powered Extraction**: Uses Claude to extract founder/company info and meeting summaries  
📁 **Google Drive Monitoring**: Automatically detects new meeting notes in specified folders  
🔗 **Affinity CRM Integration**: Creates/updates deals with formatted meeting notes  
📧 **Email Automation**: Drafts personalized follow-up emails with Gmail API  
⏰ **Scheduled Processing**: Runs automatically at configurable intervals  
🐳 **Multiple Deployment Options**: Local, systemd service, or Docker  

## Quick Start

### 1. Setup

```bash
# Clone and navigate to project
cd vc-workflow-automation

# Run setup script
python setup.py
```

### 2. Configuration

Edit `.env` file with your API credentials:

```env
# Google APIs
GOOGLE_DRIVE_FOLDER_ID=your_meeting_notes_folder_id
GOOGLE_CREDENTIALS_PATH=credentials.json

# Affinity CRM
AFFINITY_API_KEY=your_affinity_api_key
AFFINITY_PIPELINE_ID=your_dealflow_pipeline_id

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key

# Email
FROM_EMAIL=your_email@domain.com
FROM_NAME=Your Name
```

### 3. Google API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable Google Drive API and Gmail API
4. Create credentials (OAuth 2.0 or Service Account)
5. Download `credentials.json` to project root

### 4. Get Google Drive Folder ID

The folder ID is in the URL when viewing your folder:
```
https://drive.google.com/drive/folders/[FOLDER_ID_HERE]
```

### 5. Run

```bash
# Test connections
python main.py --mode test

# Run once
python main.py --mode run

# Run on schedule (every 15 minutes by default)
python main.py --mode schedule

# Preview processing for specific document
python main.py --mode preview --doc-id YOUR_DOC_ID
```

## How It Works

### 1. Document Monitoring
- Monitors specified Google Drive folder for new Google Docs
- Tracks processed documents to avoid duplicates
- Extracts full text content from documents

### 2. AI-Powered Parsing
- Uses Claude to extract:
  - Founder name and email
  - Company name and description
  - Company stage and sector
  - Meeting key points and action items
  - Ways the VC can help

### 3. CRM Integration
- Searches for existing deals by company/founder name
- Creates new deals or updates existing ones
- Formats meeting notes with structured information
- Links to original Google Doc

### 4. Email Automation
- Generates personalized follow-up emails
- References specific discussion points
- Suggests concrete ways to help
- Creates Gmail drafts for review before sending

## Configuration Options

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_DRIVE_FOLDER_ID` | ID of folder to monitor | Yes |
| `GOOGLE_CREDENTIALS_PATH` | Path to Google credentials file | Yes |
| `AFFINITY_API_KEY` | Affinity CRM API key | Yes |
| `AFFINITY_PIPELINE_ID` | ID of your dealflow pipeline | Yes |
| `ANTHROPIC_API_KEY` | Anthropic/Claude API key | Yes |
| `FROM_EMAIL` | Your email address | Yes |
| `FROM_NAME` | Your name for emails | Yes |
| `CHECK_INTERVAL_MINUTES` | How often to check for new docs | No (default: 15) |

### Meeting Note Format

The system works best with meeting notes that include:
- Founder name in title or top of document
- Company name clearly mentioned
- Discussion points about the business
- Any asks from the founder
- Action items or next steps

Example document title formats:
- "Meeting with John Smith - Acme Corp - 2024-01-15"
- "John Smith (Acme Corp) - Founder Meeting"
- "Acme Corp - John Smith - Series A Discussion"

## Deployment Options

### 🚀 Option 1: Render Cloud Deployment (Recommended - PRODUCTION READY)

**Professional 24/7 cloud deployment with monitoring dashboard**

- ✅ **Always-on monitoring** - No local machine required
- ✅ **Professional OAuth handling** - No localhost issues  
- ✅ **Web dashboard** - Monitor system status and activity
- ✅ **Automatic scaling** - Handle increased document volume
- ✅ **SSL certificates** - Secure HTTPS endpoints
- ✅ **Cost**: ~$15/month for professional automation

👉 **[Complete Render Deployment Guide](RENDER_DEPLOYMENT_GUIDE.md)**

### Option 2: Local Development & Testing
```bash
# Test with proven working components
python3 test_arjun_meeting_with_notes.py     # Real meeting test
python3 test_complete_automation.py          # End-to-end simulation
python3 run_automation.py                    # Local continuous monitoring
```

### Option 3: Systemd Service (Linux)
```bash
# Copy service file
sudo cp vc-workflow.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable vc-workflow
sudo systemctl start vc-workflow

# Check status
sudo systemctl status vc-workflow
```

### Option 4: Docker
```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## API Integrations

### Google Drive API
- **Scopes**: `drive.readonly`, `documents.readonly`
- **Usage**: Monitor folder, extract document content
- **Authentication**: OAuth 2.0 or Service Account

### Affinity CRM API
- **Endpoints**: Organizations, Opportunities (Deals)
- **Usage**: Create/update deals, search existing records
- **Authentication**: API Key

### Gmail API
- **Scopes**: `gmail.compose`
- **Usage**: Create draft emails
- **Authentication**: OAuth 2.0

### Anthropic API
- **Model**: Claude 3 Haiku
- **Usage**: Extract structured data, generate emails
- **Authentication**: API Key

## Troubleshooting

### Common Issues

**Google Drive Access Denied**
- Ensure credentials file has correct permissions
- Check that APIs are enabled in Google Cloud Console
- Verify folder ID is correct and accessible

**Affinity API Errors**
- Confirm API key is valid and has necessary permissions
- Check pipeline ID exists and is accessible
- Verify deal name format doesn't conflict with existing deals

**Email Drafts Not Created**
- Ensure Gmail API is enabled
- Check that FROM_EMAIL matches authenticated Google account
- Verify OAuth scopes include gmail.compose

**Claude/Anthropic Errors**
- Confirm API key is valid and has credits
- Check for rate limiting
- Ensure document content isn't too large

### Logs

Check logs for detailed error information:
```bash
# View log file
tail -f vc_workflow.log

# For Docker deployment
docker-compose logs -f
```

### Debug Mode

Run with debug logging:
```bash
LOG_LEVEL=DEBUG python main.py --mode run
```

## Customization

### Email Templates
Modify the email generation prompt in `email_service.py` to customize:
- Tone and style
- Signature format
- Standard elements to include

### Document Parsing
Adjust parsing logic in `document_parser.py` for:
- Different document formats
- Additional extraction fields
- Custom validation rules

### CRM Fields
Extend `affinity_service.py` to map additional fields:
- Custom deal properties
- Organization metadata
- Pipeline-specific requirements

## Security

- Store API keys in environment variables, never in code
- Use service accounts for Google APIs when possible
- Limit API key permissions to minimum required scopes
- Regularly rotate API keys
- Monitor API usage for unusual activity

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

MIT License - see LICENSE file for details.