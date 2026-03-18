let arquivoSelecionado = null;

function selecionarArquivo(event) {
  const arquivo = event.target.files[0];
  if (!arquivo) return;
  arquivoSelecionado = arquivo;
  document.getElementById("labelArquivo").textContent = arquivo.name;
  document.querySelector(".upload-label").classList.add("selecionado");
  document.getElementById("emailTexto").value = "";
}

async function analisar() {
  const texto = document.getElementById("emailTexto").value.trim();
  const btn = document.getElementById("btnAnalisar");

  if (!arquivoSelecionado && texto.length < 10) {
    mostrarToast("⚠️ Insira o texto do email ou selecione um arquivo.");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Analisando…";

  try {
    let resposta;

    if (arquivoSelecionado) {
      const form = new FormData();
      form.append("arquivo", arquivoSelecionado);
      resposta = await fetch("/classificar", { method: "POST", body: form });
    } else {
      resposta = await fetch("/classificar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
    }

    const dados = await resposta.json();

    if (!resposta.ok) {
      mostrarToast("❌ " + (dados.erro || "Erro ao analisar."));
      return;
    }

    salvarHistorico(dados, texto);
    mostrarResultado(dados);
  } catch (e) {
    mostrarToast("❌ Erro de conexão com o servidor.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Analisar Email";
  }
}

function mostrarResultado(dados) {
  const isProd = dados.categoria === "Produtivo";

  const badge = document.getElementById("badgeCategoria");
  badge.textContent = isProd ? "✅ Produtivo" : "💬 Improdutivo";
  badge.className = "badge " + (isProd ? "produtivo" : "improdutivo");

  document.getElementById("motivo").textContent = dados.motivo;
  document.getElementById("resposta").textContent = dados.resposta;
  document.getElementById("motor").textContent = "⚙ Motor: " + dados.motor;

  document.getElementById("inputCard").hidden = true;
  document.getElementById("historicoSection").hidden = true;
  document.getElementById("resultadoCard").hidden = false;
}

async function copiar() {
  const texto = document.getElementById("resposta").textContent;
  await navigator.clipboard.writeText(texto);
  mostrarToast("📋 Resposta copiada!");
}

function novo() {
  document.getElementById("emailTexto").value = "";
  document.getElementById("arquivoInput").value = "";
  document.getElementById("labelArquivo").textContent = "Selecionar arquivo";
  document.querySelector(".upload-label").classList.remove("selecionado");
  arquivoSelecionado = null;
  document.getElementById("inputCard").hidden = false;
  document.getElementById("resultadoCard").hidden = true;
  renderizarHistorico();
}

async function verificarStatus() {
  const el = document.getElementById("statusIA");
  try {
    const res = await fetch("/status");
    const dados = await res.json();
    if (dados.gemini) {
      el.textContent = "🟢 Gemini AI ativo";
      el.className = "status-ia online";
    } else {
      el.textContent = "🟡 Modo regras";
      el.className = "status-ia regras";
    }
  } catch {
    el.textContent = "🔴 Offline";
    el.className = "status-ia offline";
  }
}

function salvarHistorico(dados, texto) {
  const historico = JSON.parse(
    localStorage.getItem("mailai_historico") || "[]",
  );
  const trecho =
    texto.slice(0, 60).replace(/\n/g, " ") ||
    arquivoSelecionado?.name ||
    "Arquivo";

  historico.unshift({
    categoria: dados.categoria,
    trecho: trecho,
    hora: new Date().toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    }),
  });

  if (historico.length > 5) historico.pop();
  localStorage.setItem("mailai_historico", JSON.stringify(historico));
}

function renderizarHistorico() {
  const historico = JSON.parse(
    localStorage.getItem("mailai_historico") || "[]",
  );
  const section = document.getElementById("historicoSection");
  const lista = document.getElementById("historicoLista");

  if (historico.length === 0) {
    section.hidden = true;
    return;
  }

  lista.innerHTML = "";
  historico.forEach((item) => {
    const li = document.createElement("li");
    const isProd = item.categoria === "Produtivo";
    li.innerHTML = `
      <span class="hist-badge ${isProd ? "produtivo" : "improdutivo"}">
        ${isProd ? "Produtivo" : "Improdutivo"}
      </span>
      <span class="hist-trecho">${item.trecho}…</span>
      <span class="hist-hora">${item.hora}</span>
    `;
    lista.appendChild(li);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  verificarStatus();
  renderizarHistorico();
});

let toastTimer;
function mostrarToast(msg) {
  const toast = document.getElementById("toast");
  clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3000);
}
