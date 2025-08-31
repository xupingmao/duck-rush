import requests
import argparse

def get_location_by_ip(ip_address):
    url = f"http://ip-api.com/json/{ip_address}"
    response = requests.get(url)
    data = response.json()
    return {
    "country": data.get("country"),
    "city": data.get("city"),
    "latitude": data.get("lat"),
    "longitude": data.get("lon")
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="通过IP获取地址信息")
    parser.add_argument("ip", default="8.8.8.8", help="IP地址")
    args = parser.parse_args()
    location = get_location_by_ip(args.ip)
    print(location)