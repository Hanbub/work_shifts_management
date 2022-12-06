import json
import requests
import argparse
import os
API_KEY = os.environ['API_KEY']
parser = argparse.ArgumentParser()
parser.add_argument('event')
parser.add_argument('email')
parser.add_argument('start', nargs='?')
parser.add_argument('end', nargs='?')
args = parser.parse_args()
arg_event = args.event
arg_email = args.email
arg_start = args.start
arg_end = args.end
print(args)
print(f"event:{arg_event}")
print(f"email:{arg_email}")
print(f"start:{arg_start}")
print(f"end:{arg_end}")
headers = {'Content-type': 'application/json'}
if arg_event == "add":
    try:
        url = "http://localhost:8080/shift/{email}"
        if isinstance(arg_start, int) and isinstance(arg_end, int) and isinstance(arg_email, str):
            data_dumped = json.dumps({
                "email": arg_email,
                'APP_API_KEY': API_KEY
            })
            shift_response = requests.post(f"{url}", data=data_dumped, headers=headers)
            print(shift_response.json())
        else:
            print("SHIFT_WRONG_DATATYPE_INPUT")
    except Exception as shift_cli_error:
        print(f"shift_cli_error {shift_cli_error}")
elif arg_event == "report":
    try:
        url = "http://localhost:8080/reports/monthly/{employee_email}"
        if isinstance(arg_email, str):
            data_dumped = json.dumps({
                "employee_email": arg_email,
                'APP_API_KEY': API_KEY
            })
            report_response = requests.post(f"{url}", data=data_dumped, headers=headers)
            print(report_response.json())
        else:
            print("REPORT_WRONG_DATATYPE_INPUT")
    except Exception as report_cli_error:
        print(f"report_cli_error {report_cli_error}")
else:
    print('WRONG_EVENT')
