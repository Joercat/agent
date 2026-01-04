class Agent {
    constructor() {
        this.ws = null;
        this.state = { running: false, paused: false };
        this.el = {
            status: document.getElementById('status'),
            task: document.getElementById('task'),
            startBtn: document.getElementById('start-btn'),
            pauseBtn: document.getElementById('pause-btn'),
            stopBtn: document.getElementById('stop-btn'),
            humanInput: document.getElementById('human-input'),
            sendBtn: document.getElementById('send-btn'),
            questionBox: document.getElementById('question-box'),
            findings: document.getElementById('findings'),
            count: document.getElementById('count'),
            log: document.getElementById('log'),
            vnc: document.getElementById('vnc'),
            fullscreenBtn: document.getElementById('fullscreen-btn')
        };
        
        this.connect();
        this.bind();
    }
    
    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${location.host}/ws`);
        
        this.ws.onopen = () => this.log('Connected', 'success');
        this.ws.onclose = () => {
            this.log('Disconnected, reconnecting...', 'warn');
            setTimeout(() => this.connect(), 2000);
        };
        this.ws.onmessage = e => this.handle(JSON.parse(e.data));
    }
    
    bind() {
        this.el.startBtn.onclick = () => this.start();
        this.el.pauseBtn.onclick = () => this.togglePause();
        this.el.stopBtn.onclick = () => this.send('stop');
        this.el.sendBtn.onclick = () => this.sendInput();
        this.el.humanInput.onkeydown = e => e.key === 'Enter' && this.sendInput();
        this.el.fullscreenBtn.onclick = () => this.el.vnc.requestFullscreen();
    }
    
    handle(data) {
        if (data.type === 'state') this.updateState(data);
        else if (data.type === 'log') {
            this.log(data.message, data.level);
            if (data.level === 'question') this.showQuestion(data.message);
        }
        else if (data.type === 'finding') this.addFinding(data);
    }
    
    updateState(s) {
        this.state = { ...this.state, ...s };
        const { running, paused } = this.state;
        
        this.el.startBtn.disabled = running;
        this.el.pauseBtn.disabled = !running;
        this.el.stopBtn.disabled = !running;
        this.el.humanInput.disabled = !running;
        this.el.sendBtn.disabled = !running;
        
        this.el.pauseBtn.textContent = paused ? '▶️' : '⏸️';
        this.el.status.textContent = running ? (paused ? 'Paused' : 'Running') : 'Ready';
        this.el.status.className = `status ${running ? (paused ? 'paused' : 'running') : 'idle'}`;
    }
    
    log(msg, level = 'info') {
        const d = document.createElement('div');
        d.className = `log-entry ${level}`;
        d.textContent = msg;
        this.el.log.appendChild(d);
        this.el.log.scrollTop = this.el.log.scrollHeight;
    }
    
    showQuestion(q) {
        this.el.questionBox.textContent = q.replace('🤖 NEED HELP: ', '');
        this.el.questionBox.classList.remove('hidden');
        this.el.humanInput.focus();
    }
    
    addFinding(f) {
        const d = document.createElement('div');
        d.className = 'finding';
        d.innerHTML = `
            <div class="finding-title">${f.title || 'Item'}</div>
            <div class="finding-price">${f.price || ''}</div>
            <div class="finding-notes">${f.notes || ''}</div>
            ${f.url ? `<a class="finding-link" href="${f.url}" target="_blank">View →</a>` : ''}
        `;
        this.el.findings.prepend(d);
        this.el.count.textContent = this.el.findings.children.length;
    }
    
    send(action, data = {}) {
        if (this.ws.readyState === 1) 
            this.ws.send(JSON.stringify({ action, ...data }));
    }
    
    start() {
        const task = this.el.task.value.trim();
        if (task) this.send('start', { task });
    }
    
    togglePause() {
        this.send(this.state.paused ? 'resume' : 'pause');
    }
    
    sendInput() {
        const msg = this.el.humanInput.value.trim();
        if (msg) {
            this.send('human_input', { message: msg });
            this.el.humanInput.value = '';
            this.el.questionBox.classList.add('hidden');
        }
    }
}

new Agent();
