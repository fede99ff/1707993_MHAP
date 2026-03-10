import os
import time
import json
import pika
import pymysql
import requests
import re

BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@broker:5672/")
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://host.docker.internal:8080")
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "mars_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mars_password")
DB_NAME = os.getenv("DB_NAME", "rules_db")

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def connect_with_retry(parameters, attempts=30, base_sleep=1.0, max_sleep=10.0):
    sleep_s = base_sleep
    last_err = None
    for i in range(1, attempts + 1):
        try:
            return pika.BlockingConnection(parameters)
        except Exception as e:
            last_err = e
            print(f"[rule_engine] RabbitMQ non pronto (tentativo {i}/{attempts}): {e}")
            time.sleep(sleep_s)
            sleep_s = min(max_sleep, sleep_s * 1.5)
    raise last_err

def valuta_condizione(valore_sensore, operatore, soglia):
    try:
        val = float(valore_sensore)
        soglia = float(soglia)
        if operatore == '>': return val > soglia
        if operatore == '<': return val < soglia
        if operatore == '>=': return val >= soglia
        if operatore == '<=': return val <= soglia
        if operatore in ('==', '='): return val == soglia
    except ValueError:
        pass
    return False

def estrai_valore_da_payload(payload: dict):
    if not isinstance(payload, dict):
        return None

    if isinstance(payload.get("value"), (int, float)):
        return payload["value"]

    if isinstance(payload.get("level_pct"), (int, float)):
        return payload["level_pct"]

    for k in ("pm25", "pm10", "pm1"):
        v = payload.get(k)
        if isinstance(v, (int, float)):
            return v

    meas = payload.get("measurements")
    if isinstance(meas, list):
        for m in meas:
            if isinstance(m, dict) and isinstance(m.get("value"), (int, float)):
                return m["value"]

    return None

def trigger_actuator(actuator_id, target_state):
    url = f"{SIMULATOR_URL}/api/actuators/{actuator_id}"
    payload = {"state": target_state}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            print(f"    [ATTUATORE AZIONATO] -> {actuator_id} impostato su {target_state}!")
        else:
            print(f"    [ERRORE ATTUATORE] -> API ha risposto con {res.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"    [ERRORE RETE] -> Impossibile contattare il simulatore: {e}")

def callback(ch, method, properties, body):
    evento = json.loads(body)
    sensor_id = evento.get("source")
    payload = evento.get("payload", {})
    
    valore_attuale = estrai_valore_da_payload(payload)
    if valore_attuale is None:
        print(f"[rule_engine] payload non supportato per regole: {payload}")
        return

    print(f"\n[DATO RICEVUTO] {sensor_id}: {valore_attuale}")

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM rules WHERE enabled = TRUE AND `condition` LIKE %s" #per regole anche dopo restart
            cursor.execute(sql, (f"{sensor_id} %",))
            regole = cursor.fetchall()


        for regola in regole:
            cond_str = (regola.get("condition") or "").strip()
            m = re.match(
                r'^\s*(\S+)\s*(>=|<=|==|=|>|<)\s*([+-]?\d+(?:\.\d+)?)\s*(.*)?$',
                cond_str
            )
            if not m:
                print(f"  -> [SKIP] Condizione non parsabile: {cond_str!r}")
                continue

            sensor_cond, operatore, soglia, unita = (
                m.group(1),
                m.group(2),
                m.group(3),
                (m.group(4) or "").strip()
            )

            if sensor_cond != sensor_id:
                continue

            print(f"  -> Regola matchata per {sensor_id}: {cond_str} (unità='{unita}')")
            if valuta_condizione(valore_attuale, operatore, soglia) and regola.get("enabled"):
                print(f"    [CONDIZIONE VERA] {valore_attuale} {operatore} {soglia}")
                trigger_actuator(regola["actuator"], regola["action_taken"])
            else:
                print(f"    [CONDIZIONE FALSA] {valore_attuale} {operatore} {soglia}")

    except Exception as e:
        print(f"[ERRORE RULE ENGINE] {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

def main():
    print("Avvio Rule Engine... attendo 15s per RabbitMQ e MySQL...")
    time.sleep(15) 

    parameters = pika.URLParameters(BROKER_URL)
    connection = connect_with_retry(parameters)
    channel = connection.channel()

    channel.exchange_declare(exchange='normalized_events', exchange_type='fanout')
    channel.queue_declare(queue='rule_engine_queue', durable=True)
    channel.queue_bind(exchange='normalized_events', queue='rule_engine_queue')

    print(' [*] Rule Engine in ascolto! In attesa di dati...')
    
    channel.basic_consume(
        queue='rule_engine_queue',
        on_message_callback=callback,
        auto_ack=True
    )
    
    channel.start_consuming()

if __name__ == "__main__":
    main()