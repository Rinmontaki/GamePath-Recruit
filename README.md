
# GamePath Recruit

Sistema de reclutamiento, evaluación y formación de jugadores competitivos de VALORANT, utilizando estructuras de datos no lineales.

## Objetivo

Desarrollar una aplicación que permita evaluar preliminarmente a aspirantes a jugadores profesionales de VALORANT, gestionar su proceso de reclutamiento y generar rutas personalizadas de formación orientadas al desarrollo competitivo y al acceso a posibles oportunidades de monetización.

## Estructuras de datos

### Grafo dirigido y ponderado (principal)
- Representar rutas de entrenamiento y preparación competitiva.
- Modelar habilidades, estados de progreso y requisitos.
- Aplicar BFS y DFS para explorar recorridos.
- Aplicar Dijkstra para calcular rutas válidas de menor costo estimado.

### Árbol binario de decisión (secundario)
- Evaluar la disponibilidad de entrenamiento.
- Clasificar según el peak rank.
- Determinar la categoría de preselección del aspirante.

## Funcionamiento general

1. Registro del aspirante.
2. Perfilamiento mediante árbol binario.
3. Carga y revisión de grabaciones (VOD).
4. Evaluación y admisión por parte del reclutador.
5. Generación de rutas personalizadas de formación.
6. Reevaluación del rendimiento competitivo.
7. Orientación hacia oportunidades de monetización.

## Monetización

El sistema contempla tres alternativas:

- Participación en torneos con premios.
- Pruebas de selección y posibles contratos con equipos.
- Oportunidades de patrocinio.

La aplicación orienta al jugador, pero no garantiza ingresos ni contratación profesional.

## Tecnologías

- Python: backend y algoritmos.
- Streamlit: interfaz web.
- SQLite: persistencia de información.
- Git y GitHub: control de versiones.

## Estado del proyecto

En desarrollo.

Primera fase: construcción y pruebas del backend.
Segunda fase: desarrollo del frontend e integración.
