const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const movesEl = document.getElementById('moves');
const reportsEl = document.getElementById('reports');

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
document.getElementById('watchBtn').onclick = async () => {
  const gameId = document.getElementById('gameId').value.trim();
  if (!gameId) return;
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/viewer/${gameId}`);
  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === 'game_update') renderState(msg.data);
  };
  const game = await fetch(`/api/games/${gameId}`).then(r => r.json());
  renderState(game);
};

refreshReports();
setInterval(refreshReports, 5000);
