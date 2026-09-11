from pathlib import Path
from whitenoise import WhiteNoise

def not_found(environ, start_response):
    start_response('404 Not Found', [('Content-Type','text/plain; charset=utf-8')])
    return [b'Not found']

files = WhiteNoise(not_found, root=Path(__file__).parent / 'public', max_age=60)
def application(environ, start_response):
    if environ.get('PATH_INFO') == '/': environ['PATH_INFO'] = '/index.html'
    if environ.get('REQUEST_METHOD') not in ('GET','HEAD'):
        start_response('405 Method Not Allowed', [('Allow','GET, HEAD')])
        return [b'Method not allowed']
    return files(environ,start_response)
