# Goals: qué se construye, en qué orden y cómo correrlo

Documento de seguimiento. Lo actualizo al cerrar cada goal.
Para el detalle de un goal en curso, ver `PLAN.md` en la raíz (se reescribe por goal).

## Estado

| # | Goal | Estado |
|---|---|---|
| 0 | Fundación ejecutable | ✅ cerrado |
| 1 | Money, Account, Ledger, Deposit | ✅ cerrado |
| 2 | Transferencias seguras | ✅ cerrado |
| 3 | Gastos compartidos + contexto | ⬜ |
| 4 | Frontend MVP | ⬜ |
| 5 | Endurecimiento adversarial + auditoría | ⬜ |
| 6 | README, decisiones y demo | ⬜ |

---

## Cómo se ejecuta

Una sola vez:

```sh
cp .env.example .env
docker compose up -d db
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
cd frontend && npm install --package-lock=false
```

Correr los tests (requiere el contenedor `db` arriba):

```sh
cd backend
POSTGRES_HOST=localhost POSTGRES_USER=habicapital \
POSTGRES_PASSWORD=local-development-only POSTGRES_DB=habicapital \
../.venv/Scripts/python.exe -m pytest -v
```

Levantar la app:

```sh
cd backend && ../.venv/Scripts/python.exe manage.py runserver 8000   # :8000
cd frontend && npm run dev                                          # :5173
```

Todo junto en contenedores: `docker compose up --build`.

---

## Qué cambió respecto al plan original

El plan inicial se escribió **antes** de tener el PDF del reto. Al leerlo cambiaron tres cosas:

1. **De 10 goals a 7.** La ventana sugerida son 72 horas. Fusioné cuentas+ledger+depósito en
   un solo goal (separarlos hacía que el primero escribiera un concepto de saldo que el segundo
   reescribía), y fusioné endurecimiento con auditoría, y README con demo.
2. **La entrevista manda sobre la arquitectura.** Son 60 minutos de pair programming sobre este
   código con un cambio que no anticipo. Eso inclina cada decisión hacia *navegable* en vez de
   *impresionante*: menos indirección, nombres obvios, y ningún patrón que no resuelva un
   problema real.
3. **Las 8 preguntas del README ahora se conocen exactas**, así que el README se escribe al
   final con base en lo que de verdad pasó, y `docs/ai-log.md` va acumulando desde ya el
   material honesto para la pregunta 07.

También quedaron cerradas tres preguntas arquitectónicas que estaban abiertas, decididas por
criterio de "lo más parecido a un sistema real":

- **El dinero entra por una cuenta de sistema.** Existe `EXTERNAL_FUNDING`, única cuenta que
  puede quedar en negativo. Cargar saldo escribe `-50.000` ahí y `+50.000` en el usuario. Así la
  conservación es global y sin excepciones: la suma de *todo* el ledger es cero siempre, y
  "¿cómo sé que no pierdo un peso?" se responde con una query.
- **El saldo se deriva del ledger**, sin columna caché. No puede haber divergencia si no hay
  caché. El lock de concurrencia se toma sobre la fila de `account`.
- **Hay `User` y `Account` 1:1, sin autenticación.** Identificación por handle (`@samuel`) y
  selector de cuenta en el frontend. Auth real queda declarada como supuesto en el README.

Esto obligó a **corregir INV-1** en `references/invariants.md`: estaba escrito como "los asientos
de una operación suman cero", lo cual hacía que el primer depósito del sistema violara el
invariante. Quedó registrado en `docs/ai-log.md`.

---

## Los goals

### GOAL 0 — Fundación ✅

**Qué es.** El esqueleto ejecutable: Django 5.2 + DRF sobre PostgreSQL 17, React 19 + TypeScript
con Vite, Docker Compose, pytest y CI en dos jobs independientes. Un solo endpoint,
`/api/health/`. Cero dinero.

**Por qué no es solo andamiaje.** Tres settings quedan fijados aquí porque son caros de deshacer
después, y cada uno lleva un test que falla si alguien los cambia:

- `ATOMIC_REQUESTS = False` — si estuviera en `True`, Django envolvería cada request HTTP en una
  transacción y el límite transaccional se mudaría a la capa de presentación. Pertenece a la capa
  de aplicación.
- Aislamiento `READ COMMITTED` explícito — declara que la concurrencia se controla con locks
  pesimistas (`SELECT ... FOR UPDATE`), no con reintentos serializables.
- **Los tests corren sobre PostgreSQL, nunca SQLite** — SQLite ignora `select_for_update` en
  silencio. Una suite verde ahí no probaría nada sobre las transferencias.

**Evidencia.** Los 4 tests pasan contra Postgres real. El build de TypeScript compila. Y una
verificación manual que no estaba en el plan: con el backend arriba tumbé el contenedor de la
base y el endpoint devolvió `503 degraded` en vez de un 500 sin manejar, recuperándose solo al
levantarla. Eso prueba más que el test con mock: el mock demuestra que el `except` está escrito,
esto demuestra que atrapa el error que realmente lanza el driver.

**Deuda conocida.** El frontend no commitea `package-lock.json` y CI usa `npm install` en vez de
`npm ci`. Se corrige en el GOAL 1.

---

### GOAL 1 — Money, Account, Ledger, Deposit ✅

**Qué es.** Cuatro de los cinco puntos del núcleo: crear cuenta, cargar saldo, consultar saldo y
ver historial. Falta transferir, que es el GOAL 2.

**Las cuatro decisiones que lo definen.**

- **`Money` es un entero en centavos.** Rechaza floats, rechaza booleanos (que en Python son
  enteros disfrazados) y rechaza mezclar monedas. No existe `__float__`, así que no hay forma
  accidental de degradar la precisión.
- **Un depósito escribe dos asientos, nunca uno.** `LedgerEntryFactory.for_deposit()` devuelve
  una *tupla* de dos: `-50.000` contra `EXTERNAL_FUNDING` y `+50.000` contra tu cuenta. El
  factory justifica su existencia por lo que hace imposible: quien lo llame no puede obtener un
  asiento desbalanceado, porque el factory nunca devuelve uno solo.
- **El ledger es inmutable a nivel de base de datos.** Un trigger de PostgreSQL rechaza todo
  `UPDATE` y `DELETE` sobre los asientos. No es una convención del código: verifiqué que un
  `DELETE` lanzado directo por `psql`, saltándose la aplicación entera, rebota igual.
- **El saldo se deriva del ledger.** No hay columna `balance`, así que no hay nada que pueda
  quedar desincronizado.

**Patrones que entran aquí.** Repository, Command, Factory, Facade e inyección de dependencias.
El Repository no es decorativo: hay un test que ejecuta el depósito completo **sin base de
datos**, con repositorios falsos en memoria. Si el ORM se hubiera filtrado a la capa de
aplicación, ese test sería imposible de escribir.

**Evidencia.** 52 tests pasan contra PostgreSQL. Además, verificación manual por fuera de la
suite: 13 ataques por HTTP (monto cero, negativo, `100.5`, `100.0`, `true`, moneda USD, `2^70`,
depósito a la cuenta de funding, handle duplicado) todos rechazados con 400; suma global del
ledger igual a `0` consultada con `psql`; saldos espejo entre funding y usuarios; y el `DELETE`
bloqueado por el trigger.

**Dos correcciones que pedí en review.** El repositorio escribía el INSERT con SQL crudo donde
`bulk_create` hace lo mismo — correcto, pero es el camino de escritura más importante del sistema
y hay que poder explicarlo en vivo. Y el historial hacía una consulta por movimiento; ahora son
tres fijas, con un test que falla si el N+1 vuelve.

**Un error que encontré y que Codex no podía ver.** El `package-lock.json` que generó solo tenía
binarios de Windows, porque lo generó en Windows. CI corre en Ubuntu: `npm ci` habría fallado en
el primer push. Regenerado con todas las plataformas y verificado en limpio.

---

### GOAL 2 — Transferencias seguras ✅

El goal crítico, y el último punto del núcleo del reto. Aquí es donde la plata se puede perder
de verdad.

**Las tres cosas que lo hacen correcto.**

- **Se bloquea antes de leer.** Ambas cuentas se bloquean con `SELECT FOR UPDATE` y solo después
  se lee el saldo. Si se leyera antes, dos transferencias simultáneas verían los mismos fondos,
  ambas pasarían el chequeo y la cuenta quedaría sobregirada. Hay un test de aplicación que
  registra el orden de las llamadas y falla si alguien reordena esas dos líneas.
- **El orden del lock es por UUID ascendente, siempre**, sin importar quién envía. Si cada
  transferencia bloqueara "mi cuenta primero", una A→B y una B→A simultáneas tomarían las filas
  en orden inverso y se esperarían para siempre. Ordenar por un criterio global elimina el
  deadlock por construcción.
- **La idempotencia la impone la base de datos.** Hay una tabla con `UNIQUE` sobre la llave, y el
  duplicado se detecta atrapando el `IntegrityError`. El patrón intuitivo —consultar si existe y
  si no insertar— es justamente el que falla: dos reintentos concurrentes lo atraviesan los dos.

Además: misma llave con payload distinto devuelve **409**, porque eso es un bug del cliente y
esconderlo como si fuera un reintento sería peor que fallar. Y no se acepta una transferencia sin
llave de idempotencia: para mover plata, poder reintentar sin duplicar no es opcional.

**Decisión deliberada:** no hay reintentos automáticos ni backoff. Si la base reporta un
conflicto, sube como error. Agregar esa maquinaria ahora escondería exactamente las carreras que
estos tests existen para detectar.

**Evidencia.** 100 tests pasan. Los de concurrencia usan hilos reales con conexiones separadas y
los corrí 6 veces seguidas, todas verdes — una carrera que falla 1 de cada 5 veces no es un test
inestable, es un bug que aparece el día que hay tráfico.

Y por fuera de la suite, atacando el servidor con procesos paralelos de verdad:

| Ataque | Resultado |
|---|---|
| 10 transferencias simultáneas contra un saldo que alcanza para **una** | 1× `201`, 9× `422`. Saldo nunca negativo |
| La **misma** llave de idempotencia, 12 requests en paralelo | 1× `201`, 11× `200`, **el mismo `operation_id`**, una sola operación en el ledger |
| 40 transferencias cruzadas A→B y B→A simultáneas | 40× `201`, **cero deadlocks** |
| Misma llave, payload distinto | `409` |
| Sin llave / a sí mismo | `400` |

Tras las 50 operaciones: suma global del ledger `0`, cero operaciones desbalanceadas, cero
cuentas de usuario en negativo.

---

### GOAL 3 — Gastos compartidos + contexto ⬜

La extensión propia: transacciones que conservan contexto. El reto mismo dice que los bancos
mueven plata pero no entienden que esos $50.000 son del cumpleaños de un amigo.

`SharedExpense`, `Participant`, `Share` y `EqualSplitStrategy` (solo esa; la arquitectura debe
permitir añadir porcentual o exacta sin tocar código ajeno). Crear un gasto **no mueve plata**.
Una transferencia puede pertenecer a un gasto, y al completarse actualiza el estado de pago vía
evento de dominio despachado **después** del commit: si ese efecto secundario falla, la plata ya
está bien guardada.

---

### GOAL 4 — Frontend MVP ⬜

Cinco pantallas, ni una más: dashboard, transferir, historial, detalle de gasto y crear gasto.
Toma del repo `daily-fitness-platform` la organización, los tokens CSS y los patrones de card —
cero contenido de fitness. Paleta morado/teal/neutro, formato COP, estados vacíos y de error
cuidados, conectado a endpoints reales.

---

### GOAL 5 — Endurecimiento adversarial + auditoría ⬜

Atacar el sistema a propósito: conservación, idempotencia, concurrencia, precisión, deadlocks,
escrituras parciales, requests malformados. Test de regresión por cada hallazgo real. Después,
auditoría de arquitectura: ORM filtrándose al dominio, controllers con lógica de negocio, facade
convertido en god object, y **borrar** las abstracciones que no se ganan su complejidad.

Este goal produce la evidencia para la pregunta 02 del README.

---

### GOAL 6 — README, decisiones y demo ⬜

README en primera persona respondiendo las 8 preguntas del reto, basado solo en lo que realmente
se construyó. `docs/architecture-decisions.md` completo, con Singleton marcado explícitamente
como *considerado y rechazado* a favor de inyección de dependencias. Y puntos de conversación
para el video de 5 minutos — puntos, no un guion para leer, que el reto lo prohíbe.

---

## Cómo trabajan los dos agentes

Definido en `AGENTS.md`. Resumen: Claude decide **qué** y **dónde**, y lo escribe en `PLAN.md`.
Codex decide **cómo**, dentro de ese plan, y no rediseña. Claude revisa el `git diff`, corre los
tests él mismo, y aprueba o pide cambios.

La regla que salió de este proceso y que ya está en `docs/ai-log.md`: **ningún goal se cierra con
evidencia producida por el mismo agente que escribió el código.**
