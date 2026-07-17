import socket

ip = "52.77.216.42"
ports = [3389, 22, 5985, 5986, 445, 139]

print(f"Testing port connectivity to {ip}...")
for port in ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect((ip, port))
        print(f"Port {port}: OPEN")
    except Exception as e:
        print(f"Port {port}: CLOSED ({e})")
    finally:
        s.close()
