# input.md

# SYSTEM DESCRIPTION:
Mars Habitat Automation Platform is a distributed automation platform designed to monitor and manage the IoT ecosystem of a Mars base. The system integrates REST-based sensors to track environmental metrics and actuators to control habitat equipment. The platform extract data from the sensors and provides a real-time dashboard for data visualization while empowering users to define, modify, and delete automation rules. These rules allow the system to autonomously trigger actuators, ensuring all environmental parameters remain within safety ranges.
## 0. User Stories
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard
2) As a user, i want to be able to add an automation rule from the dashboard
3) As a user, i want to be able to delete an automation rule from the dashboard
4) As a user, i want to be able to modify an existing automation rule from the dashboard
5) As a user, i want to be able to read all the automation rule on the dashboard
6) As a user, i want to be able to manually control (turn on or off) an activator from the dashboard
7) As a user, i want to be able to know the state of the actuators (ON/OFF)
8) As a user, i want my automation rules to be persistent even if the system is restarted
9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule
10) As a user, I want the reading of the sensor in the dashboard to be automatically update periodically
11) As a user, I want to be able to read all the reading of the data from the REST sensors
12) As a user I want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

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


### 2.2 Standard sensor event schema

```json
{
  "source": "greenhouse_temperature",
  "type": "REST_SENSOR_READING",
  "status": "ok",
  "processed_at": "2026-03-09T18:20:31+00:00",
  "payload": {
    "metric": "temperature",
    "value": 27.4,
    "unit": "C"
  }
}
```

### 2.3 Field description

| Field          | Type   | Description                                            |
| -------------- | ------ | ------------------------------------------------------ |
| `source`       | string | identifier of the sensor, taken from `sensor_id`       |
| `type`         | string | normalized event type, currently `REST_SENSOR_READING` |
| `status`       | string | acquisition status, default `ok` if not provided       |
| `processed_at` | string | UTC timestamp generated during normalization  |
| `payload`      | object | normalized sensor-specific content                     |

### 2.4 Notes on normalization
For simple scalar sensors, `payload.value` contains a single numeric value.

Examples:
- scalar temperature sensor → `value: 27.4`
- chemistry payload → `value: {"ph": 6.8}`
- particulate payload → `value: {"pm25": 18.2}`

### 2.5 Example mappings from simulator sources

#### Example — scalar REST sensor
Source sensor:
- `greenhouse_temperature`

Normalized event:
```json
{
  "source": "greenhouse_temperature",
  "type": "REST_SENSOR_READING",
  "status": "ok",
  "processed_at": "2026-03-09T18:20:31+00:00",
  "payload": {
    "metric": "temperature",
    "value": 27.4,
    "unit": "C"
  }
}
```
---

---

## 3. External actuator REST payload

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

In the current implementation, this payload is generated directly by the backend or the rule engine when invoking the simulator actuator endpoint.

---

## 4. Actuator control and state handling

### 4.1 Purpose
The platform controls actuators through REST calls to the simulator and retrieves their current state for dashboard visualization.

### 4.2 Actuator invocation
When a rule is triggered, or when a user manually controls an actuator from the dashboard, the platform invokes the simulator actuator API through an HTTP request.

The simulator actuator API is called with the following payload:

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

### 4.3 Result handling
Actuator execution is currently handled synchronously through the HTTP response returned by the simulator.

### 4.4 Actuator state retrieval
The current actuator state is retrieved by the backend from the simulator actuator endpoints and included in the data exposed to the dashboard.


---

## 5. Rule model

### 5.1 Purpose
Automation rules dfine reactive behavior triggered by incoming sensor events.

### 5.2 Rule syntax
Rules follow the assignment model:

**IF** `<sensor_name>` `<operator>` `<value>` `[unit]`  
**THEN** `set <actuator_name> to ON | OFF`

Supported operators:
- `<`
- `<=`
- `=`
- `==`
- `>`
- `>=`

### 5.3 Internal persistent rule model

```json
{
  "id": 1,
  "condition": "greenhouse_temperature > 28 C",
  "action_taken": "ON",
  "actuator": "cooling_fan",
  "enabled": true
}
```
### 5.4 Rule fields
| Field          | Type    | Description                                                                      |
| -------------- | ------- | -------------------------------------------------------------------------------- |
| `id`           | integer | unique rule identifier                                                           |
| `condition`    | string  | rule condition stored as a parsable string, e.g. `greenhouse_temperature > 28 C` |
| `action_taken` | string  | target actuator state, `ON` or `OFF`                                             |
| `actuator`     | string  | actuator identifier                                                              |
| `enabled`      | boolean | whether the rule is active (see user story 12)                                   |
