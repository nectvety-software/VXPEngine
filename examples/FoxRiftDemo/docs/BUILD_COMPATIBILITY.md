# Build compatibility repair — 2026-10-07

The installed VXPEPython tool host only permits the three SDK tools. Project roster/world scripts previously used that host and failed with code 3. Both ARM header-generation commands now use CMake JSON support (minimum CMake 3.19), validate editable gameplay JSON, and produce equivalent runtime definitions.

The older installed core package contains 195 files and lacks VxpStory2D. The project carries a signed 261-file core snapshot in .vxpe/coremre/2.0.0 and uses it when the supplied package lacks Story2D. Program Files was not updated: Windows denied write access. The old package still verifies successfully.

The SDK host packaging also omitted dynamically loaded signer dependencies, including secrets. Explicit imports in packaging/windows/vxpe_python_dispatcher.py fix dependency discovery. The rebuilt host is engine/coremre/sdk/python/VXPEPython.exe in this workspace.

Use D:/MRE/VXPEngine/run_windows.bat to open the repaired workspace Editor. The previously installed Program Files host still requires an installer update to receive the signing fix.

Verified: installed ARM compiler + Ninja + SDK resource/pack tools build main_vxp successfully; CMake-generated headers match both Python generators; host gameplay tests pass; bundled core signature/integrity passes; repaired frozen SDK host signs App ID 1053070, certid 100 and verifies RSA-SHA1 successfully. Output: build-arm-signed/main/vaelora_duel-signed.vxp.
