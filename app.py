import json
from flask import Flask, render_template, jsonify
import serial
import time
import threading

app = Flask(__name__)

latest_data = {
    "temperature": None,
    "humidity": None,
    "light": None,
    "mood": "dark"
}

DEBUG_LOGGING = False

def determine_mood(temp, humidity, light):
    """Determine plant mood based on sensor values."""
    if temp is not None and temp > 30:
        return "mood_hot"
    if temp is not None and temp < 15:
        return "mood_cold"
    if humidity is not None and humidity > 80:
        return "mood_humid"
    if humidity is not None and humidity < 30:
        return "mood_thirsty"
    if light is not None and light < 20:
        return "dark"
    if light is not None and light > 80:
        return "light"
    return "mood_happy"

def serial_reader_thread():
    try:
        ser = serial.Serial('COM4', 9600, timeout=1)
        print(f"Listening on {ser.port} at {ser.baudrate} baud.")
        while True:
            raw = ser.readline()
            if not raw:
                time.sleep(0.01)
                continue

            line = raw.decode('utf-8', errors='replace').strip()
            if DEBUG_LOGGING:
                print(f"[DEBUG] {line}")

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                if DEBUG_LOGGING:
                    print(f"[DEBUG] Non‑JSON: {line}")
                time.sleep(0.01)
                continue

            latest_data["temperature"] = data.get("temperature")
            latest_data["humidity"]    = data.get("humidity")
            latest_data["light"]       = data.get("light")
            latest_data["mood"]        = determine_mood(
                latest_data["temperature"],
                latest_data["humidity"],
                latest_data["light"]
            )

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nSerial reader stopped.")
    except Exception as e:
        print(f"Serial port error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

OLLAMA_MODEL = "gemma3:4b"
last_mood = None
last_message = None

def generate_ollama_message(temp, hum, mood):
    try:
        from ollama import chat, ChatResponse
        prompt = (
            f"I have a plant with temperature {temp}°C and humidity {hum}%, "
            f"feeling {mood.replace('_',' ')}. "
            "First, write one playful sentence as if the plant is speaking—but "
            "do NOT use any terms of endearment like 'darling and do NOT use words like Honestly'. Then give one short "
            "educational tip about caring for indoor plants."
        )
        resp: ChatResponse = chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.message.content.strip() or "Tip unavailable."
    except Exception as e:
        print(f"Ollama error: {e}")
        return f"I'm feeling {mood.replace('_',' ')}! Check your plant's needs."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/plant')
def plant_api():
    global last_mood, last_message, latest_data

    temp  = latest_data.get("temperature")
    hum   = latest_data.get("humidity")
    light = latest_data.get("light")
    mood  = latest_data.get("mood", "dark")

    if temp is not None and hum is not None and mood != last_mood:
        last_message = generate_ollama_message(temp, hum, mood)
        last_mood = mood
    elif last_message is None:
        last_message = "🌱 Waiting for sensor data…"

    return jsonify({
        "temperature": temp,
        "humidity":    hum,
        "light":       light,
        "mood":        mood,
        "message":     last_message
    })

if __name__ == '__main__':
    t = threading.Thread(target=serial_reader_thread, daemon=True)
    t.start()

    print("Starting Flask server at http://0.0.0.0:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)
