import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

from google_drive_service import GoogleDriveService
from document_parser import DocumentParser
from affinity_service import AffinityService
from email_service import EmailService
from models import ProcessedDocument, FounderInfo, MeetingSummary
from config import config

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """Main orchestrator for the VC workflow automation."""
    
    def __init__(self):
        self.drive_service = GoogleDriveService()
        self.document_parser = DocumentParser()
        self.affinity_service = AffinityService()
        self.email_service = EmailService()
        self.processed_docs_file = config.PROCESSED_DOCS_FILE
        
        # Load processed documents history
        self.processed_docs = self._load_processed_docs()
    
    def run_workflow(self) -> Dict:
        """Run the complete workflow: check for new docs, process them, update CRM, draft emails."""
        logger.info("Starting VC workflow automation")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'new_documents_found': 0,
            'successfully_processed': 0,
            'deals_created_updated': 0,
            'emails_drafted': 0,
            'errors': []
        }
        
        try:
            # Step 1: Check for new documents
            new_documents = self.drive_service.monitor_folder_changes()
            results['new_documents_found'] = len(new_documents)
            
            if not new_documents:
                logger.info("No new documents found")
                return results
            
            logger.info(f"Found {len(new_documents)} new documents to process")
            
            # Step 2: Process each document
            for doc in new_documents:
                try:
                    processed_doc = self._process_single_document(doc)
                    
                    if processed_doc:
                        results['successfully_processed'] += 1
                        
                        # Step 3: Update Affinity CRM
                        deal_result = self._update_affinity_crm(processed_doc)
                        if deal_result:
                            results['deals_created_updated'] += 1
                        
                        # Step 4: Draft follow-up email
                        email_result = self._draft_follow_up_email(processed_doc)
                        if email_result:
                            results['emails_drafted'] += 1
                        
                        # Mark as processed
                        self._mark_document_processed(processed_doc)
                        
                    else:
                        results['errors'].append(f"Failed to process document: {doc['name']}")
                        
                except Exception as e:
                    error_msg = f"Error processing document {doc['name']}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Save processed documents history
            self._save_processed_docs()
            
            logger.info(f"Workflow completed. Processed: {results['successfully_processed']}, "
                       f"Deals: {results['deals_created_updated']}, Emails: {results['emails_drafted']}")
            
        except Exception as e:
            error_msg = f"Workflow error: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results
    
    def _process_single_document(self, doc: Dict) -> Optional[ProcessedDocument]:
        """Process a single Google Doc."""
        try:
            doc_id = doc['id']
            doc_title = doc['name']
            doc_url = doc['webViewLink']
            
            logger.info(f"Processing document: {doc_title}")
            
            # Skip if already processed
            if self._is_document_processed(doc_id):
                logger.info(f"Document {doc_title} already processed, skipping")
                return None
            
            # Extract document content
            content = self.drive_service.get_document_content(doc_id)
            if not content:
                logger.warning(f"No content extracted from {doc_title}")
                return None
            
            # Parse document to extract structured information
            founder_info, meeting_summary = self.document_parser.parse_document(doc_title, content)
            
            # Validate extracted data
            if not self.document_parser.validate_extracted_data(founder_info, meeting_summary):
                logger.warning(f"Invalid data extracted from {doc_title}")
                return None
            
            # Create processed document object
            processed_doc = ProcessedDocument(
                doc_id=doc_id,
                doc_title=doc_title,
                doc_url=doc_url,
                founder_info=founder_info,
                meeting_summary=meeting_summary,
                processed_at=datetime.now(),
                content_preview=content[:500] + "..." if len(content) > 500 else content
            )
            
            logger.info(f"Successfully processed {doc_title} - "
                       f"Founder: {founder_info.founder_name}, Company: {founder_info.company_name}")
            
            return processed_doc
            
        except Exception as e:
            logger.error(f"Error processing document {doc.get('name', 'Unknown')}: {e}")
            return None
    
    def _update_affinity_crm(self, processed_doc: ProcessedDocument) -> Optional[Dict]:
        """Update Affinity CRM with deal information."""
        try:
            logger.info(f"Updating Affinity CRM for {processed_doc.founder_info.company_name}")
            
            deal = self.affinity_service.create_or_update_deal(
                processed_doc.founder_info,
                processed_doc.meeting_summary,
                processed_doc.doc_title,
                processed_doc.doc_url
            )
            
            if deal:
                logger.info(f"Affinity deal updated: {deal.get('name', 'Unknown')}")
            else:
                logger.warning(f"Failed to update Affinity for {processed_doc.founder_info.company_name}")
            
            return deal
            
        except Exception as e:
            logger.error(f"Error updating Affinity CRM: {e}")
            return None
    
    def _draft_follow_up_email(self, processed_doc: ProcessedDocument) -> Optional[str]:
        """Draft follow-up email."""
        try:
            logger.info(f"Drafting follow-up email for {processed_doc.founder_info.founder_name}")
            
            # Generate email
            follow_up_email = self.email_service.draft_follow_up_email(
                processed_doc.founder_info,
                processed_doc.meeting_summary,
                processed_doc.doc_title
            )
            
            if not follow_up_email:
                logger.warning(f"Failed to generate email for {processed_doc.founder_info.founder_name}")
                return None
            
            # Create draft in Gmail
            draft_id = self.email_service.create_draft_email(follow_up_email)
            
            if draft_id:
                draft_link = self.email_service.get_draft_link(draft_id)
                logger.info(f"Email draft created for {processed_doc.founder_info.founder_name}: {draft_link}")
                return draft_id
            else:
                logger.warning(f"Failed to create email draft for {processed_doc.founder_info.founder_name}")
                return None
            
        except Exception as e:
            logger.error(f"Error drafting follow-up email: {e}")
            return None
    
    def _load_processed_docs(self) -> Dict:
        """Load processed documents history from file."""
        if os.path.exists(self.processed_docs_file):
            try:
                with open(self.processed_docs_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading processed docs file: {e}")
        
        return {}
    
    def _save_processed_docs(self):
        """Save processed documents history to file."""
        try:
            with open(self.processed_docs_file, 'w') as f:
                json.dump(self.processed_docs, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving processed docs file: {e}")
    
    def _is_document_processed(self, doc_id: str) -> bool:
        """Check if document has already been processed."""
        return doc_id in self.processed_docs
    
    def _mark_document_processed(self, processed_doc: ProcessedDocument):
        """Mark document as processed."""
        self.processed_docs[processed_doc.doc_id] = {
            'title': processed_doc.doc_title,
            'founder_name': processed_doc.founder_info.founder_name,
            'company_name': processed_doc.founder_info.company_name,
            'processed_at': processed_doc.processed_at.isoformat(),
            'url': processed_doc.doc_url
        }
    
    def test_all_services(self) -> Dict[str, bool]:
        """Test connections to all external services."""
        results = {}
        
        try:
            results['google_drive'] = bool(self.drive_service.get_folder_info())
        except Exception as e:
            logger.error(f"Google Drive test failed: {e}")
            results['google_drive'] = False
        
        try:
            results['affinity'] = self.affinity_service.test_connection()
        except Exception as e:
            logger.error(f"Affinity test failed: {e}")
            results['affinity'] = False
        
        try:
            results['gmail'] = self.email_service.test_connection()
        except Exception as e:
            logger.error(f"Gmail test failed: {e}")
            results['gmail'] = False
        
        return results
    
    def preview_processing(self, doc_id: str) -> Optional[Dict]:
        """Preview what would happen when processing a specific document."""
        try:
            # Get document info
            doc_content = self.drive_service.get_document_content(doc_id)
            if not doc_content:
                return None
            
            # Get doc title (you'd need to add this method to GoogleDriveService)
            # For now, use doc_id as title
            doc_title = f"Document {doc_id}"
            
            # Parse document
            founder_info, meeting_summary = self.document_parser.parse_document(doc_title, doc_content)
            
            if not founder_info or not meeting_summary:
                return None
            
            # Generate email preview
            email_preview = self.email_service.generate_email_preview(
                founder_info, meeting_summary, doc_title
            )
            
            return {
                'founder_info': {
                    'founder_name': founder_info.founder_name,
                    'company_name': founder_info.company_name,
                    'founder_email': founder_info.founder_email,
                    'company_description': founder_info.company_description,
                    'stage': founder_info.stage,
                    'sector': founder_info.sector
                },
                'meeting_summary': {
                    'key_points': meeting_summary.key_points,
                    'founder_asks': meeting_summary.founder_asks,
                    'next_steps': meeting_summary.next_steps,
                    'ways_to_help': meeting_summary.ways_to_help
                },
                'email_preview': email_preview
            }
            
        except Exception as e:
            logger.error(f"Error previewing document processing: {e}")
            return None