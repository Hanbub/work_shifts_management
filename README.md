# work_shifts_management
#### This is a FastAPI server with PostgreSQL and postman collection examples that tracks employee time on work, generate monthly report, save it on s3 and send over mailgan service  

## define docker-compose environment variables shuld be stored in from config.env

##prepare process
    
##building process
    docker-compose build
##running process
    docker-compose up -d

##Route add shift:
    curl --location --request POST 'http://localhost:8008/shift/email' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "email":"testmail@gmail.com",
        "start":1670351029000,
        "end":1670351030000
    }'

##Route generate report, save on S3 and send email about it
    curl --location --request POST 'http://localhost:8008/reports/monthly/employee_email' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "employee_email":"testmail@gmail.com"
    }'

##Postman collections example
#### file test.postman_collection.js can be imported as collection to Postman workspace