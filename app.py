import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QLabel, QFrame, QFileDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineDownloadRequest
)
from PyQt6.QtCore import Qt, QUrl, QStandardPaths
from PyQt6.QtGui import QFont

INJECT_JS = r"""
(function() {
  if (window.__sf_injected) return;
  window.__sf_injected = true;

  window.allmodel = [];
  var saveimagecache2 = {};
  var objects = {};

  var saveimage_to_list = function(url, file_name) {
    if (!saveimagecache2[url]) saveimagecache2[url] = { name: file_name };
  };

  window.__doDownload = function() {
    var JSZip = window.JSZip;
    if (!JSZip) { return 'not_ready'; }
    var zip = new JSZip();
    var folder = zip.folder('model');
    objects = {};
    var idx = 0;
    window.allmodel.forEach(function(obj) {
      var mdl = { name: 'model_' + idx, obj: parseobj(obj) };
      dosavefile(mdl);
      idx++;
    });
    for (var obj in objects) folder.file(obj, objects[obj], { binary: true });
    var nameEl = document.querySelector('.model-name__label');
    var file_name = nameEl ? nameEl.textContent.trim() : 'sketchfab_model';
    folder.generateAsync({ type: 'blob' }).then(function(content) {
      var url = URL.createObjectURL(content);
      var a = document.createElement('a');
      a.href = url;
      a.download = file_name + '.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
    });
    return 'ok:' + file_name;
  };

  var parseobj = function(obj) {
    var list = [];
    obj._primitives.forEach(function(p) {
      if (p && p.indices) list.push({ mode: p.mode, indices: p.indices._elements });
    });
    var attr = obj._attributes;
    return {
      vertex: attr.Vertex._elements,
      normal: attr.Normal ? attr.Normal._elements : [],
      uv: attr.TexCoord0 ? attr.TexCoord0._elements : attr.TexCoord1 ? attr.TexCoord1._elements : [],
      primitives: list
    };
  };

  var dosavefile = function(mdl) {
    var obj = mdl.obj;
    var str = 'o ' + mdl.name + '\n';
    for (var i = 0; i < obj.vertex.length; i += 3)
      str += 'v ' + obj.vertex[i] + ' ' + obj.vertex[i+1] + ' ' + obj.vertex[i+2] + '\n';
    for (i = 0; i < obj.normal.length; i += 3)
      str += 'vn ' + obj.normal[i] + ' ' + obj.normal[i+1] + ' ' + obj.normal[i+2] + '\n';
    for (i = 0; i < obj.uv.length; i += 2)
      str += 'vt ' + obj.uv[i] + ' ' + obj.uv[i+1] + '\n';
    str += 's on\n';
    var vn = obj.normal.length !== 0, vt = obj.uv.length !== 0;
    for (i = 0; i < obj.primitives.length; ++i) {
      var prim = obj.primitives[i];
      if (prim.mode === 4 || prim.mode === 5) {
        var strip = prim.mode === 5;
        for (var j = 0; j + 2 < prim.indices.length; !strip ? j += 3 : j++) {
          str += 'f ';
          var order = (strip && j % 2 === 1) ? [0,2,1] : [0,1,2];
          for (var k = 0; k < 3; k++) {
            var fn = prim.indices[j + order[k]] + 1;
            str += fn;
            if (vn || vt) { str += '/'; if (vt) str += fn; if (vn) str += '/' + fn; }
            str += ' ';
          }
          str += '\n';
        }
      }
    }
    objects[mdl.name + '.obj'] = new Blob([str], { type: 'text/plain' });
  };

  window.attachbody = function(obj) {
    if (obj._faked !== true &&
        ((obj.stateset && obj.stateset._name) || obj._name ||
         (obj._parents && obj._parents[0] && obj._parents[0]._name))) {
      obj._faked = true;
      if (obj._name === 'composer layer' || obj._name === 'Ground - Geometry') return;
      window.allmodel.push(obj);
    }
  };

  window.drawhookcanvas = function(e, imagemodel) {
    if ((e.width === 128 && e.height === 128) ||
        (e.width === 32  && e.height === 32)  ||
        (e.width === 64  && e.height === 64)) return e;
    if (imagemodel) {
      var alpha = e.options.format, url_image = e.url, max_size = 0, obr = e;
      imagemodel.attributes.images.forEach(function(img) {
        var alpha_ok = alpha === 'A' ? img.options.format === alpha : true;
        var d = img.width; while (d % 2 === 0) d /= 2;
        if (img.size > max_size && alpha_ok && d === 1) {
          max_size = img.size; url_image = img.url; obr = img;
        }
      });
      if (!saveimagecache2[url_image])
        saveimage_to_list(url_image, imagemodel.attributes.name);
      return obr;
    }
    return e;
  };

  window.drawhookimg = function(gl, t) {
    var url = t[5].currentSrc, width = t[5].width, height = t[5].height;
    if (!saveimagecache2[url]) return;
    var data = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    var halfH = height / 2 | 0, bpr = width * 4, tmp = new Uint8Array(width * 4);
    for (var y = 0; y < halfH; y++) {
      var top = y * bpr, bot = (height - y - 1) * bpr;
      tmp.set(data.subarray(top, top + bpr));
      data.copyWithin(top, bot, bot + bpr);
      data.set(tmp, bot);
    }
    var canvas = document.createElement('canvas');
    canvas.width = width; canvas.height = height;
    var ctx = canvas.getContext('2d');
    var id = ctx.createImageData(width, height);
    id.data.set(data); ctx.putImageData(id, 0, 0);
    var re = /(?:\.([^.]+))?$/;
    var ext = re.exec(saveimagecache2[url].name)[1];
    var name = saveimagecache2[url].name + '.png';
    if (ext === 'png' || ext === 'jpg' || ext === 'jpeg')
      name = saveimagecache2[url].name.replace('.' + ext, '') + '.png';
    canvas.toBlob(function(blob) { objects[name] = blob; }, 'image/png');
  };

  function loadScript(src, cb) {
    var s = document.createElement('script');
    s.src = src; s.onload = cb;
    document.head.appendChild(s);
  }
  loadScript('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.1.5/jszip.min.js', function() {
    window.__sf_ready = true;
  });

  var func_drawGeometry    = /(this\._stateCache\.drawGeometry\(this\._graphicContext,t\))/g;
  var fund_drawArrays      = /t\.drawArrays\(t\.TRIANGLES,0,6\)/g;
  var func_renderInto1     = /A\.renderInto\(n,E,R/g;
  var func_renderInto2     = /g\.renderInto=function\(e,i,r/g;
  var func_getResourceImage= /getResourceImage:function\(e,t\){/g;

  var orig = Element.prototype.appendChild;
  Element.prototype.appendChild = function(node) {
    if (node.tagName === 'SCRIPT' && node.src &&
        (node.src.indexOf('web/dist/') >= 0 || node.src.indexOf('standaloneViewer') >= 0)) {
      var req = new XMLHttpRequest();
      req.open('GET', node.src, false);
      req.send('');
      var js = req.responseText;
      var ret;
      ret = func_renderInto1.exec(js);
      if (ret) { var i=ret.index+ret[0].length; js=js.slice(0,i)+',i'+js.slice(i); }
      ret = func_renderInto2.exec(js);
      if (ret) { var i=ret.index+ret[0].length; js=js.slice(0,i)+',image_data'+js.slice(i); }
      ret = fund_drawArrays.exec(js);
      if (ret) { var i=ret.index+ret[0].length; js=js.slice(0,i)+',window.drawhookimg(t,image_data)'+js.slice(i); }
      ret = func_getResourceImage.exec(js);
      if (ret) { var i=ret.index+ret[0].length; js=js.slice(0,i)+'e=window.drawhookcanvas(e,this._imageModel);'+js.slice(i); }
      ret = func_drawGeometry.exec(js);
      if (ret) { var i=ret.index+ret[1].length; js=js.slice(0,i)+';window.attachbody(t);'+js.slice(i); }
      var s = document.createElement('script');
      s.type = 'text/javascript'; s.text = js;
      return orig.call(this, s);
    }
    return orig.call(this, node);
  };
})();
"""

CSS = """
QMainWindow, QWidget#central { background: #0a0a0f; }
QWidget { background: #0a0a0f; color: #e0e0f0; font-family: 'Consolas', monospace; }
QLineEdit {
    background: #14141f; border: 1px solid #1c1c2e; border-radius: 7px;
    color: #e0e0f0; padding: 9px 14px; font-size: 13px; font-family: 'Consolas', monospace;
}
QLineEdit:focus { border: 1px solid #00e5ff; }
QPushButton#loadBtn {
    background: #00e5ff; border: none; border-radius: 7px; color: #000;
    font-weight: bold; font-size: 13px; padding: 9px 22px;
}
QPushButton#loadBtn:hover { background: #33ecff; }
QPushButton#loadBtn:pressed { background: #00b8cc; }
QPushButton#dlBtn {
    background: #00ff88; border: none; border-radius: 8px; color: #000;
    font-weight: bold; font-size: 14px; padding: 13px 36px; min-width: 180px;
}
QPushButton#dlBtn:hover { background: #33ffaa; }
QPushButton#dlBtn:pressed { background: #00cc6e; }
QPushButton#dlBtn:disabled { background: #1c2e1c; color: #2a5a2a; }
QFrame#topbar { background: #0f0f18; border-bottom: 1px solid #1c1c2e; }
QFrame#bottombar { background: #0f0f18; border-top: 1px solid #1c1c2e; }
QLabel#hint { color: #44445a; font-size: 11px; }
QLabel#modelLabel { color: #e0e0f0; font-size: 13px; font-weight: bold; }
QLabel#title { color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 2px; }
"""

class SketchfabPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def javaScriptConsoleMessage(self, level, message, line, source):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sketchfab Downloader")
        self.setMinimumSize(1000, 720)
        self.resize(1100, 780)
        self.setStyleSheet(CSS)
        self.model_loaded = False
        self.download_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(54)
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(10)

        title = QLabel("SKETCHFAB DL")
        title.setObjectName("title")
        tl.addWidget(title)

        sep = QLabel("//")
        sep.setStyleSheet("color: #1c1c2e; font-size: 16px;")
        tl.addWidget(sep)

        self.urlInput = QLineEdit()
        self.urlInput.setPlaceholderText("https://sketchfab.com/3d-models/...")
        self.urlInput.returnPressed.connect(self.load_model)
        tl.addWidget(self.urlInput)

        loadBtn = QPushButton("Загрузить")
        loadBtn.setObjectName("loadBtn")
        loadBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        loadBtn.clicked.connect(self.load_model)
        tl.addWidget(loadBtn)

        layout.addWidget(topbar)

        # WebView
        self.profile = QWebEngineProfile("sketchfab", self)
        self.profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Handle downloads via Python
        self.profile.downloadRequested.connect(self.handle_download)

        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

        self.page = SketchfabPage(self.profile, self)
        self.webview = QWebEngineView()
        self.webview.setPage(self.page)
        self.webview.loadFinished.connect(self.on_load_finished)
        self.webview.loadStarted.connect(self.on_load_started)
        layout.addWidget(self.webview, 1)

        # Bottom bar
        bottombar = QFrame()
        bottombar.setObjectName("bottombar")
        bottombar.setFixedHeight(64)
        bl = QHBoxLayout(bottombar)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(14)

        info = QWidget()
        il = QVBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(2)
        self.modelLabel = QLabel("Модель не загружена")
        self.modelLabel.setObjectName("modelLabel")
        self.hintLabel = QLabel("Вставь ссылку выше и нажми Загрузить")
        self.hintLabel.setObjectName("hint")
        il.addWidget(self.modelLabel)
        il.addWidget(self.hintLabel)
        bl.addWidget(info, 1)

        self.dlBtn = QPushButton("⬇  СКАЧАТЬ")
        self.dlBtn.setObjectName("dlBtn")
        self.dlBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dlBtn.setEnabled(False)
        self.dlBtn.clicked.connect(self.do_download)
        bl.addWidget(self.dlBtn)

        layout.addWidget(bottombar)

    def handle_download(self, download: QWebEngineDownloadRequest):
        # Auto-accept all downloads to the Downloads folder
        suggested = download.suggestedFileName()
        save_path = os.path.join(self.download_dir, suggested)
        download.setDownloadDirectory(self.download_dir)
        download.setDownloadFileName(suggested)
        download.accept()
        download.isFinishedChanged.connect(
            lambda: self.hintLabel.setText(f"Сохранено: {save_path}")
            if download.isFinished() else None
        )
        self.hintLabel.setText(f"Скачивается: {suggested}...")

    def load_model(self):
        url = self.urlInput.text().strip()
        if not url:
            self.hintLabel.setText("Введи ссылку на модель")
            return
        if "sketchfab.com" not in url:
            self.hintLabel.setText("Это не ссылка Sketchfab")
            return
        self.model_loaded = False
        self.dlBtn.setEnabled(False)
        self.modelLabel.setText("Загрузка...")
        self.hintLabel.setText(url)
        self.webview.setUrl(QUrl(url))

    def on_load_started(self):
        self.hintLabel.setText("Загрузка страницы...")

    def on_load_finished(self, ok):
        if not ok:
            self.hintLabel.setText("Ошибка загрузки")
            return
        self.page.runJavaScript(INJECT_JS, lambda r: None)
        self.model_loaded = True
        self.dlBtn.setEnabled(True)
        self.hintLabel.setText("Дождись загрузки модели (30-60 сек), затем нажми СКАЧАТЬ")
        self.page.runJavaScript(
            "document.querySelector('.model-name__label') ? document.querySelector('.model-name__label').textContent.trim() : document.title",
            self.set_model_name
        )

    def set_model_name(self, name):
        if name:
            self.modelLabel.setText(name)

    def do_download(self):
        if not self.model_loaded:
            return
        self.hintLabel.setText("Подготовка файла...")
        self.page.runJavaScript(
            "window.__doDownload ? window.__doDownload() : 'not_ready'",
            lambda r: self.hintLabel.setText(
                "Библиотеки ещё загружаются, подожди..." 
                if str(r) == 'not_ready' else "Сохраняется..."
            )
        )


def main():
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-sandbox")
    app = QApplication(sys.argv)
    app.setApplicationName("Sketchfab Downloader")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
