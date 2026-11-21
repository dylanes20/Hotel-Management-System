# Entrega de Project Advance

| Requisito | Estado y evidencia |
|---|---|
| Esquema y scripts SQL | Disponibles en `database/`. El informe Stage 2 y sus capturas originales están en `docs/`. |
| API CRUD | Implementada para huéspedes, habitaciones y reservas en `backend/`. |
| Pruebas API | [Informe](API_TEST_REPORT.md) y [resultado de Omarchy](evidence/api/pytest_results.txt). 22 aprobadas en MySQL aislado. |
| GUI con eliminación de reservas | Implementada y servida por Flask. [Comprobación local](evidence/gui/smoke-flask.txt). |
| Integración GUI, API y MySQL | [Recorrido de verificación](evidence/gui/README.md) pendiente en navegador con MySQL. |
| README e informe final | README con instrucciones del backend y la GUI. Informe final pendiente de las evidencias de integración. |
| GitHub | Pendiente recuperar la URL original, revisar los archivos y publicar con autorización. |

## Recuperar el repositorio original

La carpeta extraída y el ZIP carecen de metadatos Git. El directorio
`.git` vacío en la carpeta superior tampoco identifica un repositorio. La
URL mostrada anteriormente en el README era un ejemplo. Recupera la URL desde
el enlace de descarga de GitHub, el historial del navegador o el compañero
que compartió el proyecto.

Con la URL confirmada, clona en una carpeta hermana nueva. Conserva la carpeta
de trabajo actual como respaldo. Desde la carpeta superior, realiza una
simulación antes de copiar:

```bash
git clone 'URL_ORIGINAL_CONFIRMADA' hotel-entrega
rsync -an --itemize-changes \
  --exclude='.git' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --include='.env.example' --exclude='.env*' \
  --exclude='*.log' --exclude='*.key' --exclude='*.pem' \
  hotel_managment-main/ hotel-entrega/
```

Compara los archivos existentes en el clon que la simulación propone
sobrescribir. Integra manualmente cualquier cambio del repositorio original
que deba conservarse. Si la simulación coincide con lo esperado, repite
`rsync` con `-a` en lugar de `-an` y revisa desde `hotel-entrega/`:

```bash
git remote -v
git status --short --ignored
git diff --check
git diff
```

Antes de preparar un commit, revisa los archivos nuevos y los ya rastreados.
Comprueba que no incluyan credenciales, `.env`, entornos virtuales, datos
personales ni volcados reales. Revisa visualmente el PDF y las capturas de
Stage 2, y aplica la misma revisión a los nuevos registros y capturas. Antes
de publicar revisa también el historial si ya contenía archivos sensibles.
El estado de cada prueba del informe debe corresponder a una ejecución
registrada. Distingue las capturas históricas de Stage 2 de los resultados
de Project Advance.
