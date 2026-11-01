// Deterministic timeline for the motion clips. window.__seek(t) pauses every animation and sets it to
// t seconds; hooks registered with onSeek(fn) handle anything CSS cannot (counters, typed text).
// Opened directly in a browser (no ?render), the clip plays itself from 0 so it can be previewed.
window.__hooks = [];
window.onSeek = fn => window.__hooks.push(fn);
window.__seek = t => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  for (const h of window.__hooks) h(t);
};
window.clamp01 = x => Math.max(0, Math.min(1, x));
// typed text: el.dataset.text typed from --at over --d seconds
window.typeAll = () => onSeek(t => {
  for (const el of document.querySelectorAll('[data-type]')) {
    const at = parseFloat(el.dataset.at || 0), d = parseFloat(el.dataset.d || 1), s = el.dataset.type;
    const n = Math.round(clamp01((t - at) / d) * s.length);
    el.textContent = s.slice(0, n);
    el.style.visibility = t < at ? 'hidden' : 'visible';
  }
});
addEventListener('load', () => {
  window.DURATION = parseFloat(document.body.dataset.duration || 10);
  if (location.search.includes('render')) { window.__seek(0); return; }
  const t0 = performance.now();
  const tick = () => { const t = (performance.now() - t0) / 1000; window.__seek(Math.min(t, DURATION));
    if (t < DURATION + 2) requestAnimationFrame(tick); else setTimeout(() => location.reload(), 1500); };
  requestAnimationFrame(tick);
});
