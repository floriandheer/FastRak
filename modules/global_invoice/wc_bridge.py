"""Thin WooCommerce REST adapter used by the global invoice system.

Kept independent of the WC monitor's Config class so the global module can
be invoked without booting the monitor. Mirrors the small subset of
WooCommerceClient methods we need.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from shared_logging import get_logger

from .models import LineItem, to_cents

logger = get_logger(__name__)


class WCBridgeError(Exception):
    pass


class WooCommerceBridge:
    """Direct WC REST client. Initialise with a credentials dict that has
    `url`, `consumer_key`, `consumer_secret`, `api_version`."""

    def __init__(self, credentials: Dict[str, str]):
        try:
            import requests
            from requests.auth import HTTPBasicAuth
        except ImportError as e:
            raise WCBridgeError(
                "requests library not installed; WC features disabled"
            ) from e
        self._requests = requests
        self.base_url = credentials["url"].rstrip("/")
        api_version = credentials.get("api_version", "wc/v3")
        self.api_url = f"{self.base_url}/wp-json/{api_version}"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(
            credentials["consumer_key"], credentials["consumer_secret"]
        )
        self.monitor_secret_key: str = credentials.get("monitor_secret_key", "") or ""

    def test_connection(self) -> tuple[bool, str]:
        try:
            r = self.session.get(f"{self.api_url}/orders", params={"per_page": 1}, timeout=15)
            if r.status_code == 200:
                return True, "Connection successful"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)

    def list_orders(
        self,
        after_iso: Optional[str] = None,
        before_iso: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        per_page: int = 100,
    ) -> List[Dict]:
        """Paginate the WC orders endpoint, yielding the union across pages.

        Dates are passed straight through as ISO-8601 strings (e.g.
        '2024-01-01T00:00:00'). Pagination stops on an empty page.
        """
        all_orders: List[Dict] = []
        page = 1
        base_params: Dict[str, object] = {
            "per_page": per_page,
            "orderby": "date",
            "order": "asc",
        }
        if after_iso:
            base_params["after"] = after_iso
        if before_iso:
            base_params["before"] = before_iso
        if statuses:
            base_params["status"] = ",".join(statuses)

        while True:
            params = dict(base_params, page=page)
            r = self.session.get(f"{self.api_url}/orders", params=params, timeout=60)
            r.raise_for_status()
            batch = r.json() or []
            if not batch:
                break
            all_orders.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return all_orders

    def update_invoice_number(self, order_id: int, new_number: str) -> bool:
        """Push our number into the WC PDF-Invoices plugin meta keys."""
        try:
            number_data = {
                "number": int(new_number) if str(new_number).isdigit() else new_number,
                "formatted_number": str(new_number),
                "prefix": "",
                "suffix": "",
            }
            r = self.session.put(
                f"{self.api_url}/orders/{order_id}",
                json={
                    "meta_data": [
                        {"key": "_wcpdf_invoice_number", "value": str(new_number)},
                        {"key": "_wcpdf_invoice_number_data", "value": number_data},
                    ]
                },
                timeout=30,
            )
            r.raise_for_status()
            logger.info(f"WC order {order_id}: invoice number set to {new_number}")
            return True
        except Exception as e:
            logger.error(f"WC order {order_id}: failed to set invoice number: {e}")
            return False


    def create_order(
        self,
        customer: Dict,
        line_items: List[Dict],
        status: str = "completed",
    ) -> Optional[Dict]:
        """Create a manual WooCommerce order and return the order dict, or None on failure.

        customer  — billing dict: first_name, last_name, email, address_1, postcode, city, country
        line_items — list of dicts: name, quantity, total (string price excl. tax)
        """
        try:
            r = self.session.post(
                f"{self.api_url}/orders",
                json={"status": status, "billing": customer, "line_items": line_items, "set_paid": True},
                timeout=30,
            )
            r.raise_for_status()
            order = r.json()
            logger.info(f"Created WC order #{order.get('number', order['id'])}")
            return order
        except Exception as e:
            logger.error(f"Failed to create WC order: {e}")
            return None

    def download_invoice_pdf(self, order_id: int, save_path: "Path") -> bool:
        """Download invoice PDF via the pipeline_get_invoice WordPress AJAX endpoint.

        Requires monitor_secret_key to be set in the credentials dict passed to __init__.
        """
        if not self.monitor_secret_key:
            logger.warning("monitor_secret_key not set — cannot download invoice PDF")
            return False
        try:
            endpoint = f"{self.base_url}/wp-admin/admin-ajax.php"
            r = self.session.get(
                endpoint,
                params={"action": "pipeline_get_invoice", "order_id": order_id, "secret": self.monitor_secret_key},
                timeout=30,
                allow_redirects=False,
            )
            if r.status_code in (301, 302, 303, 307, 308):
                logger.error(f"Invoice endpoint redirected for order {order_id} — check server config")
                return False
            if r.status_code != 200:
                logger.error(f"Invoice endpoint returned HTTP {r.status_code} for order {order_id}")
                return False
            content_type = r.headers.get("content-type", "")
            if "pdf" not in content_type:
                try:
                    msg = r.json().get("data") or r.json().get("message") or "unknown error"
                except ValueError:
                    msg = f"unexpected content-type '{content_type}'"
                logger.error(f"Invoice download failed for order {order_id}: {msg}")
                return False
            from pathlib import Path as _Path
            _Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(r.content)
            logger.info(f"Downloaded invoice PDF for order {order_id}: {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download invoice PDF for order {order_id}: {e}")
            return False


def build_draft_from_wc_order(
    order: Dict,
    company_key: str = "3D",
    default_vat_rate: float = 21.0,
) -> Dict:
    """Convert a WooCommerce order dict into a registry draft payload."""
    billing = order.get("billing") or {}
    customer_name = " ".join(
        [billing.get("first_name", ""), billing.get("last_name", "")]
    ).strip()
    if not customer_name:
        customer_name = billing.get("company") or f"Order {order.get('id')}"
    customer_address = "\n".join(
        filter(None, [
            billing.get("address_1", ""),
            billing.get("address_2", ""),
            f"{billing.get('postcode', '')} {billing.get('city', '')}".strip(),
            billing.get("country", ""),
        ])
    )

    line_items: List[LineItem] = []
    for li in order.get("line_items") or []:
        qty = float(li.get("quantity", 1))
        # WC `total` is already qty * unit, exclusive of tax
        total_excl = float(li.get("total", 0) or 0)
        unit_price_cents = to_cents(total_excl / qty) if qty else 0
        line_items.append(LineItem(
            description=li.get("name", ""),
            quantity=qty,
            unit_price_cents=unit_price_cents,
            vat_rate=default_vat_rate,
        ))
    # Shipping as a line item if present
    for shipping in order.get("shipping_lines") or []:
        cost = float(shipping.get("total", 0) or 0)
        if cost <= 0:
            continue
        line_items.append(LineItem(
            description=f"Shipping: {shipping.get('method_title', 'shipping')}",
            quantity=1,
            unit_price_cents=to_cents(cost),
            vat_rate=default_vat_rate,
        ))

    return {
        "company_key": company_key,
        "invoice_date": (order.get("date_created") or "")[:10] or None,
        "customer_name": customer_name,
        "customer_email": billing.get("email", ""),
        "customer_address": customer_address,
        "customer_vat": _extract_meta(order, ["_billing_vat", "_billing_vat_number", "vat_number"]) or "",
        "line_items": line_items,
        "currency": order.get("currency", "EUR"),
        "source": "woocommerce",
        "source_ref": str(order.get("id")),
        "notes": f"WC order #{order.get('number')}",
    }


def _extract_meta(order: Dict, keys: List[str]) -> Optional[str]:
    wanted = {k.lower() for k in keys}
    for meta in order.get("meta_data") or []:
        if meta.get("key", "").lower() in wanted:
            value = meta.get("value")
            if value:
                return str(value)
    return None


_NUMBER_RE = re.compile(r"(\d+)")


def extract_wc_invoice_info(order: Dict) -> Optional[Dict]:
    """Pull the WCPDF invoice number/date out of an order's meta.

    Returns None if no invoice number is present (the order has not been
    invoiced yet by the WC PDF plugin).

    Output keys:
      - sequence  (int)            — the numeric part of the WC number
      - raw_number (str)            — the original string for audit / display
      - invoice_date (str)          — 'YYYY-MM-DD'
      - year (int)                  — derived from invoice_date
    """
    raw_number = None
    raw_date = None
    raw_date_formatted = None
    raw_data = None

    for meta in order.get("meta_data") or []:
        key = (meta.get("key") or "").lower()
        if key == "_wcpdf_invoice_number":
            raw_number = meta.get("value")
        elif key == "_wcpdf_invoice_number_data":
            raw_data = meta.get("value")
        elif key == "_wcpdf_invoice_date":
            raw_date = meta.get("value")
        elif key == "_wcpdf_invoice_date_formatted":
            raw_date_formatted = meta.get("value")

    if raw_number in (None, "") and isinstance(raw_data, dict):
        raw_number = raw_data.get("formatted_number") or raw_data.get("number")

    if raw_number in (None, ""):
        return None

    raw_number_str = str(raw_number).strip()
    matches = _NUMBER_RE.findall(raw_number_str)
    if not matches:
        logger.warning(
            f"Order {order.get('id')}: invoice number {raw_number_str!r} "
            f"contains no digits — skipping"
        )
        return None
    sequence = int(matches[-1])

    invoice_date = _coerce_date(raw_date_formatted) or _coerce_date(raw_date)
    if not invoice_date:
        for key in ("date_paid", "date_completed", "date_created"):
            v = order.get(key)
            if v:
                invoice_date = str(v)[:10]
                break
    if not invoice_date:
        invoice_date = datetime.now().strftime("%Y-%m-%d")

    try:
        year = int(invoice_date[:4])
    except (TypeError, ValueError):
        year = datetime.now().year

    return {
        "sequence": sequence,
        "raw_number": raw_number_str,
        "invoice_date": invoice_date,
        "year": year,
    }


def _coerce_date(value) -> Optional[str]:
    """Normalise a WC date meta value (unix ts or string) to 'YYYY-MM-DD'."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    if s.isdigit():
        try:
            return datetime.fromtimestamp(int(s)).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
