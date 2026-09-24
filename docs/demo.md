# Demo — puntos para el video (máximo 5 minutos)

El reto dice explícitamente **no leer de un script**. Esto no es un guion: es el
orden de lo que se muestra y la idea que va con cada paso. Habla con tus palabras.

## Antes de grabar

```sh
docker compose up -d db
cd backend
../.venv/Scripts/python.exe manage.py migrate
../.venv/Scripts/python.exe scripts/seed_demo.py
```

El sembrador crea cuatro cuentas con historial de varios meses: Samuel con 14,
Juan con 9, Laura con 6, y **Mariana con 1 — que existe justamente para mostrar el
estado de "sin evidencia suficiente"**. Más tres gastos compartidos y pagos
parciales.

Empieza el video con **Juan** activo: es el perfil que está cerca de calificar, o
sea el que tiene una ruta interesante que mostrar.

Ten abiertas tres cosas: el navegador, una terminal con `psql`, y otra terminal
para los tests.

## El recorrido

**0:00 — La idea, en una frase** *(20s)*

Abre el dashboard. El título dice "Tu dinero, con contexto".

> Un banco mueve $60.000 y te deja una línea en el extracto. No sabe que eran de la
> cena del viernes. Eso es lo que construí.

**0:20 — El núcleo, rápido** *(40s)*

Muestra saldo y el historial. No te detengas: esto es lo que el reto pedía como
mínimo y no es lo interesante.

**1:00 — El gasto compartido** *(50s)*

Abre "Cena del viernes". Total $180.000, tres personas, $60.000 cada una, Samuel
aparece saldado porque él pagó la cuenta.

> Crear el gasto **no mueve un peso**. Registra un acuerdo. La plata se mueve
> después, con transferencias que ya eran seguras.

Esa frase importa: separa el acuerdo del dinero, y es una decisión de diseño.

**1:50 — El momento clave: pagar con contexto** *(60s)*

Cambia a la cuenta de Juan. Transfiere $60.000 a Samuel **seleccionando la cena**.

Vuelve al gasto: el pendiente bajó de $120.000 a $60.000, Juan quedó al día.

Ahora ve al historial de Juan y **señala la diferencia**: la transferencia lleva el
chip "Cena del viernes"; la carga de saldo no lleva nada.

> Ahí está el producto. El mismo movimiento de plata, pero con el acuerdo pegado.

Si solo tuvieras un minuto de video, sería este.

**2:50 — Que no se pierde un peso** *(80s)*

Cambia a la terminal de `psql`:

```sql
SELECT SUM(amount_minor) FROM persistence_ledgerentrymodel;   -- 0
```

> Cada operación escribe dos asientos que suman cero. Los depósitos también: la
> plata entra desde una cuenta de sistema. Por eso la conservación no tiene
> excepciones y la pregunta "¿perdí plata?" se responde con una query.

Luego intenta borrar un asiento:

```sql
DELETE FROM persistence_ledgerentrymodel WHERE amount_minor > 0;
-- ERROR: Ledger entries are append-only
```

> Eso es un trigger de PostgreSQL. Me estoy saltando la aplicación entera y la base
> igual dice que no.

Y los tests:

```sh
pytest -q      # 185 passed
```

> Lo que más me importa son los de concurrencia. Doce requests en paralelo con la
> misma llave de idempotencia producen **una** transferencia. Diez transferencias
> simultáneas contra un saldo que alcanza para una: pasa una sola.

**3:40 — La ruta al crédito** *(60s)*

Entra a "Tu ruta". La pantalla es oscura, a propósito: es otra habitación.

Deja que la nube se condense sin hablar encima. Dura tres segundos y vale la pena.

> Eso que acaba de pasar no es una animación de entrada. Es lo que hace el modelo:
> parte de ruido y lo convierte en estructura. Cada punto es un perfil crediticio.

Señala las cifras de arriba:

> Estos cuatro números no se los pedí a Juan. Salen de su historial en la billetera:
> nueve meses depositando, y cumplimiento del 100% en sus gastos compartidos.

Mueve el deslizador de "Hoy" a "Calificas" y deja que se vean cambiar las cifras.

> La línea no es una recta hacia el objetivo. En cada paso el modelo la reproyecta
> sobre donde viven perfiles reales. Si no hiciera eso, la recomendación sería un
> punto que voltea el clasificador pero que no describe a ninguna persona.

Cambia a **Mariana** en el selector y vuelve a "Tu ruta":

> Y cuando no hay evidencia suficiente, no le inventamos una ruta. Le decimos qué le
> falta.

Ese contraste vale más que cualquier explicación técnica.

**4:40 — Una decisión y el flujo de IA** *(50s)*

Elige **una** sola decisión. La mejor es el orden de los locks:

> Bloqueo las dos cuentas en orden ascendente de UUID, siempre, sin importar quién
> envía. Si cada transferencia bloqueara su propia cuenta primero, una A→B y una
> B→A simultáneas se esperarían para siempre. Cuarenta cruzadas a la vez: cero
> deadlocks.

Y cierra con el flujo:

> Usé dos agentes con roles separados: uno arquitecto que escribe el plan y revisa,
> otro implementador que lo ejecuta y que tiene prohibido rediseñar. El arquitecto
> escribió un invariante que decía que los asientos de una operación suman cero, yo
> lo aprobé, y dos pasos después se descubrió que el primer depósito lo violaba. De
> ahí salió la cuenta de sistema. Está documentado en el repo.

**5:20 — Fin.** Si te pasas, corta el núcleo del minuto 0:20.

## Reglas para grabar

- **No leas.** Ten estos puntos al lado, no en pantalla.
- Si algo falla en vivo, dilo y sigue. Es más creíble que un video perfecto.
- El minuto 1:50 es el que vende el producto. Los demás pueden ir rápido.
- Nunca digas "no pierde plata" sin mostrar la query inmediatamente después.
- No expliques las capas ni enumeres patrones: eso está en el README y aburre en
  video. Muestra el producto y **una** decisión técnica bien contada.

## Si te preguntan en la entrevista

**"¿Por qué difusión y no una regresión?"** Porque encontrar un cambio que voltee el
clasificador es fácil y produce basura. Lo difícil es que el cambio corresponda a
una persona que podría existir. El modelo aprende dónde vive la gente real y la ruta
se reproyecta ahí en cada paso.

**"¿Qué tan bueno es el clasificador?"** 72,9% contra 70,0% de predecir siempre la
clase mayoritaria. Dilo tal cual, sin adornar: comprimir 20 atributos en dos ejes
interpretables cuesta poder predictivo, y ese fue el intercambio.

**"¿Esto decide créditos?"** No, y está escrito en la pantalla. Es exploratorio.

## Si te falta tiempo

Corta el núcleo (minuto 0:20) y muestra solo saldo. Nunca cortes el momento del
pago con contexto, la query de conservación, ni el deslizador de la ruta.
