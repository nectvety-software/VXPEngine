# Asset Sheet — CungThuBongDen

Preview trực quan: `docs/asset_sheet_preview.png` (render từ chính các file `.raw`
trong `resources/gen/` bằng `assets/tools/AssetSheet.java`).
Nguồn: các sheet PNG trong `assets/` (titleset, sheet_labeled), cắt theo
`assets/tools/sprite_manifest.txt` bằng `AssetTool.java`.

Định dạng `.raw` (tự mô tả, little-endian):
```
offset 0: uint16 width
offset 2: uint16 height
offset 4: uint16 opaque (0 = có mask 1-bit phía sau, 1 = full hộp)
offset 6: uint16 reserved (0)
offset 8: width*height pixel RGB565
sau đó  : mask trong suốt 1-bit (MSB-first, w*h/8 byte, 1 = vẽ)
```

## Nhóm sprite (73 file)

### Nền và khối (opaque)
| Tên | Kích thước | Vai trò |
|-----|-----------|---------|
| ground1..4 | 24x24 | Ô đất nền, 4 biến thể xếp ngẫu nhiên |
| gh1..3 | 24x22 | Sàn gỗ một chiều (nhảy xuyên từ dưới lên) |
| block | 24x24 | Khối gạch đặc |
| spikes | 48x24 | Bãi gai — kéo dãn theo độ dài dải `H` |
| ladder | 12x24 | Thang — kéo dãn theo cột `L` (18px rộng) |
| wall1..6 | 24x24 | Tường/backdrop |
| tex_brick, tex_wood, tex_fog | 24x24 | Texture phủ |

### Parallax (opaque, phủ toàn chiều rộng 240px)
| Tên | Vai trò |
|-----|---------|
| bg_mid | Dải mây/trăng ở y=30 |
| bg_far | Tháp lâu đài xa ở y=58 |
| bg_near | Kiến trúc đổ nát, lát lặp từ y=100 (mỗi 46px) |

### Nhân vật
| Tên | Kích thước | Vai trò |
|-----|-----------|---------|
| arch_a/b | ~24x30 | Cung thủ: idle / đi |
| arch_c | 24x28 | Leo thang + nhảy |
| arch_d | 24x30 | Đi (frame 2) |
| arch_shoot | 24x30 | Tư thế giương cung |
| arch_hit | 24x30 | Bị trúng đòn |
| ogre_a/b/c, ogre_hit | 34x40 | Ogre bộ hành (đi, đánh) |
| boss_ogre | 56x40 | Trùm ogre đỏ (mỗi 5 đợt) |
| dragon_a/b/c | 42x22 | Rồng lửa bay (3 frame vẫy cánh) |

### Trang trí (vẽ theo ký tự trong maps/arena1.txt)
window `w` · chain1/2 `h` · shopdoor `s` · archway `a` · crate `k` · barrel `b` ·
banner `n` · pillar `i` · rubble `r` · collapsed · torch1..4 `T` (4 frame lửa, 8 tick/frame)

### Vật phẩm & hiệu ứng
| Tên | Vai trò |
|-----|---------|
| coin | Vàng rơi từ ogre (+1..3) |
| gem | Ngọc (+15 MP, +15 điểm) — rồng & trùm rơi |
| spark_s, spark_b | Tia lửa trúng đòn / nổ |
| arrow1..3 | Tên thường (2 frame bay) / tên power (to, đỏ) |

### Icon HUD & nút
| Tên | Vai trò |
|-----|---------|
| portrait | Chân dung cung thủ góc trái HUD |
| ic_gold, ic_silver, ic_gem | Bộ đếm tài nguyên |
| ic_hpotion, ic_mpotion | Thuốc (HUD + rơi) |
| ic_quiver | Bộ đếm tên |
| badge_dash/power/multi | Icon 3 kỹ năng (vẽ thu nhỏ 16px trong nút) |
| btn_dash/power/multi | Nút kỹ năng dưới màn hình (kèm label phím 7/9/0, phủ tối khi cooldown) |

### Toàn màn hình
| Tên | Kích thước | Vai trò |
|-----|-----------|---------|
| splash | 240x320 (opaque) | Màn hình title — vẽ riêng, chỉ giữ trong lúc ở ST_TITLE |

## Âm thanh (đóng gói trong .vxp, extract ra thẻ nhớ lần đầu chạy)
| Tài nguyên | Nguồn | Phát khi |
|-----------|-------|----------|
| sfx_shoot.mp3 | swing-whoosh-1 | Bắn tên |
| sfx_hit.mp3 | axe-hit-flesh | Trúng đòn (player hoặc địch) |
| sfx_pickup.mp3 | health-pickup-6860 | Nhặt vật phẩm / mua / uống thuốc |
| sfx_explode.mp3 | explosion-fx | Địch nổ khi chết |

## Tái sinh sprite
```bash
cd assets/tools
javac -d . AssetTool.java
java -cp . AssetTool build sprite_manifest.txt ..\..\resources\gen   # xem manifest để biết cú pháp dòng
# sau đó build lại (cmake sẽ đóng gói resources/gen vào resources.res)
```
Xem trước: `java -cp . AssetSheet ..\..\resources\gen out.png` (biên dịch `AssetSheet.java` trước).
