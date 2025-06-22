IMAGE_NAME = ytdlp-docker
CONTAINER_NAME = ytdlp-docker-container
PORT = 5001:5000

# Detect OS for path handling
ifeq ($(OS),Windows_NT)
    PWD := $(shell cd)
    NULL_REDIRECT := >nul 2>&1
    OR_TRUE := || exit 0
else
    PWD := $(shell pwd)
    NULL_REDIRECT := >/dev/null 2>&1
    OR_TRUE := || true
endif

.PHONY: build run sh stop rm logs build-and-run br brl full dev_ dev

build: rm
	docker build -t $(IMAGE_NAME) .

clean:
	docker system prune -a

# Production run (code baked into image)
run: stop
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT) \
		-v "$(PWD)/data:/app/data" \
		-v "$(PWD)/config:/app/config" \
		$(IMAGE_NAME)

# Development run (code mounted as volumes)
dev_: stop rm
	docker build -f Dockerfile.dev -t $(IMAGE_NAME)-dev .
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT) \
		-v "$(PWD)/data:/app/data" \
		-v "$(PWD)/config:/app/config" \
		-v "$(PWD)/src:/app" \
		-e FLASK_DEBUG=1 \
		-e FLASK_ENV=development \
		$(IMAGE_NAME)-dev

sh:
	docker exec -it $(CONTAINER_NAME) /bin/bash

stop:
	-docker stop $(CONTAINER_NAME) $(NULL_REDIRECT) $(OR_TRUE)

rm:
	-docker rm -f $(CONTAINER_NAME) $(NULL_REDIRECT) $(OR_TRUE)

logs:
	docker logs -f $(CONTAINER_NAME)

br: build run

brl: build run logs

# Development workflow
dev: dev_ logs

full: clean build run logs