import os
import threading
import json
import time
import asyncio
import requests
import pika
import pymysql
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# --- CONFIGURAZIONE ---
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "mars_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mars_password")
DB_NAME = os.getenv("DB_NAME", "rules_db")
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@broker:5672/")
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://simulator:8080")

sensor_cache = {}
rules_updated_trigger = False 

app = FastAPI(title="Mars Dashboard Backend - Full SSE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def rabbitmq_consumer():
    connection = None
    while connection is None:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
        except:
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
                sensor_cache[sid] = event # Salviamo tutto l'evento
        except: pass

    channel.basic_consume(queue=result.method.queue, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

@app.on_event("startup")
def startup_event():
    threading.Thread(target=rabbitmq_consumer, daemon=True).start()

class RuleIn(BaseModel):
    condition: str
    action_taken: str
    actuator: str
    enabled: bool = True

class RuleOut(RuleIn):
    id: int

class ActuatorCommand(BaseModel):
    state: str

def get_conn():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor, autocommit=True
    )

@app.get("/api/sensors/stream")
async def sensors_stream():
    async def event_generator():
        global rules_updated_trigger
        last_payload = ""
        while True:
            try:
                res = requests.get(f"{SIMULATOR_URL}/api/actuators", timeout=1)
                actuators_data = res.json().get("actuators", {})
            except:
                actuators_data = {}

            full_state = {
                "sensors": sensor_cache,
                "actuators": actuators_data,
                "refresh_rules": rules_updated_trigger
            }
            
            payload = json.dumps(full_state)
            if payload != last_payload:
                yield f"event: habitat_update\ndata: {payload}\n\n"
                last_payload = payload
                if rules_updated_trigger:
                    rules_updated_trigger = False 
            
            await asyncio.sleep(1)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/rules", response_model=List[RuleOut])
def list_rules():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules")
            return cur.fetchall()

@app.post("/api/rules", response_model=RuleOut)
def create_rule(rule: RuleIn):
    global rules_updated_trigger
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO rules (`condition`, action_taken, actuator, enabled) VALUES (%s, %s, %s, %s)", 
                        (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0))
            new_id = cur.lastrowid
            rules_updated_trigger = True
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s", (new_id,))
            return cur.fetchone()

@app.put("/api/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, rule: RuleIn):
    global rules_updated_trigger
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE rules SET `condition`=%s, action_taken=%s, actuator=%s, enabled=%s WHERE id=%s",
                        (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0, rule_id))
            rules_updated_trigger = True
            cur.execute("SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s", (rule_id,))
            return cur.fetchone()

@app.delete("/api/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    global rules_updated_trigger
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
            rules_updated_trigger = True
    return None

@app.post("/api/actuators/{actuator_id}")
def command_actuator(actuator_id: str, command: ActuatorCommand):
    try:
        requests.post(f"{SIMULATOR_URL}/api/actuators/{actuator_id}", json={"state": command.state}, timeout=5)
        return {"status": "success"}
    except:
        raise HTTPException(status_code=502)