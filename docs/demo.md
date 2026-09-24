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

El sembrador crea cuatro cuentas, y las tres primeras están por debajo del
umbral a distintas distancias, para que cada una tenga una ruta que se vea y se
vean distintas entre sí:

| Cuenta | Historial | Dónde está | Ruta |
|---|---|---|---|
| **Samuel** | 7 meses · $500.000 | el más cerca | corta |
| **Juan** | 5 meses · $350.000 | a media distancia | media |
| **Laura** | 4 meses · $300.000 | el más lejos | larga |
| **Mariana** | 1 mes | sin evidencia suficiente | no tiene, y eso es lo que muestra |

Empieza el video con **Juan**. Si quieres enseñar el contraste de rutas, entra
después como Laura: la suya es la más larga y la que mejor deja ver el cruce de
morado a turquesa.

**Antes de grabar, desactiva la reducción de animaciones de Windows.**
Configuración → Accesibilidad → Efectos visuales → Efectos de animación: encendido.
Si está apagada, la app respeta esa preferencia y **se salta la animación de las
partículas**, que es justo el momento que quieres mostrar. No es un fallo: es
accesibilidad, pero arruina el video.

Ten abiertas tres cosas: el navegador, una terminal con `psql`, y otra terminal
para los tests.

## El recorrido

**0:00 — La idea, en una frase** *(20s)*

Abre la app. Aterriza en el login. Entra con el acceso de demostración de
**Juan** — un clic, no escribas.

Si alguien pregunta por el login en la entrevista: la pantalla misma dice que
la autenticación es simulada y que la contraseña no se envía ni se guarda. Eso
es deliberado; un login que parece real insinuaría una seguridad que no existe.

Ya dentro, el título dice "Tu dinero, con contexto".

> Un banco mueve $60.000 y te deja una línea en el extracto. No sabe que eran de la
> cena del viernes. Eso es lo que construí.

**0:20 — El núcleo, rápido** *(40s)*

Cierra sesión y crea una cuenta en vivo desde el login: nombre y usuario, y
listo. Escribe el usuario en mayúsculas primero para que se vea que el aviso
sale **antes** de enviar, no después. Al crearla entras directo. Luego vuelve a
entrar como Juan y muestra saldo e historial.

No te detengas: esto es lo que el reto pedía como mínimo y no es lo interesante.

**1:00 — El gasto compartido** *(50s)*

Abre "Cena del viernes". Total $180.000, tres personas, $60.000 cada una, Samuel
aparece saldado porque él pagó la cuenta.

> Crear el gasto **no mueve un peso**. Registra un acuerdo. La plata se mueve
> después, con transferencias que ya eran seguras.

Esa frase importa: separa el acuerdo del dinero, y es una decisión de diseño.

**1:50 — El momento clave: pagar con contexto** *(60s)*

Transfiere $60.000 a Samuel **seleccionando la cena**.

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

**Cállate cuatro segundos.** Las partículas salen de ruido, se condensan en la
casa de Habi, se disuelven y se reordenan en los perfiles reales, y al final las
más cercanas a tu ruta se alinean formando el camino. Es el mejor plano del
video; no lo pises hablando.

Cuando ya estén los datos:

> Eso no es una animación de entrada. Es lo que hace el modelo: parte de ruido y
> lo convierte en estructura. Primero le pedí que formara el logo, para que se
> vea que la forma la decide uno. Después lo suelta y cada punto vuelve a ser un
> perfil crediticio real.

Señala las cifras de arriba:

> Estos cuatro números no se los pedí a Juan. Salen de su historial en la billetera:
> nueve meses depositando, y cumplimiento del 100% en sus gastos compartidos.

Mueve el deslizador de "Hoy" a "Calificas" y deja que se vean cambiar las cifras.

Señala el color del camino:

> El corredor no es de un color plano. Arranca morado, donde todavía no
> calificas, y termina turquesa. Ese degradado es la probabilidad real en cada
> punto del camino, no una decoración.

> La línea no es una recta hacia el objetivo. En cada paso el modelo la reproyecta
> sobre donde viven perfiles reales. Si no hiciera eso, la recomendación sería un
> punto que voltea el clasificador pero que no describe a ninguna persona.

Cierra sesión, entra con el acceso de demostración de **Mariana**, y vuelve a
"Tu ruta":

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
