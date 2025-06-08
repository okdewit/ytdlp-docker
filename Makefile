IMAGE_NAME = ytdlp-docker
CONTAINER_NAME = ytdlp-docker-container
PORT = 5001:5000

.PHONY: build run sh stop rm logs

build: rm
	docker build -t $(IMAGE_NAME) .

run: stop
	docker run -d \
	--name $(CONTAINER_NAME) \
	-p $(PORT) \
	-v $(PWD)/data:/app/data \
	$(IMAGE_NAME)

sh:
	docker exec -it $(CONTAINER_NAME) /bin/bash

stop:
	-docker stop $(CONTAINER_NAME) 2>/dev/null || true

rm:
	-docker rm -f $(CONTAINER_NAME) 2>/dev/null || true

logs:
	docker logs -f $(CONTAINER_NAME)