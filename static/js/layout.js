// 介面版型切換＋投票（學生首頁）。
// 版型只改變「東西放在哪裡」，不刪除任何功能：被收起來的按鈕會搬到「☰ 更多」抽屜裡，
// 頁面上所有元素的 id 與事件都保持原樣；任何版型都固定顯示 1925／119 求助電話。
// 參考的開源專案（只參考版面配置概念，未使用其程式碼）：
//   focus ← mckaywrigley/chatbot-ui、vercel/ai-chatbot：單欄置中、工具收進側抽屜
//   rail  ← open-webui/open-webui、danny-avila/LibreChat：左側固定導覽欄＋右側對話
//   app   ← lobehub/lobe-chat：手機 App 式全螢幕對話＋底部分頁列
(function () {
  "use strict";
  var LAYOUTS = {
    classic: { name: "原版", icon: "🧩", ref: "目前上線的版本",
      desc: "對話在左、四張功能卡在右，上方列出全部按鈕。" },
    focus: { name: "極簡專注", icon: "🎯", ref: "參考 Chatbot UI / Vercel AI Chatbot",
      desc: "只留對話框，置中好閱讀；其他工具收進「☰ 更多」。" },
    rail: { name: "左側導覽", icon: "📚", ref: "參考 Open WebUI / LibreChat",
      desc: "左邊一條精簡工具欄，右邊大對話框；說明文字收起來。" },
    app: { name: "手機 App 風", icon: "📱", ref: "參考 Lobe Chat",
      desc: "整頁都是對話，底部分頁列切換檢核、喘口氣、求助。" }
  };
  var KEY = "anla_layout";
  var VOTER_KEY = "anla_ui_voter";
  var DEFAULT = "classic";
  var DRAWER_LAYOUTS = { focus: true, rail: true, app: true };
  var script = document.currentScript;
  var voteEnabled = !script || script.getAttribute("data-ui-vote") !== "0";

  function valid(name) { return Object.prototype.hasOwnProperty.call(LAYOUTS, name); }
  function readStore(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }
  function writeStore(key, value) { try { window.localStorage.setItem(key, value); } catch (e) { /* 不記憶也沒關係 */ } }

  function initial() {
    var fromUrl = null;
    try { fromUrl = new URLSearchParams(window.location.search).get("layout"); } catch (e) { /* 舊瀏覽器 */ }
    if (valid(fromUrl)) return fromUrl;
    var saved = readStore(KEY);
    return valid(saved) ? saved : DEFAULT;
  }

  // 在 <head> 就先標上版型，避免畫面先閃一下原版。
  document.documentElement.setAttribute("data-layout", initial());

  // ---------- 抽屜：把收起來的元素搬進去，換回原版時放回原位 ----------
  var moved = [];   // { node, marker }：從頁面搬進抽屜的原生元素
  var temps = [];   // 抽屜裡臨時建立的標題與分組，換版型時直接移除
  var drawer, drawerBody, menuButton, sos, tabbar;

  function park(node, target) {
    if (!node || !target || node.parentNode === target) return;
    var marker = document.createComment("layout-slot");
    node.parentNode.insertBefore(marker, node);
    target.appendChild(node);
    moved.push({ node: node, marker: marker });
  }

  function restoreAll() {
    while (moved.length) {
      var item = moved.pop();
      if (item.marker.parentNode) {
        item.marker.parentNode.insertBefore(item.node, item.marker);
        item.marker.parentNode.removeChild(item.marker);
      }
    }
    while (temps.length) {
      var temp = temps.pop();
      if (temp.parentNode) temp.parentNode.removeChild(temp);
    }
  }

  function openDrawer(scrollTarget) {
    if (!drawer) return;
    drawer.hidden = false;
    document.body.classList.add("layout-drawer-open");
    menuButton && menuButton.setAttribute("aria-expanded", "true");
    if (scrollTarget) {
      var el = drawer.querySelector(scrollTarget);
      if (el) {
        var fold = el.closest("details");
        if (fold) fold.open = true;
        el.scrollIntoView({ block: "start" });
      }
    } else {
      drawerBody.scrollTop = 0;
    }
    var closeBtn = drawer.querySelector(".layout-drawer-close");
    closeBtn && closeBtn.focus();
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.hidden = true;
    document.body.classList.remove("layout-drawer-open");
    menuButton && menuButton.setAttribute("aria-expanded", "false");
  }

  function buildChrome() {
    var navbar = document.querySelector(".student-navbar");
    var tools = document.querySelector(".student-header-tools");
    if (!navbar || !tools) return false;

    menuButton = document.createElement("button");
    menuButton.type = "button";
    menuButton.className = "layout-menu-button";
    menuButton.setAttribute("aria-controls", "layoutDrawer");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.textContent = "☰ 更多";
    menuButton.addEventListener("click", function () { openDrawer(); });

    sos = document.createElement("div");
    sos.className = "layout-sos";
    sos.setAttribute("aria-label", "求助電話");
    sos.innerHTML = '<a href="tel:1925">📞 1925</a><a href="tel:119">🚨 119</a>';

    var bar = document.createElement("div");
    bar.className = "layout-header-bar";
    bar.appendChild(sos);
    bar.appendChild(menuButton);
    tools.appendChild(bar);

    drawer = document.createElement("aside");
    drawer.id = "layoutDrawer";
    drawer.className = "layout-drawer";
    drawer.hidden = true;
    drawer.setAttribute("aria-label", "更多功能");
    drawer.innerHTML = '<div class="layout-drawer-backdrop" data-close></div>' +
      '<div class="layout-drawer-panel" role="dialog" aria-modal="true" aria-labelledby="layoutDrawerTitle">' +
      '<div class="layout-drawer-head"><h2 id="layoutDrawerTitle">更多功能</h2>' +
      '<button type="button" class="layout-drawer-close" data-close aria-label="關閉">×</button></div>' +
      '<div class="layout-drawer-body"></div></div>';
    drawerBody = drawer.querySelector(".layout-drawer-body");
    drawer.addEventListener("click", function (event) {
      if (event.target.closest("[data-close]")) closeDrawer();
      // 從抽屜開啟對話框或執行動作後，順手把抽屜關掉，避免蓋住對話框。
      else if (event.target.closest("button[onclick], button[data-open-checkin], #hideButton, #jokeButton, #breathButton")) {
        window.setTimeout(closeDrawer, 0);
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && drawer && !drawer.hidden) closeDrawer();
    });
    document.body.appendChild(drawer);

    tabbar = document.createElement("nav");
    tabbar.className = "layout-tabbar";
    tabbar.setAttribute("aria-label", "主要功能");
    tabbar.innerHTML =
      '<button type="button" data-tab="chat">💬<span>聊天</span></button>' +
      '<button type="button" data-tab="check">🔋<span>檢核</span></button>' +
      '<button type="button" data-tab="relax">🌿<span>喘口氣</span></button>' +
      '<button type="button" data-tab="help" class="layout-tab-help">🙋<span>求助</span></button>' +
      '<button type="button" data-tab="more">☰<span>更多</span></button>';
    tabbar.addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-tab]");
      if (!btn) return;
      var tab = btn.getAttribute("data-tab");
      if (tab === "chat") { closeDrawer(); var input = document.getElementById("userInput"); input && input.focus(); }
      else if (tab === "check") { closeDrawer(); var open = document.querySelector(".sidebar-panel [data-open-checkin], [data-open-checkin]"); open && open.click(); }
      else if (tab === "relax") openDrawer("#relaxFold");
      else if (tab === "help") openDrawer("#emergencyFold");
      else openDrawer();
    });
    document.body.appendChild(tabbar);
    return true;
  }

  function arrange(layout) {
    restoreAll();
    closeDrawer();
    if (!drawerBody || !DRAWER_LAYOUTS[layout]) return;
    var keepInHeader = { headerReferralButton: true, headerSchoolReferralButton: true };
    var section = function (title) {
      var h = document.createElement("h3");
      h.className = "layout-drawer-section";
      h.textContent = title;
      temps.push(h);
      return h;
    };
    // 抽屜內容：先放求助相關，再放工具與設定。
    if (layout !== "rail") {
      park(document.querySelector(".sidebar-panel"), drawerBody);
    }
    var links = document.querySelector(".student-header-tools .nav-links");
    if (links) {
      var group = document.createElement("div");
      group.className = "layout-drawer-links";
      temps.push(group);
      var title = section("常用");
      drawerBody.insertBefore(group, drawerBody.firstChild);
      drawerBody.insertBefore(title, group);
      Array.prototype.slice.call(links.children).forEach(function (child) {
        if (!keepInHeader[child.id]) park(child, group);
      });
    }
    var meta = document.querySelector(".student-header-meta");
    if (meta) {
      drawerBody.appendChild(section("個人與設定"));
      park(meta, drawerBody);
    }
  }

  function setLayout(layout, remember) {
    if (!valid(layout)) layout = DEFAULT;
    document.documentElement.setAttribute("data-layout", layout);
    arrange(layout);
    if (remember !== false) writeStore(KEY, layout);
    renderVotePanel();
    return layout;
  }

  // ---------- 投票面板 ----------
  var votePanel, voteToggle, voteState = { counts: {}, total: 0, mine: null, loaded: false, error: "" };

  function voterId() {
    var id = readStore(VOTER_KEY);
    if (!id || !/^[A-Za-z0-9_-]{16,64}$/.test(id)) {
      var bytes = new Uint8Array(18);
      (window.crypto || window.msCrypto).getRandomValues(bytes);
      id = Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
      writeStore(VOTER_KEY, id);
    }
    return id;
  }

  function api(method, body) {
    return fetch("/api/ui-vote", {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": window.ANLA_CSRF_TOKEN || "", "X-UI-Voter": voterId() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || "投票暫時無法使用");
        return data;
      });
    });
  }

  function loadVotes() {
    api("GET").then(function (data) {
      voteState = { counts: data.counts, total: data.total, mine: data.mine, loaded: true, error: "" };
      renderVotePanel();
    }).catch(function (err) { voteState.error = err.message; renderVotePanel(); });
  }

  function vote(layout) {
    voteState.error = "";
    api("POST", { layout: layout }).then(function (data) {
      voteState = { counts: data.counts, total: data.total, mine: data.mine, loaded: true, error: "" };
      renderVotePanel("已投給「" + LAYOUTS[layout].name + "」，謝謝！想改票可以再按別的。");
    }).catch(function (err) { voteState.error = err.message; renderVotePanel(); });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderVotePanel(message) {
    if (!votePanel) return;
    var current = document.documentElement.getAttribute("data-layout");
    var max = 0;
    Object.keys(LAYOUTS).forEach(function (k) { max = Math.max(max, voteState.counts[k] || 0); });
    var html = '<div class="ui-vote-head"><h2 id="uiVoteTitle">🗳️ 選出新版面</h2>' +
      '<button type="button" class="ui-vote-close" data-vote-close aria-label="收起投票">×</button></div>' +
      '<p class="ui-vote-intro">先按「試用」看看，覺得最好用再按「投這個」。每台裝置一票，可以改票。</p><ol class="ui-vote-list">';
    Object.keys(LAYOUTS).forEach(function (k) {
      var info = LAYOUTS[k];
      var n = voteState.counts[k] || 0;
      var pct = voteState.total ? Math.round(n * 100 / voteState.total) : 0;
      var leading = voteState.total && n === max && n > 0;
      html += '<li class="ui-vote-item' + (k === current ? " is-current" : "") + (voteState.mine === k ? " is-mine" : "") + '">' +
        '<div class="ui-vote-row"><span class="ui-vote-name">' + info.icon + " " + escapeHtml(info.name) +
        (leading ? ' <span class="ui-vote-lead">領先</span>' : "") + '</span>' +
        '<span class="ui-vote-count">' + n + " 票" + (voteState.total ? "（" + pct + "%）" : "") + '</span></div>' +
        '<div class="ui-vote-ref">' + escapeHtml(info.ref) + '</div>' +
        '<div class="ui-vote-desc">' + escapeHtml(info.desc) + '</div>' +
        '<div class="ui-vote-bar" aria-hidden="true"><span style="width:' + pct + '%"></span></div>' +
        '<div class="ui-vote-actions">' +
        '<button type="button" data-preview="' + k + '"' + (k === current ? ' aria-pressed="true" disabled' : "") + '>' +
        (k === current ? "✓ 正在看" : "👀 試用") + '</button>' +
        '<button type="button" data-vote="' + k + '" class="ui-vote-cast"' + (voteState.mine === k ? ' aria-pressed="true"' : "") + '>' +
        (voteState.mine === k ? "★ 我的票" : "投這個") + '</button></div></li>';
    });
    html += '</ol><p class="ui-vote-status" role="status" aria-live="polite">' +
      escapeHtml(voteState.error || message || (voteState.loaded ? "目前共 " + voteState.total + " 票" : "讀取票數中…")) + '</p>';
    votePanel.innerHTML = html;
  }

  function buildVote() {
    voteToggle = document.createElement("button");
    voteToggle.type = "button";
    voteToggle.className = "ui-vote-toggle";
    voteToggle.setAttribute("aria-controls", "uiVotePanel");
    voteToggle.setAttribute("aria-expanded", "false");
    voteToggle.textContent = voteEnabled ? "🗳️ 版面投票" : "🖼️ 切換版面";

    votePanel = document.createElement("section");
    votePanel.id = "uiVotePanel";
    votePanel.className = "ui-vote-panel" + (voteEnabled ? "" : " vote-off");
    votePanel.setAttribute("aria-labelledby", "uiVoteTitle");
    votePanel.hidden = true;

    voteToggle.addEventListener("click", function () {
      var open = votePanel.hidden;
      votePanel.hidden = !open;
      voteToggle.setAttribute("aria-expanded", String(open));
      if (open && voteEnabled) loadVotes();
    });
    votePanel.addEventListener("click", function (event) {
      var preview = event.target.closest("[data-preview]");
      var cast = event.target.closest("[data-vote]");
      if (event.target.closest("[data-vote-close]")) {
        votePanel.hidden = true;
        voteToggle.setAttribute("aria-expanded", "false");
        voteToggle.focus();
      } else if (preview) setLayout(preview.getAttribute("data-preview"));
      else if (cast && voteEnabled) vote(cast.getAttribute("data-vote"));
    });
    document.body.appendChild(voteToggle);
    document.body.appendChild(votePanel);
    if (!voteEnabled) voteState = { counts: {}, total: 0, mine: null, loaded: true, error: "" };
    renderVotePanel();
  }

  window.AnlaLayout = {
    layouts: LAYOUTS,
    set: setLayout,
    current: function () { return document.documentElement.getAttribute("data-layout") || DEFAULT; },
    openDrawer: openDrawer,
    closeDrawer: closeDrawer
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.body.classList.contains("student-page")) return;
    buildChrome();
    buildVote();
    setLayout(window.AnlaLayout.current(), false);
  });
})();
