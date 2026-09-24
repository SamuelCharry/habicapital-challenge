# habicapital-challenge

Una billetera donde cada movimiento de dinero conserva su contexto. Ese historial puede servir como evidencia para explorar la posibilidad de acceder a un crédito de vivienda.

Reto técnico para practicantes de HabiCapital, convocatoria 2027.

## Qué construí

Implementé las funciones principales del reto: crear una cuenta, cargar saldo simulado, transferir dinero, consultar el saldo y revisar el historial.

También agregué una forma de mostrar cómo el comportamiento financiero diario podría relacionarse con un crédito de vivienda. La aplicación registra dos datos: la constancia del ahorro, calculada a partir de los depósitos hechos durante varios meses, y el cumplimiento de pagos compartidos. Por ejemplo, pagar cada mes la parte correspondiente del arriendo deja un registro de pago entre personas.

Con esos datos, un modelo de difusión ubica cada perfil junto a otros perfiles crediticios y propone una ruta hacia uno que podría calificar. La ruta indica qué cambios serían necesarios. No representa una decisión real de crédito.

Elegí esta extensión porque HabiCapital trabaja con productos financieros relacionados con vivienda y con crédito hipotecario. En ese contexto, saber si una persona podría calificar y entender qué tendría que mejorar puede ser más útil que recibir una respuesta sin explicación.

### Por qué usé un modelo de difusión

Un clasificador puede encontrar cambios que alteren su resultado, aunque esos cambios no sean realistas. Por ejemplo, podría recomendar aumentar mucho los ingresos sin considerar si ese cambio tiene sentido junto con el ahorro y la estabilidad de la persona.

El modelo de difusión aprende la forma de los perfiles del conjunto de datos. La ruta se ajusta en cada paso para mantenerse cerca de perfiles reales. Así evita recomendar combinaciones alejadas de los datos. Un test verifica que ningún punto de la ruta quede a más de 0,6 de un perfil real.

Implementé el modelo en NumPy y derivé la retropropagación a mano. Tiene cerca de 18.000 parámetros. Agregar una dependencia de unos 200 MB para hacer cuatro multiplicaciones de matrices no se justificaba en este caso. El entrenamiento se ejecuta por separado y produce un artefacto de 207 KB. El backend solo necesita cargarlo y hacer esas multiplicaciones.

### Límites del producto

La aplicación no aprueba ni rechaza créditos. La interfaz lo aclara. Muestra escenarios basados en el comportamiento registrado, pero no toma decisiones crediticias. Tampoco muestra un puntaje: el objetivo es que la persona explore posibles cambios, no que interprete un número como una evaluación real.

### Datos utilizados

Usé el conjunto UCI German Credit, que contiene 1.000 perfiles y 20 atributos. Es de Alemania, de 1994, y corresponde a crédito de consumo, no hipotecario. Lo usé por la estructura de sus perfiles, no por sus montos.

El conjunto ayuda a definir la forma de la población y la frontera entre perfiles. La relación entre el comportamiento de una persona en Colombia y los ejes del modelo la definí yo. Esa correspondencia está en `domain/credit.py`, con sus rangos de referencia. No se obtuvo directamente de los datos.

## Cómo ejecutarlo

```sh
cp .env.example .env
docker compose up --build
```

El frontend queda disponible en `http://localhost:5173` y la API en `http://localhost:8000`.

Para ejecutar los tests, primero inicia PostgreSQL:

```sh
docker compose up -d db
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
cd backend
POSTGRES_HOST=localhost POSTGRES_USER=habicapital \
POSTGRES_PASSWORD=local-development-only POSTGRES_DB=habicapital \
../.venv/Scripts/python.exe -m pytest -v
```

La suite tiene 185 tests. Incluye pruebas de dominio, aplicación sin base de datos, integración, concurrencia con hilos reales y 11 pruebas del modelo de difusión con una distribución conocida.

Estos comandos entrenan el modelo y cargan datos de demostración. Se ejecutan manualmente:

```sh
cd backend
../.venv/Scripts/python.exe scripts/train_credit_model.py  # Entrena y guarda model.npz
../.venv/Scripts/python.exe scripts/seed_demo.py             # Carga 14 meses de historial de ejemplo
```

Esta consulta permite comprobar que la suma de los asientos del ledger es cero:

```sql
SELECT SUM(amount_minor) FROM persistence_ledgerentrymodel; -- 0
```

## Stack y decisiones técnicas

**Python, Django y DRF.** Elegí Python porque es el lenguaje en el que trabajo más rápido y puedo explicar mejor el código. Django ofrece transacciones y un ORM integrado con PostgreSQL. También permite usar `SELECT FOR UPDATE` y restricciones de base de datos sin escribir SQL para cada operación.

**PostgreSQL.** Lo elegí por las transacciones ACID, el bloqueo por fila y las restricciones que puede hacer cumplir la base de datos. Algunas protecciones del proyecto viven en PostgreSQL y no dependen solo del código. El reto menciona bases relacionales y no relacionales, pero no especifica que HabiCapital use PostgreSQL.

**React y TypeScript.** Este stack cubre el frontend descrito en el reto. TypeScript permite representar los montos como `bigint` y detectar conversiones accidentales a punto flotante.

**NumPy para el modelo.** El modelo tiene cerca de 18.000 parámetros. PyTorch habría agregado unos 200 MB a CI y a la imagen de producción para hacer cuatro multiplicaciones de matrices. Implementarlo a mano tomó una tarde y me permite explicar cada operación.

**Monolito modular.** Una transferencia no necesita cruzar la red entre varios servicios. Mantenerla en un solo proceso evita tener que coordinar transacciones distribuidas para garantizar que el dinero no se pierda. Las capas están separadas, así que más adelante sería posible extraer un componente si hiciera falta.

# Las ocho preguntas

## 1. Decisiones clave

**Ledger de doble partida.** No guardo un saldo que se modifica con cada operación. Guardo asientos inmutables y calculo el saldo sumándolos. Cada operación crea dos asientos cuya suma es cero.

**Cuenta de sistema para los depósitos.** Un depósito simulado también crea dos asientos. Por ejemplo, un depósito de 50.000 registra `-50.000` en `EXTERNAL_FUNDING` y `+50.000` en la cuenta del usuario. Esa es la única cuenta que puede quedar en negativo. Su saldo muestra cuánto dinero se ha inyectado al sistema.

Así, la suma de todo el ledger es siempre cero, incluso después de los depósitos. Se puede comprobar con una consulta. No hay que crear una excepción para las operaciones que agregan dinero desde afuera.

**El saldo se calcula desde el ledger.** No hay una columna `balance`. Calcularlo puede ser más lento, pero evita que un saldo guardado quede desactualizado frente a los asientos.

**Montos enteros.** `Money` guarda centavos como enteros. Rechaza floats, booleanos y mezclas de monedas. No convierte a punto flotante.

**La base de datos impide modificar el ledger.** Un trigger de PostgreSQL rechaza cualquier `UPDATE` o `DELETE` sobre los asientos. Así, la inmutabilidad no depende solo de que la aplicación siga una regla.

En [`docs/architecture-decisions.md`](docs/architecture-decisions.md) explico cada patrón, su costo y las alternativas que descarté. También explico por qué evalué Singleton y no lo usé.

## 2. Cómo verifico que el sistema no pierde dinero

### Riesgos que revisé

1. **Escribir solo un asiento.** Si se acredita una cuenta sin debitar otra, o al revés, el dinero aparece o desaparece.
2. **Leer el saldo antes de bloquear la cuenta.** Dos transferencias podrían ver los mismos fondos y aprobarse, aunque juntas dejen la cuenta en negativo.
3. **Procesar dos veces un reintento.** Si el cliente no recibe respuesta y repite la solicitud, podría duplicar la operación.
4. **Dejar una operación a medias.** Un error podría ocurrir después de guardar solo parte de los asientos.
5. **Redondear mal un reparto.** Las partes de una división podrían no sumar el total original.
6. **Crear un deadlock.** Dos transferencias cruzadas podrían bloquear las mismas cuentas en orden opuesto y quedar esperando.

### Protecciones implementadas

**Asientos completos.** El factory devuelve una tupla con los dos asientos. El repositorio solo ofrece `append(entries)`, que recibe el conjunto completo.

**Bloqueo antes de leer el saldo.** Uso `SELECT FOR UPDATE` para bloquear las dos cuentas y después leo el saldo. Un test de aplicación registra el orden de las llamadas y falla si se cambia.

**Orden fijo para los bloqueos.** Bloqueo las cuentas por UUID ascendente, sin importar cuál envía el dinero. Así, las transferencias A→B y B→A siguen el mismo orden y no se bloquean mutuamente.

**Idempotencia en la base de datos.** Un constraint de unicidad evita procesar dos veces la misma llave. Consultar primero si la llave existe y luego insertar no alcanza: dos solicitudes simultáneas podrían pasar la consulta antes de que alguna inserte.

**Una transacción por operación.** La transacción incluye el registro de idempotencia y los dos asientos. Si falla una parte, se revierte todo. Los efectos secundarios que no son críticos, como actualizar el gasto compartido, ocurren después del commit.

**Reparto con enteros.** El residuo se distribuye de forma determinista, de a un centavo.

### Pruebas ejecutadas

Las pruebas siguientes se ejecutaron contra el servidor con solicitudes concurrentes:

| Prueba | Resultado |
|---|---|
| 10 transferencias simultáneas con saldo suficiente para una | 1 respuesta `201` y 9 respuestas `422`. El saldo no quedó negativo. |
| 12 solicitudes simultáneas con la misma llave de idempotencia | 1 respuesta `201`, 11 respuestas `200`, el mismo `operation_id` en todas y una sola operación en el ledger. |
| 40 transferencias cruzadas A→B y B→A | 40 respuestas `201` y ningún deadlock. |
| 20 depósitos y transferencias sobre la misma cuenta | Saldo final exacto al peso. |

También probé exhaustivamente 32.934 combinaciones de total y número de participantes: totales de 1 a 3.000 y entre 2 y 12 participantes. En todas, las partes sumaron el total, ninguna quedó en cero y la diferencia máxima entre la parte mayor y la menor fue de un centavo.

Para comprobar la inmutabilidad, ejecuté un `DELETE` directamente con `psql`, sin pasar por el backend. PostgreSQL respondió `ERROR: Ledger entries are append-only`.

En una prueba de inyección SQL envié `'; DELETE FROM persistence_ledgerentrymodel; --` como título de un gasto. La aplicación lo guardó como texto y el ledger no cambió. Hay un test de regresión para ese caso.

Otra prueba provoca un error después de escribir el primer asiento. Comprueba que no quede ningún asiento ni un registro de idempotencia huérfano que impida un reintento válido.

Ejecuté los tests de concurrencia cinco veces seguidas. Después de estas pruebas, la suma global del ledger siguió siendo `0`.

### Pruebas del modelo

Probé el modelo con la distribución de las dos medialunas entrelazadas, cuya forma se conoce de antemano. Once tests revisan estos resultados:

- Las muestras generadas quedan cerca de la distribución real. La mediana de la distancia al punto real más cercano es menor que 0,2.
- El modelo genera las dos medialunas, no solo una. Esto comprueba que no haya colapsado a una parte de la distribución.
- Un punto en una zona vacía se mueve hacia los datos y reduce su distancia a la distribución en más de 75%.
- La retropropagación reduce la pérdida a menos de la mitad. Esto sirve para detectar errores en las derivadas escritas a mano.

En el modelo usado por la aplicación, los 2.500 perfiles generados tienen una distancia mediana de `0,056` respecto al perfil real más cercano del conjunto de datos. Los perfiles generados y los datos reales aparecen superpuestos en el mapa.

Durante las pruebas encontré un problema en el planificador de ruido. Con 200 pasos, los valores de `beta` habituales para un DDPM de 1.000 pasos dejaban 36% de señal al final. Por eso, iniciar el muestreo desde ruido puro no era válido. Corregí el planificador y la pérdida bajó de 0,52 a 0,31.

## 3. Qué dejé fuera

**Autenticación real.** La aplicación no implementa login ni contraseñas reales. El frontend permite elegir una cuenta activa. Construir autenticación bien llevaba tiempo y no era el foco del reto. Una implementación incompleta habría dado una impresión de seguridad que no existe.

**Otros métodos de reparto.** Dejé preparada la interfaz `SplitStrategy`, pero solo implementé el reparto equitativo. `SharedExpense` no depende de un tipo de reparto específico. Preferí una extensión que funciona a varias opciones sin usar.

**Editar o borrar gastos.** Si un gasto ya tiene pagos, editarlo requiere definir qué pasa con el dinero transferido. No agregué esa función sin resolver ese caso.

**Otras funciones.** Dejé fuera paginación, búsqueda, notificaciones, gastos recurrentes, reversos, comisiones y varias monedas por alcance.

**Reintentos automáticos y backoff.** Si la base informa un conflicto, la aplicación lo devuelve como error. Automatizar el reintento podría ocultar las carreras que las pruebas intentan detectar. En producción definiría una política específica.

**Tests de frontend.** Verifiqué el frontend manualmente en el navegador. Es una deuda pendiente, sobre todo para la animación de partículas, que está hecha en canvas y no tiene pruebas automáticas.

**Validación completa del modelo.** No hice validación cruzada, no separé un conjunto de prueba, no medí otras métricas generativas y no audité sesgos. El tiempo disponible no alcanzó. Por eso, los resultados que presento no equivalen a una validación para uso real.

## 4. Qué haría con más tiempo

- **Probar el ledger con secuencias aleatorias.** Ahora verifico la conservación con secuencias que elegí. Generaría depósitos, transferencias y fallos aleatorios, y comprobaría que la suma siga siendo cero.
- **Medir el costo de calcular el saldo.** Elegí no guardar una copia del saldo para evitar inconsistencias. Con los datos de demo no se nota el costo, pero no medí cuántos asientos por cuenta empiezan a hacerlo lento.
- **Agregar idempotencia a los depósitos.** Las transferencias la tienen, pero los depósitos no. Como son simulados no es urgente, aunque la diferencia no se debe solo al diseño.
- **Agregar tests al frontend.** Empezaría por la conversión entre pesos y centavos y por la vista previa del reparto, para comprobar que coincidan con el backend.
- **Definir cuánto duran las llaves de idempotencia.** Ahora no expiran, así que la tabla crecería sin límite en un sistema real.

## 5. Qué no sé todavía

**Cómo se comportaría con carga real.** Las pruebas de concurrencia usan decenas de solicitudes simultáneas en una máquina. No medí cuándo el bloqueo por fila se vuelve un cuello de botella. Una cuenta con muchas operaciones podría serializarlas, pero no lo he comprobado.

**Si el nivel de aislamiento es adecuado para todos los casos.** Uso `READ COMMITTED` con bloqueos pesimistas porque puedo explicar cómo funciona en este sistema. No tengo experiencia práctica comparándolo con `SERIALIZABLE` y reintentos.

**Cómo se opera un ledger financiero real.** Implementé doble partida porque permite verificar la conservación, pero no conozco en detalle cómo un equipo concilia sistemas externos, prepara reportes, audita operaciones o responde a reclamos.

**Cómo monitorear el sistema.** No agregué métricas, trazas ni alertas. Si algo fallara en producción, no tendría una forma automática de detectarlo antes de que lo reporte un usuario.

**Si esta extensión es la que más valor agrega.** La elegí porque el enunciado la sugería, pero no hablé con personas que tengan este problema.

**Qué tan bueno es el clasificador.** Acierta 72,9%, frente a 70,0% al predecir siempre la clase mayoritaria. La diferencia es de 2,9 puntos porcentuales. Reducir 20 atributos a dos ejes interpretables probablemente cuesta precisión. Además, no usé validación cruzada ni un conjunto de prueba separado, así que ese resultado puede ser optimista.

**Si el mapeo de comportamiento colombiano es razonable.** Yo definí los rangos de referencia. Por ejemplo, consideré 1.500.000 mensuales como el extremo alto de capacidad y 24 meses como el extremo alto de constancia. Una persona experta en riesgo probablemente revisaría esos valores.

**Si el modelo tiene sesgos.** German Credit incluye edad y estado civil, y se usa en estudios sobre equidad algorítmica. No incluí esos atributos en los dos ejes, pero no medí si aparecen indirectamente por su relación con otros atributos. Esa sería una de las primeras revisiones antes de pensar en usuarios reales.

## 6. Supuestos

- **La autenticación es simulada.** La aplicación muestra una pantalla de acceso, pero no envía, guarda ni compara la contraseña. Solo verifica que exista el usuario. La interfaz lo indica y hay un comentario en el código donde se descarta la contraseña. Implementar hashing, sesiones y recuperación de contraseña quedaba fuera del alcance. El reto pedía un usuario con saldo; prioricé demostrar el manejo del dinero.
- **Solo hay una moneda: COP.** Cada monto conserva su moneda y el sistema lanza una excepción si se mezclan monedas. Esto deja más clara la operación si se agrega otra moneda en el futuro.
- **Los depósitos son simulados y siempre se completan.** No hay pasarela de pagos, como permite el enunciado.
- **La interfaz recibe pesos enteros.** El sistema guarda centavos porque el reparto puede necesitarlos.
- **Quien paga un gasto compartido ya cubrió su parte.** Las otras personas le transfieren a quien pagó. Una transferencia asociada al gasto solo es válida si va de un participante a esa persona.
- **Se permite pagar de más.** El pendiente llega a cero y la aplicación muestra el excedente. Si el dinero ya se movió, el registro debe describirlo.
- **Un gasto compartido necesita al menos dos personas.** Un gasto de una persona no se reparte y no genera deudas entre participantes.

## 7. Cómo trabajé con IA

### Roles

Usé dos agentes con tareas distintas:

- **Claude Code como arquitecto y revisor.** Decidía qué cambiar, en qué capa hacerlo, qué invariantes podían verse afectados y qué tests se necesitaban. Dejaba esas decisiones en `PLAN.md`; no implementaba.
- **Codex CLI como implementador.** Leía el plan y lo implementaba. No debía rediseñar el alcance. Si encontraba una contradicción o una instrucción ambigua, tenía que detenerse y reportarla.
- **Yo revisaba las decisiones de arquitectura y hacía los commits.**

El contrato está en [`AGENTS.md`](AGENTS.md) y las reglas de implementación, en [`.agents/skills/safe-financial-implementation/`](.agents/skills/safe-financial-implementation/).

Avancé por objetivos: primero el plan, luego la implementación, la revisión del cambio y los tests. Después hacía el commit.

Separar los roles ayudó a detectar contradicciones. Si un mismo agente escribe el plan y lo implementa, puede pasar por alto problemas de su propia propuesta. Al pedirle al implementador que siguiera un plan escrito por otro agente, las contradicciones quedaban más visibles.

Yo elegía la extensión del producto, el modelo financiero y el alcance. También decidía cuándo la arquitectura se estaba complicando demasiado. A los agentes les pedía implementar el código y revisarlo.

### Errores y correcciones

Registré tres casos en [`docs/ai-log.md`](docs/ai-log.md). El que más me enseñó fue un invariante incompleto.

Antes de que existiera código, le pedí a Claude que escribiera los invariantes financieros. Definió INV-1 como “los asientos de una operación suman cero”. Lo aprobé. Al planear los depósitos, detectó que acreditar solo la cuenta del usuario sumaría 50.000 en vez de cero. El invariante no cubría la primera operación que agrega dinero al sistema.

Podía dejar el depósito con un solo asiento y perder la doble partida, o crear una excepción para los depósitos. Ambas opciones debilitaban la verificación del ledger. La solución fue registrar la otra parte en `EXTERNAL_FUNDING`. Desde entonces, todos los asientos siguen sumando cero.

Aprendí que una regla puede sonar correcta y aun así no cubrir un caso básico. Conviene probarla con ejemplos concretos, incluso con el primer depósito.

En otro caso, Codex se detuvo antes de implementar los gastos compartidos. El plan pedía que cada cuota fuera positiva, pero también pedía repartir un centavo entre hasta nueve personas. Eso es imposible sin dejar a alguien con cero. El agente tenía razón; el error estaba en mi plan. Decidí rechazar el gasto cuando el total es menor que el número de participantes, en vez de cambiar la regla de las cuotas.

El tercer caso cambió cómo cierro el trabajo. Codex marcó un objetivo como “Implemented”, aunque no había podido ejecutar ningún test. Más adelante explicaba que su entorno no tenía Docker ni red. La diferencia entre el titular y la evidencia podía pasar inadvertida. Ahora ningún objetivo se cierra con pruebas ejecutadas por el mismo agente que escribió el código: yo corro los tests.

### Qué aprendí al usar IA

La IA puede ayudar a escribir código y a detectar problemas, pero el resultado necesita verificación. En este proyecto, las reglas explícitas hicieron más fácil encontrar contradicciones. En los tres casos registrados, un agente encontró un problema al chocar con una regla escrita, y dos de esos problemas los había introducido yo.

## 8. Qué aprendí

**El ledger de doble partida permite verificar una propiedad.** Antes lo relacionaba principalmente con la contabilidad. En este reto entendí que convierte “¿se perdió dinero?” en una consulta concreta: comprobar que la suma sea cero.

**La idempotencia depende de la base de datos.** Al principio habría consultado si una llave existía y luego la habría insertado. Dos solicitudes simultáneas pueden pasar esa consulta antes de que se guarde la primera. La restricción de unicidad de la base resuelve ese caso.

**El orden de los bloqueos evita deadlocks.** Si todas las operaciones bloquean las cuentas con el mismo criterio, no importa quién envía el dinero: todas esperan en el mismo orden.

**Las pruebas también pueden comprobar que un fallo no se propague.** Una prueba provoca un error al actualizar un gasto y verifica que la transferencia siga registrada correctamente. Esa prueba comprueba que el evento tiene una razón concreta; sin ella, la separación sería más difícil de justificar.

**Un modelo de difusión puede ser pequeño.** Lo relacionaba con imágenes y GPU. En este caso, el modelo consiste en agregar ruido, aprender a predecirlo y recorrer el proceso al revés. Lo útil es que aprende la forma de los datos. Aquí lo uso para que las rutas se mantengan cerca de perfiles posibles, no para hacer una predicción de crédito.

**Derivar la retropropagación ayuda a entender el modelo.** Escribí la derivada de cada capa. La primera versión estaba mal y lo detecté porque el modelo no reprodujo las dos medialunas. Comparar el resultado con una distribución conocida permitió comprobar el comportamiento, no solo leer el código.

**La IA necesita límites claros y revisión.** En este proyecto, los agentes fueron más útiles cuando sus responsabilidades y las reglas estaban escritas. Eso ayudó a que aparecieran las contradicciones, pero no reemplazó mi revisión ni la ejecución de los tests.

## Estructura del proyecto

```text
backend/
  src/domain/          Money, Account, LedgerEntry, reparto, eventos y perfil crediticio.
                       Python puro, sin Django ni NumPy.
  src/application/     Comandos, servicios y facade. Controla las transacciones.
  src/infrastructure/  ORM, repositorios y migraciones. Único lugar que usa FOR UPDATE.
                       Incluye credit/, el modelo de difusión y su artefacto.
  src/presentation/    Controladores y serializers. No contiene reglas de negocio.
  scripts/             Entrenamiento del modelo y carga de datos de demo.
                       Se ejecutan manualmente, fuera de las solicitudes.
  data/                Conjunto UCI German Credit tal como se descarga.
frontend/src/           Seis pantallas y tokens de tema.
docs/                   Decisiones de arquitectura, registro de IA, objetivos y demo.
```

Las dependencias apuntan hacia las capas internas. Un test recorre `src/domain/` y falla si encuentra una importación de Django. Así, una dependencia prohibida rompe el build en lugar de quedar como una regla informal.

**Documentos relacionados:**

- [Decisiones de arquitectura y patrones](docs/architecture-decisions.md)
- [Registro del trabajo con IA](docs/ai-log.md)
- [Seguimiento de los objetivos](docs/GOALS.md)
- [Contrato entre agentes](AGENTS.md)