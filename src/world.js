export const TERRAIN = {
  SEA: 0,
  BEACH: 1,
  CLEAR: 2,
  FOREST: 3,
  HILL: 4,
  MARSH: 5,
  RIVER: 6,
  ROAD: 7,
  TOWN: 8,
};

export const TNAME = [
  "sea",
  "beach",
  "clear",
  "forest",
  "hill",
  "marsh",
  "river",
  "road",
  "town",
];

export const DIRS = {
  N: [0, -1],
  S: [0, 1],
  E: [1, 0],
  W: [-1, 0],
};

export const DIR_KEYS = {
  ArrowUp: "N",
  ArrowDown: "S",
  ArrowLeft: "W",
  ArrowRight: "E",
  w: "N",
  s: "S",
  a: "W",
  d: "E",
  W: "N",
  S: "S",
  A: "W",
  D: "E",
};

// Indexed by terrain enum. 99 = impassable.
export const MOVE_COST = {
  knights: [99, 5, 4, 12, 8, 16, 10, 3, 4],
  infantry: [99, 6, 6, 8, 8, 12, 10, 4, 5],
  archers: [99, 6, 6, 8, 8, 12, 10, 4, 5],
  housecarls: [99, 6, 6, 8, 7, 12, 10, 4, 5],
  fyrd: [99, 7, 7, 10, 9, 14, 12, 5, 6],
  huscarls: [99, 6, 6, 8, 8, 12, 10, 4, 5],
  fleet: [3, 4, 99, 99, 99, 99, 4, 99, 4],
};

export const TYPE_LABEL = {
  knights: "Knights",
  infantry: "Infantry",
  archers: "Archers",
  housecarls: "Housecarls",
  fyrd: "Fyrd",
  huscarls: "Huscarls",
  fleet: "Fleet",
};

export const SIDE_LABEL = {
  norman: "Norman",
  english: "English",
  norse: "Norse",
};

export async function loadMap() {
  const res = await fetch("data/map.json");
  if (!res.ok) throw new Error("Could not load map");
  return res.json();
}

export function idx(map, x, y) {
  return y * map.w + x;
}

export function inBounds(map, x, y) {
  return x >= 0 && y >= 0 && x < map.w && y < map.h;
}

export function terrainAt(map, x, y) {
  if (!inBounds(map, x, y)) return TERRAIN.SEA;
  return map.terrain[idx(map, x, y)];
}

export function townAt(map, x, y) {
  return map.towns.find((t) => t.x === x && t.y === y) || null;
}

export function townByName(map, name) {
  return map.towns.find((t) => t.name === name) || null;
}

export function isPort(map, x, y) {
  const t = townAt(map, x, y);
  return !!(t && t.port);
}

export function isNavalTerrain(map, x, y) {
  const t = terrainAt(map, x, y);
  return t === TERRAIN.SEA || t === TERRAIN.BEACH || t === TERRAIN.RIVER || isPort(map, x, y);
}

export function englandLat(y) {
  return y <= 46;
}

function occupyKey(x, y) {
  return x + "," + y;
}

function placeNear(map, taken, x, y, naval) {
  const q = [[x, y]];
  const seen = new Set([occupyKey(x, y)]);
  while (q.length) {
    const [cx, cy] = q.shift();
    const terr = terrainAt(map, cx, cy);
    const ok = naval ? isNavalTerrain(map, cx, cy) : terr !== TERRAIN.SEA;
    if (ok && !taken.has(occupyKey(cx, cy))) {
      taken.add(occupyKey(cx, cy));
      return { x: cx, y: cy };
    }
    for (const [dx, dy] of Object.values(DIRS)) {
      const nx = cx + dx;
      const ny = cy + dy;
      const k = occupyKey(nx, ny);
      if (inBounds(map, nx, ny) && !seen.has(k)) {
        seen.add(k);
        q.push([nx, ny]);
      }
    }
  }
  taken.add(occupyKey(x, y));
  return { x, y };
}

function spec(id, name, side, type, town, muster, combat, opts = {}) {
  return { id, name, side, type, town, muster, combat, ...opts };
}

export function makeUnits(map) {
  const taken = new Set();
  const raw = [
    spec("william", "William", "norman", "knights", "St-Valery", 32, 160),
    spec("odo", "Odo of Bayeux", "norman", "knights", "Bayeux", 18, 90),
    spec("mortain", "Robert of Mortain", "norman", "knights", "Caen", 16, 80),
    spec("alan", "Alan of Brittany", "norman", "knights", "Dives", 16, 80),
    spec("eustace", "Eustace of Boulogne", "norman", "knights", "St-Valery", 14, 70),
    spec("fitz", "William fitzOsbern", "norman", "infantry", "Rouen", 18, 85),
    spec("ninf1", "Norman Foot", "norman", "infantry", "Caen", 16, 75),
    spec("ninf2", "Cotentin Foot", "norman", "infantry", "Bayeux", 14, 65),
    spec("narch1", "Norman Archers", "norman", "archers", "Dives", 14, 70),
    spec("narch2", "Bow of Eu", "norman", "archers", "St-Valery", 12, 60),
    spec("nfleet1", "Norman Fleet", "norman", "fleet", "St-Valery", 20, 40, { naval: true }),
    spec("nfleet2", "Dive Fleet", "norman", "fleet", "Dives", 16, 32, { naval: true }),

    spec("harold", "Harold Godwinson", "english", "housecarls", "London", 30, 150, { region: "royal" }),
    spec("gyrth", "Gyrth", "english", "housecarls", "London", 18, 90, { region: "royal" }),
    spec("leofwine", "Leofwine", "english", "housecarls", "Winchester", 16, 80, { region: "royal" }),
    spec("edwin", "Edwin of Mercia", "english", "housecarls", "York", 16, 80, { region: "north" }),
    spec("morcar", "Morcar", "english", "housecarls", "York", 16, 80, { region: "north" }),
    spec("efyrd1", "London Fyrd", "english", "fyrd", "London", 14, 50, { region: "south" }),
    spec("efyrd2", "Wessex Fyrd", "english", "fyrd", "Winchester", 14, 48, { region: "south" }),
    spec("efyrd3", "Kent Fyrd", "english", "fyrd", "Canterbury", 12, 42, { region: "south" }),
    spec("efyrd4", "Mercia Fyrd", "english", "fyrd", "Nottingham", 12, 40, { region: "north" }),
    spec("efyrd5", "Northumbrian Fyrd", "english", "fyrd", "Durham", 12, 40, { region: "north" }),
    spec("efyrd6", "East Anglian Fyrd", "english", "fyrd", "Norwich", 10, 36, { region: "south" }),

    spec("hardrada", "Harald Hardrada", "norse", "huscarls", "York", 28, 140, { dy: 1 }),
    spec("tostig", "Tostig", "norse", "huscarls", "York", 18, 85, { dy: 1, dx: 1 }),
    spec("nhusc1", "Norwegian Huscarls", "norse", "huscarls", "York", 16, 75, { dy: 2 }),
    spec("nhusc2", "Orkney Men", "norse", "huscarls", "York", 14, 65, { dx: -1, dy: 1 }),
    spec("nfleet", "Norse Fleet", "norse", "fleet", "York", 18, 36, { naval: true }),
  ];

  return raw.map((s, i) => {
    const town = townByName(map, s.town);
    const ox = (town ? town.x : 20) + (s.dx || 0);
    const oy = (town ? town.y : 20) + (s.dy || 0);
    const pos = placeNear(map, taken, ox, oy, s.naval || s.type === "fleet");
    return {
      id: s.id,
      name: s.name,
      side: s.side,
      type: s.type,
      x: pos.x,
      y: pos.y,
      muster: s.muster,
      combat: s.combat,
      maxMuster: s.muster,
      orders: [],
      progress: 0,
      broken: false,
      fatigue: 0,
      fought: false,
      embarkedOn: null,
      region: s.region || null,
      flash: 0,
      alive: true,
      supplied: true,
      index: i,
    };
  });
}

export const TICKS_PER_TURN = 32;
export const MAX_ORDERS = 8;
export const TURNS_TO_CHRISTMAS = 24;
