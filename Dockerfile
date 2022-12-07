FROM tiangolo/uvicorn-gunicorn:python3.8
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ADD ./source /app
EXPOSE 8000
RUN pip install -r requirements.txt
CMD ["python", "app.py"]