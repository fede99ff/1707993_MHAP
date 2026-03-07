import os
from typing import List, Optional

import pymysql
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "mars_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mars_password")
DB_NAME = os.getenv("DB_NAME", "rules_db")


app = FastAPI(title="Mars Rules Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


class RuleIn(BaseModel):
    condition: str = Field(..., examples=["greenhouse_temperature > 30.0"])
    action_taken: str = Field(..., examples=["ON", "OFF"])
    actuator: str = Field(..., examples=["cooling_fan"])
    enabled: bool = True


class RuleOut(RuleIn):
    id: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/rules", response_model=List[RuleOut])
def list_rules(enabled: Optional[bool] = None):
    sql = "SELECT id, `condition`, action_taken, actuator, enabled FROM rules"
    params = []
    if enabled is not None:
        sql += " WHERE enabled = %s"
        params.append(1 if enabled else 0)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return rows


@app.post("/api/rules", response_model=RuleOut, status_code=201)
def create_rule(rule: RuleIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rules (`condition`, action_taken, actuator, enabled) VALUES (%s, %s, %s, %s)",
                (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0),
            )
            new_id = cur.lastrowid

            cur.execute(
                "SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s",
                (new_id,),
            )
            row = cur.fetchone()
    return row


@app.put("/api/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, rule: RuleIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE rules SET `condition`=%s, action_taken=%s, actuator=%s, enabled=%s WHERE id=%s",
                (rule.condition, rule.action_taken, rule.actuator, 1 if rule.enabled else 0, rule_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")

            cur.execute(
                "SELECT id, `condition`, action_taken, actuator, enabled FROM rules WHERE id=%s",
                (rule_id,),
            )
            row = cur.fetchone()
    return row


@app.delete("/api/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")
    return None