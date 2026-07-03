from __future__ import annotations

import argparse
import webbrowser

from liquidation_pulse.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC liquidation and on-chain dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}"
    print(f"Bitcoin Liquidation Pulse running at {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Bitcoin Liquidation Pulse.")


if __name__ == "__main__":
    main()
