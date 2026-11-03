// v10 shared furniture (load after _v9.inc.js): the corner marker of the four contributions (V3-V6).
// marker10(n) -> HTML: the four numbers, n lit, with n's short title beside it. Titles come from v10.json.
window.MARK10 = {1: 'Judges', 2: 'Keeps', 3: 'Checks itself', 4: 'Plugs in'};
window.marker10 = (n, cls = '') => `<div class="mk ${cls}" aria-label="contribution ${n} of 4">${[1, 2, 3, 4].map(i =>
  `<span class="n${i === n ? ' on' : ''}">${i}</span>`).join('')}${n ? `<span class="lab">${MARK10[n]}</span>` : ''}</div>`;
// yamlLines(lines) -> HTML: contract lines as written, keys dimmed, nothing reworded.
window.yamlLines = lines => lines.map(l => esc(l).replace(/(\{|, )(\w+):/g, '$1<span class="k">$2:</span>')
  .replace(/^(\s*-?\s*)(\w+):/, '$1<span class="k">$2:</span>')).join('\n');
