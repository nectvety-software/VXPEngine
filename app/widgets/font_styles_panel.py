"""Asset Editor authoring and shared pixel-font style preview."""
import copy
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont,QImage,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QSpinBox,QCheckBox,QPushButton,QLabel
from pixel_fonts import ROLES,FIELDS,FONTS,PRESETS,load,save,preset,preview
class FontStylesPanel(QWidget):
    saved=Signal(str)
    def __init__(self,root,parent=None):
        super().__init__(parent);self.root=root;self.setFont(QFont("Segoe UI",9));self.loading=False
        try:self.styles=load(root)
        except (OSError,ValueError,TypeError):self.styles=preset("Royal Gold")
        self.active="title";layout=QHBoxLayout(self);left=QVBoxLayout();form=QFormLayout()
        left.addWidget(QLabel("Pixel Font Styles / Vaelora"))
        note=QLabel("Three bitmap families, five roles. Preview uses the same glyphs as core.\nSave updates project font styles; Build applies them in Vaelora Duel.");note.setWordWrap(True);left.addWidget(note)
        self.theme=QComboBox();self.theme.addItems(PRESETS);button=QPushButton("Apply theme")
        button.clicked.connect(self.apply_theme);row=QHBoxLayout();row.addWidget(self.theme);row.addWidget(button);left.addLayout(row)
        self.role=QComboBox();self.role.addItems(ROLES);form.addRow("Role",self.role);self.role.currentTextChanged.connect(self.change_role)
        self.face=QComboBox();self.face.addItems([f["name"] for f in FONTS]);form.addRow("Font",self.face);self.face.currentIndexChanged.connect(self.changed)
        self.fields={}
        for key in ("scale","spacing","color565","shadow565","outline565","highlight565"):
            field=QSpinBox();field.setRange(1 if key=="scale" else 0,4 if key in ("scale","spacing") else 65535)
            if key.endswith('565'):field.setDisplayIntegerBase(16);field.setPrefix("0x")
            field.valueChanged.connect(self.changed);self.fields[key]=field;form.addRow(key.replace('565','').title(),field)
        self.effects=[]
        for label in ("Shadow","Outline","Bevel highlight"):
            field=QCheckBox(label);field.toggled.connect(self.changed);self.effects.append(field);form.addRow(field)
        left.addLayout(form);save_button=QPushButton("Save font styles to project");save_button.clicked.connect(self.save_project);left.addWidget(save_button)
        self.status=QLabel("Body defaults to 1x for the native 240x320 layout. Runtime glyphs support printable ASCII.");self.status.setWordWrap(True);left.addWidget(self.status);left.addStretch();layout.addLayout(left,1)
        self.image=QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.image,1);self.set_fields()
    def set_fields(self):
        self.loading=True;s=self.styles[self.active];self.face.setCurrentIndex(s["font_id"])
        for key,field in self.fields.items():field.setValue(s[key])
        for i,field in enumerate(self.effects):field.setChecked(bool(s["effects"]&(1<<i)))
        self.loading=False;self.refresh()
    def changed(self,*_):
        if self.loading or not hasattr(self,"image"):return
        self.styles[self.active]={"font_id":self.face.currentIndex(),"effects":sum(1<<i for i,f in enumerate(self.effects) if f.isChecked()),**{key:f.value() for key,f in self.fields.items()}}
        self.refresh()
    def change_role(self,value):self.active=value;self.set_fields()
    def apply_theme(self):self.styles=preset(self.theme.currentText());self.set_fields()
    def refresh(self):
        im=preview(self.styles);q=QImage(im.tobytes(),im.width,im.height,im.width*3,QImage.Format.Format_RGB888).copy()
        self.image.setPixmap(QPixmap.fromImage(q).scaled(480,640,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
    def save_project(self):
        try:
            path=save(self.root,self.styles);self.status.setText("Saved JSON and C style header. Rebuild to apply.");self.saved.emit(str(path))
        except (OSError,ValueError,TypeError) as exc:self.status.setText(str(exc))
