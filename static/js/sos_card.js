// 求救小卡（2026-11-17 回饋）：說不出口時，產生一張可以拿給信任的人看的小卡。
// 全部在這台裝置上完成：不呼叫任何 API、不儲存、不通知任何人；要不要拿給誰看由學生決定。
(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const PRESETS = [
    ["需要有人陪", "我現在心情很不好，需要有人陪我一下。"],
    ["想找你談", "我有一些事想找你談，可以給我一點時間嗎？"],
    ["說不出口", "我不知道怎麼開口，但我真的需要幫忙。"],
    ["先陪著我", "請先不要問太多，陪著我就好。"],
    ["帶我找老師", "可以陪我去找輔導老師嗎？我一個人不敢去。"],
  ];
  const FONT = '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", "Heiti TC", sans-serif';
  let lastOpener = null;

  function alias() {
    // studentAlias 來自 app.js；沒填暱稱時小卡不署名。
    const name = typeof studentAlias === "string" ? studentAlias.trim() : "";
    return name && name !== "匿名同學" ? name : "";
  }

  // 中文沒有空白可斷行：逐字量寬度換行，保留學生自己打的換行。
  function wrap(ctx, text, maxWidth, maxLines) {
    const lines = [];
    for (const paragraph of text.split(/\n/)) {
      let line = "";
      for (const ch of Array.from(paragraph)) {
        if (line && ctx.measureText(line + ch).width > maxWidth) {
          lines.push(line);
          line = ch;
        } else {
          line += ch;
        }
      }
      lines.push(line);
    }
    if (lines.length > maxLines) {
      lines.length = maxLines;
      lines[maxLines - 1] = lines[maxLines - 1].replace(/.$/u, "…");
    }
    return lines;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function cardText() {
    const text = (byId("sosText").value || "").trim() || PRESETS[0][1];
    const to = (byId("sosTo").value || "").trim();
    return { text, to, from: alias() };
  }

  function draw() {
    const canvas = byId("sosCanvas");
    const ctx = canvas && canvas.getContext && canvas.getContext("2d");
    if (!ctx) return;
    const W = canvas.width, H = canvas.height;
    const { text, to, from } = cardText();
    ctx.clearRect(0, 0, W, H);
    // 底色與卡片
    ctx.fillStyle = "#FDF6EC";
    ctx.fillRect(0, 0, W, H);
    roundRect(ctx, 36, 36, W - 72, H - 72, 44);
    ctx.fillStyle = "#FFFFFF";
    ctx.fill();
    ctx.lineWidth = 6;
    ctx.strokeStyle = "#D9735B";
    ctx.stroke();
    // 標題列
    roundRect(ctx, 36, 36, W - 72, 150, 44);
    ctx.save();
    ctx.clip();
    ctx.fillStyle = "#F7DDD5";
    ctx.fillRect(36, 36, W - 72, 150);
    ctx.restore();
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    ctx.fillStyle = "#8A3B28";
    ctx.font = `800 56px ${FONT}`;
    ctx.fillText("🙋 我需要幫忙", W / 2, 114);
    // 給誰
    let y = 250;
    ctx.textAlign = "left";
    if (to) {
      ctx.fillStyle = "#6B5B53";
      ctx.font = `600 34px ${FONT}`;
      ctx.fillText(`給 ${to}：`, 88, y);
      y += 70;
    } else {
      y += 10;
    }
    // 內文
    ctx.fillStyle = "#2F241F";
    ctx.font = `700 46px ${FONT}`;
    const lines = wrap(ctx, text, W - 176, 6);
    for (const line of lines) {
      ctx.fillText(line, 88, y);
      y += 68;
    }
    // 署名
    if (from) {
      ctx.textAlign = "right";
      ctx.fillStyle = "#6B5B53";
      ctx.font = `600 34px ${FONT}`;
      ctx.fillText(`— ${from}`, W - 88, Math.min(y + 20, H - 300));
      ctx.textAlign = "left";
    }
    // 給看到小卡的人的提醒
    const boxTop = H - 262;
    roundRect(ctx, 72, boxTop, W - 144, 178, 26);
    ctx.fillStyle = "#FFF8E6";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#F1C96B";
    ctx.stroke();
    ctx.fillStyle = "#6B4E0E";
    ctx.font = `700 28px ${FONT}`;
    ctx.fillText("看到這張卡的你，可以這樣做：", 100, boxTop + 40);
    ctx.font = `500 26px ${FONT}`;
    ctx.fillText("1. 先陪著我、聽我說，不用急著給建議", 100, boxTop + 84);
    ctx.fillText("2. 陪我找輔導老師，或一起打 1925／1995", 100, boxTop + 122);
    ctx.fillText("3. 如果我有立即危險，請幫我打 119", 100, boxTop + 160);
    // 頁尾
    ctx.textAlign = "center";
    ctx.fillStyle = "#9A8A80";
    ctx.font = `500 22px ${FONT}`;
    ctx.fillText("少年仔、安啦會客室 ‧ 求救小卡", W / 2, H - 58);
  }

  function plainText() {
    const { text, to, from } = cardText();
    return [
      "【我需要幫忙】",
      to ? `給 ${to}：` : "",
      text,
      from ? `— ${from}` : "",
      "",
      "看到這張卡的你，可以這樣做：",
      "1. 先陪著我、聽我說，不用急著給建議",
      "2. 陪我找輔導老師，或一起打 1925（安心專線）／1995（生命線）",
      "3. 如果我有立即危險，請幫我打 119",
    ].filter((line, i) => line || i === 4).join("\n");
  }

  function status(text) {
    const el = byId("sosStatus");
    if (el) el.textContent = text;
  }

  function toBlob() {
    return new Promise(resolve => {
      const canvas = byId("sosCanvas");
      if (canvas.toBlob) canvas.toBlob(resolve, "image/png");
      else resolve(null);
    });
  }

  async function download() {
    draw();
    const blob = await toBlob();
    const link = document.createElement("a");
    link.download = "求救小卡.png";
    if (blob) {
      link.href = URL.createObjectURL(blob);
      setTimeout(() => URL.revokeObjectURL(link.href), 2000);
    } else {
      link.href = byId("sosCanvas").toDataURL("image/png");
    }
    document.body.appendChild(link);
    link.click();
    link.remove();
    status("已存成圖片（手機請到「下載」或相簿找）。要不要傳、傳給誰都由你決定。");
  }

  async function copy() {
    const text = plainText();
    try {
      await navigator.clipboard.writeText(text);
      status("已複製文字，可以貼到 LINE 或訊息裡傳給信任的人。");
    } catch (_) {
      const area = byId("sosText");
      area.focus();
      area.select();
      status("沒辦法自動複製；已選取卡片上的話，請按 Ctrl+C 或長按複製。");
    }
  }

  async function share() {
    draw();
    const text = plainText();
    try {
      const blob = await toBlob();
      const file = blob && typeof File === "function" ? new File([blob], "求救小卡.png", { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], text });
      } else {
        await navigator.share({ text });
      }
      status("已開啟分享。");
    } catch (error) {
      if (error && error.name === "AbortError") return;  // 學生自己取消
      status("這台裝置沒辦法直接分享，可以改用「存成圖片」或「複製文字」。");
    }
  }

  function open(event) {
    const dialog = byId("sosDialog");
    if (!dialog) return;
    lastOpener = (event && event.currentTarget) || document.activeElement;
    if (!byId("sosText").value) byId("sosText").value = PRESETS[0][1];
    status("");
    if (typeof dialog.showModal === "function") {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    markPreset();
    draw();
    // 字型可能晚一點才載入：載好後重畫一次，避免第一次畫成預設字型。
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw).catch(() => {});
    byId("sosClose").focus();
  }

  function close() {
    const dialog = byId("sosDialog");
    if (!dialog) return;
    if (typeof dialog.close === "function" && dialog.open) dialog.close();
    else dialog.removeAttribute("open");
  }

  function markPreset() {
    const value = byId("sosText").value.trim();
    byId("sosPresets").querySelectorAll("button").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.text === value));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const dialog = byId("sosDialog");
    if (!dialog) return;
    const presets = byId("sosPresets");
    for (const [label, text] of PRESETS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "choice-chip";
      button.textContent = label;
      button.title = text;
      button.dataset.text = text;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => {
        byId("sosText").value = text;
        markPreset();
        draw();
      });
      presets.appendChild(button);
    }
    byId("sosCardButton")?.addEventListener("click", open);
    byId("sosClose").addEventListener("click", close);
    byId("sosText").addEventListener("input", () => { markPreset(); draw(); });
    byId("sosTo").addEventListener("input", draw);
    byId("sosDownload").addEventListener("click", download);
    byId("sosCopy").addEventListener("click", copy);
    if (typeof navigator.share === "function") {
      byId("sosShare").hidden = false;
      byId("sosShare").addEventListener("click", share);
    }
    dialog.addEventListener("click", event => { if (event.target === dialog) close(); });
    dialog.addEventListener("close", () => {
      if (lastOpener && document.contains(lastOpener)) lastOpener.focus();
      lastOpener = null;
    });
  });

  window.AnlaSosCard = { open, plainText };
})();
