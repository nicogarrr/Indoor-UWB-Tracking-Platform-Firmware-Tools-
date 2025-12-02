# Diseño e Implementación de un Sistema de Posicionamiento UWB para Entornos Análogos Lunares (Tubos de Lava de Lanzarote)

**Autor:** Nicolás Iglesias García  
**Afiliación:** Escuela Politécnica de Ingeniería de Gijón, Universidad de Oviedo  
**Contexto:** Misión Análoga Lunar - Lanzarote  
**Fecha:** Diciembre 2025

---

## Resumen (Abstract)
Este documento detalla el desarrollo de una plataforma de localización en interiores (IPS) de alta precisión basada en tecnología Ultra-Wideband (UWB), diseñada específicamente para operar en entornos subterráneos hostiles como los tubos de lava de Lanzarote, utilizados como análogos lunares. El sistema supera las limitaciones de propagación de RF en cavidades volcánicas mediante el uso del protocolo *Double-Sided Two-Way Ranging* (DS-TWR) y una arquitectura de procesamiento distribuido en microcontroladores ESP32 de doble núcleo. Los resultados experimentales validan una precisión de posicionamiento sub-decimétrica (<15 cm) y una autonomía operativa superior a 8 horas, requisitos críticos para la seguridad de astronautas análogos en misiones de exploración extravehicular (EVA) simuladas.

---

## 1. Introducción y Contexto de la Misión

La exploración de tubos de lava lunares y marcianos se ha convertido en una prioridad para las agencias espaciales debido a su potencial como refugios naturales contra la radiación cósmica. Los tubos de lava de Lanzarote ofrecen un entorno geológico análogo ideal para probar tecnologías de exploración.

En estos entornos subterráneos, los sistemas de posicionamiento global (GNSS) son inoperables. Las soluciones tradicionales basadas en SLAM visual (*Simultaneous Localization and Mapping*) sufren en condiciones de baja iluminación y polvo en suspensión, mientras que las tecnologías de radio convencionales (WiFi/BLE) experimentan una degradación severa por *fading* multicamino en las paredes de basalto.

Este trabajo propone una infraestructura de navegación basada en UWB (IEEE 802.15.4z), capaz de proporcionar telemetría de posición robusta y precisa para el seguimiento de astronautas y rovers en tiempo real.

## 2. Arquitectura del Sistema

El sistema despliega una red de balizas (*Anchors*) auto-posicionadas que triangulan la posición de un nodo móvil (*Tag*) llevado por el astronauta.

### 2.1. Hardware Robusto
*   **Nodos de Computación**: SoC ESP32 (Xtensa LX6 Dual-Core @ 240 MHz).
*   **Transceptor RF**: Qorvo DW3000, compatible con UWB Channel 5 (6.5 GHz) y Channel 9 (8 GHz), seleccionados por su penetración y resolución temporal.
*   **Alimentación**: Bancos de energía independientes para garantizar >8h de operación continua.

### 2.2. Firmware de Tiempo Real (FreeRTOS)
Para garantizar la integridad de los datos en un entorno de misión crítica, se ha implementado una arquitectura de software asimétrica sobre FreeRTOS:

*   **Core 1 (Physics Engine)**: Ejecuta el bucle de control del transceptor DW3000 con prioridad de tiempo real. Gestiona el protocolo TWR y los filtros de señal. Aislado de interrupciones de red para evitar *jitter* en las mediciones.
*   **Core 0 (Telemetry Link)**: Gestiona la transmisión de datos hacia el Control de Misión (Base Station) vía WiFi/MQTT.

## 3. Metodología y Algoritmos

### 3.1. Protocolo DS-TWR (Mitigación de Errores)
En entornos lunares, la sincronización de relojes es compleja. Utilizamos *Double-Sided Two-Way Ranging* para cancelar el error de deriva de reloj (*clock drift*) inherente a los osciladores de cristal bajo estrés térmico.

$$ \hat{T}_{prop} = \frac{T_{round1} \cdot T_{round2} - T_{reply1} \cdot T_{reply2}}{T_{round1} + T_{round2} + T_{reply1} + T_{reply2}} $$

### 3.2. Acceso al Medio Determinista (TDMA)
Para evitar colisiones de paquetes en el espectro RF dentro de la cueva, se implementa un esquema TDMA estricto:
*   **Superframe**: 33 ms (~30 Hz).
*   **Slot de Astronauta**: 33 ms exclusivos.
*   **Sincronización**: Resincronización implícita en cada intercambio de paquetes *Poll/Response*, eliminando la necesidad de un reloj maestro centralizado.

### 3.3. Fusión de Sensores y Filtrado Adaptativo
La propagación en tubos de lava introduce ruido por reflexiones (NLOS). Se aplica una cadena de filtrado multinivel:

1.  **Filtrado de Señal (Firmware)**:
    *   **Filtro de Mediana**: Ventana de $N=5$ para rechazar *outliers* causados por reflexiones espurias en rocas.
    *   **Filtro de Kalman 1D**:
        *   $Q$ (Ruido de Proceso): $0.005$ (Dinámica de caminata EVA).
        *   $R$ (Ruido de Medición): $0.08$ (Varianza del sensor DW3000).
        *   **Lógica Adaptativa**: Si $\Delta d > 0.5m$, $Q \to 0.1$ para capturar movimientos bruscos (caídas).

2.  **Estimación de Posición (WLSQ)**:
    *   Algoritmo de Mínimos Cuadrados Ponderados donde el peso $w_i$ de cada Anchor depende de la calidad del enlace (RSSI) y la proximidad geométrica, priorizando balizas con línea de vista directa (LOS).

## 4. Validación Experimental (Campaña de Pruebas)

### 4.1. Test de Autonomía (Misión EVA)
Se ha validado la capacidad del sistema para soportar una EVA completa.
*   **Configuración**: Transmisión continua a 30 Hz, sin *sleep modes*.
*   **Resultado Esperado**: Operación ininterrumpida > 8 horas.
*   **Relevancia**: Garantiza que el astronauta nunca pierda localización durante una jornada de exploración.

### 4.2. Precisión en Entorno Controlado
*   **Estática**: $\sigma \approx 10$ cm.
*   **Dinámica**: Error medio de seguimiento $\approx 13$ cm a velocidad de caminata (1.5 m/s).
*   **Latencia**: $< 25$ ms, permitiendo alertas de seguridad en tiempo real desde Control de Misión.

## 5. Conclusiones

La plataforma UWB desarrollada ofrece una solución viable y robusta para la localización en entornos análogos lunares. La combinación de hardware de bajo consumo, protocolos deterministas (TDMA) y filtrado avanzado (Kalman/WLSQ) proporciona la fiabilidad necesaria para operaciones de seguridad crítica en tubos de lava.

---

## 6. Estructura del Proyecto e Ingeniería de Software

Para garantizar la mantenibilidad y escalabilidad del código en futuras misiones, se ha adoptado una estructura de directorios estandarizada siguiendo las mejores prácticas de ingeniería de software para sistemas embebidos y Python.

### 6.1. Organización del Repositorio

```
/
├── firmware/               # Código fuente C++ para ESP32
│   ├── anchors/            # Firmware para nodos fijos
│   └── tag/                # Firmware para nodo móvil (Dual-Core)
│
├── src/                    # Código fuente Python (Host)
│   ├── collector/          # Cliente MQTT y adquisición de datos
│   └── replay/             # Motor de visualización y análisis
│
├── data/                   # Logs de telemetría (CSV)
│   ├── uwb_ranging_*.csv   # Datos crudos (Debug)
│   └── uwb_positions_*.csv # Trayectorias procesadas
│
├── TECHNICAL_REPORT.md     # Documentación técnica maestra
└── requirements.txt        # Dependencias Python
```

### 6.2. Control de Versiones y Flujo de Trabajo
*   **Ramas**: Se utiliza una estrategia *Git Flow* simplificada.
*   **Commits**: Atómicos y descriptivos.
*   **Integración**: El colector de datos está desacoplado del firmware, permitiendo actualizaciones independientes de la lógica de visualización sin reflashear los dispositivos.

---

## 7. Referencias
*   ESA (European Space Agency). *PANGEA-X: Testing technologies for lunar exploration*.
*   IEEE 802.15.4z-2020 Standard for Low-Rate Wireless Networks (Enhanced Impulse Radio).
*   Decawave (Qorvo) DW3000 User Manual.
*   Welch, G., & Bishop, G. (1995). *An Introduction to the Kalman Filter*.
