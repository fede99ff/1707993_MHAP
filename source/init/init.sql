CREATE TABLE rules (

    id INT AUTO_INCREMENT PRIMARY KEY
    condition VARCHAR(255),
    action_taken VARCHAR(255),
    actuator VARCHAR(255)    
 );

INSERT INTO rules (`condition`, action_taken, actuator) 
VALUES 
-- Gestione Caldo (Ventola di raffreddamento)
    ('greenhouse_temperature > 30.0', 'ON', 'cooling_fan'),
    ('greenhouse_temperature < 25.0', 'OFF', 'cooling_fan'),
    
    -- Gestione Freddo (Riscaldamento dell'habitat)
    ('greenhouse_temperature < 150.0', 'ON', 'habitat_heater'),
    ('greenhouse_temperature > 200.0', 'OFF', 'habitat_heater'),
    
    -- Gestione Umidità (Umidificatore all'ingresso)
    -- (Assicurati che 'humidity' sia il nome corretto del sensore che invia il simulatore)
    ('humidity < 30.0', 'ON', 'entrance_humidifier'),
    ('humidity > 45.0', 'OFF', 'entrance_humidifier'),
    
    -- Gestione Qualità dell'aria (Ventilazione del corridoio)
    ('air_quality_pm25 > 50.0', 'ON', 'hall_ventilation'),
    ('air_quality_pm25 < 20.0', 'OFF', 'hall_ventilation');