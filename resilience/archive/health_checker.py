import httpx, time

def check(url):
    try:
        r = httpx.get(url, timeout=2)
        return r.status_code == 200
    except:
        return False

while True:
    hasil = check("http://localhost:8001/health")
    print("Sehat" if hasil else "Mati")
    time.sleep(3)