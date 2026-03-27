"""
WidgetEditorWindow v2 — The visual widget builder.
Modern Windows 11 Fluent-inspired dark UI.
"""

import copy, json, uuid, logging
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QScrollArea, QFrame,
    QPushButton, QLineEdit, QDoubleSpinBox, QSpinBox, QColorDialog,
    QComboBox, QCheckBox, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QTabWidget, QTreeWidget, QTreeWidgetItem, QSlider,
    QGroupBox, QFormLayout, QSizePolicy, QDialog, QStackedWidget,
    QGridLayout, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QAction, QBrush, QLinearGradient

from core.engine import WidgetEngine
from utils.config import AppConfig

logger = logging.getLogger("DeskFlow.Editor")

# ─── Stylesheet ───────────────────────────────────────────────────────────────

STYLE = """
* {
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
    font-size: 13px;
    color: #e4e4e8;
    selection-background-color: #3d5afe;
}
QMainWindow, QDialog {
    background: #13131a;
}
QWidget {
    background: transparent;
}
/* Sidebar panels */
#sidebar {
    background: #0e0e14;
    border-right: 1px solid #1e1e2e;
}
#rightPanel {
    background: #0e0e14;
    border-left: 1px solid #1e1e2e;
}
/* Toolbar */
QToolBar {
    background: #0e0e14;
    border-bottom: 1px solid #1e1e2e;
    spacing: 2px;
    padding: 6px 8px;
}
QToolBar::separator {
    background: #1e1e2e;
    width: 1px;
    margin: 4px 4px;
}
/* Toolbar buttons */
QToolBar QToolButton {
    background: transparent;
    color: #a0a0b0;
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background: #1e1e2e;
    color: #e4e4e8;
}
QToolBar QToolButton:checked {
    background: #3d5afe30;
    color: #82b1ff;
}
/* Status bar */
QStatusBar {
    background: #0a0a10;
    color: #666;
    border-top: 1px solid #1e1e2e;
    font-size: 11px;
    padding: 0 8px;
}
/* Buttons */
QPushButton {
    background: #1e1e2e;
    color: #e4e4e8;
    border: 1px solid #2e2e40;
    padding: 7px 16px;
    border-radius: 7px;
    font-size: 12px;
}
QPushButton:hover {
    background: #252535;
    border-color: #3d5afe;
}
QPushButton:pressed {
    background: #161622;
}
QPushButton[class="primary"] {
    background: #3d5afe;
    border-color: #3d5afe;
    color: #ffffff;
    font-weight: 600;
}
QPushButton[class="primary"]:hover {
    background: #536dfe;
    border-color: #536dfe;
}
QPushButton[class="danger"] {
    background: #c62828;
    border-color: #c62828;
    color: #ffffff;
}
QPushButton[class="danger"]:hover {
    background: #d32f2f;
}
/* Inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background: #0a0a12;
    border: 1px solid #2a2a3c;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e4e4e8;
    selection-background-color: #3d5afe;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3d5afe;
    background: #0d0d18;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #13131f;
    border: 1px solid #2a2a3c;
    selection-background-color: #3d5afe40;
}
/* Tabs */
QTabWidget::pane {
    border: 1px solid #1e1e2e;
    border-top: none;
    background: #0e0e14;
}
QTabBar::tab {
    background: #0a0a10;
    color: #666;
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #0e0e14;
    color: #82b1ff;
    border-bottom: 2px solid #3d5afe;
}
QTabBar::tab:hover:!selected {
    color: #aaa;
    background: #0d0d18;
}
/* Lists */
QListWidget {
    background: #0a0a12;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 5px;
    margin: 1px 3px;
}
QListWidget::item:hover {
    background: #1a1a28;
}
QListWidget::item:selected {
    background: #3d5afe25;
    color: #82b1ff;
}
/* Group boxes */
QGroupBox {
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #555;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QGroupBox::title {
    top: -8px; left: 10px;
    background: #0e0e14;
    padding: 0 4px;
}
/* Scroll bars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #2a2a40;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #3a3a58; }
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #2a2a40;
    border-radius: 3px;
}
QScrollBar::add-line, QScrollBar::sub-line { background: none; border: none; }
QScrollBar::corner { background: transparent; }
/* Splitter */
QSplitter::handle {
    background: #1e1e2e;
}
/* Sliders */
QSlider::groove:horizontal {
    background: #1e1e2e;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #3d5afe;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}
QSlider::handle:horizontal:hover {
    background: #536dfe;
}
QSlider::sub-page:horizontal {
    background: #3d5afe;
    border-radius: 2px;
}
/* Section labels */
#sectionLabel {
    color: #444;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 4px 0 2px 0;
}
/* Template cards */
#templateCard {
    background: #0f0f1c;
    border: 1px solid #1e1e2e;
    border-radius: 10px;
    padding: 0px;
}
#templateCard:hover {
    border-color: #3d5afe;
    background: #121222;
}
"""

# ─── Color Button ─────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 28)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)
        self.setToolTip("Click to choose color")

    def set_color(self, c): self._color = c; self._refresh()
    def get_color(self):    return self._color

    def _refresh(self):
        self.setStyleSheet(
            f"background:{self._color};border:1px solid #333;border-radius:5px;")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Choose Color",
                                   QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self._color = c.name(QColor.HexArgb)
            self._refresh()
            self.color_changed.emit(self._color)


# ─── Template Card ────────────────────────────────────────────────────────────

class TemplateCard(QWidget):
    clicked = Signal(str)   # template key

    def __init__(self, key: str, name: str, desc: str, icon: str, parent=None):
        super().__init__(parent)
        self.key    = key
        self.setObjectName("templateCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(68)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size:22px; background:#1a1a2e; border-radius:8px;")
        lay.addWidget(icon_lbl)

        text_lay = QVBoxLayout()
        text_lay.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-weight:600; font-size:13px;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color:#555; font-size:11px;")
        text_lay.addWidget(name_lbl)
        text_lay.addWidget(desc_lbl)
        lay.addLayout(text_lay)
        lay.addStretch()

        add_btn = QPushButton("Add")
        add_btn.setFixedSize(52, 26)
        add_btn.setProperty("class", "primary")
        add_btn.setStyleSheet("QPushButton{background:#3d5afe;color:#fff;border:none;border-radius:5px;font-size:11px;padding:0;}QPushButton:hover{background:#536dfe;}")
        add_btn.clicked.connect(lambda: self.clicked.emit(self.key))
        lay.addWidget(add_btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.key)


# ─── Preview Canvas ───────────────────────────────────────────────────────────

class PreviewCanvas(QWidget):
    element_selected = Signal(dict)
    element_moved    = Signal(str, int, int)
    widget_resized   = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wdef    = None
        self._renderer = None
        self._sel_el  = None
        self._drag_el = None
        self._drag_off = QPoint()
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._timer = QTimer(); self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick); self._timer.start()

    def load(self, wdef: dict):
        import copy
        self._wdef = copy.deepcopy(wdef)
        from core.renderer import WidgetRenderer
        self._renderer = WidgetRenderer(self._wdef)
        self._sel_el   = None
        self.update()

    def clear(self):
        self._wdef = None; self._renderer = None; self.update()

    def _tick(self):
        if self._renderer:
            self._renderer.refresh_data(); self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Checkerboard background
        cs = 16
        for row in range(0, self.height(), cs):
            for col in range(0, self.width(), cs):
                clr = "#0c0c18" if (row//cs + col//cs)%2==0 else "#0f0f1e"
                p.fillRect(col, row, cs, cs, QColor(clr))
        if not self._wdef or not self._renderer:
            p.setPen(QColor("#333")); p.setFont(QFont("Segoe UI",11))
            p.drawText(self.rect(), Qt.AlignCenter, "Select or create a widget\nto preview it here")
            p.end(); return
        w = self._wdef.get("size",{}).get("width",250)
        h = self._wdef.get("size",{}).get("height",200)
        ox = (self.width()-w)//2; oy = (self.height()-h)//2
        p.save(); p.translate(ox, oy)
        # Drop shadow
        from PySide6.QtGui import QRadialGradient
        shadow = QPainterPath(); shadow.addRoundedRect(QRectF(8,8,w,h),12,12)
        p.fillPath(shadow, QColor(0,0,0,90))
        self._renderer.paint_to_painter(p, w, h)
        # Selection overlay
        if self._sel_el:
            el  = self._sel_el
            sr  = QRectF(el.get("x",0), el.get("y",0), el.get("width",40), el.get("height",20))
            pen = QPen(QColor("#3d5afe"), 1.5, Qt.DashLine)
            p.setPen(pen); p.setBrush(QColor(61,90,254,20))
            p.drawRect(sr)
            # Resize handle
            p.setBrush(QColor("#3d5afe")); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(sr.right()-4, sr.bottom()-4, 8, 8))
        p.restore(); p.end()

    def _widget_offset(self):
        if not self._wdef: return 0,0
        w = self._wdef.get("size",{}).get("width",250)
        h = self._wdef.get("size",{}).get("height",200)
        return (self.width()-w)//2, (self.height()-h)//2

    def mousePressEvent(self, e):
        if not self._wdef: return
        ox, oy = self._widget_offset()
        lx, ly = e.pos().x()-ox, e.pos().y()-oy
        for el in reversed(self._wdef.get("elements",[])):
            from PySide6.QtCore import QRectF
            r = QRectF(el.get("x",0), el.get("y",0), el.get("width",40), el.get("height",20))
            if r.contains(lx, ly):
                self._sel_el  = el; self._drag_el = el
                self._drag_off = QPoint(int(lx-r.x()), int(ly-r.y()))
                self.element_selected.emit(el); self.update(); return
        self._sel_el = None; self._drag_el = None; self.update()

    def mouseMoveEvent(self, e):
        if not self._drag_el: return
        ox, oy = self._widget_offset()
        nx = e.pos().x()-ox-self._drag_off.x()
        ny = e.pos().y()-oy-self._drag_off.y()
        self._drag_el["x"] = max(0, int(nx))
        self._drag_el["y"] = max(0, int(ny))
        self.element_moved.emit(self._drag_el.get("id",""), self._drag_el["x"], self._drag_el["y"])
        self.update()

    def mouseReleaseEvent(self, e): self._drag_el = None


# ─── Properties Panel ─────────────────────────────────────────────────────────

class PropertiesPanel(QWidget):
    definition_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self._wdef   = None
        self._active = None
        self._bld    = False
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        # Widget tab
        self._w_scroll = QScrollArea(); self._w_scroll.setWidgetResizable(True)
        self._w_inner  = QWidget()
        self._w_form   = QFormLayout(self._w_inner); self._w_form.setContentsMargins(12,12,12,12); self._w_form.setSpacing(8)
        self._w_scroll.setWidget(self._w_inner)
        self.tabs.addTab(self._w_scroll, "Widget")
        # Element tab
        self._el_scroll = QScrollArea(); self._el_scroll.setWidgetResizable(True)
        self._el_inner  = QWidget()
        self._el_form   = QFormLayout(self._el_inner); self._el_form.setContentsMargins(12,12,12,12); self._el_form.setSpacing(8)
        self._el_scroll.setWidget(self._el_inner)
        self.tabs.addTab(self._el_scroll, "Element")

    def load_widget(self, wdef): self._wdef = wdef; self._build_widget_tab()
    def load_element(self, el):  self._active = el; self._build_element_tab(); self.tabs.setCurrentIndex(1)

    def _clr(self, f): self._clear_form(f)
    def _clear_form(self, form):
        while form.rowCount(): form.removeRow(0)

    def _row(self, form, label, widget):
        lbl = QLabel(label); lbl.setStyleSheet("color:#666;font-size:11px;")
        form.addRow(lbl, widget)

    def _build_widget_tab(self):
        self._clr(self._w_form)
        if not self._wdef: return
        self._bld = True
        wd = self._wdef

        def sf(k, v): 
            if not self._bld and self._wdef: self._wdef[k]=v; self.definition_changed.emit(self._wdef)
        def sn(g,k,v):
            if not self._bld and self._wdef: self._wdef.setdefault(g,{})[k]=v; self.definition_changed.emit(self._wdef)
        def ss(k,v):
            if not self._bld and self._wdef: self._wdef.setdefault("style",{})[k]=v; self.definition_changed.emit(self._wdef)

        # Name
        ne = QLineEdit(wd.get("name","Widget"))
        ne.textChanged.connect(lambda v: sf("name",v))
        self._row(self._w_form, "Name", ne)

        # Layer / Z-order
        layer = QComboBox()
        layer.addItems(["always_on_top", "normal", "desktop"])
        layer.setCurrentText(wd.get("layer","always_on_top"))
        layer.setToolTip("always_on_top = floats above all apps\nnormal = normal window order\ndesktop = sits on desktop, never interferes with apps")
        layer.currentTextChanged.connect(lambda v: sf("layer",v))
        self._row(self._w_form, "Layer", layer)

        # Size
        size = wd.get("size",{"width":250,"height":200})
        ws = QSpinBox(); ws.setRange(50,3000); ws.setValue(size.get("width",250))
        hs = QSpinBox(); hs.setRange(50,3000); hs.setValue(size.get("height",200))
        ws.valueChanged.connect(lambda v: sn("size","width",v))
        hs.valueChanged.connect(lambda v: sn("size","height",v))
        sr = QWidget(); srl = QHBoxLayout(sr); srl.setContentsMargins(0,0,0,0)
        srl.addWidget(ws); srl.addWidget(QLabel("×")); srl.addWidget(hs)
        self._row(self._w_form, "Size (px)", sr)

        # Update interval
        iv = QSpinBox(); iv.setRange(100,60000); iv.setSuffix(" ms"); iv.setValue(wd.get("update_interval",1000))
        iv.valueChanged.connect(lambda v: sf("update_interval",v))
        self._row(self._w_form, "Update Rate", iv)

        # Opacity
        op = QSlider(Qt.Horizontal); op.setRange(10,100); op.setValue(int(wd.get("opacity",1.0)*100))
        op.valueChanged.connect(lambda v: sf("opacity",v/100))
        self._row(self._w_form, "Opacity", op)

        # Background type
        bg_t = QComboBox(); bg_t.addItems(["solid","gradient","radial","glass","transparent"])
        st = wd.get("style",{})
        bg_t.setCurrentText(st.get("background_type","solid"))
        bg_t.currentTextChanged.connect(lambda v: ss("background_type",v))
        self._row(self._w_form, "Background", bg_t)

        # BG Color
        bgc = ColorButton(st.get("background_color","#0f0f1e"))
        bgc.color_changed.connect(lambda v: ss("background_color",v))
        self._row(self._w_form, "BG Color", bgc)

        # Gradient start/end
        gs = ColorButton(st.get("gradient_start","#1a1a2e"))
        gs.color_changed.connect(lambda v: ss("gradient_start",v))
        ge = ColorButton(st.get("gradient_end","#0a0a1a"))
        ge.color_changed.connect(lambda v: ss("gradient_end",v))
        gw = QWidget(); gl = QHBoxLayout(gw); gl.setContentsMargins(0,0,0,0)
        gl.addWidget(gs); gl.addWidget(QLabel("→")); gl.addWidget(ge)
        self._row(self._w_form, "Gradient", gw)

        # Corner radius
        cr = QSlider(Qt.Horizontal); cr.setRange(0,40); cr.setValue(st.get("border_radius",12))
        cr.valueChanged.connect(lambda v: ss("border_radius",v))
        self._row(self._w_form, "Corner Radius", cr)

        # Border
        bw_s = QDoubleSpinBox(); bw_s.setRange(0,8); bw_s.setSingleStep(0.5); bw_s.setValue(st.get("border_width",0))
        bw_s.valueChanged.connect(lambda v: ss("border_width",v))
        self._row(self._w_form, "Border Width", bw_s)

        bc = ColorButton(st.get("border_color","#ffffff18"))
        bc.color_changed.connect(lambda v: ss("border_color",v))
        self._row(self._w_form, "Border Color", bc)

        self._bld = False

    def _build_element_tab(self):
        self._clr(self._el_form)
        el = self._active
        if not el: return
        self._bld = True

        def se(k, v):
            if not self._bld and self._active:
                self._active[k] = v
                if self._wdef: self.definition_changed.emit(self._wdef)

        etype = el.get("type","text")
        self._el_form.addRow(QLabel(f"<b style='color:#82b1ff'>{etype.replace('_',' ').title()}</b>"))

        # Position
        xv = QSpinBox(); xv.setRange(-1000,5000); xv.setValue(el.get("x",0)); xv.valueChanged.connect(lambda v: se("x",v))
        yv = QSpinBox(); yv.setRange(-1000,5000); yv.setValue(el.get("y",0)); yv.valueChanged.connect(lambda v: se("y",v))
        pr = QWidget(); prl = QHBoxLayout(pr); prl.setContentsMargins(0,0,0,0)
        prl.addWidget(QLabel("X")); prl.addWidget(xv); prl.addWidget(QLabel("Y")); prl.addWidget(yv)
        self._row(self._el_form, "Position", pr)

        # Size
        wv = QSpinBox(); wv.setRange(5,3000); wv.setValue(el.get("width",180)); wv.valueChanged.connect(lambda v: se("width",v))
        hv = QSpinBox(); hv.setRange(5,3000); hv.setValue(el.get("height",30));  hv.valueChanged.connect(lambda v: se("height",v))
        szr = QWidget(); szrl = QHBoxLayout(szr); szrl.setContentsMargins(0,0,0,0)
        szrl.addWidget(wv); szrl.addWidget(QLabel("×")); szrl.addWidget(hv)
        self._row(self._el_form, "Size", szr)

        # Opacity
        op = QSlider(Qt.Horizontal); op.setRange(0,100); op.setValue(int(el.get("opacity",1.0)*100))
        op.valueChanged.connect(lambda v: se("opacity",v/100))
        self._row(self._el_form, "Opacity", op)

        # Text / format
        if etype in ("text","clock","date","label_value"):
            key = "format" if etype in ("clock","date") else "text" if etype=="text" else "label"
            te = QLineEdit(el.get(key,""))
            te.textChanged.connect(lambda v,k=key: se(k,v))
            self._row(self._el_form, key.title(), te)

        if etype == "todo_list":
            items_raw = "\n".join(i.get("text","") for i in el.get("items",[]))
            te = QTextEdit(items_raw); te.setFixedHeight(80)
            def _save_todo():
                lines = te.toPlainText().split("\n")
                el["items"] = [{"text":l.strip(),"done":False} for l in lines if l.strip()]
                if self._wdef: self.definition_changed.emit(self._wdef)
            te.textChanged.connect(_save_todo)
            self._row(self._el_form, "Items (one per line)", te)

        # Color
        if etype not in ("divider","image","bar_graph","line_graph"):
            cc = ColorButton(el.get("color","#e0e0e0"))
            cc.color_changed.connect(lambda v: se("color",v))
            self._row(self._el_form, "Text Color", cc)

        # Font size / weight / family / alignment (text elements)
        TEXT_ETYPES = ("text","clock","date","system_stat","label_value","world_clock",
                       "stock","crypto","forex","news","countdown","notification_bar","shortcut_btn",
                       "notes","script_btn")
        if etype in TEXT_ETYPES:
            # Font family picker
            ff = QComboBox()
            ff.addItems(["Segoe UI","Roboto","Inter","Arial","Consolas","Courier New",
                         "Georgia","Trebuchet MS","Verdana","Tahoma","Calibri"])
            ff.setCurrentText(el.get("font_family","Segoe UI"))
            ff.currentTextChanged.connect(lambda v: se("font_family",v))
            self._row(self._el_form, "Font Family", ff)
            # Size
            fs = QSpinBox(); fs.setRange(6,120); fs.setValue(el.get("font_size",13))
            fs.valueChanged.connect(lambda v: se("font_size",v))
            self._row(self._el_form, "Font Size", fs)
            # Weight
            fw = QComboBox(); fw.addItems(["thin","light","normal","medium","bold","black"])
            fw.setCurrentText(el.get("font_weight","normal"))
            fw.currentTextChanged.connect(lambda v: se("font_weight",v))
            self._row(self._el_form, "Font Weight", fw)
            # Alignment
            al = QComboBox(); al.addItems(["left","center","right"])
            al.setCurrentText(el.get("align","left"))
            al.currentTextChanged.connect(lambda v: se("align",v))
            self._row(self._el_form, "Alignment", al)
            # 12h / seconds toggles for clock/date
            if etype in ("clock","date"):
                h12 = QCheckBox("12-hour format")
                h12.setChecked(el.get("use_12h", False)
                               or el.get("time_format", "24h") == "12h")
                h12.toggled.connect(lambda v: (se("use_12h", v),
                                               se("time_format", "12h" if v else "24h")))
                self._el_form.addRow(h12)

                if etype == "clock":
                    secs_chk = QCheckBox("Show seconds")
                    secs_chk.setChecked(el.get("show_seconds", False))
                    secs_chk.toggled.connect(lambda v: se("show_seconds", v))
                    self._el_form.addRow(secs_chk)

                    sec_clr = ColorButton(el.get("sec_color", "#445588"))
                    sec_clr.color_changed.connect(lambda v: se("sec_color", v))
                    self._row(self._el_form, "Seconds Color", sec_clr)

        # Progress / ring
        if etype in ("progress","ring"):
            fc = ColorButton(el.get("fill_color","#3d5afe"))
            fc.color_changed.connect(lambda v: se("fill_color",v))
            self._row(self._el_form, "Fill Color", fc)
            tc = ColorButton(el.get("track_color","#ffffff15"))
            tc.color_changed.connect(lambda v: se("track_color",v))
            self._row(self._el_form, "Track Color", tc)
            if etype == "ring":
                th = QSpinBox(); th.setRange(2,30); th.setValue(el.get("thickness",8))
                th.valueChanged.connect(lambda v: se("thickness",v))
                self._row(self._el_form, "Thickness", th)
            sl = QCheckBox("Show label")
            sl.setChecked(el.get("show_label", etype=="ring"))
            sl.toggled.connect(lambda v: se("show_label",v))
            self._el_form.addRow(sl)

        # Graph colors
        if etype in ("bar_graph","line_graph","sparkline"):
            fc = ColorButton(el.get("fill_color","#3d5afe"))
            fc.color_changed.connect(lambda v: se("fill_color",v))
            self._row(self._el_form, "Fill/Line Color", fc)

        # Data provider info
        dp = el.get("data_provider")
        if dp:
            lbl = QLabel(f"📡  {dp}")
            lbl.setStyleSheet("color:#3d8afe;font-size:11px;")
            self._el_form.addRow(lbl)
            ref = QPushButton("🔄 Force Refresh")
            ref.setFixedHeight(26)
            def _force():
                from core.data_providers import DataProviderRegistry
                DataProviderRegistry.force_refresh(dp, el.get("provider_args",{}))
            ref.clicked.connect(_force)
            self._el_form.addRow(ref)

        self._bld = False


# ─── Element Palette ──────────────────────────────────────────────────────────

PALETTE = [
    ("text",         "📝 Text",          "Static or dynamic text"),
    ("clock",        "🕐 Digital Clock",  "Current time"),
    ("analog_clock", "🕰 Analog Clock",   "Classic clock face"),
    ("date",         "📅 Date",           "Day / month / year"),
    ("progress",     "▬ Progress Bar",   "Horizontal fill bar"),
    ("ring",         "◎ Ring",           "Circular gauge"),
    ("bar_graph",    "📊 Bar Graph",      "Historical bars"),
    ("line_graph",   "📈 Line Graph",     "Smooth history line"),
    ("sparkline",    "⚡ Sparkline",      "Compact value + line"),
    ("system_stat",  "💻 Stat Text",      "CPU/RAM/etc as text"),
    ("weather",      "⛅ Weather",        "Temp + conditions"),
    ("weather_forecast", "🌤 Forecast",  "Multi-slot forecast"),
    ("stock",        "📉 Stock Ticker",   "Live stock price"),
    ("crypto",       "₿ Crypto Price",   "Bitcoin/Eth etc."),
    ("forex",        "💱 Forex",         "Currency pair"),
    ("news",         "📰 News Feed",      "RSS headlines"),
    ("world_clock",  "🌍 World Clock",    "Multiple time zones"),
    ("battery",      "🔋 Battery",        "Battery level bar"),
    ("network",      "📶 Network Speed",  "Upload + download"),
    ("calendar_mini","📆 Mini Calendar",  "Month calendar"),
    ("todo_list",    "✅ To-Do",          "Checklist"),
    ("divider",      "─ Divider",        "Separator line"),
    ("image",        "🖼 Image",         "Custom image/logo"),
    ("icon",             "● Icon",           "Emoji / glyph"),
    ("label_value",      "🏷 Label+Value",   "Key / value pair"),
    ("media_now_playing","🎵 Media Player",  "Inline now playing"),
    ("shortcut_btn",     "⚡ Shortcut",      "App launcher button"),
    ("countdown",        "⏳ Countdown",     "Days to target date"),
    ("notification_bar", "🔔 Notification",  "Status / info bar"),
    ("notes",            "📓 Notes",         "Sticky-note text block"),
    ("pomodoro",         "🍅 Pomodoro",       "25/5 focus timer"),
    ("script_btn",       "⌘ Script Button",  "Run command / script"),
]


class ElementPalette(QWidget):
    element_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(2)
        self._list = QListWidget()
        for key, name, tip in PALETTE:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, key)
            item.setToolTip(tip)
            self._list.addItem(item)
        lay.addWidget(self._list)
        hint = QLabel("Double-click to add to widget")
        hint.setStyleSheet("color:#444;font-size:10px;padding:4px 8px;")
        lay.addWidget(hint)
        self._list.itemDoubleClicked.connect(lambda i: self.element_requested.emit(i.data(Qt.UserRole)))


# ─── Templates ────────────────────────────────────────────────────────────────

TEMPLATES_META = [
    ("clock",               "🕐 Digital Clock",      "24h time + date",                "clock"),
    ("clock_12h",           "🕐 Clock 12h",          "12-hour AM/PM format",           "clock"),
    ("clock_with_seconds",  "🕐 Clock + Seconds",    "24h with live seconds counter",  "clock"),
    ("clock_12h_seconds",   "🕐 12h + Seconds",      "12h with amber seconds",         "clock"),
    ("minimal_clock",       "🌑 Minimal",            "Transparent clock",              "clock"),
    ("analog_clock",        "🕰 Analog Clock",       "Classic smooth clock face",      "clock"),
    ("world_clock",         "🌍 World Clock",        "3 simultaneous time zones",      "clock"),
    ("weather",           "⛅ Weather",          "Live temp + conditions",             "weather"),
    ("weather_full",      "🌤 Weather Full",     "Forecast strip + details",           "weather"),
    ("system_basic",      "💻 System Basic",     "CPU/RAM/Disk bars",                  "monitor"),
    ("system_full",       "🖥 System Full",      "Full system panel + GPU",            "monitor"),
    ("neon_stats",        "🌈 Neon Stats",       "Ring gauges + sparkline",            "monitor"),
    ("finance_stocks",    "📈 Stocks",           "Live multi-stock ticker",            "finance"),
    ("finance_crypto",    "₿ Crypto",           "Bitcoin + Ethereum",                 "finance"),
    ("finance_forex",     "💱 Forex",            "5 currency pairs",                   "finance"),
    ("news_feed",         "📰 News Feed",        "BBC RSS headlines",                  "news"),
    ("media_now_playing", "🎵 Media Player",     "Now playing — any app",             "media"),
    ("media_compact",     "🎵 Media Compact",    "Slim bar — title + controls",        "media"),
    ("spotify_now_playing","♫ Spotify",         "Spotify OAuth player",               "spotify"),
    ("calendar",          "📅 Calendar",         "Mini month calendar",                "calendar"),
    ("todo",              "✅ To-Do",            "Interactive checklist",              "todo"),
    ("countdown",         "⏳ Countdown",        "Days to target date",                "todo"),
    ("shortcuts_panel",   "⚡ Shortcuts",        "App launcher buttons",               "shortcuts"),
    ("notification_feed", "🔔 Notifications",    "Status bars",                        "info"),
    ("battery_net",       "🔋 Power & Net",      "Battery + network speeds",           "system"),
    ("notes",             "📓 Notes",            "Sticky-note text widget",            "productivity"),
    ("pomodoro",          "🍅 Pomodoro",          "25/5 focus timer ring",              "productivity"),
    ("cpu_graph",         "📊 CPU Graph",         "CPU history bar graph",              "monitor"),
    ("ram_graph",         "📉 RAM Graph",         "Memory usage line graph",            "monitor"),
    ("network_monitor",   "📶 Network Monitor",   "Download / upload speeds",           "system"),
]



# ─── Main Editor Window ───────────────────────────────────────────────────────

class WidgetEditorWindow(QMainWindow):

    def __init__(self, engine: WidgetEngine, config: AppConfig, parent=None):
        super().__init__(parent)
        self.engine   = engine
        self.config   = config
        self._cur_id  : Optional[str]  = None
        self._cur_def : dict           = {}
        self._undo    : list           = []
        self._redo    : list           = []

        self.setWindowTitle("DeskFlow 2026  —  Widget Studio")
        self.resize(1300, 820)
        self.setMinimumSize(1000, 640)
        self.setStyleSheet(STYLE)

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._connect()
        self._reload_widget_list()
        self._status("Ready  ·  Double-click a template to add it instantly")

    # ── Toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = self.addToolBar("Main"); tb.setMovable(False); tb.setIconSize(QSize(14,14))
        def act(label, slot, checkable=False, checked=False, tip=""):
            a = QAction(label, self); a.triggered.connect(slot)
            if checkable: a.setCheckable(True); a.setChecked(checked)
            a.setToolTip(tip); tb.addAction(a); return a
        act("💾  Save",       self._save,   tip="Save current widget  (Ctrl+S)")
        act("↩  Undo",        self._undo_,  tip="Undo  (Ctrl+Z)")
        act("↪  Redo",        self._redo_,  tip="Redo  (Ctrl+Y)")
        tb.addSeparator()
        act("📥  Import",     self._import, tip="Import widget JSON")
        act("📤  Export",     self._export, tip="Export widget JSON")
        act("📋  Duplicate",  self._duplicate, tip="Duplicate current widget")
        tb.addSeparator()
        self._live_act = act("👁  Live Preview", self._toggle_live, checkable=True, checked=True, tip="Push changes to desktop in real time")
        tb.addSeparator()
        act("🔒  Lock All",   lambda: self.engine.set_all_edit_mode(False), tip="Lock all widgets (click-through)")
        act("🔓  Unlock All", lambda: self.engine.set_all_edit_mode(True),  tip="Unlock for dragging on desktop")
        tb.addSeparator()
        act("♫  Spotify",    self._add_spotify_widget, tip="Add Spotify Now Playing widget")
        tb.addSeparator()
        act("⚙  Settings",   self._open_settings, tip="Weather, fonts, refresh rates")
        tb.addSeparator()
        act("⚙  Settings",   self._open_settings, tip="App settings, weather, fonts")

    # ── Central layout ────────────────────────────────────────────────────────

    def _build_central(self):
        root = QWidget(); self.setCentralWidget(root)
        root_lay = QHBoxLayout(root); root_lay.setContentsMargins(0,0,0,0); root_lay.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal); splitter.setHandleWidth(1)

        # LEFT SIDEBAR
        left = self._build_left()
        left.setObjectName("sidebar"); left.setFixedWidth(240)
        splitter.addWidget(left)

        # CENTER PREVIEW
        center = self._build_center()
        splitter.addWidget(center)

        # RIGHT PROPS
        self.props = PropertiesPanel()
        self.props.setFixedWidth(300)
        splitter.addWidget(self.props)

        splitter.setStretchFactor(1, 1)
        root_lay.addWidget(splitter)

    def _build_left(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(10,10,10,10); lay.setSpacing(6)

        # Widgets section
        sec1 = QLabel("MY WIDGETS"); sec1.setObjectName("sectionLabel"); lay.addWidget(sec1)
        self.widget_list = QListWidget(); self.widget_list.setMaximumHeight(160); lay.addWidget(self.widget_list)
        btns = QWidget(); bl = QHBoxLayout(btns); bl.setContentsMargins(0,0,0,0); bl.setSpacing(6)
        self.btn_new = QPushButton("＋ New"); self.btn_new.setProperty("class","primary")
        self.btn_del = QPushButton("🗑 Delete"); self.btn_del.setProperty("class","danger")
        bl.addWidget(self.btn_new); bl.addWidget(self.btn_del); lay.addWidget(btns)

        # Elements palette
        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine); sep1.setStyleSheet("color:#1e1e2e;"); lay.addWidget(sep1)
        sec2 = QLabel("ELEMENTS"); sec2.setObjectName("sectionLabel"); lay.addWidget(sec2)
        self.palette = ElementPalette(); lay.addWidget(self.palette)

        lay.addStretch()
        return w

    def _build_center(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # Top tab: Preview | Templates
        self.center_tabs = QTabWidget()
        lay.addWidget(self.center_tabs)

        # Preview tab
        prev_w = QWidget(); prev_lay = QVBoxLayout(prev_w); prev_lay.setContentsMargins(0,0,0,0)
        self.preview = PreviewCanvas(); prev_lay.addWidget(self.preview)
        self.center_tabs.addTab(prev_w, "🖼  Preview")

        # Templates tab
        tmpl_w = QWidget(); tmpl_w.setStyleSheet("background:#0e0e14;")
        tmpl_lay = QVBoxLayout(tmpl_w); tmpl_lay.setContentsMargins(16,16,16,16); tmpl_lay.setSpacing(8)
        tmpl_lbl = QLabel("Choose a Template"); tmpl_lbl.setStyleSheet("font-size:18px;font-weight:700;color:#e4e4e8;padding-bottom:4px;")
        tmpl_lay.addWidget(tmpl_lbl)
        sub_lbl = QLabel("Double-click to instantly add to your desktop"); sub_lbl.setStyleSheet("color:#555;font-size:12px;")
        tmpl_lay.addWidget(sub_lbl)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet("border:none;background:transparent;")
        cards_w = QWidget(); cards_w.setStyleSheet("background:transparent;")
        cards_lay = QVBoxLayout(cards_w); cards_lay.setSpacing(6); cards_lay.setContentsMargins(0,8,0,8)
        self._template_cards = {}
        for key, name, desc, _ in TEMPLATES_META:
            icon = name.split(" ")[0]
            card = TemplateCard(key, " ".join(name.split(" ")[1:]), desc, icon)
            card.clicked.connect(self._add_template)
            cards_lay.addWidget(card)
            self._template_cards[key] = card
        cards_lay.addStretch()
        scroll.setWidget(cards_w)
        tmpl_lay.addWidget(scroll)
        self.center_tabs.addTab(tmpl_w, "✨  Templates")

        # Settings tab
        self.center_tabs.addTab(self._build_settings_tab(), "⚙  Settings")

        return w


    def _open_settings(self):
        self.center_tabs.setCurrentIndex(2)

    def _build_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;background:#0e0e14;")
        w = QWidget()
        w.setStyleSheet("background:#0e0e14;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        def _section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet(
                "font-size:15px;font-weight:700;color:#e4e4e8;"
                "border-bottom:1px solid #1e1e2e;padding-bottom:6px;margin-top:8px;"
            )
            lay.addWidget(lbl)

        def _note(text):
            n = QLabel(text)
            n.setStyleSheet("color:#555;font-size:11px;")
            n.setWordWrap(True)
            lay.addWidget(n)

        def _row_input(label, key, default="", placeholder=""):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFixedWidth(180)
            lbl.setStyleSheet("color:#888;font-size:12px;")
            inp = QLineEdit(str(self.config.get(key, default)))
            inp.setPlaceholderText(placeholder)
            inp.editingFinished.connect(lambda: self.config.set(key, inp.text().strip()))
            rl.addWidget(lbl)
            rl.addWidget(inp)
            lay.addWidget(row)
            return inp

        def _row_spin(label, key, default, min_v, max_v, suffix=""):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFixedWidth(180)
            lbl.setStyleSheet("color:#888;font-size:12px;")
            sp = QSpinBox()
            sp.setRange(min_v, max_v)
            sp.setValue(int(self.config.get(key, default)))
            if suffix:
                sp.setSuffix(suffix)
            sp.valueChanged.connect(lambda v: self.config.set(key, v))
            rl.addWidget(lbl)
            rl.addWidget(sp)
            lay.addWidget(row)

        # Weather section
        _section("Weather Location")
        _note(
            "Uses Open-Meteo API (free, no API key required). "
            "Enter coordinates for accurate local weather."
        )
        _row_input("Latitude",  "weather_lat", "33.7167", "e.g. 33.7167")
        _row_input("Longitude", "weather_lon", "72.6889", "e.g. 72.6889")
        _row_input("City (display only)", "weather_city", "", "e.g. Islamabad")

        unit_row = QWidget()
        ur = QHBoxLayout(unit_row)
        ur.setContentsMargins(0, 0, 0, 0)
        ulbl = QLabel("Temperature unit")
        ulbl.setFixedWidth(180)
        ulbl.setStyleSheet("color:#888;font-size:12px;")
        uc = QComboBox()
        uc.addItems(["celsius", "fahrenheit"])
        uc.setCurrentText(self.config.get("weather_unit", "celsius"))
        uc.currentTextChanged.connect(lambda v: self.config.set("weather_unit", v))
        ur.addWidget(ulbl)
        ur.addWidget(uc)
        lay.addWidget(unit_row)

        def _refresh_weather():
            from core.data_providers import DataProviderRegistry
            try:
                lat = float(self.config.get("weather_lat", 33.7167))
                lon = float(self.config.get("weather_lon", 72.6889))
            except (ValueError, TypeError):
                lat, lon = 33.7167, 72.6889
            unit = self.config.get("weather_unit", "celsius")
            DataProviderRegistry.force_refresh("weather", {"lat": lat, "lon": lon, "unit": unit})
            self._status("Weather refresh queued with new location", 3000)

        rw_btn = QPushButton("Refresh Weather Now")
        rw_btn.setProperty("class", "primary")
        rw_btn.clicked.connect(_refresh_weather)
        lay.addWidget(rw_btn)

        # Refresh rates section
        _section("Refresh Intervals")
        _note("Controls how often each data source re-fetches. Increase to reduce network calls.")
        _row_spin("Weather (minutes)", "ttl_weather", 20, 5,  120, " min")
        _row_spin("News (minutes)",    "ttl_news",    20, 5,  120, " min")
        _row_spin("Stocks (seconds)",  "ttl_stocks",  60, 10, 600, " sec")
        _row_spin("Crypto (seconds)",  "ttl_crypto",  30, 10, 300, " sec")

        apply_btn = QPushButton("Apply Refresh Rates")
        apply_btn.clicked.connect(self._apply_refresh_rates)
        lay.addWidget(apply_btn)

        # News section
        _section("News Feed")
        _note("Any RSS 2.0 feed URL. Full headline + description shown.")
        _row_input(
            "RSS Feed URL", "news_feed_url",
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://..."
        )
        _row_spin("Max headlines", "news_count", 6, 1, 20)

        def _refresh_news():
            from core.data_providers import DataProviderRegistry
            url   = self.config.get("news_feed_url",
                                    "https://feeds.bbci.co.uk/news/rss.xml")
            count = int(self.config.get("news_count", 6))
            DataProviderRegistry.force_refresh("news", {"url": url, "count": count})
            self._status("News refresh queued", 3000)

        rn_btn = QPushButton("Refresh News Now")
        rn_btn.clicked.connect(_refresh_news)
        lay.addWidget(rn_btn)

        # Custom fonts section
        _section("Custom Fonts")
        fonts_dir = self.config.assets_dir / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        _note(
            "Place .ttf or .otf files in the fonts folder below. "
            "DeskFlow loads them at startup automatically. "
            "Then select the font name in any element's Font Family picker."
        )
        fd_lbl = QLabel(str(fonts_dir))
        fd_lbl.setStyleSheet("color:#3d5afe;font-size:11px;font-family:Consolas;")
        lay.addWidget(fd_lbl)

        builtin_note = QLabel(
            "Built-in fonts (always available):  "
            "Segoe UI  |  Arial  |  Calibri  |  Consolas  |  Georgia  |  Tahoma"
        )
        builtin_note.setStyleSheet("color:#444;font-size:11px;")
        builtin_note.setWordWrap(True)
        lay.addWidget(builtin_note)

        def _open_fonts_folder():
            import os
            import sys
            if sys.platform == "win32":
                os.startfile(str(fonts_dir))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(fonts_dir)])

        def _show_fonts():
            from PySide6.QtGui import QFontDatabase
            families = sorted(QFontDatabase.families())
            msg = "\n".join(f"  {f}" for f in families[:60])
            if len(families) > 60:
                msg += "\n  ...and {} more".format(len(families) - 60)
            QMessageBox.information(
                self, "Available Fonts ({} total)".format(len(families)), msg
            )

        fb_row = QWidget()
        fbr = QHBoxLayout(fb_row)
        fbr.setContentsMargins(0, 0, 0, 0)
        fbr.setSpacing(8)
        of_btn = QPushButton("Open Fonts Folder")
        of_btn.clicked.connect(_open_fonts_folder)
        sf_btn = QPushButton("List Loaded Fonts")
        sf_btn.clicked.connect(_show_fonts)
        fbr.addWidget(of_btn)
        fbr.addWidget(sf_btn)
        lay.addWidget(fb_row)

        # Diagnostics section
        _section("Diagnostics")
        import pathlib
        log_path = pathlib.Path.home() / ".config" / "DeskFlow" / "app.log"
        dl = QLabel("Log: {}".format(log_path))
        dl.setStyleSheet("color:#444;font-size:11px;font-family:Consolas;")
        lay.addWidget(dl)

        def _open_log():
            import os
            import sys
            if sys.platform == "win32" and log_path.exists():
                os.startfile(str(log_path))

        ol_btn = QPushButton("Open Log File")
        ol_btn.clicked.connect(_open_log)
        lay.addWidget(ol_btn)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    def _apply_refresh_rates(self):
        from core.data_providers import _PROVIDERS
        overrides = [
            ("weather", float(self.config.get("ttl_weather", 20)) * 60.0),
            ("news",    float(self.config.get("ttl_news",    20)) * 60.0),
            ("stock",   float(self.config.get("ttl_stocks",  60))),
            ("crypto",  float(self.config.get("ttl_crypto",  30))),
        ]
        for key, ttl in overrides:
            if key in _PROVIDERS:
                fn, _ = _PROVIDERS[key]
                _PROVIDERS[key] = (fn, ttl)
        self._status("Refresh rates updated", 3000)


    def _build_statusbar(self):
        self.setStatusBar(QStatusBar())

    def _status(self, msg: str, ms: int = 0):
        if ms: self.statusBar().showMessage(msg, ms)
        else:  self.statusBar().showMessage(msg)

    # ── Signal connections ────────────────────────────────────────────────────

    def _connect(self):
        self.widget_list.currentItemChanged.connect(self._on_widget_sel)
        self.btn_new.clicked.connect(self._new_widget)
        self.btn_del.clicked.connect(self._delete_widget)
        self.palette.element_requested.connect(self._add_element)
        self.props.definition_changed.connect(self._on_def_changed)
        self.preview.element_selected.connect(self.props.load_element)
        self.preview.element_moved.connect(self._on_el_moved)
        # Keyboard shortcuts
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo_)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo_)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._duplicate)

    # ── Widget list ───────────────────────────────────────────────────────────

    def _reload_widget_list(self):
        self.widget_list.clear()
        for inst in self.engine.get_all_widgets():
            name = inst.widget_def.get("name", inst.widget_id[:8])
            item = QListWidgetItem(f"  {name}")
            item.setData(Qt.UserRole, inst.widget_id)
            self.widget_list.addItem(item)

    def _on_widget_sel(self, cur, prev):
        if not cur: return
        wid = cur.data(Qt.UserRole)
        self._cur_id = wid
        d = self.engine.get_widget_def(wid)
        if d:
            self._cur_def = copy.deepcopy(d)
            self.preview.load(self._cur_def)
            self.props.load_widget(self._cur_def)
            self._status(f"Editing:  {d.get('name','Widget')}  ·  {d.get('size',{}).get('width',0)}×{d.get('size',{}).get('height',0)}")

    # ── New / Delete / Duplicate ──────────────────────────────────────────────

    def _new_widget(self):
        from widgets.templates.default_widgets import blank_widget
        wid = self.engine.add_widget(blank_widget())
        self._reload_widget_list()
        self._select_by_id(wid)
        self.center_tabs.setCurrentIndex(0)

    def _delete_widget(self):
        if not self._cur_id: return
        if QMessageBox.question(self,"Delete","Delete this widget?") == QMessageBox.Yes:
            self.engine.remove_widget(self._cur_id)
            self._cur_id = None; self._cur_def = {}
            self._reload_widget_list(); self.preview.clear()

    def _duplicate(self):
        if not self._cur_def: return
        nd = copy.deepcopy(self._cur_def)
        nd["name"] = nd.get("name","Widget") + " Copy"
        nd.setdefault("position",{})["x"] = nd.get("position",{}).get("x",0) + 20
        nd.setdefault("position",{})["y"] = nd.get("position",{}).get("y",0) + 20
        wid = self.engine.add_widget(nd)
        self._reload_widget_list(); self._select_by_id(wid)

    def _add_template(self, key: str):
        if key == "spotify_now_playing":
            self._add_spotify_widget()
            return
        from widgets.templates.default_widgets import get_template
        tdef = get_template(key)
        wid  = self.engine.add_widget(tdef)
        self._reload_widget_list(); self._select_by_id(wid)
        self.center_tabs.setCurrentIndex(0)
        self._status(f"Added template: {tdef.get('name','Widget')}", 3000)

    # ── Save / Import / Export ────────────────────────────────────────────────

    def _add_spotify_widget(self):
        try:
            from plugins.spotify.plugin import _show_setup_dialog, _spotify_player_def
            _show_setup_dialog()
            wdef = _spotify_player_def()
            wid  = self.engine.add_widget(wdef)
            if wid:
                self._reload_widget_list()
                self._select_by_id(wid)
                self._status("♫  Spotify widget added!", 3000)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Spotify", f"Plugin error: {e}")

    def _save(self):
        if not self._cur_id: return
        self._push_undo()
        self.engine.update_widget_def(self._cur_id, copy.deepcopy(self._cur_def))
        self._status("✓  Widget saved", 2500)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self,"Import Widget","","JSON (*.json)")
        if path:
            with open(path) as f: wdef = json.load(f)
            wid = self.engine.add_widget(wdef)
            self._reload_widget_list(); self._select_by_id(wid)

    def _export(self):
        if not self._cur_def: return
        path, _ = QFileDialog.getSaveFileName(self,"Export Widget","","JSON (*.json)")
        if path:
            with open(path,"w") as f: json.dump(self._cur_def, f, indent=2)
            self._status(f"Exported → {path}", 3000)

    def _toggle_live(self):
        pass  # handled in _on_def_changed

    def _on_def_changed(self, nd: dict):
        self._cur_def = nd
        if self._live_act.isChecked() and self._cur_id:
            self.engine.update_widget_def(self._cur_id, copy.deepcopy(nd))
        self.preview.load(nd)

    def _add_element(self, etype: str):
        if not self._cur_def: self._new_widget()
        self._push_undo()
        el = _default_element(etype)
        self._cur_def.setdefault("elements",[]).append(el)
        self.preview.load(self._cur_def)
        self.props.load_widget(self._cur_def)
        if self._live_act.isChecked() and self._cur_id:
            self.engine.update_widget_def(self._cur_id, copy.deepcopy(self._cur_def))

    def _on_el_moved(self, eid, x, y):
        for el in self._cur_def.get("elements",[]):
            if el.get("id") == eid: el["x"]=x; el["y"]=y

    # ── Undo/Redo ─────────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo.append(copy.deepcopy(self._cur_def))
        self._redo.clear()

    def _undo_(self):
        if self._undo:
            self._redo.append(copy.deepcopy(self._cur_def))
            self._cur_def = self._undo.pop()
            self.preview.load(self._cur_def); self.props.load_widget(self._cur_def)

    def _redo_(self):
        if self._redo:
            self._undo.append(copy.deepcopy(self._cur_def))
            self._cur_def = self._redo.pop()
            self.preview.load(self._cur_def); self.props.load_widget(self._cur_def)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _select_by_id(self, wid: str):
        for i in range(self.widget_list.count()):
            if self.widget_list.item(i).data(Qt.UserRole) == wid:
                self.widget_list.setCurrentRow(i); return


# ─── Default element factories ───────────────────────────────────────────────

def _uid(): return str(uuid.uuid4())[:8]

def _default_element(etype: str) -> dict:
    base = {"id": _uid(), "type": etype, "x": 10, "y": 10}
    defs = {
        "text":         {**base, "text":"Text", "width":200,"height":28,"font_size":14,"color":"#e0e0e0"},
        "clock":        {**base, "format":"%H:%M","width":220,"height":60,"font_size":46,"font_weight":"light","align":"center","color":"#ffffff"},
        "analog_clock": {**base, "width":120,"height":120},
        "date":         {**base, "format":"%A, %B %d","width":220,"height":24,"font_size":13,"align":"center","color":"#888888"},
        "progress":     {**base, "width":200,"height":10,"fill_color":"#3d5afe","track_color":"#ffffff15","radius":5,"show_label":False},
        "ring":         {**base, "width":80,"height":80,"thickness":8,"fill_color":"#3d5afe","show_value":True},
        "bar_graph":    {**base, "width":200,"height":50,"fill_color":"#3d5afe","data_provider":"cpu"},
        "line_graph":   {**base, "width":200,"height":50,"line_color":"#3d5afe","fill_color":[61,90,254,30],"data_provider":"cpu"},
        "sparkline":    {**base, "width":200,"height":36,"line_color":"#4fc3f7","unit":"%","data_provider":"cpu"},
        "system_stat":  {**base, "width":200,"height":22,"font_size":12,"color":"#e0e0e0","data_provider":"cpu","label":"CPU","unit":"%"},
        "weather":      {**base, "width":220,"height":80,"data_provider":"weather","show_details":True},
        "weather_forecast":{**base,"width":240,"height":70},
        "stock":        {**base, "width":220,"height":50,"data_provider":"stock","provider_args":{"symbol":"AAPL"}},
        "crypto":       {**base, "width":220,"height":46,"data_provider":"crypto","provider_args":{"coin":"bitcoin"}},
        "forex":        {**base, "width":220,"height":30,"data_provider":"forex","provider_args":{"base":"USD","target":"EUR"}},
        "news":         {**base, "width":260,"height":130,"data_provider":"news","provider_args":{"url":"https://feeds.bbci.co.uk/news/rss.xml","count":5}},
        "world_clock":  {**base, "width":220,"height":70,"data_provider":"world_clock","provider_args":{"zones":[{"tz":"America/New_York","label":"New York"},{"tz":"Europe/London","label":"London"},{"tz":"Asia/Karachi","label":"Karachi"}]}},
        "battery":      {**base, "width":240,"height":30,"data_provider":"battery"},
        "network":      {**base, "width":220,"height":26,"data_provider":"net_speed"},
        "divider":      {**base, "width":220,"height":1,"color":"#ffffff15","thickness":1},
        "image":        {**base, "width":100,"height":100,"path":""},
        "icon":         {**base, "width":40,"height":40,"char":"✨","font_size":24},
        "todo_list":    {**base, "width":220,"height":100,"items":[{"text":"Task 1","done":False},{"text":"Task 2","done":True}]},
        "calendar_mini":{**base, "width":200,"height":160,"today_color":"#3d5afe"},
        "label_value":  {**base, "width":220,"height":24,"label":"Label","value":"Value","font_size":13},
        "media_now_playing":{**base,"width":360,"height":130,"show_art":True,"show_controls":True,"font_size":13},
        "shortcut_btn":     {**base,"width":80,"height":50,"icon":"🌐","label":"Browser","color":"#3d5afe","font_size":10,"radius":10},
        "countdown":        {**base,"width":200,"height":110,"target_date":"2026-12-31","label":"COUNTDOWN","font_size":44,"font_weight":"thin","color":"#ffffff"},
        "notification_bar": {**base,"width":280,"height":28,"items":["Status info here"],"accent":"#3d5afe","font_size":11},
        "notes":         {**base,"width":282,"height":200,"title":"Notes","text":"Add your notes here\n\n• Idea 1\n• Idea 2","font_size":12,"color":"#e8e8cc"},
        "pomodoro":      {**base,"width":200,"height":200,"id":_uid(),"data_provider":"pomodoro","font_size":28,"color":"#ffffff"},
        "script_btn":    {**base,"width":80,"height":50,"icon":"⌘","label":"Script","color":"#22d3ee","target":"","font_size":10,"radius":10},
    }
    return defs.get(etype, {**base, "width":200, "height":30})
