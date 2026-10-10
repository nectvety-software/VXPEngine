# Urban Toon / VxpToon3D

Nâng cấp coremre cho phong cách đô thị cel-shading trong video Jet Set Radio:
mesh hình học phối cảnh, màu chia dải, đường viền tối, nhân vật có màu nổi
bật, fog xanh ở xa. Không trích xuất model, texture hay nhân vật từ video.

## API

`graphics/VxpToon3D.h` cung cấp C API, dùng chung được với project C/C++:

```c
static uint16_t depth[320*240];
VxpeToonTarget3D target = {framebuffer, depth, 320, 240};
VxpeToonCamera3D camera;
VxpeToonMaterial3D material;
vxpe_toon3d_camera_init(&camera,320,240);
camera.position.y = 120;
vxpe_toon3d_material_init(&material,0xFFE0);
vxpe_toon3d_clear(&target,0x349F);
VxpeVec3D face[4] = {{-80,0,300},{80,0,300},{80,160,300},{-80,160,300}};
vxpe_toon3d_quad(&target,&camera,face,&material,210);
```

- +X sang phải, +Y lên trên, camera mặc định nhìn +Z. Yaw dùng sin/cos Q14;
  cặp phải được chuẩn hóa, ví dụ 0/16384 hoặc 16384/0.
- `near_z >= 1`, `far_z <= 65534`, `focal_px <= 4096`. Depth cần được clear
  mỗi frame; không truyền framebuffer và depth trùng vùng nhớ.
- Vertex nguyên; hot path không float và không cấp phát heap. Clipping
  near/far, reciprocal-depth interpolation và depth test xử lý che khuất.
- Triangle hai mặt; illumination 0..255 chọn 3 dải sáng trên albedo. Game
  cấp illumination từng mặt; API mesh có normal/light direction.
- Quad phải phẳng, lồi, vertex theo vòng biên. Hai tam giác chung không có
  viền chéo; clipping cũng giữ đúng cờ viền gốc và không vẽ đường fan nội bộ.
- Outline tam giác được vẽ vào phía trong cạnh, tối đa 4px. Billboard dùng
  external silhouette, alpha threshold 128, nearest sampling và depth test.
- Fog theo depth từng pixel của mesh. Billboard giữ màu atlas và chia dải
  theo illumination; `albedo565` chỉ áp dụng mesh, không thay màu của atlas.
- Bộ đệm depth RGB16 cần 153.600 byte ở 320×240; tổng framebuffer + depth
  307.200 byte. Giữ polygon count/overdraw thấp khi chạy trên MRE CPU.

Mesh hỗ trợ texture RGB565/A8 với UV Q8 theo pixel, nội suy perspective-correct,
nearest sampling và clamp; near/far clipping nội suy UV cùng vertex. Albedo
tint texture, rồi áp dụng cel band và fog. Texel alpha <128 không ghi depth.
Renderer hỗ trợ yaw/pitch, mesh indexed, transform affine Q14, culling, ánh sáng theo normal và UV lặp. Chưa có importer skeleton, roll camera hay physics 3D.
Dùng facade/bảng hiệu/graffiti như quad texture và sprite A8 cho nhân vật.
Tránh coi preset postprocess sprite là phép chuyển ảnh 2D thành mesh 3D.

## Editor và mẫu chạy

**Editor Assets → Game · Urban Toon**: palette mực đen, vàng, cyan, magenta,
posterize, độ bão hòa và outline; metadata dùng `VXPE_ARTSTYLE_URBAN_TOON`.
Các enum cũ giữ nguyên số; preset mới được thêm cuối danh sách.

`examples/UrbanToonDemo`: phố, tòa nhà, cửa sổ, biển hiệu, xe bus, rail,
nhân vật mesh 3D có pose tay/chân, bóng đổ, cầu bộ hành và camera nhìn chéo.
4/6 steer, 2/8 speed, 5 jump, 7 rail, 0 camera, 9 pause, Back exit.
Jump/grind trong mẫu là hiệu ứng showcase; không có collision/mission như
game Jet Set Radio hoàn chỉnh.

Kiểm tra: `vxpe_toon3d_regression.cpp`, bộ CTest core và
`examples/UrbanToonDemo/tests/preview.cpp`. Ảnh preview được xuất trực tiếp
từ framebuffer của renderer, không phải mockup hoặc ảnh AI.

API: `vxpe_toon3d_mesh`, `vxpe_toon3d_transform_point`, `vxpe_toon3d_face_light`; `texture_wrap=1` hỗ trợ UV âm. Mẫu dùng 384 vertex / 640 face, pose thủ tục.

Atlas Editor của UrbanToonDemo được bake từ mesh live: 6 frame 96×144, có alpha. `tools/bake_actor.py` tái tạo bằng renderer native; `tools/make_city.py` tạo texture biển hiệu/ban công/mái hiên.

UrbanToonDemo mặc định 240×320 dọc: world target 120×160 (RGB565 + depth: 76.800 byte), upscale `vxpe2d_upscale2x565`, HUD full resolution. Không còn buffer xoay. Mesh buffer cố định 384 vertex / 640 face. RAM khai báo 1024KB; chưa đo peak heap trên thiết bị.

UrbanToonDemo dùng `vxpe2d_scale2x565` để phóng cảnh 120×160, giữ các màu nguồn và xử lý đường chéo. Sau đó dùng lại 19.200 phần tử worldPixels làm tile nhân vật 80×120 màu + depth, compositing với depth cảnh để giữ che khuất. HUD/nhân vật full resolution, phố half resolution. Scale2x không thêm buffer và không khôi phục chi tiết đã mất khi raster cảnh nhỏ.
