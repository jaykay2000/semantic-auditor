// Shared furniture for the beat-4 clips (m7-b4-*): top bar with the required labels, headline, and the
// three-step strip that tells the viewer which transition this is. Data: window.DATA.beat4 (extract_beat4.py).
window.B4 = window.DATA && window.DATA.beat4;
window.esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
window.money = a => '$' + Number(a).toFixed(2);
window.b4Head = (step, title) => `
  <div class="bar in" style="--at:0">
    <div class="brand"><span class="logo">SRA</span>Semantic Release Auditor</div><span class="sep"></span>
    <span class="app">Spree Commerce</span><span class="tag">a real open-source store</span>
    <div class="right"><span class="tag strong">Prototype: 6 of 57 held-out agent findings converted</span>
      <span class="tag" style="color:var(--accent);border-color:var(--accentln)">Muse Spark Open (on Baseten)</span></div>
  </div>
  <div class="b4row in" style="--at:.15">
    <h2>${title}</h2>
    <div class="mini">${['finding → approved check', 'older release → next release', 'new review, from storage']
      .map((s, i) => `<span class="${i + 1 === step ? 'on' : i + 1 < step ? 'done' : ''}">${i + 1} · ${s}</span>`).join('<i>›</i>')}</div>
  </div>`;
window.b4Src = extra => `<div class="src fade" style="--at:.3"><b>Source:</b> redrawn from the saved results of run
  ${esc(B4.run.id)} (${esc(B4._source.saved.split('/').slice(-2).join('/'))})${extra ? ' · ' + extra : ''}</div>`;
