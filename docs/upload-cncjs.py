import argparse
import json
import sys

import requests

parser = argparse.ArgumentParser()
parser.add_argument("filename", help="gcode file", type=str)
parser.add_argument(
    "-u",
    "--url",
    help="cncjs url (http://IP:PORT)",
    type=str,
    default="http://cncjs.local:8000",
)
parser.add_argument(
    "-U", "--username", help="cncjs api username", type=str, default="viaconstructor"
)
parser.add_argument(
    "-P", "--password", help="cncjs api password", type=str, default="password"
)
parser.add_argument(
    "-p", "--port", help="cncjs serial port", type=str, default="/dev/ttyACM0"
)
args = parser.parse_args()


url = f"{args.url}/api/signin"
myobj = {"token": "", "name": args.username, "password": args.password}
response = requests.post(url, json=myobj)
if response.text and response.text[0] == "{":
    data = json.loads(response.text)
    token = data.get("token")
    if not token:
        print("Login-error:", response.text)

    gcode = open(args.filename, "r").read()
    url = f"{args.url}/api/gcode"
    myobj = {"port": args.port, "name": "test.ngc", "gcode": gcode}
    response = requests.post(
        url, json=myobj, headers={"Authorization": f"Bearer {token}"}
    )
    data = json.loads(response.text)
else:
    print("Login-error:", response.text)
