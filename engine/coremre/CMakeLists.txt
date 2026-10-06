cmake_minimum_required(VERSION 3.16)
project(coremre VERSION 2.0.0 LANGUAGES CXX)

set(COREMRE_SOURCES
    src/core/PhysicsActor.cpp
    src/core/Scene.cpp
    src/core/SceneManager.cpp
    src/gameplay/GameplayEventBus.cpp
    src/gameplay/InteractionTracker.cpp
    src/gameplay/StateMachine.cpp
    src/graphics/Camera2D.cpp
    src/graphics/CameraEffects.cpp
    src/graphics/Color.cpp
    src/graphics/DirtyGrid.cpp
    src/graphics/Font5x7.cpp
    src/graphics/FontManager.cpp
    src/graphics/StaticTilemapLayerCache.cpp
    src/graphics/VxpRender2D.cpp
    src/graphics/VxpColorGrade.cpp
    src/graphics/VxpStage2D.cpp
    src/graphics/VxpScene25D.cpp
    src/graphics/VxpArtStyle.cpp
    src/graphics/VxpToon3D.cpp
      src/graphics/VxpDungeonFx.cpp
    src/graphics/VxpCinematic2D.cpp
    src/graphics/VxpLight2D.cpp
    src/graphics/VxpSpriteFx.cpp
    src/graphics/VxpActorSprite2D.cpp
    src/graphics/VxpVfx2D.cpp
    src/graphics/particles/VxpParticlePool.cpp
    src/graphics/particles/ParticleEmitter.cpp
    src/graphics/ui/UIAnchorLayout.cpp
    src/graphics/ui/UIButton.cpp
    src/graphics/ui/UICheckBox.cpp
    src/graphics/ui/UIGridLayout.cpp
    src/graphics/ui/UIHorizontalLayout.cpp
    src/graphics/ui/UILabel.cpp
    src/graphics/ui/UILayout.cpp
    src/graphics/ui/UIManager.cpp
    src/graphics/ui/UIPaddingContainer.cpp
    src/graphics/ui/UIPanel.cpp
    src/graphics/ui/UISprite.cpp
    src/graphics/ui/UISpriteRef.cpp
    src/graphics/ui/UISpriteRow.cpp
    src/graphics/ui/UITouchButton.cpp
    src/graphics/ui/UITouchCheckbox.cpp
    src/graphics/ui/UITouchSlider.cpp
    src/graphics/ui/UIVerticalLayout.cpp
    src/input/ActorTouchController.cpp
    src/input/TouchCalibration.cpp
    src/input/TouchEventDispatcher.cpp
    src/input/TouchEventQueue.cpp
    src/input/TouchManager.cpp
    src/input/TouchStateMachine.cpp
    src/physics/CollisionPrimitives.cpp
    src/physics/CollisionSystem.cpp
    src/physics/KinematicActor.cpp
    src/physics/RigidActor.cpp
    src/physics/SensorActor.cpp
    src/physics/SpatialGrid.cpp
    src/physics/StaticActor.cpp
    src/physics/TileCollisionBuilder.cpp
    src/physics/TileConsumptionHelper.cpp
    src/physics/TilePixelCollision.cpp
    src/platforms/PlatformCapabilities.cpp
    src/platforms/PlatformLog.cpp
)

add_library(coremre STATIC ${COREMRE_SOURCES})
add_library(VXPEngine::coremre ALIAS coremre)
target_include_directories(coremre PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
if(MRE_SDK)
    target_include_directories(coremre PUBLIC ${MRE_SDK}/include)
endif()
target_compile_features(coremre PUBLIC cxx_std_17)
target_compile_definitions(coremre PUBLIC
    COREMRE_PLATFORM_MRE=1
    PIXELROOT32_ENABLE_PARTICLES=0
    # Selective 8bpp clear instead of full framebuffer wipe every frame.
    # Matches platformio native_test; no-op on SDL2 (no sprite buffer).
    PIXELROOT32_ENABLE_DIRTY_REGIONS=1
)
set_target_properties(coremre PROPERTIES CXX_EXTENSIONS OFF OUTPUT_NAME coremre POSITION_INDEPENDENT_CODE ON)

if(CMAKE_SYSTEM_NAME STREQUAL "Generic")
    target_compile_options(coremre PRIVATE -Os -ffunction-sections -fdata-sections -fno-exceptions -fno-rtti)
endif()
