
import logging
import json
try:
    import paho.mqtt.client as mqtt
except ImportError:
    logging.warning("Paho MQTT not installed. Run `pip install paho-mqtt`")
    mqtt = None

# Default Broker from .env or fallback
import os
BROKER = os.getenv("MQTT_BROKER", "192.168.1.50") # Default placeholder
PORT = 1883

def mqtt_publish(topic: str, payload: str, broker: str = BROKER) -> str:
    """
    Publishes a message to an MQTT topic.
    
    Args:
        topic (str): The MQTT topic (e.g., "home/livingroom/light/set")
        payload (str): The message content (e.g., "ON" or '{"state": "ON"}')
        broker (str): IP address of the MQTT Broker.
        
    Returns:
        str: Status message.
    """
    if not mqtt:
        return "Error: paho-mqtt library is missing."
        
    try:
        client = mqtt.Client(protocol=mqtt.MQTTv5)
        client.connect(broker, PORT, 60)
        client.publish(topic, payload)
        client.disconnect()
        return f"Successfully published to {topic}: {payload}"
    except Exception as e:
        return f"MQTT Error: {str(e)}"

def mqtt_subscribe(topic: str, duration: int = 5, broker: str = BROKER) -> str:
    """
    Subscribes to a topic for a short duration to listen for a response.
    BLOCKING CALL. Use with caution.
    """
    if not mqtt: return "Error: Library missing"
    
    messages = []
    
    def on_message(client, userdata, msg):
        messages.append(msg.payload.decode())
        
    try:
        client = mqtt.Client(protocol=mqtt.MQTTv5)
        client.on_message = on_message
        client.connect(broker, PORT, 60)
        client.subscribe(topic)
        client.loop_start()
        
        import time
        time.sleep(duration)
        
        client.loop_stop()
        client.disconnect()
        
        if messages:
            return f"Received {len(messages)} messages: {messages}"
        return "No messages received in window."
    except Exception as e:
        return f"MQTT Error: {str(e)}"
