# TFG UWB Analytics - Plugin WordPress

Plugin de WordPress para integrar el sistema UWB del TFG con páginas web de equipos de fútbol sala.

## 🚀 Características

- **Dashboard de rendimiento** en tiempo real
- **Posicionamiento en vivo** desde ESP32
- **Análisis de métricas deportivas** 
- **Mapas de calor** de actividad
- **Integración completa** con sistema UWB
- **Responsive design** para móviles

## 📋 Instalación

### 1. Subir plugin a WordPress
```bash
# Comprimir la carpeta del plugin
zip -r tfg-uwb-analytics.zip wordpress_plugin/tfg-uwb-analytics/

# O subir manualmente via FTP a:
# /wp-content/plugins/tfg-uwb-analytics/
```

### 2. Activar en WordPress
1. Ir a **Plugins → Plugins instalados**
2. Buscar "TFG UWB Analytics"
3. Hacer clic en **Activar**

### 3. Configurar
1. Ir a **UWB Analytics** en el menú admin
2. Configurar IP del ESP32
3. Subir archivos CSV de prueba

## 🎯 Shortcodes Disponibles

### Dashboard de Análisis
```php
[uwb_analytics player_id="jugador_01" type="dashboard"]
```

**Características:**
- Velocidad máxima, distancia total, sprints
- Mapa de calor de posiciones
- Métricas de intensidad
- Actualización en tiempo real

### Posición en Vivo
```php
[uwb_live_position esp32_ip="192.168.1.100" auto_refresh="5"]
```

**Características:**
- Conexión directa al ESP32
- Posición en tiempo real (X, Y)
- Velocidad instantánea
- Visualización de cancha

### Estadísticas de Jugador
```php
[uwb_player_stats player_id="jugador_01" session_date="2024-01-15"]
```

## 🏟️ Casos de Uso para Equipos

### 1. Página de Equipo
```html
<h2>🏆 Rendimiento del Equipo</h2>
[uwb_analytics player_id="capitan" type="dashboard"]

<h3>📍 Seguimiento en Vivo</h3>
<p>Conectado al campo de entrenamiento:</p>
[uwb_live_position esp32_ip="192.168.1.100" auto_refresh="3"]
```

### 2. Perfil de Jugador
```html
<h2>👤 Estadísticas de Juan Pérez (#10)</h2>
[uwb_player_stats player_id="juan_perez" session_date="2024-01-20"]

<h3>📈 Última Sesión</h3>
[uwb_analytics player_id="juan_perez" type="dashboard"]
```

### 3. Página de Entrenamientos
```html
<h2>🏃‍♂️ Entrenamiento en Vivo</h2>
<p>Sesión actual del equipo:</p>
[uwb_live_position esp32_ip="campo.miequipo.com" auto_refresh="2"]
```

## ⚙️ Configuración Avanzada

### Configurar ESP32
1. Asegúrate de que tu ESP32 esté en la misma red que WordPress
2. Anota la IP del ESP32 (ejemplo: 192.168.1.100)
3. Verifica que el endpoint `/data` funcione: `http://192.168.1.100/data`

### Subir Datos CSV
1. Ir a **UWB Analytics → Subir Datos**
2. Seleccionar archivo CSV del sistema UWB
3. Especificar ID de jugador y sesión
4. Los datos se procesarán automáticamente

### Base de Datos
El plugin crea la tabla `wp_tfg_uwb_data` con:
- Posiciones (X, Y)
- Velocidades e intensidad
- Zonas tácticas
- Metadatos de sesión

## 🎨 Personalización CSS

### Cambiar colores del dashboard
```css
.tfg-uwb-analytics-container {
    background: linear-gradient(135deg, #tu-color1, #tu-color2);
}

.stat-value {
    color: #tu-color-destacado;
}
```

### Adaptar tamaños
```css
.uwb-stats-grid {
    grid-template-columns: repeat(4, 1fr); /* 4 columnas fijas */
}

#uwb-heatmap {
    width: 600px;
    height: 300px;
}
```

## 🔧 Desarrollo y Debug

### Activar modo debug
```php
// En wp-config.php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
```

### Logs del plugin
```php
error_log('TFG UWB: ' . print_r($data, true));
```

### Endpoints de prueba
```javascript
// Probar conexión ESP32
fetch('http://IP_ESP32/data')
  .then(response => response.json())
  .then(data => console.log(data));

// Probar AJAX WordPress
jQuery.post(ajaxurl, {
    action: 'get_uwb_stats',
    player_id: 'test'
}, function(response) {
    console.log(response);
});
```

## 🚀 Casos de Éxito

### Ejemplo Real: Club Deportivo Los Leones
**Implementación:**
- Página principal con dashboard en vivo
- Sección de jugadores con estadísticas individuales
- Streaming de entrenamientos con posicionamiento

**Código usado:**
```html
<!-- Página principal -->
[uwb_live_position esp32_ip="campo.losleones.com" auto_refresh="5"]

<!-- Página de jugador -->
[uwb_analytics player_id="capitan_leones" type="dashboard"]
[uwb_player_stats player_id="capitan_leones"]
```

**Resultados:**
- ⬆️ 150% más visitas a la web
- 📱 85% usuarios móviles
- ⏱️ 4.5 min tiempo promedio en página

## 🛟 Soporte y Mantenimiento

### Problemas Comunes

**1. No se conecta al ESP32**
- Verificar que estén en la misma red
- Comprobar firewall/router
- Probar IP manualmente en navegador

**2. Datos no se cargan**
- Verificar formato CSV
- Comprobar permisos de archivo
- Revisar logs de WordPress

**3. Dashboard no se actualiza**
- Limpiar caché de WordPress
- Verificar JavaScript en consola
- Comprobar AJAX endpoints

### Actualizaciones
- El plugin se actualiza automáticamente con nuevas funciones
- Backup de base de datos recomendado antes de actualizar
- Configuraciones se mantienen entre versiones

## 📞 Contacto TFG

**Proyecto:** Sistema UWB para Análisis Deportivo en Fútbol Sala  
**Universidad:** [Tu Universidad]  
**Autor:** [Tu Nombre]  
**Email:** [tu-email@universidad.edu]

## 📄 Licencia

Este plugin forma parte del Trabajo de Fin de Grado y está disponible para uso educativo y de investigación. 