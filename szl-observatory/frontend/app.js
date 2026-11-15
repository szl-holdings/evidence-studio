async function load() {
  const response = await fetch('/api/v1/snapshot');
  if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
  const snapshot = await response.json();
  document.querySelector('#status').textContent = `Generated ${new Date(snapshot.generated_at).toLocaleString()}`;
  document.querySelector('#cards').innerHTML = snapshot.metrics.map((metric) => `
    <article class="card">
      <p class="source">${metric.source}</p>
      <h2>${metric.name.replaceAll('_', ' ')}</h2>
      <p class="value">${Number(metric.value).toLocaleString()} <span>${metric.unit}</span></p>
      <p class="note">${metric.note ?? ''}</p>
      ${metric.evidence_url ? `<a href="${metric.evidence_url}" target="_blank" rel="noreferrer">Evidence ↗</a>` : ''}
    </article>`).join('');
  document.querySelector('#provenance').innerHTML = snapshot.provenance.map((url) => `<li><a href="${url}" target="_blank" rel="noreferrer">${url}</a></li>`).join('');
}
load().catch((error) => { document.querySelector('#status').textContent = error.message; });
