sudo aws ecr get-login-password --region ${AWS_REGION} |
 sudo docker login --username AWS --password-stdin ${AWS_USERNAME}
local_image_name=${APP_NAME}
remote_image_name=${APP_NAME}
docker_file_name="Dockerfile"
aws_ecr_repo_address=${AWS_USERNAME}

#ARG_VERSION can be inherented on run layer
docker build --no-cache -t ${local_image_name} --build-arg ARG_VERSION=app_v1.py --file ${docker_file_name} .
sudo docker build -t ${local_image_name} --file ${docker_file_name} . && \
sudo docker tag ${local_image_name}:latest ${aws_ecr_repo_address}/${remote_image_name}:latest && \
sudo docker push ${aws_ecr_repo_address}/${remote_image_name}:latest