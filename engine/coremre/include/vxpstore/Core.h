#pragma once
/* vxpstore/Core.h — Tên core riêng của VXPEngine cho MRE VXP + Arduino.
 * Dựa trên PixelRoot32-Game-Engine nhưng đã tách thành core độc lập:
 * chỉ hỗ trợ MRE VXP và Arduino, KHÔNG dùng cho Java, KHÔNG còn tên PixelRoot32
 * ở tầng người dùng. Bên trong vẫn tái sử dụng thuật toán đã kiểm chứng.
 */
#include "core/Engine.h"
#include "core/Scene.h"
#include "core/Entity.h"
#include "graphics/Renderer.h"
#include "graphics/Camera2D.h"
#include "input/InputManager.h"

namespace vxpstore {
using Engine = ::pixelroot32::core::Engine;
using Scene = ::pixelroot32::core::Scene;
using Entity = ::pixelroot32::core::Entity;
using Renderer = ::pixelroot32::graphics::Renderer;
using Camera2D = ::pixelroot32::graphics::Camera2D;
using InputManager = ::pixelroot32::input::InputManager;
} // namespace vxpstore

/* Alias ngắn: corevxp == vxpstore == coremre (cùng một core duy nhất). */
namespace corevxp {
using Engine = ::pixelroot32::core::Engine;
using Scene = ::pixelroot32::core::Scene;
using Entity = ::pixelroot32::core::Entity;
using Renderer = ::pixelroot32::graphics::Renderer;
using Camera2D = ::pixelroot32::graphics::Camera2D;
using InputManager = ::pixelroot32::input::InputManager;
} // namespace corevxp
