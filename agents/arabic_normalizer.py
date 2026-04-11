"""
Arabic text normalization utilities.

Provides zero-latency text normalization for Arabic search queries.
Handles diacritics removal, character normalization, and whitespace cleanup.
"""

import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

# Unicode ranges
DIACRITICS_RANGE = range(0x064B, 0x0660)  # U+064B to U+065F

# Character mappings for normalization
ALEF_VARIANTS = {
    '\u0623',  # أ
    '\u0625',  # إ
    '\u0622',  # آ
    '\u0671',  # ٱ
}

TEH_MARBUTA = '\u0629'  # ة
WAW_HAMZA = '\u0624'    # ؤ
YEH_VARIANTS = {
    '\u0626',  # ئ
    '\u0649',  # ى
}
TATWEEL = '\u0640'      # ـ


def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) from text."""
    return ''.join(
        char for char in text
        if ord(char) not in DIACRITICS_RANGE
    )


def normalize_alef(text: str) -> str:
    """Normalize all Alef variants to basic Alef (ا)."""
    for variant in ALEF_VARIANTS:
        text = text.replace(variant, '\u0627')  # ا
    return text


def normalize_teh_marbuta(text: str) -> str:
    """Normalize Teh Marbuta (ة) to Heh (ه)."""
    return text.replace(TEH_MARBUTA, '\u0647')  # ه


def normalize_waw(text: str) -> str:
    """Normalize Waw with Hamza (ؤ) to Waw (و)."""
    return text.replace(WAW_HAMZA, '\u0648')  # و


def normalize_yeh(text: str) -> str:
    """Normalize Yeh variants to basic Yeh (ي)."""
    for variant in YEH_VARIANTS:
        text = text.replace(variant, '\u064A')  # ي
    return text


def remove_tatweel(text: str) -> str:
    """Remove Kashida/Tatweel character."""
    return text.replace(TATWEEL, '')


def collapse_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters to single space."""
    return ' '.join(text.split())


def normalize(text: str) -> str:
    """
    Normalize Arabic text for search matching.
    
    Performs the following transformations:
    1. Remove diacritics (tashkeel)
    2. Normalize Alef variants (أإآا -> ا)
    3. Normalize Teh Marbuta (ة -> ه)
    4. Remove Tatweel (kashida)
    5. Normalize Waw (ؤ -> و)
    6. Normalize Yeh variants (ئى -> ي)
    7. Collapse whitespace
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    
    # Apply normalization steps in order
    text = remove_diacritics(text)
    text = normalize_alef(text)
    text = normalize_teh_marbuta(text)
    text = remove_tatweel(text)
    text = normalize_waw(text)
    text = normalize_yeh(text)
    text = collapse_whitespace(text)
    
    # Final NFC normalization for consistency
    text = unicodedata.normalize('NFC', text)
    
    return text.strip()


def normalize_for_database(text: str) -> str:
    """
    Extended normalization for database storage.
    Includes case folding and additional cleaning.
    """
    text = normalize(text)
    text = text.lower()
    return text
