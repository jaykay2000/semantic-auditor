// Shared by s7-b3a/s7-b3b. Draws two equal circles (sizes never encode a count) and, if COUNTS, the numbers.
function drawOverlap(counts) {
  const D = window.DATA['overlap'];
  const n = (k) => counts ? `<tspan class="num" x="0" dy="0">${D[k]}</tspan>` : '';
  const lab = (x, y, k, text) => `<g transform="translate(${x},${y})"><text text-anchor="middle">${counts ? `<tspan class="num" x="0" dy="0">${D[k]}</tspan><tspan class="lab" x="0" dy="58">${text}</tspan>` : `<tspan class="lab" x="0" dy="0">${text}</tspan>`}</text></g>`;
  document.getElementById('venn').innerHTML = `
    <circle cx="720" cy="300" r="230" class="c1"/><circle cx="1080" cy="300" r="230" class="c2"/>
    <text x="580" y="34" text-anchor="middle" class="run">Run 1</text><text x="1220" y="34" text-anchor="middle" class="run">Run 2</text>
    ${lab(600, counts ? 300 : 315, 'run_1_only', 'only in run 1')}
    ${lab(900, counts ? 300 : 315, 'both', 'in both')}
    ${lab(1200, counts ? 300 : 315, 'run_2_only', 'only in run 2')}`;
  if (counts) document.getElementById('total').textContent = `${D.groups} groups of findings · ${D.both} in both runs`;
}
