"""Muestreo del pico de memoria del proceso (RAM) y de la GPU (VRAM vía nvidia-smi)."""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class PicoMemoria:
    ram_gb: float
    vram_gb: float | None


class MedidorMemoria:
    def __init__(self, intervalo_s: float = 0.2) -> None:
        self._intervalo = intervalo_s
        self._parar = threading.Event()
        self._proceso = psutil.Process()
        self._herramienta = shutil.which("nvidia-smi")
        self._ram_max = 0
        self._vram_max: float | None = None
        self._hilo = threading.Thread(target=self._bucle, daemon=True)

    def __enter__(self) -> MedidorMemoria:
        self._muestrear()
        self._hilo.start()
        return self

    def __exit__(self, *_) -> None:
        self._parar.set()
        self._hilo.join(timeout=2)
        self._muestrear()

    def pico(self) -> PicoMemoria:
        return PicoMemoria(ram_gb=self._ram_max / 1024**3, vram_gb=self._vram_max)

    def _bucle(self) -> None:
        while not self._parar.wait(self._intervalo):
            self._muestrear()

    def _muestrear(self) -> None:
        self._ram_max = max(self._ram_max, self._proceso.memory_info().rss)
        vram = _vram_usada_gb(self._herramienta)
        if vram is not None:
            self._vram_max = max(self._vram_max or 0.0, vram)


def _vram_usada_gb(herramienta: str | None) -> float | None:
    if herramienta is None:
        return None
    try:
        salida = subprocess.run(
            [herramienta, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout
        return float(salida.strip().splitlines()[0]) / 1024
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None
