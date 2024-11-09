from json import loads
import requests
def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    return f"{hours} hours, {minutes} mins, {remaining_seconds} secs"

def getCode() -> dict:
    url = 'https://raw.githubusercontent.com/SkalaFrost/m-data/refs/heads/main/bits.json'
    request = requests.get(url=url, headers={"Accept": "application/json"})
    if request.status_code == 200:
        body =  request.text
        return loads(body)
    