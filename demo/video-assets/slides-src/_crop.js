// crop(src, x, y, w, h, displayW): a sharp crop of a 2x page shot (3840x2160 for a 1920x1080 page; full-page shots
// keep the same 2x scale). x, y, w, h are CSS px on the page; displayW is the width the crop is drawn at.
// pageW: the CSS width the shot covers (1920 for a page shot; the clip's own width for a clipped element shot).
window.crop = (src, x, y, w, h, dw, extra = '', pageW = 1920) => {
  const k = dw / w;
  return `<div class="crop" ${extra} style="width:${dw}px;height:${Math.round(h * k)}px;background:url(${src}) ${-x * k}px ${-y * k}px/${pageW * k}px auto no-repeat"></div>`;
};
