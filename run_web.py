import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("ACCOUNTING_WEB_PORT", "5001"))
    host = os.getenv("ACCOUNTING_WEB_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=True)
