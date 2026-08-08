# Diwall — Guía del operador

Versión 1.10 — Agosto de 2026 (v1.23.0) — cuatro casos de uso demostrativos adicionales (observabilidad alojada en el propio servidor, administración de plataforma de ticketing, seguimiento de eventos locales, acceso a comercio electrónico bajo "Navegación Respetuosa").

*También disponible en francés, alemán y español bajo `docs/fr/`, `docs/de/` y `docs/es/`.*

---

## ¿Por qué Diwall? Lo que realmente delega

### El problema que resuelve Diwall

Cuando trabaja con un modelo de lenguaje grande (LLM) en una aplicación web, se produce una asimetría perceptual:
el modelo lee código, ejecuta comandos y observa la salida textual, pero no ve
la interfaz que ven sus usuarios. Usted sí la ve.

Esta asimetría crea una forma específica de ansiedad: usted no sabe si lo que
el modelo describe coincide con lo que vería en un navegador. Para estar seguro, debe
ya sea confiar en ello sin más, o verificarlo usted mismo.

Diwall resuelve este problema al crear una **referencia visual compartida**:
el modelo captura la interfaz con un navegador real (Chromium sin interfaz gráfica),
y usted tiene acceso a las mismas capturas PNG y árboles de accesibilidad.
Ya no se limita a creer lo que le dice el modelo; usted observa el mismo estado que él.

```
 Browser (headless Chromium)
        │  Playwright drives it — click, fill, navigate
        ▼
 shot.py / rpa.py
        │  reads the resulting DOM state through parallel views
        ├──▶ capture_som   PNG, interactive elements numbered
        ├──▶ elements_som  JSON list — id, tag, text
        ├──▶ a11y_tree     accessibility tree, text
        └──▶ session file  cookies only (--sauver-session)
        │
        ▼
 boussole + JSON on stdout — same state you would see in a browser
        │
        ▼
 You (the model): read → analyse → decide → act → loop
```

### Lo que realmente se delega

Diwall le permite delegar la **verificación visual repetitiva y que genera ansiedad**:

- Verificar que 20 páginas de un sitio se muestran correctamente después de una implementación.
- Confirmar que un formulario de inicio de sesión funciona en la interfaz correcta.
- Asegurarse de que una implementación no haya interrumpido el renderizado de una vista crítica.
- Validar visualmente que una corrección es visible correctamente en la pantalla.

Sin Diwall, estas verificaciones son su responsabilidad. Con Diwall, el modelo las realiza y reporta el resultado, con evidencia visual.

### Lo que conserva

Usted mantiene la **validación de sentido a nivel superior**: decide si el resultado
que presenta el modelo es aceptable, consistente con sus expectativas y acorde
con lo que sus usuarios deberían ver. Esa decisión sigue siendo suya.

### Navegación Respetuosa (v1.15.0)

Diwall no oculta su identidad para evitar la detección por bots. `--stealth`
elimina los marcadores técnicos automáticos (`navigator.webdriver`) que bloquean
los navegadores sin interfaz gráfica, independientemente de la intención; no cambia la
dirección IP del operador, ni su identidad, ni el hecho de que la ejecución esté declarada. A cambio, cada ejecución
reporta su propia huella digital (`respect`: páginas visitadas, acciones ejecutadas,
duración) y respeta los retrasos configurables y los límites máximos estrictos
(`diwall.conf [navigation]`). El derecho a navegar y el deber de navegar
de manera medible se consideran inseparables; consulte `docs/RETOUR_EXPERIENCE.md`
FR-77/FR-78/FR-79 para el contexto específico que dio forma a esto.

**Destinos locales — el retardo de cortesía no es una doctrina, es un valor
por omisión (v1.19.0):** el `min_action_delay_ms: 800` que se entrega protege
una primera ejecución sin configurar frente a la internet pública — carece de
sentido contra su propia máquina de desarrollo o producción. Póngalo a `0` en
su `diwall.conf` local para depurar en local; véase `docs/MANUEL.md` sección 3b.

### Cuándo Diwall es la herramienta adecuada

| Caso de uso | ¿Adecuado para Diwall? |
|---|---|
| Validación visual después del despliegue | ✓ Sí |
| Diagnóstico de un error de renderizado | ✓ Sí |
| Navegación y entrada de formularios (máximo ~30 segundos) | ✓ Sí |
| Delegación de comprobaciones repetitivas | ✓ Sí |
| Operación larga del servidor (clonado ~2–5 minutos) | ✗ No — Tiempo de espera de Playwright |
| Eliminación o modificación masiva | ✗ No — Preferir una llamada directa a la API |
| Flujo de trabajo que requiere un "rollback" | ✗ No — Diwall no puede deshacer |

Para casos de desánimo, consulte la sección "Cuándo NO usar Diwall" `docs/GUIDE_LLM.md`.
(Se documentan las fricciones FR-59 y FR-60).

---

**Este documento está escrito para la persona que opera Diwall.**

Complementa `GUIDE_LLM.md` (destinado a modelos) con ejemplos concretos, procedimientos paso a paso y recordatorios sobre los puntos más comunes de dificultad.

---

## Casos de uso de demostración

Los casos que se presentan a continuación ilustran cómo puede ser una sesión de "agente-más-Diwall" en la práctica. Están diseñados para que usted los evalúe en relación con su propio contexto, y no como una recomendación para adoptar ninguno específico. Solo el Caso 1 se proporciona como un escenario ejecutable; los demás son narrativos a propósito, y cada uno explica sus motivos bajo su propio encabezado.

### Caso 1: Solución de problemas de CSS/JavaScript locales

Entregado como escenario real y ejecutable:
`scenarios/exemples/depannage_local.json`. Diagnostica un desplazamiento
visual o una interacción bloqueada en una interfaz servida en local: una sonda
rápida (`--mode fast`), la lectura de `erreurs_js`/`erreurs_console`, una
captura `--som` si el desplazamiento es puramente visual, y después la
validación de la corrección con `watch.py --comparer-pixel` contra una
referencia tomada antes de la regresión. Ejecútelo directamente:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/exemples/depannage_local.json \
  --guide-version 1.2
```

### Caso 2: Comparación de componentes de hardware entre diferentes tiendas

Un agente que se le pide comparar el precio y la disponibilidad de un componente en varias tiendas online podría usar Diwall con una herramienta separada de descubrimiento de URLs (por ejemplo, una instancia de búsqueda local) para encontrar páginas de tiendas candidatas, luego usar Diwall en modo "sonde" (`--mode fast`, sin PNG) con las acciones `evaluer` para extraer el precio /stock/specifications de cada página, y finalmente comparar los resultados por sí mismo.

**Deliberadamente no entregado como escenario versionado:** nombrar una tienda
concreta en un escenario público y versionado es una decisión que le pertenece
a usted, no algo que este proyecto deba decidir en su lugar. Conlleva además un
riesgo real de fragilidad: un escenario público dirigido a un sitio comercial
nombrado puede fallar meses después, cuando cambie la postura anti-bot de ese
sitio (el 39 % de los sitios comerciales de la muestra de
`docs/RETOUR_EXPERIENCE.md` FR-77 devolvió un bloqueo inmediato), lo que
desacredita el ejemplo más de lo que ayuda. Si construye esta composición usted
mismo, tenga en cuenta que cualquier herramienta de descubrimiento de URL que
combine con Diwall (una instancia de búsqueda local u otra) no es un componente
de Diwall: es una pieza aparte que el agente compone por encima.

### Caso 3: Exploración y resumen de documentación técnica (aplicaciones de una sola página)

Un agente encargado de producir una guía de integración para un sitio de documentación construido como una aplicación de una sola página podría usar `rpa.py` con `attendre_reseau_calme` para permitir que el enrutamiento del lado del cliente se complete, extraer el árbol de accesibilidad en modo rápido para mapear la estructura de la página, luego recorrer los bloques de código recursivamente con `evaluer` para obtener su contenido exacto, y finalmente sintetizar el material recopilado en una guía.

**No se envía como un escenario predefinido, por la misma razón que en el Caso 2:**
mencionar un sitio de documentación específico (o, peor aún, un proveedor de pagos específico cuya documentación es el ejemplo funcional) implica un compromiso comercial y de reputación que este proyecto no debería asumir por defecto, y el mismo riesgo de vulnerabilidad del WAF se aplica a un escenario público vinculado a un objetivo real.

### Caso 4: Configuración de un panel de control de observabilidad o análisis alojado en su propia infraestructura

Un operador que esté configurando un panel de control de monitorización o análisis web alojado localmente
detrás de un proxy inverso puede usar Diwall para controlar la propia interfaz:
crear un panel, conectar una fuente de datos, configurar una regla de alerta; todo
de la misma manera en que se configura cualquier otro panel de administración, en lugar de editar manualmente
archivos para tareas que la interfaz de usuario está diseñada para manejar. Esto incluye objetivos que están
detrás de un desafío de autenticación HTTP básica a nivel de red (`--http-credentials`,
v1.21.0): esto se ha confirmado contra una interfaz de administración protegida por Caddy real, no
simplemente una simulación: las credenciales almacenadas respondieron al
desafío en el primer intento.

**No se envía como un escenario predefinido** — la disposición del panel y los nombres de las fuentes de datos son específicos de la infraestructura de un operador, e inventar un equivalente sintético duplicaría lo que ya cubre el entorno local en el Caso 1 para la regresión estructural, no para este tipo de trabajo de configuración guiada y con múltiples pasos.

### Caso 5: administración integral de una plataforma de gestión de tickets

Diwall se utilizó en varias sesiones para configurar y operar una instalación real de ticketing alojada por el usuario: configuración de eventos, categorías de entradas, un dominio personalizado y las herramientas de escaneo/registro del día del evento, todo a través de la misma interfaz web que utilizaría un administrador humano. Se encontraron y resolvieron problemas reales durante el proceso (manejo de sesiones, peculiaridades de los menús desplegables, una solicitud de permiso que bloqueaba un paso automatizado), lo que no resultó en un éxito sin problemas. Esto es parte de lo que hace que sea un ejemplo útil: los obstáculos eran problemas comunes de la automatización web, y no algo específico de Diwall.

**No se envía como un escenario predefinido**— la configuración de los tickets afecta
la facturación y detalles específicos del lugar que son únicos para el operador, con la misma lógica que
el Caso 2.

### Caso 6: seguimiento de un calendario de eventos regionales

Un uso sencillo de la función de "semantic probe": pedirle a un agente que revise el calendario de eventos locales para conocer los próximos acontecimientos, sin saber de antemano en qué página se encuentra la respuesta. El modo rápido de Diwall (`--mode fast`, sin captura) combinado con el árbol de accesibilidad permite al agente escanear y reportar resultados en pocas solicitudes; no se necesita un modelo de visión para este tipo de tarea de solo lectura y basada en texto. Una sesión también produjo un ejemplo claro y real del comportamiento documentado de falsos positivos de la señal WAF: una página se cargó normalmente (contenido enriquecido, sin captcha, sin intersticial) mientras que [`respect.waf_bloquants`] aún se activó, debido a un recurso de terceros no relacionado en la página que coincidía con una palabra clave de detección; esto se resolvió en aproximadamente un minuto al leer el árbol de accesibilidad ya presente en la misma respuesta, tal como lo anticipa la regla del manual "señal, nunca un bloqueo".

**No se envía como un escenario predefinido** — un sitio específico de eventos regionales
no es un objetivo público estable y reproducible, y designar uno públicamente
es decisión del operador, no una configuración por defecto del proyecto.

### Caso 7: Pruebas de acceso a sitios de comercio electrónico en condiciones reales, utilizando el enfoque "Respectful Navigation"

Una observación honesta y recurrente de sesiones reales: utilizada con respeto
(retrasos limitados por tasa, límites de página/acción, `--stealth` activo, sin intento de
forzar el acceso más allá de un bloqueo real), Diwall, al ejecutarse contra una variedad de sitios de comercio electrónico, descubre que una gran proporción de las principales plataformas devuelven un bloqueo directo: HTTP 403, o una solicitud que nunca se completa, independientemente de cuán cortés sea el tráfico. Esto no es una deficiencia de Diwall que deba corregirse:
la postura anti-bot es la elección propia del sitio, y Diwall no intenta
eludirla (ver "Navegación Respetuosa" arriba). Prácticamente: para tareas de comparación de precios contra grandes plataformas comerciales, espere una proporción significativa de resultados nulos, y trate una señal de bloqueo (`respect.waf_bloquants`) como información para evitar, no como un error
para intentar nuevamente.

Una distinción que vale la pena tener en cuenta: una pantalla de verificación invisible que
nunca se resuelve y no presenta nada con lo cual interactuar (sin casilla de verificación, sin desafío de imagen) es diferente de un CAPTCHA interactivo. Este último es legítimo para responder honestamente; un agente que opera para un humano específico, desde la propia dirección IP de ese humano, no es el "robot" al que está dirigida la pregunta. La primera opción simplemente no ofrece ninguna vía de acceso desde el lado del agente, y forzar el paso (rotación de IP, suplantación de huella digital TLS) está fuera de lo que Diwall hace.

No se envía como un escenario definido, y deliberadamente no se mencionan las
plataformas involucradas — consulte la justificación sobre la fragilidad de los WAF en el Caso 2: una tabla de bloqueo/no bloqueo con fechas que está vinculada a sitios comerciales específicos queda obsoleta y socava su propio propósito más rápido de lo que lo ilustra. `docs/RETOUR_EXPERIENCE.md`
FR-77 documenta el mismo patrón a escala de panel (tasa de bloqueo inmediato del 39%).

---

## Requisitos previos antes de comenzar

```bash
# Verificar que Diwall responda.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → debe retornar {"éxito": verdadero, ...}

# 2. Verificar que el directorio cifrado esté montado (si se utiliza gocryptfs).
ls ~/Vaults/Diwall/
# → debe mostrar archivos .json, no contenido cifrado.

# 3. Verificar las credenciales para un dominio.
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.repertoire_chiffre import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'EMPTY')
"
```

---

## Configuración de credenciales por proyecto

Cada proyecto puede tener su propio directorio de credenciales. Dos métodos:

**Método 1: Variable de entorno directa (única ejecución):**

```bash
DIWALL_SECRETS_DIR=~/Vaults/MyProject \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

Método 2: Archivo de proyecto `.diwall.conf` (recomendado para proyectos recurrentes):

```bash
# Cree el archivo en la raíz del proyecto.
echo '{"secrets_dir": "../MyProject-secrets"}' > ~/git/MyProject/.diwall.conf

# Mantén el formato de Markdown exactamente como está. Responde solo con la traducción, sin preámbulos.  Luego, antepón cada invocación (o exporta al inicio de la sesión del shell).
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

El `secrets_dir` en `.diwall.conf` puede ser una ruta relativa; se resuelve
relativamente a la ubicación del archivo `.diwall.conf`.

---

## Capturar una página y analizarla

```bash
# Verificación rápida (sin archivos PNG, ~2 segundos, solo lectura).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
# → devuelve url_courante, titre_page, a11y_tree en el formato JSON.

# Captura completa con elementos numerados.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
# La captura en formato PNG se encuentra en /tmp/diwall/capture_<ts>.png.
```

**Lo que obtiene:**
- `boussole.url_courante` + `boussole.titre_page`: URL y título efectivos tras la navegación
- `capture`: ruta del PNG de la página tal como se renderizó
- `capture_som`: PNG anotado con los números de los elementos
- `a11y_tree`: estructura de la página en texto (títulos, campos, botones)

---

## Automatización de un formulario de inicio de sesión

**Paso 1** — Preparar el archivo de credenciales.

El archivo de credenciales se llama `<hostname>.json`, donde `hostname` es el resultado de
`urlparse(url).hostname`. Para `https://app.example.com/`, el archivo es
`app.example.com.json`.

```json
{"username": "admin@example.com", "password": "my-secret"}
```

**Paso 2** — Explora la página de inicio de sesión.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ --som --a11y
```

Abra la imagen PNG con anotaciones (`capture_som`) para identificar los ID de campo.

**Paso 3** — Escriba el escenario.

```bash
cat > /tmp/login.json << 'EOF'
{
  "nom": "app_login",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "after-login"}
  ]
}
EOF
```

**Paso 4** — Ejecutar.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /tmp/login.json --som
```

---

## Validación de múltiples páginas en una única ejecución

Para revisar N páginas de un sitio autenticado sin tener que volver a ingresar cada vez:

```bash
cat > /tmp/audit.json << 'EOF'
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "naviguer",     "url": "https://app.example.com/dashboard/"},
    {"type": "capturer",     "nom": "dashboard"},
    {"type": "naviguer",     "url": "https://app.example.com/settings/"},
    {"type": "capturer",     "nom": "settings"}
  ]
}
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/audit.json --som
```

---

## Extracción de un valor de la página

Para leer una cadena de texto, un contador o cualquier valor de DOM:

```bash
cat > /tmp/extract.json << 'EOF'
[{"type": "evaluer", "script": "document.title"}]
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --actions /tmp/extract.json
# → result in evaluaciones[0].valor
```

**Importante**: escriba siempre los scripts JS en un archivo `--actions`,
nunca en línea con `--action` (el shell corrompe las comillas anidadas).

---

## Configuración de la monitorización visual

```bash
# Guarde la referencia visual.
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --nom home

# 2. Comparar posteriormente (diferencia de píxeles).
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
# → veredicto: estable / deriva / regresión (código de salida 0 o 1)

# 3. En una página autenticada: primero captura con rpa.py, luego guarda.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/login.json > /tmp/out.json
CAPTURE=$(python3 -c "import json; d=json.load(open('/tmp/out.json')); print(d['captures_intermediaires'][-1])")
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --capture "$CAPTURE" --nom dashboard
```

---

## Configuración de la monitorización estructural continua (v1.18.0)

Complementa la monitorización visual anterior: esto verifica la *estructura* de la página
(código de estado, número de elementos DOM, resultados de la evaluación de JavaScript) en lugar de su
*apariencia*. Es más económico y detecta un tipo diferente de regresión (por ejemplo, un campo de formulario que ha desaparecido pero con el diseño sin cambios).

```bash
# Guarde una referencia estructural, solo una vez.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --sauver-verifier-reference /opt/diwall/references/my-scenario.ref.json

# 2. Una verificación y alerta.
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring
```

Silencioso mientras todo es estable, un único aviso `ntfy` cuando se detecta
una regresión. Prográmelo usted mismo con cron: el script hace una pasada y
termina, no entra en bucle. `scripts/*.sh` nunca se despliega en
`/opt/diwall/`, así que la entrada de cron se ejecuta desde el código fuente
git, con su propio usuario (no con la cuenta de servicio `diwall`, que no puede
acceder a `~/git/Diwall/Diwall/`):

```bash
# crontab -e (su propio archivo crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

---

## Errores comunes

| Situación | ¿Qué hacer |
|---|---|
| `FileNotFoundError` en el archivo de credenciales | Comprobar que el archivo JSON tenga el nombre completo del FQDN (`urlparse(url).hostname`) |
| `SecretsFermesError` (salida 42) | Montar el directorio cifrado: `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh` |
| JSON inválido en la salida | Utilizar `2>/dev/null \| tail -1` para extraer solo la línea JSON |
| Los ID de SoM difieren entre sesiones | Esperado — los ID de SoM se recalculan en cada captura. No los reutilice entre sesiones |
| Inicio de sesión seguido de una redirección de Django al panel | No utilizar `naviguer` en una sesión de Django reanudada; pasar la URL a través de `--url` |
| El campo `<select>` no está relleno | Utilizar `remplir_som` (no `remplir`) con el ID de SoM del `<select>` |
| Un clic no tiene efecto en un botón fuera de la vista | Agregar `{"type":"defiler","selecteur":"#the-button"}` antes del clic |
| `auth_status: "active"` incluso en la página de inicio de sesión | El selector positivo es ambiguo (encabezado persistente); agregar `--auth-indicator-negative .btn-login` |
| Los elementos de Web Components no están numerados por SoM | Agregar `--shadow-dom` (Angular, Lit, Stencil) |
| `respect.waf_bloquants` aparece en una página que en realidad no está bloqueada | La detección se basa en palabras clave (v1.16.0, refinado v1.17.2); considérelo como una señal, no como un veredicto. Si persiste en una página que ha confirmado que no está bloqueada, agregue `--ignorer-waf` |
| `cliquer_som` hace clic en el elemento incorrecto en una página que mutó entre la captura y el clic | Agregar `--som-rafraichir` (v1.17.0); esto se resuelve mediante un marcador estable en lugar de una reindexación dinámica |
| Un escenario largo de RPA falla a mitad de camino y no desea volver a ejecutar los pasos completados | Agregar `--checkpoint FILE` (v1.17.0); relanza el mismo comando para continuar; el estado del DOM no se conserva, solo la sesión + la posición de la acción |
| Los elementos interactivos dentro de un iframe son invisibles para Diwall | SoM no puede numerar el contenido del iframe (mismo origen o diferente origen); utilice `cliquer_iframe`/`remplir_iframe` (v1.17.0) con un selector CSS explícito, o `iframe_chemin` (v1.18.0) para un iframe anidado dentro de otro |
| Su modelo informa de `"erreur": "guide_non_lu"` / salida 1 en su primera llamada a Diwall | Esperado la primera vez que un modelo utiliza Diwall en esta máquina como este usuario del sistema operativo (v1.18.0); debe leer `docs/GUIDE_LLM.md` y pasar `--guide-version` una vez. Esto es intencional, no un error; indique al modelo que lea la guía en lugar de intentar solucionar el problema |

---

## Desinstalación de Diwall

El script `~/git/Diwall/Diwall/scripts/uninstall.sh` elimina la instalación de forma limpia, en orden inverso a `install.sh`.

```bash
# Observa qué se eliminará, sin hacer nada.
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Desinstalación completa (confirmación interactiva).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# Sin confirmación (pruebas sin confirmar, reinstalaciones repetidas).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme && bash ~/git/Diwall/Diwall/scripts/install.sh
```

¿Qué se elimina:

| Item | Detail |
|---|---|
| `/opt/diwall/` | Código, entorno virtual de Python, configuración |
| `/var/log/diwall/` | Registros de operación |
| `diwall` usuario del sistema | Creado exclusivamente para Diwall |
| `diwall` grupo del sistema | Lo mismo |
| Pertenencia a grupos | Su cuenta se elimina del grupo `diwall` |
| Hook pre-push de git | `core.hooksPath` deshabilitado en el repositorio fuente |

¿Qué nunca debe ser modificado:
- `~/Vaults/` — sus credenciales
- `~/git/Diwall/` — fuentes de Git
- La caché del navegador de Playwright (`~/.cache/ms-playwright/`)

**Capturas de prueba (`/var/log/diwall/preuves/`):** si el directorio contiene
capturas, se conserva por omisión con un aviso. Para eliminarlo:

```bash
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme --purge-preuves
```

---

## Consultando el historial de operaciones

```bash
# Todas las operaciones en un objetivo.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Operaciones de mutación únicamente (clics, entrada de formularios).
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# Desde una fecha.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01
```
