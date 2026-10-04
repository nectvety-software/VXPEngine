# Nova2D Engine 1.7.0 — Assets Codebase Manager

## Assets submenu

The three-dot button in the Assets header now opens a font-icon menu:

- **Nhập tài nguyên…** — select one or more files and save them in a recommended project directory.
- **Tạo thư mục…** — choose the parent branch of the libGDX codebase and create a folder.
- **Tạo tệp…** — choose a codebase branch, create a named file, and generate a starter template based on its extension.
- **Làm mới Assets** — rescan the real project filesystem.
- **Mở thư mục dự án** — open the current project in Windows Explorer.

## Codebase-aware destinations

The destination modal offers these conventional locations:

- `assets/textures`
- `assets/audio`
- `assets/fonts`
- `assets/shaders`
- `assets/data`
- `assets/ui`
- `assets/maps`
- `scenes`
- `core/src/main/java/<package>`
- `lwjgl3/src/main/java/<package>/lwjgl3`
- `android/src/main/java/<package>/android`
- `native/src/main/cpp`

All writes are validated to remain inside the current project folder.

## File behavior

- Imported filename collisions receive `_1`, `_2`, and so on instead of silently overwriting data.
- Newly created `.java`, C/C++/header, `.json`, `.nova`, XML, shader, YAML, and Markdown files receive useful starter content.
- Double-clicking text/source files opens them in Nova2D's code editor with line numbers and syntax highlighting.
- Double-clicking binary resources opens them with the Windows default application.
- The Assets tree is built from the actual filesystem and refreshes after every operation.
