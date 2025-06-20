IMAGE_NAME = ytdlp-docker
CONTAINER_NAME = ytdlp-docker-container
PORT = 5001:5000

# Detect OS for path handling
ifeq ($(OS),Windows_NT)
    PWD := $(shell cd)
    NULL_REDIRECT := >nul 2>&1
    SHELL_CMD := cmd
    OR_TRUE := || exit 0
else
    PWD := $(shell pwd)
    NULL_REDIRECT := >/dev/null 2>&1
    SHELL_CMD := /bin/bash
    OR_TRUE := || true
endif

.PHONY: build run sh stop rm logs build-and-run br brl

build: rm
	docker build -t $(IMAGE_NAME) .

prune:
	docker system prune -a

run: stop
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT) \
		-v "$(PWD)/data:/app/data" \
		-v "$(PWD)/config:/app/config" \
		$(IMAGE_NAME)

sh:
	docker exec -it $(CONTAINER_NAME) $(SHELL_CMD)

stop:
	-docker stop $(CONTAINER_NAME) $(NULL_REDIRECT) $(OR_TRUE)

rm:
	-docker rm -f $(CONTAINER_NAME) $(NULL_REDIRECT) $(OR_TRUE)

logs:
	docker logs -f $(CONTAINER_NAME)

br: build run

brl: build run logs