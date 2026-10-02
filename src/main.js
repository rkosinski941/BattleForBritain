import { loadMap } from "./world.js";
import { createGame } from "./engine.js";
import { GameView } from "./view.js";

const title = document.getElementById("title");
const howto = document.getElementById("howto");
const gameRoot = document.getElementById("game");
const canvas = document.getElementById("map");
const hud = document.getElementById("hud");
const endScreen = document.getElementById("end");
const endText = document.getElementById("end-text");
const endScore = document.getElementById("end-score");

let view = null;
let mapData = null;

loadMap()
  .then((data) => {
    mapData = data;
    document.getElementById("play").disabled = false;
  })
  .catch((err) => {
    document.getElementById("play").textContent = "Map failed to load";
    console.error(err);
  });

document.getElementById("play").addEventListener("click", () => start());
document.getElementById("open-help").addEventListener("click", () => {
  howto.hidden = false;
});
document.getElementById("close-help").addEventListener("click", () => {
  howto.hidden = true;
});
document.getElementById("again").addEventListener("click", () => {
  endScreen.hidden = true;
  title.hidden = false;
});

function start() {
  if (!mapData) return;
  const difficulty = document.getElementById("diff").value;
  const seed = (Date.now() ^ 1066) >>> 0;
  const game = createGame(mapData, difficulty, seed);
  title.hidden = true;
  howto.hidden = true;
  endScreen.hidden = true;
  gameRoot.hidden = false;
  if (view) view.destroy();
  view = new GameView(canvas, hud, game, showEnd);
}

function showEnd(game) {
  endScreen.hidden = false;
  endText.textContent = game.outcome || "The campaign is over.";
  endScore.textContent = `Norman score ${game.score}. London is held by the ${
    game.towns.find((t) => t.name === "London")?.owner || "unknown"
  }.`;
}
