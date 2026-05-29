"""Input validation for the Content Machine pipeline.

Provides Pydantic models for validating inputs, configurations, and API requests.
"""

from __future__ import annotations

import hmac
import re
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ContentStatus(str, Enum):
    """Content publishing status."""
    DRAFT = "draft"
    PUBLISH = "publish"
    PENDING = "pending"
    FAILED = "failed"


class AuditDecision(str, Enum):
    """Audit decision values."""
    PUBLISH = "publish"
    REVISE = "revise"
    REJECT = "reject"
    SKIP = "skip"


class KeywordInput(BaseModel):
    """Validated keyword input for content generation."""
    
    keyword: str = Field(..., min_length=2, max_length=200)
    search_volume: Optional[int] = Field(None, ge=0, le=10000000)
    difficulty: Optional[float] = Field(None, ge=0, le=100)
    cpc: Optional[float] = Field(None, ge=0)
    
    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Clean and validate keyword."""
        v = v.strip().lower()
        if len(v) < 2:
            raise ValueError("Keyword must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Keyword must be at most 200 characters")
        # Remove excessive punctuation
        v = re.sub(r"[!?]{2,}", "!", v)
        v = re.sub(r"\.{2,}", ".", v)
        return v
    
    @field_validator("keyword")
    @classmethod
    def no_spam_keywords(cls, v: str) -> str:
        """Block obvious spam keywords."""
        spam_patterns = [
            r"(buy|cheap|discount|free).{0,20}(viagra|cialis|pills|drugs)",
            r"(click|visit).{0,10}(here|now).{0,10}(free|win|prize)",
            r"\b(xxx|porn|sex|adult)\b",
        ]
        for pattern in spam_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Keyword contains blocked terms")
        return v


class WordPressCredentials(BaseModel):
    """Validated WordPress credentials."""
    
    url: str = Field(..., min_length=10, max_length=500)
    username: str = Field(..., min_length=1, max_length=100)
    app_password: str = Field(..., min_length=10, max_length=100)
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate WordPress URL format."""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if not re.match(r"^https?://[a-zA-Z0-9][-a-zA-Z0-9]*", v):
            raise ValueError("Invalid URL format")
        return v.rstrip("/")
    
    @field_validator("app_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate app password format (should be base64-like)."""
        v = v.strip().replace(" ", "")
        # App passwords are typically 24+ chars with alphanumeric
        if len(v) < 16:
            raise ValueError("App password seems too short")
        return v


class DataForSEOConfig(BaseModel):
    """Validated DataForSEO API configuration."""
    
    login: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=5, max_length=100)
    
    @field_validator("login", "password")
    @classmethod
    def no_whitespace(cls, v: str) -> str:
        """Remove whitespace from credentials."""
        return v.strip()


class AnthropicConfig(BaseModel):
    """Validated Anthropic API configuration."""
    
    api_key: str = Field(..., min_length=20, max_length=200)
    model: str = Field(default="claude-3-5-sonnet-20241022")
    
    @field_validator("api_key")
    @classmethod
    def validate_api_key_format(cls, v: str) -> str:
        """Validate Anthropic API key format."""
        v = v.strip()
        if not v.startswith("sk-"):
            raise ValueError("Anthropic API key must start with 'sk-'")
        return v
    
    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model name."""
        allowed_models = [
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-haiku-20240307",
            "claude-3-5-haiku-20241022",
        ]
        if v not in allowed_models:
            raise ValueError(f"Model must be one of: {', '.join(allowed_models)}")
        return v


class ContentRequest(BaseModel):
    """Validated content generation request."""
    
    keyword: KeywordInput
    target_word_count: int = Field(default=1500, ge=500, le=5000)
    tone: str = Field(default="professional")
    include_faq: bool = Field(default=True)
    dry_run: bool = Field(default=False)
    
    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        """Validate tone setting."""
        allowed_tones = ["professional", "casual", "technical", "friendly", "formal"]
        v = v.lower().strip()
        if v not in allowed_tones:
            raise ValueError(f"Tone must be one of: {', '.join(allowed_tones)}")
        return v


class RateLimitInfo(BaseModel):
    """Rate limit tracking for API endpoints."""
    
    client_ip: str
    request_count: int = 0
    window_start: datetime = Field(default_factory=datetime.utcnow)
    
    def is_expired(self, window_seconds: int = 60) -> bool:
        """Check if rate limit window has expired."""
        elapsed = (datetime.utcnow() - self.window_start).total_seconds()
        return elapsed > window_seconds
    
    def increment(self) -> None:
        """Increment request count."""
        self.request_count += 1


class ValidationError(Exception):
    """Custom validation error with details."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[dict] = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks.
    
    Args:
        text: Raw user input
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Remove control characters except newlines and tabs
    text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t\r")
    
    # Basic XSS prevention
    text = text.replace("<script", "&lt;script")
    text = text.replace("javascript:", "[removed]")
    
    return text.strip()


def validate_webhook_url(url: str) -> bool:
    """Validate webhook URL format and security.
    
    Args:
        url: Webhook URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    # Must be HTTPS for security
    if not url.startswith("https://"):
        return False
    
    # Basic URL format check
    if not re.match(r"^https?://[a-zA-Z0-9][-a-zA-Z0-9.]*", url):
        return False
    
    # Block internal IPs
    blocked_patterns = [
        r"https?://127\.",
        r"https?://10\.",
        r"https?://192\.168\.",
        r"https?://172\.(1[6-9]|2[0-9]|3[01])\.",
        r"https?://0\.",
        r"https?://localhost",
    ]
    for pattern in blocked_patterns:
        if re.match(pattern, url):
            return False
    
    return True


def validate_auth_key(key: str, expected_key: str) -> tuple[bool, Optional[str]]:
    """Validate authentication key with timing-safe comparison.
    
    Args:
        key: Provided key
        expected_key: Expected key
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "Missing authentication key"
    
    if not expected_key:
        return False, "Server configuration error"
    
    key_clean = key.strip().replace(" ", "")
    expected_clean = expected_key.strip().replace(" ", "")
    
    if not hmac.compare_digest(key_clean, expected_clean):
        return False, "Invalid authentication key"
    
    return True, None
