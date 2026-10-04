# VXPEngine Architecture

So sánh với PixelRoot32 để dễ port.

## Engine
- `vxpengine::core::Engine` giữ `Renderer` + `InputManager` + `Scene*`.
- `Engine::init()` tạo `DrawSurface` phù hợp platform (VMDrawer cho MRE, SDLDrawer cho Native).
- `Engine::update()` tính deltaTime từ SDL_GetTicks / chrono, gọi Scene::update.
- `Engine::draw()` gọi Renderer::beginFrame -> Scene::draw -> present.
- Trên MRE, `Engine::run()` không dùng; `src/main.c` của app sẽ gọi `vm_create_timer(50, tick)` và mỗi tick gọi engine->update/draw + flush layer.

## Scene / Entity
- Tối đa 64 entities, sort theo renderLayer (0=bg, 1=game, 2=ui).
- `Scene::init()` là idempotent (gọi lại sẽ clear).

## Renderer / DrawSurface
- `DrawSurface` là interface thuần ảo: clear, drawPixel, drawFilledRect, drawText, present, processEvents.
- `VMDrawer` ghi vào `g_buf` (vm_graphic_get_layer_buffer) và fb mirror.
- `SDLDrawer` dùng SDL_Texture RGB565 streaming.

## Input
- MRE keycodes được map vào `InputManager::KEY_*` trong `main.c` handle_keyevt.
- Desktop SDL: SDLDrawer::processEvents trả về false khi quit; mở rộng để map SDLK_* vào InputManager nếu cần.

## Porting từ PixelRoot32
- Thay `#include "core/Engine.h"` -> `#include "vxpengine/vxpengine.h"` và đổi namespace `pixelroot32::` -> `vxpengine::`.
- Sprite format giữ nguyên packed 1bpp; có thể reuse TileMap/Renderer API tương tự.
- Thay `PLATFORM_NATIVE` guards bằng `VXPENGINE_HAS_SDL2` / `VXPENGINE_MRE`.
