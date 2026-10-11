import { DIR_KEYS, SIDE_LABEL, TERRAIN, TYPE_LABEL, terrainAt } from "./world.js";
import {
  beginResolve,
  cancelLast,
  clearOrders,
  cycleStack,
  dateOf,
  displayPos,
  landUnitAt,
  living,
  moveCursor,
  nextNorman,
  orderPath,
  pickUp,
  putDown,
  selectedUnit,
  setPathTo,
  sideScore,
  stepTick,
  applyUpkeep,
  tileInfo,
  unitById,
  unitsAt,
} from "./engine.js";
import { planAI } from "./ai.js";

const PAL = {
  sea: ["#1f3d58", "#2b5574"],
  beach: ["#d9c07a", "#c9ab62"],
  clear: ["#c6b17a", "#d3c08c"],
  forest: ["#355534", "#2a4629"],
  hill: ["#8a6b48", "#7a5c3c"],
  marsh: ["#6a7a4c", "#5c6c42"],
  river: ["#3d6e96", "#4d86b0"],
  road: ["#c4a86a", "#b69658"],
  town: ["#c6b17a", "#d3c08c"],
  out: ["#8a8174", "#6e655a"],
  grid: "rgba(40,28,16,0.18)",
  cursor: "#e84ac0",
  oak: "#140f0b",
  gold: "#d4b45a",
  cream: "#f0e2c0",
};

const SIDE_COL = {
  norman: { fill: "#8e1b28", ink: "#f3d9a4", edge: "#e0c36a" },
  english: { fill: "#234c34", ink: "#e7efd8", edge: "#cfe3b0" },
  norse: { fill: "#243656", ink: "#e4ecf6", edge: "#9eb4d0" },
};

const TILE = 32;

export class GameView {
  constructor(canvas, hud, game, onEnded) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.hud = hud;
    this.game = game;
    this.onEnded = onEnded;
    this.cam = { x: 0, y: 0 };
    this.t0 = performance.now();
    this.resolveAcc = 0;
    this.help = false;
    this.showTerrain = false;
    this.dpr = 1;
    this.hover = null;
    this.running = true;
    this.resize = this.resize.bind(this);
    this.loop = this.loop.bind(this);
    this.onKey = this.onKey.bind(this);
    this.onClick = this.onClick.bind(this);
    this.onMove = this.onMove.bind(this);
    window.addEventListener("resize", this.resize);
    window.addEventListener("keydown", this.onKey);
    canvas.addEventListener("click", this.onClick);
    canvas.addEventListener("mousemove", this.onMove);
    canvas.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      clearOrders(this.game);
      this.paintHud();
    });
    canvas.tabIndex = 0;
    loadBoardImage(this.game.map);
    this.resize();
    canvas.focus();
    this.centerOnCursor(true);
    planAI(this.game);
    this.paintHud();
    requestAnimationFrame(this.loop);
  }

  destroy() {
    this.running = false;
    window.removeEventListener("resize", this.resize);
    window.removeEventListener("keydown", this.onKey);
  }

  resize() {
    const wrap = this.canvas.parentElement;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = Math.floor(w * this.dpr);
    this.canvas.height = Math.floor(h * this.dpr);
    this.canvas.style.width = w + "px";
    this.canvas.style.height = h + "px";
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.vw = w;
    this.vh = h;
  }

  centerOnCursor(hard) {
    const tx = this.game.cursor.x * TILE - this.vw / 2 + TILE / 2;
    const ty = this.game.cursor.y * TILE - this.vh / 2 + TILE / 2;
    const maxX = this.game.w * TILE - this.vw;
    const maxY = this.game.h * TILE - this.vh;
    const x = clamp(tx, 0, Math.max(0, maxX));
    const y = clamp(ty, 0, Math.max(0, maxY));
    if (hard) {
      this.cam.x = x;
      this.cam.y = y;
    } else {
      this.cam.x += (x - this.cam.x) * 0.12;
      this.cam.y += (y - this.cam.y) * 0.12;
    }
  }

  screenTiles() {
    const x0 = Math.max(0, Math.floor(this.cam.x / TILE) - 1);
    const y0 = Math.max(0, Math.floor(this.cam.y / TILE) - 1);
    const x1 = Math.min(this.game.w - 1, Math.ceil((this.cam.x + this.vw) / TILE) + 1);
    const y1 = Math.min(this.game.h - 1, Math.ceil((this.cam.y + this.vh) / TILE) + 1);
    return { x0, y0, x1, y1 };
  }

  tileFromEvent(e) {
    const r = this.canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - r.left + this.cam.x) / TILE);
    const y = Math.floor((e.clientY - r.top + this.cam.y) / TILE);
    return { x, y };
  }

  onMove(e) {
    this.hover = this.tileFromEvent(e);
  }

  onClick(e) {
    if (this.game.phase === "ended") return;
    const { x, y } = this.tileFromEvent(e);
    if (x < 0 || y < 0 || x >= this.game.w || y >= this.game.h) return;
    this.game.cursor.x = x;
    this.game.cursor.y = y;
    const stack = unitsAt(this.game, x, y).filter((u) => u.side === "norman");
    if (this.game.phase === "orders" && this.game.selectedId) {
      if (stack.length && stack[0].id === this.game.selectedId) {
        putDown(this.game);
      } else {
        setPathTo(this.game, x, y);
      }
    } else if (stack.length) {
      pickUp(this.game, stack[0]);
    }
    this.paintHud();
  }

  onKey(e) {
    if (e.key === "?" || e.key === "h" || e.key === "H") {
      this.help = !this.help;
      this.paintHud();
      return;
    }
    if (e.key === "g" || e.key === "G") {
      this.showTerrain = !this.showTerrain;
      this.paintHud();
      return;
    }
    if (this.help && e.key === "Escape") {
      this.help = false;
      this.paintHud();
      return;
    }
    if (this.game.phase === "ended") return;
    if (this.game.phase === "resolve") {
      if (e.key === " " || e.key === "Escape" || e.key === "t" || e.key === "T") {
        this.skipResolve = true;
      }
      return;
    }
    const dir = DIR_KEYS[e.key];
    if (dir) {
      e.preventDefault();
      const [dx, dy] = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] }[dir];
      moveCursor(this.game, dx, dy);
      this.paintHud();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const stack = unitsAt(this.game, this.game.cursor.x, this.game.cursor.y).filter((u) => u.side === "norman");
      if (this.game.selectedId) {
        if (stack.length > 1) cycleStack(this.game);
        else putDown(this.game);
      } else if (stack.length) {
        pickUp(this.game, stack[0]);
      }
      this.paintHud();
      return;
    }
    if (e.key === "Backspace") {
      e.preventDefault();
      cancelLast(this.game);
      this.paintHud();
      return;
    }
    if (e.key === " ") {
      e.preventDefault();
      clearOrders(this.game);
      this.paintHud();
      return;
    }
    if (e.key === "n" || e.key === "N") {
      nextNorman(this.game);
      this.centerOnCursor(false);
      this.paintHud();
      return;
    }
    if (e.key === "t" || e.key === "T" || e.key === "End") {
      e.preventDefault();
      this.startResolve();
    }
  }

  startResolve() {
    if (this.game.phase !== "orders") return;
    putDown(this.game);
    beginResolve(this.game);
    this.resolveAcc = 0;
    this.skipResolve = false;
    this.paintHud();
  }

  loop(now) {
    if (!this.running) return;
    const dt = Math.min(0.05, (now - this.t0) / 1000);
    this.t0 = now;
    this.time = now / 1000;
    this.centerOnCursor(false);
    if (this.game.phase === "resolve") {
      const finish = () => {
        applyUpkeep(this.game);
        if (this.game.phase === "orders") planAI(this.game);
        if (this.game.phase === "ended" && this.onEnded) this.onEnded(this.game);
        this.paintHud();
      };
      if (this.skipResolve) {
        while (this.game.phase === "resolve") {
          if (stepTick(this.game)) {
            finish();
            break;
          }
        }
      } else {
        this.resolveAcc += dt;
        while (this.game.phase === "resolve" && this.resolveAcc >= 0.07) {
          this.resolveAcc -= 0.07;
          if (stepTick(this.game)) {
            finish();
            break;
          }
        }
      }
    }
    this.draw();
    requestAnimationFrame(this.loop);
  }

  draw() {
    const ctx = this.ctx;
    const g = this.game;
    ctx.fillStyle = PAL.oak;
    ctx.fillRect(0, 0, this.vw, this.vh);
    ctx.save();
    ctx.translate(-Math.round(this.cam.x), -Math.round(this.cam.y));
    const vis = this.screenTiles();
    const board = boardImageOf(g.map);
    if (board) this.paintBoard(ctx, g, vis, board);
    else this.paintSquares(ctx, g, vis);
    this.drawOrders(ctx);
    this.drawUnits(ctx, vis);
    this.drawTownLabels(ctx, vis);
    this.drawCursor(ctx);
    ctx.restore();
    this.drawMinimap(ctx);
    if (this.help) this.drawHelp(ctx);
  }

  drawTile(ctx, x, y) {
    drawTileAt(ctx, gmap(this.game), this.game.towns, x, y, this.time || 0);
  }

  paintSquares(ctx, g, vis) {
    ctx.fillStyle = PAL.sea[0];
    ctx.fillRect(0, 0, g.w * TILE, g.h * TILE);
    for (let y = vis.y0; y <= vis.y1; y++) {
      for (let x = vis.x0; x <= vis.x1; x++) this.drawTile(ctx, x, y);
    }
    blitCoast(ctx, coastOf(g.map), this.cam, this.vw, this.vh);
  }

  // The relief is the board. Square fills stay hidden so the picture shows.
  // G draws them back at half strength, with the smooth shore, when the
  // movement colors are what you need. Out of play, beaches, roads, and the
  // sea edge stay marked on the photograph itself.
  paintBoard(ctx, g, vis, board) {
    drawBoardImage(ctx, g.map, board);
    if (this.showTerrain) {
      ctx.save();
      ctx.globalAlpha = 0.5;
      for (let y = vis.y0; y <= vis.y1; y++) {
        for (let x = vis.x0; x <= vis.x1; x++) this.drawTile(ctx, x, y);
      }
      ctx.restore();
      blitCoast(ctx, coastOf(g.map), this.cam, this.vw, this.vh);
      return;
    }
    blitCoast(ctx, playMarksOf(g.map), this.cam, this.vw, this.vh);
    drawTownMarks(ctx, g.towns);
  }

  drawTownLabels(ctx, vis) {
    ctx.font = LABEL_FONT;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    for (const lab of layoutTownLabels(ctx, this.game.towns)) {
      if (lab.tx < vis.x0 - 3 || lab.tx > vis.x1 + 3 || lab.ty < vis.y0 - 3 || lab.ty > vis.y1 + 3) continue;
      paintOneLabel(ctx, lab);
    }
  }

  drawOrders(ctx) {
    const g = this.game;
    for (const u of living(g)) {
      if (u.side !== "norman" && u.id !== g.selectedId) continue;
      if (!u.orders.length) continue;
      const col = u.side === "norman" ? "rgba(232, 196, 90, 0.9)" : "rgba(200,220,255,0.7)";
      const pts = orderPath(u, g).map((p) => ({
        x: p.x * TILE + TILE / 2,
        y: p.y * TILE + TILE / 2,
      }));
      ctx.strokeStyle = col;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
      ctx.stroke();
      for (let i = 1; i < pts.length; i++) {
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.arc(pts[i].x, pts[i].y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  drawUnits(ctx, vis) {
    const drawn = new Set();
    for (const u of living(this.game)) {
      const p = displayPos(this.game, u);
      if (p.x < vis.x0 || p.x > vis.x1 || p.y < vis.y0 || p.y > vis.y1) continue;
      const k = p.x + "," + p.y;
      if (drawn.has(k) && u.embarkedOn) continue;
      drawn.add(k);
      this.drawCounter(ctx, u, p);
    }
  }

  drawCounter(ctx, u, p) {
    const px = p.x * TILE + 3;
    const py = p.y * TILE + 5;
    const pal = SIDE_COL[u.side];
    if (u.flash > 0) {
      ctx.fillStyle = `rgba(255,220,180,${u.flash})`;
      ctx.fillRect(px - 2, py - 2, 28, 24);
      u.flash = Math.max(0, u.flash - 0.08);
    }
    ctx.fillStyle = "rgba(12, 8, 6, 0.45)";
    roundRect(ctx, px + 1, py + 2, 26, 20, 2);
    ctx.fill();
    ctx.fillStyle = pal.fill;
    roundRect(ctx, px, py, 26, 20, 2);
    ctx.fill();
    ctx.strokeStyle = u.id === this.game.selectedId ? "#fff4c2" : pal.edge;
    ctx.lineWidth = u.id === this.game.selectedId ? 2 : 1;
    ctx.stroke();
    ctx.fillStyle = pal.ink;
    ctx.font = "bold 9px Palatino Linotype, Palatino, serif";
    ctx.textAlign = "left";
    const mark = u.type === "fleet" ? "F" : u.type === "knights" ? "K" : u.type === "archers" ? "A" : u.type === "fyrd" ? "Y" : u.type === "housecarls" || u.type === "huscarls" ? "H" : "I";
    ctx.fillText(mark, px + 3, py + 9);
    ctx.font = "9px Palatino Linotype, Palatino, serif";
    ctx.fillText(String(u.combat), px + 3, py + 18);
    if (u.broken) {
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      ctx.fillRect(px, py, 26, 20);
    }
    const cargo = living(this.game).filter((c) => c.embarkedOn === u.id);
    if (cargo.length) {
      ctx.fillStyle = PAL.gold;
      ctx.font = "bold 8px sans-serif";
      ctx.fillText("+" + cargo.length, px + 14, py + 9);
    }
  }

  drawCursor(ctx) {
    const t = 0.5 + 0.5 * Math.sin(this.time * 6);
    ctx.strokeStyle = PAL.cursor;
    ctx.globalAlpha = 0.55 + 0.45 * t;
    ctx.lineWidth = 2;
    const x = this.game.cursor.x * TILE + 1;
    const y = this.game.cursor.y * TILE + 1;
    ctx.strokeRect(x, y, TILE - 2, TILE - 2);
    ctx.globalAlpha = 1;
  }

  drawMinimap(ctx) {
    const scale = 2;
    const mw = this.game.w * scale;
    const mh = this.game.h * scale;
    const ox = 12;
    const oy = this.vh - mh - 12;
    ctx.fillStyle = "rgba(12,8,6,0.72)";
    ctx.fillRect(ox - 4, oy - 4, mw + 8, mh + 8);
    const board = boardImageOf(this.game.map);
    if (board && !this.showTerrain) {
      const b = this.game.map.board_image;
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(board, b.left, b.top, b.right - b.left, b.bottom - b.top, ox, oy, mw, mh);
      for (let y = 0; y < this.game.h; y++) {
        for (let x = 0; x < this.game.w; x++) {
          if (terrainAt(gmap(this.game), x, y) !== TERRAIN.OUT) continue;
          ctx.fillStyle = "rgba(16, 12, 8, 0.55)";
          ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale);
        }
      }
    } else {
      for (let y = 0; y < this.game.h; y++) {
        for (let x = 0; x < this.game.w; x++) {
          const t = terrainAt(gmap(this.game), x, y);
          const names = ["sea", "beach", "clear", "forest", "hill", "marsh", "river", "road", "town", "out"];
          ctx.fillStyle = PAL[names[t] || "clear"][0];
          ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale);
        }
      }
      const coast = coastOf(this.game.map);
      if (coast.overlay) {
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(coast.overlay, ox, oy, mw, mh);
      }
    }
    for (const u of living(this.game)) {
      const p = displayPos(this.game, u);
      ctx.fillStyle = SIDE_COL[u.side].fill;
      ctx.fillRect(ox + p.x * scale, oy + p.y * scale, 2, 2);
    }
    ctx.strokeStyle = PAL.gold;
    ctx.strokeRect(ox + (this.cam.x / TILE) * scale, oy + (this.cam.y / TILE) * scale, (this.vw / TILE) * scale, (this.vh / TILE) * scale);
  }

  drawHelp(ctx) {
    ctx.fillStyle = "rgba(10,8,6,0.82)";
    ctx.fillRect(this.vw / 2 - 250, 40, 500, 370);
    ctx.strokeStyle = PAL.gold;
    ctx.strokeRect(this.vw / 2 - 250, 40, 500, 370);
    ctx.fillStyle = PAL.cream;
    ctx.font = "16px Palatino Linotype, Palatino, serif";
    ctx.textAlign = "left";
    const lines = [
      "Orders first, then all sides move at once.",
      "Arrows / WASD  move the cursor (and plot orders if a unit is held)",
      "Enter  pick up or put down a Norman unit",
      "Click a unit, then click a destination, to plot a path",
      "Backspace  cancel last order    Space  clear orders",
      "N  next Norman unit             T  execute the week",
      "G  terrain plate — movement colors over the relief",
      "Right-click  clear orders",
      "March to a fleet on the coast, then order into the sea to embark.",
      "Gale turns close the Channel. Land while Harold is in the north.",
    ];
    lines.forEach((ln, i) => ctx.fillText(ln, this.vw / 2 - 230, 80 + i * 28));
  }

  paintHud() {
    const g = this.game;
    const d = dateOf(g);
    const sel = selectedUnit(g) || landUnitAt(g, g.cursor.x, g.cursor.y) || unitsAt(g, g.cursor.x, g.cursor.y)[0];
    const mover = sel && sel.embarkedOn ? unitById(g, sel.embarkedOn) || sel : sel;
    const info = tileInfo(g, g.cursor.x, g.cursor.y);
    const phase =
      g.phase === "orders" ? "Issue orders" : g.phase === "resolve" ? `Resolving tick ${g.tick}/32` : "Campaign ended";
    const unitBlock = sel
      ? `<div class="unit ${sel.side}">
          <div class="uname">${esc(sel.name)}</div>
          <div class="umeta">${SIDE_LABEL[sel.side]} · ${TYPE_LABEL[sel.type]}${g.selectedId === sel.id ? " · HELD" : ""}${sel.broken ? " · BROKEN" : ""}${sel.embarkedOn ? " · embarked" : ""}</div>
          <div class="bars">
            <span>Muster ${sel.muster}</span>
            <span>Combat ${sel.combat}</span>
            ${sel.fatigue ? `<span>Fatigue ${sel.fatigue}</span>` : ""}
            ${sel.supplied === false ? "<span>Out of supply</span>" : ""}
          </div>
          <div class="orders">Orders: ${mover.orders.length ? mover.orders.join(" ") : "hold"}</div>
        </div>`
      : `<div class="unit"><div class="uname">No unit</div><div class="umeta">${info.terr}${info.town ? " · " + info.town.name : ""}</div></div>`;

    this.hud.innerHTML = `
      <div class="brand">
        <div class="kicker">Anno Domini MLXVI</div>
        <h2>Battle for Britain</h2>
      </div>
      <div class="statline">
        <div><label>Date</label>${d.label}</div>
        <div><label>Turn</label>${g.turn + 1} / 24</div>
        <div><label>Weather</label>${g.weather.label}</div>
        <div><label>Phase</label>${phase}</div>
      </div>
      <div class="scores">
        <span class="norman">Norman ${sideScore(g, "norman")}</span>
        <span class="english">English ${sideScore(g, "english")}</span>
        <span class="norse">Norse ${sideScore(g, "norse")}</span>
      </div>
      <div class="btns">
        <button id="endturn" ${g.phase !== "orders" ? "disabled" : ""}>Execute week (T)</button>
        <button id="nextu">Next unit (N)</button>
        <button id="terrain" class="ghost">${this.showTerrain ? "Relief map (G)" : "Terrain plate (G)"}</button>
      </div>
      <div class="pad">
        <button id="dirN" class="ghost">N</button>
        <div class="pad-mid">
          <button id="dirW" class="ghost">W</button>
          <button id="pickup" class="ghost">Hold</button>
          <button id="dirE" class="ghost">E</button>
        </div>
        <button id="dirS" class="ghost">S</button>
      </div>
      ${unitBlock}
      <div class="tile">Tile ${g.cursor.x},${g.cursor.y} · ${info.terr}${info.town ? " · " + info.town.name + " (" + info.town.owner + ")" : ""}</div>
      <ol class="log">${g.log.map((l) => `<li>${esc(l)}</li>`).join("")}</ol>
      <p class="hint">? help · You are William. Take London, and Winchester or Harold's life, before Christmas.</p>
    `;
    const end = this.hud.querySelector("#endturn");
    const nxt = this.hud.querySelector("#nextu");
    if (end) end.onclick = () => this.startResolve();
    const plate = this.hud.querySelector("#terrain");
    if (plate)
      plate.onclick = () => {
        this.showTerrain = !this.showTerrain;
        this.paintHud();
      };
    if (nxt)
      nxt.onclick = () => {
        nextNorman(g);
        this.centerOnCursor(false);
        this.paintHud();
      };
    const hold = this.hud.querySelector("#pickup");
    if (hold)
      hold.onclick = () => {
        const stack = unitsAt(g, g.cursor.x, g.cursor.y).filter((u) => u.side === "norman");
        if (g.selectedId) putDown(g);
        else if (stack.length) pickUp(g, stack[0]);
        this.paintHud();
      };
    const bindDir = (id, dx, dy) => {
      const el = this.hud.querySelector(id);
      if (el)
        el.onclick = () => {
          moveCursor(g, dx, dy);
          this.refreshHudBits();
        };
    };
    bindDir("#dirN", 0, -1);
    bindDir("#dirS", 0, 1);
    bindDir("#dirW", -1, 0);
    bindDir("#dirE", 1, 0);
  }

  refreshHudBits() {
    const g = this.game;
    const sel = selectedUnit(g) || landUnitAt(g, g.cursor.x, g.cursor.y) || unitsAt(g, g.cursor.x, g.cursor.y)[0];
    const mover = sel && sel.embarkedOn ? unitById(g, sel.embarkedOn) || sel : sel;
    const orders = this.hud.querySelector(".orders");
    const tile = this.hud.querySelector(".tile");
    const umeta = this.hud.querySelector(".umeta");
    if (orders) {
      orders.textContent = mover && mover.orders.length ? "Orders: " + mover.orders.join(" ") : "Orders: hold";
    }
    if (tile) {
      const info = tileInfo(g, g.cursor.x, g.cursor.y);
      tile.textContent = `Tile ${g.cursor.x},${g.cursor.y} · ${info.terr}${info.town ? " · " + info.town.name + " (" + info.town.owner + ")" : ""}`;
    }
    if (umeta && sel) {
      umeta.textContent = `${SIDE_LABEL[sel.side]} · ${TYPE_LABEL[sel.type]}${g.selectedId === sel.id ? " · HELD" : ""}${sel.broken ? " · BROKEN" : ""}${sel.embarkedOn ? " · embarked" : ""}`;
    }
  }
}

// Names prefer the space just above their own town. Neighbours a cell apart
// (Canterbury/Dover, Pevensey/Hastings) shift sideways before they stack,
// and a short leader keeps an offset name tied to its dot.
const LABEL_FONT = "600 11px Palatino Linotype, Palatino, serif";
const LABEL_GAP = 5;

export function layoutTownLabels(ctx, towns) {
  ctx.font = LABEL_FONT;
  const placed = [];
  const ordered = towns.slice().sort((a, b) => a.y - b.y || a.x - b.x || a.name.localeCompare(b.name));
  for (const t of ordered) {
    const measured = ctx.measureText(t.name).width;
    const width = measured > 2 ? measured : t.name.length * 6.4;
    const cx = t.x * TILE + TILE / 2;
    const tileTop = t.y * TILE;
    const preferredY = tileTop - 2;
    const step = Math.max(20, width * 0.55);
    const sides = [0, -1, 1, -2, 2, -3, 3];
    const dys = [-2, TILE + 11, -16, TILE + 26, 13, -32, TILE + 40, -46, TILE + 54];
    let choice = null;
    let best = Infinity;
    for (const dy of dys) {
      for (const side of sides) {
        const x = cx + side * step;
        const y = tileTop + dy;
        const box = labelBox(x, y, width);
        if (placed.some((p) => boxesHit(p, box, LABEL_GAP))) continue;
        if (coversOtherTown(box, t, towns)) continue;
        let score = Math.abs(side) * 1.15 + Math.abs(y - preferredY) * 0.09;
        if (dy > 0) score += 0.35;
        for (const p of placed) {
          const overlap = Math.min(box.r, p.r) - Math.max(box.l, p.l);
          const vert = box.b < p.t ? p.t - box.b : p.b < box.t ? box.t - p.b : 0;
          if (overlap > 6 && vert < 36) score += 5;
        }
        if (score < best) {
          best = score;
          const leader = Math.hypot(x - cx, y - preferredY) > 14;
          choice = { name: t.name, x, y, tx: t.x, ty: t.y, leader, ...box };
        }
      }
    }
    if (!choice) {
      for (let ring = 4; ring <= 16 && !choice; ring++) {
        for (const y of [preferredY - ring * 12, tileTop + TILE + 11 + ring * 12]) {
          for (const side of sides) {
            const x = cx + side * step;
            const box = labelBox(x, y, width);
            if (placed.some((p) => boxesHit(p, box, LABEL_GAP))) continue;
            choice = { name: t.name, x, y, tx: t.x, ty: t.y, leader: true, ...box };
            break;
          }
          if (choice) break;
        }
      }
    }
    if (!choice) {
      const y = tileTop + TILE + 11 + (placed.length + 1) * 16;
      const box = labelBox(cx, y, width);
      choice = { name: t.name, x: cx, y, tx: t.x, ty: t.y, leader: true, ...box };
    }
    placed.push(choice);
  }
  return placed;
}

function labelBox(x, y, width) {
  const pad = 2;
  return { l: x - width / 2 - pad, r: x + width / 2 + pad, t: y - 12, b: y + 2 };
}

function coversOtherTown(box, self, towns) {
  for (const o of towns) {
    if (o.x === self.x && o.y === self.y) continue;
    const ox = o.x * TILE + TILE / 2;
    const oy = o.y * TILE + TILE / 2;
    if (ox > box.l + 4 && ox < box.r - 4 && oy > box.t + 2 && oy < box.b - 2) return true;
  }
  return false;
}

function paintOneLabel(ctx, lab) {
  if (lab.leader) {
    const tx = lab.tx * TILE + TILE / 2;
    const ty = lab.ty * TILE + TILE / 2;
    const x = Math.max(lab.l, Math.min(lab.r, tx));
    const y = Math.max(lab.t, Math.min(lab.b, ty));
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(x, y);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(246, 238, 214, 0.92)";
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(28, 20, 12, 0.88)";
    ctx.stroke();
  }
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;
  ctx.strokeStyle = "rgba(246, 238, 214, 0.95)";
  ctx.strokeText(lab.name, lab.x, lab.y);
  ctx.fillStyle = "#1a120c";
  ctx.fillText(lab.name, lab.x, lab.y);
}

function boxesHit(a, b, gap = 0) {
  return a.l - gap < b.r && a.r + gap > b.l && a.t - gap < b.b && a.b + gap > b.t;
}

// The photograph is aligned by board_image: its pixel rectangle
// (left, top, right, bottom) stretches onto the whole grid. One cell is
// (right-left)/w by (bottom-top)/h source pixels.
let boardCache = { key: "", img: null, status: "idle" };

export function loadBoardImage(map) {
  ensureBoard(map);
  return boardImageOf(map);
}

function ensureBoard(map) {
  const spec = map && map.board_image;
  if (!spec || !spec.path || !(spec.right > spec.left) || !(spec.bottom > spec.top)) return;
  const key = spec.path + "@" + spec.left + "," + spec.top + "," + spec.right + "," + spec.bottom;
  if (boardCache.key === key) return;
  boardCache = { key, img: null, status: "loading" };
  const img = new Image();
  img.decoding = "async";
  img.onload = () => {
    if (boardCache.key !== key) return;
    boardCache.img = img;
    boardCache.status = "ready";
  };
  img.onerror = () => {
    if (boardCache.key !== key) return;
    boardCache.status = "error";
  };
  img.src = spec.path;
}

function boardImageOf(map) {
  ensureBoard(map);
  const img = boardCache.img;
  if (!img || boardCache.status !== "ready" || !img.complete || img.naturalWidth < 1) return null;
  return img;
}

function drawBoardImage(ctx, map, img) {
  const b = map.board_image;
  const prev = ctx.imageSmoothingEnabled;
  ctx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in ctx) ctx.imageSmoothingQuality = "high";
  ctx.drawImage(img, b.left, b.top, b.right - b.left, b.bottom - b.top, 0, 0, map.w * TILE, map.h * TILE);
  ctx.imageSmoothingEnabled = prev;
}

let playMemo = null;

function playMarksOf(map) {
  if (playMemo && playMemo.map === map) return playMemo;
  playMemo = buildPlayMarks(map);
  return playMemo;
}

function buildPlayMarks(map) {
  const overlay = document.createElement("canvas");
  overlay.width = map.w * TILE;
  overlay.height = map.h * TILE;
  const ctx = overlay.getContext("2d");
  for (let y = 0; y < map.h; y++) {
    for (let x = 0; x < map.w; x++) {
      const t = terrainAt(map, x, y);
      const px = x * TILE;
      const py = y * TILE;
      if (t === TERRAIN.OUT) {
        ctx.fillStyle = "rgba(18, 14, 10, 0.52)";
        ctx.fillRect(px, py, TILE, TILE);
        ctx.strokeStyle = "rgba(10, 8, 6, 0.5)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = -TILE; i <= TILE; i += 8) {
          ctx.moveTo(px + i, py);
          ctx.lineTo(px + i + TILE, py + TILE);
        }
        ctx.stroke();
      } else if (t === TERRAIN.BEACH) {
        ctx.fillStyle = "rgba(186, 148, 72, 0.4)";
        ctx.fillRect(px, py, TILE, TILE);
      }
      if (t !== TERRAIN.OUT) {
        ctx.strokeStyle = t === TERRAIN.SEA ? "rgba(16, 40, 58, 0.2)" : "rgba(36, 28, 18, 0.3)";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, TILE - 1, TILE - 1);
      }
    }
  }
  strokeLinks(ctx, map, roadLink, "rgba(42, 28, 14, 0.55)", 4);
  strokeLinks(ctx, map, roadLink, "rgba(232, 210, 156, 0.85)", 2);
  strokeLinks(ctx, map, riverLink, "rgba(27, 78, 122, 0.82)", 3);
  strokeCellShore(ctx, map);
  return { map, overlay };
}

function roadLink(t, nt) {
  const roadish = (v) => v === TERRAIN.ROAD || v === TERRAIN.TOWN;
  return roadish(t) && roadish(nt) && (t === TERRAIN.ROAD || nt === TERRAIN.ROAD);
}

function riverLink(t, nt) {
  const river = t === TERRAIN.RIVER || nt === TERRAIN.RIVER;
  if (!river) return false;
  const wet = (v) => v === TERRAIN.RIVER || v === TERRAIN.SEA || v === TERRAIN.BEACH || v === TERRAIN.TOWN;
  return wet(t) && wet(nt);
}

function strokeLinks(ctx, map, pred, color, width) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  for (let y = 0; y < map.h; y++) {
    for (let x = 0; x < map.w; x++) {
      const t = terrainAt(map, x, y);
      const x0 = x * TILE + TILE / 2;
      const y0 = y * TILE + TILE / 2;
      if (x + 1 < map.w && pred(t, terrainAt(map, x + 1, y))) {
        ctx.moveTo(x0, y0);
        ctx.lineTo(x0 + TILE, y0);
      }
      if (y + 1 < map.h && pred(t, terrainAt(map, x, y + 1))) {
        ctx.moveTo(x0, y0);
        ctx.lineTo(x0, y0 + TILE);
      }
    }
  }
  ctx.stroke();
}

// Exact sea/land cell edges, so a move onto the shore matches the line.
// The rounded shore from the square map comes back with the terrain plate.
function strokeCellShore(ctx, map) {
  ctx.beginPath();
  ctx.lineJoin = "miter";
  for (let y = 0; y < map.h; y++) {
    for (let x = 0; x < map.w; x++) {
      if (terrainAt(map, x, y) === TERRAIN.SEA) continue;
      const px = x * TILE;
      const py = y * TILE;
      if (terrainAt(map, x, y - 1) === TERRAIN.SEA) {
        ctx.moveTo(px, py);
        ctx.lineTo(px + TILE, py);
      }
      if (terrainAt(map, x, y + 1) === TERRAIN.SEA) {
        ctx.moveTo(px, py + TILE);
        ctx.lineTo(px + TILE, py + TILE);
      }
      if (terrainAt(map, x - 1, y) === TERRAIN.SEA) {
        ctx.moveTo(px, py);
        ctx.lineTo(px, py + TILE);
      }
      if (terrainAt(map, x + 1, y) === TERRAIN.SEA) {
        ctx.moveTo(px + TILE, py);
        ctx.lineTo(px + TILE, py + TILE);
      }
    }
  }
  ctx.strokeStyle = "rgba(248, 240, 220, 0.75)";
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.strokeStyle = "rgba(20, 14, 8, 0.82)";
  ctx.lineWidth = 1.25;
  ctx.stroke();
}

function drawTownMarks(ctx, towns) {
  for (const t of towns) {
    const cx = t.x * TILE + TILE / 2;
    const cy = t.y * TILE + TILE / 2;
    ctx.beginPath();
    ctx.arc(cx, cy, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = t.owner === "norman" ? "#8e1b28" : t.owner === "norse" ? "#243656" : "#1c1814";
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#e6c86a";
    ctx.stroke();
  }
}

// Smooth the sea/land edge already stored in the map. Gameplay stays on the
// squares; only the painted shore is curved. Radius is in cells.
const COAST_RADIUS = 1.35;
const COAST_ROUND = 0.22;
const TNAMES = ["sea", "beach", "clear", "forest", "hill", "marsh", "river", "road", "town", "out"];

let coastMemo = null;

function coastOf(map) {
  if (coastMemo && coastMemo.map === map) return coastMemo;
  coastMemo = buildCoast(map);
  return coastMemo;
}

function buildCoast(map) {
  const loops = traceCoastLoops(map);
  const play = new Path2D();
  for (const loop of loops) appendRoundedLoop(play, loop, TILE, COAST_RADIUS, COAST_ROUND);
  const landEdge = [];
  const seaEdge = [];
  for (let y = 0; y < map.h; y++) {
    for (let x = 0; x < map.w; x++) {
      const t = terrainAt(map, x, y);
      if (t === TERRAIN.SEA) {
        const shore = shoreTerrain(map, x, y);
        if (shore !== null) seaEdge.push({ x, y, terr: shore });
      } else if (touchesSea(map, x, y)) {
        landEdge.push({ x, y });
      }
    }
  }
  const overlay = document.createElement("canvas");
  overlay.width = map.w * TILE;
  overlay.height = map.h * TILE;
  const ctx = overlay.getContext("2d");
  paintSlivers(ctx, map, play, landEdge, seaEdge);
  return { map, play, overlay, loops: loops.length };
}

function shoreTerrain(map, x, y) {
  let found = null;
  for (const [dx, dy] of [
    [0, -1],
    [1, 0],
    [0, 1],
    [-1, 0],
  ]) {
    const t = terrainAt(map, x + dx, y + dy);
    if (t === TERRAIN.SEA) continue;
    if (t === TERRAIN.BEACH) return TERRAIN.BEACH;
    if (found === null) found = t;
  }
  return found;
}

function touchesSea(map, x, y) {
  return (
    terrainAt(map, x, y - 1) === TERRAIN.SEA ||
    terrainAt(map, x, y + 1) === TERRAIN.SEA ||
    terrainAt(map, x - 1, y) === TERRAIN.SEA ||
    terrainAt(map, x + 1, y) === TERRAIN.SEA
  );
}

function paintSlivers(ctx, map, play, landEdge, seaEdge) {
  if (seaEdge.length) {
    ctx.save();
    ctx.beginPath();
    for (const c of seaEdge) ctx.rect(c.x * TILE, c.y * TILE, TILE, TILE);
    ctx.clip();
    ctx.clip(play, "evenodd");
    for (const c of seaEdge) fillTerrainBase(ctx, c.x * TILE, c.y * TILE, c.terr);
    ctx.restore();
  }
  if (landEdge.length) {
    const inv = new Path2D();
    inv.rect(-TILE, -TILE, map.w * TILE + TILE * 2, map.h * TILE + TILE * 2);
    inv.addPath(play);
    ctx.save();
    ctx.beginPath();
    for (const c of landEdge) ctx.rect(c.x * TILE, c.y * TILE, TILE, TILE);
    ctx.clip();
    ctx.clip(inv, "evenodd");
    for (const c of landEdge) fillTerrainBase(ctx, c.x * TILE, c.y * TILE, TERRAIN.SEA);
    ctx.restore();
  }
  ctx.save();
  ctx.clip(play, "evenodd");
  ctx.strokeStyle = "rgba(230, 212, 162, 0.95)";
  ctx.lineWidth = 8;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke(play);
  ctx.restore();
  ctx.strokeStyle = "rgba(18, 14, 10, 0.92)";
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke(play);
}

function fillTerrainBase(ctx, px, py, terr) {
  const key = TNAMES[terr] || "clear";
  const [c1, c2] = PAL[key];
  ctx.fillStyle = c1;
  ctx.fillRect(px, py, TILE, TILE);
  ctx.fillStyle = c2;
  for (let i = 0; i < TILE; i += 4) {
    for (let j = 0; j < TILE; j += 4) {
      if (((i + j) / 4) % 2 === 0) ctx.fillRect(px + i, py + j, 2, 2);
    }
  }
}

function blitCoast(ctx, coast, cam, vw, vh) {
  const overlay = coast.overlay;
  if (!overlay) return;
  const sx = Math.max(0, Math.floor(cam.x) - 2);
  const sy = Math.max(0, Math.floor(cam.y) - 2);
  const sw = Math.min(overlay.width - sx, Math.ceil(vw + (cam.x - sx) + 4));
  const sh = Math.min(overlay.height - sy, Math.ceil(vh + (cam.y - sy) + 4));
  if (sw <= 0 || sh <= 0) return;
  ctx.drawImage(overlay, sx, sy, sw, sh, sx, sy, sw, sh);
}

// Full-map paint used by the campaign view and by the atlas screenshot.
// Same shore geometry as the scrolling map, with no HUD crop.
export function paintFullMap(ctx, map, towns) {
  const board = boardImageOf(map);
  if (board) {
    drawBoardImage(ctx, map, board);
    const marks = playMarksOf(map);
    ctx.drawImage(marks.overlay, 0, 0);
    drawTownMarks(ctx, towns);
  } else {
    ctx.fillStyle = PAL.sea[0];
    ctx.fillRect(0, 0, map.w * TILE, map.h * TILE);
    for (let y = 0; y < map.h; y++) {
      for (let x = 0; x < map.w; x++) drawTileAt(ctx, map, towns, x, y, 0);
    }
    const coast = coastOf(map);
    ctx.drawImage(coast.overlay, 0, 0);
  }
  ctx.font = LABEL_FONT;
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  for (const lab of layoutTownLabels(ctx, towns)) paintOneLabel(ctx, lab);
  return coastOf(map).loops;
}

function drawTileAt(ctx, map, towns, x, y, time) {
  const t = terrainAt(map, x, y);
  const px = x * TILE;
  const py = y * TILE;
  ctx.lineWidth = 1;
  const key = TNAMES[t] || "clear";
  const [c1, c2] = PAL[key];
  ctx.fillStyle = c1;
  ctx.fillRect(px, py, TILE, TILE);
  ctx.fillStyle = c2;
  const phase = t === TERRAIN.SEA ? Math.floor(time * 2 + x) % 2 : 0;
  for (let i = 0; i < TILE; i += 4) {
    for (let j = 0; j < TILE; j += 4) {
      if (((i + j + phase * 2) / 4) % 2 === 0) ctx.fillRect(px + i, py + j, 2, 2);
    }
  }
  if (t === TERRAIN.FOREST) {
    ctx.fillStyle = "#1e331d";
    ctx.fillRect(px + 8, py + 10, 4, 12);
    ctx.fillRect(px + 20, py + 8, 4, 14);
    ctx.fillStyle = "#4a7a40";
    ctx.beginPath();
    ctx.moveTo(px + 10, py + 12);
    ctx.lineTo(px + 4, py + 20);
    ctx.lineTo(px + 16, py + 20);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(px + 22, py + 8);
    ctx.lineTo(px + 16, py + 18);
    ctx.lineTo(px + 28, py + 18);
    ctx.fill();
  }
  if (t === TERRAIN.HILL) {
    ctx.strokeStyle = "rgba(60,40,20,0.45)";
    ctx.beginPath();
    ctx.moveTo(px + 4, py + 22);
    ctx.quadraticCurveTo(px + 16, py + 8, px + 28, py + 22);
    ctx.stroke();
  }
  if (t === TERRAIN.RIVER) {
    ctx.fillStyle = "#2c5c82";
    ctx.fillRect(px + 10, py, 12, TILE);
  }
  if (t === TERRAIN.ROAD) {
    ctx.fillStyle = "#e6d09a";
    ctx.fillRect(px + 12, py, 8, TILE);
    ctx.fillRect(px, py + 12, TILE, 8);
  }
  if (t === TERRAIN.TOWN) {
    const town = towns.find((tw) => tw.x === x && tw.y === y);
    const owner = town ? town.owner : "english";
    ctx.fillStyle = owner === "norman" ? "#8e1b28" : owner === "norse" ? "#243656" : "#3a3a3a";
    ctx.fillRect(px + 7, py + 12, 8, 12);
    ctx.fillRect(px + 17, py + 10, 9, 14);
    ctx.fillStyle = "#c9b48a";
    ctx.beginPath();
    ctx.moveTo(px + 6, py + 12);
    ctx.lineTo(px + 11, py + 6);
    ctx.lineTo(px + 16, py + 12);
    ctx.fill();
    ctx.fillStyle = "#6a1c1c";
    ctx.beginPath();
    ctx.moveTo(px + 16, py + 10);
    ctx.lineTo(px + 21, py + 4);
    ctx.lineTo(px + 27, py + 10);
    ctx.fill();
  }
  if (t === TERRAIN.OUT) {
    ctx.strokeStyle = "rgba(48,40,32,0.55)";
    ctx.beginPath();
    for (let i = -TILE; i <= TILE; i += 8) {
      ctx.moveTo(px + i, py);
      ctx.lineTo(px + i + TILE, py + TILE);
    }
    ctx.stroke();
  }
  if (t === TERRAIN.SEA) {
    ctx.strokeStyle = "rgba(180,220,255,0.12)";
    ctx.beginPath();
    const oy = 8 + ((x * 3 + Math.floor(time * 6)) % 10);
    ctx.moveTo(px, py + oy);
    ctx.quadraticCurveTo(px + 16, py + oy - 3, px + 32, py + oy);
    ctx.stroke();
  } else if (!touchesSea(map, x, y)) {
    ctx.strokeStyle = PAL.grid;
    ctx.lineWidth = 1;
    ctx.strokeRect(px + 0.5, py + 0.5, TILE, TILE);
  }
}

function traceCoastLoops(map) {
  const DX = [1, 0, -1, 0];
  const DY = [0, 1, 0, -1];
  const edges = new Set();
  const add = (x, y, d) => edges.add(x + "," + y + "," + d);
  for (let y = 0; y < map.h; y++) {
    for (let x = 0; x < map.w; x++) {
      if (terrainAt(map, x, y) === TERRAIN.SEA) continue;
      if (terrainAt(map, x, y - 1) === TERRAIN.SEA) add(x + 1, y, 2);
      if (terrainAt(map, x, y + 1) === TERRAIN.SEA) add(x, y + 1, 0);
      if (terrainAt(map, x - 1, y) === TERRAIN.SEA) add(x, y, 1);
      if (terrainAt(map, x + 1, y) === TERRAIN.SEA) add(x + 1, y + 1, 3);
    }
  }
  const startAt = new Map();
  for (const key of edges) {
    const [x, y, d] = key.split(",").map(Number);
    const at = x + "," + y;
    if (!startAt.has(at)) startAt.set(at, []);
    startAt.get(at).push({ x, y, d, key });
  }
  const leftmost = (x, y, arrived) => {
    const order = [(arrived + 3) % 4, arrived, (arrived + 1) % 4, (arrived + 2) % 4];
    const cands = startAt.get(x + "," + y) || [];
    for (const d of order) {
      for (const e of cands) if (e.d === d) return e;
    }
    return null;
  };
  const unused = new Set(edges);
  const loops = [];
  for (const startKey of edges) {
    if (!unused.has(startKey)) continue;
    const [sx, sy, sd] = startKey.split(",").map(Number);
    let e = { x: sx, y: sy, d: sd, key: startKey };
    const loop = [];
    for (let guard = 0; guard < edges.size + 2; guard++) {
      if (!unused.has(e.key)) break;
      unused.delete(e.key);
      loop.push({ x: e.x, y: e.y });
      const nx = e.x + DX[e.d];
      const ny = e.y + DY[e.d];
      const nxt = leftmost(nx, ny, e.d);
      if (!nxt || nxt.key === startKey || !unused.has(nxt.key)) break;
      e = nxt;
    }
    if (loop.length > 2) loops.push(loop);
  }
  return loops;
}

function appendRoundedLoop(path, pts, scale, radius, roundness) {
  const simp = simplifyColinear(pts);
  const n = simp.length;
  if (n < 3) return;
  const segs = [];
  for (let i = 0; i < n; i++) {
    const prev = simp[(i - 1 + n) % n];
    const cur = simp[i];
    const next = simp[(i + 1) % n];
    const v1x = cur.x - prev.x;
    const v1y = cur.y - prev.y;
    const v2x = next.x - cur.x;
    const v2y = next.y - cur.y;
    const l1 = Math.hypot(v1x, v1y);
    const l2 = Math.hypot(v2x, v2y);
    if (l1 === 0 || l2 === 0) continue;
    const cut = Math.min(radius, l1 * 0.5, l2 * 0.5);
    const ax = cur.x - (v1x / l1) * cut;
    const ay = cur.y - (v1y / l1) * cut;
    const bx = cur.x + (v2x / l2) * cut;
    const by = cur.y + (v2y / l2) * cut;
    const mx = (ax + bx) / 2;
    const my = (ay + by) / 2;
    segs.push({
      ax,
      ay,
      cx: mx * (1 - roundness) + cur.x * roundness,
      cy: my * (1 - roundness) + cur.y * roundness,
      bx,
      by,
    });
  }
  if (segs.length < 3) return;
  const s0 = segs[0];
  path.moveTo(s0.ax * scale, s0.ay * scale);
  for (let i = 0; i < segs.length; i++) {
    const s = segs[i];
    path.quadraticCurveTo(s.cx * scale, s.cy * scale, s.bx * scale, s.by * scale);
    const na = segs[(i + 1) % segs.length];
    if (Math.abs(na.ax - s.bx) > 1e-4 || Math.abs(na.ay - s.by) > 1e-4) {
      path.lineTo(na.ax * scale, na.ay * scale);
    }
  }
  path.closePath();
}

function simplifyColinear(pts) {
  const n = pts.length;
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = pts[(i - 1 + n) % n];
    const b = pts[i];
    const c = pts[(i + 1) % n];
    const abx = b.x - a.x;
    const aby = b.y - a.y;
    const bcx = c.x - b.x;
    const bcy = c.y - b.y;
    const cross = abx * bcy - aby * bcx;
    const dot = abx * bcx + aby * bcy;
    if (cross !== 0 || dot < 0) out.push(b);
  }
  return out.length >= 3 ? out : pts;
}

function gmap(game) {
  return game.map;
}

function clamp(v, a, b) {
  return Math.max(a, Math.min(b, v));
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

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
