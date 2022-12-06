sudo docker run -d --rm -p 8080:8080 -it ${AWS_USERNAME}/${APP_NAME} -e APP_API_KEY=${APP_API_KEY} \
-e DATABASE_URL=${DATABASE_URL} \
-e EMAIL_API_KEY=${EMAIL_API_KEY} \
-e EMAIL_DOMAIN_NAME=${EMAIL_DOMAIN_NAME} \
-e S3_BUCKET_NAME=${S3_BUCKET_NAME}