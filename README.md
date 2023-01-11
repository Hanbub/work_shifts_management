# work_shifts_management
This is a FastAPI server with PostgreSQL and postman collection examples that tracks employee time on work, generate monthly report, save it on s3 and send over mailgun service  

### environment variables should be stored in from config.env and read and exported by "export $(cat config.env | xargs)" command

    POSTGRES_USERNAME="YOUR_DATABASE_USERNAME"
    POSTGRES_PASSWORD="YOUR_DATABASE_PASSWORD"
    POSTGRES_DATABASE="YOUR_DATABASE_NAME"
    EMAIL_API_KEY="EMAIL_API_KEY"
    EMAIL_DOMAIN_NAME="YOUR_EMAIL_DOMAIN_NAME"
    S3_BUCKET_NAME="YOUR_S3_BUCKET_NAME"
  
### building process:

    docker-compose build

### running process:

    docker-compose up -d

### Route add shift:

    curl --location --request POST 'http://localhost:8008/shift/email' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "email":"testmail@gmail.com",
        "start":1670351029000,
        "end":1670351030000
    }'

### Route that generate report, save on S3 and send email about it
    
    curl --location --request POST 'http://localhost:8008/reports/monthly/employee_email' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "employee_email":"testmail@gmail.com"
    }'

# Postman collections example

file test.postman_collection.json can be imported as collection to Postman workspace
