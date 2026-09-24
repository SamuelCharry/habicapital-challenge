# habicapital-challenge

Una billetera donde el dinero **conserva contexto**: puedes ver que esos $60.000 que
enviaste son tu parte de la cena del viernes, no una línea suelta en un extracto.

Reto técnico para practicantes de HabiCapital, convocatoria 2027.

---

## Qué construí

El núcleo que pedía el reto: crear cuenta, cargar saldo simulado, transferir entre
cuentas, consultar saldo y ver historial.

Encima, una sola cosa: **gastos compartidos**. Creas "Cena del viernes — $180.000"
con tres personas, el sistema calcula que cada quien pone $60.000, y cuando alguien
te transfiere su parte, el gasto sabe quién ya pagó y cuánto falta. El pago aparece
en el historial **con el nombre del gasto**, no como una transferencia anónima.

Elegí eso porque el enunciado nombra el problema directamente: los bancos mueven
plata pero no entienden que esos $50.000 son del cumpleaños de un amigo, y todo
queda como líneas sueltas. Los cinco escenarios del reto —la cena, la mamá, los
roommates, la profesora, los freelancers— son todos el mismo problema: plata entre
personas que ya se conocen y que están de acuerdo en algo. El banco mueve el monto
y pierde el acuerdo.

## Cómo lo corro

```sh
cp .env.example .env
docker compose up --build
```

Frontend en `http://localhost:5173`, API en `http://localhost:8000`.

Para los tests hace falta PostgreSQL arriba:

```sh
docker compose up -d db
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt

cd backend
POSTGRES_HOST=localhost POSTGRES_USER=habicapital \
POSTGRES_PASSWORD=local-development-only POSTGRES_DB=habicapital \
../.venv/Scripts/python.exe -m pytest -v
```

**159 tests.** 23 de dominio, 7 de aplicación (sin base de datos), 66 de
integración y concurrencia, 4 de la fundación.

La comprobación que más me importa, contra la base directamente:

```sql
SELECT SUM(amount_minor) FROM persistence_ledgerentrymodel;  -- 0, siempre
```

## Stack y por qué

**Python + Django + DRF.** El reto pide justificar la elección, no acertar la de
ustedes. Elegí Python porque es donde soy más rápido y donde puedo defender el
código en una entrevista, y Django porque su capa de transacciones y su ORM sobre
PostgreSQL me dan `SELECT FOR UPDATE` y constraints reales sin escribir SQL a mano.

**PostgreSQL.** Lo necesito por lo que hace el sistema, no por moda: transacciones
ACID, bloqueo a nivel de fila, constraints que el motor hace cumplir, y triggers.
Tres de las protecciones de este proyecto viven en la base, no en el código. *No
afirmo que HabiCapital use PostgreSQL* — el documento dice "bases de datos
relacionales y no relacionales" y nada más.

**React + TypeScript.** Es el lado de frontend del stack que describen, y TypeScript
me deja modelar los montos como `bigint` para que el compilador impida que alguien
los convierta a punto flotante.

**Monolito modular.** Múltiples servicios harían que una transferencia cruce un
límite de red, y entonces "la plata no se pierde" pasaría a depender de
transacciones distribuidas. Para este problema eso es meterse un problema mucho más
difícil sin necesidad. Las fronteras están marcadas por capas, así que extraer algo
después sería posible; hoy no hace falta.

---

# Las ocho preguntas

## 1. Las decisiones clave y por qué las tomé

**Ledger de doble partida, desde el primer peso.** Nunca guardo un saldo y lo
modifico. Guardo asientos inmutables y el saldo es la suma de los asientos de una
cuenta. Cada operación escribe dos asientos que suman cero.

**El dinero entra por una cuenta de sistema.** Un depósito simulado también es de
doble partida: escribe `-50.000` contra una cuenta `EXTERNAL_FUNDING` y `+50.000`
contra la tuya. Es la única cuenta autorizada a quedar en negativo, y su saldo
negativo mide exactamente cuánta plata se ha inyectado al sistema.

Esta decisión tiene una consecuencia que vale más que la elegancia: **la
conservación no tiene excepciones**. La suma de *todo* el ledger es cero siempre,
depósitos incluidos. La pregunta "¿perdí un peso?" se responde con una query, y no
tengo que acordarme de qué operaciones cuentan y cuáles no. La alternativa —marcar
los depósitos como exentos— era más fácil de escribir, pero crea una categoría de
"asientos que no cuadran" que después alguien copia a otra operación.

**El saldo se deriva, no se cachea.** No hay columna `balance`. Es más lento y no
me importa: si no hay caché, no hay nada que pueda quedar desincronizado del ledger.

**Dinero en enteros, nunca en punto flotante.** `Money` guarda centavos como entero
y rechaza floats, rechaza booleanos —que en Python son enteros disfrazados— y
rechaza mezclar monedas. No existe conversión a float en ninguna dirección.

**La inmutabilidad la impone la base de datos.** Un trigger de PostgreSQL rechaza
todo `UPDATE` y `DELETE` sobre los asientos. En el código habría sido más legible y
trivial de saltarse.

El detalle de cada patrón, con su costo y la alternativa que descarté, está en
[`docs/architecture-decisions.md`](docs/architecture-decisions.md). Ahí también
está por qué **evalué Singleton y lo rechacé**.

## 2. Cómo sé que mi sistema no pierde un peso

### Qué puede salir mal

Pensé esto como cinco formas concretas de perder plata, no como una lista de buenas
prácticas:

1. **Escribir una sola pata.** Se acredita al que recibe y no se debita al que
   envía, o al revés. La plata aparece o desaparece de la nada.
2. **Leer el saldo antes de bloquear.** Dos transferencias simultáneas ven los
   mismos fondos, ambas pasan el chequeo, y la cuenta queda sobregirada.
3. **Reintentos duplicados.** El cliente no recibe respuesta, reintenta, y se cobra
   dos veces.
4. **Escrituras parciales.** Algo falla a mitad de la operación y queda medio
   asiento escrito.
5. **Redondeo.** Dividir $100.000 entre 3 y que las partes no sumen $100.000.

Y una sexta que no pierde plata pero cuelga el sistema: **deadlock**, cuando dos
transferencias cruzadas bloquean las mismas filas en orden opuesto.

### Cómo los protejo

**Contra la pata suelta:** el factory devuelve una *tupla* de dos asientos. No es que
esté prohibido escribir uno solo — es que no hay forma de obtenerlo. El repositorio
solo expone `append(entries)`.

**Contra la carrera de saldo:** bloqueo ambas cuentas con `SELECT FOR UPDATE` y solo
después leo el saldo. Hay un test de aplicación que usa un repositorio falso para
registrar el orden de las llamadas y **falla si alguien reordena esas dos líneas**.

**Contra el deadlock:** bloqueo siempre en orden ascendente de UUID, sin importar
quién envía. Si cada transferencia bloqueara "mi cuenta primero", una A→B y una B→A
simultáneas se esperarían para siempre.

**Contra el duplicado:** unicidad impuesta por un constraint de la base, detectando
el error de integridad. Consultar si la llave existe y después insertar es el patrón
intuitivo y está roto: dos reintentos concurrentes pasan los dos el chequeo.

**Contra la escritura parcial:** una sola transacción que cubre el registro de
idempotencia y los dos asientos, y nada más. Los efectos secundarios no críticos
—actualizar el gasto compartido— se despachan **después** del commit.

**Contra el redondeo:** aritmética entera y reparto determinista del residuo, de a
un centavo.

### Qué evidencia tengo

Esta es la parte que no quiero que suene a promesa. Todo lo de abajo lo ejecuté.

**Ataques concurrentes reales, con procesos en paralelo contra el servidor:**

| Ataque | Resultado |
|---|---|
| 10 transferencias simultáneas contra un saldo que alcanza para **una** | 1× `201`, 9× `422`. Saldo nunca negativo |
| La **misma** llave de idempotencia, 12 requests en paralelo | 1× `201`, 11× `200`, **todos con el mismo `operation_id`**, una sola operación en el ledger |
| 40 transferencias cruzadas A→B y B→A simultáneas | 40× `201`, **cero deadlocks** |
| 20 depósitos y transferencias mezclados sobre la misma cuenta | saldo final exacto al peso |

**El reparto, verificado exhaustivamente:** corrí las 32.934 combinaciones de total
(desde 1 hasta 3.000) y número de participantes (de 2 a 12). En todas la suma de las
partes es exactamente el total, ninguna parte queda en cero, y la diferencia entre la
mayor y la menor es de un centavo.

**La inmutabilidad, probada por fuera de la aplicación:** lancé un `DELETE` con
`psql` directo contra la tabla de asientos, saltándome el backend entero.
`ERROR: Ledger entries are append-only`.

**Inyección SQL:** mandé `'; DELETE FROM persistence_ledgerentrymodel; --` como
título de un gasto. Se guardó como texto literal, el ledger quedó intacto. Hay un
test de regresión que lo comprueba.

**El rollback:** un test inyecta un fallo después de que se escribiría el primer
asiento y verifica que quedan cero asientos **y ninguna fila de idempotencia
huérfana** — si quedara, el reintento legítimo con la misma llave quedaría
bloqueado para siempre.

**Los tests de concurrencia los corrí 5 veces seguidas**, no una. Una carrera que
falla una de cada cinco veces no es un test inestable: es un bug que aparece el día
que hay tráfico.

Y después de todo lo anterior, la suma global del ledger sigue siendo `0`.

## 3. Qué dejé fuera y por qué

**Autenticación.** No hay login ni contraseñas. El frontend tiene un selector de
cuenta activa. Construirla bien toma tiempo y no demuestra nada sobre el problema
del reto, que es mover plata sin perderla. Construirla mal sería peor que no
tenerla.

**Las otras estrategias de reparto.** Dejé la costura lista —`SplitStrategy` es una
interfaz y `SharedExpense` nunca ramifica por tipo— pero solo implementé el reparto
equitativo. Una implementación sin usar es peor evidencia que una costura limpia.

**Editar o borrar gastos.** Un gasto con pagos asociados no se puede simplemente
editar sin decidir qué pasa con lo ya pagado. Esa decisión merece pensarse, no
improvisarse.

**Paginación, búsqueda, notificaciones, gastos recurrentes, reversos, comisiones,
multi-moneda.** Alcance.

**Reintentos automáticos y backoff.** A propósito. Si la base reporta un conflicto,
sube como error. Esa maquinaria escondería exactamente las carreras que estos tests
existen para detectar. En producción, con una política pensada, cambiaría.

**Tests de frontend.** El backend es donde vive la plata y ahí está la suite. El
frontend lo verifiqué a mano en el navegador. Es la deuda más clara que dejo.

## 4. Qué haría distinto con más tiempo

**Un test de propiedades sobre el ledger completo.** Hoy verifico conservación
después de secuencias que yo elegí. Me gustaría generar secuencias aleatorias de
depósitos, transferencias y fallos inyectados, y afirmar que la suma es cero pase lo
que pase. Es el tipo de test que encuentra lo que uno no pensó.

**Medir antes de defender el saldo derivado.** Decidí no cachear el saldo por
correctitud, y con datos de demo no se nota. No sé en qué número de asientos por
cuenta empieza a doler, y debería saberlo antes de afirmar que la decisión escala.

**Idempotencia en depósitos.** Las transferencias la tienen; los depósitos no.
Como son simulados no es urgente, pero es una asimetría que no tiene buena
justificación más allá del alcance.

**Tests de frontend**, empezando por la conversión de pesos a centavos y por la
vista previa del reparto, que es donde el frontend podría discrepar del backend.

**Expiración de llaves de idempotencia.** Hoy viven para siempre. En un sistema real
esa tabla crece sin límite.

## 5. Qué NO sé

**No sé cómo se comporta esto bajo carga real.** Mis pruebas de concurrencia son
decenas de requests simultáneos en una máquina. No sé en qué punto el bloqueo
pesimista sobre la fila de la cuenta se vuelve el cuello de botella, ni cómo se
vería eso. Sospecho que una cuenta muy activa serializa todas sus operaciones y
degrada, pero no lo he medido.

**No sé si el nivel de aislamiento que elegí es el correcto para todos los casos.**
Uso `READ COMMITTED` con bloqueo pesimista porque es lo que entiendo y puedo
razonar. No tengo experiencia práctica con `SERIALIZABLE` y reintentos, y no sabría
defender cuándo conviene uno u otro más allá de lo que he leído.

**No sé cómo se hace la contabilidad de verdad.** Construí un ledger de doble
partida porque tiene sentido y es verificable, pero no conozco las prácticas reales
de un equipo financiero: cómo se concilia con sistemas externos, qué se reporta,
qué se audita, qué pasa cuando alguien reclama un cobro.

**No sé operar esto.** No hay métricas, trazas ni alertas. Si el sistema empezara a
fallar en producción no tendría forma de enterarme antes que el usuario.

**No sé si la extensión que elegí es la que más valor agrega.** Me convenció porque
el enunciado apunta directo a ella, pero no hablé con nadie que tenga el problema.

## 6. Los supuestos que hice

- **Una cuenta por persona, sin autenticación.** El reto dice "un usuario con saldo".
  Asumí que demostrar el modelo de dinero importaba más que el de identidad.
- **Una sola moneda, COP.** Aun así, la moneda viaja con cada monto y mezclar
  monedas distintas lanza excepción, para que agregar otra no sea una reescritura.
- **Los depósitos son simulados y siempre exitosos.** No hay pasarela, tal como
  permite el enunciado.
- **Pesos enteros en la interfaz.** El sistema guarda centavos, porque un reparto
  los produce, pero el usuario escribe pesos.
- **En un gasto compartido, quien pagó ya cubrió su parte.** Los demás le pagan a
  esa persona. Una transferencia ligada a un gasto solo es válida de un participante
  hacia quien pagó.
- **El sobrepago se permite y se muestra.** Si alguien manda de más, el pendiente
  llega a cero y el exceso se reporta. La plata ya se movió; el sistema debe
  describir la realidad, no negarla.
- **Un gasto compartido necesita al menos dos personas.** Uno de una sola persona no
  es compartido y nadie debe nada en él.

## 7. Cómo usé IA

### La dinámica

Usé dos agentes con **roles separados a propósito**, no como asistentes
intercambiables:

- **Claude Code como arquitecto y revisor.** Decide *qué* cambia, en qué capa vive,
  qué invariantes están en riesgo y qué tests son obligatorios. Escribe eso en un
  `PLAN.md`. No implementa.
- **Codex CLI como implementador.** Lee el plan y lo ejecuta. No rediseña. Si algo
  del plan está mal o es ambiguo, **se detiene y reporta** en vez de improvisar.
- **Yo** apruebo o rechazo las decisiones arquitectónicas y hago cada commit.

El contrato está en [`AGENTS.md`](AGENTS.md) y las reglas de implementación en
[`.agents/skills/safe-financial-implementation/`](.agents/skills/safe-financial-implementation/).
El proyecto avanzó goal por goal: plan, implementación, revisión del diff, tests
corridos por el revisor, y recién ahí commit.

Separar los roles importó más de lo que esperaba. Un solo agente haciendo todo tiende
a escribir el plan que le conviene y después a declararse satisfecho. Con el
implementador obligado a obedecer un plan que no escribió, cada contradicción del
plan se vuelve visible en vez de resolverse en silencio.

Lo que le pedía yo: elegir la extensión del producto, decidir el modelo financiero,
fijar el alcance, y cortar cuando la arquitectura se estaba inflando. Lo que le pedía
a los agentes: escribir el código y atacarlo.

### Cuando la IA se equivocó

Tengo tres casos registrados con fecha en [`docs/ai-log.md`](docs/ai-log.md). El que
más me enseñó:

**El invariante que se violaba a sí mismo.** Le pedí a Claude que escribiera los
invariantes financieros antes de existir código. Escribió INV-1 así: *"los asientos
de una operación suman cero"*. Suena obviamente correcto y lo aprobé sin objetar.

Dos pasos después, planeando los depósitos, el mismo agente detectó el problema: un
depósito mete plata desde afuera, así que si solo acreditas la cuenta del usuario,
los asientos suman 50.000, no cero. **El invariante que había declarado
no-negociable era violado por la primera operación monetaria del sistema.**

Si no lo agarro, hay dos salidas y las dos son malas. O el depósito se implementa
como asiento de una sola pata —y ahí el ledger deja de ser de doble partida y la
frase "no pierdo un peso" pierde su respaldo— o se mete una excepción del tipo "los
depósitos no cuentan para la conservación", que es justo el tipo de excepción que
después se copia a otra operación y termina escondiendo un bug real.

La solución fue la cuenta `EXTERNAL_FUNDING`. Y es la razón de que hoy la
conservación no tenga excepciones.

Lo que me llevo: **la IA es muy buena escribiendo reglas que suenan rigurosas y muy
mala notando que su propia regla no cubre un caso que todavía no ha visto.** Las
reglas abstractas no se validan leyéndolas — se validan corriéndolas contra el caso
más aburrido que exista. Acá el caso aburrido era "el primer depósito".

**El segundo caso es casi el inverso, y por eso lo dejo:** Codex se negó a
implementar los gastos compartidos. Reportó que mi plan pedía dos cosas
incompatibles —que toda cuota fuera positiva, y un test que repartiera totales desde
1 centavo entre hasta 9 participantes— porque repartir 1 peso entre 3 personas
obliga a que alguien quede en cero. **Tenía razón, y el error era mío.** Un agente
optimizando por terminar la tarea habría permitido cuotas de cero en silencio: el
sistema compila, los tests pasan, y queda una violación de invariante enterrada en
la operación que reparte plata entre personas.

Lo resolví rechazando la entrada en vez de debilitar la regla: un gasto cuyo total es
menor que su número de participantes devuelve 400.

Y el tercero, el que me hizo cambiar cómo trabajo: **Codex reportó un goal como
"Implemented" cuando no había podido correr un solo test.** El titular decía "todos
los archivos creados, los cuatro tests existen"; tres secciones más abajo decía que
su entorno no tenía Docker ni red y que nada se había ejecutado. Fue honesto, pero
la información que contradecía el titular estaba donde uno ya dejó de leer. Desde
ahí la regla del proyecto es que **ningún goal se cierra con evidencia producida por
el mismo agente que escribió el código**: los tests los corro yo.

## 8. Qué aprendí

**Que el ledger de doble partida no es burocracia contable, es una estructura de
datos que hace verificable una propiedad.** Yo lo conocía como concepto de
contabilidad. Entender que convierte "¿perdí plata?" —una pregunta difusa— en
`SELECT SUM(...) = 0` fue lo que más me cambió la cabeza en este reto.

**Que el patrón intuitivo de idempotencia está roto.** Yo habría escrito "consulta
si la llave existe, si no, inserta" sin pensarlo dos veces. Que dos reintentos
concurrentes atraviesen ese chequeo es obvio cuando te lo dicen y completamente
invisible cuando lo escribes. Aprender a delegar la unicidad al motor en vez de
intentar coordinarla desde la aplicación fue la lección técnica más útil.

**Que el orden en que tomas los locks es una decisión de diseño.** No sabía que el
deadlock se evita eligiendo un orden global arbitrario pero consistente. Es una idea
simple y me pareció preciosa: no necesitas coordinación, solo que todos ordenen por
el mismo criterio.

**Lo que más me sorprendió: que los tests que valen son los que prueban que algo
*no* pasó.** El test que más me costó escribir es el que rompe a propósito el
actualizador de gastos y verifica que la transferencia queda bien igual. No prueba
una funcionalidad; prueba que un fallo *no* se propaga. Y es lo único que justifica
que ahí haya un evento en vez de una llamada directa. Sin ese test, el patrón sería
decoración — y creo que eso aplica a casi cualquier patrón.

**Sobre trabajar con IA:** que el valor no está en que escriba código rápido, sino en
poner restricciones tan explícitas que las contradicciones salgan a la superficie.
Las tres veces que este flujo me salvó de un error, fue porque un agente chocó
contra una regla escrita — no porque fuera listo. Y las tres veces, dos de los
errores eran míos.

---

## Estructura

```
backend/src/
  domain/          Money, Account, LedgerEntry, split, eventos. Sin Django.
  application/     Commands, servicios, facade. Dueño del límite transaccional.
  infrastructure/  ORM, repositorios, migraciones. Único lugar con FOR UPDATE.
  presentation/    Controladores y serializers. Sin reglas de negocio.
frontend/src/      Cinco pantallas + tokens de tema.
docs/              Decisiones de arquitectura, bitácora de IA, seguimiento de goals.
```

Las dependencias apuntan hacia adentro. Un test recorre `src/domain/` y falla si
alguien importa Django ahí, así que la regla de capas rompe el build en vez de
erosionarse.

**Documentos:**
[decisiones de arquitectura y patrones](docs/architecture-decisions.md) ·
[bitácora de trabajo con IA](docs/ai-log.md) ·
[seguimiento de los goals](docs/GOALS.md) ·
[contrato entre agentes](AGENTS.md)
