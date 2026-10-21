# MedGuía (Windows)

Consulta local de guías clínicas. Fase 1: ingesta, índice y biblioteca.
Todo se queda en el PC; no hay servidor.

## Requisitos

- Windows 10/11, Python 3.12 o superior.
- Para la Fase 2 (Gemma 4 en GPU): RTX 5080 con drivers recientes y CUDA 12.8 o superior.
  La RAM mínima recomendada es 16 GB; esta máquina tiene 32 GB.

## Instalación (desarrollo)

```powershell
cd medguia-win
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[ui,dev]"
```

## Ejecutar

```powershell
python -m medguia
```

Los datos se guardan en `%LOCALAPPDATA%\MedGuia\biblioteca.sqlite`.
Para usar otra carpeta, define `MEDGUIA_HOME` antes de arrancar.

## Añadir guías

1. Arrastra PDFs a la ventana, o usa «Importar PDF…».
2. Revisa los metadatos: título, sociedad, año, ámbito y especialidad.
3. La indexación empieza sola y muestra el progreso. Si cierras la app a mitad,
   el documento vuelve a «Pendiente» y se retoma al abrirla.
4. Los PDF escaneados (sin capa de texto) aparecen en la columna «Avisos».

Los PDF no se copian ni se suben a git (`*.pdf` está en `.gitignore`).

## Exportar e importar el índice

«Exportar índice…» genera un `.medidx` con el texto completo de las guías.
Trátalo como uso personal o institucional permitido: contiene texto con copyright.
«Importar índice…» añade los documentos que no estén ya presentes (por SHA-256).

## Pruebas

```powershell
pytest
```

Incluye extracción, troceado, persistencia, exportación y un test de la interfaz
en modo offscreen (se omite si PySide6 no está instalado).

## Estructura

Ver `src/medguia/`: `domain` (entidades), `ingestion` (PDF, tablas, troceado, servicio),
`persistence` (SQLite, FTS5, exportación), `ui` (PySide6).
