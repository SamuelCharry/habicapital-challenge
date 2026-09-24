# Decisiones de arquitectura y patrones

Un patrón que no resuelve un problema concreto es peso muerto: hay que explicarlo,
mantenerlo y rodearlo. Para cada uno anoto el problema real, dónde vive, qué cuesta
y cuál era la alternativa más simple que descarté.

Al final está el patrón que **no** usé, y por qué.

---

## Arquitectura en capas

**Problema.** El dinero se mueve con reglas que no dependen de dónde se guarde
—conservación, fondos suficientes, precisión— y con mecánica que sí depende
totalmente de eso: locks de fila, constraints, transacciones. Mezclarlas hace que
no puedas probar las reglas sin levantar una base de datos, ni cambiar de
almacenamiento sin tocar las reglas.

**Dónde.** `domain/` (reglas puras, sin Django), `application/` (orquestación y el
límite transaccional), `infrastructure/` (ORM, locks, SQL), `presentation/` (HTTP).

**Qué gano.** El depósito y la transferencia se prueban sin base de datos, con
repositorios falsos en memoria. Y las reglas de dinero se leen sin ruido de
framework alrededor.

**Costo.** Más archivos, y una capa de traducción entre entidades de dominio y
modelos del ORM que hay que mantener a mano.

**Alternativa que descarté.** Django estándar con lógica en los modelos. Es más
corto y más idiomático. Lo descarté porque ata cada regla financiera al ORM: para
probar que un reparto no pierde un peso necesitarías una base de datos.

**Cómo se sostiene.** Un test recorre `src/domain/**.py` y falla si alguno importa
`django`, `rest_framework` o `src.infrastructure`. La regla no es una convención
que se erosiona: rompe el build.

---

## Repository

**Problema.** Si la capa de aplicación consulta el ORM directamente, no se puede
ejercitar una operación financiera sin base de datos, y el `SELECT ... FOR UPDATE`
se dispersa por todo el código.

**Dónde.** Interfaces abstractas en `domain/repositories.py`; implementaciones
Django en `infrastructure/persistence/repositories.py`.

**Qué gano.** Es lo que hace posible `tests/application/test_deposit_service.py` y
`test_transfer_service.py`: ejecutan la lógica completa contra repositorios en
memoria. Uno de ellos prueba algo que de otra forma sería casi imposible de
verificar: que el servicio **bloquea antes de leer el saldo**, usando un
repositorio falso que registra el orden de las llamadas.

**Costo.** Una interfaz y una implementación por cada colección.

**Alternativa que descarté.** Llamar al ORM desde los servicios y probar todo con
base de datos. Más rápido de escribir; imposible de usar para afirmar el orden de
las operaciones dentro de una transacción.

---

## Factory

**Problema.** Un asiento suelto rompe la conservación de forma permanente y
silenciosa. Basta con que alguien, alguna vez, escriba solo una pata.

**Dónde.** `domain/factories.py`. `for_deposit()` y `for_transfer()` devuelven una
**tupla de dos asientos**.

**Qué gano.** No es que esté prohibido escribir un asiento desbalanceado: es que no
hay forma de obtener uno. El factory nunca devuelve uno solo, y el repositorio
solo expone `append(entries)`. La regla está en la forma del código, no en un
comentario.

**Costo.** Casi ninguno; son dos funciones.

**Alternativa que descarté.** Un método `create_entry()` más un test que verifique
que siempre se llaman de a dos. Eso confía en que nadie escriba un tercer camino.

---

## Command

**Problema.** Las operaciones financieras llevan varios datos que viajan juntos y
tienen que estar validados antes de tocar la base.

**Dónde.** `application/commands.py`: `CreateAccountCommand`, `DepositCommand`,
`TransferCommand`, `CreateSharedExpenseCommand`. Dataclasses congeladas.

**Qué gano.** La firma dice qué necesita la operación, y el objeto no se puede
mutar a mitad de camino.

**Costo.** Una clase por operación.

**Alternativa que descarté.** Pasar argumentos sueltos. Funciona con tres
parámetros; `TransferCommand` tiene cinco y uno es opcional.

---

## Facade

**Problema.** Los controladores no deberían saber que existen cuatro servicios
distintos ni en qué orden se arman los comandos.

**Dónde.** `application/facade.py`, 57 líneas.

**Qué gano.** Un solo punto de entrada. Los controladores quedan de tres o cuatro
líneas, sin una sola regla de negocio.

**Costo.** Un método por operación que solo delega. Es el patrón que más fácil se
degrada en un god object.

**Cómo evito que se degrade.** El facade **no** tiene lógica: construye el comando
y delega. Si alguna vez necesita un `if` sobre reglas de negocio, ese `if`
pertenece a un servicio.

---

## Strategy

**Problema.** Repartir un gasto varía de verdad: en partes iguales, por porcentaje,
por monto exacto. No es variación hipotética, es el dominio.

**Dónde.** `domain/split.py`: `SplitStrategy` abstracta, `EqualSplitStrategy`
concreta.

**Decisión deliberada: solo implementé la equitativa.** Las otras dos son
alcance que no necesito para demostrar el producto. Lo que sí importa es que
`SharedExpense` dependa de la abstracción y nunca ramifique por tipo de reparto,
para que agregar una no obligue a tocar código ajeno. Una costura limpia es mejor
evidencia que una implementación sin usar.

**Costo.** Una interfaz con una sola implementación, que es exactamente el olor que
suele indicar sobreingeniería. Lo acepto aquí porque la variación es real y está
nombrada, no imaginada.

**Alternativa que descarté.** Una función de reparto y un `if` cuando llegue la
segunda. Honestamente es defendible. Elegí la interfaz porque el reparto es el
único lugar del sistema donde el dominio dice explícitamente "esto varía".

---

## Observer / eventos de dominio

**Problema.** Cuando una transferencia se completa, hay que actualizar el estado del
gasto compartido. Pero eso **no** es crítico financieramente: si falla, la plata
igual tiene que haberse movido bien.

**Dónde.** `domain/events.py` (un despachador de 30 líneas),
`application/event_handlers.py`.

**Qué gano.** El evento se despacha con `transaction.on_commit`, o sea **después**
de que la plata está guardada. Un handler que explota se registra en el log y no
revierte nada.

**Cómo lo pruebo.** `test_expense_update_failure_does_not_roll_back_the_transfer`
rompe el handler a propósito y verifica tres cosas: que corre fuera de la
transacción, que los asientos ya existen cuando corre, y que la transferencia
queda en 201 con el ledger balanceado. **Sin ese test el patrón sería decoración**:
es la única prueba de que el desacople compra algo real.

**Costo.** Indirección. Leyendo `TransferService` no ves quién reacciona al evento.

**Alternativa que descarté.** Llamar al actualizador directamente al final de la
transferencia. Más fácil de seguir, pero mete un efecto no crítico en el camino
crítico: un fallo actualizando el gasto podría revertir una transferencia válida.

**Y lo que rechacé explícitamente: las señales de Django.** Hacen lo mismo con menos
código, pero son implícitas y globales — no ves desde el código quién escucha. En
una entrevista de 60 minutos modificando este código en vivo, eso es exactamente lo
que no quiero.

---

## Inyección de dependencias

**Problema.** Un servicio que construye sus propios repositorios no se puede probar
sin base de datos.

**Dónde.** Todos los servicios reciben sus dependencias por constructor.
`infrastructure/container.py` arma el grafo en una función, `build_wallet()`.

**Qué gano.** Además de los repositorios, están inyectados `atomic`, el reloj y el
generador de UUIDs. Por eso los tests de aplicación pueden controlar el tiempo y
los identificadores sin parchear nada global.

**Costo.** Constructores más largos.

**Alternativa que descarté.** Un framework de DI. Para cuatro servicios es
maquinaria que hay que explicar sin ganar nada.

---

## Singleton — CONSIDERADO Y RECHAZADO

Lo evalué para el contenedor: `build_wallet()` se llama en cada request y arma
repositorios y despachador cada vez. Cachearlo en un módulo sería trivial.

**No lo hice, por tres razones.**

La primera es que no compra nada medible. Los objetos son *stateless*: no abren
conexiones ni mantienen caché. Instanciarlos es asignar cuatro punteros. La
conexión a base de datos ya la gestiona Django, que es donde ese problema
realmente vive.

La segunda es que haría los tests peores. Un contenedor global se comparte entre
tests, y un test que suscribe un handler distinto —como el que rompe el handler de
gastos a propósito— contaminaría a los que corran después. Terminaría escribiendo
código para resetear el singleton entre tests, que es pagar complejidad para
arreglar la complejidad que introduje.

La tercera es que el estado global mutable es la fuente de bugs más difícil de
rastrear en un sistema concurrente, y este sistema es concurrente por diseño. No
quiero que ningún objeto compartido entre hilos exista si puedo evitarlo.

**Cuándo sí lo reconsideraría:** si `build_wallet()` apareciera en un perfilado, o
si algún componente pasara a mantener estado caro de construir, como un pool de
conexiones propio o un cliente externo con handshake.

Dejo esto escrito porque "no usamos Singleton" suena a omisión, y fue una decisión.

---

## Decisiones que no son patrones

**Saldo derivado, sin columna `balance`.** El saldo es siempre
`SUM(asientos)`. Una columna cacheada es más rápida y puede desincronizarse del
ledger; sin caché no hay nada que pueda divergir. El invariante INV-10 queda
satisfecho por construcción. Si el rendimiento importara, se agrega con un test de
reconciliación obligatorio — pero primero tendría que importar.

**Inmutabilidad del ledger en la base de datos.** Un trigger de PostgreSQL rechaza
todo `UPDATE` y `DELETE` sobre los asientos. Lo verifiqué lanzando un `DELETE`
directo por `psql`, saltándome la aplicación entera: rebota igual. Ponerlo en el
código habría sido más fácil de leer y trivial de saltarse.

**Idempotencia por constraint único, no por consulta previa.** Verificar si la
llave existe y luego insertar es el patrón intuitivo y está roto: dos reintentos
concurrentes pasan los dos el chequeo. La unicidad la impone la base y el duplicado
se detecta atrapando el error de integridad. Doce requests paralelos con la misma
llave producen una sola transferencia.

**Orden determinista de locks.** Ambas cuentas se bloquean en orden ascendente de
UUID, siempre, sin importar quién envía. Si cada transferencia bloqueara "mi cuenta
primero", una A→B y una B→A simultáneas se esperarían para siempre. Cuarenta
transferencias cruzadas simultáneas: cero deadlocks.

**Sin reintentos automáticos ni backoff.** Si la base reporta un conflicto, sube
como error. Esa maquinaria escondería justo las carreras que los tests existen para
detectar. Es una decisión para este contexto: en producción, con una política de
reintentos pensada, cambiaría.
