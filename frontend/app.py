import os

import requests
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

API_BASE_URL = os.getenv("API_BASE_URL", "http://haproxy:80")
API_KEY = os.getenv("API_KEY")

ROLE_PERMISSIONS = {
    "interesado": [
        "Ver documentos personales propios",
        "Ver libelos propios",
        "Firmar cuando sea solicitado",
    ],
    "testigo": [
        "Ver identificacion propia",
        "Ver libelos propios",
        "Firmar cuando sea solicitado",
    ],
    "abogado": [
        "Ver libelos de clientes asignados",
        "Consultar estado de expediente",
    ],
    "juez": [
        "Ver casos activos",
        "Descargar desde web si esta autorizado",
        "Firmar documentos asignados",
    ],
    "notario": [
        "Acceso documental completo",
        "Descargar desde web",
        "Autorizar y firmar documentos",
    ],
    "admin_ti": [
        "Gestion tecnica",
        "Auditoria operativa",
        "Soporte sin acceso implicito al contenido",
    ],
    "admin": [
        "Gestion tecnica",
        "Auditoria operativa",
    ],
}


def build_headers(channel="web"):
    headers = {
        "Accept": "application/json",
        "x-client-channel": channel,
    }

    if API_KEY:
        headers["x-api-key"] = API_KEY

    token = session.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def api_request(method, path, **kwargs):
    response = requests.request(
        method,
        f"{API_BASE_URL}{path}",
        headers=build_headers(kwargs.pop("channel", "web")),
        timeout=10,
        **kwargs,
    )

    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "url": f"{API_BASE_URL}{path}",
        "data": data,
    }


def current_user():
    user = session.get("usuario")
    if not user:
        return None

    role = user.get("role")
    return {
        **user,
        "permissions": ROLE_PERMISSIONS.get(role, ["Consulta limitada por API"]),
        "can_download_web": role in {"juez", "notario"},
    }


def load_dashboard(selected_case_id=None, selected_document_id=None):
    user = current_user()
    cases = []
    documents = []
    document_view = None
    result = None

    if not user:
        return cases, documents, document_view, result

    cases_result = api_request("GET", "/api/cases")
    result = cases_result

    if cases_result["ok"]:
        cases = cases_result["data"]

    if not selected_case_id and cases:
        selected_case_id = str(cases[0]["id"])

    if selected_case_id:
        documents_result = api_request("GET", f"/api/cases/{selected_case_id}/documents")
        result = documents_result

        if documents_result["ok"]:
            documents = documents_result["data"]

    if selected_document_id:
        view_result = api_request("GET", f"/api/documents/{selected_document_id}/view")
        result = view_result

        if view_result["ok"]:
            document_view = view_result["data"]

    return cases, documents, document_view, result


@app.route("/", methods=["GET", "POST"])
def index():
    message = None
    selected_case_id = request.form.get("case_id") or request.args.get("case_id")
    selected_document_id = request.form.get("document_id") or request.args.get("document_id")

    if request.method == "POST":
        action = request.form.get("accion")

        if action == "login":
            payload = {
                "email": request.form.get("email", ""),
                "password": request.form.get("password", ""),
            }
            login_result = api_request("POST", "/login", json=payload)

            if login_result["ok"]:
                session["token"] = login_result["data"].get("access_token")
                session["usuario"] = login_result["data"].get("usuario")
                return redirect(url_for("index"))

            message = login_result["data"]

        elif action == "logout":
            session.clear()
            return redirect(url_for("index"))

        elif action == "download" and selected_document_id:
            download_result = api_request(
                "GET",
                f"/api/documents/{selected_document_id}/download",
            )
            message = download_result["data"]

    cases, documents, document_view, result = load_dashboard(
        selected_case_id,
        selected_document_id,
    )

    return render_template(
        "index.html",
        api_url=API_BASE_URL,
        usuario=current_user(),
        cases=cases,
        documents=documents,
        selected_case_id=selected_case_id,
        selected_document_id=selected_document_id,
        document_view=document_view,
        resultado=result,
        message=message,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "flask"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
