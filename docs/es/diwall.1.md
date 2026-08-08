% DIWALL(1) | Comandos de Diwall
%
% Julio de 2026

# NOMBRE

diwall - conjunto de herramientas para la percepción visual y la automatización robótica de procesos (RPA) para agentes de modelos de lenguaje grandes (LLM)

# SINOPSIS

**diwall-shot** \[*opciones*\] **--url** *URL*

**diwall-rpa** \[*opciones*\] **--scenario** *ARCHIVO*

**diwall-watch** \[*opciones*\]

**diwall-monter-secrets** \[*opciones*\]

**diwall-demonter-secrets** \[*opciones*\]

**diwall-monitor-verifier** **--scenario** *ARCHIVO* **--reference** *ARCHIVO*

# DESCRIPCIÓN

Diwall proporciona a un agente de LLM "ojos" y "manos" en interfaces web que de otro modo no podría ver ni operar: capturas de pantalla, anotaciones tipo "Set-of-Mark" y un árbol de accesibilidad en un lado, y acciones impulsadas por Playwright en el otro. Cada comando imprime un único objeto JSON en la salida estándar, diseñado para ser leído por un programa y no por un humano.

Este paquete instala seis comandos bajo **/usr/bin**. Son envoltorios ligeros alrededor de los puntos de entrada de Python en **/opt/diwall**, y leen su configuración desde **/etc/diwall/diwall.conf** en lugar del **/opt/diwall/diwall.conf** utilizado por el canal de instalación de git-clone.

Hay una página de manual para los seis comandos, intencionalmente: una sola página no puede perder su coherencia interna. Para obtener la lista exhaustiva de opciones de cualquier comando, ejecútelo con **--help**; esa salida siempre tiene prioridad sobre esta página.

# COMANDOS

**diwall-shot**
: Captura una página y devuelve un JSON que la describe. Con **--som**, los elementos interactivos se numeran en la captura de pantalla para que un agente pueda referirse a ellos por índice; con **--a11y**, se incluye el árbol de accesibilidad. Las acciones se pueden ejecutar en la misma sesión del navegador mediante **--actions**.

**diwall-rpa**
: Ejecuta un archivo de escenario (JSON o YAML) que describe una secuencia de acciones,
y devuelve una línea en formato JSON. Este es el comando a utilizar para cualquier
operación repetible, y es el único que evalúa las aserciones del escenario.

**diwall-watch**
: Monitoreo visual. Guarda una imagen de referencia de una página y luego compara capturas posteriores con ella: diferencia de píxeles localmente o una descripción proporcionada por un modelo de visión local. Se utiliza para detectar regresiones visuales sin la intervención humana.

**diwall-monter-secrets**, **diwall-demonter-secrets**
: Monta y desmonta el directorio de credenciales cifrado con gocryptfs. Diwall se niega a resolver cualquier credencial mientras está cerrado, saliendo con el código de estado 42 en lugar de recurrir a una alternativa menos segura.

**diwall-monitor-verifier**
: Ejecuta una única pasada de verificación estructural para un escenario, comparándola con una referencia guardada, y sale con un código distinto de cero si hay divergencias. Está diseñado para ser ejecutado por cron o un temporizador systemd; no contiene ningún bucle propio.

# OPCIONES COMUNES

Las opciones que se muestran a continuación son comunes a **diwall-shot** y **diwall-rpa**, a menos que se indique lo contrario. Esta es una selección, no la lista completa.

**--guide-version** *X.Y*
: Es obligatorio proporcionar una prueba de que **/opt/diwall/docs/GUIDE_LLM.md** fue leído. Sin ella
— y sin un marcador local aún válido — el comando se niega a ejecutarse y
sale con código 1. El valor esperado es el comentario "notice-version" en la línea 3 de esa
guía. Este es el único lugar donde Diwall no es opcional.

**--version**
: Imprime la versión instalada en formato JSON y sal de la aplicación, sin iniciar un navegador.
Es diferente de **--guide-version**; los dos números no están relacionados.

**--mode** *fast*|*full*
: *fast* es **--no-capture --a11y**: sin PNG, aproximadamente dos segundos más rápido,
suficiente para leer el estado. *full* es el valor predeterminado y captura la renderización.

**--som**
: Numera los elementos interactivos visibles en la captura, para que las acciones puedan
dirigirse a ellos por índice en lugar de por selector CSS.

**--wait-until** *networkidle*|*load*|*domcontentloaded*
: Cuándo se considera que la navegación inicial ha finalizado. El valor predeterminado es
*networkidle*, que espera 500 ms de inactividad en la red y es adecuado para la mayoría de
los casos. Una página que realiza sondeos continuos nunca permanece inactiva; use *load* en ese caso;
establecer **--timeout** no ayudará, ya que la página nunca finalizará.
**diwall-shot** solo.

**--timeout** *MS*
: Tiempo de espera por operación en milisegundos (por defecto 10000). Distinto de
**--screenshot-timeout** (por defecto 120000), que cubre únicamente la captura de pantalla.

**--stealth**
: Elimine los marcadores automáticos que identifican un navegador sin interfaz gráfica. No
cambia la dirección IP del operador ni falsifica una identidad; el objetivo
es el trato equitativo, no el disfraz.

**--secrets** *ARCHIVO*
: Resuelve las credenciales desde un archivo JSON explícito dentro de un directorio montado, en lugar de la búsqueda predeterminada basada en el host.

**--no-evaluer**
: Rechazar la acción de **evaluar** para toda la ejecución; el código JavaScript arbitrario no se ejecuta en la página de destino.

**--no-filtre-evaluer**
: Desactivar la neutralización de la salida estándar (stdout) de los valores devueltos por **evaluer**, las URLs y los mensajes de error; solo para ejecuciones de depuración explícitas. La neutralización está activada por defecto; cuando se desactiva, `boussole.filtre_evaluer_actif: false` se establece en la salida para que el operador pueda auditarla directamente desde el JSON.

# ARCHIVOS

**/etc/diwall/diwall.conf**
: Configuración leída por los comandos empaquetados. Creada por el operador, nunca
generada automáticamente. La variable de entorno **DIWALL_CONF** anula
esta ruta, que es como varios proyectos mantienen configuraciones separadas en una
misma máquina.

**/opt/diwall/**
: Código de la aplicación, el entorno virtual de Python y la documentación a la que hacen referencia los comandos mismos.

**/opt/diwall/docs/GUIDE_LLM.md**
: El punto de entrada que un agente debe leer.  **MANUEL.md** en el mismo
directorio contiene los comandos exactos con las rutas reales.

**/var/log/diwall/**
: Registro de operaciones de solo añadido. Se conserva con **apt remove**, se elimina con **apt purge**.

**/tmp/diwall/**
: Archivos PNG capturados, eliminados al reiniciar.

# ESTADO DE SALIDA

**0**
: La ejecución se completó. Tenga en cuenta que un error HTTP 404 o 403 en el objetivo se reporta
en el formato JSON, no como una falla del comando.

**1**
: El proceso falló, o la verificación previa no se cumplió (*guide_non_lu*) .

**2**
: Argumentos incompatibles, rechazados antes de que se iniciara cualquier navegador.

**42**
: El directorio de credenciales está cerrado. Móntele con **diwall-monter-secrets**.

**43**
: No se pudo verificar la integridad de las credenciales.

# EJEMPLOS

Captura una página con elementos numerados y el árbol de accesibilidad:

    diwall-shot --url https://example.com --som --a11y --guide-version 1.2

Lee solo el estado de una página, sin generar una imagen:

    diwall-shot --url https://example.com --mode fast --guide-version 1.2

Acceda a un panel de administración que actualice las estadísticas continuamente:

    diwall-shot --url http://target.local/ --wait-until load --som

Ejecuta un escenario con las credenciales de un archivo específico:

    diwall-rpa --scenario ./login.json --secrets ~/Vaults/project/creds.json

Verifica que una página no haya retrocedido estructuralmente:

    diwall-monitor-verifier --scenario ./page.json --reference ./page.ref.json

# VÉASE TAMBIÉN

La documentación completa se instala con el paquete:
**/opt/diwall/docs/MANUEL.md** para el manual del operador,
**/opt/diwall/docs/GUIDE_LLM.md** para la guía dirigida a los agentes,
**/opt/diwall/docs/FAQ_LLM.md** para las respuestas organizadas por versión y funcionalidad.

La página de inicio del proyecto se puede encontrar mediante el comando **apt show diwall**.
