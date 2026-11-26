import json,sys,os
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
DB={}
class H(SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),**k)
    def end_headers(s):
        s.send_header('Access-Control-Allow-Origin','*');s.send_header('Cache-Control','no-store');super().end_headers()
    def do_OPTIONS(s): s.send_response(204);s.send_header('Access-Control-Allow-Headers','*');s.end_headers()
    def do_GET(s):
        if s.path.startswith('/__db'):
            if s.path.startswith('/__db/reset'): DB.clear()
            b=json.dumps(DB).encode();s.send_response(200);s.send_header('Content-Type','application/json');s.end_headers();s.wfile.write(b);return
        super().do_GET()
    def do_POST(s):
        n=int(s.headers.get('Content-Length',0));ops=json.loads(s.rfile.read(n))
        for o in ops:
            if o['op']=='set': DB[o['path']]=o['data']
            else: DB.pop(o['path'],None)
        s.send_response(200);s.end_headers();s.wfile.write(b'ok')
    def log_message(s,*a): pass
ThreadingHTTPServer(('0.0.0.0',8001),H).serve_forever()
