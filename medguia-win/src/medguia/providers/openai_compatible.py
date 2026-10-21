"""API opcional compatible con OpenAI (OpenRouter). La consulta SALE DEL DISPOSITIVO: la UI debe avisarlo."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from medguia.domain.puertos import AlRecibirToken, Mensaje

URL_OPENROUTER = "https://openrouter.ai/api/v1"
TEMPERATURA = 0.1


class ErrorApi(Exception):
    pass


class ApiCompatibleOpenAI:
    nombre = "openrouter"

    def __init__(
        self,
        modelo: str,
        obtener_clave: Callable[[], str],
        base_url: str = URL_OPENROUTER,
        cliente: httpx.Client | None = None,
    ) -> None:
        self._modelo = modelo
        self._obtener_clave = obtener_clave
        self._base_url = base_url.rstrip("/")
        self._cliente = cliente or httpx.Client(timeout=120)

    def generar(self, mensajes: list[Mensaje], al_recibir_token: AlRecibirToken | None = None) -> str:
        clave = self._obtener_clave()
        if not clave:
            raise ErrorApi("No hay clave de API configurada")
        cuerpo = {
            "model": self._modelo,
            "temperature": TEMPERATURA,
            "stream": True,
            "messages": [{"role": m.rol, "content": m.texto} for m in mensajes],
        }
        partes: list[str] = []
        with self._cliente.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {clave}"},
            json=cuerpo,
        ) as respuesta:
            if respuesta.status_code >= 400:
                raise ErrorApi(f"La API respondió {respuesta.status_code}")
            for linea in respuesta.iter_lines():
                if not linea.startswith("data: "):
                    continue
                datos = linea[len("data: ") :]
                if datos.strip() == "[DONE]":
                    break
                delta = json.loads(datos)["choices"][0].get("delta", {}).get("content")
                if delta:
                    partes.append(delta)
                    if al_recibir_token:
                        al_recibir_token(delta)
        return "".join(partes)

    def liberar(self) -> None:
        return None
