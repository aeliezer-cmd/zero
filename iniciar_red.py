"""Launch a separate LAN listener without interrupting the local instance."""
import socket
import webbrowser
import threading
import urllib.request
import app

PORT = 8001

def addresses():
    result=set()
    try:
        result.update(socket.gethostbyname_ex(socket.gethostname())[2])
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1',80))
            result.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in result if not ip.startswith('127.') and ip!='0.0.0.0')

if __name__=='__main__':
    url=f'http://127.0.0.1:{PORT}/'
    try:
        server=app.ThreadingHTTPServer(('0.0.0.0',PORT),app.Handler)
    except OSError:
        print('El puerto 8001 ya está ocupado. Si Zero está abierto en red, use su enlace existente.')
        raise SystemExit(1)
    app.initialize()
    print('ZERO EN RED — Mantenga esta ventana abierta.\n')
    for ip in addresses():
        print(f'En las otras computadoras abra: http://{ip}:{PORT}/')
    print('\nTodos los equipos deben estar en la misma red. Cierre esta ventana para detener el acceso de red.')
    threading.Timer(0.8,lambda:webbrowser.open(url)).start()
    server.serve_forever()
