// This runs inside the Sketchfab page context BEFORE any page scripts
// Mirrors exactly what Tampermonkey does with @run-at document-start

const { ipcRenderer } = require('electron');

(function () {
  'use strict';

  // ── regex patterns from original userscript ──────────────────────────────
  var func_drawGeometry   = /(this\._stateCache\.drawGeometry\(this\._graphicContext,t\))/g;
  var fund_drawArrays     = /t\.drawArrays\(t\.TRIANGLES,0,6\)/g;
  var func_renderInto1    = /A\.renderInto\(n,E,R/g;
  var func_renderInto2    = /g\.renderInto=function\(e,i,r/g;
  var func_getResourceImage = /getResourceImage:function\(e,t\){/g;

  // ── state ─────────────────────────────────────────────────────────────────
  window.allmodel = [];
  var saveimagecache2 = {};
  var objects = {};

  // ── helpers ───────────────────────────────────────────────────────────────
  var saveimage_to_list = function (url, file_name) {
    if (!saveimagecache2[url]) saveimagecache2[url] = { name: file_name };
  };

  // ── download trigger (called from renderer via ipc) ───────────────────────
  window.__doDownload = function () {
    if (!window.JSZip) { ipcRenderer.send('dl-status', 'jszip_not_ready'); return; }
    if (window.allmodel.length === 0) { ipcRenderer.send('dl-status', 'empty'); return; }

    var zip = new JSZip();
    var folder = zip.folder('model');
    objects = {};

    var idx = 0;
    window.allmodel.forEach(function (obj) {
      var mdl = { name: 'model_' + idx, obj: parseobj(obj) };
      dosavefile(mdl);
      idx++;
    });

    for (var obj in objects) folder.file(obj, objects[obj], { binary: true });

    var nameEl = document.querySelector('.model-name__label');
    var file_name = nameEl ? nameEl.textContent.trim() : 'sketchfab_model';

    folder.generateAsync({ type: 'nodebuffer' }).then(function (buffer) {
      ipcRenderer.send('save-zip', { buffer: buffer, name: file_name + '.zip' });
    });
  };

  window.__getModelCount = function () {
    return window.allmodel.length;
  };

  // ── geometry extraction ───────────────────────────────────────────────────
  var parseobj = function (obj) {
    var list = [];
    obj._primitives.forEach(function (p) {
      if (p && p.indices) list.push({ mode: p.mode, indices: p.indices._elements });
    });
    var attr = obj._attributes;
    return {
      vertex: attr.Vertex._elements,
      normal: attr.Normal ? attr.Normal._elements : [],
      uv: attr.TexCoord0 ? attr.TexCoord0._elements :
          attr.TexCoord1 ? attr.TexCoord1._elements : [],
      primitives: list
    };
  };

  var dosavefile = function (mdl) {
    var obj = mdl.obj;
    var str = 'o ' + mdl.name + '\n';
    for (var i = 0; i < obj.vertex.length; i += 3)
      str += 'v ' + obj.vertex[i] + ' ' + obj.vertex[i + 1] + ' ' + obj.vertex[i + 2] + '\n';
    for (i = 0; i < obj.normal.length; i += 3)
      str += 'vn ' + obj.normal[i] + ' ' + obj.normal[i + 1] + ' ' + obj.normal[i + 2] + '\n';
    for (i = 0; i < obj.uv.length; i += 2)
      str += 'vt ' + obj.uv[i] + ' ' + obj.uv[i + 1] + '\n';
    str += 's on\n';
    var vn = obj.normal.length !== 0, vt = obj.uv.length !== 0;
    for (i = 0; i < obj.primitives.length; ++i) {
      var prim = obj.primitives[i];
      if (prim.mode === 4 || prim.mode === 5) {
        var strip = prim.mode === 5;
        for (var j = 0; j + 2 < prim.indices.length; !strip ? j += 3 : j++) {
          str += 'f ';
          var order = (strip && j % 2 === 1) ? [0, 2, 1] : [0, 1, 2];
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
    objects[mdl.name + '.obj'] = Buffer.from(str);
  };

  // ── hooks injected into patched Sketchfab code ────────────────────────────
  window.attachbody = function (obj) {
    if (obj._faked !== true &&
        ((obj.stateset && obj.stateset._name) || obj._name ||
         (obj._parents && obj._parents[0] && obj._parents[0]._name))) {
      obj._faked = true;
      if (obj._name === 'composer layer' || obj._name === 'Ground - Geometry') return;
      window.allmodel.push(obj);
      ipcRenderer.send('model-count', window.allmodel.length);
    }
  };

  window.drawhookcanvas = function (e, imagemodel) {
    if ((e.width === 128 && e.height === 128) ||
        (e.width === 32  && e.height === 32)  ||
        (e.width === 64  && e.height === 64)) return e;
    if (imagemodel) {
      var alpha = e.options.format, url_image = e.url, max_size = 0, obr = e;
      imagemodel.attributes.images.forEach(function (img) {
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

  window.drawhookimg = function (gl, t) {
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
    canvas.toBlob(function (blob) {
      blob.arrayBuffer().then(function (ab) {
        objects[name] = Buffer.from(ab);
      });
    }, 'image/png');
  };

  // ── load JSZip from CDN ───────────────────────────────────────────────────
  var s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.1.5/jszip.min.js';
  document.head.appendChild(s);

  // ── THE KEY PART: intercept Sketchfab scripts before execution ────────────
  // This is what Tampermonkey does — we patch JS before it runs
  var http = require('http');
  var https = require('https');

  var origOpen = XMLHttpRequest.prototype.open;

  // Patch via MutationObserver on <script> tags (same as Tampermonkey approach)
  var patchScript = function (src) {
    var mod = src.indexOf('web/dist/') >= 0 || src.indexOf('standaloneViewer') >= 0;
    if (!mod) return null;

    var xhr = new XMLHttpRequest();
    xhr.open('GET', src, false); // sync
    xhr.send('');
    var js = xhr.responseText;

    var ret, patched = 0;

    ret = func_renderInto1.exec(js);
    if (ret) { var i = ret.index + ret[0].length; js = js.slice(0, i) + ',i' + js.slice(i); patched++; }

    ret = func_renderInto2.exec(js);
    if (ret) { var i = ret.index + ret[0].length; js = js.slice(0, i) + ',image_data' + js.slice(i); patched++; }

    ret = fund_drawArrays.exec(js);
    if (ret) { var i = ret.index + ret[0].length; js = js.slice(0, i) + ',window.drawhookimg(t,image_data)' + js.slice(i); patched++; }

    ret = func_getResourceImage.exec(js);
    if (ret) { var i = ret.index + ret[0].length; js = js.slice(0, i) + 'e=window.drawhookcanvas(e,this._imageModel);' + js.slice(i); patched++; }

    ret = func_drawGeometry.exec(js);
    if (ret) { var i = ret.index + ret[1].length; js = js.slice(0, i) + ';window.attachbody(t);' + js.slice(i); patched++; }

    ipcRenderer.send('patch-status', patched);
    return js;
  };

  // Intercept appendChild to catch <script src="..."> before execution
  var origAppendChild = Node.prototype.appendChild;
  Node.prototype.appendChild = function (node) {
    if (node && node.tagName === 'SCRIPT' && node.src) {
      var patched = patchScript(node.src);
      if (patched !== null) {
        var s = document.createElement('script');
        s.type = 'text/javascript';
        s.text = patched;
        return origAppendChild.call(this, s);
      }
    }
    return origAppendChild.call(this, node);
  };

  var origInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function (node, ref) {
    if (node && node.tagName === 'SCRIPT' && node.src) {
      var patched = patchScript(node.src);
      if (patched !== null) {
        var s = document.createElement('script');
        s.type = 'text/javascript';
        s.text = patched;
        return origInsertBefore.call(this, s, ref);
      }
    }
    return origInsertBefore.call(this, node, ref);
  };

})();
