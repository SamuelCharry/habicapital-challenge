# Demo — puntos para el video (máximo 5 minutos)

El reto dice explícitamente **no leer de un script**. Esto no es un guion: es el
orden de lo que se muestra y la idea que va con cada paso. Habla con tus palabras.

## Antes de grabar

```sh
docker compose up -d db
cd backend && ../.venv/Scripts/python.exe manage.py migrate
```

Sembrar datos limpios: cuatro cuentas (Samuel, Juan, Laura, Mariana) con saldo, el
gasto "Cena del viernes" de $180.000 entre tres, y "Arriendo noviembre" de
$2.400.000. Deja **el pago de Juan sin hacer** — lo haces en vivo, es el momento
más importante del video.

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
pytest -q      # 159 passed
```

> Lo que más me importa son los de concurrencia. Doce requests en paralelo con la
> misma llave de idempotencia producen **una** transferencia. Diez transferencias
> simultáneas contra un saldo que alcanza para una: pasa una sola.

**4:10 — Una decisión y el flujo de IA** *(50s)*

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

**5:00 — Fin.**

## Reglas para grabar

- **No leas.** Ten estos puntos al lado, no en pantalla.
- Si algo falla en vivo, dilo y sigue. Es más creíble que un video perfecto.
- El minuto 1:50 es el que vende el producto. Los demás pueden ir rápido.
- Nunca digas "no pierde plata" sin mostrar la query inmediatamente después.
- No expliques las capas ni enumeres patrones: eso está en el README y aburre en
  video. Muestra el producto y **una** decisión técnica bien contada.

## Si te sobra tiempo

La vista previa del reparto: escribe $100.000 entre tres y muestra que da
33.333,33 / 33.333,33 / **33.333,34**, y que el frontend y el backend coinciden
hasta en a quién le toca el centavo. Es un detalle pequeño que dice mucho.

## Si te falta tiempo

Corta el núcleo (minuto 0:20) y muestra solo saldo. Nunca cortes el momento del
pago con contexto ni la query de conservación.
