"""Outlook ingestion layer."""

from .outlook_ingest import ingest_outlook_orders, parse_email_body, parse_paths_field

__all__ = ["ingest_outlook_orders", "parse_email_body", "parse_paths_field"]
