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
