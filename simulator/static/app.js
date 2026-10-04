// ===========================================================================
// VXPEngine Frame Simulator — frontend logic.
// Gọi các endpoint của standalone_simulator.py để hiện panel SDK kiểu
// Extensions, đồng thời điều khiển hoạt ảnh khung máy (multi-tap, cursor).
// ===========================================================================

const els = {
  list:        document.getElementById("extension-list"),
  summary:     document.getElementById("summary"),
  search:      document.getElementById("search"),
  filter:      document.getElementById("filter"),
  updateInfo:  document.getElementById("update-info"),
  logTail:     document.getElementById("log-tail"),
  btnRecheck:  document.getElementById("btn-recheck"),
  btnInstallAll: document.getElementById("btn-install-all"),
  btnCheck:    document.getElementById("btn-check-updates"),
  multitan:    document.getElementById("multitan-hint"),
  subject:     null, // chèn vào lúc render
  toast:       document.getElementById("toast"),
};

let cache = { requirements: [], summary: null };

const FILTER_MODES = {
  all: () => true,
  installed: r => r.satisfied,
  missing: r => !r.satisfied,
  installable: r => !r.satisfied && r.installable,
};

const STATE_LABELS = {
  installed: "Đã cài đặt",
  auto:      "Có thể cài tự động",
  manual:    "Cần làm thủ công",
};

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function apiGet(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} → HTTP ${res.status}`);
  return res.json();
}

async function apiPost(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(`POST ${path} → HTTP ${res.status}`);
    err.payload = data;
    throw err;
  }
  return data;
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

let toastTimer = null;
function toast(message, kind = "ok", timeout = 2400) {
  els.toast.textContent = message;
  els.toast.className = "toast " + kind;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.hidden = true; }, timeout);
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderSummary(summary) {
  if (!summary) {
    els.summary.textContent = "Đang kiểm tra…";
    return;
  }
  els.summary.textContent = summary.headline;
}

function makeRow(requirement) {
  const row = document.createElement("div");
  row.className = "ext-row";
  row.dataset.state = requirement.state;
  row.dataset.key = requirement.key;
  row.dataset.name = requirement.name.toLowerCase();
  row.dataset.hint = requirement.hint.toLowerCase();

  const icon = document.createElement("div");
  icon.className = "ext-icon";
  icon.innerHTML = `<span class="ic">${iconForRequirement(requirement.key)}</span>`;
  row.appendChild(icon);

  const main = document.createElement("div");
  main.className = "ext-main";
  main.innerHTML = `
    <div class="name">
      ${escapeHtml(requirement.name)}
      ${requirement.optional ? '<span class="tag">tuỳ chọn</span>' : ""}
    </div>
    <div class="hint" title="${escapeHtml(requirement.hint)}">
      ${escapeHtml(requirement.hint || "—")}
    </div>
  `;
  row.appendChild(main);

  const badge = document.createElement("div");
  badge.className = "ext-badge";
  badge.dataset.state = requirement.state;
  badge.textContent = requirement.state_label;
  row.appendChild(badge);

  const actionWrap = document.createElement("label");
  actionWrap.style.display = "inline-flex";
  actionWrap.style.alignItems = "center";
  actionWrap.style.gap = "8px";

  if (!requirement.satisfied && requirement.installable) {
    const button = document.createElement("button");
    button.className = "ext-action";
    button.textContent = "Cài đặt";
    button.addEventListener("click", () => install([requirement.key]));
    actionWrap.appendChild(button);
  } else if (requirement.satisfied) {
    const span = document.createElement("span");
    span.className = "ext-action ok-state";
    span.style.padding = "6px 12px";
    span.style.borderRadius = "6px";
    span.style.border = "1px solid var(--ok)";
    span.style.background = "rgba(63,178,127,0.10)";
    span.style.color = "var(--ok)";
    span.textContent = "✓ Đã có";
    actionWrap.appendChild(span);
  } else {
    const span = document.createElement("span");
    span.className = "ext-action";
    span.style.opacity = "0.55";
    span.textContent = "Thủ công";
    actionWrap.appendChild(span);
  }
  row.appendChild(actionWrap);
  return row;
}

function renderList(requirements) {
  els.list.replaceChildren();
  for (const requirement of requirements) {
    els.list.appendChild(makeRow(requirement));
  }
  applyFilter();
}

function applyFilter() {
  const needle = els.search.value.trim().toLowerCase();
  const mode = els.filter.value;
  const predicate = FILTER_MODES[mode] || FILTER_MODES.all;
  let shown = 0;
  for (const row of els.list.children) {
    const key = row.dataset.key;
    const requirement = cache.requirements.find(r => r.key === key);
    if (!requirement) continue;
    const matchesSearch = !needle
      || row.dataset.name.includes(needle)
      || row.dataset.hint.includes(needle)
      || key.includes(needle);
    const visible = predicate(requirement) && matchesSearch;
    row.style.display = visible ? "" : "none";
    if (visible) shown += 1;
  }
  if (shown === 0) {
    if (!document.getElementById("empty-row")) {
      const empty = document.createElement("div");
      empty.id = "empty-row";
      empty.style.padding = "20px";
      empty.style.color = "var(--txt-2)";
      empty.style.textAlign = "center";
      empty.textContent = "Không có thành phần nào khớp bộ lọc.";
      els.list.appendChild(empty);
    }
  } else {
    const empty = document.getElementById("empty-row");
    if (empty) empty.remove();
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Icon Font-Awesome-ish glyph (chỉ là emoji/ký tự hình học thường — không cần
// font MDL2/Fluent cũng hiển thị được). Trùng khớp với key trong icon map.
function iconForRequirement(key) {
  switch (key) {
    case "cmake":        return "⚙";
    case "vs2022":       return "🪟";
    case "bash":         return "▶_";
    case "arm_gcc":      return "⌬";
    case "python_deps":  return "🐍";
    case "mre_sdk":      return "▦";
    case "tiny_mresdk":  return "✎";
    case "vxpemu":       return "▢";
    case "vxpemu":       return "🖥";
    case "signing_key":  return "🔑";
    default:             return "◫";
  }
}

// ---------------------------------------------------------------------------
// Environment fetch
// ---------------------------------------------------------------------------

async function loadEnvironment() {
  try {
    const payload = await apiGet("/api/environment");
    cache.requirements = payload.requirements || [];
    cache.summary = payload.summary;
    renderSummary(payload.summary);
    renderList(cache.requirements);
  } catch (error) {
    toast("Không tải được danh sách môi trường: " + error.message, "err");
    renderSummary({
      headline:
        "Không truy cập được app.environment_setup — chạy script từ thư mục repo VXPEngine.",
      total: 0, installed: 0, missing: 0, installable_auto: 0, manual: 0,
    });
  }
}

async function install(keys) {
  if (!keys || !keys.length) return;
  els.btnInstallAll.disabled = true;
  els.btnRecheck.disabled = true;
  toast(`Đang cài ${keys.length} thành phần…`, "ok", 30000);
  try {
    const result = await apiPost("/api/install", { keys });
    if (result.log && result.log.length) {
      els.logTail.hidden = false;
      els.logTail.textContent = result.log.join("\n");
      els.logTail.scrollTop = els.logTail.scrollHeight;
    }
    cache.requirements = result.requirements || cache.requirements;
    cache.summary = result.summary;
    renderSummary(result.summary);
    renderList(cache.requirements);
    if (result.ok) {
      toast(`Đã cài xong ${keys.length} thành phần — bấm Check for updates.`, "ok", 4500);
    } else if (result.failed && result.failed.length) {
      toast(`Lỗi: ${result.failed.join(", ")}. Xem nhật ký.`, "err", 6000);
    }
  } catch (error) {
    toast("Lỗi cài đặt: " + (error.message || "không xác định"), "err", 6000);
  } finally {
    els.btnInstallAll.disabled = false;
    els.btnRecheck.disabled = false;
  }
}

async function checkUpdates() {
  els.btnCheck.disabled = true;
  els.btnCheck.textContent = "Đang kiểm tra…";
  try {
    const result = await apiPost("/api/check-updates", {});
    if (result.status === "up_to_date") {
      els.updateInfo.className = "update-info up-to-date";
      els.updateInfo.innerHTML = `
        <span class="glyph">✓</span>
        <div>
          <b style="color: var(--ok)">Không cần cập nhật.</b><br>
          <span>${escapeHtml(result.message)}</span>
        </div>
      `;
      toast(result.message, "ok", 4000);
    } else {
      const names = result.missing.map(r => r.name).join(", ");
      els.updateInfo.className = "update-info update-available";
      els.updateInfo.innerHTML = `
        <span class="glyph">⚠</span>
        <div>
          <b>Có ${result.missing.length} thành phần cần cập nhật:</b>
          ${names}.<br>
          <span>${escapeHtml(result.message)}</span>
        </div>
      `;
      toast(result.message, "err", 5000);
    }
    els.updateInfo.dataset.checkedAt = result.checked_at || "";
  } catch (error) {
    toast("Không kiểm tra được cập nhật: " + error.message, "err");
  } finally {
    els.btnCheck.disabled = false;
    els.btnCheck.innerHTML = '<span class="ic">↻</span> Check for updates';
  }
}

// ---------------------------------------------------------------------------
// Wiring: extension list interactions
// ---------------------------------------------------------------------------

els.btnRecheck.addEventListener("click", loadEnvironment);
els.btnInstallAll.addEventListener("click", async () => {
  const keys = cache.requirements
    .filter(r => !r.satisfied && r.installable)
    .map(r => r.key);
  if (!keys.length) {
    toast("Không có thành phần nào có thể cài tự động.", "err");
    return;
  }
  await install(keys);
});
els.btnCheck.addEventListener("click", checkUpdates);
els.search.addEventListener("input", applyFilter);
els.filter.addEventListener("change", applyFilter);

// ---------------------------------------------------------------------------
// Multi-tap animation + cursor blink  (purely cosmetic for the simulator)
// ---------------------------------------------------------------------------

const LETTERS = {
  "1": ".,?!1",
  "2": "abc",
  "3": "def",
  "4": "ghi",
  "5": "jkl",
  "6": "mno",
  "7": "pqrs",
  "8": "tuv",
  "9": "wxyz",
  "0": " ",
  "*": "+",
  "#": "#",
};

const IDLE_HINT = "Multi-tan:&nbsp;<b>2</b>=a·b·c &nbsp; <b>3</b>=d·e·f &nbsp; " +
                  "<b>7</b>=p·q·r·s &nbsp; <b>0</b>=space";

let tapKey = "";
let tapCount = 0;
let tapTimer = null;

const subjectEl = document.querySelector(".subject");
const caretEl = document.querySelector(".caret");

function enterLetter(letter) {
  // Nếu subject chưa có "G" thì đặt "G", nếu rồi thì nối thêm theo vị trí.
  const current = subjectEl.textContent || "";
  // Bỏ các dấu "_" mặc định và thay bằng chữ vừa nhập.
  const underscores = current.replace(/[A-Za-z+ ]/g, "").length;
  const text = current.replace(/[_]/g, "");
  const newText = (text + letter).slice(0, 6);
  let formatted = "";
  for (let i = 0; i < newText.length; i++) {
    formatted += newText[i];
    if (i < newText.length - 1) formatted += "_";
  }
  while (formatted.length < current.length && current.length <= 7) {
    formatted += "_";
  }
  subjectEl.textContent = formatted;
  // Đảm bảo con trỏ luôn ở cuối — không nhảy lung tung khi bấm phím khác.
  if (caretEl && caretEl.parentNode) {
    caretEl.parentNode.appendChild(caretEl);
  }
}

function flashHint(key, letter, position, total) {
  els.multitan.innerHTML = `
    <span class="chosen-key">${key}</span>
    <span class="arrow"> → </span>
    <span class="chosen-letter">${letter === " " ? "space" : letter}</span>
    <span class="letter-info">letter ${position}/${total}</span>
  `;
}

function resetHint() {
  els.multitan.innerHTML = IDLE_HINT;
  tapKey = "";
  tapCount = 0;
}

document.querySelectorAll(".k.phone").forEach((button) => {
  button.addEventListener("click", () => {
    const ch = button.dataset.char;
    if (ch === undefined) return;
    const letters = LETTERS[ch] || "";
    if (tapKey === ch) tapCount += 1;
    else { tapKey = ch; tapCount = 1; }
    const letter = letters[(tapCount - 1) % letters.length];
    flashHint(ch, letter, tapCount > letters.length ? tapCount - letters.length : tapCount, letters.length);
    enterLetter(letter);
    clearTimeout(tapTimer);
    tapTimer = setTimeout(resetHint, 1200);
    // Animation lún phím — visual feedback.
    button.animate(
      [{ transform: "translateY(0)" }, { transform: "translateY(1px)" }, { transform: "translateY(0)" }],
      { duration: 120, easing: "ease-out" }
    );
  });
});

document.querySelectorAll(".k.nav, .k.soft, .k.tall").forEach((button) => {
  button.addEventListener("click", () => {
    button.animate(
      [{ transform: "translateY(0)" }, { transform: "translateY(1px)" }, { transform: "translateY(0)" }],
      { duration: 120, easing: "ease-out" }
    );
    // Cụm điều hướng: reset multi-tap như VXPEmu thật, không nhập chữ.
    resetHint();
  });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

loadEnvironment().then(() => {
  // Sau khi danh sách sẵn sàng, tự động chạy Check for updates một lần.
  checkUpdates();
});
