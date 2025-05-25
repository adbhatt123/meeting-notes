from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class FounderInfo:
    """Extracted information about founder and company from meeting notes."""
    founder_name: str
    company_name: str
    founder_email: Optional[str] = None
    company_description: Optional[str] = None
    stage: Optional[str] = None
    sector: Optional[str] = None

@dataclass
class MeetingSummary:
    """Summary of meeting discussion points."""
    key_points: List[str]
    founder_asks: List[str]
    next_steps: List[str]
    ways_to_help: List[str]
    
@dataclass
class ProcessedDocument:
    """Information about a processed Google Doc."""
    doc_id: str
    doc_title: str
    doc_url: str
    founder_info: FounderInfo
    meeting_summary: MeetingSummary
    processed_at: datetime
    content_preview: str
    
@dataclass
class AffinityDeal:
    """Affinity deal creation/update data."""
    name: str
    pipeline_id: str
    notes: str
    founder_name: str
    company_name: str
    stage_id: Optional[str] = None
    
@dataclass
class FollowUpEmail:
    """Follow-up email content."""
    to_email: str
    subject: str
    body: str
    founder_name: str
    company_name: str