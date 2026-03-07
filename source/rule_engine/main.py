import os
import time
import json
import pika
import pymysql
import requests

# --- CONFIGURAZIONI ---
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@broker:5672/")
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://host.docker.internal:8080")

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "mars_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mars_password")
DB_NAME = os.getenv("DB_NAME", "rules_db")

def get_db_connection():
    """Crea una nuova connessione al database MySQL."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

import time
import pika

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
    #Fa il confronto matematico tra il dato letto e la regola del DB.
    try:
        val = float(valore_sensore)
        soglia = float(soglia)
        if operatore == '>': return val > soglia
        if operatore == '<': return val < soglia
        if operatore == '>=': return val >= soglia
        if operatore == '<=': return val <= soglia
        if operatore == '==': return val == soglia
    except ValueError:
        pass
    return False

def estrai_valore_da_payload(payload: dict):
    
    #I sensori hanno formati diversi (es. 'value' per temp, 'pm25' per aria).
    #Questa funzione cerca il numero giusto da controllare.
    if not isinstance(payload, dict):
        return None

    if "value" in payload and isinstance(payload["value"], (int, float)):
        return payload["value"]

    meas = payload.get("measurements")
    if isinstance(meas, list) and len(meas) > 0 and isinstance(meas[0], dict):
        v = meas[0].get("value")
        return v if isinstance(v, (int, float)) else None


    return None

def trigger_actuator(actuator_id, target_state):
    #Invia il comando HTTP POST al simulatore per accendere/spegnere l'attuatore.
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
    #Questa funzione scatta OGNI VOLTA che arriva un dato da RabbitMQ.
    evento = json.loads(body)
    sensor_id = evento.get("source")
    payload = evento.get("payload", {})
    
    valore_attuale = estrai_valore_da_payload(payload)
    if valore_attuale is None:
        print(f"[rule_engine] payload non supportato per regole: {payload}")
        return # Ignora se non riusciamo a estrarre un numero valido

    print(f"\n[DATO RICEVUTO] {sensor_id}: {valore_attuale}")

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Trucco SQL: Cerchiamo le regole la cui colonna 'condition' INIZIA con il nome del sensore
            # es. "greenhouse_temperature %"
            sql = "SELECT * FROM rules WHERE `condition` LIKE %s"
            cursor.execute(sql, (f"{sensor_id} %",))
            regole = cursor.fetchall()

        # Valutiamo tutte le regole trovate per questo sensore
        for regola in regole:
            # Spezzettiamo la stringa: "greenhouse_temperature > 28.0" -> ['greenhouse_temperature', '>', '28.0']
            parti_regola = regola['condition'].split(' ')
            
            if len(parti_regola) == 3:
                operatore = parti_regola[1]
                soglia = parti_regola[2]
                
                print(f"  -> Controllo regola: Se {valore_attuale} {operatore} {soglia} allora {regola['actuator']}={regola['action_taken']}")
                
                # Facciamo la vera e propria valutazione matematica
                if valuta_condizione(valore_attuale, operatore, soglia):
                    print("    [!] CONDIZIONE AVVERATA!")
                    trigger_actuator(regola['actuator'], regola['action_taken'])
                else:
                    print("    [OK] Condizione NON avverata.")

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

    # Dichiariamo l'exchange e la coda
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