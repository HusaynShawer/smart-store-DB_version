/* متجر زكي — front-end (vanilla JS, no build step). */
"use strict";

const API = "/api";
const $ = (sel) => document.querySelector(sel);

const state = {
  sessionId: localStorage.getItem("zaki_session") || crypto.randomUUID(),
  selectedProduct: null,
  pendingAction: null,
  recording: false,
  attachedImage: null,
};

localStorage.setItem("zaki_session", state.sessionId);

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    $("#panel-chat").classList.toggle("hidden", btn.dataset.tab !== "chat");
    $("#panel-admin").classList.toggle("hidden", btn.dataset.tab !== "admin");
    if (btn.dataset.tab === "admin") renderAdmin("products");
  });
});

/* ── Chat helpers ─────────────────────────────────────────────────────────── */
function addMessage(text, role = "bot") {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = text; // contains safe links / product markup
  wrap.appendChild(bubble);
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return bubble;
}

function addProducts(products) {
  const container = document.createElement("div");
  container.className = "products";
  products.forEach((p) => {
    const card = document.createElement("div");
    card.className = "product-card";
    const store = p.shop_name ? `<div class="p-store">🏪 ${p.shop_name}${p.shop_distance ? ` (${p.shop_distance} كم)` : ""}</div>` : "";
    card.innerHTML = `
      <img src="${p.image || ""}" alt="" loading="lazy">
      <div class="p-title">${p.title}</div>
      <div class="p-price">$${p.price}</div>
      ${store}
      <button class="buy-btn" data-id="${p.id}">اشتري ده</button>`;
    card.querySelector(".buy-btn").addEventListener("click", () => openOrderModal(p));
    container.appendChild(card);
  });
  const wrap = document.createElement("div");
  wrap.className = "msg bot";
  wrap.appendChild(container);
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

function showTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg bot"; wrap.id = "typing";
  wrap.innerHTML = '<div class="bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>';
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}
function hideTyping() { $("#typing")?.remove(); }

async function apiCall(path, options) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function buildChatOptions(extra = {}) {
  return {
    message: extra.message,
    session_id: state.sessionId,
    customer_name: $("#nameInput").value?.trim() || null,
    customer_phone: $("#phoneInput").value?.trim() || null,
    selected_product: state.selectedProduct,
    ...extra.passthrough,
  };
}

/* ── Send flows ───────────────────────────────────────────────────────────── */
async function sendText() {
  const input = $("#textInput");
  const text = input.value.trim();
  if (!text && !state.attachedImage) return;
  input.value = "";
  addMessage(escapeHtml(text || (state.attachedImage ? "🖼️ صورة" : "")), "user");

  if (state.attachedImage) {
    const img = state.attachedImage;
    clearAttachedImage();
    return sendImageChat(img, text);
  }

  if (state.selectedProduct && /هشتري|hشتري|اشتري|شراء|اطلب/i.test(text)) {
    // User confirms the picked product by typing.
    return sendChat(text);
  }
  sendChat(text);
}

async function sendImageChat(file, text) {
  showTyping();
  const form = new FormData();
  form.append("image", file);
  form.append("session_id", state.sessionId);
  if (text) form.append("message", text);
  const name = $("#nameInput").value?.trim();
  const phone = $("#phoneInput").value?.trim();
  if (name) form.append("customer_name", name);
  if (phone) form.append("customer_phone", phone);
  if (state.selectedProduct) form.append("selected_product", JSON.stringify(state.selectedProduct));
  try {
    renderReply(await apiCall("/image/chat", { method: "POST", body: form }));
  } catch (err) {
    hideTyping();
    addMessage("تعذر تحليل الصورة: " + escapeHtml(err.message), "bot");
  }
}

/* ── Image attach (preview, sent on Send) ───────────────────────────────── */
function renderImagePreview(file) {
  const box = $("#imgPreview");
  box.innerHTML = "";
  const img = document.createElement("img");
  img.src = URL.createObjectURL(file);
  const name = document.createElement("span");
  name.className = "ip-name";
  name.textContent = file.name;
  const remove = document.createElement("button");
  remove.className = "ip-remove";
  remove.title = "إزالة";
  remove.textContent = "✕";
  remove.addEventListener("click", clearAttachedImage);
  box.append(img, name, remove);
  box.classList.remove("hidden");
}

function clearAttachedImage() {
  state.attachedImage = null;
  const box = $("#imgPreview");
  box.classList.add("hidden");
  box.innerHTML = "";
  $("#imageInput").value = "";
}

$("#imageInput").addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  e.target.value = "";
  state.attachedImage = file;
  renderImagePreview(file);
});

async function sendChat(message) {
  showTyping();
  try {
    const data = await apiCall("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        buildChatOptions({ message, passthrough: { latitude: null, longitude: null, location_text: null } })
      ),
    });
    renderReply(data);
  } catch (err) {
    hideTyping();
    addMessage("حدث خطأ: " + escapeHtml(err.message), "bot");
  }
}

function renderReply(data) {
  hideTyping();
  addMessage(data.response.replace(/\n/g, "<br>"), "bot");
  if (data.products?.length) addProducts(data.products);
  if (data.order_confirmation) {
    state.selectedProduct = null;
    const c = data.order_confirmation;
    addMessage(`✅ تم تأكيد الطلب #${c.order_id}`, "bot");
  }
}

/* ── Image upload ─────────────────────────────────────────────────────────── */

/* ── Voice recording ──────────────────────────────────────────────────────── */
let recorder = null;
$("#micBtn").addEventListener("click", async () => {
  if (state.recording) { recorder?.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: "audio/webm" });
      addMessage("🎤 تسجيل صوت", "user");
      showTyping();
      const form = new FormData();
      form.append("audio", blob, "voice.webm");
      form.append("session_id", state.sessionId);
      const name = $("#nameInput").value?.trim();
      const phone = $("#phoneInput").value?.trim();
      if (name) form.append("customer_name", name);
      if (phone) form.append("customer_phone", phone);
      if (state.selectedProduct) form.append("selected_product", JSON.stringify(state.selectedProduct));
      try {
        renderReply(await apiCall("/voice/chat", { method: "POST", body: form }));
      } catch (err) {
        hideTyping();
        addMessage("تعذر تحويل الصوت: " + escapeHtml(err.message), "bot");
      }
      state.recording = false;
      $("#micBtn").textContent = "🎤";
    };
    recorder.start();
    state.recording = true;
    $("#micBtn").textContent = "⏹️";
  } catch {
    addMessage("مشكلة في الوصول للميكروفون", "bot");
  }
});

/* ── Order modal ──────────────────────────────────────────────────────────── */
function openOrderModal(product) {
  state.selectedProduct = product;
  $("#modalBody").innerHTML = `
    <div>${escapeHtml(product.title)} — <b>$${product.price}</b></div>
    <input id="mName" type="text" placeholder="اسمك" value="${escapeAttr($("#nameInput").value || "")}">
    <input id="mPhone" type="tel" placeholder="رقم تليفونك" value="${escapeAttr($("#phoneInput").value || "")}">
    <button class="confirm-btn">أكّد الطلب</button>`;
  $("#modal").classList.remove("hidden");
  $("#modalBody .confirm-btn").onclick = async () => {
    const name = $("#mName").value.trim();
    const phone = $("#mPhone").value.trim();
    if (!name || !phone) { alert("اكتب اسمك ورقم تليفونك أولاً"); return; }
    $("#nameInput").value = name;
    $("#phoneInput").value = phone;
    $("#modal").classList.add("hidden");
    addMessage(`طلب: ${product.title}`, "user");
    await sendChat("هشتري ده — يلا نكمل الطلب");
  };
}
$("#modalClose").addEventListener("click", () => {
  $("#modal").classList.add("hidden");
});

$("#sendBtn").addEventListener("click", sendText);
$("#textInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });

/* ── Admin ────────────────────────────────────────────────────────────────── */
document.querySelectorAll(".admin-nav").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".admin-nav").forEach((b) => b.classList.toggle("active", b === btn));
    renderAdmin(btn.dataset.entity);
  });
});

async function renderAdmin(entity) {
  const box = $("#admin-content");
  box.innerHTML = '<div class="loading">جاري التحميل...</div>';
  try {
    if (entity === "products") box.innerHTML = await adminProducts();
    if (entity === "stores") box.innerHTML = await adminStores();
    if (entity === "orders") box.innerHTML = await adminOrders();
    if (entity === "sessions") box.innerHTML = await adminSessions();
  } catch (err) {
    box.innerHTML = `<div class="loading">خطأ: ${escapeHtml(err.message)}</div>`;
  }
}

async function adminProducts() {
  const { items } = await apiCall("/admin/products?limit=50");
  return `
    <h3>المنتجات (${items.length})</h3>
    <div class="add-form">
      <input id="pTitle" placeholder="الاسم"><input id="pPrice" type="number" placeholder="السعر">
      <input id="pCat" placeholder="الفئة"><button data-add="product">إضافة</button>
    </div>
    <table class="admin-table"><tr><th>#</th><th>الاسم</th><th>الفئة</th><th>السعر</th></tr>
      ${items.map((p) => `<tr><td>${p.id}</td><td>${escapeHtml(p.title)}</td><td>${escapeHtml(p.category)}</td><td>$${p.price}</td></tr>`).join("")}
    </table>`;
}

async function adminStores() {
  const { items } = await apiCall("/admin/stores?limit=60");
  return `
    <h3>المتاجر (${items.length})</h3>
    <table class="admin-table"><tr><th>#</th><th>الاسم</th><th>المحافظة</th><th>الهاتف</th></tr>
      ${items.map((s) => `<tr><td>${s.id}</td><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.governorate)}</td><td>${escapeHtml(s.phone || "")}</td></tr>`).join("")}
    </table>`;
}

async function adminOrders() {
  const { items } = await apiCall("/admin/orders?limit=50");
  return `
    <h3>الطلبات (${items.length})</h3>
    <table class="admin-table"><tr><th>#</th><th>المنتج</th><th>العميل</th><th>الهاتف</th><th>الحالة</th></tr>
      ${items.map((o) => `<tr><td>${o.id}</td><td>${escapeHtml(o.product_name)}</td><td>${escapeHtml(o.customer_name)}</td><td>${escapeHtml(o.customer_phone)}</td>
      <td><span class="badge ${escapeAttr(o.status)}">${escapeHtml(o.status)}</span></td></tr>`).join("")}
    </table>`;
}

async function adminSessions() {
  const { items } = await apiCall("/admin/sessions?limit=50");
  return `
    <h3>المحادثات (${items.length})</h3>
    <table class="admin-table"><tr><th>id</th><th>الرسائل</th><th>آخر تحديث</th></tr>
      ${items.map((s) => `<tr><td>${escapeHtml(s.session_id)}</td><td>${s.msg_count}</td><td>${s.updated_at || ""}</td></tr>`).join("")}
    </table>`;
}

/* modal add — event delegation */
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-add='product']");
  if (!btn) return;
  const title = $("#pTitle").value.trim();
  const price = parseFloat($("#pPrice").value || 0);
  const category = $("#pCat").value.trim();
  if (!title || !category) return;
  apiCall("/admin/products", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, price, category, description: "", image: "", rating: { rate: 0, count: 0 } }),
  }).then(() => renderAdmin("products")).catch((err) => alert(err.message));
});

/* ── utils ────────────────────────────────────────────────────────────────── */
function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
function escapeAttr(text) {
  return escapeHtml(text);
}