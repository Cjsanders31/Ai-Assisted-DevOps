const queryInput = document.querySelector('#query');
const askForm = document.querySelector('#askForm');
const chatMessages = document.querySelector('#chatMessages');
const sendButton = document.querySelector('#sendButton');
const conversation = [];

function addMessage(role, text) {
  const article = document.createElement('article');
  article.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;

  if (role !== 'user') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'P';
    article.append(avatar);
  }

  const body = document.createElement('div');
  body.className = 'message-body';
  const label = document.createElement('span');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'YOU' : 'PAPERTRAIL';
  const content = document.createElement('p');
  content.className = 'message-text';
  content.textContent = text;
  body.append(label, content);

  article.append(body);
  chatMessages.append(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return article;
}

function renderLibrary(files) {
  const count = document.querySelector('#docCount');
  const library = document.querySelector('#library');
  count.textContent = `${files.length} PDF${files.length === 1 ? '' : 's'}`;
  library.replaceChildren();
  if (!files.length) {
    const empty = document.createElement('p');
    empty.className = 'library-empty';
    empty.textContent = 'Add a PDF to start asking questions.';
    library.append(empty);
    return;
  }

  files.forEach((file) => {
    const item = document.createElement('div');
    item.className = 'library-file';
    const icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.textContent = 'PDF';
    const name = document.createElement('span');
    name.textContent = file;
    name.title = file;
    item.append(icon, name);
    library.append(item);
  });
}

async function refreshStatus() {
  const statusText = document.querySelector('#statusText');
  try {
    const [statusResponse, libraryResponse] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/library'),
    ]);
    if (!statusResponse.ok || !libraryResponse.ok) throw new Error('Could not load library status.');
    const status = await statusResponse.json();
    const library = await libraryResponse.json();
    statusText.textContent = `${status.documents} documents · ${status.chunks} passages indexed`;
    renderLibrary(library.files || []);
  } catch {
    statusText.textContent = 'Library status unavailable';
    renderLibrary([]);
  }
}

async function ask(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion || sendButton.disabled) return;

  addMessage('user', cleanQuestion);
  const pending = addMessage('assistant', 'Searching your PDFs…');
  pending.classList.add('pending-message');
  sendButton.disabled = true;
  queryInput.disabled = true;
  conversation.push({ role: 'user', content: cleanQuestion });

  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: cleanQuestion, history: conversation.slice(-8) }),
    });
    if (!response.ok) throw new Error(`Request failed (${response.status}). Please try again.`);
    const result = await response.json();
    const assistantText = result.answer || 'I could not produce an answer for that question.';
    pending.querySelector('.message-text').textContent = assistantText;
    pending.classList.remove('pending-message');
    pending.querySelector('.message-body').append(makeSourceDetails(result.sources || []));
    conversation.push({ role: 'assistant', content: assistantText });
  } catch (error) {
    pending.querySelector('.message-text').textContent = error.message || 'Something went wrong. Please try again.';
    pending.classList.remove('pending-message');
    pending.classList.add('error-message');
    conversation.pop();
  } finally {
    sendButton.disabled = false;
    queryInput.disabled = false;
    queryInput.value = '';
    queryInput.focus();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function makeSourceDetails(sourceItems) {
  if (!sourceItems.length) return document.createDocumentFragment();
  const details = document.createElement('details');
  details.className = 'message-sources';
  const summary = document.createElement('summary');
  summary.textContent = `Sources used (${sourceItems.length})`;
  const list = document.createElement('div');
  list.className = 'source-list';

  sourceItems.forEach((source) => {
    const card = document.createElement('article');
    card.className = 'source-card';
    const meta = document.createElement('div');
    meta.className = 'source-meta';
    const filename = document.createElement('strong');
    filename.textContent = source.filename;
    const page = document.createElement('span');
    page.textContent = `PAGE ${source.page} · ${(source.score * 100).toFixed(0)}% MATCH`;
    const passage = document.createElement('p');
    passage.textContent = source.text;
    meta.append(filename, page);
    card.append(meta, passage);
    list.append(card);
  });

  details.append(summary, list);
  return details;
}

askForm.addEventListener('submit', (event) => {
  event.preventDefault();
  ask(queryInput.value);
});

queryInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    ask(queryInput.value);
  }
});

document.querySelectorAll('[data-question]').forEach((button) => {
  button.addEventListener('click', () => {
    queryInput.value = button.dataset.question;
    ask(queryInput.value);
  });
});

document.querySelector('#fileInput').addEventListener('change', async (event) => {
  const files = [...event.target.files];
  if (!files.length) return;
  const uploadLabel = document.querySelector('.upload');
  const originalLabel = uploadLabel.childNodes[1]?.textContent || ' Add PDFs';
  uploadLabel.childNodes[1].textContent = ' Indexing PDFs…';
  try {
    const data = new FormData();
    files.forEach((file) => data.append('files', file));
    const response = await fetch('/api/ingest', { method: 'POST', body: data });
    if (!response.ok) throw new Error('PDF upload failed. Please try again.');
    const result = await response.json();
    await refreshStatus();
    addMessage('assistant', `Library updated: ${result.documents} documents and ${result.chunks} passages indexed.`);
  } catch (error) {
    addMessage('assistant', error.message || 'Could not upload the selected PDFs.');
  } finally {
    uploadLabel.childNodes[1].textContent = originalLabel;
    event.target.value = '';
  }
});

refreshStatus();