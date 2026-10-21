"""Bloqueo opcional al abrir con Windows Hello (huella, rostro o PIN del equipo).

Requiere los paquetes winrt de Windows (ver README). Si no están, `disponible()` devuelve False
y la app no permite activar el bloqueo.
"""

from __future__ import annotations

import asyncio
from typing import Protocol


class VerificadorIdentidad(Protocol):
    def disponible(self) -> bool: ...

    def verificar(self, motivo: str) -> bool: ...


class WindowsHello:
    def disponible(self) -> bool:
        try:
            resultado = asyncio.run(self._disponibilidad())
        except Exception:
            return False
        return resultado

    def verificar(self, motivo: str) -> bool:
        try:
            return asyncio.run(self._pedir(motivo))
        except Exception:
            return False

    async def _disponibilidad(self) -> bool:
        from winrt.windows.security.credentials.ui import (
            UserConsentVerifier,
            UserConsentVerifierAvailability,
        )

        estado = await UserConsentVerifier.check_availability_async()
        return estado == UserConsentVerifierAvailability.AVAILABLE

    async def _pedir(self, motivo: str) -> bool:
        from winrt.windows.security.credentials.ui import (
            UserConsentVerificationResult,
            UserConsentVerifier,
        )

        resultado = await UserConsentVerifier.request_verification_async(motivo)
        return resultado == UserConsentVerificationResult.VERIFIED


def desbloqueo_necesario(ajustes_bloqueo: bool, verificador: VerificadorIdentidad) -> bool:
    """True si hay que pedir identidad antes de abrir. Sin Hello disponible, la app abre con aviso."""
    return ajustes_bloqueo and verificador.disponible()
