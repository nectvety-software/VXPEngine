import sys
sys.path.insert(0, r"D:\MRE\VXPEngine\app")
from project_store import ProjectStore
s = ProjectStore()
p = s.create_project(
    "Rootline Rush",
    r"C:\Users\doxuanhop\Documents\VXP Projects",
    app_name="rootline_rush",
    developer="VXPstore",
    ram_kb="800",
    api_list="File Audio ProMng",
    viewport_width=320,
    viewport_height=240,
)
print(p.path)
print("APPID=" + p.app_id)
