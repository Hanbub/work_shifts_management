from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
import databases
import requests
import sqlalchemy
import logging
import uvicorn
import json
import os
from datetime import datetime, timedelta
import calendar
import zipfile
from io import StringIO, BytesIO
import boto3

custom_logger = logging.getLogger('custom_logger')
APP_API_KEY = os.environ['APP_API_KEY']
DATABASE_URL = os.environ["DATABASE_URL"]
EMAIL_API_KEY = os.environ['EMAIL_API_KEY']
EMAIL_DOMAIN_NAME = os.environ['EMAIL_DOMAIN_NAME']
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_CLIENT = boto3.client('s3')

app = FastAPI()

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"])

db = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

query_get_last_shift_today = """
select * from TimeShifts t
where t.email='%s' and 
      t."start" >= '%s'::timestamp and 
      t."start" < current_date::timestamp + interval '1 day'
order by t.start desc
limit 1
"""

query_insert_new_shift = """
insert into TimeShifts
(email,"start") values ('%s','%s'::timestamp)
"""

query_update_existing_shift = """
update TimeShifts
set "end" = '%s'::timestamp
where "start" = (select max("start") from TimeShifts
             where email = '%s' and 
                   "start" >= current_date::timestamp and
                   "start" < current_date::timestamp + interval '1 day')
"""

query_get_last_shift_yesterday = """
select *,current_date::timestamp from TimeShifts t 
where t.email ='%s' and
      t."start" >= current_date::timestamp - interval '1 day' and 
      t."start" < current_date::timestamp and t."end" isnull 
order by t."start" asc
limit 1
"""

query_update_unclosed_yesterday_shift = """
update TimeShifts
set "end" = current_date::timestamp - interval '1 second'
where email = '%s' and 
      "start" = '%s'
"""

query_move_and_close_yesterdays_shift_today = """
insert into TimeShifts
(email,"start","end") values ('%s',current_date::timestamp, '%s'::timestamp)
"""

query_get_monthly_records = """
    select * from TimeShifts t 
    where email = '%s' and 
    extract('month' from "start") = extract('month' from current_date)
    """


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


# misunderstood task
@app.post('/shift/{email}')
async def shift(email: Request):
    data = await email.json()
    try:
        apikey = data['API_KEY']
        if apikey != APP_API_KEY:
            raise Exception('WRONG_API_KEY')
        email_value = data['email']
    except Exception as api_key_error:
        return JSONResponse(content={"error": str(api_key_error)})
    # bugfix replace microseconds on 0 to wrap in error unclosed events
    track_timestamp = datetime.utcnow().replace(microsecond=0)
    update_obj = {"email": email_value,
                  "start": None,
                  "end": None}

    # get last shift today from db
    last_shift_today = await db.fetch_one(query_get_last_shift_today % email_value)
    # first enter event today
    if not last_shift_today:
        # check yesterday if unclosed -> close at 23:59:59 yesterday and open at 00:00:00 today
        last_shift_yesterday = await db.fetch_one(query_get_last_shift_yesterday % email)
        if not last_shift_yesterday:  # wrap case when there is no unclosed time periods from yesterday
            update_obj['start'] = track_timestamp
        else:  # wrap exit case when there is unclosed time periods from yesterday (exit on next day)
            await db.execute(query_update_unclosed_yesterday_shift % (email_value, dict(last_shift_yesterday)['start']))
            await db.execute(query_move_and_close_yesterdays_shift_today % (email_value, track_timestamp))
    else:  # exit event (entered today)
        hash_shift_obj = dict(last_shift_today)
        if not hash_shift_obj['end']:  # leave in the middle of the day event
            if hash_shift_obj['start'] == track_timestamp:
                errormsg = f"wait at least 1 second and retry, event from {email_value}, at {track_timestamp.isoformat()}"
                print(errormsg)
                return JSONResponse(content={'error': errormsg})
            update_obj.update({"start": hash_shift_obj['start'],
                               'end': track_timestamp})
        else:  # back in the middle of the daye event
            update_obj['start'] = track_timestamp
    print(f'update_obj: {update_obj}')
    if update_obj['end']:
        await db.execute(query_update_existing_shift % (update_obj['end'], email_value))
    else:
        await db.execute(query_insert_new_shift % (email_value, update_obj['start']))
    return JSONResponse(content={'response': last_shift_today})


@app.post('/reports/monthly/{employee_email}')
async def monthly_report(employee_email: Request):
    data = await employee_email.json()
    try:
        apikey = data['API_KEY']
        if apikey != APP_API_KEY:
            raise Exception('WRONG_API_KEY')
        email_value = data['employee_email']
    except Exception as input_error:
        return JSONResponse(content={"error": str(input_error)})
    report_timestamp = datetime.utcnow().replace(microsecond=0)

    monthly_records = [dict(fetched_record) for fetched_record in
                       await db.fetch_all(query_get_monthly_records % email_value) if fetched_record]
    monthly_report_hashmap = {}
    current_month = report_timestamp.month
    current_year = report_timestamp.year
    month_days_count = calendar.monthrange(report_timestamp.year, current_month)[1]
    # fill hashmap with day in current month
    for each_day in range(1, month_days_count + 1):
        monthly_report_hashmap[each_day] = {'H': 0}

    sum_hours = 0
    # iterate over records
    for record in monthly_records:
        record_start = record['start']
        record_end = record['end']
        record_day = record['start'].day
        record_hours = (record_end - record_start).total_seconds() / 3600
        print(record_hours, record)
        sum_hours += record_hours
        monthly_report_hashmap[record_day]['H'] += record_hours

    parsed_days = [f"D {z:02d} H {round(monthly_report_hashmap[z]['H'], 1):.1f}" for z in
                   range(1, month_days_count + 1)]
    dayly_rows_text = '\n'.join(parsed_days)
    plain_text_output = f"Month #{current_month}\n" \
                        f"Employee: {email_value}\n\n" \
                        f"{dayly_rows_text}\n" \
                        f"{'-' * 12}\n" \
                        f"Total {round(sum_hours, 1)} hours"
    response_obj = {
        "plain_text": plain_text_output,
        "s3_upload_success": False,
        "s3_response": None,
        "email_delivery_success": False,
        "email_delivery_response": None
    }
    # upload to s3
    try:
        output = StringIO()
        output.write(plain_text_output)
        zip_buffer = BytesIO()
        file_name = f"{email_value}_{current_year}_{current_month}"
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zipper:
            zipper.writestr(f"{file_name}.txt", output.getvalue())
        s3_upload = S3_CLIENT.upload_fileobj(zip_buffer, S3_BUCKET_NAME, f"{file_name}.zip")
        response_obj.update({'s3_upload_success': True,
                             "s3_response": s3_upload})
    except Exception as s3_upload_error:
        custom_logger.error('s3_upload_error')
        response_obj.update({'s3_upload_success': False,
                             "s3_response": s3_upload_error})

    # email_delivery
    try:
        response = requests.post(f"https://api.mailgun.net/v3/{EMAIL_DOMAIN_NAME}/messages",
                                 auth=("api", EMAIL_API_KEY),
                                 data={"from": f"Excited User <mailgun@{EMAIL_DOMAIN_NAME}>",
                                       "to": [email_value, f"YOU@{EMAIL_DOMAIN_NAME}"],
                                       "subject": "This is the email of an accounting department",
                                       "text": plain_text_output}, timeout=300)
        response_obj.update({'email_delivery_success': True,
                             "email_delivery_response": response.status_code})
    except Exception as email_delivery_error:
        custom_logger.error("email_delivery_error")
        response_obj.update({'email_delivery_success': False,
                             "email_delivery_response": email_delivery_error})
    return JSONResponse(content=response_obj)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
