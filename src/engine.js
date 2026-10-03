import {
  DIRS,
  MAX_ORDERS,
  MOVE_COST,
  TERRAIN,
  TICKS_PER_TURN,
  TNAME,
  TURNS_TO_CHRISTMAS,
  englandLat,
  inBounds,
  isNavalTerrain,
  isPort,
  makeUnits,
  terrainAt,
  townAt,
  townByName,
} from "./world.js";

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function cloneTowns(towns) {
  return towns.map((t) => ({ ...t }));
}

export function createGame(map, difficulty = "normal", seed = 1066) {
  const game = {
    map,
    w: map.w,
    h: map.h,
    difficulty,
    seed,
    rng: mulberry32(seed),
    turn: 0,
    phase: "orders",
    tick: 0,
    weather: null,
    units: makeUnits(map),
    towns: cloneTowns(map.towns),
    cursor: { x: 0, y: 0 },
    selectedId: null,
    log: [],
    winner: null,
    score: 0,
    flash: [],
  };
  const william = unitById(game, "william");
  if (william) {
    game.cursor.x = william.x;
    game.cursor.y = william.y;
  }
  applyDifficulty(game);
  game.weather = rollWeather(game);
  log(game, "18 September 1066. Hardrada lies before York. Harold holds London. The Channel still pent you in.");
  return game;
}

function applyDifficulty(game) {
  const mul = game.difficulty === "easy" ? 0.85 : game.difficulty === "hard" ? 1.15 : 1;
  for (const u of game.units) {
    if (u.side === "english") {
      u.combat = Math.round(u.combat * mul);
      u.muster = Math.round(u.muster * (mul > 1 ? 1.05 : mul < 1 ? 0.95 : 1));
      u.maxMuster = u.muster;
    }
  }
}

export function log(game, msg) {
  game.log.unshift(msg);
  if (game.log.length > 14) game.log.pop();
}

export function living(game) {
  return game.units.filter((u) => u.alive && u.muster > 0);
}

export function unitById(game, id) {
  return game.units.find((u) => u.id === id) || null;
}

export function unitsAt(game, x, y) {
  return living(game).filter((u) => displayPos(game, u).x === x && displayPos(game, u).y === y);
}

export function landUnitAt(game, x, y) {
  return (
    living(game).find((u) => {
      const p = displayPos(game, u);
      return p.x === x && p.y === y && u.type !== "fleet" && !u.embarkedOn;
    }) || null
  );
}

export function displayPos(game, u) {
  if (u.embarkedOn) {
    const f = unitById(game, u.embarkedOn);
    if (f && f.alive) return { x: f.x, y: f.y };
  }
  return { x: u.x, y: u.y };
}

export function selectedUnit(game) {
  return game.selectedId ? unitById(game, game.selectedId) : null;
}

export function dateOf(game) {
  // 18 Sep 1066 + 4 days per turn
  let day = 18 + game.turn * 4;
  let month = 9;
  let year = 1066;
  const mdays = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  while (day > mdays[month]) {
    day -= mdays[month];
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  const names = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return { day, month, year, label: `${day} ${names[month]} ${year}` };
}

const WEATHERS = [
  { id: "fair", label: "Fair wind", seaMul: 1, landMul: 1, cross: true },
  { id: "breeze", label: "East wind", seaMul: 0.85, landMul: 1, cross: true },
  { id: "rain", label: "Rain and chop", seaMul: 1.25, landMul: 1.3, cross: true },
  { id: "gale", label: "Channel gale", seaMul: 8, landMul: 1.15, cross: false },
];

function galeChance(game) {
  const { month } = dateOf(game);
  let g = month === 9 ? 0.18 : month === 10 ? 0.3 : month === 11 ? 0.42 : 0.52;
  if (game.difficulty === "easy") g -= 0.08;
  if (game.difficulty === "hard") g += 0.08;
  return g;
}

export function rollWeather(game) {
  const g = galeChance(game);
  const r = game.rng();
  if (r < g) return WEATHERS[3];
  if (r < g + 0.28) return WEATHERS[2];
  if (r < g + 0.28 + 0.28) return WEATHERS[1];
  return WEATHERS[0];
}

export function moveCost(game, unit, x, y) {
  const terr = terrainAt(game.map, x, y);
  let type = unit.type;
  if (unit.embarkedOn) type = "fleet";
  const table = MOVE_COST[type] || MOVE_COST.infantry;
  let cost = table[terr];
  if (type === "fleet" && terr === TERRAIN.TOWN && !isPort(game.map, x, y)) return 99;
  if (unit.type !== "fleet" && !unit.embarkedOn && terr === TERRAIN.SEA) return 99;
  if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER || terr === TERRAIN.BEACH) {
    cost = Math.ceil(cost * game.weather.seaMul);
  } else {
    cost = Math.ceil(cost * game.weather.landMul);
  }
  if (!game.weather.cross && terr === TERRAIN.SEA) return 99;
  return cost;
}

export function canEnter(game, unit, x, y) {
  if (!inBounds(game.map, x, y)) return false;
  const terr = terrainAt(game.map, x, y);
  if (terr === TERRAIN.OUT) return false;
  if (unit.type === "fleet") {
    if (!isNavalTerrain(game.map, x, y)) return false;
    return moveCost(game, unit, x, y) < 90;
  }
  if (unit.embarkedOn) {
    if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER) return moveCost(game, unit, x, y) < 90;
    return terr !== TERRAIN.SEA;
  }
  if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER) {
    return living(game).some((f) => f.side === unit.side && f.type === "fleet" && f.alive);
  }
  return moveCost(game, unit, x, y) < 90;
}

export function enemyZoc(game, unit, x, y) {
  for (const [dx, dy] of Object.values(DIRS)) {
    const o = landUnitAt(game, x + dx, y + dy);
    if (o && o.side !== unit.side && o.type !== "fleet") return true;
  }
  return false;
}

function cargoOf(game, fleetId) {
  return living(game).filter((u) => u.embarkedOn === fleetId);
}

export function tryEmbark(game, unit, nx, ny) {
  const terr = terrainAt(game.map, nx, ny);
  if (terr !== TERRAIN.SEA && terr !== TERRAIN.RIVER) return false;
  const fleets = living(game).filter(
    (f) =>
      f.type === "fleet" &&
      f.side === unit.side &&
      Math.abs(f.x - unit.x) + Math.abs(f.y - unit.y) <= 1,
  );
  const roomy = fleets.find((f) => cargoOf(game, f.id).length < 3);
  if (!roomy) return false;
  unit.embarkedOn = roomy.id;
  unit.x = roomy.x;
  unit.y = roomy.y;
  return true;
}

export function tryDisembark(game, unit, nx, ny) {
  if (!unit.embarkedOn) return false;
  const terr = terrainAt(game.map, nx, ny);
  if (terr !== TERRAIN.BEACH && !isPort(game.map, nx, ny) && terr !== TERRAIN.CLEAR && terr !== TERRAIN.ROAD && terr !== TERRAIN.TOWN) {
    return false;
  }
  if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER) return false;
  unit.embarkedOn = null;
  unit.x = nx;
  unit.y = ny;
  return true;
}

export function pathToOrders(game, unit, tx, ty, limit = MAX_ORDERS) {
  const start = displayPos(game, unit);
  if (start.x === tx && start.y === ty) return [];
  const key = (x, y) => x + "," + y;
  const open = [{ x: start.x, y: start.y, g: 0, prev: null }];
  const best = new Map([[key(start.x, start.y), 0]]);
  let found = null;
  let guard = 0;
  while (open.length && guard++ < 2500) {
    open.sort((a, b) => a.g + Math.abs(a.x - tx) + Math.abs(a.y - ty) - (b.g + Math.abs(b.x - tx) + Math.abs(b.y - ty)));
    const cur = open.shift();
    if (cur.x === tx && cur.y === ty) {
      found = cur;
      break;
    }
    for (const [dir, [dx, dy]] of Object.entries(DIRS)) {
      const nx = cur.x + dx;
      const ny = cur.y + dy;
      if (!inBounds(game.map, nx, ny)) continue;
      const occ = landUnitAt(game, nx, ny);
      const isDest = nx === tx && ny === ty;
      if (occ && occ.id !== unit.id && occ.side === unit.side && !isDest) continue;
      if (!isDest && occ && occ.side !== unit.side) continue;
      if (!canEnter(game, unit, nx, ny) && !(isDest && occ && occ.side !== unit.side)) continue;
      const step = moveCost(game, unit, nx, ny);
      const g = cur.g + (step >= 90 ? 50 : step);
      const k = key(nx, ny);
      if (best.has(k) && best.get(k) <= g) continue;
      best.set(k, g);
      open.push({ x: nx, y: ny, g, prev: cur, dir });
    }
  }
  if (!found) return [];
  const dirs = [];
  let n = found;
  while (n && n.prev) {
    dirs.push(n.dir);
    n = n.prev;
  }
  dirs.reverse();
  return dirs.slice(0, limit);
}

export function orderPath(unit, game) {
  let mover = unit;
  if (game && unit.embarkedOn) {
    const f = unitById(game, unit.embarkedOn);
    if (f && f.alive) mover = f;
  }
  const start = game ? displayPos(game, mover) : { x: mover.x, y: mover.y };
  const pts = [{ x: start.x, y: start.y }];
  let x = start.x;
  let y = start.y;
  for (const d of mover.orders) {
    const [dx, dy] = DIRS[d];
    x += dx;
    y += dy;
    pts.push({ x, y });
  }
  return pts;
}

export function pickUp(game, unit) {
  if (!unit || !unit.alive || unit.side !== "norman") return;
  game.selectedId = unit.id;
  const p = orderPath(unit, game);
  const last = p[p.length - 1];
  game.cursor.x = last.x;
  game.cursor.y = last.y;
}

export function putDown(game) {
  game.selectedId = null;
}

export function addOrder(game, dir) {
  const u = selectedUnit(game);
  if (!u || game.phase !== "orders") return;
  const target = u.embarkedOn ? unitById(game, u.embarkedOn) || u : u;
  if (target.orders.length >= MAX_ORDERS) return;
  target.orders.push(dir);
}

export function cancelLast(game) {
  const u = selectedUnit(game);
  if (!u) return;
  const target = u.embarkedOn ? unitById(game, u.embarkedOn) || u : u;
  if (!target.orders.length) return;
  target.orders.pop();
  const p = orderPath(u, game);
  const last = p[p.length - 1];
  game.cursor.x = last.x;
  game.cursor.y = last.y;
}

export function clearOrders(game, unit) {
  const u = unit || selectedUnit(game);
  if (!u) return;
  u.orders = [];
  if (u.embarkedOn) {
    const f = unitById(game, u.embarkedOn);
    if (f) f.orders = [];
  }
}

export function setPathTo(game, x, y) {
  const u = selectedUnit(game);
  if (!u || game.phase !== "orders") return;
  const path = pathToOrders(game, u, x, y);
  if (u.embarkedOn) {
    const f = unitById(game, u.embarkedOn);
    if (f) f.orders = path;
    u.orders = [];
  } else {
    u.orders = path;
  }
  const p = orderPath(u, game);
  const last = p[p.length - 1];
  game.cursor.x = last.x;
  game.cursor.y = last.y;
}

export function moveCursor(game, dx, dy) {
  const nx = game.cursor.x + dx;
  const ny = game.cursor.y + dy;
  if (!inBounds(game.map, nx, ny)) return;
  game.cursor.x = nx;
  game.cursor.y = ny;
  if (game.selectedId && game.phase === "orders") {
    const dir = Object.entries(DIRS).find(([, v]) => v[0] === dx && v[1] === dy);
    if (dir) addOrder(game, dir[0]);
  }
}

export function cycleStack(game) {
  const stack = unitsAt(game, game.cursor.x, game.cursor.y).filter((u) => u.side === "norman");
  if (!stack.length) return;
  const i = stack.findIndex((u) => u.id === game.selectedId);
  pickUp(game, stack[(i + 1) % stack.length]);
}

export function nextNorman(game) {
  const mine = living(game).filter((u) => u.side === "norman");
  if (!mine.length) return;
  const i = mine.findIndex((u) => u.id === game.selectedId);
  const nxt = mine[(i + 1) % mine.length];
  pickUp(game, nxt);
}

function breakThreshold(u) {
  return Math.max(8, Math.floor(u.maxMuster * 0.9));
}

function inSupply(game, u) {
  const pos = displayPos(game, u);
  if (u.side === "norman" && !englandLat(pos.y)) return true;
  const sources = [];
  for (const t of game.towns) {
    if (t.owner === u.side) sources.push([t.x, t.y]);
  }
  if (u.side === "norman") {
    for (const f of living(game).filter((x) => x.side === "norman" && x.type === "fleet")) {
      sources.push([f.x, f.y]);
    }
  }
  if (u.side === "norse") {
    for (const f of living(game).filter((x) => x.side === "norse" && x.type === "fleet")) {
      sources.push([f.x, f.y]);
    }
  }
  if (!sources.length) return false;
  const key = (x, y) => x + "," + y;
  const seen = new Set([key(pos.x, pos.y)]);
  const q = [{ x: pos.x, y: pos.y, d: 0 }];
  while (q.length) {
    const cur = q.shift();
    if (sources.some(([sx, sy]) => sx === cur.x && sy === cur.y)) return true;
    if (cur.d >= 12) continue;
    for (const [dx, dy] of Object.values(DIRS)) {
      const nx = cur.x + dx;
      const ny = cur.y + dy;
      const k = key(nx, ny);
      if (seen.has(k) || !inBounds(game.map, nx, ny)) continue;
      const terr = terrainAt(game.map, nx, ny);
      if (terr === TERRAIN.OUT) continue;
      if (terr === TERRAIN.SEA && u.side !== "norman" && u.side !== "norse") continue;
      const enemy = landUnitAt(game, nx, ny);
      if (enemy && enemy.side !== u.side) continue;
      seen.add(k);
      q.push({ x: nx, y: ny, d: cur.d + 1 });
    }
  }
  return false;
}

function fight(game, a, b) {
  const strike = (atk, def, attacker) => {
    let str = atk.combat;
    if (!inSupply(game, atk)) str = Math.max(1, Math.floor(str / 2));
    if (atk.fatigue) str = Math.floor(str * (1 - 0.12 * atk.fatigue));
    const terr = terrainAt(game.map, def.x, def.y);
    if (!attacker && (terr === TERRAIN.TOWN || terr === TERRAIN.HILL)) str = Math.floor(str * 1.45);
    if (attacker && terr === TERRAIN.FOREST && atk.type === "knights") str = Math.floor(str * 0.7);
    if (attacker && atk.type === "archers") str = Math.floor(str * 1.12);
    if (!attacker && def.type === "housecarls") str = Math.floor(str * 1.1);
    const p = Math.min(0.72, str / 240);
    if (game.rng() < p) {
      def.combat = Math.max(0, def.combat - 4);
      def.muster = Math.max(0, def.muster - 1);
      def.flash = 1;
      return true;
    }
    return false;
  };
  strike(a, b, true);
  strike(b, a, false);
  a.fought = true;
  b.fought = true;
  if (b.combat < breakThreshold(b) && b.muster > 0) {
    b.broken = true;
    b.orders = [];
    log(game, `${b.name} breaks.`);
  }
  if (a.combat < breakThreshold(a) && a.muster > 0) {
    a.broken = true;
    a.orders = [];
    log(game, `${a.name} breaks.`);
  }
  if (b.muster <= 0) destroy(game, b, a);
  if (a.muster <= 0) destroy(game, a, b);
}

function destroy(game, dead, killer) {
  dead.alive = false;
  dead.muster = 0;
  dead.combat = 0;
  dead.orders = [];
  log(game, `${dead.name} is destroyed${killer ? " by " + killer.name : ""}.`);
  const near = living(game).filter(
    (u) => u.side === dead.side && Math.abs(u.x - dead.x) + Math.abs(u.y - dead.y) <= 2,
  );
  if (near.length) {
    const rec = near[0];
    rec.muster = Math.min(rec.maxMuster + 4, rec.muster + 2);
    rec.combat += 6;
  }
}

function retreatDir(game, u) {
  const enemies = living(game).filter((o) => o.side !== u.side);
  if (!enemies.length) return null;
  let best = null;
  let bestScore = -1e9;
  for (const [dir, [dx, dy]] of Object.entries(DIRS)) {
    const nx = u.x + dx;
    const ny = u.y + dy;
    if (!canEnter(game, u, nx, ny)) continue;
    if (landUnitAt(game, nx, ny)) continue;
    const d = enemies.reduce((s, e) => s + Math.abs(e.x - nx) + Math.abs(e.y - ny), 0);
    if (d > bestScore) {
      bestScore = d;
      best = dir;
    }
  }
  return best;
}

function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function beginResolve(game) {
  game.phase = "resolve";
  game.tick = 0;
  for (const u of living(game)) {
    u.progress = 0;
    u.fought = false;
  }
}

export function stepTick(game) {
  game.tick += 1;
  const order = shuffled(living(game), game.rng);
  for (const u of order) {
    if (!u.alive) continue;
    if (u.embarkedOn) {
      const f = unitById(game, u.embarkedOn);
      if (!f || !f.alive) {
        u.embarkedOn = null;
      } else {
        u.x = f.x;
        u.y = f.y;
      }
    }
    if (u.broken) {
      u.progress += 1;
      if (u.progress >= 4) {
        const d = retreatDir(game, u);
        if (d) {
          const [dx, dy] = DIRS[d];
          u.x += dx;
          u.y += dy;
        }
        u.progress = 0;
      }
      continue;
    }
    if (!u.orders.length) continue;
    const dir = u.orders[0];
    const [dx, dy] = DIRS[dir] || [0, 0];
    const from = displayPos(game, u);
    const nx = from.x + dx;
    const ny = from.y + dy;
    const cost = canEnter(game, u, nx, ny) ? moveCost(game, u, nx, ny) : 6;
    u.progress += 1;
    if (u.progress < Math.max(2, Math.min(cost, 16))) continue;

    if (!inBounds(game.map, nx, ny)) {
      u.orders.shift();
      u.progress = 0;
      continue;
    }

    const occ = landUnitAt(game, nx, ny);
    if (occ && occ.id !== u.id && occ.side === u.side) {
      continue;
    }
    if (occ && occ.side !== u.side) {
      fight(game, u, occ);
      u.progress = 0;
      continue;
    }

    if (enemyZoc(game, u, from.x, from.y) && enemyZoc(game, u, nx, ny)) {
      u.orders.shift();
      u.progress = 0;
      continue;
    }

    if (u.embarkedOn) {
      if (tryDisembark(game, u, nx, ny)) {
        u.orders.shift();
        u.progress = 0;
        continue;
      }
      const terr = terrainAt(game.map, nx, ny);
      if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER) {
        // cargo stays with the fleet; skip independent sea walking
        u.orders.shift();
        u.progress = 0;
        continue;
      }
    } else if (u.type !== "fleet") {
      const terr = terrainAt(game.map, nx, ny);
      if (terr === TERRAIN.SEA || terr === TERRAIN.RIVER) {
        if (tryEmbark(game, u, nx, ny)) {
          const rest = u.orders.slice(1);
          const f = unitById(game, u.embarkedOn);
          if (f) f.orders = [...f.orders, ...rest].slice(0, MAX_ORDERS);
          u.orders = [];
          u.progress = 0;
          continue;
        }
        u.orders.shift();
        u.progress = 0;
        continue;
      }
    }

    if (!canEnter(game, u, nx, ny)) {
      u.orders.shift();
      u.progress = 0;
      continue;
    }

    u.x = nx;
    u.y = ny;
    if (u.type === "fleet") {
      for (const c of cargoOf(game, u.id)) {
        c.x = nx;
        c.y = ny;
      }
    }
    u.orders.shift();
    u.progress = 0;
  }
  return game.tick >= TICKS_PER_TURN;
}

function captureTowns(game) {
  for (const t of game.towns) {
    const u = landUnitAt(game, t.x, t.y);
    if (u) t.owner = u.side;
  }
}

function englishLevies(game) {
  const landed = living(game).some(
    (u) => u.side === "norman" && u.type !== "fleet" && !u.embarkedOn && englandLat(u.y),
  );
  if (!landed) return;
  if (game.turn !== 6 && game.turn !== 9 && game.turn !== 12) return;
  const spots = ["Gloucester", "Oxford", "Lincoln"];
  const names = ["Gloucester Fyrd", "Oxford Fyrd", "Lindsey Fyrd"];
  const i = game.turn === 6 ? 0 : game.turn === 9 ? 1 : 2;
  const town = townByName({ towns: game.towns }, spots[i]);
  if (!town || town.owner !== "english") return;
  if (landUnitAt(game, town.x, town.y)) return;
  game.units.push({
    id: "levy" + game.turn,
    name: names[i],
    side: "english",
    type: "fyrd",
    x: town.x,
    y: town.y,
    muster: 10,
    combat: 36,
    maxMuster: 12,
    orders: [],
    progress: 0,
    broken: false,
    fatigue: 0,
    fought: false,
    embarkedOn: null,
    region: "south",
    flash: 0,
    alive: true,
    index: game.units.length,
  });
  log(game, `${names[i]} answers the fyrd-call at ${town.name}.`);
}

export function sideScore(game, side) {
  let s = 0;
  for (const t of game.towns) if (t.owner === side) s += t.value;
  return s;
}

export function checkVictory(game) {
  const london = game.towns.find((t) => t.name === "London");
  const winch = game.towns.find((t) => t.name === "Winchester");
  const harold = unitById(game, "harold");
  const william = unitById(game, "william");
  const hardrada = unitById(game, "hardrada");
  const williamDead = !william || !william.alive;
  const haroldDead = !harold || !harold.alive;
  game.score = sideScore(game, "norman") + (haroldDead ? 20 : 0) + (hardrada && !hardrada.alive ? 8 : 0);
  if (williamDead) {
    game.winner = "english";
    game.outcome = "William has fallen. The invasion dies with him.";
    return true;
  }
  if (london && london.owner === "norman" && ((winch && winch.owner === "norman") || haroldDead)) {
    game.winner = "norman";
    game.outcome = haroldDead
      ? "Harold is dead and London is yours. The Witan will come to heel."
      : "London and Winchester are yours. England has a new king.";
    return true;
  }
  if (game.turn >= TURNS_TO_CHRISTMAS) {
    if (london && london.owner === "norman") {
      game.winner = "norman";
      game.outcome = "Christmas, and London holds for William. The kingdom is his to keep.";
    } else {
      game.winner = "english";
      game.outcome = "Christmas, and London still holds for Harold. The invasion has spent itself.";
    }
    return true;
  }
  return false;
}

export function applyUpkeep(game) {
  captureTowns(game);
  for (const u of living(game)) {
    const supplied = inSupply(game, u);
    u.supplied = supplied;
    if (supplied) {
      u.combat = Math.min(u.muster * 5, u.combat + 2);
      if (u.side === "english" && u.type === "fyrd") {
        u.muster = Math.min(u.maxMuster, u.muster + 1);
      }
    } else {
      if (game.rng() < 0.18) u.muster = Math.max(1, u.muster - 1);
      u.combat = Math.min(u.combat, u.muster * 4);
    }
    if (u.fought) u.fatigue = Math.min(3, u.fatigue + 1);
    else u.fatigue = Math.max(0, u.fatigue - 1);
    if (u.broken && u.combat >= 12) u.broken = false;
  }
  englishLevies(game);
  game.turn += 1;
  game.weather = rollWeather(game);
  const d = dateOf(game);
  log(game, `${d.label}. ${game.weather.label}.`);
  if (checkVictory(game)) {
    game.phase = "ended";
    log(game, game.outcome);
    return;
  }
  game.phase = "orders";
  game.tick = 0;
}

export function tileInfo(game, x, y) {
  const terr = TNAME[terrainAt(game.map, x, y)];
  const town = game.towns.find((t) => t.x === x && t.y === y);
  const stack = unitsAt(game, x, y);
  return { terr, town, stack };
}

export { inSupply };
