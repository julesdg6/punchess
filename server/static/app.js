const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const movesEl = document.getElementById('moves');
const reportsEl = document.getElementById('reports');
const gameIdEl = document.getElementById('gameId');
const launchStatusEl = document.getElementById('launchStatus');
const startMatchBtn = document.getElementById('startMatchBtn');
const watchBtn = document.getElementById('watchBtn');

const pieces = {
  p: '♟', r: '♜', n: '♞', b: '♝', q: '♛', k: '♚',
  P: '♙', R: '♖', N: '♘', B: '♗', Q: '♕', K: '♔'
};

function renderBoard(fen) {
  boardEl.innerHTML = '';
  const rows = fen.split(' ')[0].split('/');
  for (let r = 0; r < 8; r++) {
    const tr = document.createElement('tr');
    let file = 0;
    for (const ch of rows[r]) {
      if (!isNaN(ch)) {
        for (let i = 0; i < Number(ch); i++) {
          const td = document.createElement('td');
          td.className = (r + file) % 2 === 0 ? 'light' : 'dark';
          tr.appendChild(td);
          file++;
        }
      } else {
        const td = document.createElement('td');
        td.className = (r + file) % 2 === 0 ? 'light' : 'dark';
        td.textContent = pieces[ch] || ch;
        tr.appendChild(td);
        file++;
      }
    }
    boardEl.appendChild(tr);
  }
}

function renderState(state) {
  renderBoard(state.fen);
  statusEl.textContent = JSON.stringify({
    players: state.players,
    turn: state.turn,
    current_fen: state.fen,
    status: state.status,
    result: state.result,
    termination_reason: state.termination_reason,
    captured_pieces: state.captured_pieces_count,
    checks: state.checks,
    illegal_move_warnings: state.illegal_attempts,
    seconds_left: state.seconds_left,
    report_url: state.report_url
  }, null, 2);
  movesEl.textContent = state.moves.join(' ');
}

function setLaunchStatus(message, isError = false) {
  launchStatusEl.textContent = message;
  launchStatusEl.className = isError ? 'error' : '';
}

async function refreshReports() {
  const data = await fetch('/api/reports').then(r => r.json());
  reportsEl.innerHTML = '';
  for (const rep of data.reports) {
    const li = document.createElement('li');
    li.innerHTML = `<strong>${rep.game_id}</strong> ${rep.result} - <a href="${rep.report_json}">json</a> <a href="${rep.report_md}">md</a> <a href="${rep.game_pgn}">pgn</a>`;
    reportsEl.appendChild(li);
  }
}

let ws = null;
async function watchGame() {
  const gameId = gameIdEl.value.trim();
  if (!gameId) return;
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/viewer/${gameId}`);
  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === 'game_update') renderState(msg.data);
  };
  const game = await fetch(`/api/games/${gameId}`).then(r => r.json());
  renderState(game);
}

watchBtn.onclick = watchGame;

startMatchBtn.onclick = async () => {
  startMatchBtn.disabled = true;
  setLaunchStatus('Launching bundled clients...');
  try {
    const payload = {
      white_client: document.getElementById('whiteClient').value,
      white_name: document.getElementById('whiteName').value,
      black_client: document.getElementById('blackClient').value,
      black_name: document.getElementById('blackName').value
    };
    const response = await fetch('/api/matches/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to launch bundled clients');
    }
    const names = data.clients.map((client) => `${client.color}: ${client.name}`).join(' · ');
    if (data.game_id) {
      gameIdEl.value = data.game_id;
      setLaunchStatus(`Started ${names}. Watching game ${data.game_id}.`);
      await watchGame();
    } else if (data.auto_start) {
      const whiteName = data.clients.find((c) => c.color === 'white')?.name;
      const blackName = data.clients.find((c) => c.color === 'black')?.name;
      setLaunchStatus(`Launched ${names}. Waiting for the bots to finish pairing...`);
      const gameId = await pollForGame(whiteName, blackName);
      if (gameId) {
        gameIdEl.value = gameId;
        setLaunchStatus(`Started ${names}. Watching game ${gameId}.`);
        await watchGame();
      } else {
        setLaunchStatus(`Launched ${names}. Bots are still pairing – check the server logs.`, true);
      }
    } else {
      setLaunchStatus(`Launched ${names}. They joined the lobby, but auto-start is disabled.`);
    }
  } catch (error) {
    setLaunchStatus(error.message || 'Failed to launch bundled clients', true);
  } finally {
    startMatchBtn.disabled = false;
  }
};

async function pollForGame(whiteName, blackName, timeoutMs = 60000, intervalMs = 1000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    try {
      const resp = await fetch('/api/games');
      const data = await resp.json();
      const match = (data.games || []).find(
        (g) => g.white === whiteName && g.black === blackName
      );
      if (match) return match.game_id;
    } catch (_) { /* ignore transient errors */ }
  }
  return null;
}

refreshReports();
setInterval(refreshReports, 5000);
