import os
from flask import Flask, render_template, request

app = Flask(__name__)


@app.get("/")
@app.post("/")
def index():
    api_version = request.form.get("api_version", "v4")
    api_url = os.getenv("API_BASE_URL", "http://api_v4:8000")

    return render_template(
        "index.html",
        api_version=api_version,
        api_url=api_url,
        requiere_api_key=True,
        requiere_jwt=True,
        usuario=None,
        token=None,
        resultado=None,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "flask"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
