# VXPEngine Frame Simulator

**Simulator độc lập** — chỉ hiện khung máy VXPEmu (đúng layout ảnh tham chiếu
`8687567.PNG`), kèm **panel SDK kiểu Extensions của VS Code** để liệt kê
mọi thành phần môi trường đã cài / chưa cài, kèm nút **Check for updates**.

> Trái ngược với `app/widgets/emulator_panel.py` (chrome nhúng trong IDE) và
> VXPEmu gốc (toàn bộ UI với menu, dock, cây project, cửa sổ log…),
> simulator này **chỉ giữ lại đúng phần khung**: thanh công cụ 7 nút +
> màn hình 240×320 + dòng nhắc Multi-tan + bàn phím MRE 20 phím.

## Chạy

```bash
cd D:\MRE\VXPEngine
python simulator/standalone_simulator.py            # mặc định cổng 8765
python simulator/standalone_simulator.py --port 9000 --no-browser
```

Không cần PySide6/Qt — chỉ cần Python 3.11+ (stdlib `http.server`).
Trình duyệt mặc định sẽ tự mở `http://127.0.0.1:8765/`.

## Kiến trúc

```
simulator/
├── standalone_simulator.py     ← entry: HTTP server + JSON API
├── templates/
│   └── index.html              ← khung máy + panel SDK
├── static/
│   ├── style.css               ← dark theme khớp ảnh tham chiếu
│   └── app.js                  ← render extensions, filter, install
└── README.md
```

### Điểm nối với IDE

* Detection ở `app/environment_spec.py` — module **không Qt**, dùng chung
  với `app/environment_setup.py` (Qt-based). Cả IDE lẫn simulator đều
  thấy đúng một danh sách thành phần.
* `EnvironmentInstaller` của IDE vẫn dùng `QProcess`; simulator dùng
  `subprocess` — hành vi cài đặt giống nhau (cùng `command()` callable).
* Khi thêm/sửa `Requirement` ở `environment_spec.py`, cả hai nơi tự đồng
  bộ — không phải khai báo hai lần.

## API

| Method | Path                  | Mô tả |
|--------|-----------------------|-------|
| GET    | `/`                   | Trang HTML chính. |
| GET    | `/static/{css,js}`    | Tài nguyên tĩnh. |
| GET    | `/api/environment`    | Danh sách thành phần + tóm tắt. |
| GET    | `/api/health`         | Heartbeat. |
| POST   | `/api/check-updates`  | So với manifest latest, trả `NO_UPDATE_NEEDED` hoặc `UPDATE_AVAILABLE`. |
| POST   | `/api/install`        | Body `{"keys": [...]}` — chạy lệnh cài qua subprocess. |

## Check for updates — hành vi

Trong cùng manifest `LATEST_MANIFEST` ở `standalone_simulator.py`
(version `engine_version`, `sdk_latest`, v.v.), simulator so với trạng
thái thực tế trên máy:

* **Mọi thành phần đều `satisfied`** → trả `NO_UPDATE_NEEDED`:
  > *Đã cài đặt SDK và thư viện môi trường mới nhất. Không cần cập nhật.*

  — đúng yêu cầu: "khi đã cài đặt thư viện môi trường SDK mới nhất rồi thì
  khi kiểm tra cập nhật sẽ báo không phải cập nhật nữa".

* **Có thành phần thiếu** → trả `UPDATE_AVAILABLE` và liệt kê
  danh sách cần cài trong `missing[]`.

## Liệt kê kiểu Extensions

Mỗi "extension" là một `Requirement` từ `app.environment_spec`:

* Icon (theo key)
* Tên đậm + tag "tuỳ chọn" nếu `optional=True`
* Mô tả / gợi ý (`hint`) — dòng nhỏ xám
* Huy hiệu trạng thái — xanh/vàng/đỏ
* Nút hành động — **Cài đặt** (nếu `installable`) hoặc **✓ Đã có** /
  **Thủ công**

Có thanh tìm kiếm + bộ lọc (Tất cả / Đã cài / Chưa cài / Có thể cài tự
động) y hệt khung Extensions của VS Code.

## Bàn phím (chỉ làm cảnh)

Nhấn phím số sẽ cập nhật chuỗi overlay `G_M_A_S` ở góc trên-trái màn
hình — giống cảm giác đang gõ multi-tap. Dòng nhắc `Multi-tan: 2=a·b·c
…` chuyển sang dạng `2 → b   letter 2/3` khi đang gõ. Phím điều
hướng lún xuống như phím thật.

Đây là bản xem trước UI, không chạy game thật; runtime duy nhất là VXPEmu.
Bấm Check for updates và quan sát badge đổi màu là đủ chứng
minh chức năng "đã cài → không cần cập nhật".
