"""Dataclasses for invoices, companies, line items, plus money helpers.

Money is stored as integer cents to avoid float rounding. All conversion
to/from a float-shaped UI happens via to_cents() / format_money().
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import List, Optional


@dataclass
class Company:
    key: str
    display_name: str
    legal_name: str
    vat: str
    address_lines: List[str]
    output_prefix: str
    default_vat_rate: float = 21.0
    email: str = ""
    iban: str = ""
    bic: str = ""
    template_path: Optional[str] = None
    wc_binding: Optional[dict] = None

    @property
    def uses_libreoffice(self) -> bool:
        return bool(self.template_path)

    @property
    def uses_woocommerce(self) -> bool:
        return bool(self.wc_binding)

    @property
    def address_block(self) -> str:
        return "\n".join(self.address_lines)


@dataclass
class LineItem:
    description: str
    quantity: float
    unit_price_cents: int
    vat_rate: float

    @property
    def line_subtotal_cents(self) -> int:
        return round(self.unit_price_cents * self.quantity)

    @property
    def line_vat_cents(self) -> int:
        return round(self.line_subtotal_cents * self.vat_rate / 100.0)

    @property
    def line_total_cents(self) -> int:
        return self.line_subtotal_cents + self.line_vat_cents

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price_cents": self.unit_price_cents,
            "vat_rate": self.vat_rate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LineItem":
        return cls(
            description=d["description"],
            quantity=float(d["quantity"]),
            unit_price_cents=int(d["unit_price_cents"]),
            vat_rate=float(d["vat_rate"]),
        )


@dataclass
class Invoice:
    company_key: str
    invoice_date: date
    customer_name: str
    line_items: List[LineItem]
    customer_vat: str = ""
    customer_address: str = ""
    customer_email: str = ""
    currency: str = "EUR"
    source: str = "manual"          # 'manual' | 'woocommerce'
    source_ref: Optional[str] = None
    notes: str = ""

    # Filled after registry write:
    id: Optional[int] = None
    year: Optional[int] = None
    sequence: Optional[int] = None
    status: str = "draft"           # 'draft' | 'issued' | 'voided'
    void_reason: Optional[str] = None
    pdf_path: Optional[str] = None

    @property
    def subtotal_cents(self) -> int:
        return sum(li.line_subtotal_cents for li in self.line_items)

    @property
    def vat_cents(self) -> int:
        return sum(li.line_vat_cents for li in self.line_items)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.vat_cents

    @property
    def formatted_number(self) -> str:
        return f"{self.sequence:03d}" if self.sequence else ""


def to_cents(amount: float | int | str) -> int:
    """Convert a user-entered amount (e.g. '12.34' or '12,34') to integer cents."""
    if isinstance(amount, int):
        return amount * 100
    s = str(amount).strip().replace(" ", "").replace(" ", "")
    # Accept both '1,234.56' (English) and '1.234,56' (European)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return round(float(s) * 100)


def format_money(cents: int, currency: str = "EUR") -> str:
    """Format integer cents as European-style currency."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, rem = divmod(cents, 100)
    # Insert thousands separators (dot in European convention)
    whole_str = f"{whole:,}".replace(",", ".")
    symbol = {"EUR": "€", "USD": "$"}.get(currency, currency + " ")
    return f"{symbol} {sign}{whole_str},{rem:02d}"


def format_money_plain(cents: int) -> str:
    """Like format_money but without currency symbol; for table cells."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, rem = divmod(cents, 100)
    whole_str = f"{whole:,}".replace(",", ".")
    return f"{sign}{whole_str},{rem:02d}"
