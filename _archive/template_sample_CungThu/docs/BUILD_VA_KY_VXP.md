# Hướng dẫn build & ký ứng dụng MRE `.vxp` chạy trên Nokia 225 Dual SIM

Tài liệu này ghi lại toàn bộ quy trình build ứng dụng MRE từ mã nguồn C/C++
thành file `.vxp` chạy được trên điện thoại Nokia 225 (và các máy S30+ tương tự),
bao gồm cả bước **ký số (signing)** để máy bán lẻ chấp nhận mở ứng dụng.

Dự án mẫu ở đây là **TextButtonTest** — một app tối giản hiển thị tiêu đề, một
nút `PRESS` và dòng trạng thái, điều khiển bằng phím cứng.

---

## 1. Bối cảnh & khái niệm

### `.vxp` là gì
`.vxp` là định dạng ứng dụng của nền tảng **MRE** (MediaTek Runtime Environment)
chạy trên điện thoại phổ thông (feature phone) dùng chip MediaTek, ví dụ Nokia
225 / 220 / 225 Dual SIM. Về bản chất nó là một file **ELF ARM** (mã máy) được
nhồi thêm tài nguyên (`.res`) và một khối **tag** mô tả ứng dụng (tên, appid,
certid, API dùng, RAM...) cùng một **chữ ký RSA** ở cuối file.

### Hai loại file khác nhau — dễ nhầm
| Đuôi file | Dùng cho | Sinh ra khi build với |
|-----------|----------|-----------------------|
| `.vxp`    | **Điện thoại thật** (ARM) | toolchain `arm-none-eabi` |
| `.vc.vxp` | Giả lập MoDis / MREmu trên Windows | Visual Studio (Win32) |

> Không chạy chéo được: `.vc.vxp` không mở trên máy thật, và `.vxp` không mở trên MoDis.

### Vì sao phải ký
Máy Nokia bán lẻ (chưa bẻ khóa developer) chỉ mở ứng dụng thỏa mãn **đồng thời**:

1. `appid` **không âm** (khác `-1`), và
2. được ký bằng **chứng chỉ tin cậy** `certid = 100` (chứng chỉ mà firmware
   retail công nhận).

App để `appid = 0` (chế độ đang phát triển) hoặc ký bằng chứng chỉ test
(`certid = 1` hoặc `2`) sẽ **bị máy retail lặng lẽ từ chối mở** — đây chính là
lỗi "không mở được ứng dụng" thường gặp.

Cách công cụ đóng gói (`PackApp`) quyết định có ký hay không:

```
Chỉ tạo chữ ký RSA khi:  appid != -1  VÀ  certid != 1
Ngược lại: ghi 64 byte 0 (file coi như KHÔNG ký).
```

### Mô hình ký của VXPEngine (từ v4.6)

Khóa ký là **tài sản cốt lõi của engine** nên được tách hoàn toàn khỏi project:

| Thành phần | Nằm ở đâu | Ai sở hữu |
|-----------|-----------|-----------|
| Khóa ký `certid=100` (`cert100-key.pem`) | `VXPEngine/signing/` | Engine — **không bao giờ copy vào project** |
| `certid` | Truyền lúc build (`-DCERTID`) | Engine |
| **App ID** (`-tai` / `APPID`) | `project.vxp.json` của từng project | Mỗi project giữ **một ID riêng** |

- Khi tạo project, VXPEngine **không sinh thư mục `signing/`** trong project nữa.
- Mỗi project nhận **một App ID riêng** (6–7 chữ số, do engine phát sinh ngẫu nhiên
  và bảo đảm không trùng với project khác). App ID được lưu trong
  `project.vxp.json` và tự điền vào `CMakeLists.txt`.
- Nút **Build ARM Signed** trong VXPEngine sẽ: lấy App ID của project → ghép với
  khóa ký của engine → truyền xuống `build_arm_signed.sh` qua ba biến môi trường
  `VXP_APPID`, `VXP_CERTID`, `VXP_CERT`.
- Nếu phát hiện khóa ký lọt vào project (bản cũ), VXPEngine sẽ **xóa và cảnh báo**
  trong console khi mở dự án.
- App ID hiển thị trên **thanh trạng thái** của cửa sổ editor.

---

## 2. Yêu cầu môi trường

| Thành phần | Dùng để | Ghi chú trong máy này |
|-----------|---------|------------------------|
| CMake | cấu hình build | `C:/Program Files/CMake` |
| ARM GCC (`arm-none-eabi`) | biên dịch mã ARM cho máy thật | `C:/msys64/mingw64/bin` (GCC 13.3.0) |
| `mingw32-make` | trình build | đi kèm msys64 |
| MRE SDK | header + thư viện `.a` + giả lập | biến môi trường `MRE_SDK` |
| TinyMRESDK | `PackRes` (đóng gói tài nguyên) + `PackApp` (đóng gói + ký) | biến môi trường `TinyMRESDK` |
| OpenSSL | tạo/kiểm tra key RSA (đi kèm msys64) | `C:/msys64/mingw64/bin/openssl` |
| Private key `certid=100` | ký ứng dụng | `VXPEngine/signing/cert100-key.pem` — **thuộc engine, không nằm trong project** |

Kiểm tra nhanh:

```bash
echo "$MRE_SDK"        # .../third_party/mre-sdk/app
echo "$TinyMRESDK"     # .../TinyMRESDK-main
arm-none-eabi-gcc --version
```

---

## 3. Cấu trúc dự án

```
new-project/
├─ CMakeLists.txt        # cấu hình chung: tên app, IMSI, APPID, CERTID, API, RAM
├─ project.vxp.json      # descriptor: App ID riêng của project (do engine cấp)
├─ main/
│  ├─ CMakeLists.txt     # khai báo target vxp, link mreapi
│  └─ main.cpp           # mã nguồn ứng dụng (vm_main + xử lý sự kiện)
├─ mreapi/               # gom toàn bộ MRE API thành 1 static lib
├─ resources/            # tài nguyên (ảnh, text) -> đóng thành .res
├─ common/               # gccmain.c, scat.ld (linker script), dll.def
├─ cmake/                # toolchain ARM + các hàm add_exec_vxp / add_pack_vxp
├─ build_arm.sh          # build bản CHƯA ký (dev/test)
└─ build_arm_signed.sh   # build bản ĐÃ ký (nhận khóa + App ID từ engine)
```

> **Không có thư mục `signing/` trong project.** Khóa `certid=100` nằm tại
> `VXPEngine/signing/cert100-key.pem` và chỉ engine được phép dùng. Project luôn ở
> trạng thái `CERTID=1` / `CERT=none`; khi build bản ký, VXPEngine truyền
> `-DCERTID=100 -DCERT=<đường dẫn khóa engine>` từ bên ngoài.

---

## 4. Viết mã điều khiển bằng phím cứng (quan trọng cho Nokia 225)

Nokia 225 **không có màn hình cảm ứng**. Nếu app chỉ xử lý sự kiện chạm (pen
event) thì trên máy thật sẽ không bấm được gì. Vì vậy phải xử lý sự kiện **phím**
trong `handle_keyevt`.

Mã trong `main/main.cpp`:

```c
void handle_keyevt(VMINT event, VMINT keycode) {
    if (event != VM_KEY_EVENT_DOWN)   // chỉ xử lý lúc nhấn xuống
        return;

    switch (keycode) {
    case VM_KEY_OK:            // phím giữa (chọn) -> đổi trạng thái nút
    case VM_KEY_NUM5:          // phím 5 (giữa bàn phím) cũng đổi
        button_pressed = button_pressed == VM_FALSE ? VM_TRUE : VM_FALSE;
        draw_screen();
        break;

    case VM_KEY_RIGHT_SOFTKEY: // softkey phải / Back / Clear -> thoát
    case VM_KEY_BACK:
    case VM_KEY_CLEAR:
        if (layer_hdl[0] != -1) {
            vm_graphic_delete_layer(layer_hdl[0]);
            layer_hdl[0] = -1;
        }
        vm_exit_app();
        break;
    }
}
```

Mã pen event (`handle_penevt`) vẫn giữ nguyên để bản chạy trên MoDis/máy cảm ứng
dùng được. Bảng mã phím MRE tham khảo (trong `vmio.h`):

| Phím | Hằng số | Giá trị |
|------|---------|---------|
| Lên/Xuống/Trái/Phải | `VM_KEY_UP` … `VM_KEY_RIGHT` | -1 … -4 |
| OK (giữa) | `VM_KEY_OK` | -5 |
| Softkey trái/phải | `VM_KEY_LEFT_SOFTKEY` / `VM_KEY_RIGHT_SOFTKEY` | -6 / -7 |
| Clear / Back | `VM_KEY_CLEAR` / `VM_KEY_BACK` | -8 / -9 |
| Số 0–9 | `VM_KEY_NUM0` … `VM_KEY_NUM9` | 48 … 57 |

> Lưu ý C++: hàm `vm_ascii_to_ucs2` nhận `char*` (không phải `const char*`), nên
> khi truyền chuỗi tam nguyên `cond ? "a" : "b"` phải ép kiểu `(VMSTR)` để tránh
> lỗi biên dịch `invalid conversion from 'const char*'`.

---

## 5. Cấu hình ứng dụng trong `CMakeLists.txt`

```cmake
set(APP_NAME "TextButtonTest")
set(DEVELOPER_NAME "VXPstore")
set(RAM "500")                                    # RAM yêu cầu (KB)
set(IMSI "91234567890" CACHE STRING "...")        # xem lưu ý bên dưới
set(API "File SIM_card ProMng")                   # danh sách API app dùng
set(APPID "612345"  CACHE STRING "...")           # VXPEngine cấp riêng cho mỗi project
set(CERTID "1" CACHE STRING "...")                # project luôn mặc định CHƯA ký
set(CERT "none" CACHE STRING "...")               # project KHÔNG giữ khóa ký
```

- `APPID` do VXPEngine ghi vào khi tạo project (mỗi project một ID riêng) và lưu
  đồng thời trong `project.vxp.json`.
- `CERTID` / `CERT` trong project **luôn** là `1` / `none`. Giá trị retail
  (`certid=100` + đường dẫn khóa) chỉ tồn tại trong lệnh build do engine phát ra.

Các giá trị `APPID`, `CERTID`, `CERT`, `IMSI` để ở dạng `CACHE STRING` nên có thể
**ghi đè từ dòng lệnh** bằng `-DAPPID=...` mà không cần sửa file.

**Về IMSI:** khi ký bằng `certid=100` + `appid` dương thì app **không** khóa theo
IMSI, giá trị này trở thành dữ liệu thừa. Nó chỉ quan trọng với license cá nhân
(`appid=-1`, `certid=1`). Nếu dùng license cá nhân trên Nokia, phải thêm số `9`
ở đầu IMSI (bug của MRE API).

---

## 6. Build bản CHƯA ký (để test nhanh / máy đã unlock dev)

Dùng khi bạn muốn thử nhanh và máy đang ở chế độ developer. Script `build_arm.sh`:

```bash
bash build_arm.sh
# -> build-arm/main/TextButtonTest.vxp   (appid=0, KHÔNG có chữ ký)
```

Lệnh CMake tương đương (nếu muốn chạy tay):

```bash
export PATH="/c/msys64/mingw64/bin:$PATH"
cmake -S . -B build-arm -G "MinGW Makefiles" \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-arm-none-eabi.cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DTOOLCHAIN_PREFIX="C:/msys64/mingw64" \
  -DCMAKE_MAKE_PROGRAM="C:/msys64/mingw64/bin/mingw32-make.exe" \
  -DMRE_SDK="$MRE_SDK" -DTinyMRESDK="$TinyMRESDK"
cmake --build build-arm --target main_vxp
```

---

## 7. Build bản ĐÃ ký (để phân phối, chạy trên máy retail)

### 7.1. Chuẩn bị key — **thuộc engine, không làm trong project**
Private key `certid=100` nằm sẵn tại `VXPEngine/signing/cert100-key.pem`.
Người làm dự án **không cần và không nên** copy key vào project. Kiểm tra tính
hợp lệ (chỉ trên máy sở hữu key):

```bash
openssl rsa -in VXPEngine/signing/cert100-key.pem -check -noout   # -> "RSA key ok"
```

### 7.2. Cách khuyến nghị: bấm "Build ARM Signed" trong VXPEngine
VXPEngine tự lấy App ID của project và truyền khóa ký xuống script qua môi trường:

| Biến môi trường | Ý nghĩa |
|-----------------|---------|
| `VXP_APPID`  | App ID riêng của project |
| `VXP_CERTID` | `100` — chứng chỉ tin cậy của firmware retail |
| `VXP_CERT`   | Đường dẫn tuyệt đối tới khóa ký của engine |

### 7.3. Chạy script ký sẵn
```bash
# Bình thường: do VXPEngine gọi, đã có sẵn 3 biến trên
bash build_arm_signed.sh
# -> build-arm-signed/main/<AppName>.vxp   (ĐÃ ký, chạy máy retail)

# Thủ công (chỉ trên máy sở hữu khóa ký):
VXP_APPID=612345 VXP_CERTID=100 VXP_CERT=/path/to/VXPEngine/signing/cert100-key.pem \
  bash build_arm_signed.sh
```

Thiếu một trong ba biến trên, script thoát ngay với mã lỗi `2` và thông báo rõ
lý do — nó **không tự tìm key trong thư mục dự án**.

Nội dung then chốt của `build_arm_signed.sh`:

```bash
APPID="${VXP_APPID:-}"      # do VXPEngine truyền
CERTID="${VXP_CERTID:-}"    # do VXPEngine truyền
CERT_KEY="${VXP_CERT:-}"    # do VXPEngine truyền — trỏ ra khóa của engine

# PATH phải ở dạng Git Bash (/c/...) chứ KHÔNG phải C:/... — nếu để C:/...
# compiler không tìm thấy DLL runtime và CMake báo
# "not able to compile a simple test program".
export PATH="/c/msys64/mingw64/bin:$PATH"

cmake -S "$PROJECT_DIR" -B "$PROJECT_DIR/build-arm-signed" -G "MinGW Makefiles" \
  -DCMAKE_TOOLCHAIN_FILE="$PROJECT_DIR/cmake/toolchain-arm-none-eabi.cmake" \
  -DCMAKE_BUILD_TYPE=Release \
  -DTOOLCHAIN_PREFIX="C:/msys64/mingw64" \
  -DCMAKE_MAKE_PROGRAM="C:/msys64/mingw64/bin/mingw32-make.exe" \
  -DMRE_SDK="..." -DTinyMRESDK="..." \
  -DAPPID="$APPID" -DCERTID="$CERTID" -DCERT="$CERT_KEY"

cmake --build "$PROJECT_DIR/build-arm-signed" --target main_vxp
```

Khi ký thành công, `PackApp` in ra dòng:

```
Creating signature
```

Nếu **không** thấy dòng này nghĩa là điều kiện `appid != -1 && certid != 1` chưa
thỏa — kiểm tra lại `-DAPPID` và `-DCERTID`.

---

## 8. Kiểm chứng file đã ký

Có thể đọc khối tag ở cuối file để xác nhận `appid`, `certid` và kiểm tra vùng
chữ ký khác 0. Script Python nhỏ (chạy `python3`):

```python
import struct
d = open("build-arm-signed/main/TextButtonTest.vxp", "rb").read()
tp = struct.unpack('<i', d[-12:-8])[0]      # vị trí bắt đầu khối tag
pos = tp
names = {1:'dev',2:'appid',3:'certid',4:'name',0x12:'imsi',0x21:'ftype',0xf:'ram'}
while pos < len(d) - 86:
    tid, ln = struct.unpack('<ii', d[pos:pos+8]); pos += 8
    v = d[pos:pos+ln]; pos += ln
    if tid == 0: break
    if tid in (2,3,0x21,0xf): print(hex(tid), names.get(tid,''), struct.unpack('<i', v[:4])[0])
    elif tid in (1,4,0x12):   print(hex(tid), names.get(tid,''), v.split(b'\0')[0].decode('latin1','replace'))
# vùng chữ ký: 64 byte, nằm sau khối const 10 byte ở trailer
sig = d[-76:-12]
print("signature nonzero:", sum(1 for b in sig if b), "/64")
```

Kết quả mong đợi cho bản ký đúng:

```
0x1 dev    XimikBoda
0x2 appid  67200          <- KHÔNG âm
0x3 certid 100            <- chứng chỉ tin cậy
0x4 name   TextButtonTest
0x21 ftype 6              <- vxp (GCC)
signature nonzero: 64 /64 <- toàn bộ 64 byte khác 0 => ĐÃ ký
```

So sánh: bản chưa ký (`build-arm/`) sẽ cho `appid 0` và `signature nonzero: 0/64`.

---

## 9. Cài lên máy

1. Chép `build-arm-signed/main/TextButtonTest.vxp` vào thẻ nhớ (thư mục ứng dụng
   MRE của máy, ví dụ `E:\Others\` tùy máy).
2. Trên điện thoại, mở trình quản lý ứng dụng MRE và chọn app để chạy.

---

## 10. Phân phối cho nhiều máy — hiểu đúng

- File `.vxp` **đã chứa sẵn chữ ký** bên trong. Chỉ cần **copy đúng file đó** sang
  máy khác là chạy — **không phải ký lại trên từng máy**. Ký là việc làm **một lần
  lúc build**.
- Máy khác chạy được **là nhờ chữ ký `certid=100`** có sẵn trong file, không phải
  vì "không cần ký". Nếu đem bản **chưa ký** (`build-arm/`) sang máy retail thì đa
  số vẫn không mở.
- Vì dùng `appid` dương + `certid=100` (không phải license cá nhân), app **không
  khóa theo IMSI**, nên chạy trên nhiều máy / nhiều SIM khác nhau.
- Áp dụng cho máy dùng cùng engine MRE tin cậy `certid=100` (Nokia 225/220/225
  Dual SIM và các đời S30+ tương tự). Nền tảng khác (Java, KaiOS, Series 40 cũ)
  không liên quan.
- **Độ phân giải:** tag để "màn hình = any"; Nokia 225 là 240x320. Trên máy khác
  kích thước, app vẫn mở nhưng bố cục vẽ tay (toạ độ nút cố định) có thể lệch —
  đây không phải lỗi ký.

---

## 11. Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|-----------|-------------|-----------|
| Máy retail không mở app | Bản chưa ký / `appid=0` / `certid` test | Build bằng **Build ARM Signed** trong VXPEngine (App ID riêng + certid=100) |
| PackApp không in `Creating signature` | `appid=-1` hoặc `certid=1` | Chạy signed từ VXPEngine để nhận `-DAPPID` + `-DCERTID=100` |
| `ERROR: thiếu tham số ký từ VXPEngine` | Chạy `build_arm_signed.sh` ngoài VXPEngine | Bấm **Build ARM Signed** trong VXPEngine, hoặc tự truyền `VXP_APPID`/`VXP_CERTID`/`VXP_CERT` |
| Console báo "Đã xóa khóa ký lọt vào project" | Project tạo bởi bản VXPEngine cũ còn `signing/` | Chỉ là thông báo dọn dẹp; khóa ký giờ do engine giữ |
| CMake báo "not able to compile a simple test program" | `PATH` để dạng `C:/...` nên thiếu DLL runtime | Dùng `export PATH="/c/msys64/mingw64/bin:$PATH"` |
| `invalid conversion from 'const char*'` | truyền chuỗi literal vào `vm_ascii_to_ucs2` | Ép kiểu `(VMSTR)"..."` |
| Bấm phím không phản hồi trên máy thật | Chỉ xử lý pen event (cảm ứng) | Thêm xử lý trong `handle_keyevt` |
| App báo lỗi license (bản license cá nhân) | Thiếu số 9 đầu IMSI trên Nokia | Đặt `-DIMSI="9<imsi_thật>"` |

---

## 12. Tóm tắt lệnh

```bash
# Bản test (chưa ký)
bash build_arm.sh

# Bản phân phối (đã ký, chạy máy retail) — gọi từ VXPEngine
bash build_arm_signed.sh     # cần VXP_APPID / VXP_CERTID / VXP_CERT

# Output
#   build-arm/main/<AppName>.vxp          (chưa ký)
#   build-arm-signed/main/<AppName>.vxp   (đã ký -> copy sang máy)
```

> Không còn bước copy key nào: khóa ký nằm cố định tại `VXPEngine/signing/`,
> mỗi project chỉ mang theo **App ID riêng** của nó.
