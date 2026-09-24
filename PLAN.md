# PLAN — La animación primero, y fuera los rótulos vacíos

Status: awaiting implementation by Codex (parte A). La parte B la hace Claude.

## Goal

Dos problemas de la pantalla "Tu ruta", y uno de tono en toda la aplicación.

**El mapa está debajo de las cifras.** La animación de las partículas es lo
más atractivo del producto y hoy te la pierdes si tardas en bajar. Tiene que
ser lo primero que se ve.

**Los antetítulos en mayúscula no dicen nada.** "TU DINERO, CON CONTEXTO",
"MÁS QUE UNA TRANSFERENCIA", "TU POSICIÓN HOY" son decoración: ocupan la línea
donde debería empezar el contenido y no ordenan nada.

---

## Parte A — Orden de la pantalla y rótulos *(Codex)*

### A1. "Tu ruta" empieza por el mapa

Reordenar `src/pages/CreditPath.tsx`. Orden nuevo, de arriba abajo:

1. **El mapa** (`<CreditMap>`), lo primero, sin nada encima.
2. **El deslizador**, pegado debajo del mapa.
3. **El titular** (`headline`) y las cuatro cifras con su procedencia.
4. **"TU RUTA"** y los tres pasos.
5. El aviso de que esto no aprueba ni niega créditos.

El estado de "sin evidencia suficiente" mantiene el mismo orden: mapa arriba,
y el bloque que explica qué falta donde antes iban los pasos.

### A2. Fuera los antetítulos decorativos

Quitar el antetítulo en mayúscula del encabezado de página en **todas** las
pantallas:

| Pantalla | Rótulo a quitar |
|---|---|
| `Dashboard.tsx` | `TU DINERO, CON CONTEXTO` y `MÁS QUE UNA TRANSFERENCIA` |
| `Transfer.tsx` | `DALE UN MOTIVO A TU DINERO` |
| `History.tsx` | `EL DETALLE DE CADA PAGO` |
| `CreateSharedExpense.tsx` | `UN PLAN EN COMÚN` |
| `SharedExpenseDetail.tsx` | `GASTO COMPARTIDO` |
| `CreditPath.tsx` | `TU POSICIÓN HOY` |
| `Login.tsx` | `TU HISTORIA CONTINÚA` |
| `CreateAccount.tsx` | `TU PRIMER PASO` |

**Se quedan** los que sí encabezan un bloque distinto dentro de la página:
`TU RUTA` (los tres pasos), `ANTES DE CREAR` (la vista previa del reparto) y
`DESDE TU CUENTA` (la columna lateral de transferir). Esos ordenan; los otros
solo decoran.

El título grande se queda en todas. Al quitar el antetítulo hay que revisar
que el espacio superior siga respirando: probablemente sobre margen.

---

## Parte B — El lienzo *(Claude, no tocar)*

Solo `src/components/CreditMap.tsx` y `creditMapShape.ts`.

- **Más zoom.** El encuadre se calcula hoy con el mínimo y el máximo absolutos,
  así que un perfil extremo encoge todo lo demás. Pasa a calcularse por
  percentiles, garantizando que la trayectoria entera quepa.
- **El camino.** Las ~500 partículas más cercanas a la ruta se alinean sobre
  ella formando un corredor luminoso que atraviesa la nube. No es decoración:
  ese camino está hecho de los perfiles reales por los que pasa tu ruta.
- **Más difusión.** El corredor también se forma desde su posición dispersa,
  así que hay un segundo momento de "ruido que se vuelve estructura".

## Affected components

**Codex (parte A):** las ocho páginas de la tabla y `src/index.css`.

**Claude (parte B):** `src/components/CreditMap.tsx`,
`src/components/creditMapShape.ts`.

`index.css` es de Codex en esta tarea. Claude no lo toca, para no repetir la
colisión de la vez pasada.

## Layer assignment

Solo presentación.

## Patterns

Ninguno nuevo.

## Invariants at risk

Ninguno de los `INV-*`. No se toca dinero, ni el backend, ni el cálculo de la
ruta: la trayectoria que llega de la API no cambia, solo cómo se dibuja.

## Decisions

1. **El mapa va primero aunque cueste contexto.** El titular explica dónde
   estás, y perderlo de la primera pantalla es un costo real; se acepta porque
   la animación es lo que comunica la idea en tres segundos y hoy se pierde.
2. **Se quitan los antetítulos decorativos, se quedan los estructurales.** El
   criterio es simple: si encabeza un bloque distinto dentro de la página, se
   queda; si solo adorna el título, se va.
3. **El corredor se hace con las partículas más cercanas a la ruta**, no con
   partículas inventadas. Mantiene la afirmación del producto: el camino pasa
   por gente que existe.

## Required tests

No hay runner de tests en el frontend. La puerta:

1. `npm run lint` pasa.
2. `npm run build` pasa sin errores de TypeScript.
3. Los 185 tests del backend siguen pasando, **sin cambios**.

## Acceptance criteria

1. Al entrar a "Tu ruta", el mapa es lo primero que aparece, sin scroll.
2. El deslizador queda inmediatamente debajo del mapa.
3. Ningún antetítulo decorativo queda en las ocho pantallas de la tabla.
4. `TU RUTA`, `ANTES DE CREAR` y `DESDE TU CUENTA` siguen ahí.
5. El estado de "sin evidencia suficiente" sigue mostrando el mapa arriba.
6. `npm run lint` y `npm run build` pasan.

## Out of scope

- el backend
- `CreditMap.tsx` y `creditMapShape.ts` (los hace Claude en paralelo)
- volver a tocar la escala de la interfaz ni el login
- rediseñar cualquier pantalla más allá de quitar el antetítulo
