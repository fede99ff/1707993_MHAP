# SYSTEM DESCRIPTION:

**Project name:** Mars Habitat Automation Platform

This project is a distributed automation platform designed to monitor and manage the IoT ecosystem of a Mars habitat. 
The system integrates REST-based sensors to track environmental metrics and actuators to control habitat equipment.
The platform provides a real-time dashboard for data visualization and empowers users to define, modify, and delete automation rules.
These rules allow the system to autonomously trigger actuators, ensuring all environmental parameters remain within safety ranges.

# USER STORIES:

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

# CONTAINERS:

## CONTAINER_NAME: ingestion_service

### DESCRIPTION: 
The container is responsible for collecting raw data from the REST sensors exposed by the Mars simulator, putting them into a normalized internal format, and sharing them through the message broker.
It is the entry point of the asynchronous data pipeline and periodically polls the simulator sensor API.

### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

### PORTS: 
No ports are published externally by this container

### PERSISTENCE EVALUATION
Persistence of data is not required for this container because its responsibility is limited to polling the latest sensor readings, normalizing them, and publishing them.
If the container restarts, it can resume from the next polling cycle without recovering previous in-memory state.

### EXTERNAL SERVICES CONNECTIONS
ingestion_service connects to:
- the Mars simulator REST API (`http://simulator:8080`)
- RabbitMQ broker (`amqp://guest:guest@broker:5672/`)

### MICROSERVICES:

#### MICROSERVICE: data normalization and publishing
- TYPE: backend
- DESCRIPTION: polls the simulator sensor endpoints, transforms heterogeneous sensor payloads into a common normalized JSON event, and publishes the normalized event to the RabbitMQ fanout exchange `normalized_events`
- PORTS: none
- TECHNOLOGICAL SPECIFICATION:
Python, `requests` for HTTP polling, `pika` for RabbitMQ communication.
The service normalizes different sensor payload shapes such as single metric/value pairs, measurement arrays, particulate readings, and tank level data.
- SERVICE ARCHITECTURE:
Single-process worker architecture.
The service periodically calls `/api/sensors`, iterates through the available sensor identifiers, fetches `/api/sensors/{sensor_id}`, normalizes the result, and publishes the event to RabbitMQ.
Communication with downstream services is asynchronous and decoupled through the message broker.

- ENDPOINTS:

	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
	| GET | /api/sensors | Retrieve the list of simulator sensors (called on the external simulator) | 1, 10, 11 |
	| GET | /api/sensors/{sensor_id} | Retrieve one simulator sensor reading (called on the external simulator) | 1, 10, 11 |


## CONTAINER_NAME: db

### DESCRIPTION: 
Handles the data that need to be persistent in the system, namely the automation rules.
It guarantees that rules remain available even if other parts of the system are restarted.

### USER STORIES:
2) As a user, i want to be able to add an automation rule using an interface

3) As a user, i want to be able to delete an automation rule from the interface

4) As a user, i want to be able to modify an existing automation rule

5) As a user, i want to be able to read all the automation rule on the dashboard

8) As a user, i want my automation rules to be persistent even if the system is restarted

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

12) As a user i want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

### PORTS: 
3306:3306

### PERSISTENCE EVALUATION
Rules stored in MySQL must be persistent.
Persistence is granted by the Docker volume `db_data` mounted on `/var/lib/mysql`.
In addition, the schema is initialized through `init.sql`, which creates the `rules` table if it does not already exist.

### EXTERNAL SERVICES CONNECTIONS
None

### MICROSERVICES:

#### MICROSERVICE: mysql rules database
- TYPE: database
- DESCRIPTION: works as the persistent storage for automation rules and supports CRUD queries from the backend and read access from the rule engine
- PORTS: 3306
- TECHNOLOGICAL SPECIFICATION:
MySQL 8.0
- SERVICE ARCHITECTURE:
Works as an isolated database service inside the Docker network and accepts connections only from authenticated clients.

- DB STRUCTURE:

	**rules** :	| **id** | condition | action_taken | actuator | enabled | created_at |

## CONTAINER_NAME: rule_engine

### DESCRIPTION: 
The rule_engine container is responsible for checking, for every sensor event received from RabbitMQ, whether one or more enabled automation rules may apply to that sensor.
It reads candidate rules from MySQL, parses the textual condition, extracts a comparable numeric value from the normalized payload, and determines whether the rule can be matched and enforced through the corresponding actuator command.

### USER STORIES:

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

12) As a user i want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

### PORTS: 
No ports are published externally by this container

### PERSISTENCE EVALUATION
Persistence is required for the rules, but it is delegated to the MySQL container.
This container does not store persistent local data.

### EXTERNAL SERVICES CONNECTIONS
rule_engine connects to:
- RabbitMQ broker
- MySQL database
- Mars simulator actuator API

### MICROSERVICES:

#### MICROSERVICE: rule evaluation worker
- TYPE: backend
- DESCRIPTION: consumes normalized sensor events from RabbitMQ, extracts values from payloads, retrieves enabled rules from MySQL, parses condition expressions such as `sensor_id > threshold`, checks whether a rule matches the incoming reading, and calls the simulator actuator API when a rule is satisfied
- PORTS: none
- TECHNOLOGICAL SPECIFICATION:
Python, `pika` for message consumption, `pymysql` for database access, `requests` for actuator API invocation, `re` for parsing textual conditions.
Supported operators in the code are `>`, `<`, `>=`, `<=`, `==`, and `=`.
- SERVICE ARCHITECTURE:
Single worker connected to the `normalized_events` fanout exchange through a dedicated queue.
The worker follows an event-driven architecture and evaluates rules asynchronously on each incoming message.

Important note: in the current implementation the callback flow completes the full automation cycle.
When a rule condition is satisfied, the worker calls the simulator actuator endpoint and attempts to enforce the target actuator state.

- ENDPOINTS:

	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
	| POST | /api/actuators/{actuator_id} | Target simulator endpoint that can be called by the worker to set actuator state (external simulator API) | 9 |

## CONTAINER_NAME: backend

### DESCRIPTION:
This container exposes the main HTTP API of the system.
It provides CRUD operations for automation rules, a Server-Sent Events stream for pushing sensor and actuator updates to the dashboard, an endpoint for manual actuator control, and a helper endpoint to return the current in-memory sensor cache.

### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

2) As a user, i want to be able to add an automation rule using an interface

3) As a user, i want to be able to delete an automation rule from the interface

4) As a user, i want to be able to modify an existing automation rule

5) As a user, i want to be able to read all the automation rule on the dashboard

6) As a user, i want to be able to manually control (turn on or off) an activator from the dashboard

7) As a user, i want to be able to know the state of the actuators (ON/OFF)

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

12) As a user i want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

### PORTS:
8000:8000

### PERSISTENCE EVALUATION
The backend keeps an in-memory `sensor_cache` for the latest consumed events, but this cache is not persistent.
Persistent information, namely the automation rules, is delegated to the MySQL database.

### EXTERNAL SERVICES CONNECTIONS
backend connects to:
- MySQL database for rule CRUD
- RabbitMQ broker to consume normalized events
- Mars simulator REST API to read actuator state and manually command actuators

### MICROSERVICES:

#### MICROSERVICE: dashboard api
- TYPE: backend
- DESCRIPTION: exposes the REST API used by the frontend and aggregates live data coming from RabbitMQ and the simulator
- PORTS: 8000
- TECHNOLOGICAL SPECIFICATION:
FastAPI, Pydantic models, PyMySQL, Requests, RabbitMQ consumer thread, SSE through `StreamingResponse`, CORS enabled for web frontend integration.
- SERVICE ARCHITECTURE:
HTTP API plus background consumer architecture.
At startup, the backend launches a background RabbitMQ consumer thread that subscribes to normalized events and updates the in-memory cache.
The HTTP layer exposes CRUD operations and streams consolidated habitat state to the frontend through Server-Sent Events.

- ENDPOINTS:

	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
	| GET | /api/sensors/stream | SSE stream that pushes the current sensor cache, current actuator states, and a refresh flag for rules | 1, 7, 10, 11 |
	| GET | /api/sensors/current | Return the current in-memory sensor cache | 1, 11 |
	| GET | /api/rules | Read all automation rules from MySQL | 5 |
	| POST | /api/rules | Create a new automation rule | 2 |
	| PUT | /api/rules/{rule_id} | Update an existing automation rule | 4 |
	| DELETE | /api/rules/{rule_id} | Delete an automation rule | 3 |
	| POST | /api/actuators/{actuator_id} | Manually set actuator state by forwarding the command to the simulator | 6, 7 |


## CONTAINER_NAME: frontend

### DESCRIPTION:
This container serves the user-facing dashboard.
It provides visualization of sensor values, actuator states, the last update time, and a rule management interface for add/edit/delete operations.

### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

2) As a user, i want to be able to add an automation rule using an interface

3) As a user, i want to be able to delete an automation rule from the interface

4) As a user, i want to be able to modify an existing automation rule

5) As a user, i want to be able to read all the automation rule on the dashboard

6) As a user, i want to be able to manually control (turn on or off) an activator from the dashboard

7) As a user, i want to be able to know the state of the actuators (ON/OFF)

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

12) As a user i want the manual activation of a given actuator to last for 30 seconds even if there is a rule that would change the state of it

### PORTS:
3000:80

### PERSISTENCE EVALUATION
No persistent storage is required in this container.
It serves static assets and uses the backend API for all application data.

### EXTERNAL SERVICES CONNECTIONS
frontend connects to:
- backend API on port 8000

### MICROSERVICES:

#### MICROSERVICE: web dashboard
- TYPE: frontend
- DESCRIPTION: static single-page dashboard for live monitoring, rule CRUD operations, and manual actuator control
- PORTS: 80 internally, published as 3000 externally
- TECHNOLOGICAL SPECIFICATION:
Nginx serving a static `index.html`, Bootstrap 5 for styling, vanilla JavaScript for API calls, SSE for real-time updates.
- SERVICE ARCHITECTURE:
Single-page frontend architecture.
The page subscribes to the backend SSE stream, updates dashboard widgets in real time, loads rules through REST calls, and sends CRUD or actuator commands to the backend API.

- PAGES:

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| Dashboard | Shows sensor values, last update timestamp, actuator states and switches, and the rules table | web dashboard | 1, 5, 6, 7, 10, 11 |
	| Rule modal | Bootstrap modal used to add and edit automation rules | web dashboard | 2, 4 |
	| Delete interaction | Confirmation-based deletion from the rules table | web dashboard | 3 |

## CONTAINER_NAME: broker

### DESCRIPTION:
This container provides the asynchronous middleware used to decouple producers and consumers in the distributed system.
It hosts RabbitMQ and distributes normalized sensor events to all subscribed services.

### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

### PORTS:
5672:5672 and 
15672:15672

### PERSISTENCE EVALUATION
Message persistence is not currently configured at application level for the exchanged sensor events.
However, RabbitMQ runtime data is mounted on the `rabbitmq_data` Docker volume so that broker internal state is not entirely lost on container recreation.

### EXTERNAL SERVICES CONNECTIONS
None

### MICROSERVICES:

#### MICROSERVICE: message broker
- TYPE: backend
- DESCRIPTION: receives normalized events from ingestion_service and distributes them to backend and rule_engine through the fanout exchange `normalized_events`
- PORTS: 5672, 15672
- TECHNOLOGICAL SPECIFICATION:
RabbitMQ 3 management image, AMQP protocol, management UI enabled on port 15672.
- SERVICE ARCHITECTURE:
Broker-based publish/subscribe architecture.
The ingestion service publishes to a fanout exchange, while backend and rule_engine bind their own queues to consume the same stream independently.


## CONTAINER_NAME: simulator

### DESCRIPTION:
This container runs the provided Mars IoT simulator used as environment for the project.
It exposes REST endpoints for sensors and actuators and acts as the source of raw telemetry as well as the target of actuator commands.

### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

6) As a user, i want to be able to manually control (turn on or off) an activator from the dashboard

7) As a user, i want to be able to know the state of the actuators (ON/OFF)

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

### PORTS:
8080:8080

### PERSISTENCE EVALUATION
Persistence is not managed by the application code of the project.
The simulator is included in the Docker Compose orchestration through a prebuilt image and is treated as an infrastructural dependency rather than a component implemented by the team.

### EXTERNAL SERVICES CONNECTIONS
None from the project point of view

### MICROSERVICES:

#### MICROSERVICE: mars habitat simulator api
- TYPE: backend
- DESCRIPTION: provides REST endpoints for reading sensors, reading actuators, and setting actuator state
- PORTS: 8080
- TECHNOLOGICAL SPECIFICATION:
Prebuilt simulator image `mars-iot-simulator:multiarch_v1`
- SERVICE ARCHITECTURE:
Prebuilt service integrated through REST by ingestion_service, backend, and rule_engine, and started through the project Docker Compose configuration.

- ENDPOINTS:

	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
	| GET | /api/sensors | Return available sensors | 1, 10, 11 |
	| GET | /api/sensors/{sensor_id} | Return one sensor reading | 1, 10, 11 |
	| GET | /api/actuators | Return current actuator states | 7 |
	| POST | /api/actuators/{actuator_id} | Set actuator state | 6, 9 |
