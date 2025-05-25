import logging
import re
from typing import Optional, List, Dict
from anthropic import Anthropic

from config import config
from models import FounderInfo, MeetingSummary

logger = logging.getLogger(__name__)

class DocumentParser:
    """Parser for extracting structured information from meeting notes."""
    
    def __init__(self):
        self.anthropic = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    def parse_document(self, doc_title: str, doc_content: str) -> tuple[Optional[FounderInfo], Optional[MeetingSummary]]:
        """Parse document to extract founder info and meeting summary."""
        try:
            # First try to extract basic info from title
            founder_info = self._extract_founder_info_from_title(doc_title)
            
            # If title parsing fails, use AI to extract from content
            if not founder_info or not founder_info.founder_name or not founder_info.company_name:
                founder_info = self._extract_founder_info_with_ai(doc_title, doc_content)
            
            # Extract meeting summary using AI
            meeting_summary = self._extract_meeting_summary_with_ai(doc_content, founder_info)
            
            return founder_info, meeting_summary
            
        except Exception as e:
            logger.error(f"Error parsing document: {e}")
            return None, None
    
    def _extract_founder_info_from_title(self, title: str) -> Optional[FounderInfo]:
        """Extract founder and company info from document title using regex patterns."""
        # Common title patterns:
        # "Meeting with John Smith - Acme Corp - 2024-01-15"
        # "John Smith (Acme Corp) - Meeting Notes"
        # "Acme Corp - John Smith - Founder Meeting"
        
        patterns = [
            r"(?:meeting with|call with)?\s*([A-Za-z\s]+?)\s*[-–]\s*([A-Za-z\s&,.']+?)\s*[-–]",
            r"([A-Za-z\s]+?)\s*\(([A-Za-z\s&,.']+?)\)",
            r"([A-Za-z\s&,.']+?)\s*[-–]\s*([A-Za-z\s]+?)\s*[-–]",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                name_candidate = match.group(1).strip()
                company_candidate = match.group(2).strip()
                
                # Heuristic: name should be shorter and have fewer special chars
                if self._looks_like_person_name(name_candidate) and self._looks_like_company_name(company_candidate):
                    return FounderInfo(
                        founder_name=name_candidate,
                        company_name=company_candidate
                    )
                elif self._looks_like_person_name(company_candidate) and self._looks_like_company_name(name_candidate):
                    return FounderInfo(
                        founder_name=company_candidate,
                        company_name=name_candidate
                    )
        
        return None
    
    def _looks_like_person_name(self, text: str) -> bool:
        """Heuristic to determine if text looks like a person's name."""
        if not text:
            return False
        
        # Split into words
        words = text.split()
        
        # Should be 1-4 words
        if len(words) < 1 or len(words) > 4:
            return False
        
        # Each word should start with capital letter
        if not all(word[0].isupper() for word in words if word):
            return False
        
        # Shouldn't contain company indicators
        company_indicators = ['corp', 'inc', 'llc', 'ltd', 'company', 'co', 'technologies', 'tech', 'labs', 'ai', 'software']
        if any(indicator in text.lower() for indicator in company_indicators):
            return False
        
        return True
    
    def _looks_like_company_name(self, text: str) -> bool:
        """Heuristic to determine if text looks like a company name."""
        if not text:
            return False
        
        # Common company name patterns
        company_indicators = ['corp', 'inc', 'llc', 'ltd', 'company', 'co', 'technologies', 'tech', 'labs', 'ai', 'software', 'systems', 'solutions']
        
        # Check if it contains company indicators
        text_lower = text.lower()
        has_company_indicator = any(indicator in text_lower for indicator in company_indicators)
        
        # Or if it's a proper noun that doesn't look like a person name
        words = text.split()
        is_proper_noun = len(words) >= 1 and all(word[0].isupper() for word in words if word)
        
        return has_company_indicator or (is_proper_noun and not self._looks_like_person_name(text))
    
    def _extract_founder_info_with_ai(self, title: str, content: str) -> Optional[FounderInfo]:
        """Use AI to extract founder and company information from document content."""
        try:
            prompt = f"""
            Analyze this meeting document and extract the founder and company information.
            
            Document Title: {title}
            
            Document Content: {content[:3000]}...
            
            Please identify:
            1. Founder/CEO name (first and last name)
            2. Company name
            3. Founder email (if mentioned)
            4. Company description/what they do
            5. Company stage (seed, series A, etc.)
            6. Industry/sector
            
            Return the information in this JSON format:
            {{
                "founder_name": "First Last",
                "company_name": "Company Name",
                "founder_email": "email@company.com or null",
                "company_description": "Brief description of what the company does",
                "stage": "seed/series-a/series-b/etc or null",
                "sector": "fintech/healthcare/ai/etc or null"
            }}
            
            Only extract information that is clearly stated in the document. Use null for missing information.
            """
            
            response = self.anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            founder_data = json.loads(response.content[0].text)
            
            return FounderInfo(
                founder_name=founder_data.get('founder_name', ''),
                company_name=founder_data.get('company_name', ''),
                founder_email=founder_data.get('founder_email'),
                company_description=founder_data.get('company_description'),
                stage=founder_data.get('stage'),
                sector=founder_data.get('sector')
            )
            
        except Exception as e:
            logger.error(f"Error extracting founder info with AI: {e}")
            return None
    
    def _extract_meeting_summary_with_ai(self, content: str, founder_info: Optional[FounderInfo]) -> Optional[MeetingSummary]:
        """Use AI to extract meeting summary and action items."""
        try:
            founder_context = ""
            if founder_info:
                founder_context = f"The meeting was with {founder_info.founder_name} from {founder_info.company_name}."
            
            prompt = f"""
            Analyze this VC meeting transcript/notes and extract key information for follow-up.
            
            {founder_context}
            
            Meeting Content: {content[:4000]}...
            
            Please extract:
            1. Key discussion points (3-5 main topics covered)
            2. What the founder is asking for (funding, introductions, advice, etc.)
            3. Next steps or action items mentioned
            4. Ways the VC could potentially help (even if not explicitly stated)
            
            Return the information in this JSON format:
            {{
                "key_points": ["Point 1", "Point 2", "Point 3"],
                "founder_asks": ["What they're asking for"],
                "next_steps": ["Action items or next steps"],
                "ways_to_help": ["How VC could help based on discussion"]
            }}
            
            Focus on actionable information that would be useful for a follow-up email.
            """
            
            response = self.anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            summary_data = json.loads(response.content[0].text)
            
            return MeetingSummary(
                key_points=summary_data.get('key_points', []),
                founder_asks=summary_data.get('founder_asks', []),
                next_steps=summary_data.get('next_steps', []),
                ways_to_help=summary_data.get('ways_to_help', [])
            )
            
        except Exception as e:
            logger.error(f"Error extracting meeting summary with AI: {e}")
            return None
    
    def validate_extracted_data(self, founder_info: Optional[FounderInfo], meeting_summary: Optional[MeetingSummary]) -> bool:
        """Validate that extracted data has minimum required information."""
        if not founder_info:
            logger.warning("No founder info extracted")
            return False
        
        if not founder_info.founder_name or not founder_info.company_name:
            logger.warning("Missing founder name or company name")
            return False
        
        if not meeting_summary:
            logger.warning("No meeting summary extracted")
            return False
        
        if not meeting_summary.key_points:
            logger.warning("No key points extracted from meeting")
            return False
        
        return True