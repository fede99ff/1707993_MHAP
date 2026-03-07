USE rules_db;

CREATE TABLE IF NOT EXISTS rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  `condition` VARCHAR(255) NOT NULL,
  action_taken VARCHAR(16) NOT NULL,
  actuator VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO rules (`condition`, action_taken, actuator) VALUES
  ('greenhouse_temperature > 30.0', 'ON',  'cooling_fan'),
  ('greenhouse_temperature < 25.0', 'OFF', 'cooling_fan'),

  ('greenhouse_temperature < 15.0', 'ON',  'habitat_heater'),
  ('greenhouse_temperature > 20.0', 'OFF', 'habitat_heater'),

  ('entrance_humidity < 30.0', 'ON',  'entrance_humidifier'),
  ('entrance_humidity > 45.0', 'OFF', 'entrance_humidifier'),

  ('air_quality_pm25 > 50.0', 'ON',  'hall_ventilation'),
  ('air_quality_pm25 < 20.0', 'OFF', 'hall_ventilation');