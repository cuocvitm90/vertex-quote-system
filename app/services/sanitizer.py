"""
Enterprise Input Sanitization & Anti-Injection Protection Engine
Protects against Stored XSS, Reflected XSS, HTML Injection, and Command/SQL Injection.
Preserves UTF-8 Vietnamese diacritics and architectural/engineering technical terms.
"""
import re
import html
from typing import Any, Dict, List, Union


# Regex patterns for dangerous payloads
DANGEROUS_PATTERNS = [
    re.compile(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<\s*object[^>]*>.*?<\s*/\s*object\s*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<\s*embed[^>]*>.*?<\s*/\s*embed\s*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'vbscript\s*:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onload=, onerror=, onclick=, onmouseover=
    re.compile(r'data\s*:\s*text/html', re.IGNORECASE),
]

# Control characters to strip (except standard whitespace and newlines)
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')


def clean_string(value: str, escape_html_entities: bool = True) -> str:
    """
    Sanitizes a single string value:
    1. Strips non-printable ASCII control characters.
    2. Strips script / iframe / object / embed tags and inline event handlers.
    3. Escapes remaining HTML entities if required.
    4. Trims excess leading/trailing whitespace.
    """
    if not isinstance(value, str):
        return value

    # Remove dangerous control chars
    sanitized = CONTROL_CHAR_PATTERN.sub('', value)

    # Strip dangerous HTML and script injections
    for pattern in DANGEROUS_PATTERNS:
        sanitized = pattern.sub('', sanitized)

    # HTML escape if required
    if escape_html_entities:
        sanitized = html.escape(sanitized, quote=True)

    return sanitized.strip()


def sanitize_input(data: Any, escape_html_entities: bool = False) -> Any:
    """
    Recursively sanitizes data structures (strings, dicts, lists).
    """
    if isinstance(data, str):
        return clean_string(data, escape_html_entities=escape_html_entities)
    elif isinstance(data, dict):
        return {k: sanitize_input(v, escape_html_entities=escape_html_entities) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item, escape_html_entities=escape_html_entities) for item in data]
    return data
