# SYSTEM DESCRIPTION:

[Name of the project] is a distributed automation platform designed to monitor and manage the IoT ecosystem of a Mars habitat. 
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


# CONTAINERS:

## CONTAINER_NAME: ingestion_service

### DESCRIPTION: 


### USER STORIES:
1) As a user, i want to be able to see when it was the last update of the reading of the REST sensor in a dashboard

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

10) As a user, i want the reading of the sensor in the dashboard to be automatically update periodically

11) As a user, i want to be able to read all the reading of the data from the REST sensors

### PORTS: 
<used ports>

### DESCRIPTION:
The container is responsible of collecting the raw data from the REST sensors, to put them in a normalized form
and to share them with via the message broker. 

### PERSISTENCE EVALUATION
persistence of data is not required to ingest and normalize the latest reading of the sensors

### EXTERNAL SERVICES CONNECTIONS
ingestion_service does not connect to external services

### MICROSERVICES:

#### MICROSERVICE: data normalization
- TYPE: backend
- DESCRIPTION: ingest and normalize the data collected by polling them from the IoT server
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

#### MICROSERVICE: normalized data sharing
- TYPE: backend
- DESCRIPTION: share to the message broker the normalized data to make it availble to other components of the system
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |


## CONTAINER_NAME: db

### DESCRIPTION: 
<description of the container>

### USER STORIES:
2) As a user, i want to be able to add an automation rule using an interface

3) As a user, i want to be able to delete an automation rule from the interface

4) As a user, i want to be able to modify an existing automation rule

5) As a user, i want to be able to read all the automation rule on the dashboard

8) As a user, i want my automation rules to be persistent even if the system is restarted

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

### PORTS: 
3306:3306

### DESCRIPTION:
Handles the data that need to be persistent in the system i.e. the automation rules. In particoular it grants us that the
rules saved in the system are persistent in the case that any other part of the system (also IoT server) are restarted.

### PERSISTENCE EVALUATION
Rules stored in the MySQL DB must be persistent. persistence is granted by the Docker Volume (db_data) in the directory /var/lib/mysql

### EXTERNAL SERVICES CONNECTIONS
None

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: database
- DESCRIPTION: Works as a DB for the automation rules, making them persistent and handling the incoming CRUD qury.
- PORTS: 3306
- TECHNOLOGICAL SPECIFICATION:
MySQL
- SERVICE ARCHITECTURE: 
Works in isolation, accept connections from the outside only if right credential are presented.

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**** :	| **id** | condition | action_taken | actuator | enabled | created_at |

## CONTAINER_NAME: rule_engine

### DESCRIPTION: 
<description of the container>

### USER STORIES:

9) As a user, i want the system to be able to recognize changes in the values registered by the sensors and enforce the corresponding automation rule

### PORTS: 
<used ports>

### DESCRIPTION:
The rule_container is responsible to check at every reading of the sensors if any of the conditions inside the automation rules is satisfied and if so
to trigger an actuator state update, according to what is stated in the corresponding rule. Rule are always checked as an user may add, delete or modify one at any time.

### PERSISTENCE EVALUATION
Persistence is required to the rules, which are not directly linked to the container as it only reads them.

### EXTERNAL SERVICES CONNECTIONS
rule_engine does not connect to external services

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>

## CONTAINER_NAME: backend

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>

## CONTAINER_NAME: frontend

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>

## CONTAINER_NAME: <name of the container>

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>

