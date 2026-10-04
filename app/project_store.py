"""VXPEngine project registry — UI compatible với Home/Grid cũ, project sinh theo template MRE VXP + core coremre."""
from __future__ import annotations
import json, os, re, time, unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from PySide6.QtCore import QStandardPaths

from core_migration import migrate_core_layout
from project_template import ProjectTemplateManager
from signing_service import (
    DEV_CERT_ID,
    ensure_app_id,
    generate_app_id,
    purge_signing_artifacts,
    read_app_id,
    validate_app_id,
)

ENGINE_VERSION = "2.0.0"
COREMRE_VERSION = ENGINE_VERSION

PROJECT_TEMPLATES = {
    "blank": {"name": "Dự án trống (MRE VXP)", "description": "Khung MRE VXP 240×320 hoặc 320×240 trống: không tài nguyên, không SFX. Thêm ảnh/âm thanh từ Thư viện của VXPEngine khi cần."},
}
INVALID_WINDOWS_NAMES = {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}

@dataclass(slots=True)
class ProjectInfo:
    name: str
    path: str
    created_at: str
    modified_at: str
    engine_version: str = ENGINE_VERSION
    platform: str = "MRE VXP (240x320)"
    preview_variant: int = 0
    framework: str = "VXPEngine/MRE"
    framework_version: str = ENGINE_VERSION
    language: str = "C (MRE SDK)"
    app_name: str = ""
    developer: str = "VXPstore"
    ram_kb: str = "800"
    api_list: str = "File Audio ProMng"
    imsi: str = "91234567890"
    app_id: str = "0"
    template_key: str = "blank"
    native_enabled: bool = False
    viewport_width: int = 240
    viewport_height: int = 320
    aspect_ratio: str = "3:4"
    package_name: str = "com.vxp.test"
    layout_version: int = 1
    template_version: str = ""

    @property
    def folder(self): return Path(self.path)
    @property
    def descriptor(self): return self.folder / "project.vxp.json"
    @property
    def package_path(self): return Path(*self.package_name.split("."))
    @property
    def cert_id(self):
        """Certid luôn do engine cấp khi build; project không giữ chứng thư."""
        return DEV_CERT_ID

    @property
    def is_signed_ready(self) -> bool:
        """True khi project đã có App ID riêng do engine cấp."""
        return self.app_id != "0"

class ProjectStore:
    def __init__(self):
        app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not app_data: app_data = str(Path.home()/".vxpe_storage")
        self.data_dir = Path(app_data)/"VXPEngine"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.data_dir/"projects.json"
    @staticmethod
    def default_projects_directory(): 
        docs=QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        base=Path(docs) if docs else Path.home()/"Documents"
        return base/"VXP Projects"
    @staticmethod
    def validate_project_name(name): 
        v=name.strip()
        if not v: raise ValueError("Nhập tên dự án.")
        if len(v)>60: raise ValueError("Tên quá dài.")
        if re.search(r'[<>:"/\\|?*\x00-\x1F]',v): raise ValueError('Ký tự cấm')
        if v.rstrip(". ")!=v: raise ValueError("Không kết thúc bằng .")
        if v.split(".",1)[0].upper() in INVALID_WINDOWS_NAMES: raise ValueError("Tên Windows reserved.")
        return v
    @staticmethod
    def app_name_from_project(name):
        a=unicodedata.normalize("NFKD",name)
        a="".join(c for c in a if not unicodedata.combining(c))
        s=re.sub(r"[^a-z0-9]+","_",a.lower()).strip("_")
        s=re.sub(r"_+","_",s)
        if not s: s="my_vxp"
        if s[0].isdigit(): s=f"vxp_{s}"
        return s[:24].rstrip("_") or "my_vxp"
    @staticmethod
    def package_from_project_name(name):
        a=unicodedata.normalize("NFKD",name)
        a="".join(c for c in a if not unicodedata.combining(c))
        s=re.sub(r"[^a-z0-9]+","_",a.lower()).strip("_")
        s=re.sub(r"_+","_",s)
        if not s: s="ten_project"
        if s[0].isdigit(): s=f"game_{s}"
        return f"com.vxp.{s[:40].rstrip('_')}"
    @staticmethod
    def validate_app_name(v):
        v=v.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,30}",v): raise ValueError("APP_NAME")
        return v
    @staticmethod
    def validate_package_name(v):
        v=v.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,}",v): raise ValueError("Package ID")
        return v
    def load(self):
        if not self.registry_path.exists(): return []
        try: raw=json.loads(self.registry_path.read_text(encoding="utf-8"))
        except: return []
        projects=[]; seen=set(); valid=set(ProjectInfo.__dataclass_fields__)
        for item in raw if isinstance(raw,list) else []:
            if not isinstance(item,dict): continue
            norm={k:v for k,v in item.items() if k in valid}
            # compat: legacy projects may only have package_name; map it to app_name
            if "app_name" not in norm and "package_name" in item:
                try:
                    pkg=str(item["package_name"])
                    last=pkg.split(".")[-1]
                    norm["app_name"]=self.app_name_from_project(last)
                except: pass
            # compat: legacy registry lưu "appid"; "certid" không còn thuộc project
            if "app_id" not in norm and "appid" in item:
                try: norm["app_id"]=validate_app_id(item["appid"])
                except: pass
            try: p=ProjectInfo(**norm)
            except: continue
            import os; n=os.path.normcase(os.path.abspath(p.path))
            if n in seen or not Path(p.path).exists(): continue
            seen.add(n); projects.append(p)
        changed=False
        for p in projects:
            # Không bao giờ để chứng thư/khóa ký nằm trong project của người dùng.
            self.purge_signing(p)
            # Project cũ chưa có App ID riêng → engine cấp lúc nạp, không trùng id đang tồn tại
            if p.app_id=="0":
                p.app_id=generate_app_id(self.reserved_app_ids(excluding=p.path))
                try: self._write_descriptor(p)
                except: pass
                changed=True
        if changed: self.save(projects)
        projects.sort(key=lambda p: p.modified_at, reverse=True)
        return projects
    def reserved_app_ids(self, excluding=None):
        excluded=os.path.normcase(os.path.abspath(excluding)) if excluding else None
        ids=set()
        try: raw=json.loads(self.registry_path.read_text(encoding="utf-8"))
        except: return ids
        for item in raw if isinstance(raw,list) else []:
            if not isinstance(item,dict): continue
            path=item.get("path")
            if excluded is not None and path and os.path.normcase(os.path.abspath(str(path)))==excluded: continue
            value=item.get("app_id", item.get("appid","0"))
            try: value=validate_app_id(value)
            except: continue
            if value!="0": ids.add(value)
        return ids
    def purge_signing(self, project_or_path):
        """Xóa khóa ký/thư mục signing lọt vào project (chỉ tài sản do engine sở hữu)."""
        path = getattr(project_or_path, "path", project_or_path)
        try: return purge_signing_artifacts(path)
        except OSError: return []
    def migrate_core(self, project_or_path) -> list[str]:
        """Đưa project tạo trước khi gộp core về layout `engine/coremre`.

        Trả về danh sách thông báo để IDE in ra console; rỗng khi không có gì phải làm.
        Hàm rẻ khi project đã đúng layout (chỉ vài lệnh stat).
        """
        path = getattr(project_or_path, "path", project_or_path)
        try: return migrate_core_layout(path)
        except OSError as error: return [f"[Core] Không thể di trú core: {error}"]
    def sync_template(self, project: ProjectInfo) -> list[str]:
        """Cập nhật phần hạ tầng layout v2 mà không ghi đè code/asset người dùng."""
        if int(getattr(project, "layout_version", 1)) < 2:
            return []
        manager=self._template_manager()
        updated,preserved=manager.sync(project.folder)
        if Path("CMakeLists.txt") in updated:
            self._patch_cmake(project)
        patchable={p.as_posix() for p in updated if p.as_posix() in {
            "scripts/build_arm.bat","scripts/run_vxpemu.bat","README.md"
        }}
        if patchable:
            self._patch_scripts(project, patchable)
        manager.finalize(project.folder, updated)
        project.layout_version=manager.layout_version
        project.template_version=manager.version
        notices=[]
        if updated:
            notices.append(f"[Template] Đã cập nhật an toàn {len(updated)} tệp hạ tầng lên {manager.version}.")
        if preserved:
            notices.append(f"[Template] Giữ nguyên {len(preserved)} tệp đã sửa cục bộ; không ghi đè thay đổi của bạn.")
        return notices
    def sync_app_id(self, project):
        """Bảo đảm project có App ID riêng trong descriptor, không trùng project khác."""
        project.app_id=ensure_app_id(project.path, self.reserved_app_ids(excluding=project.path))
        return project.app_id
    def save(self, projects):
        payload=[asdict(p) for p in projects]
        content=json.dumps(payload, ensure_ascii=False, indent=2)
        tmp=self.registry_path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        last_error=None
        for attempt in range(4):
            try:
                tmp.replace(self.registry_path)
                return
            except OSError as error:
                # Windows: antivirus/process khác có thể khóa registry tạm — thử lại rồi ghi trực tiếp.
                last_error=error
                time.sleep(0.05 * (attempt + 1))
        try:
            self.registry_path.write_text(content, encoding="utf-8")
        except OSError:
            raise last_error from None
        try:
            tmp.unlink()
        except OSError:
            pass
    def upsert(self, project):
        if project.app_id=="0":
            # Project được mở lại từ máy/thư mục khác: ưu tiên App ID đã lưu trong descriptor.
            try: project.app_id=read_app_id(project.path)
            except OSError: pass
        if project.app_id=="0":
            project.app_id=generate_app_id(self.reserved_app_ids(excluding=project.path))
        projects=self.load()
        n=os.path.normcase(os.path.abspath(project.path))
        projects=[p for p in projects if os.path.normcase(os.path.abspath(p.path))!=n]
        projects.insert(0,project); self.save(projects); return project
    def remove(self, path):
        import os; n=os.path.normcase(os.path.abspath(path))
        self.save([p for p in self.load() if os.path.normcase(os.path.abspath(p.path))!=n])
    def touch(self, project):
        project.modified_at=datetime.now(timezone.utc).isoformat()
        return self.upsert(project)
    def create_project(self, name, base_directory, app_name=None, developer="VXPstore", ram_kb="800", api_list="File Audio ProMng", template_key="blank", **kwargs):
        # Legacy compat: package_name -> app_name, viewport -> 240x320, native_enabled ignored
        if app_name is None and "package_name" in kwargs:
            pkg=str(kwargs["package_name"]).strip()
            last=pkg.split(".")[-1] if "." in pkg else pkg
            try: app_name=self.validate_app_name(last)
            except: app_name=self.app_name_from_project(name)
        project_name=self.validate_project_name(name)
        app=self.validate_app_name(app_name or self.app_name_from_project(project_name))
        if not base_directory.strip(): raise ValueError("Chọn thư mục lưu.")
        base=Path(base_directory).expanduser(); base.mkdir(parents=True, exist_ok=True)
        project_dir=base/project_name
        if project_dir.exists() and any(project_dir.iterdir()): raise FileExistsError(f"Thư mục '{project_dir}' đã tồn tại.")
        tk=template_key if template_key in PROJECT_TEMPLATES else "blank"
        project_dir.mkdir(parents=True, exist_ok=True)
        now=datetime.now(timezone.utc).isoformat()
        # MRE QVGA chỉ dùng hai hướng vật lý: portrait hoặc landscape.
        vw=int(kwargs.get("viewport_width",240)); vh=int(kwargs.get("viewport_height",320))
        vw, vh = ((320, 240) if vw > vh else (240, 320))
        pkg_name=kwargs.get("package_name", self.package_from_project_name(project_name))
        try: pkg_name=self.validate_package_name(pkg_name)
        except: pkg_name=self.package_from_project_name(project_name)
        # Mỗi project có một App ID riêng do engine cấp (máy retail yêu cầu id khác 0).
        app_id=generate_app_id(self.reserved_app_ids())
        aspect="4:3" if vw > vh else "3:4"
        project=ProjectInfo(name=project_name, path=str(project_dir.resolve()), created_at=now, modified_at=now,
                            preview_variant=abs(hash(str(project_dir)))%6, app_name=app, developer=developer,
                            ram_kb=ram_kb, api_list=api_list, template_key=tk, app_id=app_id,
                            viewport_width=vw, viewport_height=vh, aspect_ratio=aspect,
                            platform=f"MRE VXP ({vw}x{vh})", package_name=pkg_name)
        self._write_template(project)
        return self.upsert(project)
    def register_existing(self, path):
        p=Path(path).expanduser().resolve()
        if not p.is_dir(): raise ValueError("Không phải thư mục.")
        desc=p/"project.vxp.json"
        if desc.exists():
            data={}
            try: data=json.loads(desc.read_text(encoding="utf-8"))
            except (OSError, ValueError): data={}
            if not isinstance(data, dict): data={}
            name=data.get("name") or p.name
            now=datetime.now(timezone.utc).isoformat()
            info=self._from_descriptor(p, name, data, now)
            self.migrate_core(p)        # project tạo trước khi gộp core → engine/coremre
            info=self.upsert(info)      # giữ nguyên App ID đã có, cấp mới nếu chưa có
            self._write_descriptor(info)
            return info
        if (p/"src"/"main.c").exists() or (p/"CMakeLists.txt").exists():
            now=datetime.now(timezone.utc).isoformat()
            info=ProjectInfo(name=p.name, path=str(p), created_at=now, modified_at=now)
            self.migrate_core(p)     # project tạo trước khi gộp core → engine/coremre
            info=self.upsert(info)   # engine cấp App ID riêng trước khi ghi descriptor
            self._write_descriptor(info); return info
        raise ValueError("Không phải project VXP.")
    def _from_descriptor(self, root, name, data, now):
        """Tạo ProjectInfo từ descriptor có sẵn để không mất App ID/metadata."""
        screen=data.get("screen") or {}
        mre=data.get("mre") or {}
        def pick(key, default, caster=str):
            try: return caster(data.get(key, default))
            except (TypeError, ValueError): return default
        app_id="0"
        for candidate in (data.get("app_id"), data.get("appid"), mre.get("app_id"), mre.get("appid")):
            try:
                app_id=validate_app_id(candidate); break
            except (ValueError, TypeError): continue
        template=data.get("template", "blank")
        info=ProjectInfo(name=str(name), path=str(root), created_at=data.get("created_at") or now, modified_at=now,
                         app_name=data.get("app_name") or self.app_name_from_project(str(name)),
                         developer=data.get("developer") or "VXPstore",
                         ram_kb=pick("ram_kb", mre.get("ram_kb", "800")),
                         api_list=mre.get("api") or "File Audio ProMng",
                         app_id=app_id, template_key=template if template in PROJECT_TEMPLATES else "blank",
                         viewport_width=int(pick("viewport_width", screen.get("width", 240), int)),
                         viewport_height=int(pick("viewport_height", screen.get("height", 320), int)),
                         package_name=data.get("package_name") or self.package_from_project_name(str(name)),
                         layout_version=max(1, int(pick("layout_version", 1, int))),
                         template_version=str(data.get("template_version", "") or ""))
        info.aspect_ratio="4:3" if info.viewport_width > info.viewport_height else "3:4"
        info.platform=f"MRE VXP ({info.viewport_width}x{info.viewport_height})"
        return info
    def _write_template(self, project):
        manager=self._template_manager()
        copied=manager.create(project.folder)
        project.layout_version=manager.layout_version
        project.template_version=manager.version
        purge_signing_artifacts(project.folder)
        self._patch_cmake(project); self._patch_scripts(project); self._write_descriptor(project)
        if project.template_key=="blank": self._strip_to_blank(project)
        manager.finalize(project.folder,copied,initialize=True)
    @staticmethod
    def _template_manager():
        template_dir=Path(__file__).resolve().parent.parent/"template_blank"
        if not template_dir.exists(): raise FileNotFoundError("Thiếu thư mục template_blank/ trong VXPEngine.")
        return ProjectTemplateManager(template_dir)
    def _patch_cmake(self, project):
        cmake_path=project.folder/"CMakeLists.txt"
        if not cmake_path.exists(): return
        try: text=cmake_path.read_text(encoding="utf-8")
        except: return
        text=re.sub(r'set\(APP_NAME\s+"[^"]+"\)',f'set(APP_NAME "{project.app_name}")',text)
        text=re.sub(r'set\(DEVELOPER_NAME\s+"[^"]+"\)',f'set(DEVELOPER_NAME "{project.developer}")',text)
        text=re.sub(r'set\(RAM\s+"[^"]+"\)',f'set(RAM "{project.ram_kb}")',text)
        text=re.sub(r'project\s*\(\s*"[^"]+"\s*\)',f'project("{project.app_name}")',text)
        # App ID riêng của project: cập nhật cả giá trị CACHE lẫn non-CACHE
        text=re.sub(r'set\(APPID\s+"[^"]+"\s*(?:CACHE\s+STRING\s+"[^"]*")?\)',f'set(APPID "{project.app_id}" CACHE STRING "App id")',text)
        # Project luôn ở trạng thái chưa ký: certid dev và không trỏ tới khóa nào.
        # Khóa retail (certid 100) chỉ được engine truyền qua -D khi build signed.
        text=re.sub(r'set\(CERTID\s+"[^"]+"\s*(?:CACHE\s+STRING\s+"[^"]*")?\)',f'set(CERTID "{project.cert_id}" CACHE STRING "Cert id")',text)
        text=re.sub(r'set\(CERT\s+"[^"]+"\s*(?:CACHE\s+STRING\s+"[^"]*")?\)','set(CERT "none" CACHE STRING "Path to cert")',text)
        cmake_path.write_text(text,encoding="utf-8")
    def _patch_scripts(self, project, only=None):
        old_names=("BlankApp",)
        targets=["scripts/run_vxpemu.bat","scripts/build_arm.bat","run_vxpemu.bat","build_arm.bat"]
        src_dir=project.folder/"src"
        if src_dir.exists():
            targets.extend(
                item.relative_to(project.folder).as_posix()
                for item in src_dir.iterdir()
                if item.suffix in {".c",".h"}
            )
        for script in targets:
            if only is not None and script not in only: continue
            path=project.folder/script
            if not path.exists(): continue
            try: text=path.read_text(encoding="utf-8",errors="replace")
            except OSError: continue
            for old in old_names: text=text.replace(old,project.app_name)
            path.write_text(text,encoding="utf-8")
        readme=project.folder/"README.md"
        if only is not None and "README.md" not in only: return
        if readme.exists():
            try: text=readme.read_text(encoding="utf-8",errors="replace")
            except OSError: text=""
            for old in old_names: text=text.replace(old,project.app_name)
            readme.write_text(text,encoding="utf-8")
    def _write_descriptor(self, project):
        payload=self._descriptor_payload(project)
        project.descriptor.parent.mkdir(parents=True, exist_ok=True)
        project.descriptor.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    def _descriptor_payload(self, project):
        orientation="Landscape" if project.viewport_width > project.viewport_height else "Portrait"
        payload={"format":"VXPEngine VXP Project","format_version":2,"engine_version":ENGINE_VERSION,"name":project.name,"app_name":project.app_name,"developer":project.developer,"template":project.template_key,"template_version":project.template_version,"layout_version":project.layout_version,"created_at":project.created_at,"modified_at":project.modified_at,"screen":{"width":project.viewport_width,"height":project.viewport_height,"type":f"MRE QVGA {orientation}"},"mre":{"sdk_version":"3.0","api":project.api_list,"ram_kb":project.ram_kb,"imsi":project.imsi}}
        if project.descriptor.exists():     # giữ các trường lạ do bản khác ghi thêm
            try:
                old=json.loads(project.descriptor.read_text(encoding="utf-8"))
                if isinstance(old,dict):
                    for key,value in old.items():
                        if key not in payload: payload[key]=value
            except (OSError, ValueError): pass
        # App ID riêng của project — tài sản nhận dạng duy nhất mà project giữ.
        # Chứng thư/certid không bao giờ nằm ở đây, engine cấp lúc build.
        payload["app_id"]=project.app_id
        payload["signing"]={"owner":"VXPEngine","cert_id":project.cert_id,"app_id_source":"engine"}
        mre=payload.setdefault("mre",{})
        mre["app_id"]=project.app_id
        mre.pop("appid",None); mre.pop("certid",None)
        payload.pop("appid",None); payload.pop("certid",None)
        return payload
    def _strip_to_blank(self, project):
        readme=project.folder/"README_VXP.md"
        readme.write_text(f"# {project.name} — VXPEngine Blank (MainScreen {project.viewport_width}x{project.viewport_height})\n\nApp: {project.app_name}.vxp\nCore: coremre\n",encoding="utf-8")
        scenes_dir=project.folder/"assets"/"scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        orientation="landscape" if project.viewport_width > project.viewport_height else "portrait"
        main_dtfe={"name":"MainScreen","screen_id":"main","type":"VXPScreen","viewport":{"width":project.viewport_width,"height":project.viewport_height,"type":"FitViewport","orientation":orientation},"engine":{"core":"coremre","version":ENGINE_VERSION},"children":[{"id":"camera2d","name":"Camera2D","type":"OrthographicCamera","position":[0,0],"zoom":[1,1]},{"id":"bg","name":"Background","code_name":"Background","type":"Rectangle2D","position":[0,0],"scale":[1,1],"display_size":[project.viewport_width,project.viewport_height],"shape":{"width":project.viewport_width,"height":project.viewport_height,"fill":"#0F1B2E","stroke":"#263B57","stroke_width":0},"component_category":"background","ui_role":"Background","resizable":False,"lock_aspect":True,"locked":True,"pixel_snap":True,"z_index":-10}]}
        (scenes_dir/"main.dtfe").write_text(json.dumps(main_dtfe,ensure_ascii=False,indent=2),encoding="utf-8")
    @staticmethod
    def ensure_dtfe_runtime(project_path):
        return False, "VXPEngine VXP runtime OK"
