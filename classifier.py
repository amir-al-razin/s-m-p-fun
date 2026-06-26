import re
import json
import logging
import httpx
from config import OPENROUTER_API_KEY
from cache import global_cache
from schemas import (
    TicketRequest, TicketResponse, CaseTypeEnum, 
    SeverityEnum, DepartmentEnum
)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Regex patterns for heuristic classification
PATTERNS_WRONG_TRANSFER = [
    r"wrong\s+number", r"wrong\s+recipient", r"wrong\s+account", 
    r"sent\s+(?:money|taka|bdt)?\s+to\s+wrong", r"wrongly\s+sent", 
    r"bhul\s+number", r"bhul\s+numbere", r"bhul\s+pathai", r"bhul\s+pathise",
    r"ভুল\s+নাম্বার", r"ভুল\s+নম্বর", r"ভুল\s+নাম্বারে", r"ভুল\s+নম্বরে", 
    r"ভুল\s+করে\s+টাকা", r"ভুল\s+সেন্ড"
]

PATTERNS_PAYMENT_FAILED = [
    r"failed\s+payment", r"payment\s+failed", r"transaction\s+failed",
    r"balance\s+deducted", r"money\s+deducted", r"taka\s+kete", r"kete\s+nise",
    r"kete\s+nilo", r"payment\s+fail", r"transaction\s+fail",
    r"পেমেন্ট\s+ফেইল", r"ফেইলড", r"কেটে\s+নিয়েছে", r"টাকা\s+কেটেছে", 
    r"ব্যালেন্স\s+কেটে"
]

PATTERNS_REFUND = [
    r"refund", r"refund\s+request", r"money\s+back", r"return\s+money",
    r"taka\s+ferot", r"ferot\s+taka", r"refund\s+chan",
    r"টাকা\s+ফেরত", r"ফেরত\s+দিন", r"রিফান্ড"
]

PATTERNS_PHISHING = [
    r"otp", r"pin", r"password", r"scam", r"fake\s+call", r"scammer",
    r"asking\s+my\s+otp", r"asking\s+my\s+pin", r"otp\s+chaitese", r"pin\s+chaitese",
    r"ওটিপি", r"পিন", r"পাসওয়ার্ড", r"প্রতারক", r"পিন\s+চাইছে", r"ওটিপি\s+চাইছে"
]

def sanitize_summary(summary: str) -> str:
    """
    Enforces the Safety Rule & escalation penalties:
    1. Credentials Request Check (-15 pts penalty)
    2. Unauthorized Action / Direct Promise Check (-10 pts penalty)
    3. Suspicious Third Party Redirect Check (-10 pts penalty)
    """
    sanitized = summary
    
    # 1. Credentials Request Sanitization
    ask_patterns = [
        r"(?:ask|request|please|share|provide|tell|send|input|give)\s+(?:the\s+)?(?:customer|user|client)?\s*(?:to\s+)?(?:share|provide|tell|send|give|input)?\s*(?:their|your|his|her)?\s*(?:pin|otp|password|card\s+number)",
        r"(?:পিন|ওটিপি|পাসওয়ার্ড|কার্ড\s+নাম্বার)\s*(?:শেয়ার|দিতে|বলুন|অনুরোধ)"
    ]
    for pattern in ask_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Safety Rule violation (credential request) detected in summary: '{summary}'. Sanitizing.")
            sanitized = re.sub(pattern, "Customer reports security concern regarding account credentials.", sanitized, flags=re.IGNORECASE)
            
    forbidden_phrases = [
        "ask customer for pin", "ask user for pin", "request pin", "please share your pin", "ask client for pin",
        "ask customer for otp", "ask user for otp", "request otp", "please share your otp", "ask client for otp",
        "ask customer for password", "ask user for password", "request password",
        "ask customer for card number", "ask user for card number"
    ]
    for phrase in forbidden_phrases:
        if phrase in sanitized.lower():
            logger.warning(f"Forbidden credential phrase '{phrase}' detected. Sanitizing.")
            sanitized = sanitized.replace(phrase, "review security logs")

    # 2. Unauthorized Actions Promise Sanitization (Agent must not promise reversals/refunds)
    promise_patterns = [
        (r"\b(?:we\s+will|i\s+will|agent\s+will)\s+(?:refund|return|reverse|pay\s+back|send\s+back|transfer\s+back)\b", "customer requests refund/recovery"),
        (r"\b(?:money|funds|taka|bdt)\s+(?:has\s+been|will\s+be)\s+(?:refunded|returned|reversed|sent\s+back)\b", "customer requests refund/recovery"),
        (r"\b(?:we\s+have|i\s+have)\s+(?:refunded|reversed|transferred|returned)\b", "customer requests refund/recovery")
    ]
    for pattern, replacement in promise_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Safety Rule violation (unauthorized promise) detected: '{summary}'. Sanitizing.")
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # 3. Suspicious Third Party Instructions Sanitization
    third_party_patterns = [
        r"\b(?:call|contact|message|reach\s+out\s+to)\s+(?:[a-zA-Z]+\s+){0,4}(?:unauthorized|suspicious|third\s+party|unofficial|external|other)\b"
    ]
    for pattern in third_party_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Safety Rule violation (suspicious third party redirect) detected: '{summary}'. Sanitizing.")
            sanitized = re.sub(pattern, "refer the customer to official support channels", sanitized, flags=re.IGNORECASE)

    return sanitized

def classify_heuristically(message: str) -> dict:
    """
    Classifies the ticket using regex pattern matching.
    Returns a dictionary of classification fields.
    """
    msg_lower = message.lower()
    
    # Check Phishing
    for pattern in PATTERNS_PHISHING:
        if re.search(pattern, msg_lower):
            return {
                "case_type": CaseTypeEnum.PHISHING_OR_SOCIAL_ENGINEERING,
                "severity": SeverityEnum.CRITICAL,
                "department": DepartmentEnum.FRAUD_RISK,
                "agent_summary": "Customer reports a suspicious call or message requesting sensitive credentials.",
                "confidence": 0.90
            }
            
    # Check Wrong Transfer
    for pattern in PATTERNS_WRONG_TRANSFER:
        if re.search(pattern, msg_lower):
            # Try to extract money amount if present
            amount_match = re.search(r"(\d+)\s*(?:taka|bdt|টাকা)?", msg_lower)
            amount_str = f" {amount_match.group(1)} BDT" if amount_match else ""
            return {
                "case_type": CaseTypeEnum.WRONG_TRANSFER,
                "severity": SeverityEnum.HIGH,
                "department": DepartmentEnum.DISPUTE_RESOLUTION,
                "agent_summary": f"Customer reports sending{amount_str} to a wrong number and requests recovery.",
                "confidence": 0.85
            }
            
    # Check Payment Failed
    for pattern in PATTERNS_PAYMENT_FAILED:
        if re.search(pattern, msg_lower):
            return {
                "case_type": CaseTypeEnum.PAYMENT_FAILED,
                "severity": SeverityEnum.HIGH,
                "department": DepartmentEnum.PAYMENTS_OPS,
                "agent_summary": "Customer reports a failed transaction where balance may have been deducted.",
                "confidence": 0.85
            }
            
    # Check Refund Request
    for pattern in PATTERNS_REFUND:
        if re.search(pattern, msg_lower):
            return {
                "case_type": CaseTypeEnum.REFUND_REQUEST,
                "severity": SeverityEnum.LOW,
                "department": DepartmentEnum.CUSTOMER_SUPPORT,
                "agent_summary": "Customer requests a refund for a transaction.",
                "confidence": 0.80
            }
            
    # Default to Other
    return {
        "case_type": CaseTypeEnum.OTHER,
        "severity": SeverityEnum.LOW,
        "department": DepartmentEnum.CUSTOMER_SUPPORT,
        "agent_summary": "Customer reporting general issue or query.",
        "confidence": 0.70
    }

def classify_with_llm(message: str, channel: str = None, locale: str = None) -> dict:
    """
    Classifies the ticket using the Gemini LLM via OpenRouter.
    Returns a dictionary of classification fields or raises an exception.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set.")
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "You are an expert customer service ticket classifier for a digital finance platform.\n"
        "Analyze the message, channel, and locale, then return a JSON response matching the classification requirements.\n\n"
        "Classify into these Enums:\n"
        "- case_type:\n"
        "  - 'wrong_transfer': Money sent to the wrong recipient.\n"
        "  - 'payment_failed': Transaction failed but balance may be deducted.\n"
        "  - 'refund_request': Customer is asking for a refund.\n"
        "  - 'phishing_or_social_engineering': Suspicious calls, SMS, or someone asking for PIN, OTP, or password.\n"
        "  - 'other': Anything not covered above.\n"
        "- severity:\n"
        "  - 'low', 'medium', 'high', 'critical'\n"
        "  - Phishing/social engineering MUST be 'critical'.\n"
        "  - Wrong transfer and payment failed with balance deducted should be 'high'.\n"
        "  - Simple refunds and app crashes should be 'low'.\n"
        "- department:\n"
        "  - 'customer_support': for 'other', and low severity 'refund_request'.\n"
        "  - 'dispute_resolution': for 'wrong_transfer', and contested or high severity 'refund_request'.\n"
        "  - 'payments_ops': for 'payment_failed'.\n"
        "  - 'fraud_risk': for 'phishing_or_social_engineering'.\n\n"
        "Agent Summary Guidelines:\n"
        "- A neutral 1-2 sentence description of the complaint.\n"
        "- CRITICAL SAFETY RULE: The agent_summary MUST NEVER ask the customer to share their PIN, OTP, password, or full card number. "
        "Do not write phrases like 'Please share your PIN' or 'Ask user to input OTP'. The summary must be a passive description, "
        "e.g., 'Customer reports receiving a suspicious call asking for their OTP.'\n\n"
        "Return ONLY a valid JSON object with the following fields: 'case_type', 'severity', 'department', 'agent_summary', 'confidence'. "
        "Ensure all keys and values are valid JSON strings, and confidence is a float between 0 and 1."
    )
    
    prompt = f"Ticket Channel: {channel}\nTicket Locale: {locale}\nTicket Message: {message}"
    
    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    with httpx.Client(timeout=4.5) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_json = response.json()
        
    content_str = response_json["choices"][0]["message"]["content"]
    result = json.loads(content_str.strip())
    
    # Map raw string responses to proper Enum values to validate them
    result["case_type"] = CaseTypeEnum(result["case_type"])
    result["severity"] = SeverityEnum(result["severity"])
    result["department"] = DepartmentEnum(result["department"])
    result["confidence"] = float(result["confidence"])
    
    return result

def classify_ticket(request: TicketRequest) -> TicketResponse:
    """
    Main classification coordinator.
    Checks the exact LRU cache first, then attempts LLM classification,
    falling back to Heuristics if it fails or if the key is missing.
    """
    # 1. Check exact normalized cache
    cached_res = global_cache.get(request.message)
    if cached_res:
        logger.info(f"Cache HIT for ticket {request.ticket_id} (Message hash match)")
        # Map cached results to response, ensuring current ticket_id is preserved
        return TicketResponse(
            ticket_id=request.ticket_id,
            case_type=cached_res["case_type"],
            severity=cached_res["severity"],
            department=cached_res["department"],
            agent_summary=cached_res["agent_summary"],
            human_review_required=cached_res["human_review_required"],
            confidence=cached_res["confidence"]
        )

    # 2. Cache miss -> run classification
    classification = None
    
    # Try LLM
    if OPENROUTER_API_KEY:
        try:
            logger.info(f"Attempting LLM classification for ticket {request.ticket_id}")
            classification = classify_with_llm(request.message, request.channel, request.locale)
            logger.info(f"LLM classification succeeded for ticket {request.ticket_id}")
        except Exception as e:
            logger.error(f"LLM classification failed for ticket {request.ticket_id}: {str(e)}. Falling back to heuristics.")
            
    # Fallback to heuristics
    if not classification:
        logger.info(f"Using Heuristic classification for ticket {request.ticket_id}")
        classification = classify_heuristically(request.message)
        
    # Enforce Safety Rule on summary
    sanitized_summary = sanitize_summary(classification["agent_summary"])
    
    # Determine human_review_required
    severity_val = classification["severity"]
    case_type_val = classification["case_type"]
    
    human_review = (
        severity_val in [SeverityEnum.CRITICAL, SeverityEnum.HIGH] or
        case_type_val == CaseTypeEnum.PHISHING_OR_SOCIAL_ENGINEERING
    )
    
    response_obj = TicketResponse(
        ticket_id=request.ticket_id,
        case_type=classification["case_type"],
        severity=classification["severity"],
        department=classification["department"],
        agent_summary=sanitized_summary,
        human_review_required=human_review,
        confidence=classification["confidence"]
    )
    
    # 3. Store result in cache
    cache_entry = {
        "case_type": response_obj.case_type,
        "severity": response_obj.severity,
        "department": response_obj.department,
        "agent_summary": response_obj.agent_summary,
        "human_review_required": response_obj.human_review_required,
        "confidence": response_obj.confidence
    }
    global_cache.set(request.message, cache_entry)
    
    return response_obj
