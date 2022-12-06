FROM tiangolo/uvicorn-gunicorn:python3.8
WORKDIR /app
ADD ./source /app
EXPOSE 8080
RUN pip install -r requirements.txt
CMD ["python", "${ARG_VERSION}"]