import json
from gunicorn.glogging import Logger
from community.safe_logging import SafeFormatter


class PrivateLogger(Logger):
    def setup(self, cfg):
        super().setup(cfg)
        for handler in self.error_log.handlers:
            handler.setFormatter(SafeFormatter())

    def access(self, resp, req, environ, request_time):
        path = environ.get('PATH_INFO', '')
        # A route category is enough for operations. Never log user-controlled URLs.
        category = next((name for name in ('api', 'account', 'admin', 'static') if path.startswith('/' + name + '/')), 'other')
        status = str(getattr(resp, 'status', '')).split(' ')[0]
        self.access_log.info(json.dumps({'route': category, 'status': status if status.isdigit() else 'unknown', 'duration_ms': round(request_time.total_seconds()*1000)}))


logger_class = PrivateLogger
bind = '0.0.0.0:8080'
workers = 2
accesslog = '-'
errorlog = '-'
capture_output = False
