# Diwall: Referencia visual compartida entre humanos y modelos de lenguaje grandes (LLM)

> **Para el operador humano:** Diwall le permite delegar la verificación visual a su modelo de lenguaje. Ambos ven la misma captura — ya no tiene que confiar a ciegas en su palabra.
>
> **Para el modelo de lenguaje:** [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md) es su referencia operativa. Empiece por ahí.
> Si es un agente de IA que está descubriendo Diwall, omita la página de inicio con formato y obtenga sus instrucciones directamente: **[https://diwall.davalan.fr/instructions.md](https://diwall.davalan.fr/instructions.md)**

---

## ¿Qué es Diwall?

Diwall crea una **referencia visual compartida** entre un operador humano y un modelo de lenguaje. Le da al LLM la capacidad de **ver interfaces web** y le brinda al operador humano una forma de **delegar la verificación visual** sin perder el control.

Sin Diwall, el operador debe confiar a ciegas en la palabra de su modelo de lenguaje o verificar el resultado por sí mismo. Con Diwall, ambas partes ven la misma captura PNG y el mismo árbol de accesibilidad. La duda desaparece en ambos lados.

```
El LLM actúa → Diwall captura → el LLM ve e informa → el operador verifica desde el mismo estado
```

**Lo que gana el humano:** la delegación del trabajo repetitivo y estresante de verificación visual. En lugar de revisar docenas de páginas después de una implementación, el humano revisa los resultados ya generados por el LLM.

**Lo que gana el modelo:** una percepción real de la interfaz. Sin Diwall, un modelo que desarrolla una aplicación web modifica código pero no puede ver el resultado en un navegador. `lynx` no procesa las interfaces modernas.

### Lo que el modelo realmente recibe

![Captura Set-of-Mark: cada elemento interactivo numerado sobre la página renderizada](../images/som-example-es.png)

Se trata de una captura `--som` real, no de una maqueta. Cada elemento
interactivo está numerado en la página renderizada, y los mismos números
vuelven en el JSON — de modo que `{"type": "cliquer_som", "id": 7}` pulsa
*Sign in*, sin selector que adivinar y sin ambigüedad sobre qué botón se
pretendía. Reprodúzcalo usted mismo — la página es una fixture versionada en
este repositorio, así que obtendrá los mismos números que nosotros:

```bash
cd scenarios/interoperabilite/fixture && python3 -m http.server 8765 &
diwall-shot --url http://127.0.0.1:8765/demo_som_en.html --som --guide-version 1.2
```

`elements_som` regresa con `{"id": 7, "tag": "BUTTON", "texte": "Sign in"}`.

---

## Arquitectura

```
Modelo de lenguaje (el cerebro — bucle ReAct)
        ↓  invoca
  shot.py (las manos — ejecutor Playwright)
        ↓
  Chromium headless → captura PNG
        ↓
  El modelo de lenguaje lee el PNG directamente (multimodal)
```

`shot.py` no tiene inteligencia. Ejecuta instrucciones y devuelve el estado.
El modelo de lenguaje decide qué hacer a continuación.

---

## Capacidades

| Característica | Descripción |
|---|---|
| **Captura** | Captura una captura de pantalla de cualquier página web |
| **Acciones** | Rellena formularios, haz clic, navega |
| **Conjunto de marcas (SoM)** | Numera todos los elementos interactivos para clics precisos en el DOM |
| **Instantánea de accesibilidad** | Extrae la estructura semántica de la página (árbol A11y) |
| **Persistencia de sesión** | Mantiene el estado de inicio de sesión a través de bucles ReAct de varios pasos |
| **Escenarios de RPA** | Ejecuta secuencias de acciones desde archivos JSON |
| **Monitoreo visual** | Detecta si una página ha cambiado desde la última referencia |
| **Diferencia de píxeles** | Diferencia cuantitativa y determinista con respecto a una referencia almacenada (v1.2) |
| **Resolución de credenciales** | Inyección segura de credenciales; nunca en texto plano, nunca en la línea de comandos |
| **Directorio cifrado** | Volumen gocryptfs — `SecretsFermesError` (salida 42) si no está montado (v1.5) |
| **Desplazamiento** | Acción `defiler` — desplazamiento relativo de píxeles o por selector CSS `scrollIntoView` (v1.6) |
| **Advertencia fuera de pantalla** | Cuenta `som_hors_viewport` en JSON cuando existen elementos interactivos debajo del pliegue (v1.6) |
| **Memoria procedimental** | Las ejecuciones exitosas se almacenan como habilidades reproducibles a través de `journal.py --exporter-skill` (v1.6) |
| **TOTP 2FA** | Códigos de Google Authenticator / Authy generados en tiempo de ejecución desde una semilla almacenada (v1.6) |
| **MFA asíncrono a través de ntfy** | Códigos 2FA de SMS/correo electrónico recibidos de forma asíncrona a través de la notificación push de ntfy (v1.6) |
| **Perfil de operador** | Perfil YAML para eliminar confirmaciones administrativas repetitivas (v1.3) |
| **Trazabilidad del modelo** | Cada ejecución registra qué modelos se llamaron, incluido el resumen de Ollama (v1.3) |
| **Registro de operaciones** | Registro persistente y de solo escritura de todas las ejecuciones: quién hizo qué, dónde, cuándo (v1.4) |
| **Recorrido del DOM sombreado** | Números `--shadow-dom` de elementos interactivos dentro de Shadow Roots abiertos; Angular, Lit, Stencil, FAST (v1.13.0) |
| **Navegación Respetuosa** | `--stealth` (elimina los marcadores automáticos del modo headless), retrasos de cortesía y límites estrictos (`min_action_delay_ms`, `max_pages_par_run`, `max_actions_par_run`), métricas de impacto (`respect`) informadas en cada ejecución (v1.15.0) |
| **Veredicto determinista** | El objeto `etat` (`pret_a_agir`, `niveau_confiance`, `raisons`) sintetiza señales de autenticación, deriva de sesión y fricción en una sola lectura (v1.16.0) |
| **Identidad de ejecución unificada** | `operation_id` aísla los archivos temporales de cada ejecución y los vincula a su entrada del registro de operaciones (v1.16.0) |
| **Señal pasiva de WAF** | `respect.waf_bloquants` marca un posible bloqueo (HTTP 403/429 o palabras clave conocidas) como una señal no fatal, nunca como una excepción (v1.16.0) |
| **No regresión estructural** | `--replay-verifier` compara el estado HTTP, las estadísticas del DOM y los resultados de `evaluer` con una referencia guardada; sin píxeles, sin modelo de visión (v1.17.0) |
| **Puntos de control del escenario** | `--checkpoint` reanuda un escenario largo después de un fallo a la mitad sin reproducir las acciones completadas (v1.17.0) |
| **Identidad SoM estable** | `--som-rafraichir` resuelve los identificadores `cliquer_som`/`remplir_som` mediante un marcador del DOM en lugar de una reindexación en vivo, evitando el cambio silencioso de destino en páginas altamente dinámicas (v1.17.0) |
| **Iframes entre orígenes** | Los elementos de destino `cliquer_iframe` / `remplir_iframe` dentro de iframes del mismo origen o de diferentes orígenes a través de la API de marco nativa de Playwright (v1.17.0) |
| **Iframes anidados** | Descenso `iframe_chemin` (matriz) iframe-dentro-de-iframe, mutuamente excluyente con `iframe_selecteur` (v1.18.0) |
| **Bloqueo de guía-lectura** | `shot.py`/`rpa.py`/`watch.py` se niega a ejecutarse sin una prueba de que se leyó `docs/GUIDE_LLM.md` — un marcador local lo persiste por máquina/usuario (v1.18.0) |
| **Consejos de configuración** | `mode_conseille` recomienda `--mode`/`--shadow-dom`/`--som-rafraichir` a partir de ejecuciones de diagnóstico reales anteriores en el mismo host; nunca una conjetura (v1.18.0) |
| **Trazabilidad de escenarios encadenados** | `chainage` registra el árbol de llamadas ordenado de escenarios encadenados a través de `declencher_scenario`, que se muestra en el registro de operaciones (v1.19.0) |
| **Temporización por acción** | `latences_actions` informa la latencia de despacho para cada acción ejecutada, siempre presente (v1.20.0) |
| **Vista de registro solo de errores** | `journal.py --erreurs` filtra el registro de operaciones para mostrar solo las ejecuciones fallidas (v1.20.0) |
| **Autenticación HTTP básica** | `--http-credentials` resuelve la autenticación Básica a nivel de red (RFC 7617) desde el archivo de credenciales, con ámbito del origen del objetivo; distinto y adicional a la autenticación basada en formularios (v1.21.0) |
| **Escalado de clics de JavaScript** | `repli_js` en `cliquer` reintenta un clic nativo fallido mediante JS, informado solo en la boussole cuando realmente se ejecutó (v1.22.0) |
| **Objetivos que nunca están inactivos** | `--wait-until load\|domcontentloaded` alcanza páginas que realizan sondeos continuos y nunca permanecen sin actividad de red, donde ningún valor de `--timeout` sería suficiente (v1.22.0) |

---

## Requisitos

| Componente | Versión / Notas |
|---|---|
| **Sistema operativo** | Debian 13 Trixie (Linux, puede funcionar en macOS — no probado en Windows) |
| **Servidor de visualización** | Wayland (Playwright se ejecuta en este ecosistema) |
| **Python** | 3.11+ en un entorno virtual aislado (PEP 668 — pip del sistema bloqueado en Debian 13) |
| **Playwright** | 1.50+ (instalado en el entorno virtual) |
| **playwright-stealth** | 2.0+ — requerido para `--stealth` (v1.15.0). Incompatible con la API de la versión 1.x |
| **Chromium** | Sin interfaz gráfica, instalado a través de `playwright install chromium` |
| **Ollama** | Modelos de visión locales para `cliquer_visuel` y `watch.py` |
| **GPU** | Recomendado: NVIDIA RTX 3060 de 12 GB de VRAM o equivalente (para los modelos qwen3-vl de Ollama) |

---

## Instalación

Dos canales, **exclusivos entre sí en una misma máquina**. Elija el paquete de Debian a menos que tenga la intención de modificar el código propio de Diwall.

### Paquete de Debian: el camino más sencillo

Descargue el recurso `.deb` de la
[última versión](https://github.com/RonanDavalan/diwall/releases) — nombre del archivo
`diwall_<version>-1_all.deb` — luego:

```bash
sudo apt install ./diwall_1.23.0-1_all.deb
```

Crea el usuario del sistema `diwall`, el entorno virtual y
`/opt/diwall/`, instala los seis comandos `diwall-*` en su `PATH`, y proporciona
la página de manual:

```bash
man diwall              # covers all six commands
diwall-shot --version
```

La configuración se encuentra en `/etc/diwall/diwall.conf`; una muestra comentada está instalada junto a ella como `diwall-sample.conf`. Referencia completa de comandos: sección 1a, `docs/MANUEL.md`.

La actualización es `sudo apt install ./diwall_<newer>-1_all.deb` y su configuración se conserva. La eliminación es `sudo apt remove diwall`, o `sudo apt purge diwall` para eliminar también la configuración.

### Desde la fuente: para modificar Diwall en sí mismo

Si pretende modificar el código de Diwall, instale desde el repositorio: así
las fuentes quedan donde `deploy.sh` puede enviar sus cambios a
`/opt/diwall/`. El procedimiento de seis pasos está en
[`docs/MANUEL.md`](MANUEL.md) sección 1b, junto a las órdenes que
ejecutará después.

## Desinstalación

Instalado desde el paquete de Debian:

```bash
sudo apt remove diwall     # keeps /etc/diwall/diwall.conf
sudo apt purge diwall      # removes the configuration as well
```

Instalado desde el código fuente:

```bash
# Vista previa de lo que se eliminará (sin modificar nada)
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Desinstalación completa con confirmación interactiva.
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# No interactivo (pruebas de integración continua, reinstalaciones).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme
```

Elimina: `/opt/diwall/`, `/var/log/diwall/`, usuario del sistema `diwall`, grupo del sistema `diwall`, pertenencia al grupo de operadores, "git pre-push" hook.

No se ha modificado: `~/Vaults/` (sus credenciales), el repositorio en sí mismo, la caché del navegador de Playwright.

Si `/var/log/diwall/preuves/` contiene capturas, se conservan por omisión. Añada `--purge-preuves` para eliminarlas.

---

## Uso (por parte del modelo de lenguaje)

### Captura simple

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://your-app.local/ --som --a11y
```

### Bucle de ReAct (navegación en múltiples pasos)

```bash
# Paso 1: navegar y observar.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://your-app.local/ \
  --sauver-session /tmp/diwall/session.json --som

# Paso 2: Actuar según lo observado.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session /tmp/diwall/session.json \
  --action '{"type":"cliquer_som","id":2}' \
  --sauver-session /tmp/diwall/session.json --som
```

### Escenario RPA

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my_scenario.json --som
```

Referencia completa para los modelos: [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md)

---

## Credenciales

Las credenciales se almacenan en archivos JSON, uno por dominio, **nunca en el código ni en los archivos de escenarios**:

```
~/Vaults/Diwall/
├── my-app.local.json        → {"password": "...", "username": "admin"}
└── other-service.com.json   → {"password": "...", "api_key": "..."}
```

En un escenario o acción: `"valeur": "depuis_secrets", "secret_cle": "password"` — Diwall lee la credencial en tiempo de ejecución desde el directorio de credenciales.

La ruta es configurable a través de `/opt/diwall/diwall.conf` o la variable de entorno `DIWALL_SECRETS_DIR`.

**Recomendación:** proteja `~/Vaults/Diwall/` con `chmod 700` y encripte con `gocryptfs` (consulte `~/git/Diwall/Diwall/scripts/configurer-repertoire-chiffre.sh --gocryptfs`). El directorio cifrado está completamente soportado desde la versión v1.5.0; si se inicializa pero no se monta, Diwall devuelve una estructura `SecretsFermesError` (código de salida 42) en lugar de fallar silenciosamente.

---

## Seguridad

### Almacenamiento de capturas

Por defecto, las capturas se almacenan en `/tmp/diwall/` con permisos `700` (solo el propietario).
No cambie `--output-dir` a una ubicación compartida (`/tmp/`, `~/Desktop/`, etc.)—las capturas pueden contener datos de interfaz confidenciales.

### Modelos locales versus modelos en la nube

Cuando Diwall se utiliza con un LLM basado en la nube (API de Claude, OpenAI, etc.), las capturas PNG se transmiten a servidores externos. Esto es responsabilidad del usuario. Para interfaces que contienen datos privados (credenciales, información del cliente, claves privadas), utilice únicamente modelos Ollama locales.

### Directorio de credenciales

El directorio de credenciales, donde sea que hayas apuntado, por ejemplo, `secrets_dir` —como en `~/Vaults/Diwall/`— contiene credenciales en texto plano JSON cuando está desmontado. Protéjelo:

```bash
chmod 700 ~/Vaults/Diwall/
```

El soporte para sistemas de archivos cifrados (`gocryptfs`) ha sido compatible por completo desde la versión 1.5.0;
consulte "Credenciales" arriba y `~/git/Diwall/Diwall/scripts/configurer-repertoire-chiffre.sh`.

---

## Documentación en otros idiomas (v1.23.0)

El inglés es la versión de referencia y no se mueve. Las traducciones de los
documentos dirigidos a personas (este README, `docs/GUIDE.md`,
`docs/MANUEL.md`, `docs/CHEAT_SHEET.md` y la página de manual) viven en
`docs/fr/`, `docs/de/` y `docs/es/` — un directorio por idioma, junto a los
originales en inglés.

Las guías del LLM (`docs/GUIDE_LLM.md` y sus tres avisos) están solo en inglés,
deliberadamente. Están protegidas por el "guide-lock": una traducción cuya
número de versión se resincroniza mecánicamente con contenido obsoleto permitiría
que un agente supere la protección habiendo leído instrucciones obsoletas; este es exactamente
el fallo que la protección existe para evitar. Un modelo lee inglés de forma nativa, por lo tanto,
la ventaja es nula y el riesgo es real.

Se crea un único archivo PDF de referencia por idioma a partir de estas fuentes, en un orden
declarado una sola vez y compartido por todos los idiomas. Los archivos PDF se publican en el
sitio web en lugar de almacenarse aquí; son artefactos generados, y un repositorio
no es un canal de distribución para binarios:
<https://diwall.davalan.fr/en/guides/downloads/>

La propia cadena de traducción y de generación de PDF no está en este
repositorio. Produce la documentación; no forma parte de Diwall — necesita
`pandoc`, un motor LaTeX y una instancia local de Ollama, ninguno de los cuales
es una dependencia de Diwall ni aparece en `requirements.txt`. El markdown
traducido es el entregable; la máquina que lo produce es herramienta de
mantenedor.

---

## Para los modelos de lenguaje (LLM) que descubren Diwall

Si usted es un modelo de lenguaje que está leyendo este archivo README: consulte [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md) para la referencia técnica completa: patrones de invocación, uso de SoM, integración de credenciales, reglas de navegación de SPA y especificaciones del modelo Ollama.

---

## Créditos

Este proyecto fue desarrollado utilizando un **modelo de colaboración humano-LLM asimétrico**.
Los roles están documentados formalmente para reflejar el trabajo real realizado.

**Arquitecto y Árbitro:** Ronan Davalan
Visión del producto, requisitos de seguridad, dirección del proyecto, validación y pruebas.
Todas las decisiones arquitectónicas son validadas por él.

**Ingeniero de Sistemas y Desarrollador Líder:** Claude Code (Anthropic)
Implementación del patrón ReAct, scripts en Python/Bash, gestión compleja de estados,
inyección de SoM, persistencia de sesiones. Autor principal del código fuente.

**Sintetizador y Asesor Estratégico:** Gemini (Google)
Análisis arquitectónico independiente, resolución lógica de conflictos,
optimización de flujos de trabajo, validación cruzada de decisiones técnicas.

**Modelos de percepción (Ollama, local):**
- `qwen3-vl:2b` (Alibaba) — localización por clic y comparación semántica, ~9–19 segundos (predeterminado desde la versión 1.3.1)
- `qwen3-vl:8b` (Alibaba) — alternativa robusta, ~114 segundos

**Operadores de mantenimiento (a través de OpenCode):**
- Big Pickle: limpieza semántica exhaustiva de la documentación.
- MiniMax: verificación y confirmaciones.
- DeepSeek V4 Flash: ponerse al día con las confirmaciones omitidas.
- Qwen3.6 Plus: pruebas de roles, incluyendo la documentación de una tarea real desde cero como un modelo sin información previa, lo que reveló dos lagunas en la documentación.

---

## Licencia

MIT — consultar el archivo `LICENSE`.

*Desarrollado en Debian 13 Trixie · Wayland · AMD Ryzen 9 3950X · NVIDIA RTX 3060*
