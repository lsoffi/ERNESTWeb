"""Do not serialize request URLs, query strings, headers, bodies or exceptions."""
import json
import logging


class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Even exception messages can contain passwords, SQL values or email addresses.
        event = record.msg if record.msg in ('mail_delivery_failed', 'admin_mfa_enrolled') else 'application_event'
        return json.dumps({'level': record.levelname, 'event': event})
