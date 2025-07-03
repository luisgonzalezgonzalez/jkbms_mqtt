
#!/usr/bin/env python3

import socket
import struct
import configparser
import os
from pathlib import Path
import time
import json
import paho.mqtt.client as mqtt
import traceback

def get_config_variable(name, default='mandatory'):
    config_path = Path(__file__).resolve().parent / 'jkbms.ini'
    try:
        value = os.getenv(name)
        if value is not None:
            print(f"[CONFIG] {name} = {value} (fuente: variable de entorno)")
            return value
        config = configparser.ConfigParser()
        config.read(config_path)
        value = config['jkbms'][name]
        print(f"[CONFIG] {name} = {value} (fuente: {config_path})")
        return value
    except Exception as e:
        if default != 'mandatory':
            print(f"[CONFIG] {name} = {default} (valor por defecto)")
            return default
        print(f"[ERROR] No se pudo leer '{name}' desde {config_path}: {e}")
        exit(1)

def build_modbus_tcp_frame(unit_id, function_code, start_address, register_count):
    transaction_id = 0x0001
    protocol_id = 0x0000
    length = 6
    mbap = struct.pack(">HHHB", transaction_id, protocol_id, length, unit_id)
    pdu = struct.pack(">BHH", function_code, start_address, register_count)
    return mbap + pdu

def read_register(ip, port, unit_id, address, count=1):
    frame = build_modbus_tcp_frame(unit_id, 3, address, count)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((ip, port))
            s.sendall(frame)
            response = s.recv(256)
            if len(response) >= 9 + count * 2 and response[6] == unit_id and response[7] == 0x03:
                return response[9:9 + count * 2]
    except Exception as e:
        print(f"[ERROR] Lectura fallida en dirección 0x{address:04X}: {e}")
    return None

def publish_discovery(sensors, client, mqtt_topic , homeassistant_topic="homeassistant", debug=False):
    device = {
        "identifiers": ["jkbms"],
        "manufacturer": "JK",
        "model": "JK-BMS",
        "name": "JK BMS"
    }

    for sensor in sensors:
        unique_id = f"jkbms_{sensor['key_name']}"
        discovery_topic = f"{homeassistant_topic}/sensor/jkbms/{unique_id}/config"
        state_topic = f"{mqtt_topic}/state"

        payload = {
            "name": f"{sensor['name']}",
            "state_topic": state_topic,
            "unit_of_measurement": f"{sensor['unit']}",
            "value_template": f"{{{{ value_json.{sensor['key_name']} }}}}",
            "unique_id": f"{sensor['key_name']}",
            "device": device
        }

        if debug:
            print(f"[DISCOVERY] {discovery_topic} → {json.dumps(payload)}")

        client.publish(discovery_topic, json.dumps(payload), retain=True)

    #state_payload = json.dumps(bms_data)
    #if debug:
     #   print(f"[STATE] {mqtt_topic}/jkbms/state → {state_payload}")
    #lient.publish(f"{base_topic}/jkbms/state", state_payload, retain=True)

def main():
    ip = get_config_variable('modbus_ip')
    port = int(get_config_variable('modbus_port', '502'))
    unit_id = int(get_config_variable('modbus_unit', '1'))
    mqtt_host = get_config_variable('mqtt_server')
    mqtt_port = int(get_config_variable('mqtt_port', '1883'))
    mqtt_user = get_config_variable('mqtt_user', '')
    mqtt_pass = get_config_variable('mqtt_pass', '')
    query_seconds = int(get_config_variable('query_seconds', '30'))
    mqtt_topic = get_config_variable("mqtt_topic", "jkbms")
    homeassistant_mqtt_topic = get_config_variable("homeassistant_mqtt_topic", "homeassistant")
    debug_values = get_config_variable("debug_values", "false").lower() in ["1", "true", "yes"]

    sensors = [
        {"name": "Battery Voltage", "key_name": "battery_voltage", "address": 0x1292, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Battery Power", "key_name": "battery_power",     "address": 0x1294, "unit": "W", "type": "U_DWORD", "multiplier": 0.001},
        {"name": "Battery Current", "key_name": "battery_current", "address": 0x1298, "unit": "A", "type": "S_DWORD", "multiplier": 0.001},
        {"name": "Cell 00 Voltage", "key_name": "cell_00_voltage", "address": 0x1200, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 01 Voltage", "key_name": "cell_01_voltage", "address": 0x1202, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 02 Voltage", "key_name": "cell_02_voltage", "address": 0x1204, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 03 Voltage", "key_name": "cell_03_voltage", "address": 0x1206, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 04 Voltage", "key_name": "cell_04_voltage", "address": 0x1208, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 05 Voltage", "key_name": "cell_05_voltage", "address": 0x120A, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 06 Voltage", "key_name": "cell_06_voltage", "address": 0x120C, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 07 Voltage", "key_name": "cell_07_voltage", "address": 0x120E, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 08 Voltage", "key_name": "cell_08_voltage", "address": 0x1210, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 09 Voltage", "key_name": "cell_09_voltage", "address": 0x1212, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 10 Voltage", "key_name": "cell_10_voltage", "address": 0x1214, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 11 Voltage", "key_name": "cell_11_voltage", "address": 0x1216, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 12 Voltage", "key_name": "cell_12_voltage", "address": 0x1218, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 13 Voltage", "key_name": "cell_13_voltage", "address": 0x121A, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 14 Voltage", "key_name": "cell_14_voltage", "address": 0x121C, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "Cell 15 Voltage", "key_name": "cell_15_voltage", "address": 0x121E, "unit": "V", "type": "U_WORD", "multiplier": 0.001},
        {"name": "MOS Temperature", "key_name": "mos_temperature", "address": 0x128A, "unit": "C", "type": "S_WORD", "multiplier": 0.1},
        {"name": "Battery Temperature 1", "key_name": "battery_temperature_1", "address": 0x129C, "unit": "º", "type": "S_WORD", "multiplier": 0.1},
        {"name": "Battery Temperature 2", "key_name": "battery_temperature_2", "address": 0x129E, "unit": "º", "type": "S_WORD", "multiplier": 0.1},
        {"name": "Balance Current", "key_name": "balance_current", "address": 0x12A4, "unit": "mA", "type": "S_WORD"},
        {"name": "Battery SOC", "key_name": "battery_soc", "address": 0x12A6, "unit": "%", "type": "U_WORD", "bitmask": 0xFF}

    ]

    published_discovery = False
    client = None
    # intento conectarme al mqtt
    bms_data = {}


    while True:
        try:
            if client is None:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                if mqtt_user != "":
                    client.username_pw_set(mqtt_user, mqtt_pass)
                client.connect(mqtt_host, mqtt_port)
                client.loop_start()

            
            for sensor in sensors:
                count = 2 if "DWORD" in sensor["type"] else 1
                raw = read_register(ip, port, unit_id, sensor["address"], count)
                if raw:
                    if sensor["type"] == "U_WORD":
                        value = int.from_bytes(raw, byteorder='big', signed=False)
                    elif sensor["type"] == "S_WORD":
                        value = int.from_bytes(raw, byteorder='big', signed=True)
                    elif sensor["type"] == "U_DWORD":
                        value = int.from_bytes(raw, byteorder='big', signed=False)
                    elif sensor["type"] == "S_DWORD":
                        value = int.from_bytes(raw, byteorder='big', signed=True)
                    else:
                        continue

                    if "multiplier" in sensor:
                        value = round(value * sensor["multiplier"], 3)

                    #key = sensor["name"].lower().replace(" ", "_")
                    bms_data[sensor["key_name"]] = value

                    #topic = f"{mqtt_topic}/{key}"
                    #client.publish(topic, payload=value, retain=True)
            state_payload = json.dumps(bms_data)
            client.publish(f"{mqtt_topic}/state", state_payload, retain=True)
            if debug_values:
                 print(f"[STATE] {mqtt_topic}/state → {state_payload}")

            if bms_data and not published_discovery:
                 publish_discovery(sensors, client, mqtt_topic, homeassistant_mqtt_topic, debug_values)
                 published_discovery = True

        except Exception as e:
            try:
                print(f"[ERROR] Error al desconectar MQTT: {e}")
                traceback.print_exc()
                if client:
                    client.loop_stop()
                    client.disconnect()
                    client = None
                    print("[MQTT] Cliente desconectado para reconexión.")
            except Exception as disconn_err:
                print(f"[ERROR] Error al desconectar MQTT: {disconn_err}")
                traceback.print_exc()



            time.sleep(query_seconds)

if __name__ == "__main__":
    main()

