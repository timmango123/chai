// 2026-10-31 流程圖：開場心情選擇、對話中的 BSRS-5、紅燈四個按鈕與「找真人聊聊」、一鍵隱藏小遊戲、背景音樂、笑話。
// 這些都只在這台裝置上顯示；心情選擇本身不會提高燈號，也不會送到工作臺。
window.AnlaFlow = (() => {
  const byId = id => document.getElementById(id);
  const post = (url, body) => fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRF-Token": window.ANLA_CSRF_TOKEN},
    body: JSON.stringify(body),
  }).then(async res => ({ok: res.ok, data: await res.json().catch(() => ({}))}));

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function chip(label, onClick, className = "choice-chip") {
    const b = el("button", label, className);
    b.type = "button";
    b.addEventListener("click", onClick);
    return b;
  }

  function scrollToEnd() {
    const chat = byId("chatMessages");
    if (chat) chat.scrollTop = chat.scrollHeight;
  }

  // ---------- 開場心情（流程圖「你好嗎？今天心情如何？」） ----------
  // Flow chart: a mood, then how strong it is (1–5).
  const MOODS = [["😃", "開心"], ["😊", "還不錯"], ["🙂", "普通"], ["😟", "焦慮"], ["😡", "生氣"],
                 ["😢", "難過"], ["😞", "低落"]];

  function moodPicker() {
    if (byId("moodPicker") || typeof appendMessage !== "function") return;
    const bubble = appendMessage("ai", "你好嗎？今天心情如何？點一個最接近的就好：");
    const box = bubble.closest(".message");
    box.id = "moodPicker";
    const row = el("div", "", "mood-row mood-picker");
    const strength = el("div", "", "mood-strength-row");
    strength.hidden = true;
    MOODS.forEach(([emoji, label]) => {
      const b = chip(`${emoji} ${label}`, () => {
        row.querySelectorAll(".mood-chip").forEach(other => other.setAttribute("aria-pressed", String(other === b)));
        askStrength(strength, emoji, label);
      }, "mood-chip");
      b.setAttribute("aria-pressed", "false");
      row.appendChild(b);
    });
    bubble.append(row, strength);
    scrollToEnd();
  }

  function askStrength(strength, emoji, label) {
    strength.replaceChildren(el("p", `「${label}」大概有多強烈？`, "mood-strength-label"),
                             el("span", "1 一點點", "mood-scale-end"));
    for (let n = 1; n <= 5; n++) {
      const b = chip(String(n), () => {
        byId("moodPicker")?.remove();
        byId("userInput").value = `我今天的心情：${emoji} ${label}（程度 ${n}/5）`;
        sendMessage();
      }, "mood-chip");
      b.setAttribute("aria-label", `程度 ${n}，滿分 5`);
      strength.appendChild(b);
    }
    strength.appendChild(el("span", "5 非常強烈", "mood-scale-end"));
    strength.hidden = false;
    strength.querySelector("button")?.focus();
    scrollToEnd();
  }

  // ---------- 對話中的 BSRS-5（計畫書流程 5：橙燈時融入對話；流程圖分支 B） ----------
  const ITEMS = [
    ["sleep", "這一星期（包括今天），睡眠有沒有困難？像是難以入睡、容易醒或太早醒。"],
    ["anxiety", "這一星期，會不會覺得緊張或不安？"],
    ["anger", "這一星期，會不會很容易苦惱或動怒？"],
    ["depression", "這一星期，會不會覺得憂鬱、心情低落？"],
    ["inferiority", "這一星期，會不會覺得自己比不上別人？"],
    ["suicide", "最後一題比較直接，想認真問你：這一星期，有沒有出現自殺的想法？"],
  ];
  const LEVELS = ["完全沒有", "輕微", "中等", "厲害", "非常厲害"];
  let checking = false;

  function askOne(question) {
    return new Promise(resolve => {
      const bubble = appendMessage("ai", question);
      const row = el("div", "", "choice-chips chat-check-chips");
      LEVELS.forEach((label, score) => row.appendChild(chip(label, () => done(score, label))));
      row.appendChild(chip("先不要", () => done(null, "先不要"), "choice-chip chip-quiet"));
      bubble.appendChild(row);
      scrollToEnd();
      function done(score, label) {
        row.querySelectorAll("button").forEach(b => { b.disabled = true; });
        appendMessage("user", label);
        resolve(score);
      }
    });
  }

  async function startCheck() {
    if (checking) return;
    checking = true;
    try {
      appendMessage("ai", "好，我會一題一題問，選最接近這一星期的就好，沒有對錯，也可以隨時按「先不要」。");
      const answers = {};
      for (const [key, question] of ITEMS) {
        const score = await askOne(question);
        if (score === null) {
          appendMessage("ai", "好，我們先停在這裡，不用勉強。想到什麼都可以繼續跟我說。");
          return;
        }
        answers[key] = score;
      }
      const {ok, data} = await post("/api/assessment", {bsrs5: answers, category: "對話中的身心檢核"});
      if (!ok) throw new Error(data.error || "暫時無法整理結果，你可以繼續聊，需要時直接撥 1925。");
      const bubble = appendMessage("ai", data.result?.text || "謝謝你回答完。");
      if (data.help_draft && !data.show_urgent_help) {
        bubble.appendChild(el("p", "想找輔導老師聊聊的話，這是可以修改後自己傳出去的字條（還沒有寄出）：", "chat-check-note"));
        const area = el("textarea", "", "choice-text");
        area.rows = 5;
        area.value = data.help_draft;
        bubble.appendChild(area);
      }
      window.AnlaNextSteps?.update(data);
      if (data.result?.ask_safety) byId("userInput").placeholder = "現在安全嗎？想說什麼都可以在這裡打…";
      scrollToEnd();
    } catch (error) {
      appendMessage("ai", error.message);
    } finally {
      checking = false;
    }
  }

  function offerCheck(bubble) {
    if (!bubble || checking) return;
    const box = el("div", "", "choice-chips chat-check-offer");
    box.appendChild(el("p", "想用幾個小問題，幫你看看這一星期的狀況嗎？大概一分鐘。", "chat-check-note"));
    box.appendChild(chip("好，問我吧", () => { box.remove(); startCheck(); }));
    box.appendChild(chip("先不要", () => box.remove(), "choice-chip chip-quiet"));
    bubble.appendChild(box);
  }

  // ---------- 紅燈四個按鈕（流程圖紅色狀態） ----------
  // 生命線文字協談：衛福部公告平日 13:00–17:00、18:00–01:00；生命線官網公告 2026/10/4 起週六日夜間也有。
  const LIFELINE_LINE = "https://page.line.me/093wgvxu";
  const LIFELINE_SOURCE = "https://www.life1995.org.tw/";

  function lifelineOpen(now) {
    const day = now.getDay(), hour = now.getHours();
    const weekday = d => d >= 1 && d <= 5;
    if (hour < 1) return weekday((day + 6) % 7);           // 00:00–01:00 belongs to the previous evening
    return weekday(day) && ((hour >= 13 && hour < 17) || hour >= 18);
  }

  function phone(number, label) {
    const a = el("a", `📞 ${number} ${label}`, "btn-hotline");
    a.href = `tel:${number.replace(/[^0-9]/g, "")}`;
    return a;
  }

  function link(text, href) {
    const a = el("a", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  function telLink(r) {
    const a = el("a", String(r.phone));
    a.href = `tel:${String(r.phone).split(/[#/]/)[0].replace(/[^0-9]/g, "")}`;
    return a;
  }

  function resourceList(items) {
    const list = el("ul", "", "urgent-action-list");
    items.forEach(r => {
      const item = el("li", `${r.name}：`);
      item.appendChild(telLink(r));
      list.appendChild(item);
    });
    return list;
  }

  // 按鈕一：校內、校外輔導與醫療資源，依學生登錄的鄉鎮排序。
  async function showResources(box) {
    box.replaceChildren(el("p", "現在就能打的電話：", "urgent-action-title"));
    const row = el("div", "", "urgent-action-phones");
    [["119", "緊急救護"], ["110", "報案"], ["1925", "安心專線（24 小時）"], ["1995", "生命線（24 小時）"],
     ["113", "保護專線（24 小時）"], ["1980", "張老師"]].forEach(([n, l]) => row.appendChild(phone(n, l)));
    box.appendChild(row);
    box.appendChild(el("p", "🏫 校內資源", "urgent-action-title"));
    box.appendChild(el("p", "學校輔導室：上課時間可以直接走進去，或請導師、信任的老師陪你去。不知道怎麼開口，可以按「📝 幫我整理狀況」做一張小卡帶著。"));
    try {
      const state = await (await fetch("/api/chat/state", {cache: "no-store"})).json();
      const township = state.student_profile?.township || "南投市";
      const data = await (await fetch(`/api/resources?township=${encodeURIComponent(township)}`)).json();
      const all = data.resources || [];
      const near = r => (r.township === township || (r.suggested_townships || []).includes(township) ? 0 : 1);
      const pick = test => all.filter(r => test(r.category || "")).sort((a, b) => near(a) - near(b));
      const school = pick(c => c.includes("校園輔導"));
      if (school.length) box.appendChild(resourceList(school.slice(0, 1)));
      const counsel = pick(c => c.includes("心衛中心") || c.includes("心理及聯合") || c.includes("協談"));
      box.appendChild(el("p", `🤝 校外輔導與諮商（${township}附近）`, "urgent-action-title"));
      box.appendChild(resourceList(counsel.slice(0, 4)));
      const medical = pick(c => c.includes("醫院") || c.includes("身心科") || c.includes("衛生所"));
      box.appendChild(el("p", "🏥 醫療資源", "urgent-action-title"));
      box.appendChild(resourceList(medical.slice(0, 4)));
      box.appendChild(link("看全部南投資源", "/resources"));
    } catch (_) { /* the phones above are enough */ }
  }

  // 按鈕四：21:00 前直接打開生命線 LINE 文字協談；21:00 後先陪你緩一下（小遊戲／笑話／預約專業資源）。
  function isLate(now) {
    return now.getHours() >= 21 || now.getHours() < 6;
  }

  function showFindPerson(box) {
    const now = new Date();
    const late = isLate(now);
    box.replaceChildren();
    if (!late) {
      box.appendChild(el("p", "幫你打開生命線的 LINE 文字協談，可以直接打字跟真人聊 💬", "urgent-action-title"));
      const opened = window.open(LIFELINE_LINE, "_blank", "noopener");
      const again = el("p", "");
      again.append(opened ? "如果沒有跳出來，" : "瀏覽器擋住了新視窗，", link("點這裡打開生命線 LINE", LIFELINE_LINE), "。");
      box.appendChild(again);
      box.appendChild(el("p", "想用講的也可以，這些電話都有真人：", "urgent-action-title"));
      const row = el("div", "", "urgent-action-phones");
      row.appendChild(phone("1995", "生命線"));
      row.appendChild(phone("1925", "安心專線（24 小時）"));
      row.appendChild(phone("1980", "張老師"));
      box.appendChild(row);
      const src = el("p", "", "school-referral-hint");
      src.append("生命線文字協談的服務時間以", link("生命線官網", LIFELINE_SOURCE), "公告為準。");
      box.appendChild(src);
      return;
    }
    box.appendChild(el("p", "已經晚上 9 點多了，生命線的文字協談可能已經休息。你願意先讓我陪你緩一下嗎？", "urgent-action-title"));
    const choices = el("div", "", "choice-chips");
    choices.appendChild(chip("🎮 玩一下小遊戲", () => openGame(false)));
    choices.appendChild(chip("😄 聽個笑話", tellJoke));
    choices.appendChild(chip("📅 預約專業資源", () => showBooking(box)));
    box.appendChild(choices);
    box.appendChild(el("p", "如果真的很難受、想現在就跟人說話，這兩支電話 24 小時都有真人接：", "urgent-action-title"));
    const row = el("div", "", "urgent-action-phones");
    row.appendChild(phone("1925", "安心專線（24 小時）"));
    row.appendChild(phone("1995", "生命線（24 小時）"));
    box.appendChild(row);
  }

  // 南投縣心理諮商預約單：學生在畫面上填好、複製，再自己打電話或交給輔導室；網站不會代為送出。
  const BOOKING_CENTERS = [["南投區社區心理衛生中心", "049-2202662"], ["埔里區社區心理衛生中心", "049-2911925"],
                           ["竹山區社區心理衛生中心", "049-2631925"]];

  function showBooking(box) {
    if (box.querySelector(".urgent-booking")) {
      box.querySelector(".urgent-booking").scrollIntoView({block: "nearest"});
      return;
    }
    const card = el("div", "", "urgent-booking");
    card.appendChild(el("h4", "📅 南投縣心理諮商預約單", "booking-title"));
    card.appendChild(el("p", "南投縣社區心理衛生中心提供免費心理諮商（一段 4 次、每次約 50 分鐘）。先把下面填一填，上班時間打電話時照著念就好；也可以交給學校輔導室請老師幫你轉介。"));
    const form = el("div", "", "booking-form");
    const fields = {};
    [["name", "怎麼稱呼你（暱稱也可以）", "text"], ["age", "年級／年齡", "text"],
     ["time", "方便接電話或去諮商的時間", "text"], ["topic", "想談的事情（寫幾個字就好）", "textarea"]].forEach(([key, label, type]) => {
      const id = `booking_${key}`;
      const caption = el("label", label);
      caption.htmlFor = id;
      const input = document.createElement(type === "textarea" ? "textarea" : "input");
      input.id = id;
      if (type === "textarea") input.rows = 2; else input.type = "text";
      input.maxLength = 200;
      form.append(caption, input);
      fields[key] = input;
    });
    const centerLabel = el("label", "想預約的中心");
    centerLabel.htmlFor = "booking_center";
    const center = document.createElement("select");
    center.id = "booking_center";
    BOOKING_CENTERS.forEach(([n, p]) => center.appendChild(new Option(`${n}（${p}）`, `${n}（${p}）`)));
    form.append(centerLabel, center);
    card.appendChild(form);
    const copy = chip("複製預約單", async () => {
      const text = ["【南投縣心理諮商預約單】", `稱呼：${fields.name.value.trim() || "（未填）"}`,
                    `年級／年齡：${fields.age.value.trim() || "（未填）"}`, `方便的時間：${fields.time.value.trim() || "（未填）"}`,
                    `想談的事情：${fields.topic.value.trim() || "（未填）"}`, `預約中心：${center.value}`].join("\n");
      try {
        await navigator.clipboard.writeText(text);
        copy.textContent = "已複製 ✔";
      } catch (_) {
        copy.textContent = "無法自動複製，請手動抄下";
      }
    });
    card.appendChild(copy);
    const row = el("div", "", "urgent-action-phones");
    BOOKING_CENTERS.forEach(([n, p]) => row.appendChild(phone(p, n.replace("社區心理衛生中心", ""))));
    card.appendChild(row);
    const src = el("p", "", "school-referral-hint");
    src.append("資料來源：", link("南投縣政府衛生局〈我要心理諮商〉", "https://www.ntshb.gov.tw/counseling/index?Parser=99,5,74,42"),
               "。這張單只存在你的畫面上，網站不會替你送出。");
    card.appendChild(src);
    box.appendChild(card);
    fields.name.focus();
  }

  // The note is shown inside the panel: the panel covers the whole screen, so a note added to the chat behind it
  // looked like the button did nothing (2026-10-31 user report).
  async function showNote(box) {
    box.replaceChildren(el("p", "正在幫你整理…", "urgent-action-title"));
    const {ok, data} = await post("/api/generate-draft", {target: "輔導老師"}).catch(() => ({ok: false, data: {}}));
    if (!ok || !data.draft) {
      box.replaceChildren(el("p", data.error || "小卡暫時無法產生；需要時可以直接撥 1925。"));
      return;
    }
    box.replaceChildren(el("p", "這是可以拿給學校輔導老師的求助小卡，可以先改成你自己的話（還沒有寄出）：", "urgent-action-title"));
    const area = el("textarea", "", "choice-text");
    area.rows = 6;
    area.value = data.draft;
    area.setAttribute("aria-label", "給輔導老師的求助小卡");
    const copy = chip("複製小卡", async () => {
      try {
        await navigator.clipboard.writeText(area.value);
        copy.textContent = "已複製";
      } catch (_) {
        area.focus();
        area.select();
      }
    });
    box.append(area, copy,
               el("p", "要不要給、給誰都由你決定。如果現在有立即危險，請先撥 119 或 1925，不用等小卡。", "school-referral-hint"));
    area.focus();
  }

  function urgentActions() {
    const host = byId("urgentActions");
    if (!host || host.childElementCount) return;
    const box = el("div", "", "urgent-action-box");
    const buttons = el("div", "", "urgent-action-buttons");
    // 2026-11-08 四個按鈕改用貼圖（static/stickers），排列跟原圖一樣：找真人聊聊、幫我整理狀況／我需要幫助、我很安全。
    const sticker = (label, file, onClick) => {
      const b = chip("", onClick, "urgent-action urgent-sticker");
      b.setAttribute("aria-label", label);
      b.title = label;
      const img = el("img");
      img.src = `/static/stickers/${file}.webp`;
      img.alt = label;
      img.width = 360;
      img.height = 315;
      b.appendChild(img);
      return b;
    };
    buttons.append(
      sticker("找真人聊聊", "find-person", () => showFindPerson(box)),
      sticker("幫我整理狀況", "make-note", () => showNote(box)),
      sticker("我需要幫助", "need-help", () => showResources(box)),
      sticker("我很安全", "safe", () => {
        // 回到對話：仍保留高風險觀察（伺服器的燈號不會因此降低），求助電話列縮小保留，但不再自動跳出四個按鈕。
        window.AnlaNextSteps?.stayCompact?.();
        byId("keepTalkingButton")?.click();
        const input = byId("userInput");
        input.value = "我現在是安全的，只是需要有人陪我聊聊";
        sendMessage();
      }));
    host.append(buttons, box);
  }

  // ---------- 一鍵隱藏（益智小遊戲）、背景音樂、笑話 ----------
  let tiles = [];

  function shuffled() {
    // Random legal moves from the solved board, so the puzzle can always be solved.
    let board = [1, 2, 3, 4, 5, 6, 7, 8, 0];
    for (let i = 0; i < 120; i++) {
      const z = board.indexOf(0), moves = neighbours(z);
      const pick = moves[Math.floor(Math.random() * moves.length)];
      [board[z], board[pick]] = [board[pick], board[z]];
    }
    return board;
  }

  function neighbours(i) {
    const r = Math.floor(i / 3), c = i % 3, out = [];
    if (r > 0) out.push(i - 3);
    if (r < 2) out.push(i + 3);
    if (c > 0) out.push(i - 1);
    if (c < 2) out.push(i + 1);
    return out;
  }

  // 遊戲中的打氣話（流程圖：遊戲過程要給滿滿的情緒價值）。一鍵隱藏時不顯示，避免被旁人看出來。
  const CHEERS = [
    "你很專心耶，慢慢推就好 👍", "這一步很聰明！", "不用急，卡住也沒關係，換個方向試試 🌱",
    "你願意先讓自己喘口氣，真的很棒。", "越來越接近了，我在旁邊幫你加油！", "手感來了喔 ✨",
    "每推一格都是前進，就跟你一樣。", "你比你以為的還要厲害。", "休息一下也可以，我會一直在這裡。",
  ];
  let moves = 0, cheerHidden = false;

  function cheer(solved) {
    const box = byId("puzzleCheer");
    if (!box || cheerHidden) return;
    if (solved) {
      box.textContent = `🎉 完成了！只用了 ${moves} 步。你真的很棒，願意陪自己度過這段時間的你，也很了不起。`;
    } else if (moves === 1) {
      box.textContent = "好，開始了！慢慢來，沒有時間限制 😊";
    } else if (moves % 6 === 0) {
      box.textContent = CHEERS[Math.floor(Math.random() * CHEERS.length)];
    }
  }

  function drawGame() {
    const grid = byId("puzzleGrid");
    grid.replaceChildren();
    tiles.forEach((n, i) => {
      const t = chip(n ? String(n) : "", () => {
        const z = tiles.indexOf(0);
        if (!neighbours(z).includes(i)) return;
        [tiles[z], tiles[i]] = [tiles[i], tiles[z]];
        moves += 1;
        drawGame();
      }, n ? "puzzle-tile" : "puzzle-tile puzzle-empty");
      t.disabled = !n;
      grid.appendChild(t);
    });
    const solved = tiles.join(",") === "1,2,3,4,5,6,7,8,0";
    byId("puzzleStatus").textContent = solved ? "完成了！要再玩一次嗎？" : "把數字推回 1 到 8 的順序。";
    cheer(solved);
  }

  function newGame() {
    tiles = shuffled();
    moves = 0;
    const box = byId("puzzleCheer");
    if (box) box.textContent = cheerHidden ? "" : "謝謝你願意先陪自己一下。這局慢慢玩，玩完再回來聊也可以 💛";
    drawGame();
  }

  function openGame(hidden) {
    const overlay = byId("puzzleOverlay");
    cheerHidden = Boolean(hidden);
    newGame();
    overlay.hidden = false;
    overlay.dataset.hidden = hidden ? "true" : "";
    document.title = hidden ? "數字推推樂" : document.title;
    if (typeof stopSpeech === "function") stopSpeech();
    byId("puzzleBack").focus();
  }

  const realTitle = document.title;
  function closeGame() {
    byId("puzzleOverlay").hidden = true;
    document.title = realTitle;
    byId("userInput")?.focus();
  }

  let audio = null;
  function toggleMusic() {
    const button = byId("musicToggle");
    if (audio) {
      audio.master.gain.setTargetAtTime(0, audio.ctx.currentTime, 0.4);
      const old = audio;
      setTimeout(() => old.ctx.close(), 1500);
      audio = null;
      button.textContent = "🌊 白噪音";
      button.setAttribute("aria-pressed", "false");
      return;
    }
    // 平靜的白噪音（2026-11-08 回饋：音樂改平靜一點）：在本機產生柔和的棕噪音，經低通濾波，
    // 音量像海浪一樣每 10 秒緩慢起伏。不下載任何音檔。
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const seconds = 4, buffer = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < data.length; i++) {
      last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02;   // brown noise: soft, low rumble
      data[i] = last * 3.5;
    }
    // Fade the loop seam so it never clicks.
    const fade = Math.floor(ctx.sampleRate * 0.05);
    for (let i = 0; i < fade; i++) {
      const k = i / fade;
      data[i] = data[i] * k + data[data.length - fade + i] * (1 - k);
    }
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.loopEnd = seconds - 0.05;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 900;
    const wave = ctx.createGain();
    wave.gain.value = 0.75;
    const lfo = ctx.createOscillator(), depth = ctx.createGain();
    lfo.frequency.value = 0.1;                                    // one slow swell every 10 seconds
    depth.gain.value = 0.25;
    lfo.connect(depth).connect(wave.gain);
    const master = ctx.createGain();
    master.gain.value = 0;
    source.connect(filter).connect(wave).connect(master).connect(ctx.destination);
    master.gain.setTargetAtTime(0.35, ctx.currentTime, 1.5);
    source.start();
    lfo.start();
    audio = {ctx, master};
    button.textContent = "🌊 白噪音：開";
    button.setAttribute("aria-pressed", "true");
  }

  // ---------- 4-7-8 呼吸（放在「喘口氣」工具區；不離開對話頁） ----------
  const BREATH = [["吸氣", 4, "用鼻子慢慢吸氣"], ["停住", 7, "輕輕停住，不用憋太用力"], ["吐氣", 8, "用嘴巴慢慢把氣吐乾淨"]];
  let breathTimer = null;

  function openBreath() {
    const overlay = byId("breathOverlay");
    if (!overlay) return;
    overlay.hidden = false;
    if (typeof stopSpeech === "function") stopSpeech();
    runBreath();
    byId("breathClose").focus();
  }

  function closeBreath() {
    clearTimeout(breathTimer);
    breathTimer = null;
    const overlay = byId("breathOverlay");
    if (overlay) overlay.hidden = true;
    byId("userInput")?.focus();
  }

  function runBreath() {
    clearTimeout(breathTimer);
    const ball = byId("breathBall"), phaseEl = byId("breathPhase"), hint = byId("breathHint"), count = byId("breathCount");
    const roundEl = byId("breathRound");
    const ROUNDS = 4;
    let round = 1, phase = 0, left = BREATH[0][1];
    function show() {
      const [name, secs, tip] = BREATH[phase];
      phaseEl.textContent = name;
      hint.textContent = tip;
      roundEl.textContent = `第 ${round} / ${ROUNDS} 輪`;
      if (left === secs) {
        ball.style.transitionDuration = `${secs}s`;
        ball.style.transform = phase === 0 ? "scale(1)" : phase === 1 ? "scale(1)" : "scale(.45)";
      }
      count.textContent = String(left);
    }
    function tick() {
      left -= 1;
      if (left <= 0) {
        phase += 1;
        if (phase >= BREATH.length) {
          phase = 0;
          round += 1;
          if (round > ROUNDS) {
            phaseEl.textContent = "完成了";
            hint.textContent = "做得很好。身體有沒有比剛剛鬆一點點？想再做一次可以按「再做一次」。";
            count.textContent = "🌿";
            ball.style.transform = "scale(.7)";
            return;
          }
        }
        left = BREATH[phase][1];
      }
      show();
      breathTimer = setTimeout(tick, 1000);
    }
    ball.style.transitionDuration = "0s";
    ball.style.transform = "scale(.45)";
    requestAnimationFrame(() => { show(); breathTimer = setTimeout(tick, 1000); });
  }

  // ---------- 黃燈／橙燈：鼓勵找身邊信任的人或輔導室聊聊（學生頁仍不顯示燈號） ----------
  let nudged = false;
  function encourageTrustedPeople(bubble, wanted) {
    if (nudged || !bubble || !wanted) return;
    nudged = true;
    const box = el("div", "", "trusted-nudge");
    box.appendChild(el("p", "💛 這些心事不用一個人扛。如果願意，也可以找身邊信任的人（家人、朋友、導師）聊聊，或在下課時間去學校輔導室坐坐，輔導老師很願意聽你說。", ""));
    const row = el("div", "", "choice-chips");
    row.appendChild(chip("📝 幫我寫一張給輔導老師的字條", () => window.AnlaNextSteps?.openNote()));
    row.appendChild(chip("💬 不知道怎麼開口？", () => {
      box.appendChild(el("p", "可以這樣說：「老師／○○，我最近心情有點不好，可以找時間跟你聊一下嗎？」不用一次說完，先說一句就很棒了。", "chat-check-note"));
    }));
    box.appendChild(row);
    bubble.appendChild(box);
  }

  const JOKES = [
    "為什麼數學課本總是很憂鬱？因為它有太多問題。",
    "鉛筆跟橡皮擦吵架，最後誰贏了？橡皮擦，因為它把錯都擦掉了。",
    "哪個字大家都會念錯？「錯」。",
    "為什麼電腦很冷靜？因為它有很多風扇。",
    "蚊子為什麼都晚上出來？因為白天要補習。",
    "哪一種水果最有禮貌？香蕉，因為它一直彎腰。",
    "什麼東西越洗越髒？水。",
    "為什麼海那麼鹹？因為魚一直在流汗。",
    "考試的時候，最安靜的是誰？筆，因為它在默寫。",
    "企鵝為什麼不怕冷？因為牠有一件洗不掉的燕尾服。",
    "什麼門永遠關不上？球門。",
    "為什麼月亮不會迷路？因為它有很多星星導航。",
    "布丁跟果凍誰比較勇敢？布丁，因為它敢在盤子上抖來抖去。",
    "哪種書最好讀？臉書，因為大家都有在看。",
    "為什麼床很懂你？因為它每天都陪你躺平。",
    "西瓜為什麼很有自信？因為它知道自己很有料。",
    "什麼東西明明有很多牙齒，卻從來不咬人？梳子。",
    "為什麼小雞過馬路？因為對面有在發飼料。",
    "什麼東西打破了才能用？雞蛋。",
    "什麼東西你越用它越長？你的作業清單（開玩笑的，一題一題來就好）。",
  ];
  let lastJoke = -1;
  function tellJoke() {
    let i = Math.floor(Math.random() * JOKES.length);
    if (i === lastJoke) i = (i + 1) % JOKES.length;
    lastJoke = i;
    appendMessage("ai", "😄 " + JOKES[i]);
    scrollToEnd();
  }

  document.addEventListener("DOMContentLoaded", () => {
    moodPicker();
    urgentActions();
    byId("hideButton")?.addEventListener("click", () => openGame(true));
    byId("puzzleBack")?.addEventListener("click", closeGame);
    byId("puzzleAgain")?.addEventListener("click", newGame);
    byId("musicToggle")?.addEventListener("click", toggleMusic);
    byId("jokeButton")?.addEventListener("click", tellJoke);
    byId("breathButton")?.addEventListener("click", openBreath);
    byId("breathClose")?.addEventListener("click", closeBreath);
    byId("breathAgain")?.addEventListener("click", runBreath);
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      if (byId("puzzleOverlay") && !byId("puzzleOverlay").hidden) closeGame();
      if (byId("breathOverlay") && !byId("breathOverlay").hidden) closeBreath();
    });
  });

  return {startCheck, offerCheck, openGame, tellJoke, lifelineOpen, isLate, openBreath, encourageTrustedPeople,
          removeMoodPicker: () => byId("moodPicker")?.remove()};
})();
