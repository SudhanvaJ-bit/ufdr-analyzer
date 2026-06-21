"""
entity_extractor.py — Finds and tags critical forensic entities in text.

WHY THIS FILE EXISTS:
  Raw chat messages are just text strings. We need to automatically find:
  - Phone numbers (especially international/foreign ones)
  - Cryptocurrency wallet addresses (Bitcoin, Ethereum, USDT)
  - Email addresses
  - URLs
  - Suspicious keywords (drugs, weapons, crypto, threats)
  - Risk score (0-10) indicating how suspicious a message is

HOW IT WORKS:
  1. Regex patterns → very precise, catches structured data like
     phone numbers and crypto addresses with near-100% accuracy
  2. Keyword matching → scans for suspicious words from our config list
  3. Risk scoring → adds up signals to produce a 0-10 score

WHY REGEX OVER ML HERE?
  For structured patterns like phone numbers and crypto addresses,
  regex is MORE reliable than ML. The Bitcoin address format is
  mathematically defined. Regex can't make false positives if written right.
  ML is used for semantic understanding (RAG), not pattern matching.

INTERVIEW TIP:
  Be able to explain each regex pattern. Interviewers love this.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from backend.config import settings


@dataclass
class ExtractedEntities:
    """
    Container for all entities found in a single piece of text.
    Uses Python dataclass = auto-generates __init__, __repr__, etc.
    """
    phone_numbers: list[str] = field(default_factory=list)
    foreign_numbers: list[str] = field(default_factory=list)   # non-Indian
    crypto_addresses: list[str] = field(default_factory=list)
    crypto_types: list[str] = field(default_factory=list)      # BTC, ETH, USDT
    email_addresses: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    suspicious_keywords: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    risk_factors: list[str] = field(default_factory=list)       # human-readable reasons

    def to_dict(self) -> dict:
        """Convert to plain dict for JSON storage in database."""
        return {
            "phone_numbers": self.phone_numbers,
            "foreign_numbers": self.foreign_numbers,
            "crypto_addresses": self.crypto_addresses,
            "crypto_types": self.crypto_types,
            "email_addresses": self.email_addresses,
            "urls": self.urls,
            "suspicious_keywords": self.suspicious_keywords,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
        }


class EntityExtractor:
    """
    Extracts forensically relevant entities from text using regex + keyword matching.
    """

    # ── Phone Number Patterns ──────────────────────────────────
    # Matches international format with optional spaces/dashes
    # Examples: +919876543210, +44 7911 123456, 09876543210
    PHONE_PATTERN = re.compile(
        r'(?<!\d)'                    # not preceded by digit (avoid matching card numbers)
        r'(\+?(?:91|0)?[6-9]\d{9}'   # Indian mobile: starts 6-9, 10 digits
        r'|\+\d{1,3}[\s\-]?\d{4,14}' # International: +<country code> <number>
        r')',
        re.VERBOSE
    )

    # Indian numbers start with +91 or 0
    INDIAN_PHONE_PATTERN = re.compile(r'(?:\+91|0)[6-9]\d{9}')

    # ── Crypto Address Patterns ────────────────────────────────
    # Bitcoin Legacy (P2PKH): starts with 1, 25-34 chars
    BTC_LEGACY_PATTERN = re.compile(r'\b1[a-km-zA-HJ-NP-Z1-9]{25,34}\b')

    # Bitcoin P2SH: starts with 3
    BTC_P2SH_PATTERN = re.compile(r'\b3[a-km-zA-HJ-NP-Z1-9]{25,34}\b')

    # Bitcoin Bech32 (SegWit): starts with bc1
    BTC_BECH32_PATTERN = re.compile(r'\bbc1[a-z0-9]{6,87}\b', re.IGNORECASE)

    # Ethereum: 0x followed by 40 hex characters
    ETH_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{40}\b')

    # TRON (USDT-TRC20): starts with T, 34 chars, base58
    TRON_PATTERN = re.compile(r'\bT[a-km-zA-HJ-NP-Z1-9]{33}\b')

    # ── Email Pattern ──────────────────────────────────────────
    EMAIL_PATTERN = re.compile(
        r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'
    )

    # ── URL Pattern ───────────────────────────────────────────
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\']+|www\.[^\s<>"\']+',
        re.IGNORECASE
    )

    # ── Country Codes (non-Indian = foreign) ──────────────────
    # Common country codes that appear in investigations
    FOREIGN_COUNTRY_CODES = {
        "+1": "USA/Canada", "+44": "UK", "+971": "UAE",
        "+92": "Pakistan", "+880": "Bangladesh", "+86": "China",
        "+7": "Russia", "+966": "Saudi Arabia", "+974": "Qatar",
        "+65": "Singapore", "+60": "Malaysia", "+852": "Hong Kong",
        "+1868": "Trinidad", "+234": "Nigeria", "+27": "South Africa",
    }

    def extract(self, text: str) -> ExtractedEntities:
        """
        Main method — extracts all entities from a text string.

        Args:
            text: The raw message/note text to analyze

        Returns:
            ExtractedEntities with all found entities and a risk score
        """
        if not text:
            return ExtractedEntities()

        text_lower = text.lower()
        entities = ExtractedEntities()

        # Run all extractors
        self._extract_phone_numbers(text, entities)
        self._extract_crypto(text, entities)
        self._extract_emails(text, entities)
        self._extract_urls(text, entities)
        self._extract_keywords(text_lower, entities)

        # Calculate risk score based on what was found
        entities.risk_score = self._calculate_risk_score(entities)

        return entities

    def _extract_phone_numbers(self, text: str, entities: ExtractedEntities):
        """Find all phone numbers and flag foreign ones."""
        found = self.PHONE_PATTERN.findall(text)

        # Deduplicate
        seen = set()
        for num in found:
            num_clean = re.sub(r'[\s\-]', '', num)   # remove spaces/dashes
            if num_clean not in seen and len(num_clean) >= 7:
                seen.add(num_clean)
                entities.phone_numbers.append(num_clean)

                # Check if it's a foreign number
                for code, country in self.FOREIGN_COUNTRY_CODES.items():
                    if num_clean.startswith(code):
                        entities.foreign_numbers.append(f"{num_clean} ({country})")
                        entities.risk_factors.append(f"Foreign number detected: {country}")
                        break

    def _extract_crypto(self, text: str, entities: ExtractedEntities):
        """Find cryptocurrency wallet addresses."""

        patterns = [
            (self.BTC_LEGACY_PATTERN, "Bitcoin (Legacy)"),
            (self.BTC_P2SH_PATTERN, "Bitcoin (P2SH)"),
            (self.BTC_BECH32_PATTERN, "Bitcoin (Bech32)"),
            (self.ETH_PATTERN, "Ethereum"),
            (self.TRON_PATTERN, "TRON/USDT"),
        ]

        for pattern, crypto_type in patterns:
            matches = pattern.findall(text)
            for match in matches:
                if match not in entities.crypto_addresses:
                    entities.crypto_addresses.append(match)
                    entities.crypto_types.append(crypto_type)
                    entities.risk_factors.append(
                        f"Crypto address found: {crypto_type} ({match[:12]}...)"
                    )

    def _extract_emails(self, text: str, entities: ExtractedEntities):
        """Find email addresses."""
        found = self.EMAIL_PATTERN.findall(text)
        entities.email_addresses = list(set(found))

    def _extract_urls(self, text: str, entities: ExtractedEntities):
        """Find URLs, especially suspicious ones (dark web, etc.)."""
        found = self.URL_PATTERN.findall(text)
        entities.urls = list(set(found))

        # Flag .onion links (dark web)
        for url in entities.urls:
            if ".onion" in url:
                entities.risk_factors.append(f"Dark web URL detected: {url[:30]}...")

    def _extract_keywords(self, text_lower: str, entities: ExtractedEntities):
        """Scan for suspicious keywords from our config list."""
        for keyword in settings.SUSPICIOUS_KEYWORDS:
            if keyword.lower() in text_lower:
                if keyword not in entities.suspicious_keywords:
                    entities.suspicious_keywords.append(keyword)

    def _calculate_risk_score(self, entities: ExtractedEntities) -> float:
        """
        Calculate a 0-10 risk score based on what was found.

        Scoring logic:
        - Crypto address: +3.0 (major red flag in most investigations)
        - Foreign number: +2.0 (common in transnational crime)
        - Each suspicious keyword: +0.5 (up to max 4.0)
        - Dark web URL: +3.0
        - Email: +0.2 (minor signal)

        Cap at 10.0
        """
        score = 0.0

        # Crypto addresses are major red flags
        score += min(len(entities.crypto_addresses) * 3.0, 6.0)

        # Foreign numbers
        score += min(len(entities.foreign_numbers) * 2.0, 4.0)

        # Suspicious keywords (each adds 0.5, capped at 4.0)
        score += min(len(entities.suspicious_keywords) * 0.5, 4.0)

        # Dark web URLs
        dark_web_count = sum(1 for url in entities.urls if ".onion" in url)
        score += dark_web_count * 3.0

        return min(round(score, 2), 10.0)   # cap at 10

    def highlight_text(self, text: str) -> str:
        """
        Returns text with entity markers added.
        Useful for displaying highlighted results in the frontend.

        Example:
          Input:  "send 0.5 BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf"
          Output: "send 0.5 BTC to [CRYPTO:BTC:1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf]"
        """
        entities = self.extract(text)
        highlighted = text

        for addr in entities.crypto_addresses:
            highlighted = highlighted.replace(addr, f"[🔴CRYPTO:{addr[:10]}...]")

        for phone in entities.foreign_numbers:
            # Extract just the number part before " ("
            num = phone.split(" (")[0]
            highlighted = highlighted.replace(num, f"[🌍FOREIGN:{num}]")

        for keyword in entities.suspicious_keywords:
            # Case-insensitive replace
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted = pattern.sub(f"[⚠️KEYWORD:{keyword.upper()}]", highlighted)

        return highlighted


# ── Convenience function ───────────────────────────────────────
# So other modules can do:  from backend.extractors.entity_extractor import extract_entities
def extract_entities(text: str) -> ExtractedEntities:
    extractor = EntityExtractor()
    return extractor.extract(text)
