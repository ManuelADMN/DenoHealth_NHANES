# Denoise the Health — NHANES Coach (RAG + ML + API + UI)

Solución lista para **local**, **Colab** o **Docker** que integra:
- **API FastAPI** para extracción de datos en lenguaje natural, predicción ML, plan de hábitos guiado por KB (RAG) y generación de reportes.
- **UI Gradio** en tema oscuro con **tarjetas clickeables** (prompts rápidos), chat y **descarga de reportes** (PDF y HTML).
- **RAG local** con búsqueda híbrida (BM25 + embeddings cuando están disponibles) sobre la carpeta `kb/`.
- **Empaquetado** del proyecto en un ZIP único sin sobreescribir tu trabajo previo (reusa lo que ya esté en `/content` y rellena solo lo mínimo si falta).

---

## Estructura del proyecto

```
NHANES_Coach/
  api/
    main.py               # FastAPI: /health, /endpoints, /extract, /predict, /coach_llm, /kb/search, /report/pdf
  app/
    gradio_app.py         # UI Gradio: chat oscuro, tarjetas clickeables, descarga de PDF/HTML
  kb/                     # Base de conocimiento (RAG): .md / .txt / .pdf
  artifacts/              # Modelo y metadatos (opcional): model_calibrated.joblib, features.json, label_mode.txt
  exports/                # Reportes generados (PDF) y archivos listos para descarga
  scripts/
    run_api.sh            # Arranque rápido de API
    run_ui.sh             # Arranque rápido de UI
  Dockerfile.api          # Contenedor para la API
  Dockerfile.ui           # Contenedor para la UI
  docker-compose.yml      # Orquestación API + UI
  README.md               # (este documento)
```

---

## Arranque rápido (entorno local)

1) Crear entorno e instalar dependencias:
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.api.txt -r requirements.ui.txt
```

2) Levantar API (puerto 8000):
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

3) Levantar UI (puerto 7860) en otra terminal:
```bash
python -m app.gradio_app
```

4) **Smoke test** rápido de la API:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/extract -H "Content-Type: application/json" -d '{"text":"hombre 42 años 1.75m 86kg presión 128/82"}'
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"sex":"M","age":42,"height_cm":175,"weight_kg":86,"waist_cm":92,"sbp":128,"dbp":82,"sleep_hours":6.5,"days_mvpa_week":3,"income_poverty_ratio":2.0}'
```

---

## Uso en Colab / cuaderno

- Las celdas de empaquetado **reusan** `api/`, `app/`, `kb/`, `artifacts/`, `exports/` si ya existen en `/content` y **no sobreescriben** archivos.
- Si falta algo clave, se crean **fallbacks mínimos** estables (por ejemplo, `api/main.py` o `app/gradio_app.py`).
- El ZIP final se guarda como **`/mnt/data/DenoHealth_NHANES.zip`** y se deja una copia en la raíz del entorno de trabajo.

---

## Ejecución con Docker

### Build manual (opcional)
```bash
docker build -t nhanes-api  -f Dockerfile.api .
docker build -t nhanes-ui   -f Dockerfile.ui  .
docker run --rm -p 8000:8000 nhanes-api
docker run --rm -p 7860:7860 --network host nhanes-ui
```

### Con Docker Compose (recomendado)
```bash
docker compose up --build
```
- API disponible en `http://localhost:8000`
- UI disponible en `http://localhost:7860`

> El `docker-compose.yml` monta `./kb`, `./artifacts` y `./exports` como volúmenes en el contenedor de la API para que puedas actualizar documentación, modelos o descargar reportes sin reconstruir imágenes.

---

## Endpoints principales de la API

- `GET /health`  
  Estado de carga de modelo, features y tamaño de la KB.

- `GET /endpoints`  
  Índice de rutas disponibles.

- `POST /extract`  
  **Entrada**: `{"text": "...texto libre con edad, talla, peso, PA, sueño, objetivo..."}`  
  **Salida**: JSON con campos normalizados (sexo, edad, altura, peso, cintura, PA, etc.).

- `POST /predict`  
  **Entrada**: JSON con los campos normalizados.  
  **Salida**: `{ "score": <probabilidad>, "drivers": [...], "bmi": <IMC> }`

- `POST /coach_llm?goal=<objetivo>`  
  **Entrada**: JSON con los campos del paciente.  
  **Salida**: Plan priorizado (4–12 semanas) y citas de la KB local.

- `GET /kb/search?q=<consulta>&k=5`  
  Búsqueda híbrida en la carpeta `kb/` (archivos `.md`, `.txt`, `.pdf`).

- `POST /report/pdf`  
  Genera un PDF con el plan y lo guarda en `exports/` para descarga desde la UI.

---

## UI (Gradio)

- **Tema oscuro** y layout legible de conversación.
- **Tarjetas clickeables** con prompts de ejemplo (perfiles/goles y consultas KB).
- Chat que orquesta `/extract → /predict → /coach_llm` mostrando:
  - **Score de riesgo** y **drivers** del modelo.
  - **Plan priorizado** + **citas** relevantes de la KB.
  - Pestañas colapsables con la **entrada interpretada** y la **respuesta de predicción**.
- **Descarga de reportes**:
  - **PDF**: vía `POST /report/pdf` y carpeta `exports/`.
  - **HTML**: generado por la UI con resumen, plan, entrada y resultados.

---

## Base de conocimiento (RAG)

- Coloca documentos en `kb/` (`.md`, `.txt`, `.pdf`).  
- La indexación es **automática** al levantar la API.  
- La búsqueda es híbrida: **BM25** siempre y **embeddings** cuando el runtime dispone del backend de embeddings (se activa solo si está presente).

---

## Modelos y artefactos

- Si dispones de un modelo calibrado: `artifacts/model_calibrated.joblib`
- Lista de features esperadas: `artifacts/features.json`
- Modo de etiquetas (si aplica): `artifacts/label_mode.txt`

> Si estos archivos **no** están presentes, la API responderá con valores por defecto (la UI seguirá funcionando y generará planes educativos con soporte de la KB).

---

## Exports y logging

- Reportes (PDF/HTML) en `exports/`.
- Eventos de uso (prompts/requests) en `logs/prompts.jsonl` (se crea automáticamente si existe permiso de escritura).

---

## Buenas prácticas operativas

- **Privacidad**: el material es educativo y no reemplaza evaluación clínica.
- **Trazabilidad**: mantén separados `kb/` (fuentes), `artifacts/` (modelos) y `exports/` (salidas).
- **Portabilidad**: usa Docker Compose para la demo completa y CI/CD para despliegues.
- **Observabilidad**: conserva `logs/prompts.jsonl` para auditoría básica y mejora continua.

---

## Licencia y atribuciones

Hecho con amor por Manuel Díaz.
