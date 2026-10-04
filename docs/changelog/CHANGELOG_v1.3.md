# Nova2D Engine v1.3

## Custom Windows controls

- Added `WindowStateController` for Normal, Minimized, Maximized and Hidden states.
- Persisted normal position/size and maximized state through `QSettings`.
- Added safe multi-monitor/DPI placement recovery.
- Added restore-under-pointer when dragging a maximized title bar.
- Synced maximize/restore font icon with real Qt window state changes.
- Removed rounded frame and resize gutter while maximized.
- Close now saves placement and stops the active libGDX/Gradle/CMake process.
