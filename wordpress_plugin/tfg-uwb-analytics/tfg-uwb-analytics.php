<?php
/**
 * Plugin Name: TFG UWB Analytics - Sistema de Análisis Deportivo
 * Description: Integración del sistema UWB del TFG para análisis de rendimiento en fútbol sala
 * Version: 1.0.0
 * Author: TFG Sistema UWB
 * Text Domain: tfg-uwb-analytics
 */

// Prevenir acceso directo
if (!defined('ABSPATH')) {
    exit;
}

class TFG_UWB_Analytics {
    
    public function __construct() {
        add_action('init', array($this, 'init'));
        add_action('wp_enqueue_scripts', array($this, 'enqueue_scripts'));
        add_shortcode('uwb_analytics', array($this, 'display_analytics'));
        add_shortcode('uwb_live_position', array($this, 'display_live_position'));
        add_shortcode('uwb_player_stats', array($this, 'display_player_stats'));
        
        // Hooks para el admin
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_post_upload_uwb_data', array($this, 'handle_file_upload'));
        add_action('wp_ajax_get_uwb_stats', array($this, 'get_uwb_stats'));
        add_action('wp_ajax_nopriv_get_uwb_stats', array($this, 'get_uwb_stats'));
        add_action('wp_ajax_get_live_data', array($this, 'get_live_data'));
        add_action('wp_ajax_nopriv_get_live_data', array($this, 'get_live_data'));
    }
    
    public function init() {
        // Crear tabla para almacenar datos UWB
        $this->create_uwb_table();
    }
    
    public function enqueue_scripts() {
        wp_enqueue_script('tfg-uwb-js', plugin_dir_url(__FILE__) . 'assets/tfg-uwb.js', array('jquery'), '1.0.0', true);
        wp_enqueue_style('tfg-uwb-css', plugin_dir_url(__FILE__) . 'assets/tfg-uwb.css', array(), '1.0.0');
        
        // Localizar script para AJAX
        wp_localize_script('tfg-uwb-js', 'tfg_uwb_ajax', array(
            'ajax_url' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('tfg_uwb_nonce')
        ));
    }
    
    /**
     * Shortcode para mostrar análisis de rendimiento
     */
    public function display_analytics($atts) {
        $atts = shortcode_atts(array(
            'player_id' => '',
            'session_date' => '',
            'type' => 'dashboard'
        ), $atts);
        
        ob_start();
        ?>
        <div class="tfg-uwb-analytics-container">
            <h3>📊 Análisis de Rendimiento UWB</h3>
            
            <?php if ($atts['type'] == 'dashboard'): ?>
                <div class="uwb-dashboard">
                    <div class="uwb-stats-grid">
                        <div class="stat-card">
                            <h4>⚡ Velocidad Máxima</h4>
                            <span class="stat-value" id="max-speed">--</span>
                            <span class="stat-unit">m/s</span>
                        </div>
                        <div class="stat-card">
                            <h4>📏 Distancia Total</h4>
                            <span class="stat-value" id="total-distance">--</span>
                            <span class="stat-unit">metros</span>
                        </div>
                        <div class="stat-card">
                            <h4>🏃 Sprints</h4>
                            <span class="stat-value" id="total-sprints">--</span>
                            <span class="stat-unit">episodios</span>
                        </div>
                        <div class="stat-card">
                            <h4>🎯 Intensidad</h4>
                            <span class="stat-value" id="avg-intensity">--</span>
                            <span class="stat-unit">%</span>
                        </div>
                    </div>
                    
                    <div class="uwb-heatmap-container">
                        <canvas id="uwb-heatmap" width="400" height="200"></canvas>
                    </div>
                    
                    <div class="uwb-load-data">
                        <button onclick="loadUWBData()" class="btn-load-data">
                            🔄 Cargar Datos Más Recientes
                        </button>
                    </div>
                </div>
            <?php endif; ?>
        </div>
        
        <script>
        function loadUWBData() {
            jQuery.ajax({
                url: tfg_uwb_ajax.ajax_url,
                type: 'POST',
                data: {
                    action: 'get_uwb_stats',
                    nonce: tfg_uwb_ajax.nonce,
                    player_id: '<?php echo esc_js($atts['player_id']); ?>'
                },
                success: function(response) {
                    if (response.success) {
                        updateDashboard(response.data);
                    }
                }
            });
        }
        
        function updateDashboard(data) {
            document.getElementById('max-speed').textContent = data.max_speed || '--';
            document.getElementById('total-distance').textContent = data.total_distance || '--';
            document.getElementById('total-sprints').textContent = data.total_sprints || '--';
            document.getElementById('avg-intensity').textContent = data.avg_intensity || '--';
            
            // Actualizar heatmap
            drawHeatmap(data.heatmap_data);
        }
        
        function drawHeatmap(heatmapData) {
            const canvas = document.getElementById('uwb-heatmap');
            const ctx = canvas.getContext('2d');
            
            // Limpiar canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Dibujar cancha de fútbol sala
            drawFutsalCourt(ctx, canvas.width, canvas.height);
            
            // Dibujar datos de calor
            if (heatmapData && heatmapData.length > 0) {
                drawHeatmapPoints(ctx, heatmapData, canvas.width, canvas.height);
            }
        }
        
        function drawFutsalCourt(ctx, width, height) {
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            
            // Perímetro
            ctx.strokeRect(0, 0, width, height);
            
            // Línea central
            ctx.beginPath();
            ctx.moveTo(width/2, 0);
            ctx.lineTo(width/2, height);
            ctx.stroke();
            
            // Círculo central
            ctx.beginPath();
            ctx.arc(width/2, height/2, 30, 0, 2 * Math.PI);
            ctx.stroke();
            
            // Áreas de portería
            const goalWidth = 60;
            const goalHeight = height * 0.6;
            const goalY = (height - goalHeight) / 2;
            
            ctx.strokeRect(0, goalY, goalWidth, goalHeight);
            ctx.strokeRect(width - goalWidth, goalY, goalWidth, goalHeight);
        }
        
        function drawHeatmapPoints(ctx, points, canvasWidth, canvasHeight) {
            points.forEach(point => {
                const x = (point.x / 40) * canvasWidth;  // Escalar de 40m a canvas
                const y = (point.y / 20) * canvasHeight; // Escalar de 20m a canvas
                const intensity = point.intensity || 0.5;
                
                ctx.fillStyle = `rgba(255, ${255 - intensity * 255}, 0, ${intensity})`;
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, 2 * Math.PI);
                ctx.fill();
            });
        }
        
        // Cargar datos al cargar la página
        document.addEventListener('DOMContentLoaded', function() {
            loadUWBData();
        });
        </script>
        <?php
        return ob_get_clean();
    }
    
    /**
     * Shortcode para posición en vivo
     */
    public function display_live_position($atts) {
        $atts = shortcode_atts(array(
            'esp32_ip' => '192.168.1.100',
            'auto_refresh' => '5'
        ), $atts);
        
        ob_start();
        ?>
        <div class="tfg-live-position">
            <h3>📍 Posición en Tiempo Real</h3>
            <p><strong>Estado:</strong> <span id="connection-status">Conectando...</span></p>
            
            <div class="live-court-container">
                <canvas id="live-court" width="600" height="300"></canvas>
            </div>
            
            <div class="live-stats">
                <div class="live-stat">
                    <label>Posición X:</label>
                    <span id="current-x">--</span> m
                </div>
                <div class="live-stat">
                    <label>Posición Y:</label>
                    <span id="current-y">--</span> m
                </div>
                <div class="live-stat">
                    <label>Velocidad:</label>
                    <span id="current-speed">--</span> m/s
                </div>
            </div>
        </div>
        
        <script>
        let liveUpdateInterval;
        
        function startLiveTracking() {
            const esp32Ip = '<?php echo esc_js($atts['esp32_ip']); ?>';
            const refreshRate = <?php echo intval($atts['auto_refresh']); ?> * 1000;
            
            liveUpdateInterval = setInterval(function() {
                fetch(`http://${esp32Ip}/data`)
                    .then(response => response.json())
                    .then(data => {
                        updateLivePosition(data);
                        document.getElementById('connection-status').textContent = '🟢 Conectado';
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        document.getElementById('connection-status').textContent = '🔴 Desconectado';
                    });
            }, refreshRate);
        }
        
        function updateLivePosition(data) {
            document.getElementById('current-x').textContent = data.x?.toFixed(2) || '--';
            document.getElementById('current-y').textContent = data.y?.toFixed(2) || '--';
            document.getElementById('current-speed').textContent = data.speed?.toFixed(2) || '--';
            
            drawLivePosition(data.x, data.y);
        }
        
        function drawLivePosition(x, y) {
            const canvas = document.getElementById('live-court');
            const ctx = canvas.getContext('2d');
            
            // Limpiar y dibujar cancha
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            drawFutsalCourt(ctx, canvas.width, canvas.height);
            
            // Dibujar posición actual
            if (x !== undefined && y !== undefined) {
                const canvasX = (x / 40) * canvas.width;
                const canvasY = (y / 20) * canvas.height;
                
                ctx.fillStyle = '#ff0000';
                ctx.beginPath();
                ctx.arc(canvasX, canvasY, 8, 0, 2 * Math.PI);
                ctx.fill();
                
                // Etiqueta del jugador
                ctx.fillStyle = '#ffffff';
                ctx.font = '12px Arial';
                ctx.fillText('JUGADOR', canvasX + 10, canvasY - 10);
            }
        }
        
        // Iniciar cuando se carga la página
        document.addEventListener('DOMContentLoaded', function() {
            startLiveTracking();
        });
        
        // Limpiar al salir
        window.addEventListener('beforeunload', function() {
            if (liveUpdateInterval) {
                clearInterval(liveUpdateInterval);
            }
        });
        </script>
        <?php
        return ob_get_clean();
    }
    
    /**
     * Crear tabla en la base de datos
     */
    private function create_uwb_table() {
        global $wpdb;
        
        $table_name = $wpdb->prefix . 'tfg_uwb_data';
        
        $charset_collate = $wpdb->get_charset_collate();
        
        $sql = "CREATE TABLE $table_name (
            id mediumint(9) NOT NULL AUTO_INCREMENT,
            timestamp datetime DEFAULT CURRENT_TIMESTAMP,
            player_id varchar(50) NOT NULL,
            session_id varchar(100) NOT NULL,
            x_position decimal(10,3) NOT NULL,
            y_position decimal(10,3) NOT NULL,
            velocity decimal(10,3) DEFAULT 0,
            intensity decimal(5,2) DEFAULT 0,
            zone varchar(100) DEFAULT '',
            raw_data text,
            PRIMARY KEY (id),
            KEY player_session (player_id, session_id),
            KEY timestamp_idx (timestamp)
        ) $charset_collate;";
        
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
        dbDelta($sql);
    }
    
    /**
     * Menú de administración
     */
    public function add_admin_menu() {
        add_menu_page(
            'TFG UWB Analytics',
            'UWB Analytics',
            'manage_options',
            'tfg-uwb-analytics',
            array($this, 'admin_page'),
            'dashicons-location-alt',
            30
        );
    }
    
    /**
     * Página de administración
     */
    public function admin_page() {
        // Mostrar mensajes de estado
        if (isset($_GET['message'])) {
            $message = urldecode($_GET['message']);
            $type = isset($_GET['type']) ? $_GET['type'] : 'error';
            $class = ($type == 'success') ? 'notice-success' : 'notice-error';
            echo '<div class="notice ' . $class . ' is-dismissible"><p>' . esc_html($message) . '</p></div>';
        }
        ?>
        <div class="wrap">
            <h1>🏟️ TFG UWB Analytics - Panel de Control</h1>
            
            <div class="tfg-admin-tabs">
                <h2>📤 Subir Datos UWB</h2>
                <form method="post" enctype="multipart/form-data" id="uwb-upload-form" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                    <?php wp_nonce_field('tfg_uwb_upload', 'tfg_uwb_nonce'); ?>
                    <input type="hidden" name="action" value="upload_uwb_data">
                    
                    <table class="form-table">
                        <tr>
                            <th scope="row">Archivo CSV</th>
                            <td>
                                <input type="file" name="uwb_csv_file" accept=".csv" required>
                                <p class="description">Sube archivos CSV generados por el sistema UWB</p>
                            </td>
                        </tr>
                        <tr>
                            <th scope="row">ID del Jugador</th>
                            <td>
                                <input type="text" name="player_id" placeholder="ej: jugador_01" required>
                            </td>
                        </tr>
                        <tr>
                            <th scope="row">ID de Sesión</th>
                            <td>
                                <input type="text" name="session_id" placeholder="ej: entrenamiento_2024_01_15" required>
                            </td>
                        </tr>
                    </table>
                    
                    <p class="submit">
                        <input type="submit" class="button-primary" value="📊 Procesar y Subir Datos">
                    </p>
                </form>
                
                <div id="upload-status" style="margin-top: 15px;"></div>
                
                <h2>⚙️ Configuración ESP32</h2>
                <table class="form-table">
                    <tr>
                        <th scope="row">IP del ESP32</th>
                        <td>
                            <input type="text" id="esp32-ip" value="192.168.1.100" placeholder="192.168.1.100">
                            <button type="button" onclick="testESP32Connection()" class="button">🔍 Probar Conexión</button>
                            <span id="esp32-status"></span>
                        </td>
                    </tr>
                </table>
                
                <h2>📋 Shortcodes Disponibles</h2>
                <div class="shortcode-examples">
                    <p><strong>Dashboard de análisis:</strong></p>
                    <code>[uwb_analytics player_id="jugador_01" type="dashboard"]</code>
                    
                    <p><strong>Posición en vivo:</strong></p>
                    <code>[uwb_live_position esp32_ip="192.168.1.100" auto_refresh="5"]</code>
                    
                    <p><strong>Estadísticas de jugador:</strong></p>
                    <code>[uwb_player_stats player_id="jugador_01" session_date="2024-01-15"]</code>
                </div>
                
                <h2>📊 Datos Almacenados</h2>
                <?php $this->display_stored_data(); ?>
            </div>
        </div>
        
        <script>
        function testESP32Connection() {
            const ip = document.getElementById('esp32-ip').value;
            const status = document.getElementById('esp32-status');
            
            status.innerHTML = '🔄 Probando...';
            
            fetch(`http://${ip}/data`, {mode: 'no-cors'})
                .then(response => {
                    status.innerHTML = '✅ Conexión exitosa';
                    status.style.color = 'green';
                })
                .catch(error => {
                    status.innerHTML = '❌ Error de conexión';
                    status.style.color = 'red';
                });
        }
        
        function viewPlayerStats(playerId, sessionId) {
            alert('Función de visualización de estadísticas para: ' + playerId + ' - Sesión: ' + sessionId + '\n\nEsta función se puede expandir para mostrar gráficos detallados.');
        }
        
        // Mejorar el formulario de subida
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('uwb-upload-form');
            const status = document.getElementById('upload-status');
            
            if (form) {
                form.addEventListener('submit', function(e) {
                    const fileInput = document.querySelector('input[name="uwb_csv_file"]');
                    const playerInput = document.querySelector('input[name="player_id"]');
                    const sessionInput = document.querySelector('input[name="session_id"]');
                    
                    if (!fileInput.files[0]) {
                        e.preventDefault();
                        status.innerHTML = '<div class="notice notice-error"><p>❌ Por favor selecciona un archivo CSV</p></div>';
                        return;
                    }
                    
                    if (!playerInput.value.trim() || !sessionInput.value.trim()) {
                        e.preventDefault();
                        status.innerHTML = '<div class="notice notice-error"><p>❌ Por favor completa todos los campos</p></div>';
                        return;
                    }
                    
                    // Validar archivo CSV
                    const file = fileInput.files[0];
                    if (!file.name.toLowerCase().endsWith('.csv')) {
                        e.preventDefault();
                        status.innerHTML = '<div class="notice notice-error"><p>❌ El archivo debe ser formato CSV</p></div>';
                        return;
                    }
                    
                    if (file.size > 10 * 1024 * 1024) { // 10MB límite
                        e.preventDefault();
                        status.innerHTML = '<div class="notice notice-error"><p>❌ El archivo es demasiado grande (máximo 10MB)</p></div>';
                        return;
                    }
                    
                    // Mostrar progreso
                    status.innerHTML = '<div class="notice notice-info"><p>🔄 Subiendo y procesando archivo... Por favor espera.</p></div>';
                    
                    // Deshabilitar botón de envío
                    const submitBtn = form.querySelector('input[type="submit"]');
                    submitBtn.disabled = true;
                    submitBtn.value = '🔄 Procesando...';
                });
            }
        });
        </script>
        <?php
    }
    
    /**
     * Manejar subida de archivos
     */
    public function handle_file_upload() {
        // Verificar nonce y permisos
        if (!wp_verify_nonce($_POST['tfg_uwb_nonce'], 'tfg_uwb_upload') || !current_user_can('manage_options')) {
            wp_die('Acceso denegado');
        }
        
        $message = '';
        $type = 'error';
        
        if (isset($_FILES['uwb_csv_file']) && $_FILES['uwb_csv_file']['error'] == 0) {
            $uploaded_file = $_FILES['uwb_csv_file'];
            $player_id = sanitize_text_field($_POST['player_id']);
            $session_id = sanitize_text_field($_POST['session_id']);
            
            // Validar archivo
            $allowed_types = array('text/csv', 'application/csv', 'text/plain');
            if (!in_array($uploaded_file['type'], $allowed_types)) {
                $message = 'Error: Solo se permiten archivos CSV';
            } else {
                // Procesar CSV y guardar en base de datos
                $result = $this->process_csv_file($uploaded_file, $player_id, $session_id);
                if ($result['success']) {
                    $message = "✅ Archivo procesado exitosamente. {$result['records']} registros insertados.";
                    $type = 'success';
                } else {
                    $message = "❌ Error procesando archivo: " . $result['error'];
                }
            }
        } else {
            $message = '❌ Error: No se pudo subir el archivo';
        }
        
        wp_redirect(admin_url('admin.php?page=tfg-uwb-analytics&message=' . urlencode($message) . '&type=' . $type));
        exit;
    }
    
    /**
     * Procesar archivo CSV
     */
    private function process_csv_file($file, $player_id, $session_id) {
        global $wpdb;
        
        $table_name = $wpdb->prefix . 'tfg_uwb_data';
        $records_inserted = 0;
        $errors = array();
        
        try {
            if (($handle = fopen($file['tmp_name'], 'r')) !== FALSE) {
                // Leer y validar header
                $header = fgetcsv($handle);
                
                // Headers esperados (flexibles) - específico para tus CSVs del TFG
                $expected_headers = array('timestamp', 'x', 'y', 'tag_id');
                $header_map = array();
                
                foreach ($expected_headers as $expected) {
                    $found = false;
                    foreach ($header as $index => $column) {
                        // Mapeo específico para tus datos
                        $column_clean = trim(strtolower($column));
                        if ($column_clean === $expected || 
                            ($expected === 'tag_id' && $column_clean === 'tag_id') ||
                            stripos($column, $expected) !== false) {
                            $header_map[$expected] = $index;
                            $found = true;
                            break;
                        }
                    }
                    if (!$found && $expected !== 'tag_id') {
                        return array('success' => false, 'error' => "Columna '$expected' no encontrada en CSV. Headers disponibles: " . implode(', ', $header));
                    }
                }
                
                // Si no hay tag_id en el CSV, usar el player_id proporcionado
                if (!isset($header_map['tag_id'])) {
                    $header_map['tag_id'] = null;
                }
                
                // Procesar datos
                while (($data = fgetcsv($handle)) !== FALSE) {
                    if (count($data) >= 3) {
                        // Extraer datos usando el mapeo de headers
                        $timestamp = $data[$header_map['timestamp']];
                        $x_pos = floatval($data[$header_map['x']]);
                        $y_pos = floatval($data[$header_map['y']]);
                        
                        // Obtener tag_id del CSV o usar el proporcionado
                        $csv_tag_id = '';
                        if ($header_map['tag_id'] !== null && isset($data[$header_map['tag_id']])) {
                            $csv_tag_id = $data[$header_map['tag_id']];
                        }
                        
                        // Usar velocidad del CSV si está disponible
                        $velocity = 0;
                        foreach ($header as $idx => $col) {
                            if (stripos($col, 'velocity') !== false && isset($data[$idx]) && is_numeric($data[$idx])) {
                                $velocity = floatval($data[$idx]);
                                break;
                            }
                        }
                        
                        // Si no hay velocidad en CSV, calcularla
                        if ($velocity == 0 && $records_inserted > 0) {
                            $prev_record = $wpdb->get_row($wpdb->prepare(
                                "SELECT x_position, y_position, timestamp FROM $table_name 
                                WHERE player_id = %s AND session_id = %s 
                                ORDER BY id DESC LIMIT 1",
                                $player_id, $session_id
                            ));
                            
                            if ($prev_record) {
                                $dx = $x_pos - $prev_record->x_position;
                                $dy = $y_pos - $prev_record->y_position;
                                $distance = sqrt($dx*$dx + $dy*$dy);
                                
                                $time_diff = strtotime($timestamp) - strtotime($prev_record->timestamp);
                                if ($time_diff > 0) {
                                    $velocity = $distance / $time_diff;
                                }
                            }
                        }
                        
                        // Calcular zona del campo
                        $zone = $this->calculate_field_zone($x_pos, $y_pos);
                        
                        // Insertar en base de datos
                        $result = $wpdb->insert(
                            $table_name,
                            array(
                                'timestamp' => $timestamp,
                                'player_id' => $player_id,
                                'session_id' => $session_id,
                                'x_position' => $x_pos,
                                'y_position' => $y_pos,
                                'velocity' => $velocity,
                                'intensity' => min(100, abs($velocity) * 20), // Intensidad estimada
                                'zone' => $zone,
                                'raw_data' => implode(',', $data)
                            ),
                            array('%s', '%s', '%s', '%f', '%f', '%f', '%f', '%s', '%s')
                        );
                        
                        if ($result) {
                            $records_inserted++;
                        } else {
                            $errors[] = "Error insertando fila " . ($records_inserted + 1);
                        }
                    }
                }
                fclose($handle);
                
                return array(
                    'success' => true, 
                    'records' => $records_inserted,
                    'errors' => $errors
                );
                
            } else {
                return array('success' => false, 'error' => 'No se pudo abrir el archivo CSV');
            }
            
        } catch (Exception $e) {
            return array('success' => false, 'error' => $e->getMessage());
        }
    }
    
    /**
     * AJAX: Obtener estadísticas UWB
     */
    public function get_uwb_stats() {
        // Verificar nonce
        if (!wp_verify_nonce($_POST['nonce'], 'tfg_uwb_nonce')) {
            wp_die('Security check failed');
        }
        
        global $wpdb;
        $table_name = $wpdb->prefix . 'tfg_uwb_data';
        $player_id = sanitize_text_field($_POST['player_id']);
        
        try {
            // Obtener datos más recientes del jugador
            $recent_data = $wpdb->get_results($wpdb->prepare(
                "SELECT * FROM $table_name 
                WHERE player_id = %s 
                ORDER BY timestamp DESC 
                LIMIT 1000",
                $player_id
            ));
            
            if (empty($recent_data)) {
                wp_send_json_error('No hay datos para este jugador');
                return;
            }
            
            // Calcular estadísticas
            $total_distance = 0;
            $speeds = array();
            $sprints = 0;
            $heatmap_data = array();
            
            foreach ($recent_data as $row) {
                $speeds[] = $row->velocity;
                if ($row->velocity > 4.0) $sprints++;
                
                $heatmap_data[] = array(
                    'x' => floatval($row->x_position),
                    'y' => floatval($row->y_position),
                    'intensity' => floatval($row->intensity) / 100
                );
            }
            
            // Calcular distancia total (aproximada)
            for ($i = 1; $i < count($recent_data); $i++) {
                $dx = $recent_data[$i]->x_position - $recent_data[$i-1]->x_position;
                $dy = $recent_data[$i]->y_position - $recent_data[$i-1]->y_position;
                $total_distance += sqrt($dx*$dx + $dy*$dy);
            }
            
            $stats = array(
                'max_speed' => round(max($speeds), 2),
                'total_distance' => round($total_distance, 1),
                'total_sprints' => $sprints,
                'avg_intensity' => round(array_sum(array_column($recent_data, 'intensity')) / count($recent_data), 1),
                'heatmap_data' => $heatmap_data,
                'records_count' => count($recent_data)
            );
            
            wp_send_json_success($stats);
            
        } catch (Exception $e) {
            wp_send_json_error('Error obteniendo estadísticas: ' . $e->getMessage());
        }
    }
    
    /**
     * AJAX: Obtener datos en vivo del ESP32
     */
    public function get_live_data() {
        // Para esta función, podríamos proxy la petición al ESP32
        // o devolver datos simulados para testing
        
        // Datos simulados para testing
        $live_data = array(
            'x' => 20 + sin(time() / 10) * 10,
            'y' => 10 + cos(time() / 8) * 5,
            'speed' => 2 + rand(0, 30) / 10,
            'timestamp' => current_time('mysql'),
            'status' => 'connected'
        );
        
        wp_send_json_success($live_data);
    }
    
    /**
     * Shortcode para estadísticas de jugador (implementación básica)
     */
    public function display_player_stats($atts) {
        $atts = shortcode_atts(array(
            'player_id' => '',
            'session_date' => ''
        ), $atts);
        
        global $wpdb;
        $table_name = $wpdb->prefix . 'tfg_uwb_data';
        
        // Obtener estadísticas del jugador
        $stats = $wpdb->get_results($wpdb->prepare(
            "SELECT 
                COUNT(*) as total_records,
                AVG(velocity) as avg_speed,
                MAX(velocity) as max_speed,
                AVG(intensity) as avg_intensity,
                MIN(timestamp) as first_record,
                MAX(timestamp) as last_record
            FROM $table_name 
            WHERE player_id = %s",
            $atts['player_id']
        ));
        
        if (empty($stats) || $stats[0]->total_records == 0) {
            return '<p>No hay datos disponibles para este jugador.</p>';
        }
        
        $stat = $stats[0];
        
        ob_start();
        ?>
        <div class="uwb-player-stats">
            <h3>📊 Estadísticas de <?php echo esc_html($atts['player_id']); ?></h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <strong>Sesiones:</strong> <?php echo esc_html($stat->total_records); ?> registros
                </div>
                <div class="stat-item">
                    <strong>Velocidad promedio:</strong> <?php echo esc_html(round($stat->avg_speed, 2)); ?> m/s
                </div>
                <div class="stat-item">
                    <strong>Velocidad máxima:</strong> <?php echo esc_html(round($stat->max_speed, 2)); ?> m/s
                </div>
                <div class="stat-item">
                    <strong>Intensidad promedio:</strong> <?php echo esc_html(round($stat->avg_intensity, 1)); ?>%
                </div>
                <div class="stat-item">
                    <strong>Período:</strong> <?php echo esc_html(date('d/m/Y', strtotime($stat->first_record))); ?> - <?php echo esc_html(date('d/m/Y', strtotime($stat->last_record))); ?>
                </div>
            </div>
        </div>
        <style>
        .uwb-player-stats { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 10px; }
        .stat-item { background: white; padding: 10px; border-radius: 4px; border-left: 4px solid #007cba; }
        </style>
        <?php
        return ob_get_clean();
    }
    
    /**
     * Mostrar datos almacenados en la interfaz de administración
     */
    private function display_stored_data() {
        global $wpdb;
        $table_name = $wpdb->prefix . 'tfg_uwb_data';
        
        // Verificar si la tabla existe
        $table_exists = $wpdb->get_var("SHOW TABLES LIKE '$table_name'") == $table_name;
        
        if (!$table_exists) {
            echo '<p>⚠️ La tabla de datos UWB no existe aún. Se creará automáticamente al subir el primer archivo.</p>';
            return;
        }
        
        // Obtener estadísticas generales
        $stats = $wpdb->get_results("
            SELECT 
                player_id,
                session_id,
                COUNT(*) as total_records,
                AVG(velocity) as avg_speed,
                MAX(velocity) as max_speed,
                MIN(timestamp) as first_record,
                MAX(timestamp) as last_record
            FROM $table_name 
            GROUP BY player_id, session_id 
            ORDER BY last_record DESC
            LIMIT 10
        ");
        
        if (empty($stats)) {
            echo '<p>📭 No hay datos almacenados aún. Sube tu primer archivo CSV para comenzar.</p>';
            return;
        }
        
        echo '<table class="wp-list-table widefat fixed striped">';
        echo '<thead><tr>
                <th>👤 Jugador</th>
                <th>🎯 Sesión</th>
                <th>📊 Registros</th>
                <th>🏃 Vel. Prom.</th>
                <th>⚡ Vel. Máx.</th>
                <th>📅 Período</th>
                <th>⚙️ Acciones</th>
              </tr></thead>';
        echo '<tbody>';
        
        foreach ($stats as $stat) {
            $period = date('d/m/Y H:i', strtotime($stat->first_record)) . ' - ' . date('d/m/Y H:i', strtotime($stat->last_record));
            echo '<tr>';
            echo '<td><strong>' . esc_html($stat->player_id) . '</strong></td>';
            echo '<td>' . esc_html($stat->session_id) . '</td>';
            echo '<td>' . number_format($stat->total_records) . '</td>';
            echo '<td>' . round($stat->avg_speed, 2) . ' m/s</td>';
            echo '<td>' . round($stat->max_speed, 2) . ' m/s</td>';
            echo '<td>' . esc_html($period) . '</td>';
            echo '<td>
                    <button type="button" class="button button-small" onclick="viewPlayerStats(\'' . esc_js($stat->player_id) . '\', \'' . esc_js($stat->session_id) . '\')">
                        📈 Ver Stats
                    </button>
                  </td>';
            echo '</tr>';
        }
        
        echo '</tbody></table>';
        
        // Total de registros
        $total_records = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
        echo '<p><strong>📊 Total de registros en base de datos:</strong> ' . number_format($total_records) . '</p>';
    }
    
    /**
     * Calcular zona del campo de fútbol sala (40x20m)
     */
    private function calculate_field_zone($x, $y) {
        // Validar que esté dentro del campo
        if ($x < 0 || $x > 40 || $y < 0 || $y > 20) {
            return 'Fuera del campo';
        }
        
        // Áreas de portería (semicírculo de 6m)
        $goal_distance_left = sqrt(pow($x - 0, 2) + pow($y - 10, 2));
        $goal_distance_right = sqrt(pow($x - 40, 2) + pow($y - 10, 2));
        
        if ($goal_distance_left <= 6 && $x <= 6) {
            return 'Área de portería local';
        }
        if ($goal_distance_right <= 6 && $x >= 34) {
            return 'Área de portería visitante';
        }
        
        // Círculo central (radio 3m)
        $center_distance = sqrt(pow($x - 20, 2) + pow($y - 10, 2));
        if ($center_distance <= 3) {
            return 'Círculo central';
        }
        
        // Zonas por tercios del campo
        if ($x <= 13.33) {
            return 'Zona defensiva local';
        } elseif ($x <= 26.67) {
            return 'Zona media';
        } else {
            return 'Zona ofensiva';
        }
    }
}

// Inicializar el plugin
new TFG_UWB_Analytics();
?> 