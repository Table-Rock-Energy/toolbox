"""Contact data normalization for GoHighLevel integration.

Normalizes phone numbers to E.164 format (US +1), emails to lowercase,
and validates contact data before API calls.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger(__name__)

# Email validation pattern - simple but effective
EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone number to E.164 format assuming US (+1) country code.

    Args:
        phone: Phone number string (any format)

    Returns:
        E.164 formatted phone number (e.g., "+15127481234") or None if invalid
    """
    if not phone:
        return None

    # Remove whitespace
    phone = phone.strip()
    if not phone:
        return None

    try:
        # Parse with US default region
        parsed = phonenumbers.parse(phone, "US")

        # Validate the number
        if not phonenumbers.is_valid_number(parsed):
            logger.warning("Invalid phone format")
            return None

        # Return E.164 format
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    except NumberParseException:
        logger.warning("Invalid phone format")
        return None


def normalize_email(email: str) -> Optional[str]:
    """Normalize email address to lowercase and validate format.

    Args:
        email: Email address string

    Returns:
        Normalized email (lowercase, trimmed) or None if invalid
    """
    if not email:
        return None

    # Strip whitespace and lowercase
    email = email.strip().lower()
    if not email:
        return None

    # Validate basic email format
    if not EMAIL_PATTERN.match(email):
        logger.warning("Invalid email format")
        return None

    return email


def normalize_name(name: str) -> str:
    """Normalize name by trimming whitespace and applying title case.

    Args:
        name: Name string

    Returns:
        Normalized name (title case, trimmed) or empty string if None/empty
    """
    if not name:
        return ""

    # Strip whitespace and apply title case
    return name.strip().title()


def normalize_contact(data: dict) -> dict:
    """Apply all normalizations to a contact data dictionary.

    Args:
        data: Contact data dictionary with keys: first_name, last_name, email, phone

    Returns:
        Normalized contact dictionary with same keys
    """
    normalized = {}

    # Normalize names
    if "first_name" in data:
        normalized["first_name"] = normalize_name(data["first_name"])

    if "last_name" in data:
        normalized["last_name"] = normalize_name(data["last_name"])

    # Normalize email
    if "email" in data:
        normalized["email"] = normalize_email(data["email"])

    # Normalize phone
    if "phone" in data:
        normalized["phone"] = normalize_phone(data["phone"])

    # Pass through other fields unchanged
    for key, value in data.items():
        if key not in ["first_name", "last_name", "email", "phone"]:
            normalized[key] = value

    return normalized


def validate_contact(data: dict) -> tuple[bool, Optional[str]]:
    """Validate that contact has at least email OR phone after normalization.

    Args:
        data: Contact data dictionary (should be normalized first)

    Returns:
        Tuple of (is_valid, error_message). Error message is None if valid.
    """
    email = data.get("email")
    phone = data.get("phone")

    # Must have at least one contact method
    if not email and not phone:
        return False, "Contact must have at least email or phone"

    return True, None
