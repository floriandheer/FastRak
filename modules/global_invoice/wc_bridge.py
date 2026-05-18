"""Thin WooCommerce REST adapter used by the global invoice system.

Kept independent of the WC monitor's Config class so the global module can
be invoked without booting the monitor. Mirrors the small subset of
WooCommerceClient methods we need.
"""

from __future__ import annotations

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

    def test_connection(self) -> tuple[bool, str]:
        try:
            r = self.session.get(f"{self.api_url}/orders", params={"per_page": 1}, timeout=15)
            if r.status_code == 200:
                return True, "Connection successful"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)

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
