'use strict';

const state = {
  activeTab: 'text',
  selectedFile: null,
  lastResult: null,
};

const SAMPLES = {
  productive: `De: joao.silva@empresa.com
Para: suporte@financeiro.com
Assunto: Problema urgente – Acesso bloqueado ao sistema de pagamentos

Prezada equipe de suporte,

Meu nome é João Silva e sou Analista Financeiro do setor de Contas a Pagar.
Estou enfrentando um problema crítico desde esta manhã: meu acesso ao sistema 
de pagamentos foi bloqueado sem aviso prévio, impedindo o processamento de 
transferências urgentes com prazo hoje às 17h.

Número do meu usuário: USR-20481
Mensagem de erro: "401 – Acesso não autorizado"

Solicitações pendentes afetadas: NF-7821, NF-7834, NF-7850 (total: R$ 285.000,00)

Preciso urgentemente da restauração do acesso ou de um canal alternativo 
para processar esses pagamentos antes do prazo.

Atenciosamente,
João Silva
(11) 9 9123-4567`,

  unproductive: `De: maria.oliveira@empresa.com
Para: equipe@financeiro.com
Assunto: Feliz Natal e Próspero Ano Novo! 🎄🎆

Olá, querida equipe!

Queria aproveitar esse momento especial para desejar a todos um 
Feliz Natal repleto de paz, alegria e amor!

Que o próximo ano seja cheio de realizações, saúde e muitos 
momentos felizes para vocês e suas famílias.

Foi um prazer imenso trabalhar ao lado de todos vocês este ano. 
Juntos, alcançamos resultados incríveis!

Com muito carinho e gratidão,
Maria Oliveira 🎁✨`,
};

const $ = (id) => document.getElementById(id);
const setHidden = (el, val) => val ? el.setAttribute('hidden', '') : el.removeAttribute('hidden');

async function checkHealth() {
  const dot = $('statusDot');
  const label = $('statusLabel');
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    dot.className = 'badge-dot online';
    label.textContent = data.ai_enabled ? 'IA Online (Gemini)' : 'Online (Regras)';
  } catch {
    dot.className = 'badge-dot offline';
    label.textContent = 'Offline';
  }
}

function switchTab(tab) {
  state.activeTab = tab;
  ['text', 'file'].forEach((t) => {
    const btn = $(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`);
    const panel = $(`panel${t.charAt(0).toUpperCase() + t.slice(1)}`);
    const active = t === tab;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', String(active));
    panel.classList.toggle('active', active);
    setHidden(panel, !active);
  });
}

function updateCharCount() {
  const len = $('emailText').value.length;
  $('charCount').textContent = `${len.toLocaleString('pt-BR')} caractere${len !== 1 ? 's' : ''}`;
}

function loadSample(type) {
  switchTab('text');
  const ta = $('emailText');
  ta.value = SAMPLES[type] || '';
  ta.dispatchEvent(new Event('input'));
  ta.focus();
  showToast('💡 Exemplo carregado – clique em Analisar Email!', 'success');
}

function triggerFileInput() { $('fileInput').click(); }

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) setFile(file);
}

function handleDragOver(event) {
  event.preventDefault();
  $('dropZone').classList.add('drag-over');
}

function handleDragLeave() {
  $('dropZone').classList.remove('drag-over');
}

function handleDrop(event) {
  event.preventDefault();
  $('dropZone').classList.remove('drag-over');
  const file = event.dataTransfer.files[0];
  if (file) {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.txt') && !name.endsWith('.pdf')) {
      showToast('❌ Apenas arquivos .txt ou .pdf são aceitos.', 'error');
      return;
    }
    setFile(file);
  }
}

function setFile(file) {
  state.selectedFile = file;
  $('fileName').textContent = file.name;
  setHidden($('filePreview'), false);
  showToast(`📄 Arquivo "${file.name}" selecionado.`, 'success');
}

function removeFile(event) {
  event.stopPropagation();
  state.selectedFile = null;
  $('fileInput').value = '';
  setHidden($('filePreview'), true);
  showToast('🗑️ Arquivo removido.', '');
}

async function analyzeEmail() {
  const btn = $('analyzeBtn');
  const btnTxt = btn.querySelector('.btn-text');
  const btnLdr = btn.querySelector('.btn-loading');

  const isFile = state.activeTab === 'file';
  const text = $('emailText').value.trim();

  if (isFile && !state.selectedFile) {
    showToast('⚠️ Por favor, selecione um arquivo .txt ou .pdf.', 'error');
    return;
  }
  if (!isFile && text.length < 10) {
    showToast('⚠️ O email é muito curto. Insira pelo menos 10 caracteres.', 'error');
    $('emailText').focus();
    return;
  }

  btn.disabled = true;
  setHidden(btnTxt, true);
  setHidden(btnLdr, false);
  setHidden($('resultsPlaceholder'), false);
  setHidden($('resultsContent'), true);

  try {
    let res;
    if (isFile) {
      const formData = new FormData();
      formData.append('file', state.selectedFile);
      res = await fetch('/api/classify', { method: 'POST', body: formData });
    } else {
      res = await fetch('/api/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
    }

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Erro ${res.status}`);
    }

    state.lastResult = data;
    renderResults(data);

  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    console.error('Erro na análise:', err);
  } finally {
    btn.disabled = false;
    setHidden(btnTxt, false);
    setHidden(btnLdr, true);
  }
}

function renderResults(data) {
  const { category, confidence, reason, key_topics, priority, suggested_response, ai_powered, preprocessing } = data;

  const isProd = category === 'Produtivo';

  const badge = $('categoryBadge');
  badge.className = `category-badge ${isProd ? 'productive' : 'unproductive'}`;
  $('categoryIcon').textContent = isProd ? '✅' : '💬';
  $('categoryValue').textContent = category;

  const priorityColors = { Alta: '#ef4444', Média: '#f59e0b', Baixa: '#10b981' };
  $('priorityValue').textContent = priority || 'Média';
  $('priorityValue').style.color = priorityColors[priority] || '#f59e0b';

  $('aiValue').textContent = ai_powered ? '🤖 Gemini' : '⚙️ Regras';

  const pct = Math.round((confidence || 0) * 100);
  $('confidencePct').textContent = `${pct}%`;
  $('confidenceBar').setAttribute('aria-valuenow', pct);
  requestAnimationFrame(() => {
    $('confidenceFill').style.width = `${pct}%`;
  });

  $('reasonText').textContent = reason || '—';

  const topicsList = $('topicsList');
  topicsList.innerHTML = '';
  const topics = key_topics && key_topics.length > 0 ? key_topics : (preprocessing?.top_terms || []);
  if (topics.length > 0) {
    topics.slice(0, 10).forEach((t) => {
      const span = document.createElement('span');
      span.className = 'topic-tag';
      span.textContent = t;
      topicsList.appendChild(span);
    });
    setHidden($('topicsSection'), false);
  } else {
    setHidden($('topicsSection'), true);
  }

  if (preprocessing) {
    $('nlpChars').textContent = (preprocessing.original_length || 0).toLocaleString('pt-BR');
    $('nlpTokens').textContent = (preprocessing.token_count || 0).toLocaleString('pt-BR');
    $('nlpFiltered').textContent = (preprocessing.filtered_token_count || 0).toLocaleString('pt-BR');
  }

  $('responseBox').textContent = suggested_response || '—';

  setHidden($('resultsPlaceholder'), true);
  const content = $('resultsContent');
  setHidden(content, false);
  content.classList.remove('results-content-enter');
  void content.offsetWidth;
  content.classList.add('results-content-enter');

  if (window.innerWidth < 900) {
    $('resultsCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  showToast(`✨ Email classificado como ${category}!`, 'success');
}

async function copyResponse() {
  const text = $('responseBox').textContent;
  const btn = $('copyBtn');
  try {
    await navigator.clipboard.writeText(text);
    btn.classList.add('copied');
    btn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <path d="M2 7l4 4 6-6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Copiado!`;
    showToast('📋 Resposta copiada!', 'success');
    setTimeout(() => {
      btn.classList.remove('copied');
      btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <rect x="4" y="4" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
          <path d="M4 4V3a1 1 0 011-1h5a1 1 0 011 1v1" stroke="currentColor" stroke-width="1.4"/>
        </svg>
        Copiar`;
    }, 2500);
  } catch {
    showToast('❌ Falha ao copiar. Selecione o texto manualmente.', 'error');
  }
}

function resetAnalysis() {
  $('emailText').value = '';
  updateCharCount();
  removeFile({ stopPropagation: () => {} });
  switchTab('text');
  setHidden($('resultsPlaceholder'), false);
  setHidden($('resultsContent'), true);
  $('confidenceFill').style.width = '0%';
  state.lastResult = null;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

let toastTimer;
function showToast(message, type = '') {
  const toast = $('toast');
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast ${type} show`;
  toastTimer = setTimeout(() => { toast.classList.remove('show'); }, 3500);
}

document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  updateCharCount();

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      analyzeEmail();
    }
  });
});
