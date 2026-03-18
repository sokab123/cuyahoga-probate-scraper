#!/usr/bin/env python3
"""
Simple HTTP server for Railway health checks + manual trigger endpoint
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import threading
import os

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        
        elif self.path == '/run-scraper':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Running scraper...\n')
            
            # Run scraper in background
            def run():
                result = subprocess.run(['python3', 'cuyahoga_scraper_v3.py'], 
                                      capture_output=True, text=True)
                print(result.stdout)
                print(result.stderr)
            
            thread = threading.Thread(target=run)
            thread.start()
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress request logging
        pass

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'Health check server running on port {port}')
    print('Endpoints:')
    print('  /health - Health check')
    print('  /run-scraper - Manually trigger scraper')
    server.serve_forever()
