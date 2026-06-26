from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ChannelEnum(str, Enum):
    APP = "app"
    SMS = "sms"
    CALL_CENTER = "call_center"
    MERCHANT_PORTAL = "merchant_portal"

class LocaleEnum(str, Enum):
    BN = "bn"
    EN = "en"
    MIXED = "mixed"

class CaseTypeEnum(str, Enum):
    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    PHISHING_OR_SOCIAL_ENGINEERING = "phishing_or_social_engineering"
    OTHER = "other"

class SeverityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DepartmentEnum(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    FRAUD_RISK = "fraud_risk"

class TicketRequest(BaseModel):
    ticket_id: str = Field(..., description="Unique ID of the ticket")
    channel: Optional[ChannelEnum] = Field(None, description="Communication channel")
    locale: Optional[LocaleEnum] = Field(None, description="Language locale")
    message: str = Field(..., description="Raw text of the customer complaint")

class TicketResponse(BaseModel):
    ticket_id: str
    case_type: CaseTypeEnum
    severity: SeverityEnum
    department: DepartmentEnum
    agent_summary: str
    human_review_required: bool
    confidence: float
