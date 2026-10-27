"""
serve_dashboard.py - Lightweight server to launch the TAM Agentic Dashboard.
Runs on pure standard library (no dependencies required).
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Change directory to this script's directory
repo_dir = Path(__file__).parent.resolve()
os.chdir(repo_dir)


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/dashboard.html"
        return super().do_GET()


def run_server(port=8000):
    server_address = ("", port)
    try:
        httpd = HTTPServer(server_address, DashboardHandler)
    except OSError:
        port = 8080
        server_address = ("", port)
        httpd = HTTPServer(server_address, DashboardHandler)

    url = f"http://localhost:{port}"
    print("=" * 65)
    print("🚀 ZYCUS TAM AGENTIC TRIAGE DASHBOARD")
    print("=" * 65)
    print(f"Server running at: {url}")
    print("Press Ctrl+C to stop the server.")
    print("=" * 65)

    # Automatically open in browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server. Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
