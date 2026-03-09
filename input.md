# input.md

# SYSTEM DESCRIPTION:
Mars Habitat Automation Platform is a distributed automation platform designed to monitor and manage the IoT ecosystem of a Mars habitat. 
The system integrates REST-based sensors to track environmental metrics and actuators to control habitat equipment.
The platform provides a real-time dashboard for data visualization and empowers users to define, modify, and delete automation rules.
These rules allow the system to autonomously trigger actuators, ensuring all environmental parameters remain within safety ranges.
## 0. User Stories
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard
2) As a user, i want to be able to add an automation rule using an interface
3) As a user, i want to be able to delete an automation rule from the interface
4) As a user, i want to be able to modify an existing automation rule
5) As a user, i want to be able to read all the automation rule on the dashboard
6) As a user, i want to be able to manually control (turn on or off) an activator from the dashboard
7) As a user, i want to be able to know the state of the actuators (ON/OFF)
8) As a user, i want my automation rules to be persistent even if the system is restarted
9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule
10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically
11) As a user, i want to be able to read all the reading of the data from the REST sensors
12) As a user i want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

## 1. Assumptions

The following assumptions are used in the current design:
- the simulator is reachable at `http://simulator:8080` inside docker-compose networking
- all sensors are globally visible
- only the latest sensor state is required in memory
- automation rules follow the simple IF-THEN model defined by the assignment
- actuators are controlled only through REST with payload `{"state":"ON"}` or `{"state":"OFF"}`

---

## 2. Internal standard event schema

### 2.1Purpose
The system receives device data in heterogeneous formats.  
To decouple ingestion, rule evaluation, state caching, and presentation, all incoming data is transformed into a single internal event schema.

This schema is used on RabbitMQ exchanges/queues and inside backend services.


### 2.2Standard sensor event schema

```json
{
  "event_id": "uuid",
  "event_type": "sensor.reading",
  "timestamp": "2026-03-09T18:20:31Z",
  "source_type": "rest",
  "source_name": "greenhouse_temperature",
  "schema_family": "rest.scalar.v1",
  "value": 27.4,
  "unit": "C",
  "status": "OK",
  "raw_payload": {
    "temperature": 27.4,
    "unit": "C"
  }
}
```

### 2.3 Field description

| Field | Type |  | Description |
|---|---|---:|---|
| `event_id` | string |  | unique identifier of the event |
| `event_type` | string |  | logical type of the event, e.g. `sensor.reading` |
| `timestamp` | string |  | ISO 8601 timestamp of normalization/publication |
| `source_type` | string |  | source category, e.g. `rest` |
| `source_name` | string |  | simulator sensor identifier |
| `schema_family` | string |  | schema family associated with the source |
| `value` | number/string/object |  | normalized reading value |
| `unit` | string/null |  | measurement unit if applicable |
| `status` | string |  | acquisition status, e.g. `OK`, `ERROR` |
| `raw_payload` | object |  | original source payload for traceability/debugging |

### 2.4 Notes on normalization
For simple scalar sensors, `value` contains a single numeric value.

Examples:
- scalar temperature sensor → `value: 27.4`
- chemistry payload → `value: {"ph": 6.8}`
- particulate payload → `value: {"pm25": 18.2}`

### 2.5 Example mappings from simulator sources

#### Example — scalar REST sensor
Source sensor:
- `greenhouse_temperature`
- schema family: `rest.scalar.v1`

Normalized event:
```json
{
  "event_id": "5a0b9b34-8d17-4a27-a1af-72dbd7a0c001",
  "event_type": "sensor.reading",
  "timestamp": "2026-03-09T18:20:31Z",
  "source_type": "rest",
  "source_name": "greenhouse_temperature",
  "schema_family": "rest.scalar.v1",
  "value": 27.4,
  "unit": "C",
  "status": "OK",
  "raw_payload": {
    "temperature": 27.4,
    "unit": "C"
  }
}
```
---

## 3. Internal actuator command schema

### 3.1 Purpose
Rule evaluation is decoupled from actuator invocation through a dedicated internal command event.

### 3.2 Standard actuator command event

```json
{
  "command_id": "uuid",
  "event_type": "actuator.command",
  "timestamp": "2026-03-09T18:21:02Z",
  "actuator_name": "cooling_fan",
  "target_state": "ON",
  "trigger_rule_id": "rule-001",
  "triggering_event_id": "5a0b9b34-8d17-4a27-a1af-72dbd7a0c001"
}
```

### 3.3 Field description

| Field | Type |  | Description |
|---|---|---:|---|
| `command_id` | string |  | unique identifier of the command |
| `event_type` | string |  | must be `actuator.command` |
| `timestamp` | string |  | command creation timestamp |
| `actuator_name` | string |  | target actuator identifier |
| `target_state` | string |  | target actuator state: `ON` or `OFF` |
| `trigger_rule_id` | string |  | identifier of the rule that generated the command |
| `triggering_event_id` | string |  | sensor event that caused the rule to fire |

---

## 4. External actuator REST payload

The simulator actuator API is invoked with the following payload:

```json
{
  "state": "ON"
}
```

or

```json
{
  "state": "OFF"
}
```

This payload is generated by `actuator-service` from the internal `actuator.command` event.

---

## 5. Actuator state update event

### 5.1 Purpose
After invoking the simulator actuator API, the actuator service emits an event to notify the rest of the platform.

### 5.2 Standard actuator state event

```json
{
  "event_id": "uuid",
  "event_type": "actuator.state.changed",
  "timestamp": "2026-03-09T18:21:03Z",
  "actuator_name": "cooling_fan",
  "state": "ON",
  "result": "SUCCESS",
  "command_id": "uuid"
}
```

---

## 6. Rule model

### 6.1 Purpose
Automation rules define reactive behavior triggered by incoming sensor events.

### 6.2 Rule syntax
Rules follow the assignment model:

**IF** `<sensor_name>` `<operator>` `<value>` `[unit]`  
**THEN** `set <actuator_name> to ON | OFF`

Supported operators:
- `<`
- `<=`
- `=` or `==``
- `>`
- `>=`

### 6.3 Internal persistent rule model

```json
{
  "rule_id": "rule-001",
  "name": "Turn on cooling fan when greenhouse temperature is high",
  "enabled": true,
  "sensor_name": "greenhouse_temperature",
  "operator": ">",
  "threshold_value": 28,
  "unit": "C",
  "actuator_name": "cooling_fan",
  "target_state": "ON"
}
```

### 6.4 Rule fields

| Field | Type |  | Description |
|---|---|---:|---|
| `rule_id` | string |  | unique rule identifier |
| `name` | string |  | human-readable rule name |
| `enabled` | boolean |  | whether the rule is active |
| `sensor_name` | string |  | sensor identifier |
| `operator` | string |  | comparison operator |
| `threshold_value` | number |  | threshold value used in evaluation |
| `unit` | string/null |  | expected unit |
| `actuator_name` | string | | actuator to control |
| `target_state` | string |  | `ON` or `OFF` |

### 6.5 Example

**IF** greenhouse_temperature > 28 C  
**THEN** set cooling_fan to ON


