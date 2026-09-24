# Registro de trabajo con IA

Bitácora de desacuerdos, errores y correcciones **reales** entre los agentes y yo.

No es un log de prompts. Solo entro aquí cosas que cambiaron una decisión o
que habrían causado un defecto si nadie las hubiera visto. El reto pide contar
al menos una vez en que la IA se equivocó o casi me hizo equivocar; quiero que
ese ejemplo sea verdadero y verificable contra el historial de git, no una
anécdota redactada al final.

Formato: fecha, qué pasó, quién lo detectó, qué se hizo.

---

## 2026-09-23 — La IA escribió un invariante que su propio plan violaba

**Qué pasó.** Claude redactó `references/invariants.md` antes de que existiera
código. INV-1 (conservación) quedó escrito así: *"the ledger entries of a
single operation sum to zero"*. Suena obviamente correcto y lo aprobé sin
objetar.

Dos pasos después, el mismo agente planeó el goal de depósitos. Un depósito
simulado mete plata al sistema desde afuera: si solo escribes `+50.000` en la
cuenta del usuario, los asientos de esa operación suman `50.000`, no cero. El
invariante que la IA había escrito como no negociable era violado por la
primera operación monetaria que el sistema iba a ejecutar.

**Quién lo detectó.** Claude, al planear el goal de depósitos — pero contra un
documento que él mismo había escrito y que yo ya había aceptado. Es decir: la
IA produjo con total seguridad una regla incompleta, y la incompletitud solo
salió a la luz cuando se intentó aplicarla a un caso concreto.

**Por qué importa.** Si nadie lo nota, hay dos salidas y las dos son malas. O
el depósito se implementa como asiento de una sola pata, y entonces el ledger
deja de ser de doble partida y la frase "no perdemos un peso" pierde su
respaldo; o se mete una excepción del tipo "los depósitos no cuentan para la
conservación", que es exactamente el tipo de excepción que después se copia a
otras operaciones y termina escondiendo un bug de verdad.

**Qué se hizo.** Se introdujo una cuenta de sistema `EXTERNAL_FUNDING`, única
cuenta autorizada a quedar en negativo. Un depósito ahora escribe `-50.000`
contra funding y `+50.000` contra el usuario. INV-1 se reescribió para decir
que la conservación es **global y sin excepciones**, y se añadió una segunda
verificación: la suma de *todo* el ledger es cero, siempre. INV-3 se ajustó
para declarar que funding es la única cuenta exenta de fondos suficientes.

**Lo que me llevo.** La IA es buena escribiendo reglas que suenan rigurosas y
mala notando que su propia regla no cubre un caso que aún no ha visto. Las
reglas abstractas no se validan leyéndolas: se validan corriéndolas contra el
caso más aburrido que exista. Aquí el caso aburrido era "el primer depósito".

---

## 2026-09-23 — "Implementado" no quería decir "funciona"

**Qué pasó.** Codex terminó el goal de fundación y reportó bajo el encabezado
*Implemented*: "Created all 31 listed files". Bajo *Tests*: "All four required
tests exist. Static checks passed."

Leído rápido, eso es un goal terminado. No lo era. Más abajo, en *Risks*, el
mismo reporte decía que Docker no estaba disponible en su entorno, que las
descargas de dependencias fueron bloqueadas, y que por lo tanto ni los tests ni
el build del frontend se habían llegado a ejecutar. El agente lo declaró
honestamente —cerró con "Goal 0 is **not verified complete**"— pero la
información que contradecía el titular estaba tres secciones más abajo.

**Qué habría pasado si me lo trago.** Habría cerrado el goal con cuatro tests
que nadie corrió nunca, y habría construido el ledger encima de una base no
verificada. El fallo no habría aparecido en el goal 0: habría aparecido en el
goal 3, cuando un test de concurrencia fallara y yo no supiera si el problema
era el lock, la transacción o que la fundación nunca funcionó.

**Qué hice.** Levanté Docker y Postgres 17 en mi máquina, instalé las
dependencias y corrí todo yo: los cuatro tests pasan contra PostgreSQL real
(no SQLite, que es justo lo que uno de esos tests verifica), el build de
TypeScript compila, y el endpoint responde 200. Además hice una prueba que no
estaba en el plan: tumbé el contenedor de la base con el backend arriba y
confirmé que devuelve 503 `degraded` en vez de un 500 sin manejar, y que se
recupera solo al levantarla otra vez. Eso vale más que el test con mock,
porque el mock demuestra que el `except` está escrito y esto demuestra que
atrapa el error que de verdad lanza el driver.

**Lo que me llevo.** El reporte de un agente describe lo que *intentó* hacer,
no lo que quedó funcionando, y la diferencia se esconde donde uno deja de
leer. Mi regla desde aquí: ningún goal se cierra con evidencia que produjo el
mismo agente que escribió el código. Los tests los corro yo.

---

## 2026-09-24 — Un test que pasaba solo y fallaba acompañado

**Qué pasó.** En la fase de endurecimiento escribí un test de concurrencia que
mezcla depósitos y transferencias sobre la misma cuenta. Corriéndolo aislado
pasaba. Corriéndolo junto al archivo de concurrencia existente fallaba, con un
error de llave foránea al insertar un asiento.

La causa: los tests transaccionales vacían las tablas entre casos, y eso
borraba la cuenta `EXTERNAL_FUNDING`, que se crea en una migración de datos.
El archivo de concurrencia que ya existía tenía un fixture justo para
restaurarla; mi archivo nuevo no. Moví el test a donde vive esa
infraestructura en vez de duplicar el fixture.

**Por qué lo dejo anotado.** Lo tentador era correrlo aislado, verlo verde y
seguir. Fallaba 5 de 5 veces en compañía, siempre igual, así que no era
inestabilidad: era estado compartido. La diferencia importa, porque "el test
es flaky" es una excusa y "el test depende de datos que otro test borra" es un
defecto con causa.

**Lo que me llevo.** Un test que pasa solo y falla acompañado no está roto por
azar: está diciendo algo sobre estado compartido que no modelé. Y correr la
suite una sola vez no lo habría mostrado nunca.

---

## 2026-09-24 — El agente se negó a implementar, y el error era mío de diseño

**Qué pasó.** Escribí el plan de gastos compartidos con dos requisitos que
parecían independientes. Uno decía que toda cuota debe ser positiva. Otro
pedía un test de propiedad que recorriera totales desde 1 centavo repartidos
entre hasta 9 participantes, verificando que las partes sumaran exacto.

Codex no escribió una línea. Reportó que los dos requisitos son incompatibles:
repartir 1 peso entre 3 personas obliga matemáticamente a que alguien quede en
cero, y no existe implementación que cumpla ambos.

**Por qué es el caso más interesante que me ha pasado con IA.** Los dos
registros anteriores son sobre agentes que se equivocan o sobre instrucciones
mías mal redactadas. Este es distinto: el agente encontró **un defecto de
diseño en el plan del arquitecto**, en un requisito que yo había escrito con
confianza y revisado.

Y lo que habría pasado sin ese contrato es peor que un error visible. Un agente
optimizando por "terminar la tarea" resuelve el conflicto en silencio y por el
camino más fácil: permite cuotas de cero. El sistema compila, los tests pasan,
y queda una violación de invariante enterrada en el código, en la operación
que reparte plata entre personas. Nadie se entera hasta que alguien reclama.

**Qué decidí.** No debilité la regla: rechacé la entrada. Un gasto cuyo total
es menor que su número de participantes devuelve 400. Un participante que no
debe nada no es un participante, y un gasto del que nadie puede deber una parte
no es un gasto. La regla "toda cuota es positiva" sigue intacta, y el caso
imposible ahora tiene una respuesta explícita en vez de un comportamiento
accidental.

**Lo que me llevo.** El valor de decirle a un agente "detente ante una
contradicción" no está en que evite código malo: está en que convierte los
huecos de mi propio razonamiento en preguntas, cuando normalmente se
convertirían en comportamiento. Verifiqué después el reparto con 32.934
combinaciones de total y número de participantes: suma exacta en todas, ninguna
cuota en cero, diferencia máxima entre cuotas de un centavo.

---

## 2026-09-23 — El agente se frenó por una ambigüedad mía

**Qué pasó.** En el primer intento de implementar la fundación, Codex no
escribió ni un archivo. Reportó un conflicto: mi instrucción decía
"`backend/src/` debe contener solo `presentation/`", pero `PLAN.md` listaba
también `backend/src/__init__.py`. Literalmente, un `__init__.py` no es
`presentation/`.

**Por qué lo dejo anotado.** Tenía razón, y el contrato que yo mismo escribí le
ordena parar y reportar en vez de improvisar arquitectura. Es el
comportamiento que quería. Pero cuesta una iteración completa, y la causa no
fue el modelo: fue que yo escribí una restricción absoluta ("solo") cuando
quería una prohibición específica (no crear `domain/`, `application/` ni
`infrastructure/`). Al reformularla así, implementó sin objetar.

**Lo que me llevo.** Un agente con instrucción de detenerse ante
contradicciones convierte cada ambigüedad mía en una parada. Es el intercambio
correcto para código que mueve plata —prefiero pagar iteraciones que recibir
arquitectura inventada— pero significa que la precisión de mis instrucciones
es parte del costo, no un detalle de estilo.

---
