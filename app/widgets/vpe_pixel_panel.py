"""Embed VPE Pixel in Asset Editor, sharing its original Documents library."""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QPalette
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
from vendor.vpe_pixel.vpx_editor.main_window import MainWindow
from vendor.vpe_pixel.vpx_editor.document import Document
from vendor.vpe_pixel.vpx_editor.theme import get_theme
from vendor.vpe_pixel.vpx_editor.vpe import rgb_to_565, c565_to_rgb


class EmbeddedPixelWindow(MainWindow):
    def _apply_theme(self):
        # Embedded tools must never replace VXPEngine's application QSS/palette.
        self.setStyleSheet(get_theme().qss())
        tokens=get_theme().tokens
        palette=QPalette()
        for role,key in [(QPalette.ColorRole.Window,'bg'),(QPalette.ColorRole.WindowText,'text'),
                         (QPalette.ColorRole.Base,'surface'),(QPalette.ColorRole.Text,'text'),
                         (QPalette.ColorRole.Button,'surface2'),(QPalette.ColorRole.ButtonText,'text'),
                         (QPalette.ColorRole.Highlight,'accent'),(QPalette.ColorRole.PlaceholderText,'muted')]:
            palette.setColor(role,QColor(tokens[key]))
        self.setPalette(palette)
        if hasattr(self, 'canvas'):
            self.canvas._checker=self.canvas._make_checker()
            self.canvas.refresh()
            self.timeline.rebuild()
        if hasattr(self, '_gallery'):self._gallery.apply_theme()
        if hasattr(self, '_palette'):self._palette._refresh_styles()
        if hasattr(self, '_size_sel'):self._size_sel.set_size(self._size_sel.size())

    def closeEvent(self, event):
        # File > Exit closes the host dialog, preserving the host's discard check.
        event.ignore()
        host=self.parent()
        while host is not None:
            if hasattr(host, 'reject'):
                host.reject();break
            host=host.parent()


class VpePixelPanel(QWidget):
    received=Signal(object,str,int,bool)
    send_requested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.editor=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        row=QHBoxLayout()
        send=QPushButton('Đưa canvas / timeline sang VPE Pixel')
        send.clicked.connect(self.send_requested.emit);row.addWidget(send)
        receive=QPushButton('Nhận ảnh / animation vào Assets')
        receive.clicked.connect(self.receive_document);row.addWidget(receive)
        self.white_alpha=QCheckBox('Trắng → trong suốt')
        self.white_alpha.setToolTip('VPE565 không có alpha. Chỉ bật nếu trắng là nền cần xóa.')
        row.addWidget(self.white_alpha);row.addStretch();layout.addLayout(row)
        note=QLabel('Chung thư viện Documents/VPE Pixel • .vpe / .vpea • VPE dùng RGB565; vùng alpha chuyển thành trắng khi gửi.')
        note.setWordWrap(True);layout.addWidget(note)
        self.body=QVBoxLayout();layout.addLayout(self.body,1)

    def ensure_editor(self):
        if self.editor is None:
            self.editor=EmbeddedPixelWindow()
            self.editor._fade.stop()
            self.editor.setWindowOpacity(1)
            self.editor.setWindowFlags(Qt.WindowType.Widget)
            self.editor.setMinimumSize(640,440)
            self.body.addWidget(self.editor)
            for action in self.editor.findChildren(QAction):
                action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        return self.editor

    def open_native(self,path):
        editor=self.ensure_editor()
        if not editor._confirm_discard():return False
        path=Path(path).resolve()
        doc=editor._load_doc(str(path))
        editor._set_doc(doc,str(path));editor._show_editor()
        return True

    def set_images(self,images,name,delay_ms=100,loop=True):
        editor=self.ensure_editor()
        if not editor._confirm_discard():return False
        if not images or len(images)>256:raise ValueError('VPE hỗ trợ 1–256 frame.')
        width,height=images[0].width(),images[0].height()
        if not (1<=width<=640 and 1<=height<=640):raise ValueError('VPE hỗ trợ tối đa 640×640.')
        if any((im.width(),im.height())!=(width,height) for im in images):
            raise ValueError('Các frame cần cùng kích thước trước khi chuyển sang VPE.')
        frames=[]
        for image in images:
            pixels=[]
            for y in range(height):
                for x in range(width):
                    c=image.pixelColor(x,y);alpha=c.alpha()
                    channels=[(v*alpha+255*(255-alpha)+127)//255 for v in (c.red(),c.green(),c.blue())]
                    pixels.append(rgb_to_565(*channels))
            frames.append(pixels)
        doc=Document.from_frames(width,height,frames,name,delay_ms=delay_ms,loop=loop)
        doc.dirty=True;editor._set_doc(doc,None);editor._show_editor()
        return True

    def receive_document(self):
        editor=self.ensure_editor();editor.timeline.stop();doc=editor._doc
        images=[]
        for pixels in doc.frames:
            image=QImage(doc.width,doc.height,QImage.Format.Format_ARGB32)
            for i,pixel in enumerate(pixels):
                color=QColor(*c565_to_rgb(pixel))
                if self.white_alpha.isChecked() and pixel==65535:color.setAlpha(0)
                image.setPixelColor(i%doc.width,i//doc.width,color)
            images.append(image)
        self.received.emit(images,doc.name,doc.delay_ms,doc.loop)
        # Contents are now held by the host's undo/save pipeline.
        doc.dirty=False

    def can_close(self):
        return self.editor is None or self.editor._confirm_discard()

    def stop(self):
        if self.editor is not None:self.editor.timeline.stop();self.editor._fade.stop()
