# Arquitectura de task3-prototype

## Objetivo y problema

`task3-prototype` busca facilitar el descubrimiento, la comprensión y la reutilización responsable de datasets lingüísticos indígenas, inicialmente de Quechua y Aymara. Actualmente, explorar muchos corpus exige descargar archivos, interpretar formatos heterogéneos y escribir código antes de conocer su contenido.

Esta primera iteración crea únicamente la arquitectura base y un endpoint de salud. No implementa el catálogo, Atlas Vivo, Corpus Radio, Dataset Playbook ni procesamiento real.

## Arquitectura

El repositorio es un monorepo modular:

- `backend/`: API FastAPI. Separa transporte HTTP, dominio, casos de uso, persistencia, modelos, contratos públicos y configuración de base de datos.
- `frontend/`: ubicación reservada para la futura aplicación Next.js.
- `ml/`: canal de integración y análisis, dividido en ingestión, preprocesamiento, embeddings, análisis y evaluación.
- `datasets/`: futuros manifiestos por idioma y esquemas canónicos.
- `data/`: datos locales separados según su etapa de transformación.
- `notebooks/`: exploraciones reproducibles, no lógica de producción.
- `docs/`: decisiones y documentación técnica.
- `scripts/`: tareas operativas explícitas y reutilizables.

La solución empieza como un monolito modular para mantener el despliegue y el aprendizaje simples. PostgreSQL será la fuente de persistencia y la imagen de Docker incluye pgvector para una iteración posterior.

## Flujo general de datos

1. Un adaptador futuro lee un corpus externo y registra su procedencia y licencia.
2. La copia original se conserva sin cambios en `data/raw/`.
3. Validaciones y transformaciones trazables producen artefactos en `data/interim/`.
4. Los registros canónicos preparados se escriben en `data/processed/` y, cuando corresponda, en PostgreSQL.
5. La API consulta los datos mediante repositorios y servicios; las interfaces futuras los presentan o exportan.

## Principios de diseño

- Arquitectura centrada en datasets y adaptadores incrementales.
- Procedencia, licencia, idioma y variante como datos explícitos de primera importancia.
- Valores desconocidos representados como `null`; nunca se inventan metadatos.
- Datos originales inmutables y separación clara de etapas.
- Cada registro derivado debe mantener el vínculo con su fuente.
- Responsabilidades pequeñas, nombres claros y configuración por entorno.
- Sin autenticación, microservicios ni abstracciones prematuras en esta etapa.
