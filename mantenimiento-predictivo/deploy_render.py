"""Publica o reutiliza la demo en Render sin crear recursos de pago."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NAME = "mantenimiento-predictivo-demo"
REPO = "https://github.com/occ108/33"
BRANCH = "deploy/mantenimiento-predictivo"


class RenderAPI:
    def __init__(self):
        self.token = os.environ.get("RENDER_API_KEY")
        if not self.token:
            raise RuntimeError("RENDER_API_KEY no está disponible en este proceso.")

    def send(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            "https://api.render.com/v1" + path,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Industrial-Maintenance-Deployment/1.0",
            },
        )
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                message = json.loads(raw).get("message", "Solicitud rechazada")
            except (ValueError, AttributeError):
                message = "El proveedor bloquea esta solicitud; no devuelve JSON."
            raise RuntimeError(
                f"Render HTTP {exc.code}: {str(message).replace(self.token, '[oculto]')}"
            ) from None


def ensure_service(api, owner_id):
    query = urlencode({"ownerId": owner_id, "name": NAME, "limit": 100})
    matches = [
        item["service"]
        for item in api.send("GET", "/services?" + query)
        if item["service"]["name"] == NAME
        and item["service"]["ownerId"] == owner_id
    ]
    if len(matches) > 1:
        raise RuntimeError("Hay varios servicios coincidentes; revisar antes de continuar.")
    if matches:
        service = matches[0]
        if (
            service.get("type") != "web_service"
            or service.get("repo", "").removesuffix(".git") != REPO
            or service.get("branch") != BRANCH
            or service.get("serviceDetails", {}).get("plan") != "free"
        ):
            raise RuntimeError("Existe un servicio con ese nombre y otra configuración.")
        return service, False

    result = api.send(
        "POST",
        "/services",
        {
            "type": "web_service",
            "name": NAME,
            "ownerId": owner_id,
            "repo": REPO,
            "branch": BRANCH,
            "autoDeployTrigger": "commit",
            "envVars": [{"key": "PORT", "value": "8501"}],
            "serviceDetails": {
                "runtime": "docker",
                "plan": "free",
                "region": "frankfurt",
                "healthCheckPath": "/_stcore/health",
                "envSpecificDetails": {
                    "dockerfilePath": "./mantenimiento-predictivo/Dockerfile",
                    "dockerContext": "./mantenimiento-predictivo",
                },
            },
        },
    )
    return result["service"], True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", required=True, help="ID del workspace tea-… o usr-…")
    parser.add_argument("--state-file", default="/tmp/mantenimiento-render-state.json")
    args = parser.parse_args()
    if not args.owner_id.startswith(("tea-", "usr-")):
        parser.error("El identificador debe empezar por tea- o usr-.")
    try:
        service, created = ensure_service(RenderAPI(), args.owner_id)
    except RuntimeError as exc:
        parser.exit(1, str(exc) + "\n")
    state = {
        "id": service["id"],
        "owner_id": args.owner_id,
        "url": service.get("serviceDetails", {}).get("url"),
        "dashboard_url": service.get("dashboardUrl"),
        "created": created,
    }
    Path(args.state_file).write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2))
    print("La creación del servicio no acredita todavía que el despliegue esté disponible.")


if __name__ == "__main__":
    main()
