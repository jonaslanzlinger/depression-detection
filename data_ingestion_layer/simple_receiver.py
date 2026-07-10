import socket
import wave

HOST = '0.0.0.0'
PORT = 8000
OUTPUT_FILE = "clean_slave_recording.wav"

print(f"🎧 Listening on Port {PORT}...")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)

conn, addr = server.accept()
print(f"✅ Board connected from {addr}!")

with wave.open(OUTPUT_FILE, 'wb') as wav:
    wav.setnchannels(1)      # Mono
    wav.setsampwidth(2)      # 16-bit
    wav.setframerate(16000)
    
    print("🔴 Recording... (Press Ctrl+C to stop)")
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            wav.writeframes(data)
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")

conn.close()
server.close()
