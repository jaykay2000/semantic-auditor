// Shared by m7-b3a/m7-b3b: the two circles of s7-b3a/b drift together until they overlap in part, then the labels
// (and, in the counted variant only, the numbers) appear. Circles stay equal: size never encodes a count.
// The overlap is wider than in s7-b3a/b so "in both" no longer crosses the circle outlines; its width encodes nothing.
function drawOverlapMotion(counts) {
  const D = window.DATA['overlap'];
  const lab = (x, y, k, text, at) => `<g transform="translate(${x},${y})" class="fade" style="--at:${at}"><text text-anchor="middle">${counts
    ? `<tspan class="num" x="0" dy="0">${D[k]}</tspan><tspan class="lab" x="0" dy="58">${text}</tspan>`
    : `<tspan class="lab" x="0" dy="0">${text}</tspan>`}</text></g>`;
  document.getElementById('venn').innerHTML = `
    <circle id="k1" cx="760" cy="300" r="230" class="c1"/><circle id="k2" cx="1040" cy="300" r="230" class="c2"/>
    <text x="600" y="34" text-anchor="middle" class="run fade" style="--at:.5">Run 1</text>
    <text x="1200" y="34" text-anchor="middle" class="run fade" style="--at:.5">Run 2</text>
    ${lab(625, counts ? 300 : 315, 'run_1_only', 'only in run 1', 2.3)}
    ${lab(900, counts ? 300 : 315, 'both', 'in both', 2.9)}
    ${lab(1175, counts ? 300 : 315, 'run_2_only', 'only in run 2', 2.3)}`;
  if (counts) document.getElementById('total').textContent = `${D.groups} groups of findings · ${D.both} in both runs`;
  const ease = x => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);
  onSeek(t => {
    const p = ease((t - .5) / 1.6), op = Math.min(1, Math.max(0, (t - .3) / .4));
    const k1 = document.getElementById('k1'), k2 = document.getElementById('k2');
    k1.setAttribute('cx', 520 + (760 - 520) * p); k2.setAttribute('cx', 1280 - (1280 - 1040) * p);
    k1.style.opacity = op; k2.style.opacity = op;
  });
}
