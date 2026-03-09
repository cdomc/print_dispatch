"""Outlook ingestion layer."""

from .outlook_ingest import ingest_outlook_orders, parse_email_body, parse_paths_field

from .outlook_ingest import get_outlook_connection_status

__all__ = ["ingest_outlook_orders", "parse_email_body", "parse_paths_field", "get_outlook_connection_status"]
