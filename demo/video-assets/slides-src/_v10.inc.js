// v10 shared furniture (load after _v9.inc.js): the corner marker of the four contributions (V3-V6).
// marker10(n) -> HTML: the four numbers, n lit, with the first word of n's title beside it (v10.json contributions,
// so changing a title in extract_v10.py changes the marker too).
window.MARK10 = n => window.DATA.v10.contributions[n - 1].title.split(' ')[0];
window.marker10 = (n, cls = '') => `<div class="mk ${cls}" aria-label="contribution ${n} of 4">${[1, 2, 3, 4].map(i =>
  `<span class="n${i === n ? ' on' : ''}">${i}</span>`).join('')}${n ? `<span class="lab">${esc(MARK10(n))}</span>` : ''}</div>`;
// yamlLines(lines) -> HTML: contract lines as written, keys dimmed, nothing reworded.
window.yamlLines = lines => lines.map(l => esc(l).replace(/(\{|, )(\w+):/g, '$1<span class="k">$2:</span>')
  .replace(/^(\s*-?\s*)(\w+):/, '$1<span class="k">$2:</span>')).join('\n');
