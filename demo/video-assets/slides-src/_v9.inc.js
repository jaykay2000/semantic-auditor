// v9 shared furniture: the one persistent header (SRA badge · app chip · model pill) and small helpers.
// v9Head({app, note, model}) -> HTML. app: finablo | spree | northbound | brightdesk | null; model: pill text or null.
window.APP9 = {finablo: 'Finablo', spree: 'Spree', northbound: 'Northbound', brightdesk: 'Brightdesk'};
window.esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
window.v9Head = ({app = null, note = '', model = null} = {}) => `<header class="h9">
  <div class="sra"><span class="logo">SRA</span><span>Semantic Release Auditor</span></div>
  ${app ? `<span class="sep"></span><span class="appchip" data-app="${app}"><i></i>${APP9[app]}${note ? `<em>${note}</em>` : ''}</span>` : ''}
  ${model ? `<span class="model">${model}</span>` : ''}</header>`;
// counter: el.textContent counts from 0 to el.dataset.to over [at, at+d], formatted with thousands separators
window.counters = () => onSeek(t => document.querySelectorAll('[data-count]').forEach(el => {
  const at = +el.dataset.at, d = +(el.dataset.d || 1), to = +el.dataset.count;
  const p = 1 - Math.pow(1 - clamp01((t - at) / d), 3);
  el.textContent = (el.dataset.pre || '') + Math.round(to * p).toLocaleString('en-US') + (el.dataset.post || '');
}));
// .when-on: toggles class "on" at data-on seconds (for highlight states CSS cannot time on its own)
window.toggles = () => onSeek(t => document.querySelectorAll('[data-on]').forEach(el =>
  el.classList.toggle('on', t >= +el.dataset.on && !(el.dataset.off && t >= +el.dataset.off))));
