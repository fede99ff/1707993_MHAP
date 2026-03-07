import os
import time
import json
import uuid
import requests
import pika
from datetime import datetime, timezone

# Configurazione via variabili d'ambiente
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:8080")
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672/")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

def get_rabbitmq_channel():
    """Connessione resiliente a RabbitMQ."""
    parameters = pika.URLParameters(BROKER_URL)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    # Exchange fanout: invia a tutte le code collegate
    channel.exchange_declare(exchange='normalized_events', exchange_type='fanout')
    return connection, channel

def normalize_data(sensor_data):
    """
    Traduce i formati nativi del simulatore nel Normalized Data Format del team.
    Basato sulle specifiche di SCHEMA_CONTRACT.md.
    """
    # Struttura base del nostro formato normalizzato
    normalized_event = {
        "source": sensor_data.get("sensor_id", "unknown"),
        "type": "REST_SENSOR_READING",
        "status": sensor_data.get("status", "ok"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "payload": {}
    }

    # Riconoscimento del formato tramite le chiavi presenti nel JSON
    if "metric" in sensor_data and "value" in sensor_data:
        # Schema rest.scalar.v1 (es. greenhouse_temperature)
        normalized_event["payload"] = {
            "metric": sensor_data["metric"],
            "value": sensor_data["value"],
            "unit": sensor_data["unit"]
        }
    elif "measurements" in sensor_data:
        # Schema rest.chemistry.v1 (es. hydroponic_ph)
        normalized_event["payload"] = {
            "measurements": sensor_data["measurements"]
        }
    elif "pm25_ug_m3" in sensor_data:
        # Schema rest.particulate.v1 (es. air_quality_pm25)
        normalized_event["payload"] = {
            "pm1": sensor_data["pm1_ug_m3"],
            "pm25": sensor_data["pm25_ug_m3"],
            "pm10": sensor_data["pm10_ug_m3"]
        }
    elif "level_pct" in sensor_data:
        # Schema rest.level.v1 (es. water_tank_level)
        normalized_event["payload"] = {
            "level_pct": sensor_data["level_pct"],
            "level_liters": sensor_data["level_liters"]
        }
    else:
        # Fallback di sicurezza se arriva un formato sconosciuto
        normalized_event["payload"] = {"raw_data": sensor_data}

    return normalized_event

def poll_sensors(channel):
    """Esegue il polling e pubblica su RabbitMQ."""
    try:
        # 1. Recupera la lista dei sensori attivi
        res = requests.get(f"{SIMULATOR_URL}/api/sensors", timeout=5)
        res.raise_for_status()
        sensors_list = res.json()

        # 2. Interroga ogni singolo sensore
        for sensor_id in sensors_list["sensors"]:
            sensor_res = requests.get(f"{SIMULATOR_URL}/api/sensors/{sensor_id}", timeout=5)
    
            if sensor_res.status_code == 200:
            
                raw_data = sensor_res.json()
                # 3. Normalizza i dati secondo SCHEMA_CONTRACT.md
                normalized_event = normalize_data(raw_data)
                print(normalized_event)
                # 4. Pubblica su RabbitMQ
                channel.basic_publish(
                    exchange='normalized_events',
                    routing_key='', 
                    body=json.dumps(normalized_event)
                )
                print(f"[x] Inviato: {sensor_id} | Status: {normalized_event['status']}")
                
    except requests.exceptions.RequestException as e:
        print(f"[!] Errore di connessione al simulatore: {e}")

def main():
    print("Starting Ingestion Service...")
    time.sleep(5) # Piccola attesa iniziale
    channel = None
    connection = None
    while not connection:
        try:
            connection, channel = get_rabbitmq_channel()
            print("Connesso a RabbitMQ con successo!")
        except pika.exceptions.AMQPConnectionError:
            print("In attesa di RabbitMQ...")
            time.sleep(3)

    try:
        while True:
            poll_sensors(channel)
            time.sleep(POLL_INTERVAL)
           
    except KeyboardInterrupt:
        print("Chiusura servizio...")
        if connection and not connection.is_closed:
            connection.close()

if __name__ == "__main__":
    main()