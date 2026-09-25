# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Usuario primario: el equipo evaluador de HabiCapital** (convocatoria de practicantes 2027). Revisan la aplicación en una ventana corta —el reto contempla ~60 minutos de pair programming sobre este código— y buscan evidencia de que las cinco funciones del núcleo funcionan y de que el rigor técnico detrás (ledger de doble partida, concurrencia, idempotencia, modelo de difusión) es real y explicable.

El usuario final de la billetera es una figura del escenario: una persona en Colombia que ahorra, reparte gastos como el arriendo y quiere entender qué tendría que cambiar para acceder a un crédito de vivienda. Sus tareas definen los flujos, pero cuando una decisión de diseño obliga a elegir, gana lo que hace legible el trabajo al evaluador.

## Stack

Existente. Frontend: React 19 + TypeScript + Vite + react-router-dom 7, CSS propio con tokens en `frontend/src/theme/tokens.css` (sin framework de UI ni librería de componentes). Backend: Python, Django, DRF, PostgreSQL. Modelo de difusión en NumPy (~18.000 parámetros, artefacto de 207 KB). Orquestación con Docker Compose; frontend en `:5173`, API en `:8000`.

## Product Purpose

Una billetera donde cada movimiento de dinero conserva su contexto. Ese historial acumulado sirve como evidencia para explorar la posibilidad de acceder a un crédito de vivienda.

Éxito para el evaluador: las cinco funciones del núcleo se demuestran sin fricción, y la extensión de crédito se entiende como una capa que se apoya en el comportamiento registrado, no como un adorno. Éxito para el usuario del escenario: entender qué cambios acercarían su perfil a uno que podría calificar.

## Positioning

El mecanismo diferencial es la ruta, no un veredicto. Un clasificador puede proponer cambios que alteren su resultado sin ser realistas. El modelo de difusión aprende la forma de la población de perfiles y ajusta la ruta en cada paso para mantenerse cerca de perfiles reales: un test verifica que ningún punto de la ruta quede a más de 0,6 de un perfil existente. El producto muestra un camino plausible entre perfiles, con los cambios que implicaría.

El contexto conservado es la otra mitad: la constancia del ahorro (depósitos a lo largo de varios meses) y el cumplimiento de pagos compartidos (pagar cada mes la parte del arriendo deja un registro entre personas) son datos que la billetera produce como subproducto del uso, no un formulario aparte.

## Operating Context

- **El núcleo del reto, que ninguna decisión de diseño puede desplazar ni esconder:**
  1. Crear una cuenta (un usuario con saldo).
  2. Cargar saldo (simulado, sin pasarela real).
  3. Transferir saldo entre cuentas del sistema.
  4. Consultar el saldo en cualquier momento.
  5. Ver el historial de movimientos de la cuenta.
  La ruta al crédito y el modelo de difusión son la capa que va encima. Si compiten por atención, el núcleo gana.
- Rutas actuales: `/entrar`, `/cuentas/nueva`, `/` (dashboard), `/recargar`, `/transfer`, `/history`, `/ruta`, `/expenses/new`, `/expenses/:expenseId`.
- Un gasto compartido lo paga una persona y las demás le transfieren su parte; una transferencia asociada solo es válida si va de un participante a quien pagó.
- El evaluador puede llegar por `docker compose up --build`, por el README, o leyendo el código. Existe un seed de demostración con 14 meses de historial (`scripts/seed_demo.py`), que es lo que hace visible la constancia del ahorro.

## Capabilities and Constraints

- **La ruta al crédito no aprueba ni rechaza nada, y no muestra puntaje.** No hay score, ni "aprobado/rechazado", ni número que pueda leerse como evaluación. La interfaz muestra escenarios derivados del comportamiento registrado y debe declarar ese límite.
- **Autenticación simulada, visible como tal.** Existe una pantalla de acceso, pero la contraseña no se envía, no se guarda y no se compara; solo se verifica que el usuario exista. La interfaz no debe aparentar más seguridad de la que hay.
- **Una sola moneda: COP.** La interfaz recibe y muestra pesos enteros; el sistema guarda centavos (el reparto los necesita). Mezclar monedas lanza excepción.
- **Los depósitos son simulados y siempre se completan.** No hay pasarela de pagos.
- **El saldo se calcula desde el ledger**, no se guarda como columna. No hay estado de saldo que la interfaz pueda mostrar desincronizado.
- **Se permite pagar de más** en un gasto compartido: el pendiente llega a cero y la interfaz muestra el excedente.
- **Un gasto compartido requiere al menos dos participantes**, y se rechaza si el total es menor que el número de participantes.
- Fuera de alcance por decisión explícita, que el diseño no debe insinuar como disponible: autenticación real, editar o borrar gastos, otros métodos de reparto además del equitativo, paginación, búsqueda, notificaciones, gastos recurrentes, reversos, comisiones, varias monedas.
- **Deuda conocida:** no hay tests de frontend. La animación de partículas en canvas se verificó solo a mano.

## Brand Commitments

- Nombre y marca: **habi capital**. Logo en `frontend/src/assets/habi-logo.png`, acompañado de la palabra "capital".
- Morado `#7c01ff` como color de marca, con la paleta actual derivada de él (`--color-purple-soft: #f4ebff`, teal de apoyo `#087c70`).
- **Todo el copy en español colombiano.** `<html lang="es">`. Montos en COP con formato local.
- Línea presente en el pie: "El dinero cuenta historias."

## Evidence on Hand

Real y verificable, disponible para cualquier trabajo futuro:

- `README.md` — las ocho preguntas del reto respondidas, con decisiones, límites y supuestos.
- `docs/architecture-decisions.md` — cada patrón, su costo y las alternativas descartadas.
- `docs/ai-log.md` — tres casos registrados de error y corrección trabajando con agentes.
- `docs/GOALS.md`, `AGENTS.md`, `.agents/skills/safe-financial-implementation/`.
- 185 tests en el backend, incluidos concurrencia con hilos reales y 11 tests del modelo de difusión.
- Resultados medidos que se pueden citar tal cual: 2.500 perfiles generados con distancia mediana de `0,056` al perfil real más cercano; clasificador en 72,9% frente a 70,0% de la clase mayoritaria; 32.934 combinaciones de reparto verificadas; suma del ledger igual a `0` tras las pruebas.
- Dataset: UCI German Credit (1.000 perfiles, 20 atributos, Alemania, 1994, crédito de consumo). El mapeo a comportamiento colombiano lo definió el autor y vive en `domain/credit.py`.

**No existe y no debe fabricarse:** usuarios reales, testimonios, clientes, casos de estudio, prensa, cifras de adopción, precios, acuerdos con entidades financieras, validación del modelo para uso real (no hay validación cruzada, ni conjunto de prueba separado, ni auditoría de sesgos).

## Product Principles

1. **El núcleo primero.** Las cinco funciones del reto deben ser evidentes y completables sin buscar. La extensión de crédito se apoya sobre ellas; nunca las tapa.
2. **El contexto es el producto.** Cada movimiento conserva por qué ocurrió. Un historial que se lee como una lista de cifras pierde lo único que justifica la extensión de crédito.
3. **Ruta, no veredicto.** Mostrar el camino y lo que implicaría. Ningún elemento de la interfaz puede leerse como una decisión de crédito ni como un puntaje.
4. **Decir exactamente lo que es.** Depósitos simulados, acceso simulado, modelo sin validación para uso real: cada límite se declara donde el usuario lo encuentra, no solo en el README.
5. **El rigor se ve o no cuenta.** El evaluador no leerá los 185 tests durante la demo. Lo que la interfaz hace visible —la conservación del dinero, la inmutabilidad del historial, la cercanía de la ruta a perfiles reales— es la parte del rigor que llega.

## Accessibility & Inclusion

**WCAG 2.1 AA como piso.** Contraste suficiente en texto y controles, foco visible, navegación completa por teclado, y `prefers-reduced-motion` respetado.

Estado actual e implicaciones pendientes: el skip-link ("Ir al contenido") ya existe y `<html lang="es">` está puesto; el uso de `aria-*` es mínimo (solo `aria-invalid` en un formulario y `aria-label` en la navegación), y la animación de partículas en canvas necesita una alternativa estática y respetar movimiento reducido. El mapa de crédito, al ser una visualización, requiere un equivalente textual de la ruta y sus cambios.
