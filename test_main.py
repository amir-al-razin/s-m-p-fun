import pytest
from fastapi.testclient import TestClient
from main import app
from schemas import CaseTypeEnum, SeverityEnum, DepartmentEnum

client = TestClient(app)

def test_health_endpoint():
    """
    Test that /health returns 200 and the correct health status.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.parametrize(
    "message, expected_case_type, expected_severity, expected_department",
    [
        (
            "I sent 3000 to wrong number", 
            CaseTypeEnum.WRONG_TRANSFER, 
            SeverityEnum.HIGH, 
            DepartmentEnum.DISPUTE_RESOLUTION
        ),
        (
            "Payment failed but balance deducted", 
            CaseTypeEnum.PAYMENT_FAILED, 
            SeverityEnum.HIGH, 
            DepartmentEnum.PAYMENTS_OPS
        ),
        (
            "Someone called asking my OTP, is that bKash?", 
            CaseTypeEnum.PHISHING_OR_SOCIAL_ENGINEERING, 
            SeverityEnum.CRITICAL, 
            DepartmentEnum.FRAUD_RISK
        ),
        (
            "Please refund my last transaction, I changed my mind", 
            CaseTypeEnum.REFUND_REQUEST, 
            SeverityEnum.LOW, 
            DepartmentEnum.CUSTOMER_SUPPORT
        ),
        (
            "App crashed when I opened it", 
            CaseTypeEnum.OTHER, 
            SeverityEnum.LOW, 
            DepartmentEnum.CUSTOMER_SUPPORT
        ),
    ]
)
def test_public_sample_cases(message, expected_case_type, expected_severity, expected_department):
    """
    Test the 5 public sample cases provided in the specification.
    """
    payload = {
        "ticket_id": "T-TEST",
        "message": message,
        "channel": "app",
        "locale": "en"
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["ticket_id"] == "T-TEST"
    assert data["case_type"] == expected_case_type.value
    assert data["severity"] == expected_severity.value
    assert data["department"] == expected_department.value
    assert isinstance(data["agent_summary"], str)
    assert len(data["agent_summary"]) > 0
    assert isinstance(data["human_review_required"], bool)
    assert isinstance(data["confidence"], float)
    
    # Check human_review_required constraint:
    if expected_severity in [SeverityEnum.CRITICAL, SeverityEnum.HIGH] or expected_case_type == CaseTypeEnum.PHISHING_OR_SOCIAL_ENGINEERING:
        assert data["human_review_required"] is True
    else:
        assert data["human_review_required"] is False

def test_optional_fields_missing():
    """
    Test that optional request fields are handled correctly when omitted.
    """
    payload = {
        "ticket_id": "T-002",
        "message": "I want a refund for the double payment"
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["ticket_id"] == "T-002"
    assert data["case_type"] in [CaseTypeEnum.REFUND_REQUEST, CaseTypeEnum.PAYMENT_FAILED]

def test_validation_errors():
    """
    Test that invalid request payloads trigger validation errors in JSON format.
    """
    # Missing required field 'message'
    payload = {
        "ticket_id": "T-INVALID",
        "channel": "sms"
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "details" in data

    # Missing required field 'ticket_id'
    payload = {
        "message": "Hello world"
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 422

def test_safety_rule_enforcement():
    """
    Test that agent_summary never requests sensitive parameters like PIN, OTP, password, or card number.
    """
    from classifier import sanitize_summary
    
    # Text that contains a request/prompt for PIN
    violating_summary = "We need to ask the customer to share their PIN to complete transaction rollback."
    sanitized = sanitize_summary(violating_summary)
    
    # Assert it was cleaned and no longer contains "ask ... share ... pin"
    assert "ask" not in sanitized.lower() or "pin" not in sanitized.lower()
    assert "credentials" in sanitized.lower() or "security" in sanitized.lower()
    
    # Direct check with a ticket classification containing scammer message
    payload = {
        "ticket_id": "T-SAFE",
        "message": "A caller wanted my PIN 1234. Please send money."
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Check that the summary doesn't prompt for sensitive details
    summary_lower = data["agent_summary"].lower()
    
    # Verify the summary doesn't command asking for sensitive keys
    assert "ask customer for pin" not in summary_lower
    assert "ask user for pin" not in summary_lower
    assert "request pin" not in summary_lower
    assert "please share your pin" not in summary_lower

def test_frontend_endpoint():
    """
    Test that the root route (GET /) serves the diagnostic HTML index file.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "QueueStorm Triage" in response.text

def test_health_cache_stats():
    """
    Test that GET /health includes active cache statistics.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "cache_stats" in data
    assert "hits" in data["cache_stats"]
    assert "misses" in data["cache_stats"]
    assert "hit_ratio" in data["cache_stats"]

def test_caching_behavior():
    """
    Test that duplicate requests hit the LRU cache and skip execution.
    """
    from cache import global_cache
    
    # Reset stats
    global_cache.hits = 0
    global_cache.misses = 0
    
    message = "I sent 4500 taka to wrong number"
    payload = {
        "ticket_id": "T-CACHE-1",
        "message": message
    }
    
    # First Request: Cache Miss
    res1 = client.post("/sort-ticket", json=payload)
    assert res1.status_code == 200
    assert global_cache.misses == 1
    assert global_cache.hits == 0
    
    # Second Request: Cache Hit
    payload["ticket_id"] = "T-CACHE-2"
    res2 = client.post("/sort-ticket", json=payload)
    assert res2.status_code == 200
    assert global_cache.misses == 1
    assert global_cache.hits == 1
    
    # Assert data is identical except for the requested ticket_id
    data1 = res1.json()
    data2 = res2.json()
    assert data1["case_type"] == data2["case_type"]
    assert data1["severity"] == data2["severity"]
    assert data1["agent_summary"] == data2["agent_summary"]
    assert data2["ticket_id"] == "T-CACHE-2"

def test_unauthorized_action_safety():
    """
    Test that summaries with unauthorized promises or redirects are sanitized.
    """
    from classifier import sanitize_summary
    
    # Test Unauthorized Promise Rejection
    promise_summary = "We will refund the 3000 BDT to your account within 24 hours."
    sanitized_promise = sanitize_summary(promise_summary)
    assert "will refund" not in sanitized_promise.lower()
    assert "requests refund" in sanitized_promise.lower()
    
    # Test Suspicious Redirect Rejection
    redirect_summary = "Please contact this suspicious third party number for assistance."
    sanitized_redirect = sanitize_summary(redirect_summary)
    assert "suspicious third party" not in sanitized_redirect.lower()
    assert "official support channels" in sanitized_redirect.lower()


def test_benign_credential_requests():
    """
    Verify that benign password/PIN resets do not trigger phishing.
    """
    payload = {
        "ticket_id": "T-BENIGN-RESET",
        "message": "I forgot my password and want to reset it"
    }
    response = client.post("/sort-ticket", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["case_type"] != CaseTypeEnum.PHISHING_OR_SOCIAL_ENGINEERING.value


def test_safety_spaced_credentials():
    """
    Verify safety sanitization scrubs spaced credentials requests.
    """
    from classifier import sanitize_summary
    summary = "Please ask the user to share their p i n to proceed."
    sanitized = sanitize_summary(summary)
    assert "p i n" not in sanitized.lower()
    assert "credentials" in sanitized.lower()


def test_safety_bengali_promises():
    """
    Verify safety sanitization scrubs Bengali refund promises.
    """
    from classifier import sanitize_summary
    summary = "আমরা গ্রাহককে টাকা ফেরত দিয়েছি।"
    sanitized = sanitize_summary(summary)
    assert "টাকা ফেরত" not in sanitized
    assert "রিফান্ড" in sanitized or "আবেদন" in sanitized


def test_safety_phone_and_url_redaction():
    """
    Verify safety sanitization redacts phone numbers and links.
    """
    from classifier import sanitize_summary
    summary = "Please check the status on www.untrusted-site.com or call 01712345678."
    sanitized = sanitize_summary(summary)
    assert "www.untrusted-site.com" not in sanitized
    assert "01712345678" not in sanitized
    assert "[REDACTED_URL]" in sanitized
    assert "[REDACTED_CONTACT]" in sanitized


