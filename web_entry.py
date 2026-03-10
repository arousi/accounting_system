import os
import threading
import webbrowser

from app import create_app


app = create_app()


def _open_browser(url):
    # Delay browser launch slightly to ensure the web server is accepting connections.
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


if __name__ == "__main__":
    port = int(os.getenv("ACCOUNTING_WEB_PORT", "5001"))
    host = os.getenv("ACCOUNTING_WEB_HOST", "127.0.0.1")
    open_browser = os.getenv("ACCOUNTING_OPEN_BROWSER", "1") == "1"
    server_url = f"http://{host}:{port}"

    if open_browser:
        _open_browser(server_url)

    app.run(host=host, port=port, debug=False, use_reloader=False)
