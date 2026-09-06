# HyperOS Bootloader Quota Sniper

[English](README.md) | [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()

Sniper de red de alta frecuencia universal y multiplataforma para asegurar cupos diarios de desbloqueo de bootloader en Xiaomi HyperOS (`apply/bl-auth`).

---

## Comparativa Arquitectonica

| Caracteristica | Scripts Clasicos por ADB | Herramientas Legacy de Bypass | HyperOS BL Sniper (Este Proyecto) |
| :--- | :--- | :--- | :--- |
| **Autenticacion** | Extraccion manual de cookies | Endpoints obsoletos (30001) | **Flujo Oficial por QR + Auto-Renovacion con passToken** |
| **Modo de Disparo** | Disparo unico a ciegas | Intentos de spoofing (parchados) | **Rafaga Intercalada Double-Tap con Sockets Duales** |
| **Plataforma** | Requiere celular USB conectado | Exclusivo de Windows | **Windows, macOS y Linux (CLI / Headless / VPS)** |
| **Capa de Red** | Handshake TLS en frio (~500ms lag)| HTTP plano sin cifrar | **Precalentamiento Dual TLS Keep-Alive en Paralelo** |
| **Compensacion de Transito** | Estimacion estatica | Ninguna | **Perfilado Pasivo TCP de Capa 4 (`RTT / 2`)** |
| **Precision de Reloj** | Reloj del sistema operativo | Ninguna | **Multi-Servidor NTP + Bucle de Busy-Wait al Microsegundo** |
| **Correccion de Sesgo** | Ninguna | Ninguna | **Analisis de Cabecera Date HTTP + Consenso Comunitario** |
| **Accion Post-Aprobacion** | Ninguna | Ninguna | **Desprogramacion Automatica + Guia Clara de Siguientes Pasos** |

---

## Tecnologias Centrales

### 1. Rafaga Intercalada Double-Tap con Sockets Duales
La ventana de apertura de cupos de Xiaomi dura apenas entre 50 y 150 milisegundos. Para eliminar el riesgo de disparar unos milisegundos temprano y evitar que la competencia gane el cupo, el sniper precalienta dos conexiones TLS independientes en paralelo:
* **Socket A (Primario):** Enviado a `target_epoch - one_way_transit - bias` con payload `is_retry: false`.
* **Socket B (Paracaidas):** Enviado exactamente `+100ms` despues con payload `is_retry: true`.
Si el socket primario llega una fraccion de segundo antes de medianoche, el secundario entra en la ventana activa del servidor.

### 2. Ciclo de Vida Autonomo del Token (Recuperacion con `passToken`)
Al iniciar sesion mediante codigo QR, la herramienta almacena de forma segura `userId`, `new_bbs_serviceToken` y el `passToken` permanente de Xiaomi. Si el token de servicio expira (`codigo: 100004`), el sniper contacta de manera reactiva y transparente a `account.xiaomi.com/pass/serviceLogin` para obtener un nuevo token de sesion sin interrumpir la ejecucion ni requerir intervencion del usuario.

### 3. Red de Inteligencia Colectiva
Los nodos que ejecutan el script en el mundo reportan metricas anonimas de tiempo de transito (RTT, sesgo aplicado, respuesta del servidor) a un endpoint edge aislado. Un motor de consenso diario (clustering 1D DBSCAN, mediana truncada y filtros Anti-Sybil) calcula el sesgo ganador y publica `community_bias.json` en GitHub. Los clientes sincronizan este sesgo optimo antes del disparo. Cero datos personales, credenciales o identificadores de hardware son transmitidos.

---

## Inicio Rapido

### 1. Clonar e Instalar Dependencias
```bash
git clone https://github.com/JoshRob297/hyperos-bl-sniper.git
cd hyperos-bl-sniper
pip install -r requirements.txt
```

### 2. Ejecucion Autonoma en Un Solo Comando (Recomendado)
Ejecuta un unico comando que verifica autenticacion, programa la tarea diaria y entra al bucle de disparo:
```bash
python cli.py start
```
Si no existe sesion previa, el asistente interactivo te guiara para iniciar sesion. Una vez guardada, valida la elegibilidad de tu cuenta, programa la tarea diaria en el sistema operativo y espera en modo Deep Sleep hasta la hora de apertura del cupo.

---

## Comandos Detallados

### Inicio de Sesion con Asistente Oficial
Compatible con autorizacion en navegador, credenciales en terminal o inyeccion manual:
```bash
python cli.py login
```
* **Opcion 1 (Asistente oficial via `migate`):** Abre la pagina oficial de Xiaomi en navegador (Browser), permite ingresar credenciales/OTP en consola (Terminal), o muestra codigo QR.
* **Opcion 2 (Inyeccion manual de cookies):** Pega directamente tu `userId` y `new_bbs_serviceToken` copiados desde [c.mi.com](https://c.mi.com) con las herramientas de desarrollador (F12). Tambien accesible mediante `python cli.py login --manual`.

### Comprobar Sesion y Estado de Cuenta
```bash
python cli.py status
```
Muestra la validez del token, estado de la tarea programada en el sistema operativo y permisos oficiales (`is_pass`, fecha limite y periodos de penalizacion activos).

### Activar Disparo Automatico Diario (Multiplataforma)
Registra automaticamente una tarea en segundo plano en tu sistema operativo (Crontab en Linux, `launchd` en macOS, o Programador de Tareas en Windows) configurada para despertar 2 minutos antes de medianoche hora de Beijing (00:00:00 GMT+8):
```bash
python cli.py schedule
```
Para desactivar la tarea programada en cualquier momento:
```bash
python cli.py unschedule
```

---

## Seguridad de Cuenta y Reglas Anti-Baneo
El sistema de control de riesgo de Xiaomi es sensible a cambios bruscos de red e IP durante la solicitud de cupo:
* **Evita VPNs / Proxies:** Ejecuta el bot directamente sobre la conexion nativa de tu proveedor de Internet (fibra residencial / IP real). Los saltos de VPN aumentan la latencia y disparan bloqueos temporales (`Account Error / codigo 6`).
* **No cambies de red:** Nunca alternes entre Wi-Fi y datos moviles cerca de la hora de reinicio. Manten una sola conexion estable.
* **Evita DNS personalizados:** Utiliza el DNS de tu ISP o resolvedores locales estandar para evitar desvios de enrutamiento detectados por Xiaomi.
* **Una sola instancia por cuenta:** No intentes solicitar cupo con la misma cuenta en multiples terminales simultaneamente.

---

## Referencia de Codigos de Respuesta

### Codigos de Solicitud de Cupo (`apply/bl-auth`)

| Codigo | Estado | Significado |
| :---: | :--- | :--- |
| **`1`** | `[APROBADA]` | Cupo otorgado. Permiso de desbloqueo de bootloader activo hasta fecha limite. |
| **`2`** | `[ERROR_CUENTA]` | Error de cuenta o restriccion temporal. Intentar despues de la fecha limite. |
| **`3`** | `[AGOTADO]` | Cupo diario agotado antes de la llegada de la solicitud. Proxima apertura a las 00:00 GMT+8. |
| **`4`** | `[FALLIDA]` | Solicitud fallida. Intentar en la siguiente ventana diaria. |
| **`5`** | `[ESPERA]` | Limite de tasa temporal activado. Esperar un minuto antes de reintentar. |
| **`6`** | `[CONTROL_RIESGO]` | Control de riesgo activado en el servidor. Evitar sondeos agresivos. |

### Codigos de Estado y Elegibilidad (`bl-switch/state`)

| Codigo (`is_pass` / `button_state`) | Estado | Significado |
| :---: | :--- | :--- |
| `is_pass == 1` | `[APROBADA]` | Permiso ya activo. No es necesario disparar. |
| `is_pass == 4`, `btn == 1` | `[READY]` | Cuenta elegible. Lista para disparar a las 00:00 GMT+8. |
| `is_pass == 4`, `btn == 2` | `[BLOQUEADA]` | Enfriamiento temporal activo hasta fecha limite. |
| `is_pass == 4`, `btn == 3` | `[ACCOUNT_TOO_NEW]`| Cuenta creada hace menos de 30 dias. Aun no elegible. |

---

## Modo Standalone / Suspension Profunda (Deep Sleep)
Si ejecutas el bot manualmente en un VPS, servidor o contenedor:
```bash
python cli.py run
```
* **Proteccion contra ejecucion temprana:** Si se ejecuta con mas de 15 minutos de anticipacion, el bot entra en **Modo Deep Sleep**, consumiendo cero CPU y cero red hasta T-15 minutos.
* **T-15m:** Despierta, resincroniza desfase NTP, perfila latencia pasiva TCP y descarga el sesgo comunitario.
* **T-12s:** Precalienta ambos sockets TLS hacia los clusters edge de Singapur.
* **T-0:** Entra en bucle busy-wait al microsegundo y dispara la rafaga Double-Tap.
* **T+2s:** Evalua la respuesta del servidor, guarda la calibracion adaptativa, despacha notificaciones y desprograma la tarea si fue aprobado.

---

## Configuracion (`config.json`)

```json
{
  "auth": {
    "userId": "1234567890",
    "cUserId": "h4sh3d_s3cr3t",
    "new_bbs_serviceToken": "token_aqui",
    "passToken": "token_permanente_aqui",
    "deviceId": "STABLE_ANONYMOUS_ID",
    "versionCode": "500439",
    "versionName": "5.4.39"
  },
  "sniper": {
    "mode": "double_tap",
    "tap_interval_ms": 100.0
  },
  "calibration": {
    "auto_tune": true,
    "bias_ms": 0.0
  },
  "community": {
    "share_metrics": true,
    "fetch_global_bias": true
  },
  "language": "es",
  "telegram": {
    "bot_token": "",
    "chat_id": ""
  }
}
```

---

## Pasos Criticos al Ser Aprobado
Una vez que el sniper obtiene el cupo, imprime una guia clara en consola y envia la notificacion:
1. Inserta una tarjeta SIM con **datos moviles activos** en tu celular Xiaomi.
2. **Apaga el Wi-Fi** (la vinculacion falla obligatoriamente bajo conexiones Wi-Fi).
3. Ve a: **Ajustes -> Ajustes adicionales -> Opciones de desarrollador -> Estado de Mi Unlock**.
4. Toca en **Agregar cuenta y dispositivo**.
5. Comenzara tu periodo de espera oficial (ejemplo: 72 horas). Una vez transcurrido, conecta por USB y desbloquea en PC.

---

## Suite de Pruebas
Ejecuta la suite integrada de pruebas unitarias y de regresion (26 tests que cubren criptografia, zonas horarias, auto-renovacion de tokens, sanitizacion de telemetria y formato Clean UI):
```bash
python test_suite.py
```

---

## Creditos y Reconocimientos
* **[offici5l / MiForge](https://github.com/offici5l/migate):** Autor de la libreria `migate`, pasarela de autenticacion oficial de Xiaomi para Python utilizada en este proyecto para el inicio de sesion seguro, asi como por la referencia de codigos de respuesta de `MiCommunityTool`.

---

## Licencia
Este proyecto esta licenciado bajo la [Licencia MIT](LICENSE).
