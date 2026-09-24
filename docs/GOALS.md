# Goals: qué se construye, en qué orden y cómo correrlo

Documento de seguimiento. Lo actualizo al cerrar cada goal.
Para el detalle de un goal en curso, ver `PLAN.md` en la raíz (se reescribe por goal).

## Estado

| # | Goal | Estado |
|---|---|---|
| 0 | Fundación ejecutable | ✅ cerrado |
| 1 | Money, Account, Ledger, Deposit | ✅ cerrado |
| 2 | Transferencias seguras | ✅ cerrado |
| 3 | Gastos compartidos + contexto | ✅ cerrado |
| 4 | Frontend MVP | ✅ cerrado |
| 5 | Endurecimiento adversarial + auditoría | ✅ cerrado |
| 6 | README, decisiones y demo | ✅ cerrado |

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

### GOAL 3 — Gastos compartidos + contexto ✅

Nuestra extensión propia. El reto dice que los bancos mueven plata pero no entienden que esos
$50.000 son del cumpleaños de un amigo, y que todo queda como líneas sueltas en un extracto.
Esto es lo que ataca ese problema.

**Lo que hace.** Un gasto compartido agrupa un total, sus participantes y lo que cada uno debe.
"Cena del viernes — COP 180.000" entre tres da 60.000 exactos cada uno, y quien pagó queda
saldado de entrada. Una transferencia puede pertenecer al gasto, y al completarse el gasto sabe
quién pagó y cuánto falta. El historial deja de decir "transferencia -60.000" y pasa a decir
"transferencia -60.000 → Cena del viernes".

**Las tres decisiones que importan.**

- **Crear un gasto no mueve un peso.** Registra un acuerdo. La plata solo se mueve por
  transferencias, que ya existían y ya eran seguras. Verificado: crear el gasto escribe **cero**
  asientos en el ledger.
- **El reparto es exacto.** Dividir 100.000 entre 3 no da redondo, así que el residuo se reparte
  de a un centavo de forma determinista. Lo verifiqué con **32.934 combinaciones** de total y
  número de participantes: suma exacta en todas, ninguna cuota en cero, diferencia máxima entre
  cuotas de un centavo.
- **El evento se despacha después del commit.** Actualizar un gasto no es crítico
  financieramente; la plata sí. Hay un test que rompe el handler a propósito y verifica que corre
  *fuera* de la transacción, que los asientos ya existen cuando corre, y que la transferencia
  queda correcta con el ledger balanceado igual. Ese test es la única justificación válida para
  usar un evento aquí en vez de una llamada directa.

**Dos patrones entran, y ambos se ganan el puesto.** Strategy, porque repartir sí varía de
verdad — equitativo, por porcentaje, por monto exacto — pero **solo se implementó el
equitativo**: una costura limpia es mejor evidencia que una implementación sin usar. Y Observer,
justificado por el test del handler roto. El dispatcher son 30 líneas explícitas; se rechazaron
las señales de Django a propósito, porque son implícitas y difíciles de seguir cuando te piden un
cambio en vivo.

**Reglas de borde que se probaron.** Transferencia de alguien que no participa en el gasto → 400.
Gasto con total menor que su número de participantes → 400. Sobrepago permitido y visible: el
pendiente llega a cero y el exceso se reporta, porque la plata ya se movió y el sistema debe
describir la realidad, no negarla.

**Evidencia.** 148 tests pasan. Flujo completo por HTTP verificado, suma global del ledger `0`,
cero operaciones desbalanceadas, cero importaciones de Django en el dominio, cero señales.

**Un hallazgo del proceso.** Codex se negó a implementar este goal en el primer intento porque
encontró una contradicción en mi plan que yo no había visto. Está en `docs/ai-log.md`.

### GOAL 4 — Frontend MVP ✅

Cinco pantallas: dashboard, transferir, historial, detalle de gasto y crear gasto. Conectadas a la
API real, sin un solo dato simulado.

**Lo que el frontend tenía que probar.** Que el producto se entiende en treinta segundos. El
dashboard abre con "Tu dinero, con contexto"; en la actividad, la transferencia a Samuel lleva el
chip **"Cena del viernes"** y el depósito no lleva ninguno. Esa diferencia visible *es* el
producto — si no se notara en el video, el goal habría fallado.

**La parte más difícil de acertar.** La vista previa del reparto, antes de crear el gasto, calcula
las cuotas en el navegador. Si discrepara del backend, el usuario vería una cifra y el sistema
guardaría otra. Verifiqué 100.000 entre tres personas: el frontend mostró 33.333,33 / 33.333,33 /
**33.333,34** y el backend calculó exactamente lo mismo, con el centavo sobrante en la misma
persona. Coincide hasta en el orden del residuo.

**Precisión.** Cero `parseFloat` en todo el frontend. Los montos son `bigint` en unidades menores
de punta a punta; el usuario escribe pesos enteros y la conversión se hace con manejo de cadenas.
Formatear para mostrar es la única conversión, y va en un solo sentido.

**Decisiones de alcance.** Sin biblioteca de estado: React y context alcanzan para cinco
pantallas, y la respuesta a "¿por qué no Redux?" es "porque nada aquí lo necesitaba". Sin UI kit
ni framework CSS. Selector de cuenta en vez de login, porque no hay autenticación y eso está
declarado como supuesto.

**Un hallazgo que los números escondían.** El frontend eran 675 líneas en 22 archivos, que suena
compacto — hasta que medí el largo de las líneas: había **una de 1.111 caracteres** y 28 sobre
200. Eran componentes enteros aplastados en una sola línea de JSX. La compactación era falsa. Se
incorporó Prettier y se reformateó: la línea más larga ahora son 144 caracteres. Importa porque la
entrevista son 60 minutos de pair programming sobre este código con un cambio no anticipado.

**Evidencia.** Lint y build limpios, 148 tests del backend intactos, las cinco pantallas navegadas
en el navegador contra la API real, y conservación global en `0` después de todo.

### GOAL 5 — Endurecimiento adversarial + auditoría ✅

**La auditoría de arquitectura pasó las seis comprobaciones**, verificadas con grep, no de
memoria: cero ORM en dominio o aplicación, cero imports de Django en el dominio, controladores sin
reglas de negocio, `SELECT FOR UPDATE` solo en repositorios, `transaction.atomic` solo en
servicios, y cero estado global mutable. El facade son 57 líneas de pura delegación y el archivo
más grande del backend tiene 205 líneas, así que no hay god objects.

**Ataqué el sistema y encontré dos cosas.** Un gasto "compartido" de una sola persona se aceptaba
—no es compartido y nadie debe nada— y ahora se rechaza. Y una ruta `/api/` no encontrada
devolvía HTML en vez de JSON, inconsistente para una API.

**Lo que resistió:** inyección SQL en título y handle (guardada como texto literal, ledger
intacto), unicode y campos gigantes, UUIDs malformados, JSON roto, la cuenta de funding como
parte de una transferencia o de un gasto, pagos en dirección inversa, y 20 depósitos y
transferencias mezclados en paralelo sobre la misma cuenta con saldo final exacto al peso.

**11 tests de regresión nuevos**, uno por cada comportamiento que probé a mano. Total: **159
tests**, corridos 3 veces seguidas, y los de concurrencia 5 veces.

**Un hallazgo del proceso:** uno de mis tests nuevos pasaba aislado y fallaba en compañía, 5 de 5
veces. No era inestabilidad: los tests transaccionales vacían la cuenta de sistema, y el archivo
de concurrencia ya tenía un fixture para restaurarla. Quedó en `docs/ai-log.md`.

---

### GOAL 6 — README, decisiones y demo ✅

**`README.md`** en primera persona, respondiendo las ocho preguntas del reto con base en lo que
realmente se construyó y midió. La pregunta 2 —cómo sé que no pierde un peso— está escrita como
cinco formas concretas de perder plata, cada una con su protección y su evidencia ejecutada.

**`docs/architecture-decisions.md`** con cada patrón: el problema real, dónde vive, qué cuesta y
cuál era la alternativa más simple. Incluye **Singleton como considerado y rechazado**, con las
tres razones y la condición bajo la cual lo reconsideraría.

**`docs/demo.md`** con los puntos para el video de 5 minutos, con tiempos por bloque. No es un
guion: el reto prohíbe leer de uno.

