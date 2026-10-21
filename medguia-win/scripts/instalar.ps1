# Crea el entorno virtual e instala MedGuía. Para Gemma en GPU, ver la sección CUDA del README.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1  [-ConLlm]
param([switch]$ConLlm)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -e ".[ui,dev]"

if ($ConLlm) {
    # Requiere Visual Studio Build Tools (C++) y CUDA Toolkit 12.8+ para la RTX 5080 (sm_120).
    $env:CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120"
    & .venv\Scripts\python.exe -m pip install -e ".[llm]" --no-cache-dir --force-reinstall
    & .venv\Scripts\python.exe -c "from llama_cpp import llama_supports_gpu_offload as f; print('GPU offload:', f())"
} else {
    Write-Host "Falta llama-cpp-python para ejecutar los modelos. Repite con -ConLlm cuando tengas CUDA listo."
}
& .venv\Scripts\python.exe -m pytest -q
