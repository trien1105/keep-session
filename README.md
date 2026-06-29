# GA Session Keeper 🕐

Tool tự động giữ session active user sống trên **Google Analytics** bằng cách gửi hit liên tục qua [Measurement Protocol](https://developers.google.com/analytics/devguides/collection/protocol/ga4).

Khi push lên GitHub → **GitHub Actions tự động chạy và treo 24/7**.

---

## 📋 Cấu trúc file

```
ga_session_keeper/
├── ga_keeper.py          ← Script chính
├── config.json           ← Cấu hình local (không commit lên GitHub!)
├── requirements.txt
├── .gitignore
└── .github/
    └── workflows/
        └── ga_keeper.yml ← GitHub Actions workflow
```

---

## 🔑 Bước 1 — Lấy GA4 API Secret

1. Vào **Google Analytics** → Admin → **Data Streams** → chọn stream của bạn
2. Kéo xuống **Measurement Protocol API secrets**
3. Nhấn **Create** → đặt tên → copy **Secret value**
4. Copy luôn **Measurement ID** (dạng `G-XXXXXXXXXX`) ở đầu trang Data Stream

---

## 🔐 Bước 2 — Thêm GitHub Secrets

Vào repo GitHub → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Giá trị |
|---|---|
| `GA4_MEASUREMENT_ID` | `G-XXXXXXXXXX` |
| `GA4_API_SECRET` | secret value vừa copy |
| `TARGET_URL` | `https://your-website.com` |
| `UA_TRACKING_ID` | (để trống nếu không dùng UA) |

---

## 💻 Bước 3 — Chạy local (test)

```bash
cd ga_session_keeper
pip install -r requirements.txt

# Sửa config.json với credentials thật
python ga_keeper.py
```

---

## 🚀 Bước 4 — Push lên GitHub

```bash
# Đảm bảo không commit config.json chứa credentials thật!
# Đã có .gitignore bảo vệ rồi.

git init
git add .
git commit -m "feat: add GA session keeper"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

→ GitHub Actions **tự động kích hoạt** và chạy tool.

---

## ⚙️ Tham số có thể điều chỉnh

| Biến môi trường | Mô tả | Mặc định |
|---|---|---|
| `NUM_VIRTUAL_USERS` | Số user ảo đồng thời | `5` |
| `HIT_INTERVAL_MIN` | Thời gian chờ tối thiểu giữa mỗi cycle (giây) | `25` |
| `HIT_INTERVAL_MAX` | Thời gian chờ tối đa (giây) | `40` |
| `RUN_DURATION_HOURS` | Số giờ chạy 1 lần (để dưới 6h) | `5.5` |

---

## 🔄 Cách GitHub Actions tự treo 24/7

GitHub Actions giới hạn mỗi job chạy tối đa **6 giờ**. Tool xử lý bằng cách:

1. Mỗi lần chạy giữ đúng **5.5 giờ**
2. Cron schedule `0 */5 * * *` sẽ **tự kick lại** mỗi 5 tiếng
3. Kết quả: tool chạy liên tục không bị gián đoạn

---

## ⚠️ Lưu ý

- **Không commit `config.json`** chứa API key thật (đã có .gitignore)
- GitHub Actions Free tier cho **2,000 phút/tháng** — dùng repo private sẽ tốn phút; public repo miễn phí không giới hạn
- Tool gửi hit tới GA Measurement Protocol endpoint chính thức của Google
