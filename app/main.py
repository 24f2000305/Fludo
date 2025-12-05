from __future__ import annotations

import os
import sys
import tempfile
import json
from io import BytesIO
from pathlib import Path
from base64 import urlsafe_b64encode

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QTimer, QBuffer, QIODevice

from PIL import Image


APP_TITLE = "HASE Parametric CAD – Desktop"


class MainWindow(QtWidgets.QMainWindow):
    _last_spec: dict[str, object] | None
    _pending_spec_payload: tuple[str | None, bool] | None
    _pending_options: dict[str, object] | None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1280, 800)
        self.temp_dir = tempfile.mkdtemp(prefix="hase_app_")
        self._last_spec = None
        self._viewer_ready = False
        self._pending_spec_payload = None
        self._pending_options = None
        self._materialPreset = "luminous"
        self._backgroundPreset = "night"
        self._setup_palette()
        self._setup_ui()

    def _setup_palette(self) -> None:
        # Black & white theme
        pal = QtGui.QPalette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#0a0a0a"))
        pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#ffffff"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#111111"))
        pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#151515"))
        pal.setColor(QtGui.QPalette.Text, QtGui.QColor("#ffffff"))
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor("#111111"))
        pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#ffffff"))
        pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#ffffff"))
        pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#000000"))
        self.setPalette(pal)

    def _setup_ui(self) -> None:
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        main = QtWidgets.QHBoxLayout(cw)

        # Splitter layout for resizeable panels
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background: #222; }")

        # Left widget
        leftw = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(leftw)
        title = QtWidgets.QLabel("Parametric CAD Prompt")
        title.setStyleSheet("font-size:18px;font-weight:600; letter-spacing:0.3px;")
        left.addWidget(title)

        self.promptEdit = QtWidgets.QTextEdit()
        self.promptEdit.setPlaceholderText("Describe your model... e.g. box 20x10x5")
        self.promptEdit.setFixedHeight(120)
        left.addWidget(self.promptEdit)

        # Parameter overrides
        paramsBox = QtWidgets.QGroupBox("Parameters (optional override)")
        form = QtWidgets.QFormLayout(paramsBox)
        self.useParams = QtWidgets.QCheckBox("Use overrides below")
        self.widthSpin = QtWidgets.QDoubleSpinBox(); self.widthSpin.setRange(0.001, 1e6); self.widthSpin.setValue(20.0)
        self.depthSpin = QtWidgets.QDoubleSpinBox(); self.depthSpin.setRange(0.001, 1e6); self.depthSpin.setValue(10.0)
        self.heightSpin = QtWidgets.QDoubleSpinBox(); self.heightSpin.setRange(0.001, 1e6); self.heightSpin.setValue(5.0)
        form.addRow(self.useParams)
        form.addRow("Width", self.widthSpin)
        form.addRow("Depth", self.depthSpin)
        form.addRow("Height", self.heightSpin)
        left.addWidget(paramsBox)

        controls = QtWidgets.QHBoxLayout()
        self.generateBtn = QtWidgets.QPushButton("Generate 3D Object")
        self.generateBtn.clicked.connect(self.on_generate)
        controls.addWidget(self.generateBtn)
        clearBtn = QtWidgets.QPushButton("Clear")
        clearBtn.clicked.connect(lambda: self.promptEdit.clear())
        controls.addWidget(clearBtn)
        left.addLayout(controls)

        # Log
        self.logEdit = QtWidgets.QPlainTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.setPlaceholderText("Logs...")
        left.addWidget(self.logEdit, 1)

        # Viewer (right)
        rightw = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(rightw)
        header = QtWidgets.QHBoxLayout()
        self.spinChk = QtWidgets.QCheckBox("Auto-Spin")
        self.gridChk = QtWidgets.QCheckBox("Grid")
        self.axesChk = QtWidgets.QCheckBox("Axes")
        self.fitBtn = QtWidgets.QPushButton("Fit View")
        self.fitBtn.clicked.connect(self.on_fit_view)
        header.addWidget(self.spinChk)
        header.addWidget(self.gridChk)
        header.addWidget(self.axesChk)
        header.addStretch(1)
        header.addWidget(self.fitBtn)
        right.addLayout(header)

        combo_style = (
            "QComboBox { background:#181818; border:1px solid #303030; border-radius:16px;"
            " padding:4px 12px; color:#f2f2f2; min-width:110px; }"
            "QComboBox::drop-down { border:0px; width:18px; }"
            "QComboBox QAbstractItemView { background:#202020; color:#f2f2f2; selection-background-color:#444; }"
        )
        style_row = QtWidgets.QHBoxLayout()
        style_row.setContentsMargins(0, 10, 0, 6)
        style_row.setSpacing(12)
        look_lbl = QtWidgets.QLabel("Look")
        look_lbl.setStyleSheet("color:#9aa0ac; font-size:11px; letter-spacing:1px; text-transform:uppercase;")
        style_row.addWidget(look_lbl)
        self.materialCombo = QtWidgets.QComboBox()
        self.materialCombo.addItem("Luminous", "luminous")
        self.materialCombo.addItem("Studio", "studio")
        self.materialCombo.addItem("Wireframe", "wireframe")
        self.materialCombo.setStyleSheet(combo_style)
        self.materialCombo.currentIndexChanged.connect(self._on_material_changed)
        if hasattr(self, "_materialPreset"):
            idx = self.materialCombo.findData(self._materialPreset)
            if idx >= 0:
                block = self.materialCombo.blockSignals(True)
                self.materialCombo.setCurrentIndex(idx)
                self.materialCombo.blockSignals(block)
        style_row.addWidget(self.materialCombo)
        bg_lbl = QtWidgets.QLabel("Backdrop")
        bg_lbl.setStyleSheet("color:#9aa0ac; font-size:11px; letter-spacing:1px; text-transform:uppercase;")
        style_row.addWidget(bg_lbl)
        self.backgroundCombo = QtWidgets.QComboBox()
        self.backgroundCombo.addItem("Night", "night")
        self.backgroundCombo.addItem("Neutral", "neutral")
        self.backgroundCombo.addItem("Horizon", "horizon")
        self.backgroundCombo.setStyleSheet(combo_style)
        self.backgroundCombo.currentIndexChanged.connect(self._on_background_changed)
        if hasattr(self, "_backgroundPreset"):
            idx_bg = self.backgroundCombo.findData(self._backgroundPreset)
            if idx_bg >= 0:
                block_bg = self.backgroundCombo.blockSignals(True)
                self.backgroundCombo.setCurrentIndex(idx_bg)
                self.backgroundCombo.blockSignals(block_bg)
        style_row.addWidget(self.backgroundCombo)
        style_row.addStretch(1)
        right.addLayout(style_row)

        self.web = QWebEngineView()
        # Allow local viewer to load local OBJ and remote CDN scripts
        s = self.web.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        viewer_html = Path(__file__).with_name("viewer.html").as_uri()
        self.web.setUrl(viewer_html)
        self.web.loadFinished.connect(self._on_viewer_load_finished)

        self.spinChk.toggled.connect(self._push_current_options)
        self.gridChk.toggled.connect(self._push_current_options)
        self.axesChk.toggled.connect(self._push_current_options)

        # Create a splitter so the viewer sits beside a spec / controls panel
        inner_split = QtWidgets.QSplitter()
        inner_split.setOrientation(QtCore.Qt.Horizontal)
        inner_split.setHandleWidth(2)
        inner_split.setStyleSheet("QSplitter::handle { background: #222; }")

        inner_split.addWidget(self.web)

        # Spec / controls panel
        spec_w = QtWidgets.QWidget()
        spec_l = QtWidgets.QVBoxLayout(spec_w)
        spec_label = QtWidgets.QLabel("Model Spec (JSON)")
        spec_label.setStyleSheet("font-weight:600;")
        spec_l.addWidget(spec_label)

        # Scene outline and actions
        self.outline = QtWidgets.QListWidget()
        self.outline.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.outline.itemSelectionChanged.connect(self.on_outline_selection_changed)
        spec_l.addWidget(QtWidgets.QLabel("Scene Objects"))
        spec_l.addWidget(self.outline, 1)

        outline_actions = QtWidgets.QHBoxLayout()
        self.highlightBtn = QtWidgets.QPushButton("Highlight")
        self.highlightBtn.clicked.connect(self.on_highlight_selected)
        outline_actions.addWidget(self.highlightBtn)
        self.deleteBtn = QtWidgets.QPushButton("Delete Selected")
        self.deleteBtn.clicked.connect(self.on_delete_selected)
        outline_actions.addWidget(self.deleteBtn)
        outline_actions.addStretch(1)
        spec_l.addLayout(outline_actions)

        self.specView = QtWidgets.QTextEdit()
        self.specView.setReadOnly(True)
        self.specView.setPlaceholderText("Generated spec will appear here...")
        spec_l.addWidget(self.specView)

        btn_row = QtWidgets.QHBoxLayout()
        self.editLastBtn = QtWidgets.QPushButton("Edit Last with Prompt")
        self.editLastBtn.clicked.connect(self.on_edit_last)
        btn_row.addWidget(self.editLastBtn)
        self.recordBtn = QtWidgets.QPushButton("Record GIF")
        self.recordBtn.clicked.connect(self.on_record_gif)
        btn_row.addWidget(self.recordBtn)
        spec_l.addLayout(btn_row)

        save_row = QtWidgets.QHBoxLayout()
        exportBtn = QtWidgets.QPushButton("Save Spec as JSON")
        exportBtn.clicked.connect(self.on_export_spec)
        save_row.addWidget(exportBtn)
        spec_l.addLayout(save_row)

        inner_split.addWidget(spec_w)
        inner_split.setStretchFactor(0, 7)
        inner_split.setStretchFactor(1, 4)

        right.addWidget(inner_split, 1)

        splitter.addWidget(leftw)
        splitter.addWidget(rightw)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main.addWidget(splitter)
        self._push_current_options()

    @QtCore.Slot()
    def on_generate(self) -> None:
        prompt = self.promptEdit.toPlainText().strip()
        if not prompt:
            self._log("Enter a prompt.")
            return
        # Require Gemini for AI-driven generation
        try:
            from .agent import have_gemini as _have
            if not _have():
                QtWidgets.QMessageBox.warning(self, "AI Not Connected", "Gemini is not connected. Set GEMINI_API_KEY and restart.")
                return
        except Exception:
            pass
        # Build a JSON spec using the agent (no Blender). Send to viewer to render.
        from .agent import build_spec
        existing_spec = getattr(self, "_last_spec", None)
        spec = build_spec(prompt, json.dumps(existing_spec) if existing_spec else None)
        # If user enabled overrides for box, apply to first box
        if self.useParams.isChecked():
            for obj in spec.get("objects", []):
                if obj.get("type") == "box":
                    obj.setdefault("params", {})
                    obj["params"].update({
                        "width": float(self.widthSpin.value()),
                        "depth": float(self.depthSpin.value()),
                        "height": float(self.heightSpin.value()),
                    })
                    break
        self._last_spec = spec
        # Push the spec to the embedded viewer
        self._update_viewer_spec(self._last_spec, fit=True)
        self._push_current_options()
        self._log("Spec generated.")
        # Update spec view (pretty-printed JSON)
        try:
            self.specView.setPlainText(json.dumps(self._last_spec, indent=2))
        except Exception:
            try:
                self.specView.setPlainText(str(self._last_spec))
            except Exception:
                pass
        self._refresh_outline_from_spec()

    @QtCore.Slot()
    def on_edit_last(self) -> None:
        """Apply the current prompt as an edit to the last generated spec and update the viewer."""
        prompt = self.promptEdit.toPlainText().strip()
        if not prompt:
            self._log("Enter a prompt to edit the last output.")
            return
        try:
            from .agent import have_gemini as _have
            if not _have():
                QtWidgets.QMessageBox.warning(self, "AI Not Connected", "Gemini is not connected. Set GEMINI_API_KEY and restart.")
                return
        except Exception:
            pass
        existing = getattr(self, "_last_spec", None)
        if existing is None:
            self._log("No previous spec to edit.")
            return
        from .agent import build_spec
        try:
            spec = build_spec(prompt, json.dumps(existing))
        except Exception as exc:
            self._log(f"Spec generation failed: {exc}")
            return
        self._last_spec = spec
        try:
            self.specView.setPlainText(json.dumps(self._last_spec, indent=2))
        except Exception:
            self.specView.setPlainText(str(self._last_spec))
        self._update_viewer_spec(self._last_spec, fit=True)
        self._push_current_options()
        self._log("Applied edit to last spec.")
        self._refresh_outline_from_spec()

    def on_export_spec(self) -> None:
        if not getattr(self, "_last_spec", None):
            self._log("No spec to export.")
            return
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Spec", str(Path.home() / "model_spec.json"), "JSON Files (*.json)")
        if not fname:
            return
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(self._last_spec, f, indent=2)
            self._log(f"Spec saved: {fname}")
        except Exception as exc:
            self._log(f"Failed to save spec: {exc}")

    def on_record_gif(self) -> None:
        """Capture a short rotating GIF of the viewer and save to temp dir."""
        if not getattr(self, "_last_spec", None):
            self._log("No model to record.")
            return
        # Ensure viewer is set to spinning mode for capture
        self._update_viewer_spec(self._last_spec, fit=True)
        self._queue_options(
            spin=True,
            grid=self.gridChk.isChecked(),
            axes=self.axesChk.isChecked(),
            preset=self._materialPreset,
            background=self._backgroundPreset,
        )
        self._flush_viewer_updates()
        # let the viewer settle and spin for a short moment
        self.recordBtn.setEnabled(False)
        QTimer.singleShot(600, lambda: self._capture_frames(n_frames=24, interval_ms=80))

    def _capture_frames(self, n_frames: int = 30, interval_ms: int = 100) -> None:
        frames: list[Image.Image] = []
        count = {"i": 0}

        def step():
            try:
                pix = self.web.grab()
                img = pix.toImage()
                buf = QBuffer()
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "PNG")
                data = bytes(buf.data())
                buf.close()
                pil = Image.open(BytesIO(data)).convert("RGBA")
                frames.append(pil)
            except Exception as exc:
                self._log(f"Frame capture failed: {exc}")
            count["i"] += 1
            if count["i"] < n_frames:
                QTimer.singleShot(interval_ms, step)
            else:
                # save GIF if we captured at least one frame
                try:
                    if not frames:
                        raise RuntimeError("No frames captured")
                    out = os.path.join(self.temp_dir, f"capture_{int(QtCore.QDateTime.currentMSecsSinceEpoch())}.gif")
                    frames[0].save(out, save_all=True, append_images=frames[1:], duration=interval_ms, loop=0, disposal=2)
                    self._log(f"Saved GIF: {out}")
                except Exception as exc:
                    self._log(f"Failed to save GIF: {exc}")
                finally:
                    self.recordBtn.setEnabled(True)
                    self._push_current_options()

        # start capture loop
        step()

    def on_fit_view(self) -> None:
        self.web.page().runJavaScript("window.fit && window.fit();")

    def _log(self, msg: str) -> None:
        self.logEdit.appendPlainText(msg)

    def _on_viewer_load_finished(self, ok: bool) -> None:
        if not ok:
            self._log("Viewer failed to load.")
            self._viewer_ready = False
            return
        self._viewer_ready = True
        self._flush_viewer_updates()
        self._push_current_options()

    def _push_current_options(self) -> None:
        preset = None
        background = None
        if hasattr(self, "materialCombo"):
            preset = self.materialCombo.currentData()
        if hasattr(self, "backgroundCombo"):
            background = self.backgroundCombo.currentData()
        if preset:
            self._materialPreset = str(preset)
        if background:
            self._backgroundPreset = str(background)
        self._queue_options(
            spin=self.spinChk.isChecked(),
            grid=self.gridChk.isChecked(),
            axes=self.axesChk.isChecked(),
            preset=self._materialPreset,
            background=self._backgroundPreset,
        )

    def _update_viewer_spec(self, spec: dict[str, object] | None, *, fit: bool) -> None:
        if spec is None:
            self._pending_spec_payload = (None, fit)
        else:
            try:
                payload = urlsafe_b64encode(json.dumps(spec, separators=(",", ":")).encode()).decode()
            except Exception as exc:
                self._log(f"Failed to serialize spec: {exc}")
                return
            self._pending_spec_payload = (payload, fit)
        self._flush_viewer_updates()

    def _queue_options(self, **options: object) -> None:
        opts = {k: v for k, v in options.items() if v is not None}
        if not opts:
            return
        if self._pending_options is None:
            self._pending_options = opts
        else:
            self._pending_options.update(opts)
        self._flush_viewer_updates()

    def _on_material_changed(self, index: int) -> None:
        if index < 0:
            return
        data = self.materialCombo.itemData(index)
        if not data:
            return
        self._materialPreset = str(data)
        self._queue_options(preset=self._materialPreset)

    def _on_background_changed(self, index: int) -> None:
        if index < 0:
            return
        data = self.backgroundCombo.itemData(index)
        if not data:
            return
        self._backgroundPreset = str(data)
        self._queue_options(background=self._backgroundPreset)

    def _flush_viewer_updates(self) -> None:
        if not self._viewer_ready:
            return
        if self._pending_spec_payload is not None:
            payload, fit = self._pending_spec_payload
            if payload is None:
                self._run_js("window.clearScene && window.clearScene();")
            else:
                self._run_js("window.showLoading && window.showLoading();")
                script = f"window.loadSpecFromPayload({json.dumps(payload)}, {str(fit).lower()});"
                self._run_js(script)
            self._pending_spec_payload = None
        if self._pending_options:
            script = f"window.updateOptions({json.dumps(self._pending_options)});"
            self._run_js(script)
            self._pending_options = None

    def _run_js(self, script: str) -> None:
        if not self._viewer_ready:
            return
        try:
            self.web.page().runJavaScript(script)
        except Exception as exc:
            self._log(f"Viewer script failed: {exc}")

    def _run_js_with_result(self, script: str, callback: callable | None) -> None:
        if not self._viewer_ready:
            if callback:
                callback(None)
            return
        try:
            self.web.page().runJavaScript(script, callback)
        except Exception as exc:
            self._log(f"Viewer script failed: {exc}")
            if callback:
                callback(None)

    def _refresh_outline_from_spec(self) -> None:
        self.outline.clear()
        spec = getattr(self, "_last_spec", None)
        if not spec:
            return
        for obj in spec.get("objects", []):
            item = QtWidgets.QListWidgetItem(f"{obj.get('id')} ({obj.get('type')})")
            item.setData(QtCore.Qt.UserRole, obj.get("id"))
            self.outline.addItem(item)

    @QtCore.Slot()
    def on_outline_selection_changed(self) -> None:
        items = self.outline.selectedItems()
        if not items:
            return
        obj_id = items[0].data(QtCore.Qt.UserRole)
        self._run_js(f"window.selectById && window.selectById({json.dumps(obj_id)});")

    @QtCore.Slot()
    def on_highlight_selected(self) -> None:
        self.on_outline_selection_changed()

    @QtCore.Slot()
    def on_delete_selected(self) -> None:
        items = self.outline.selectedItems()
        if not items:
            self._log("No selection to delete.")
            return
        obj_id = items[0].data(QtCore.Qt.UserRole)
        spec = getattr(self, "_last_spec", None)
        if not spec:
            return
        original_len = len(spec.get("objects", []))
        spec["objects"] = [o for o in spec.get("objects", []) if o.get("id") != obj_id]
        if len(spec.get("objects", [])) == original_len:
            self._log("Object not found in spec.")
            return
        self._last_spec = spec
        try:
            self.specView.setPlainText(json.dumps(self._last_spec, indent=2))
        except Exception:
            self.specView.setPlainText(str(self._last_spec))
        # Update viewer and outline
        self._update_viewer_spec(self._last_spec, fit=False)
        self._push_current_options()
        self._refresh_outline_from_spec()
        self._log(f"Deleted {obj_id}.")


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


