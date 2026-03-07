import os
import threading
import json
import time
from typing import List, Optional

import asyncio
import json
from fastapi.responses import StreamingResponse

import pika
import pymysql
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi import HTTPException


# --- VARIABILI D'AMBIENTE ---
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "mars_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mars_password")
DB_NAME = os.getenv("DB_NAME", "rules_db")
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@broker:5672/")
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://simulator:8080")

# --- CACHE IN MEMORIA PER I SENSORI ---
sensor_cache = {}

app = FastAPI(title="Mars Dashboard Backend")

# --- CORS (Permette al frontend di comunicare) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- THREAD RABBITMQ IN BACKGROUND ---
def rabbitmq_consumer():
    """Ascolta l'ingestor e aggiorna la cache in tempo reale"""
    connection = None
    while connection is None:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
        except Exception:
            time.sleep(3)

    channel = connection.channel()
    channel.exchange_declare(exchange='normalized_events', exchange_type='fanout')
    
    result = channel.queue_declare(queue='', exclusive=True)
    channel.queue_bind(exchange='normalized_events', queue=result.method.queue)

    def callback(ch, method, properties, body):
        try:
            event = json.loads(body)
            if event.get("source"):
                sid = event["source"]

                # tieni in cache tutto l'evento (o un subset controllato)
                new_ts = event.get("processed_at")

                old = sensor_cache.get(sid)
                old_ts = old.get("processed_at") if isinstance(old, dict) else None

                # update idempotente "best effort" su processed_at (ISO string compare funziona se ISO ben formattato)
                if (old is None) or (old_ts is None) or (new_ts is None) or (new_ts >= old_ts):
                    sensor_cache[sid] = {
                        "source": sid,
                        "type": event.get("type"),
                        "status": event.get("status"),
                        "processed_at": new_ts,
                        "payload": event.get("payload", {}),
                    }
        except Exception:
            pass

    channel.basic_consume(queue=result.method.queue, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

@app.on_event("startup")
def startup_event():
    threading.Thread(target=rabbitmq_consumer, daemon=True).start()


# --- MODELLI DATI ---
class RuleIn(BaseModel):
    condition: str = Field(...)
    action_taken: str = Field(...)
    actuator: str = Field(...)
    enabled: bool = True

class RuleOut(RuleIn):
    id: int

class ActuatorCommand(BaseModel):
    state: str


def get_conn(retries: int = 20, delay_s: float = 1.0):
    last_exc = None
    for i in range(retries):
        try:
            return pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=3,
            )
        except Exception as e:
            last_exc = e
            print(f"[backend] DB non pronto (tentativo {i+1}/{retries}): {e}")
            time.sleep(delay_s)
    raise last_exc

# --- ENDPOINT SENSORI E ATTUATORI ---

@app.get("/api/sensors/latest")
def get_sensors():
    return sensor_cache

@app.get("/api/sensors/latest/{sensor_id}")
def get_sensor_latest(sensor_id: str):
    s = sensor_cache.get(sensor_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sensor not found in cache yet")
    return s

@app.get("/api/sensors/stream")
async def sensors_stream():
    async def event_generator():
        # facciamo push periodico: minimo, robusto, zero refactor
        last_payload = None
        while True:
            payload = json.dumps(sensor_cache)  # sensor_cache già esiste nel tuo backend
            # opzionale: invia solo se cambia (riduce traffico)
            if payload != last_payload:
                yield f"event: sensors\ndata: {payload}\n\n"
                last_payload = payload

            # keep-alive / ritmo aggiornamenti
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")








from datetime import datetime, timezone

def _parse_iso(ts: str):
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

@app.get("/api/sensors/latest/{sensor_id}/fresh")
def get_sensor_latest_fresh(sensor_id: str, max_age_s: int = 30):
    s = sensor_cache.get(sensor_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sensor not found in cache yet")

    dt = _parse_iso(s.get("processed_at"))
    if not dt:
        return {"state": s, "stale": False, "age_s": None}

    now = datetime.now(timezone.utc)
    age = (now - dt).total_seconds()
    return {"state": s, "stale": age > max_age_s, "age_s": age}

















@app.get("/api/actuators")
def get_actuators():
    """Recupera lo stato attuale di tutti gli attuatori dal simulatore"""
    try:
        # Interroga il simulatore REST
        res = requests.get(f"{SIMULATOR_URL}/api/actuators", timeout=5)
        res.raise_for_status()
        return res.json()
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Simulatore non raggiungibile")


@app.post("/api/actuators/{actuator_id}")
def command_actuator(actuator_id: str, command: ActuatorCommand):
    """Inoltra il comando di accensione/spegnimento al simulatore"""
    try:
        res = requests.post(f"{SIMULATOR_URL}/api/actuators/{actuator_id}", json={"state": command.state}, timeout=5)
        res.raise_for_status()
        return {"status": "success"}
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Simulatore non raggiungibile")
    




# --- ENDPOINT REGOLE (CRUD) ---
@app.get("/api/rules", response_model=List[RuleOut])
def list_rules():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules")
            return cur.fetchall()

@app.post("/api/rules", response_model=RuleOut, status_code=201)
def create_rule(rule: RuleIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO rules (`condition`, action_taken, actuator, enabled) VALUES (%s, %s, %s, %s)", 
                        (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0))
            new_id = cur.lastrowid
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s", (new_id,))
            return cur.fetchone()

@app.put("/api/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, rule: RuleIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE rules SET `condition`=%s, action_taken=%s, actuator=%s, enabled=%s WHERE id=%s",
                        (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0, rule_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s", (rule_id,))
            return cur.fetchone()

@app.delete("/api/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")
    return None