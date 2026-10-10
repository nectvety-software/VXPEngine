import sys,os
from pathlib import Path
sys.path.insert(0,'D:/MRE/VXPEngine/app')
os.chdir('D:/MRE/VXPEngine')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from main import MainWindow,load_stylesheet,configure_windows_app_id,app_icon
from project_store import ProjectStore
configure_windows_app_id()
app=QApplication(sys.argv);app.setApplicationName('VXPEngine');app.setOrganizationName('VXPEngine');app.setOrganizationDomain('vxpengine.local');app.setWindowIcon(app_icon());load_stylesheet(app)
window=MainWindow();project=ProjectStore().register_existing('C:/Users/doxuanhop/Documents/VXP Projects/WampDejaVu');window._open_project(project);window.show();window.raise_();window.activateWindow()
QTimer.singleShot(1500,lambda:Path('C:/Users/doxuanhop/Documents/VXP Projects/WampDejaVu/docs/editor_opened.txt').write_text('VXPEngine MainWindow opened WampDejaVu, App ID '+str(window.current_project.app_id)))
sys.exit(app.exec())
