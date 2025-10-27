# Configuración Segura de Credenciales WiFi

## ⚠️ IMPORTANTE: Seguridad de Credenciales

Este proyecto ha sido actualizado para **NO incluir credenciales reales en el código fuente**. Esto previene:
- Exposición de credenciales de red en repositorios públicos
- Cambio accidental de credenciales entre deployments
- Riesgos de seguridad al compartir código

## 📝 Instrucciones de Configuración

### Para el Tag (uwb_tag.ino)

1. **Ve al directorio del firmware del tag:**
   ```bash
   cd firmware/tag/uwb_tag/
   ```

2. **Crea el archivo de configuración desde la plantilla:**
   ```bash
   cp config_wifi.h.example config_wifi.h
   ```

3. **Edita `config_wifi.h` con tus credenciales reales:**
   ```cpp
   #define STA_SSID "Tu_Red_WiFi_Real"
   #define STA_PASS "Tu_Contraseña_Real"
   ```

4. **Complila y sube el firmware:**
   - El archivo `config_wifi.h` NO se versionará en Git (está en .gitignore)
   - Solo existe en tu máquina local con tus credenciales

### Para los Anchors

Los anchors solo necesitan su ID único configurado en `ID_PONG` (1, 2, 3, 4, 5).

## ✅ Verificación

El código compila correctamente con o sin `config_wifi.h`:

- **Con config_wifi.h:** Usa tus credenciales reales desde el archivo externo
- **Sin config_wifi.h:** Usa valores por defecto de ejemplo (solo desarrollo)

## 🔒 Aspectos de Seguridad

1. **`config_wifi.h` está en .gitignore**
   - Nunca se subirá al repositorio
   - Cada desarrollador mantiene sus credenciales locales

2. **`config_wifi.h.example` está versionado**
   - Documenta la estructura necesaria
   - Sirve como plantilla para nuevos desarrolladores

3. **Valores por defecto no funcionales**
   - Si no existe config_wifi.h, el código NO usa credenciales reales
   - Previene accidentalmente usar credenciales de ejemplo en producción

## 🚨 Si Olvidas Crear config_wifi.h

El firmware compilará pero fallará al conectarse a WiFi. Verás en Serial Monitor:
```
WiFi connection FAILED! Status: [código de error]
```

**Solución:** Crea `config_wifi.h` desde el ejemplo con tus credenciales reales.

## 📚 Estructura de Archivos

```
firmware/tag/uwb_tag/
├── uwb_tag.ino                    # Código principal (versionado)
├── config_wifi.h.example          # Plantilla (versionado)
└── config_wifi.h                  # Tus credenciales (NO versionado, .gitignore)
```

---

**Autor:** Actualización de seguridad - 2025  
**Razón:** Prevenir exposición de credenciales WiFi en código público

