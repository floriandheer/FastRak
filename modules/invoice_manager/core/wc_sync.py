"""One-shot / on-demand WooCommerce → registry import.

Bridges the gap when WooCommerce has already issued invoices (via the
WCPDF plugin) before the global registry existed: the registry is empty,
so its `next_number` computation would collide with existing WC numbers.

`sync_woocommerce_invoices` walks every order that already has a WCPDF
invoice number and imports each one into the registry at its original
`(year, sequence)` slot, leaving everything else untouched.

Idempotent: re-runs are safe and cheap. After a sync, the registry is
the source of truth and `reserve_next_number` will continue the
sequence correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from shared_logging import get_logger

from .registry import InvoiceRegistry, RegistryConflictError
from .wc_bridge import (
    WooCommerceBridge,
    build_draft_from_wc_order,
    extract_wc_invoice_info,
)

logger = get_logger(__name__)


@dataclass
class SyncEntry:
    order_id: str
    order_number: str
    year: int
    sequence: int
    raw_number: str
    customer_name: str
    detail: str = ""


@dataclass
class SyncReport:
    imported: List[SyncEntry] = field(default_factory=list)
    already_present: List[SyncEntry] = field(default_factory=list)
    no_invoice_number: List[SyncEntry] = field(default_factory=list)
    conflicts: List[SyncEntry] = field(default_factory=list)
    errors: List[SyncEntry] = field(default_factory=list)
    orders_scanned: int = 0

    def as_text(self) -> str:
        lines = [
            f"Scanned {self.orders_scanned} WooCommerce order(s).",
            "",
            f"  ✅ Imported:        {len(self.imported)}",
            f"  ↪️  Already present: {len(self.already_present)}",
            f"  ⏭  No invoice yet:  {len(self.no_invoice_number)}",
            f"  ⚠  Conflicts:       {len(self.conflicts)}",
            f"  ❌ Errors:           {len(self.errors)}",
        ]
        for label, items in [
            ("Imported", self.imported),
            ("Conflicts", self.conflicts),
            ("Errors", self.errors),
        ]:
            if not items:
                continue
            lines.append("")
            lines.append(f"— {label} —")
            for e in items[:25]:
                lines.append(
                    f"  • #{e.sequence:03d} ({e.year})  order #{e.order_number}  "
                    f"{e.customer_name}{(' — ' + e.detail) if e.detail else ''}"
                )
            if len(items) > 25:
                lines.append(f"  … and {len(items) - 25} more (see log).")
        return "\n".join(lines)


ProgressCb = Optional[Callable[[str], None]]


def sync_woocommerce_invoices(
    registry: InvoiceRegistry,
    bridge: WooCommerceBridge,
    *,
    company_key: str = "3D",
    default_vat_rate: float = 21.0,
    after_iso: Optional[str] = None,
    before_iso: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    progress: ProgressCb = None,
) -> SyncReport:
    """Import every WC-numbered invoice missing from the registry.

    Args:
        registry: The InvoiceRegistry instance to write to.
        bridge:   A WooCommerceBridge with valid credentials.
        company_key: Registry company_key to assign to imported rows.
        default_vat_rate: Used when building line-item drafts.
        after_iso / before_iso / statuses: Forwarded to bridge.list_orders.
        progress: Optional callback for status updates (one line per event).
    """
    report = SyncReport()

    def _emit(msg: str):
        logger.info(msg)
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    _emit("Fetching WooCommerce orders…")
    try:
        orders = bridge.list_orders(
            after_iso=after_iso, before_iso=before_iso, statuses=statuses,
        )
    except Exception as e:
        logger.exception("WC sync: list_orders failed")
        report.errors.append(SyncEntry(
            order_id="-", order_number="-", year=0, sequence=0,
            raw_number="-", customer_name="-",
            detail=f"list_orders failed: {e}",
        ))
        return report

    report.orders_scanned = len(orders)
    _emit(f"Fetched {len(orders)} order(s); scanning for invoice numbers…")

    for order in orders:
        order_id = str(order.get("id", ""))
        order_number = str(order.get("number", order_id))
        billing = order.get("billing") or {}
        customer_name = " ".join([
            billing.get("first_name", ""), billing.get("last_name", "")
        ]).strip() or billing.get("company", "") or f"Order {order_number}"

        info = extract_wc_invoice_info(order)
        if not info:
            report.no_invoice_number.append(SyncEntry(
                order_id=order_id, order_number=order_number,
                year=0, sequence=0, raw_number="",
                customer_name=customer_name,
                detail="no WCPDF invoice number on order",
            ))
            continue

        entry = SyncEntry(
            order_id=order_id, order_number=order_number,
            year=info["year"], sequence=info["sequence"],
            raw_number=info["raw_number"],
            customer_name=customer_name,
        )

        # Fast-path: already imported
        existing = registry.get_by_source_ref("woocommerce", order_id)
        if existing:
            if (existing["year"] == info["year"]
                    and existing["sequence"] == info["sequence"]):
                report.already_present.append(entry)
                continue
            # Same order, different number — surface as conflict
            entry.detail = (
                f"registry already has this order at "
                f"#{existing['sequence']:03d} ({existing['year']}); "
                f"WC has #{info['sequence']:03d} ({info['year']})"
            )
            report.conflicts.append(entry)
            continue

        try:
            draft = build_draft_from_wc_order(
                order, company_key=company_key, default_vat_rate=default_vat_rate,
            )
            draft["invoice_date"] = info["invoice_date"]
            registry.import_existing_invoice(
                year=info["year"], sequence=info["sequence"], draft=draft,
            )
            report.imported.append(entry)
            _emit(
                f"Imported #{info['sequence']:03d} ({info['year']}) — "
                f"order #{order_number}, {customer_name}"
            )
        except RegistryConflictError as e:
            entry.detail = str(e)
            report.conflicts.append(entry)
            logger.warning(f"WC sync conflict on order {order_number}: {e}")
        except Exception as e:
            entry.detail = str(e)
            report.errors.append(entry)
            logger.exception(f"WC sync failed on order {order_number}")

    _emit("Sync finished.")
    return report
