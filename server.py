#!/usr/bin/env python3
"""LambdaJobsAI dashboard server. Run from project root."""

import sqlite3
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'applications.db')

class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/applications':
            self._serve_applications()
        elif self.path == '/api/status' and False:
            pass
        elif self.path in ('/', '/dashboard.html'):
            self.path = '/dashboard.html'
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/status/'):
            self._update_status()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_applications(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            apps = conn.execute("""
              SELECT a.id, a.job_title, a.job_url, a.llm_runtime, a.status,
                     a.tailored, a.cover_letter_generated, a.created_at,
                     a.keyword_report, c.name as company_name, c.slug as company_slug
              FROM applications a JOIN companies c ON c.id = a.company_id
              ORDER BY a.created_at DESC
            """).fetchall()

            result = []
            for a in apps:
                d = dict(a)
                try:
                    d["keyword_report"] = json.loads(d.get("keyword_report") or "{}")
                except Exception:
                    d["keyword_report"] = {}
                d["tailored"] = bool(d["tailored"])
                d["cover_letter_generated"] = bool(d["cover_letter_generated"])
                files = conn.execute(
                    "SELECT file_type, file_path FROM generated_files WHERE application_id = ?",
                    (d["id"],)
                ).fetchall()
                d["files"] = [dict(f) for f in files]
                result.append(d)

            self.wfile.write(json.dumps({"applications": result}).encode())
        finally:
            conn.close()

    def _update_status(self):
        app_id = self.path.split('/')[-1]
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        status = body.get('status', 'generated')

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE applications SET status=?, updated_at=? WHERE id=?",
                (status, now, app_id)
            )
            conn.commit()
        finally:
            conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, format, *args):
        # Suppress GET spam for static files
        if args and str(args[1]) == '200' and any(
            str(args[0]).endswith(ext) for ext in ('.js', '.css', '.png', '.ico')
        ):
            return
        super().log_message(format, *args)


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = 8000
    httpd = HTTPServer(('', port), DashboardHandler)
    print(f"LambdaJobsAI dashboard → http://localhost:{port}")
    httpd.serve_forever()
