// ── Mascot tips ───────────────────────────────────────────────
const tips = [
  "¿Sabías que el <strong>IVA en México es 16%</strong>? Ya lo precargué para ti.",
  "El <strong>RFC</strong> del receptor es obligatorio en CFDI 4.0. No olvides pedírselo a tu cliente.",
  "Usa <strong>Uso CFDI G03</strong> para gastos en general. Es el más común.",
  "El método de pago <strong>PUE</strong> significa que el cliente pagará en una sola exhibición.",
  "¿Dudas sobre facturación? Chatea conmigo y te ayudo en segundos.",
  "Recuerda guardar el <strong>XML</strong> y el <strong>PDF</strong> de tus facturas por 5 años.",
  "Si tu cliente es empresa, su <strong>régimen fiscal</strong> suele ser 601 o 612.",
];
let tipIdx = 0;

function showMascotTip() {
  const bubble = document.querySelector('.mascot-bubble');
  if (!bubble) return;
  bubble.innerHTML = tips[tipIdx % tips.length];
  bubble.classList.add('visible');
  tipIdx++;
  setTimeout(() => bubble.classList.remove('visible'), 5000);
}

function initMascot() {
  const avatar = document.querySelector('.mascot-avatar');
  if (!avatar) return;

  // Show first tip after 2s, then rotate
  setTimeout(showMascotTip, 2000);
  setInterval(showMascotTip, 12000);

  // Clicking avatar opens chat
  avatar.addEventListener('click', toggleChat);
}

// ── AI Chat ───────────────────────────────────────────────────
const chatHistory = [];

function toggleChat() {
  const panel = document.querySelector('.chat-panel');
  const btn = document.querySelector('.chat-btn');
  if (!panel) return;
  const isOpen = panel.classList.contains('open');
  panel.classList.toggle('open', !isOpen);
  btn?.classList.toggle('open', !isOpen);
  if (!isOpen) {
    document.getElementById('chat-input')?.focus();
    // Send greeting on first open
    if (chatHistory.length === 0) {
      addBotMessage("¡Hola! Soy **Max**, tu asistente de facturación mexicana 🤖\n\nPuedo ayudarte con CFDI 4.0, RFC, IVA, régimen fiscal y más. ¿En qué te ayudo hoy?");
    }
  }
}

function addBotMessage(text) {
  const messages = document.querySelector('.chat-messages');
  if (!messages) return;
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  div.innerHTML = `<div class="msg-bubble">${text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addUserMessage(text) {
  const messages = document.querySelector('.chat-messages');
  if (!messages) return;
  const div = document.createElement('div');
  div.className = 'chat-msg user';
  div.innerHTML = `<div class="msg-bubble">${text}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function showTyping() {
  const messages = document.querySelector('.chat-messages');
  if (!messages) return;
  const div = document.createElement('div');
  div.className = 'chat-msg bot typing-msg';
  div.innerHTML = `<div class="msg-bubble"><div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

async function sendChat(text) {
  if (!text.trim()) return;
  addUserMessage(text);
  chatHistory.push({ role: 'user', content: text });

  const typingEl = showTyping();

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory }),
    });
    const data = await resp.json();
    typingEl?.remove();
    const reply = data.content || 'Lo siento, no pude procesar tu mensaje.';
    addBotMessage(reply);
    chatHistory.push({ role: 'assistant', content: reply });
  } catch {
    typingEl?.remove();
    addBotMessage('Ocurrió un error de conexión. Inténtalo de nuevo.');
  }
}

function initChat() {
  const btn = document.querySelector('.chat-btn');
  btn?.addEventListener('click', toggleChat);

  const input = document.getElementById('chat-input');
  const sendBtn = document.querySelector('.chat-send');

  sendBtn?.addEventListener('click', () => {
    const txt = input.value.trim();
    if (!txt) return;
    input.value = '';
    sendChat(txt);
  });

  input?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const txt = input.value.trim();
      if (!txt) return;
      input.value = '';
      sendChat(txt);
    }
  });

  document.querySelectorAll('.chat-suggestion').forEach(s => {
    s.addEventListener('click', () => {
      const txt = s.textContent;
      if (!document.querySelector('.chat-panel').classList.contains('open')) toggleChat();
      sendChat(txt);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initMascot();
  initChat();
});
