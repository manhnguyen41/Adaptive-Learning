# Docker Guide

Hướng dẫn build và chạy Docker container cho Adaptive Learning Diagnostic Test API.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 1.29+ (optional, nếu dùng docker-compose)

## Build Docker Image

### Cách 1: Build từ Dockerfile

```bash
docker build -t adaptive-learning-api:latest .
```

### Cách 2: Build với tag tùy chỉnh

```bash
docker build -t adaptive-learning-api:v1.0.0 -t adaptive-learning-api:latest .
```

## Chạy Container

### Cách 1: Chạy trực tiếp với Docker

```bash
docker run -d \
  --name adaptive-learning-api \
  -p 8000:8000 \
  -v $(pwd)/user_question_progress_100000.json:/app/user_question_progress_100000.json:ro \
  -v $(pwd)/topic_questions_asvab.csv:/app/topic_questions_asvab.csv:ro \
  adaptive-learning-api:latest
```

**Windows PowerShell:**
```powershell
docker run -d `
  --name adaptive-learning-api `
  -p 8000:8000 `
  -v ${PWD}/user_question_progress_100000.json:/app/user_question_progress_100000.json:ro `
  -v ${PWD}/topic_questions_asvab.csv:/app/topic_questions_asvab.csv:ro `
  adaptive-learning-api:latest
```

**Windows CMD:**
```cmd
docker run -d ^
  --name adaptive-learning-api ^
  -p 8000:8000 ^
  -v %cd%/user_question_progress_100000.json:/app/user_question_progress_100000.json:ro ^
  -v %cd%/topic_questions_asvab.csv:/app/topic_questions_asvab.csv:ro ^
  adaptive-learning-api:latest
```

### Cách 2: Chạy với Docker Compose (Recommended)

```bash
docker-compose up -d
```

Xem logs:
```bash
docker-compose logs -f
```

Dừng container:
```bash
docker-compose down
```

## Kiểm tra Container

### Xem logs

```bash
docker logs adaptive-learning-api
```

### Kiểm tra health

```bash
docker ps
```

Container sẽ hiển thị status "healthy" sau khi health check pass.

### Truy cập API

Sau khi container chạy, truy cập:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Cấu trúc Dockerfile

Dockerfile sử dụng **multi-stage build** để tối ưu kích thước:

1. **Builder stage**: Build và cài đặt dependencies
2. **Production stage**: Chỉ copy những gì cần thiết

## Volume Mounting

Data files được mount như volumes để:
- Có thể update dữ liệu mà không cần rebuild image
- Giảm kích thước image
- Dễ dàng backup và restore

## Environment Variables

Có thể thêm environment variables trong `docker-compose.yml` hoặc khi chạy:

```bash
docker run -d \
  -e PYTHONUNBUFFERED=1 \
  -p 8000:8000 \
  adaptive-learning-api:latest
```

## Troubleshooting

### Container không start

```bash
docker logs adaptive-learning-api
```

### Kiểm tra file data

```bash
docker exec adaptive-learning-api ls -lh /app/
```

### Vào trong container

```bash
docker exec -it adaptive-learning-api /bin/bash
```

### Rebuild image

```bash
docker build --no-cache -t adaptive-learning-api:latest .
```

## Production Deployment

### Build cho production

```bash
docker build -t adaptive-learning-api:prod .
```

### Deploy với Docker Swarm hoặc Kubernetes

Cần tạo:
- `docker-stack.yml` cho Docker Swarm
- `k8s/` directory với manifests cho Kubernetes

### Health Check

Container có health check tự động. Nếu container unhealthy:

```bash
docker inspect --format='{{json .State.Health}}' adaptive-learning-api
```

## Tối ưu Image Size

- Image sử dụng Python slim (nhỏ hơn ~200MB so với full image)
- Multi-stage build loại bỏ build dependencies
- Chỉ copy những file cần thiết

## Security

- Container chạy với non-root user (`appuser`)
- Data files mounted read-only
- Minimal base image

