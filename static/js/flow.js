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

  async function showResources(box) {
    box.replaceChildren(el("p", "現在就能打的電話：", "urgent-action-title"));
    const row = el("div", "", "urgent-action-phones");
    [["119", "緊急救護"], ["110", "報案"], ["1925", "安心專線（24 小時）"], ["1995", "生命線（24 小時）"],
     ["113", "保護專線（24 小時）"], ["1980", "張老師"]].forEach(([n, l]) => row.appendChild(phone(n, l)));
    box.appendChild(row);
    try {
      const state = await (await fetch("/api/chat/state", {cache: "no-store"})).json();
      const township = state.student_profile?.township || "南投市";
      const data = await (await fetch(`/api/resources?township=${encodeURIComponent(township)}`)).json();
      const list = el("ul", "", "urgent-action-list");
      (data.resources || []).slice(0, 4).forEach(r => {
        const item = el("li", `${r.name}：`);
        const tel = el("a", r.phone);
        tel.href = `tel:${String(r.phone).split("#")[0].replace(/[^0-9]/g, "")}`;
        item.appendChild(tel);
        list.appendChild(item);
      });
      box.appendChild(el("p", `${township}附近的輔導與心理資源：`, "urgent-action-title"));
      box.appendChild(list);
      box.appendChild(link("看全部南投資源", "/resources"));
    } catch (_) { /* the phones above are enough */ }
  }

  function showFindPerson(box) {
    const now = new Date();
    const late = now.getHours() >= 21 || now.getHours() < 6;
    box.replaceChildren(el("p", "這些地方現在可以找真人：", "urgent-action-title"));
    const row = el("div", "", "urgent-action-phones");
    row.appendChild(phone("1925", "安心專線（24 小時）"));
    row.appendChild(phone("1995", "生命線（24 小時）"));
    if (!late) row.appendChild(phone("1980", "張老師"));
    box.appendChild(row);
    const line = el("p", "");
    if (lifelineOpen(now)) {
      line.append("💬 不想講電話，可以用 LINE 打字跟生命線的人聊：", link("生命線文字協談", LIFELINE_LINE));
    } else {
      line.append("💬 生命線文字協談（LINE）平日 13:00–17:00、18:00–01:00，週末夜間也有；現在不在服務時間，",
                  link("時間以官網為準", LIFELINE_SOURCE), "。");
    }
    box.appendChild(line);
    if (late) {
      box.appendChild(el("p", "已經很晚了。打電話是最快的；如果現在還不想打，也可以先讓自己緩一下：", "urgent-action-title"));
      const choices = el("div", "", "choice-chips");
      choices.appendChild(chip("🎮 玩一下小遊戲", () => openGame(false)));
      choices.appendChild(chip("😄 聽個笑話", tellJoke));
      choices.appendChild(chip("📅 預約專業資源", () => showBooking(box)));
      box.appendChild(choices);
    } else {
      box.appendChild(chip("📅 預約專業資源", () => showBooking(box)));
    }
  }

  function showBooking(box) {
    const card = el("div", "", "urgent-booking");
    card.appendChild(el("p", "南投縣社區心理衛生中心有免費心理諮商（一段 4 次、每次約 50 分鐘），上班時間打電話預約：", ""));
    const row = el("div", "", "urgent-action-phones");
    row.appendChild(phone("049-2202662", "南投區"));
    row.appendChild(phone("049-2631925", "竹山區"));
    card.appendChild(row);
    const src = el("p", "", "school-referral-hint");
    src.append("資料來源：", link("南投縣政府衛生局〈我要心理諮商〉", "https://www.ntshb.gov.tw/counseling/index?Parser=99,5,74,42"),
               "。學生也可以請學校輔導室幫忙轉介。");
    card.appendChild(src);
    box.appendChild(card);
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
    buttons.appendChild(chip("🆘 我需要幫助", () => showResources(box), "urgent-action"));
    buttons.appendChild(chip("🙂 我很安全", () => {
      byId("keepTalkingButton")?.click();
      const input = byId("userInput");
      input.value = "我現在是安全的，只是需要有人陪我聊聊";
      sendMessage();
    }, "urgent-action"));
    buttons.appendChild(chip("📝 幫我整理狀況", () => showNote(box), "urgent-action"));
    buttons.appendChild(chip("🙋 找真人聊聊", () => showFindPerson(box), "urgent-action"));
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

  function drawGame() {
    const grid = byId("puzzleGrid");
    grid.replaceChildren();
    tiles.forEach((n, i) => {
      const t = chip(n ? String(n) : "", () => {
        const z = tiles.indexOf(0);
        if (!neighbours(z).includes(i)) return;
        [tiles[z], tiles[i]] = [tiles[i], tiles[z]];
        drawGame();
      }, n ? "puzzle-tile" : "puzzle-tile puzzle-empty");
      t.disabled = !n;
      grid.appendChild(t);
    });
    const solved = tiles.join(",") === "1,2,3,4,5,6,7,8,0";
    byId("puzzleStatus").textContent = solved ? "完成了！要再玩一次嗎？" : "把數字推回 1 到 8 的順序。";
  }

  function openGame(hidden) {
    const overlay = byId("puzzleOverlay");
    tiles = shuffled();
    drawGame();
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
      button.textContent = "🎵 背景音樂";
      button.setAttribute("aria-pressed", "false");
      return;
    }
    // A soft generated pad (no audio files, nothing downloaded): four gentle chords, slow fades, low volume.
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const master = ctx.createGain();
    master.gain.value = 0;
    master.connect(ctx.destination);
    master.gain.setTargetAtTime(0.06, ctx.currentTime, 1.5);
    const chords = [[261.6, 329.6, 392.0, 493.9], [220.0, 261.6, 329.6, 392.0], [174.6, 220.0, 261.6, 329.6],
                    [196.0, 246.9, 293.7, 329.6]];
    let step = 0;
    function play() {
      if (!audio) return;
      const t = ctx.currentTime;
      chords[step % chords.length].forEach(freq => {
        const osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.25, t + 1.5);
        gain.gain.linearRampToValueAtTime(0, t + 4.2);
        osc.connect(gain).connect(master);
        osc.start(t);
        osc.stop(t + 4.3);
      });
      step += 1;
      audio.timer = setTimeout(play, 4000);
    }
    audio = {ctx, master, timer: null};
    play();
    button.textContent = "🎵 音樂：開";
    button.setAttribute("aria-pressed", "true");
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
    byId("puzzleAgain")?.addEventListener("click", () => { tiles = shuffled(); drawGame(); });
    byId("musicToggle")?.addEventListener("click", toggleMusic);
    byId("jokeButton")?.addEventListener("click", tellJoke);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && byId("puzzleOverlay") && !byId("puzzleOverlay").hidden) closeGame();
    });
  });

  return {startCheck, offerCheck, openGame, tellJoke, lifelineOpen, removeMoodPicker: () => byId("moodPicker")?.remove()};
})();
