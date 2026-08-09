import http.server
import socketserver
import webbrowser
import os
import sys
import urllib.parse
import json

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class SafeHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves files and handles GET API calls."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Parse query parameters
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == '/set_active_pair':
            query_params = urllib.parse.parse_qs(parsed_url.query)
            pair = query_params.get('pair', [None])[0]
            if pair:
                # Write selection to shared config file
                config_path = os.path.join(DIRECTORY, "shared_config.json")
                try:
                    with open(config_path, "w") as f:
                        json.dump({"active_pair": pair}, f)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    # Allow cross-origin requests if needed
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "active_pair": pair}).encode())
                    print(f"[API] Front-end set active trading pair to: {pair}")
                    return
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(str(e).encode())
                    return
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing 'pair' parameter")
                return
                
        # Fallback to serving static HTML/JS/CSS files
        super().do_GET()

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer(("", PORT), SafeHandler) as httpd:
            print("\n=========================================")
            print(f"  QUANT ENGINE DASHBOARD SERVER ACTIVE   ")
            print("=========================================")
            print(f"Dashboard URL: http://localhost:{PORT}/dashboard.html")
            print("Keep this window open to view live performance updates.")
            print("Press Ctrl+C to stop the dashboard server.\n")
            
            # Automatically launch default browser to view the dashboard
            webbrowser.open(f"http://localhost:{PORT}/dashboard.html")
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start dashboard server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()
