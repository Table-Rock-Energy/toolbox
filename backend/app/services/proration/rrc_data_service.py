"""Service for downloading and managing RRC proration data."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import requests
import urllib3

# Suppress SSL warnings since RRC website has outdated SSL configuration
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Data directory for storing RRC CSVs
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
OIL_DATA_FILE = DATA_DIR / "oil_proration.csv"
GAS_DATA_FILE = DATA_DIR / "gas_proration.csv"

# RRC URLs
OIL_SEARCH_URL = "https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do"
GAS_SEARCH_URL = "https://webapps2.rrc.texas.gov/EWA/gasProQueryAction.do"


def create_rrc_session() -> requests.Session:
    """Create a requests session configured for RRC website's SSL requirements."""
    import ssl
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    class RRCSSLAdapter(HTTPAdapter):
        """Custom SSL adapter that works with RRC's outdated SSL configuration."""

        def init_poolmanager(self, *args, **kwargs):
            # Create a custom SSL context with legacy settings
            ctx = create_urllib3_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Enable legacy renegotiation for older servers (if available)
            if hasattr(ssl, 'OP_LEGACY_SERVER_CONNECT'):
                ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT

            # Additional compatibility options for legacy servers
            if hasattr(ssl, 'OP_ALL'):
                ctx.options |= ssl.OP_ALL

            # Set minimum TLS version to allow older protocols
            if hasattr(ctx, 'minimum_version'):
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2

            # RRC website uses AES256-GCM-SHA384 cipher - add it plus other compatible ciphers
            # This includes both ECDHE and non-ECDHE variants for maximum compatibility
            try:
                ctx.set_ciphers(
                    "AES256-GCM-SHA384:AES128-GCM-SHA256:AES256-SHA256:AES128-SHA256:"
                    "ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:"
                    "DHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:"
                    "DEFAULT:@SECLEVEL=1"
                )
            except ssl.SSLError:
                # Fall back to default ciphers if custom ones fail
                pass

            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    adapter = RRCSSLAdapter()
    session.mount("https://", adapter)
    # Disable certificate verification for RRC's certificate chain issues
    session.verify = False
    # Add browser-like headers to avoid being blocked
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    return session


class RRCDataService:
    """Service for managing RRC proration data downloads and lookups."""

    def __init__(self):
        self._oil_lookup: dict[tuple[str, str], dict] | None = None
        self._gas_lookup: dict[tuple[str, str], dict] | None = None
        self._combined_lookup: dict[tuple[str, str], dict] | None = None
        self._last_loaded: datetime | None = None

    def download_oil_data(self) -> tuple[bool, str, int]:
        """
        Download oil proration data from RRC.

        Returns:
            Tuple of (success, message, row_count)
        """
        try:
            logger.info("Downloading oil proration data from RRC...")

            # Create session with custom SSL handling for RRC's outdated config
            session = create_rrc_session()

            # First, do a search to establish session (query all districts)
            search_data = {
                "methodToCall": "search",
                "searchArgs.districtCodeArg": "08",  # Start with district 08
            }
            response = session.post(OIL_SEARCH_URL, data=search_data, timeout=60)
            response.raise_for_status()
            logger.info(f"Search response: status={response.status_code}, content-type={response.headers.get('content-type', 'unknown')}")

            # Now download CSV
            csv_data = {
                "methodToCall": "generateOilProrationReportCsv",
            }
            response = session.post(OIL_SEARCH_URL, data=csv_data, timeout=300)
            response.raise_for_status()

            # Log response details for debugging
            content_type = response.headers.get('content-type', 'unknown')
            content_length = len(response.content)
            logger.info(f"CSV response: status={response.status_code}, content-type={content_type}, length={content_length}")

            # Check if we got CSV or HTML
            content_start = response.content[:500].decode('utf-8', errors='ignore')
            logger.info(f"Response starts with: {content_start[:200]}")

            if '<html' in content_start.lower() or '<!doctype' in content_start.lower():
                return False, "RRC returned HTML instead of CSV - session may have expired", 0

            # Save to file
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            OIL_DATA_FILE.write_bytes(response.content)

            # Count rows
            df = pd.read_csv(OIL_DATA_FILE, skiprows=2, low_memory=False)
            row_count = len(df)

            logger.info(f"Downloaded oil proration data: {row_count:,} rows")
            self._oil_lookup = None  # Clear cache
            self._combined_lookup = None

            return True, f"Downloaded {row_count:,} oil proration records", row_count

        except Exception as e:
            logger.exception(f"Error downloading oil data: {e}")
            return False, f"Error downloading oil data: {str(e)}", 0

    def download_gas_data(self) -> tuple[bool, str, int]:
        """
        Download gas proration data from RRC.

        Returns:
            Tuple of (success, message, row_count)
        """
        try:
            logger.info("Downloading gas proration data from RRC...")

            # Create session with custom SSL handling for RRC's outdated config
            session = create_rrc_session()

            # First, do a search
            search_data = {
                "methodToCall": "search",
                "searchArgs.districtCodeArg": "08",
            }
            response = session.post(GAS_SEARCH_URL, data=search_data, timeout=60)
            response.raise_for_status()
            logger.info(f"Search response: status={response.status_code}, content-type={response.headers.get('content-type', 'unknown')}")

            # Download CSV
            csv_data = {
                "methodToCall": "generateGasProrationReportCsv",
            }
            response = session.post(GAS_SEARCH_URL, data=csv_data, timeout=300)
            response.raise_for_status()

            # Log response details for debugging
            content_type = response.headers.get('content-type', 'unknown')
            content_length = len(response.content)
            logger.info(f"CSV response: status={response.status_code}, content-type={content_type}, length={content_length}")

            # Check if we got CSV or HTML
            content_start = response.content[:500].decode('utf-8', errors='ignore')
            logger.info(f"Response starts with: {content_start[:200]}")

            if '<html' in content_start.lower() or '<!doctype' in content_start.lower():
                return False, "RRC returned HTML instead of CSV - session may have expired", 0

            # Save to file
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            GAS_DATA_FILE.write_bytes(response.content)

            # Count rows
            df = pd.read_csv(GAS_DATA_FILE, skiprows=2, low_memory=False)
            row_count = len(df)

            logger.info(f"Downloaded gas proration data: {row_count:,} rows")
            self._gas_lookup = None  # Clear cache
            self._combined_lookup = None

            return True, f"Downloaded {row_count:,} gas proration records", row_count

        except Exception as e:
            logger.exception(f"Error downloading gas data: {e}")
            return False, f"Error downloading gas data: {str(e)}", 0

    def download_all_data(self) -> tuple[bool, str, dict]:
        """
        Download both oil and gas proration data.

        Returns:
            Tuple of (success, message, stats_dict)
        """
        oil_success, oil_msg, oil_count = self.download_oil_data()
        gas_success, gas_msg, gas_count = self.download_gas_data()

        stats = {
            "oil_rows": oil_count,
            "gas_rows": gas_count,
            "oil_success": oil_success,
            "gas_success": gas_success,
        }

        if oil_success and gas_success:
            return True, f"Downloaded {oil_count:,} oil and {gas_count:,} gas records", stats
        elif oil_success:
            return False, f"Oil OK ({oil_count:,} rows), Gas failed: {gas_msg}", stats
        elif gas_success:
            return False, f"Gas OK ({gas_count:,} rows), Oil failed: {oil_msg}", stats
        else:
            return False, f"Both failed. Oil: {oil_msg}, Gas: {gas_msg}", stats

    def get_data_status(self) -> dict:
        """Get status of locally stored RRC data."""
        status = {
            "oil_available": OIL_DATA_FILE.exists(),
            "gas_available": GAS_DATA_FILE.exists(),
            "oil_rows": 0,
            "gas_rows": 0,
            "oil_modified": None,
            "gas_modified": None,
        }

        if OIL_DATA_FILE.exists():
            status["oil_modified"] = datetime.fromtimestamp(
                OIL_DATA_FILE.stat().st_mtime
            ).isoformat()
            try:
                df = pd.read_csv(OIL_DATA_FILE, skiprows=2, low_memory=False)
                status["oil_rows"] = len(df)
            except Exception:
                pass

        if GAS_DATA_FILE.exists():
            status["gas_modified"] = datetime.fromtimestamp(
                GAS_DATA_FILE.stat().st_mtime
            ).isoformat()
            try:
                df = pd.read_csv(GAS_DATA_FILE, skiprows=2, low_memory=False)
                status["gas_rows"] = len(df)
            except Exception:
                pass

        return status

    def _load_lookup(self) -> dict[tuple[str, str], dict]:
        """Load and cache the combined lookup table."""
        if self._combined_lookup is not None:
            return self._combined_lookup

        lookup = {}

        def clean_district(d):
            d = str(d).strip()
            if d and d[0].isdigit():
                return d.zfill(2) if len(d) == 1 else d
            return d

        # Load oil data - SUM acres when multiple rows exist for same lease
        if OIL_DATA_FILE.exists():
            try:
                df = pd.read_csv(OIL_DATA_FILE, skiprows=2, low_memory=False)
                for _, row in df.iterrows():
                    key = (clean_district(row["District"]), str(row["Lease No."]).strip())
                    try:
                        acres = float(row["Acres"]) if pd.notna(row["Acres"]) else 0.0
                        if key in lookup:
                            # Sum acres for multiple rows with same lease number
                            existing_acres = lookup[key].get("acres") or 0.0
                            lookup[key]["acres"] = existing_acres + acres
                            lookup[key]["row_count"] = lookup[key].get("row_count", 1) + 1
                        else:
                            lookup[key] = {
                                "acres": acres if acres > 0 else None,
                                "type": "oil",
                                "lease_name": row.get("Lease Name"),
                                "operator": row.get("Operator Name"),
                                "field_name": row.get("Field Name"),
                                "row_count": 1,
                            }
                    except (ValueError, TypeError):
                        pass
                logger.info(f"Loaded {len(lookup):,} oil proration records")
            except Exception as e:
                logger.error(f"Error loading oil data: {e}")

        # Load gas data - SUM acres when multiple rows exist for same lease
        if GAS_DATA_FILE.exists():
            try:
                df = pd.read_csv(GAS_DATA_FILE, skiprows=2, low_memory=False)
                gas_added = 0
                for _, row in df.iterrows():
                    key = (clean_district(row["District"]), str(row["Lease No."]).strip())
                    try:
                        acres = float(row["Acres"]) if pd.notna(row["Acres"]) else 0.0
                        if key in lookup:
                            # Sum acres for multiple rows with same lease number
                            # (could be oil + gas or multiple gas entries)
                            existing_acres = lookup[key].get("acres") or 0.0
                            lookup[key]["acres"] = existing_acres + acres
                            lookup[key]["row_count"] = lookup[key].get("row_count", 1) + 1
                            # Mark as both if mixing oil and gas
                            if lookup[key]["type"] == "oil":
                                lookup[key]["type"] = "both"
                        else:
                            lookup[key] = {
                                "acres": acres if acres > 0 else None,
                                "type": "gas",
                                "lease_name": row.get("Lease Name"),
                                "operator": row.get("Operator Name"),
                                "field_name": row.get("Field Name"),
                                "row_count": 1,
                            }
                            gas_added += 1
                    except (ValueError, TypeError):
                        pass
                logger.info(f"Added {gas_added:,} gas proration records")
            except Exception as e:
                logger.error(f"Error loading gas data: {e}")

        self._combined_lookup = lookup
        logger.info(f"Combined lookup table: {len(lookup):,} total entries")
        return lookup

    def lookup_acres(self, district: str, lease_number: str) -> dict | None:
        """
        Look up acres for a given district and lease number.

        Args:
            district: RRC district (e.g., "08", "8A")
            lease_number: Lease number (e.g., "41100")

        Returns:
            Dict with acres and metadata, or None if not found
        """
        lookup = self._load_lookup()

        # Normalize district
        if district and district[0].isdigit():
            district = district.zfill(2) if len(district) == 1 else district

        key = (district, str(lease_number).strip())
        return lookup.get(key)

    def lookup_by_lease_number(self, lease_number: str) -> dict | None:
        """
        Look up acres by lease number only (searches across all districts).
        Sums acres if the same lease number appears in multiple districts.

        Args:
            lease_number: Lease number (e.g., "59748")

        Returns:
            Dict with total acres and metadata, or None if not found
        """
        lookup = self._load_lookup()
        lease_number = str(lease_number).strip()

        total_acres = 0.0
        found_count = 0
        well_types = set()
        matches = []

        for (district, ln), info in lookup.items():
            if ln == lease_number:
                acres = info.get("acres") or 0.0
                total_acres += acres
                found_count += 1
                well_types.add(info.get("type", "unknown"))
                matches.append({
                    "district": district,
                    "acres": acres,
                    "type": info.get("type"),
                    "row_count": info.get("row_count", 1),
                })

        if found_count == 0:
            return None

        # Determine combined well type
        if "oil" in well_types and "gas" in well_types:
            combined_type = "both"
        elif "both" in well_types:
            combined_type = "both"
        elif "oil" in well_types:
            combined_type = "oil"
        elif "gas" in well_types:
            combined_type = "gas"
        else:
            combined_type = "unknown"

        return {
            "acres": total_acres if total_acres > 0 else None,
            "type": combined_type,
            "districts_found": found_count,
            "matches": matches,
        }

    def parse_rrc_lease(self, rrc_string: str) -> tuple[str | None, str | None]:
        """
        Parse RRC lease string to extract district and lease number (first one only).

        Args:
            rrc_string: RRC lease string (e.g., "08-41100", "8A-60687")

        Returns:
            Tuple of (district, lease_number)
        """
        if not rrc_string or pd.isna(rrc_string):
            return None, None

        # Take first if comma-separated
        rrc_string = str(rrc_string).split(",")[0].strip()

        # Match pattern like "08-41100" or "8A-60687"
        match = re.match(r"(\d+[A-Z]?)-(\d+)", rrc_string)
        if match:
            district = match.group(1)
            # Normalize district (pad single digit)
            if district.isdigit():
                district = district.zfill(2)
            return district, match.group(2)

        return None, None

    def parse_all_rrc_leases(self, rrc_string: str) -> list[tuple[str, str]]:
        """
        Parse RRC lease string to extract ALL district and lease number pairs.

        Args:
            rrc_string: RRC lease string, may contain multiple comma-separated values
                       (e.g., "08-41100, 08-41200, 8A-60687")

        Returns:
            List of (district, lease_number) tuples
        """
        if not rrc_string or pd.isna(rrc_string):
            return []

        results = []
        # Split by comma and process each
        for part in str(rrc_string).split(","):
            part = part.strip()
            # Match pattern like "08-41100" or "8A-60687"
            match = re.match(r"(\d+[A-Z]?)-(\d+)", part)
            if match:
                district = match.group(1)
                # Normalize district (pad single digit)
                if district.isdigit():
                    district = district.zfill(2)
                results.append((district, match.group(2)))

        return results

    def lookup_multiple_acres(self, rrc_string: str) -> dict:
        """
        Look up acres for multiple RRC leases and sum them.

        Args:
            rrc_string: RRC lease string, may contain multiple comma-separated values

        Returns:
            Dict with:
                - total_acres: sum of all found acres
                - leases_found: number of leases found in RRC data
                - leases_total: total number of leases parsed
                - details: list of individual lease lookups
                - well_type: combined well type (oil, gas, both, or unknown)
        """
        leases = self.parse_all_rrc_leases(rrc_string)

        if not leases:
            return {
                "total_acres": None,
                "leases_found": 0,
                "leases_total": 0,
                "details": [],
                "well_type": "unknown",
            }

        total_acres = 0.0
        leases_found = 0
        details = []
        well_types = set()

        for district, lease_number in leases:
            info = self.lookup_acres(district, lease_number)
            if info:
                acres = info.get("acres")
                if acres is not None:
                    total_acres += acres
                    leases_found += 1
                    well_types.add(info.get("type", "unknown"))
                details.append({
                    "district": district,
                    "lease_number": lease_number,
                    "acres": acres,
                    "found": True,
                    "type": info.get("type"),
                })
            else:
                details.append({
                    "district": district,
                    "lease_number": lease_number,
                    "acres": None,
                    "found": False,
                    "type": None,
                })

        # Determine combined well type
        if "oil" in well_types and "gas" in well_types:
            combined_type = "both"
        elif "oil" in well_types:
            combined_type = "oil"
        elif "gas" in well_types:
            combined_type = "gas"
        else:
            combined_type = "unknown"

        return {
            "total_acres": total_acres if leases_found > 0 else None,
            "leases_found": leases_found,
            "leases_total": len(leases),
            "details": details,
            "well_type": combined_type,
        }


# Global instance
rrc_data_service = RRCDataService()
