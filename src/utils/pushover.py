from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path, override=False)


def send_pushover_notification(title: str, message: str) -> None:
    """
    Envoie une notification via le service NotifyHub/Pushover

    Garde-fou :
    - si la configuration n'est pas définie dans les variables d'environnement,
      la fonction ne fait rien ;
    - si l'envoi échoue, la fonction affiche un message simple puis continue.

    Variables d'environnement attendues :
    - NOTIFYHUB_BASE_URL
    - NOTIFYHUB_API_KEY
    """
    base_url = os.getenv("NOTIFYHUB_BASE_URL", "").strip()
    api_key = os.getenv("NOTIFYHUB_API_KEY", "").strip()

    if not base_url or not api_key:
        return

    endpoint = f"{base_url.rstrip('/')}/v1/notify"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }
    payload = {
        "title": title,
        "message": message,
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[notification] Envoi impossible : {exc}")