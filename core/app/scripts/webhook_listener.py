# app/scripts/webhook_listener.py
"""A webhook receiver for trying webhooks locally: prints each delivery, and whether its signature checks out, the way a
site would check it.

    python -m app.scripts.webhook_listener            # on http://localhost:8787/webhooks
    python -m app.scripts.webhook_listener --fail     # answer 500, to watch the retries

Point the demo community at it by setting DEMO_WEBHOOK_URL=http://localhost:8787/webhooks in core/.env: the dev seed
then gives it a webhook with the shared development secret. Or point any community at it with app.scripts.set_webhook
and pass the secret it prints as --secret.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.services.webhook_service import DEMO_SECRET, verify


def make_handler(secret: str, fail: bool):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            ok = verify(
                secret,
                self.headers.get("webhook-id"),
                self.headers.get("webhook-timestamp"),
                self.headers.get("webhook-signature"),
                body,
            )
            try:
                shown = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
            except ValueError:
                shown = body
            print(f"\n── {self.headers.get('webhook-id')}  signature {'OK' if ok else 'BAD'}"
                  f"{'  (answering 500)' if fail and ok else ''}\n{shown}", flush=True)

            status = 401 if not ok else 500 if fail else 204
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):
            pass  # The summary above is enough

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print webhook deliveries and check their signatures")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--secret", default=DEMO_SECRET, help="The endpoint's whsec_ secret (default: the dev one)")
    parser.add_argument("--fail", action="store_true", help="Answer 500, so ThreadFS retries")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.secret, args.fail))
    print(f"Listening on http://localhost:{args.port}/webhooks (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
