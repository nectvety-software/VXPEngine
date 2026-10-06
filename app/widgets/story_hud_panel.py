"""Story HUD authoring for the project Asset Editor."""
from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QComboBox
from story_hud import load, save, preview

class StoryHudPanel(QWidget):
    saved = Signal(str)
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.root=root
        layout=QHBoxLayout(self); controls=QVBoxLayout(); form=QFormLayout()
        controls.addWidget(QLabel("Story HUD / Coremre"))
        note=QLabel("Title, location, progress and keypad. Save exports JSON + C header.\nInclude src/story_hud_generated.h and call vxpe_story_hud_draw.\nEmberChronicleDemo uses this configuration directly after Build.")
        note.setWordWrap(True); controls.addWidget(note)
        self.fields={}; self.last_data={}
        self.size=QComboBox(); self.size.addItems(["240x320","320x240"]);form.addRow("Viewport",self.size)
        self.size.currentTextChanged.connect(self.refresh)
        for key in ("title","gold","ivory","muted","panel","border","keycap","alpha"):
            field=QLineEdit() if key=="title" else QSpinBox()
            if key=="title": field.setMaxLength(48); field.textChanged.connect(self.refresh)
            else:
                field.setRange(0,255 if key=="alpha" else 65535)
                if key!="alpha": field.setDisplayIntegerBase(16);field.setPrefix("0x")
                field.valueChanged.connect(self.refresh)
            self.fields[key]=field;form.addRow(key.title(),field)
        self.key_fields=[];self.label_fields=[]
        for i in range(6):
            row=QHBoxLayout();key=QLineEdit();label=QLineEdit()
            key.setMaxLength(4);label.setMaxLength(12);key.setMaximumWidth(70)
            key.textChanged.connect(self.refresh);label.textChanged.connect(self.refresh)
            row.addWidget(key);row.addWidget(label);form.addRow("Control "+str(i+1),row)
            self.key_fields.append(key);self.label_fields.append(label)
        controls.addLayout(form)
        button=QPushButton("Save HUD to project");button.clicked.connect(self.save_project);controls.addWidget(button)
        self.status=QLabel();self.status.setWordWrap(True);controls.addWidget(self.status);controls.addStretch()
        layout.addLayout(controls,1)
        self.image=QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.image,1)
        try: data=load(root)
        except (OSError,ValueError,TypeError) as exc:
            from story_hud import DEFAULT
            data=dict(DEFAULT);self.status.setText(str(exc))
        self.set_data(data)
    def set_data(self,data):
        self.last_data=data
        for key,field in self.fields.items():
            field.blockSignals(True)
            if key=="title":field.setText(data[key])
            else:field.setValue(data[key])
            field.blockSignals(False)
        for fields,key in ((self.key_fields,"keys"),(self.label_fields,"labels")):
            for field,value in zip(fields,data[key]):
                field.blockSignals(True);field.setText(value);field.blockSignals(False)
        self.refresh()
    def data(self):
        return {**{key:(field.text() if key=="title" else field.value()) for key,field in self.fields.items()},
                "keys":[f.text() for f in self.key_fields],"labels":[f.text() for f in self.label_fields]}
    def refresh(self,*_):
        if not hasattr(self,"image"):return
        try:
            size=tuple(map(int,self.size.currentText().split("x")))
            p=self.root/"assets/backgrounds/village.png"
            bg=None
            if p.exists():
                with Image.open(p) as source:bg=source.copy()
            im=preview(self.data(),size,bg).convert("RGB")
            q=QImage(im.tobytes(),im.width,im.height,im.width*3,QImage.Format.Format_RGB888).copy()
            self.image.setPixmap(QPixmap.fromImage(q).scaled(im.width*2,im.height*2,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
            self.status.setText("ASCII 5x7 / RGB565. Preview: title and controls; location/progress come from gameplay.")
        except (OSError,ValueError,TypeError) as exc:self.status.setText(str(exc))
    def save_project(self):
        try:
            path=save(self.root,self.data());self.last_data=self.data()
            self.status.setText("Saved. Build the project to update runtime HUD.");self.saved.emit(str(path))
        except (OSError,ValueError,TypeError) as exc:self.status.setText(str(exc))
