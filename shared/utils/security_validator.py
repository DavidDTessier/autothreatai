import re
import logging
import secrets
from typing import Union

logger = logging.getLogger(__name__)

# SQL injection patterns - common SQL keywords combined with dangerous characters
SQL_INJECTION_PATTERNS = [
    r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE|TRUNCATE|MERGE)\b.*[\'";\-–—])',
    r'[\'";\-–—]\s*(OR|AND)\s+\d+\s*=\s*\d+',
    r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE|TRUNCATE|MERGE)\b\s*\([^\)]*\))',
    r'--\s*$',  # SQL comment
    r'#\s*$',   # MySQL/SQLite comment
    r'/\*.*\*/', # Multi-line comment
]

# Code evaluation patterns - attempts to execute arbitrary code
CODE_EVAL_PATTERNS = [
    r'\b(eval|exec|compile|__import__|getattr|setattr|delattr|globals|locals|vars)\b\s*\(',
    r'\b(open|file|input|raw_input)\b\s*\([^\)]*[\'"][^\'"]*[\'"][^\)]*\)',  # File operations with paths
    r'\b(subprocess|Popen|call|run|check_output)\b\s*\(',
    r'\b(os\.system|os\.popen|os\.spawn)\b',
    r'\b(__[A-Z_]+__)\s*=',
]

# Secret/credential probing patterns
SECRET_PROBE_PATTERNS = [
    r'(api[_-]?key|access[_-]?token|secret[_-]?key|private[_-]?key|auth[_-]?token|bearer[_\s]*token)',
    r'(password|passwd|pwd|passphrase)[\s]*[=:]',
    r'(mongodb|mysql|postgresql)://[^\s]+',
    r'(AKIA|AGT|AROA|AIDA|ANPA|ANVA|ASIA)[A-Z0-9]{16,}',
    r'[0-9a-f]{32,}',  # Potential MD5/hash
    r'[0-9a-f]{40,}',  # Potential SHA1
    r'[0-9a-f]{64,}',  # Potential SHA256
]

def contains_sql_injection(text: str) -> bool:
    """
    Check if text contains potential SQL injection patterns.

    Args:
        text: Input text to check

    Returns:
        True if SQL injection patterns detected, False otherwise
    """
    if not text or not isinstance(text, str):
        return False

    text_lower = text.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            logger.warning(f"Potential SQL injection detected: {pattern}")
            return True
    return False

def contains_code_eval(text: str) -> bool:
    """
    Check if text contains potential code evaluation attempts.

    Args:
        text: Input text to check

    Returns:
        True if code eval patterns detected, False otherwise
    """
    if not text or not isinstance(text, str):
        return False

    text_lower = text.lower()
    for pattern in CODE_EVAL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            logger.warning(f"Potential code evaluation attempt detected: {pattern}")
            return True
    return False

def contains_secret_probe(text: str) -> bool:
    """
    Check if text contains potential secret/credential probing.

    Args:
        text: Input text to check

    Returns:
        True if secret probing patterns detected, False otherwise
    """
    if not text or not isinstance(text, str):
        return False

    text_lower = text.lower()
    for pattern in SECRET_PROBE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            logger.warning(f"Potential secret probing detected: {pattern}")
            return True
    return False

def validate_input_safety(text: str) -> tuple[bool, str]:
    """
    Validate that input text is safe for processing.

    Args:
        text: Input text to validate

    Returns:
        Tuple of (is_safe, error_message)
        is_safe: True if input is safe, False if threats detected
        error_message: Description of threat if detected, empty string if safe
    """
    if not text:
        return True, ""

    if not isinstance(text, str):
        # Convert to string for safety checking
        text = str(text)

    if contains_sql_injection(text):
        return False, "Input contains potential SQL injection patterns"

    if contains_code_eval(text):
        return False, "Input contains potential code evaluation attempts"

    if contains_secret_probe(text):
        return False, "Input contains potential secret/credential probing"

    return True, ""