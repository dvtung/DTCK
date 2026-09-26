# DTCK — Quy trình cài đặt offline (Môi trường air-gapped / cô lập mạng)

## Cách cập nhật gói offline (chạy trên máy có kết nối internet)

```bash
pip download -r requirements.txt -d ./offline_package/wheels
# chốt phiên bản chính xác để tái lập:
# pip freeze > offline_package/requirements-offline.txt   (dựa trên venv)
```

## Cách cài đặt offline

```bash
pip install --no-index --find-links=./offline_package/wheels -r requirements-offline.txt
```

## Yêu cầu đối với bộ gói này

- Python 3.12 (khớp với Docker base image: `python:3.12-slim`)
- Bản build xgboost/lightgbm từ wheel mặc định chỉ chạy CPU
- Xem `helper/resources_vi.md` để xem ma trận phiên bản phụ thuộc
