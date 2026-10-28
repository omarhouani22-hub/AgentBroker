/* Private metadata only. Never render provider text, prompts, errors or credentials. */
(() => {
  'use strict';
  const status = document.getElementById('connection-status');
  const refresh = document.getElementById('connection-refresh');
  const test = document.getElementById('connection-test');
  if (!status || !refresh || !test) return;
  const routes = {local:'Local model',openrouter_free:'Free OpenRouter route',experimental_local_with_free_fallback:'Experimental local model (free OpenRouter fallback)',experimental_local:'Experimental local model',local_rule:'Local text rule',unknown:'Unknown'};
  async function check(runTest) {
    refresh.disabled = test.disabled = true;
    status.textContent = runTest ? 'Waiting for Clara’s diagnostic response…' : 'Checking…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 115000);
    try {
      const response = await fetch('/companion/connection' + (runTest ? '/test' : ''), {
        method:runTest ? 'POST' : 'GET', cache:'no-store', signal:controller.signal,
        headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},
        body:runTest ? '{}' : undefined
      });
      if (response.status === 401) { status.textContent = 'Sign in to view Clara’s private connection.'; return; }
      const data = await response.json();
      if (!data.selected_route) { status.textContent = response.status === 429 ? 'Daily free allowance reached.' : response.status === 409 ? 'Clara is busy; try shortly.' : 'Connection status unavailable.'; return; }
      const last = data.last_observation;
      status.textContent = 'Selected: ' + (routes[data.selected_route] || 'Unknown') +
        ' · Configured: ' + (data.configured ? 'Yes' : 'No') +
        ' · Remaining today: ' + (data.remaining_today ?? 'No daily local limit') +
        (last ? ' · Last observed: ' + (routes[last.route] || 'Unknown') +
          ' · Provider-reported model: ' + last.model + ' · Result: ' + last.status +
          (last.error ? ' (' + last.error + ')' : '') + ' · Response time: ' + last.duration_ms + ' ms' +
          ' · Checked: ' + last.checked_at : ' · Provider-reported model: unknown · No observation yet') +
        ' · Observations reset when the server restarts.';
    } catch (_) { status.textContent = 'Connection check unavailable or timed out. Refresh status before retrying.'; }
    finally { clearTimeout(timer); refresh.disabled = test.disabled = false; }
  }
  refresh.onclick = () => check(false);
  test.onclick = () => check(true);
})();
