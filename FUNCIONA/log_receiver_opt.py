# log_receiver_mqtt.py
import paho.mqtt.client as mqtt
import datetime
import os
import time

# --- Configuración ---
# Puedes cambiar a tu IP real si usas otro broker
BROKER_ADDRESS = "172.20.10.2"  # IP del broker MQTT de tu PC
BROKER_PORT = 1883
LOG_TOPIC = "uwb/tag/logs"    # Topic donde los tags publican los logs
# Directorio para logs de ranging
LOG_DIR = "uwb_logs_mqtt"     # Directorio para guardar logs con distancias
# Directorio para datos principales (compatible movement_replay.py)
MAIN_DIR = "uwb_replay_csv"

# Encabezados
EXPECTED_HEADER = "Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_cm,Filtered_Distance_cm,Signal_Power_dBm,Anchor_Status" # Mantener el formato CSV esperado

# Header para archivo compatible con movement_replay.py
MAIN_HEADER = "timestamp,tag_id,x,y,anchor_10_dist,anchor_20_dist,anchor_30_dist,anchor_40_dist,anchor_50_dist"

# -- Variables Globales --
# Archivos globales
current_log_file = None
log_file_handle = None

current_main_file = None
main_file_handle = None

def create_log_directory_and_file():
    """Crea el directorio de logs si no existe y abre un nuevo archivo CSV con timestamp."""
    global current_log_file, log_file_handle
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
            print(f"Created log directory: {LOG_DIR}")

        # Cerrar archivo anterior si está abierto
        if log_file_handle and not log_file_handle.closed:
            log_file_handle.close()
            print(f"Closed previous log file: {current_log_file}")

        # Generar nombre único y abrir nuevo archivo
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uwb_log_{timestamp_str}.csv"
        current_log_file = os.path.join(LOG_DIR, filename)

        log_file_handle = open(current_log_file, 'w') 
        log_file_handle.write(EXPECTED_HEADER + '\n') 
        log_file_handle.flush() # Asegurar que se escriba inmediatamente
        print(f"Opened new log file: {current_log_file}")

    except Exception as e:
        print(f"Error creating/opening log file: {e}")
        current_log_file = None
        log_file_handle = None

def create_main_directory_and_file():
    global current_main_file, main_file_handle
    try:
        if not os.path.exists(MAIN_DIR):
            os.makedirs(MAIN_DIR)
            print(f"Created replay directory: {MAIN_DIR}")

        # Cerrar anterior
        if main_file_handle and not main_file_handle.closed:
            main_file_handle.close()
            print(f"Closed previous main file: {current_main_file}")

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uwb_replay_{timestamp_str}.csv"
        current_main_file = os.path.join(MAIN_DIR, filename)

        main_file_handle = open(current_main_file, 'w')
        main_file_handle.write(MAIN_HEADER + '\n')
        main_file_handle.flush()
        print(f"Opened new main file: {current_main_file}")

    except Exception as e:
        print(f"Error creating/opening main file: {e}")
        current_main_file = None
        main_file_handle = None

def on_connect(client, userdata, flags, rc):
    """Callback que se ejecuta cuando el cliente se conecta al broker MQTT."""
    if rc == 0:
        print(f"Conectado al Broker MQTT en {BROKER_ADDRESS}:{BROKER_PORT}")
        # Suscribirse a logs de rango y a estados de posicion
        topics = [
            ("uwb/tag/logs", 0),
            ("uwb/tag/+/status", 0)
        ]
        client.subscribe(topics)
        for t, _ in topics:
            print(f"Suscrito a: {t}")
    else:
        print(f"Fallo al conectar, código de error: {rc}")

def on_message(client, userdata, msg):
    """Callback que se ejecuta cuando se recibe un mensaje en un topic suscrito."""
    global log_file_handle
    payload_str = ""
    try:
        # Decodificar el mensaje (payload)
        payload_str = msg.payload.decode("utf-8")
        # print(f"Mensaje recibido en [{msg.topic}]: {payload_str}") # Descomentar para debug

        # --- Procesar LOGS de rango CSV ---
        if msg.topic == "uwb/tag/logs":
            if payload_str and len(payload_str.split(',')) == len(EXPECTED_HEADER.split(',')):
                # Escribir en el archivo CSV si está abierto
                if log_file_handle and not log_file_handle.closed:
                    log_file_handle.write(payload_str + '\n')
                    log_file_handle.flush() # Forzar escritura a disco
                else:
                    print("Advertencia: Mensaje MQTT recibido pero el archivo de log no está abierto.")
                    # Intentar reabrir el archivo si se cerró inesperadamente
                    create_log_directory_and_file()
                    if log_file_handle and not log_file_handle.closed:
                         log_file_handle.write(payload_str + '\n')
                         log_file_handle.flush()
            else:
                print(f"Advertencia: Payload inválido en [{msg.topic}]")

        # --- Procesar STATUS JSON para replay ---
        elif msg.topic.endswith("/status"):
            try:
                import json
                data = json.loads(payload_str)
                ts_system = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                tag_id = data.get('tag_id', 0)
                pos = data.get('position', {})
                x = pos.get('x', 0.0)
                y = pos.get('y', 0.0)
                ad = data.get('anchor_distances', {})

                row = [
                    ts_system,
                    tag_id,
                    x,
                    y,
                    ad.get('10', 0.0),
                    ad.get('20', 0.0),
                    ad.get('30', 0.0),
                    ad.get('40', 0.0),
                    ad.get('50', 0.0)
                ]

                if main_file_handle and not main_file_handle.closed:
                    main_file_handle.write(','.join(str(v) for v in row) + '\n')
                else:
                    create_main_directory_and_file()
                    if main_file_handle and not main_file_handle.closed:
                        main_file_handle.write(','.join(str(v) for v in row) + '\n')

            except Exception as e:
                print(f"Error procesando JSON status: {e}")
        # Otros topics
        else:
            pass

    except Exception as e:
        print(f"Error procesando mensaje MQTT: {e}")
        print(f"Payload problemático: {payload_str}")


def setup_mqtt_client():
    """Configura e inicia el cliente MQTT."""
    global client
    # Crear un ID de cliente único para evitar desconexiones si se ejecutan varias instancias
    client_id = f"log-receiver-{os.getpid()}-{time.time()}"
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print(f"Intentando conectar a {BROKER_ADDRESS}:{BROKER_PORT}...")
        client.connect(BROKER_ADDRESS, BROKER_PORT, 60) # 60 segundos de keepalive
    except ConnectionRefusedError:
        print(f"Error: Conexión rechazada. ¿Está el broker MQTT ({BROKER_ADDRESS}:{BROKER_PORT}) en ejecución?")
        return None
    except OSError as e:
         print(f"Error de red al conectar al broker: {e}")
         return None
    except Exception as e:
        print(f"Error inesperado al conectar al broker MQTT: {e}")
        return None
    return client

# --- Main Execution ---
if __name__ == "__main__":
    print("Iniciando Receptor de Logs MQTT...")

    # Crear directorio y archivo de log inicial
    create_log_directory_and_file()
    create_main_directory_and_file()
    if not current_log_file or not current_main_file:
        print("Error crítico al crear el archivo de log inicial. Saliendo.")
        exit(1)

    # Configurar e iniciar cliente MQTT
    client = setup_mqtt_client()

    if client:
        try:
            # Iniciar el bucle de red MQTT (bloqueante)
            # Este bucle maneja la reconexión y procesa los callbacks
            client.loop_forever()
        except KeyboardInterrupt:
            print("\nReceptor detenido por el usuario (Ctrl+C).")
        except Exception as e:
            print(f"Error inesperado en el bucle MQTT: {e}")
        finally:
            # Limpieza al salir
            print("Desconectando del broker MQTT...")
            if client.is_connected():
                 client.loop_stop() # Detener el bucle de red de forma limpia si es posible
                 client.disconnect()
            if log_file_handle and not log_file_handle.closed:
                log_file_handle.close()
                print(f"Archivo de log cerrado: {current_log_file}")
            if main_file_handle and not main_file_handle.closed:
                main_file_handle.close()
            print("Receptor de Logs MQTT detenido.")
    else:
        print("No se pudo iniciar el cliente MQTT. Saliendo.")
        # Asegurarse de cerrar el archivo si el cliente no pudo iniciar
        if log_file_handle and not log_file_handle.closed:
             log_file_handle.close()
        if main_file_handle and not main_file_handle.closed:
            main_file_handle.close()
        exit(1)