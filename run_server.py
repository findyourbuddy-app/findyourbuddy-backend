import socket
import sys
import uvicorn

def is_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except Exception:
        return False

def main():
    preferred_ports = [8001, 8000, 8080, 8088]
    selected_port = None

    for p in preferred_ports:
        if is_port_available("0.0.0.0", p):
            selected_port = p
            break

    if selected_port is None:
        selected_port = 8001

    print("\n=======================================================")
    print("FindYourBuddy FastAPI Backend Starting...")
    print(f"Selected Port: {selected_port} (Auto-detected free port)")
    print(f"Access URL: http://0.0.0.0:{selected_port}")
    print("=======================================================\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=selected_port, reload=True)

if __name__ == "__main__":
    main()
