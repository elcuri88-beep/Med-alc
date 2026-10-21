# MedGuía (Windows)

Consulta local de guías clínicas. Todo se queda en el PC: el LLM y los embeddings corren en local
(Gemma 4 y EmbeddingGemma vía llama.cpp, en la GPU). La API externa es opcional y está desactivada por defecto.

## Requisitos

- Windows 10/11, Python 3.12 o superior.
- RTX 5080 (16 GB de VRAM) con drivers recientes y CUDA Toolkit 12.8 o superior (Blackwell, sm_120).
- 32 GB de RAM en el equipo de referencia. Con 16 GB o menos se recomienda E2B.

## Instalación (desarrollo)

```powershell
cd medguia-win
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[ui,dev]"
```

### Gemma 4 en GPU (llama-cpp-python con CUDA)

Las wheels precompiladas pueden no incluir sm_120. Si no hay wheel con CUDA para tu versión:

```powershell
$env:CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120"
pip install -e ".[llm]" --no-cache-dir --force-reinstall
```

Requiere Visual Studio Build Tools (carga C++) y el CUDA Toolkit instalados.
Si falla, prueba Vulkan (`-DGGML_VULKAN=on`) como alternativa más lenta.
Comprueba la GPU con `python -c "from llama_cpp import llama_supports_gpu_offload as f; print(f())"`.

## Ejecutar

```powershell
python -m medguia
```

Los datos se guardan en `%LOCALAPPDATA%\MedGuia` (`biblioteca.sqlite`, `ajustes.json`, `modelos\`).
Para usar otra carpeta, define `MEDGUIA_HOME` antes de arrancar.

## Modelos

En **Ajustes → Descargar modelos** se bajan el modelo LLM elegido y EmbeddingGemma, con progreso.
Cada descarga se guarda primero como `.part` y solo se renombra si el SHA-256 coincide.

**Repositorios pendientes de configurar.** Los identificadores de Hugging Face del catálogo no se
han podido verificar desde el entorno de desarrollo. Hasta que los configures, la descarga avisa
con un mensaje claro. Para fijarlos, crea `%LOCALAPPDATA%\MedGuia\modelos.json`:

```json
{
  "gemma-e4b":      {"repo": "usuario/repo-e4b", "archivo": "modelo-e4b.gguf", "sha256": "..."},
  "gemma-e2b":      {"repo": "usuario/repo-e2b", "archivo": "modelo-e2b.gguf"},
  "embeddinggemma": {"repo": "usuario/repo-emb", "archivo": "modelo-emb.gguf"}
}
```

Sin `sha256` publicado, la app guarda el hash calculado al descargar y lo comprueba en las siguientes
verificaciones. Eso detecta corrupción posterior, pero no garantiza que el archivo sea el original.

**Recomendación:** E4B si hay al menos 16 GB de RAM y 8 GB de VRAM; si no, E2B.

## Consultar

1. Pestaña **Consulta**. Filtra por especialidad, sociedad o antigüedad si quieres.
2. La respuesta sale en streaming. Debajo se listan las fuentes: doble clic abre el PDF en la página citada.
3. Si el aviso de verificación aparece, revisa las citas o las cifras señaladas antes de usar la respuesta.
4. Si ningún fragmento supera el umbral de similitud, la app responde «Las guías disponibles no cubren
   esta pregunta» sin llamar al modelo.

**Verificación.** Cada párrafo clínico debe llevar una cita que corresponda a un fragmento recuperado,
y cada cifra con unidad (mg, mmHg, %…) debe aparecer literalmente en ese fragmento. Lo comprueba el código,
no el modelo.

**API externa (OpenRouter).** Está desactivada por defecto. Al activarla, la pregunta y los fragmentos
salen del equipo; la pantalla de consulta lo muestra en rojo. La clave se guarda en el Administrador de
credenciales de Windows, no en `ajustes.json`.

**Liberación de memoria.** Al pasar la app a segundo plano, tras 60 s se descargan los modelos de VRAM y RAM.

## Añadir guías

1. Arrastra PDFs a la pestaña **Biblioteca**, o usa «Importar PDF…».
2. Revisa los metadatos. La indexación empieza sola, con progreso.
3. Si cierras la app a mitad, el documento vuelve a «Pendiente» y se retoma al abrirla.
4. Los PDF escaneados (sin capa de texto) aparecen en «Avisos».

Los PDF no se copian ni se suben a git (`*.pdf` está en `.gitignore`).

## Exportar e importar el índice

«Exportar índice…» genera un `.medidx` con el texto completo de las guías y sus vectores.
Trátalo como uso personal o institucional permitido: contiene texto con copyright.
«Importar índice…» añade los documentos que no estén ya presentes (por SHA-256). Los vectores se copian
solo si el índice se calculó con el mismo modelo de embeddings; si no, se recalculan.

## Pruebas

```powershell
pytest
```

Cubren extracción, troceado, persistencia, vectores, recuperación híbrida, prompt, presupuesto,
verificación de citas y cifras, el pipeline de respuesta con un LLM falso, los proveedores con dobles,
la descarga con verificación de integridad y la interfaz en modo offscreen.

**No cubiertas aquí:** Gemma 4 y EmbeddingGemma reales en GPU (requieren el equipo y los modelos),
y el visor PDF (requiere PySide6 completo). Esas pruebas se hacen a mano; ver la guía de la Fase 2.

## Estructura

- `domain/`: entidades y puertos (LLM, embeddings).
- `ingestion/`: PDF, tablas, troceado, servicio de biblioteca.
- `persistence/`: SQLite, FTS5, sqlite-vec, exportación.
- `retrieval/`: BM25 + vectores, RRF, diversidad, umbral.
- `generation/`: prompt literal, presupuesto, verificador, pipeline.
- `providers/`: Gemma local, EmbeddingGemma local, API compatible con OpenAI.
- `models/`: catálogo, descarga, integridad, recomendación.
- `ui/`: PySide6.
