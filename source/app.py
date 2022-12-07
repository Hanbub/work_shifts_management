from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
import databases
import requests
import sqlalchemy
import logging
import uvicorn
import os
from datetime import datetime, timedelta
import calendar
import zipfile
from io import StringIO, BytesIO
import boto3

custom_logger = logging.getLogger('custom_logger')
DATABASE_URL = os.environ["DATABASE_URL"]
EMAIL_API_KEY = os.environ["EMAIL_API_KEY"]
EMAIL_DOMAIN_NAME = os.environ["EMAIL_DOMAIN_NAME"]
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

query_get_daily_records = """
select * from TimeShifts t
where t.email='%s' and 
      t."start" >= '%s'::timestamp and
      t."start" < '%s'::timestamp
"""

query_insert_new_shift = """
insert into TimeShifts
(email, "start", "end") values ('%s','%s'::timestamp,'%s'::timestamp)
"""

query_get_monthly_records = """
    select * from TimeShifts t 
    where email = '%s' and 
    extract('month' from "start") = extract('month' from current_date)
    """


async def add_or_merge_shift(in_start_dt, in_end_dt, in_email):
    custom_logger.info(f'working_with: {in_email}, from {in_start_dt}, up_to: {in_end_dt}')
    start_of_startday = in_start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_startday = in_start_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    daily_rows = await db.fetch_all(query_get_daily_records % (in_email, start_of_startday, end_of_startday))
    daily_records = [dict(x) for x in daily_rows]
    if len(daily_records) == 0:
        await db.execute(query_insert_new_shift % (in_email, in_start_dt, in_end_dt))
    call_next_day_flag = False
    for daily_record in daily_records:
        start_record = daily_record['start']
        end_record = daily_record['end']
        if start_record == in_start_dt and in_end_dt == end_record:
            custom_logger.info(f'record for this time corridor already exist')
        elif (in_start_dt <= start_record and in_end_dt <= start_record) or \
                (in_start_dt >= end_record and in_end_dt <= end_of_startday):
            await db.execute(query_insert_new_shift % (in_email, in_start_dt, in_end_dt))
            break
        elif in_start_dt <= start_record > in_end_dt:
            await db.execute(query_insert_new_shift % (in_email, in_start_dt, end_record))
            break
        elif end_record > in_start_dt and in_end_dt <= end_of_startday:
            await db.execute(query_insert_new_shift % (in_email, end_record, in_end_dt))
            break
        elif in_start_dt <= end_record and in_end_dt > end_of_startday:
            await db.execute(query_insert_new_shift % (in_email, end_record, end_of_startday))
            call_next_day_flag = True
            break
        elif in_start_dt > end_record and in_end_dt > end_of_startday:
            await db.execute(query_insert_new_shift % (in_email, end_record, end_of_startday))
            call_next_day_flag = True
            break
        else:
            continue
    if call_next_day_flag:
        next_day_dt = end_of_startday + timedelta(seconds=1)
        await add_or_merge_shift(next_day_dt, in_end_dt, in_email)


@app.on_event("startup")
async def startup():
    await db.connect()
    await db.execute("""CREATE TABLE IF NOT EXISTS Timeshifts (email text, "start" timestamp, "end" timestamp)""")


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.post('/shift/{email}')
async def shift(email: Request):
    data = await email.json()
    try:
        start_value = data['start']
        start_dt = datetime.utcfromtimestamp(start_value / 1e3)
        end_value = data['end']
        end_dt = datetime.utcfromtimestamp(end_value / 1e3)
        if start_dt + timedelta(days=1) <= end_dt:
            raise Exception('more_than_one_day_error')
        if end_value <= start_value:
            raise Exception('end <= start')
        email_value = data['email']
    except Exception as wrong_input:
        custom_logger.error("wrong_input")
        return JSONResponse(content={"error": str(wrong_input)})
    try:
        await add_or_merge_shift(start_dt, end_dt, email_value)
    except Exception as add_or_merge_shift_error:
        custom_logger.error('add_or_merge_shift_error')
        return JSONResponse(content={"error": str(add_or_merge_shift_error)})
    return JSONResponse(content={"success": True,
                                 "email": email_value,
                                 "start": start_dt.isoformat(),
                                 "end": end_dt.isoformat()})


@app.post('/reports/monthly/{employee_email}')
async def monthly_report(employee_email: Request):
    try:
        data = await employee_email.json()
        email_value = data['employee_email']
        report_generated_flag = False
        report_timestamp = datetime.utcnow().replace(microsecond=0)
        monthly_records = [dict(fetched_record) for fetched_record in
                           await db.fetch_all(query_get_monthly_records % email_value) if fetched_record]
        if len(monthly_records) > 0:
            report_generated_flag = True
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
            "report_generated_flag": report_generated_flag,
            "s3_upload_success": False,
            "s3_response": None,
            "email_delivery_success": False,
            "email_delivery_response": None
        }
    except Exception as report_build_error:
        custom_logger.error("report_build_error")
        return JSONResponse(content={"error": "report_build_error"})
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
