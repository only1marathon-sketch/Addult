// ---------- Config ----------
// Paste your payment processor's hosted checkout links here (CCBill, Segpay, ...).
const CHECKOUT_URLS = { credits_50: "", credits_200: "", credits_1000: "" };
const CREDIT_METER_MAX = 50;

// ---------- Helpers ----------
const $ = (id) => document.getElementById(id);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

let token = store.get("token");
let me = null;
let authMode = "login";
let style = "";
let aspect = "square";
let chatHistory = [];
let images = []; // {id, src, prompt}
let reportTarget = null;

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? "Please check the form fields." : "Something went wrong.";
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return data;
}

function toast(text, type = "ok") {
  const t = document.createElement("div");
  t.className = `toast ${type}`; t.textContent = text;
  $("toasts").append(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, 3800);
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

// ---------- Screens ----------
function showScreen(name) {
  for (const id of ["auth", "verify", "studio"]) $(id).classList.toggle("hidden", id !== name);
}

async function refresh() {
  if (!token) return showScreen("auth");
  try {
    me = await api("/api/me");
    renderAccount();
    if (me.age_verified) { showScreen("studio"); loadStyles(); }
    else showScreen("verify");
  } catch (e) {
    logout(false);
    if (e.status === 403) toast(e.message, "error");
  }
}

function renderAccount() {
  $("userEmail").textContent = me.email;
  $("userAvatar").textContent = me.email[0].toUpperCase();
  $("creditCount").textContent = me.credits;
  $("creditMeter").style.width = `${Math.min(100, (me.credits / CREDIT_METER_MAX) * 100)}%`;
}

function logout(showToast = true) {
  token = null; me = null; store.del("token");
  chatHistory = []; images = [];
  renderImages(); resetChat();
  showScreen("auth");
  if (showToast) toast("Logged out");
}
document.querySelectorAll(".js-logout").forEach((b) => (b.onclick = () => logout()));

// ---------- Age gate ----------
if (store.get("gate_ok") === "1") $("gate").classList.add("hidden");
$("enter").onclick = () => { store.set("gate_ok", "1"); $("gate").classList.add("hidden"); };

// ---------- Auth ----------
document.querySelectorAll("#authSeg button").forEach((b) => {
  b.onclick = () => {
    authMode = b.dataset.mode;
    document.querySelectorAll("#authSeg button").forEach((x) => x.classList.toggle("on", x === b));
    document.querySelector(".signup-only").classList.toggle("hidden", authMode !== "signup");
    $("authSubmit").textContent = authMode === "signup" ? "Create account" : "Log in";
    $("password").autocomplete = authMode === "signup" ? "new-password" : "current-password";
  };
});

$("authForm").onsubmit = async (e) => {
  e.preventDefault();
  const btn = $("authSubmit"); btn.disabled = true;
  try {
    const creds = { email: $("email").value.trim(), password: $("password").value };
    if (authMode === "signup") {
      if (!$("dob").value) throw new Error("Please enter your date of birth.");
      if (!$("terms").checked) throw new Error("Please accept the terms to continue.");
      ({ token } = await api("/api/auth/register", { ...creds, date_of_birth: $("dob").value, accept_terms: true }));
      toast("Welcome! Your free credits are waiting.");
    } else {
      ({ token } = await api("/api/auth/login", creds));
    }
    store.set("token", token);
    await refresh();
  } catch (err) { toast(err.message, "error"); }
  btn.disabled = false;
};

// ---------- Verification ----------
$("startVerify").onclick = async () => {
  const btn = $("startVerify"); btn.disabled = true;
  try {
    const r = await api("/api/age-verification/start", {});
    if (r.redirect_url) { window.location.href = r.redirect_url; return; }
    toast("You're verified. Enjoy!");
    await refresh();
  } catch (err) { toast(err.message, "error"); }
  btn.disabled = false;
};

// ---------- Navigation ----------
function go(view) {
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("on", n.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${view}`));
  if (view === "chat") setTimeout(() => $("chatInput").focus(), 50);
}
document.querySelectorAll(".nav-item").forEach((n) => (n.onclick = () => go(n.dataset.view)));

// ---------- Styles & aspect ----------
async function loadStyles() {
  try {
    const { styles } = await api("/api/styles");
    const wrap = $("styleChips");
    wrap.innerHTML = "";
    for (const s of ["", ...styles]) {
      const c = el("button", "chip" + (s === style ? " on" : ""));
      c.textContent = s ? s.replace(/[-_]/g, " ") : "Natural";
      c.dataset.style = s;
      wrap.append(c);
    }
  } catch {}
}
$("styleChips").onclick = (e) => {
  const c = e.target.closest(".chip"); if (!c) return;
  style = c.dataset.style;
  $("styleChips").querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === c));
};
document.querySelectorAll("#aspectSeg button").forEach((b) => {
  b.onclick = () => {
    aspect = b.dataset.aspect;
    document.querySelectorAll("#aspectSeg button").forEach((x) => x.classList.toggle("on", x === b));
  };
});

// ---------- Image generation ----------
function tile(img) {
  const t = el("div", "tile");
  const i = new Image(); i.src = img.src; i.alt = img.prompt; i.loading = "lazy";
  const o = el("div", "overlay");
  o.innerHTML = `
    <a class="icon-btn" title="Download" download="velvet-ai-${img.id}.png" href="${img.src}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg></a>
    <button class="icon-btn" title="Report" data-report="${img.id}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 21V4h11l-1.5 4L16 12H5"/></svg></button>`;
  t.append(i, o);
  t.onclick = (e) => {
    if (e.target.closest("a")) return;
    const r = e.target.closest("[data-report]");
    if (r) { e.stopPropagation(); return openReport(img.id); }
    openLightbox(img);
  };
  return t;
}

function renderImages() {
  const latest = $("latest"), gallery = $("gallery");
  latest.querySelectorAll(".tile").forEach((n) => n.remove());
  gallery.innerHTML = "";
  images.slice(0, 8).forEach((img) => latest.append(tile(img)));
  images.forEach((img) => gallery.append(tile(img)));
  const none = images.length === 0 && !latest.querySelector(".skeleton");
  $("emptyImages").classList.toggle("hidden", !none);
  $("emptyGallery").classList.toggle("hidden", images.length > 0);
}

async function generate() {
  const prompt = $("prompt").value.trim();
  if (!prompt) { $("prompt").focus(); return toast("Describe what you'd like to see.", "error"); }
  const btn = $("genBtn");
  btn.disabled = true; btn.classList.add("loading"); btn.querySelector(".btn-label").textContent = "Creating";
  const sk = el("div", `skeleton ${aspect}`, "<span>Painting your scene…</span>");
  $("latest").prepend(sk); $("emptyImages").classList.add("hidden");
  try {
    const r = await api("/api/generate/image", {
      prompt, negative_prompt: $("negative").value.trim(), style: style || null, aspect,
    });
    images.unshift({ id: r.generation_id, src: `data:image/png;base64,${r.image_b64}`, prompt });
    me.credits = r.credits; renderAccount();
  } catch (err) {
    toast(err.message, "error");
    if (err.status === 402) openModal("buyModal");
  }
  sk.remove(); renderImages();
  btn.disabled = false; btn.classList.remove("loading"); btn.querySelector(".btn-label").textContent = "Generate";
}
$("genBtn").onclick = generate;
$("prompt").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) generate(); });

// ---------- Chat ----------
function resetChat() {
  chatHistory = [];
  $("chatLog").querySelectorAll(".msg").forEach((m) => m.remove());
  $("chatEmpty").classList.remove("hidden");
}
$("newChat").onclick = resetChat;

function addMsg(role, text) {
  $("chatEmpty").classList.add("hidden");
  const m = el("div", `msg ${role}`);
  if (role === "assistant") m.append(el("div", "persona-avatar sm", "N"));
  const b = el("div", "bubble"); b.textContent = text;
  m.append(b); $("chatLog").append(m);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
  return m;
}

async function sendChat(text) {
  text = (text ?? $("chatInput").value).trim();
  if (!text) return;
  $("chatInput").value = ""; autosize();
  addMsg("user", text);
  chatHistory.push({ role: "user", content: text });
  const typing = el("div", "msg assistant typing");
  typing.append(el("div", "persona-avatar sm", "N"), el("div", "bubble", "<i></i><i></i><i></i>"));
  $("chatLog").append(typing); $("chatLog").scrollTop = $("chatLog").scrollHeight;
  $("sendBtn").disabled = true;
  try {
    const r = await api("/api/chat", { messages: chatHistory.slice(-20) });
    typing.remove();
    chatHistory.push({ role: "assistant", content: r.reply });
    addMsg("assistant", r.reply);
  } catch (err) {
    typing.remove(); chatHistory.pop();
    toast(err.message, "error");
  }
  $("sendBtn").disabled = false; $("chatInput").focus();
}
$("chatForm").onsubmit = (e) => { e.preventDefault(); sendChat(); };
$("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
function autosize() { const t = $("chatInput"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 160) + "px"; }
$("chatInput").addEventListener("input", autosize);
document.querySelectorAll(".starter").forEach((s) => (s.onclick = () => sendChat(s.textContent)));

// ---------- Modals ----------
function openModal(id) { $(id).classList.remove("hidden"); }
function closeModals() { document.querySelectorAll(".modal").forEach((m) => m.classList.add("hidden")); }
document.querySelectorAll(".modal").forEach((m) => {
  m.addEventListener("click", (e) => { if (e.target === m || e.target.closest(".js-close")) closeModals(); });
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModals(); });

function openLightbox(img) {
  $("lbImg").src = img.src; $("lbPrompt").textContent = img.prompt;
  $("lbDownload").href = img.src; $("lbDownload").download = `velvet-ai-${img.id}.png`;
  $("lbReport").onclick = () => { closeModals(); openReport(img.id); };
  openModal("lightbox");
}

$("buyBtn").onclick = () => openModal("buyModal");
document.querySelectorAll(".pack").forEach((p) => {
  p.onclick = () => {
    const url = CHECKOUT_URLS[p.dataset.pack];
    if (!url) return toast("Payments aren't connected yet.", "error");
    const u = new URL(url); if (me) u.searchParams.set("user_id", me.id);
    window.location.href = u.toString();
  };
});

function openReport(id) { reportTarget = id; $("reportReason").value = ""; openModal("reportModal"); }
$("reportForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/api/report", { generation_id: reportTarget, reason: $("reportReason").value.trim() });
    closeModals(); toast("Thanks. Our safety team will review it.");
  } catch (err) { toast(err.message, "error"); }
};

// ---------- Boot ----------
renderImages();
refresh();
