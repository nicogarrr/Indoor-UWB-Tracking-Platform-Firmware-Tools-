# Anchor Unificado - Explicación

## ⚠️ IMPORTANTE: Este archivo es OPCIONAL

**NO reemplaza** los archivos `anchor_1.ino`, `anchor_2.ino`, etc. que ya funcionan correctamente.

## ¿Por qué existe `anchor_unified.ino`?

Es una **refactorización experimental** para eliminar duplicación de código entre los 5 archivos de anclas.

### Problema Actual:
- `anchor_1.ino`, `anchor_2.ino`, ..., `anchor_5.ino` son **idénticos** excepto por:
  - Línea 4: `static int ID_PONG = 1;` vs `ID_PONG = 2;` etc.

### Solución Propuesta:
- **Un único archivo** `anchor_unified.ino` que configura el ID dinámicamente.

## ¿De dónde viene el código?

`anchor_unified.ino` es **exactamente** `anchor_1.ino` (268 líneas) + funciones adicionales:
- `loadAnchorID()` - Carga ID desde NVS o usa default
- `saveAnchorID(int id)` - Guarda ID en NVS
- `#include <Preferences.h>` - Librería ESP32 para NVS

**La lógica de comunicación DW3000 es 100% idéntica.**

## ¿Cómo usar `anchor_unified.ino`?

### Opción 1: Compile-time (como los originales)
```
1. Abre anchor_unified.ino en Arduino IDE
2. Tools > Board Settings > Compiler flags
3. Añade: -DDEFAULT_ANCHOR_ID=1
4. Compila y sube
```

Para anchor 2, repite con `-DDEFAULT_ANCHOR_ID=2`, etc.

### Opción 2: NVS (nuevo - persistente)
```
1. Sube anchor_unified.ino una vez (con DEFAULT_ANCHOR_ID=1)
2. El ID se carga automáticamente desde NVS
3. Para cambiar a anchor 2, programa de nuevo o usa WiFi config
```

## Comparación de Código

| Aspecto | anchor_1.ino | anchor_unified.ino |
|---------|--------------|-------------------|
| Líneas de código | 268 | 322 (+54 líneas) |
| Incluye `anchor_1.ino` | ✅ | ✅ |
| Funcionalidad DW3000 | ✅ | ✅ |
| State machine | ✅ | ✅ |
| Auto-restart | ✅ | ✅ |
| Estadísticas | ✅ | ✅ |
| **Lógica adicional** | ❌ | ✅ Carga ID desde NVS |
| **Configuración ID** | Hardcodeado | Configurable |

## ¿Cuál usar?

### Usa `anchor_1.ino` hasta `anchor_5.ino` si:
- ✅ Ya funcionan correctamente
- ✅ No quieres cambiar nada
- ✅ Prefieres simplicidad

### Usa `anchor_unified.ino` si:
- ✅ Quieres evitar duplicación de código
- ✅ Necesitas cambiar IDs sin recompilar
- ✅ Estás dispuesto a probar la nueva funcionalidad

## ¿Se mantiene la compatibilidad?

**SÍ.** `anchor_unified.ino` es 100% compatible con el protocolo actual.

La **única diferencia** es:
- Original: ID hardcodeado en línea 4
- Unificado: ID cargado en `setup()` desde NVS o DEFAULT

El resto del comportamiento (DW3000, state machine, estadísticas) es **idéntico**.

## Nota Final

Este archivo es una **propuesta de mejora**. Los archivos `anchor_1.ino` a `anchor_5.ino` 
**siguen siendo válidos** y pueden seguir usándose normalmente.

---

**Autor:** Refactorización experimental  
**Fecha:** 2025  
**Status:** Opcional - No rompe funcionalidad existente

